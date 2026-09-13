import aiosqlite
import json
from config import DB_PATH

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                file_ids TEXT,
                thumb_paths TEXT,
                caption TEXT,
                buttons_json TEXT,
                button_layout TEXT DEFAULT 'vertical',
                scheduled_time TEXT NOT NULL,
                timezone TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS vip_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                channel_id INTEGER NOT NULL,
                vip_sequence INTEGER NOT NULL,
                join_date TEXT NOT NULL,
                expiry_date TEXT NOT NULL,
                status TEXT DEFAULT 'ACTIVE',
                reminded INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS counters (
                name TEXT PRIMARY KEY,
                val INTEGER DEFAULT 0
            )
        """)
        await db.execute("INSERT OR IGNORE INTO counters (name, val) VALUES ('vip_seq', 0)")
        await db.commit()

async def get_next_vip_sequence() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE counters SET val = val + 1 WHERE name = 'vip_seq'")
        await db.commit()
        async with db.execute("SELECT val FROM counters WHERE name = 'vip_seq'") as cursor:
            row = await cursor.fetchone()
            return row[0]

async def add_scheduled_post(channel_id: int, content_type: str, file_ids: list, thumb_paths: list,
                             caption: str, buttons: list, layout: str, scheduled_time: str, tz: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO scheduled_posts (
                channel_id, content_type, file_ids, thumb_paths, caption, 
                buttons_json, button_layout, scheduled_time, timezone, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
        """, (
            channel_id, content_type, json.dumps(file_ids), json.dumps(thumb_paths),
            caption, json.dumps(buttons), layout, scheduled_time, tz
        ))
        await db.commit()
        return cursor.lastrowid

async def get_scheduled_post(post_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM scheduled_posts WHERE id = ?", (post_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_all_pending_posts():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM scheduled_posts WHERE status = 'PENDING' ORDER BY scheduled_time ASC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def update_post_status(post_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE scheduled_posts SET status = ? WHERE id = ?", (status, post_id))
        await db.commit()

async def update_post_caption(post_id: int, caption: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE scheduled_posts SET caption = ? WHERE id = ?", (caption, post_id))
        await db.commit()

async def delete_scheduled_post(post_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM scheduled_posts WHERE id = ?", (post_id,))
        await db.commit()

async def add_vip_member(user_id: int, username: str, channel_id: int, seq: int, join_date: str, expiry_date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO vip_members (user_id, username, channel_id, vip_sequence, join_date, expiry_date, status, reminded)
            VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', 0)
        """, (user_id, username, channel_id, seq, join_date, expiry_date))
        await db.commit()

async def get_active_vip_members():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM vip_members WHERE status = 'ACTIVE'") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_vip_record_by_user(user_id: int, channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM vip_members WHERE user_id = ? AND channel_id = ? ORDER BY id DESC LIMIT 1", (user_id, channel_id)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def renew_vip_member(record_id: int, new_expiry_date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE vip_members SET expiry_date = ?, status = 'ACTIVE', reminded = 0 WHERE id = ?", (new_expiry_date, record_id))
        await db.commit()

async def mark_vip_reminded(record_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE vip_members SET reminded = 1 WHERE id = ?", (record_id,))
        await db.commit()

async def revoke_vip_member(record_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE vip_members SET status = 'EXPIRED' WHERE id = ?", (record_id,))
        await db.commit()
