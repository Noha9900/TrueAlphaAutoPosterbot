import os
import subprocess
import zipfile
from pathlib import Path

def get_media_duration(file_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    try:
        res = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        return float(res)
    except Exception:
        return 60.0

def extract_screenshots(video_path: str, output_dir: str, count: int = 10) -> list:
    """
    Extracts up to 100 equidistant video frames across total duration using FFmpeg.
    """
    count = max(1, min(100, count))
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    duration = get_media_duration(video_path)
    interval = duration / (count + 1)
    extracted_frames = []

    for i in range(1, count + 1):
        timestamp = interval * i
        frame_file = out_path / f"frame_{i:03d}.jpg"
        cmd = [
            "ffmpeg", "-ss", str(timestamp), "-i", video_path,
            "-frames:v", "1", "-q:v", "2", "-y", str(frame_file)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if frame_file.exists():
            extracted_frames.append(str(frame_file))

    return extracted_frames

def extract_video_from_archive(archive_path: str, output_dir: str) -> str | None:
    """
    Finds and extracts the first video file found within a ZIP archive.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm')

    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path, 'r') as z:
            for filename in z.namelist():
                if filename.lower().endswith(video_extensions):
                    return z.extract(filename, path=output_dir)
    return None
