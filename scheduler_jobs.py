import os
import json
import pytz
from datetime import datetime, timedelta
from pyrogram import Client
from pyrogram.types import InputMediaPhoto, InputMediaVideo, InputMediaDocument
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import database
from formatter import build_glass_buttons

scheduler = AsyncIOScheduler()

async def execute_scheduled_post(bot: Client, post_id: int):
    post = await database.get_scheduled_post(post_id)
    if not post or post["status"] != "PENDING":
        return

    channel_id = post["channel_id"]
    content_type = post["content_type"]
    file_ids = json.loads(post["file_ids"]) if post["file_ids"] else []
    thumb_paths = json.loads(post["thumb_paths"]) if post["thumb_paths"] else []
    caption = post["caption"]
    buttons_data = json.loads(post["buttons_json"]) if post["buttons_json"] else []
    layout = post.get("button_layout", "vertical")
    markup = build_glass_buttons(buttons_data, layout=layout)

    try:
        if content_type == "text":
            await bot.send_message(channel_id, text=caption, reply_markup=markup, disable_web_page_preview=True)

        elif content_type == "single_media":
            fid = file_ids[0]
            thumb = thumb_paths[0] if thumb_paths and os.path.exists(thumb_paths[0]) else None
            if str(fid).endswith((".jpg", ".png", ".jpeg")):
                await bot.send_photo(channel_id, photo=fid, caption=caption, reply_markup=markup)
            elif str(fid).endswith((".mp4", ".mkv", ".mov")):
                await bot.send_video(channel_id, video=fid, caption=caption, thumb=thumb, reply_markup=markup)
            else:
                await bot.send_document(channel_id, document=fid, caption=caption, thumb=thumb, reply_markup=markup)

        elif content_type == "media_batch":
            media_group = []
            for idx, fid in enumerate(file_ids):
                current_caption = caption if idx == 0 else ""
                thumb = thumb_paths[idx] if idx < len(thumb_paths) and os.path.exists(thumb_paths[idx]) else None
                if str(fid).endswith((".mp4", ".mkv")):
                    media_group.append(InputMediaVideo(media=fid, caption=current_caption, thumb=thumb))
                elif str(fid).endswith((".jpg", ".png", ".jpeg")):
                    media_group.append(InputMediaPhoto(media=fid, caption=current_caption))
                else:
                    media_group.append(InputMediaDocument(media=fid, caption=current_caption, thumb=thumb))

            if media_group:
                await bot.send_media_group(channel_id, media=media_group)
                if markup:
                    await bot.send_message(channel_id, text="🔗 **Access Links:**", reply_markup=markup)

        await database.update_post_status(post_id, "PUBLISHED")
    except Exception as e:
        print(f"[Post Failed] ID: {post_id} - Error: {e}")
        await database.update_post_status(post_id, f"FAILED: {e}")

async def audit_vip_expirations(bot: Client):
    """
    Checks active subscriptions hourly, issues 24h reminders, and revokes expired members.
    """
    now = datetime.now(pytz.utc)
    active_members = await database.get_active_vip_members()

    for mem in active_members:
        rec_id = mem["id"]
        user_id = mem["user_id"]
        chan_id = mem["channel_id"]
        exp_dt = datetime.fromisoformat(mem["expiry_date"]).astimezone(pytz.utc)

        # 24-Hour Expiry Warning
        if (exp_dt - now) <= timedelta(hours=24) and mem["reminded"] == 0 and now < exp_dt:
            try:
                await bot.send_message(
                    user_id,
                    "⏳ **VIP Renewal Notice**\n\n"
                    f"Your VIP access for `{config.VIP_CHANNELS.get(chan_id, {}).get('name', 'VIP Hub')}` "
                    "will expire in less than **24 hours**.\n"
                    "Use `/start` to renew immediately to maintain uninterrupted access."
                )
                await bot.send_message(
                    config.ADMIN_ID,
                    f"🔔 **Audit Reminder**: VIP member `{user_id}` (@{mem['username']}) will expire in 24 hours."
                )
                await database.mark_vip_reminded(rec_id)
            except Exception:
                pass

        # Revocation upon Expiry
        elif now >= exp_dt:
            try:
                await bot.ban_chat_member(chan_id, user_id)
                await bot.unban_chat_member(chan_id, user_id)

                await bot.send_message(
                    user_id,
                    "🚫 **VIP Access Expired**\n\n"
                    f"Your access to `{config.VIP_CHANNELS.get(chan_id, {}).get('name', 'VIP Hub')}` has ended.\n"
                    "Use `/start` to purchase a renewal pass and re-enter anytime."
                )
                await bot.send_message(
                    config.ADMIN_ID,
                    f"🚫 **Access Revoked**: Removed expired user `{user_id}` (@{mem['username']}) from `{chan_id}`."
                )
            except Exception as e:
                print(f"[Audit Revocation Failed] User: {user_id} - Error: {e}")

            await database.revoke_vip_member(rec_id)

async def load_persistent_jobs(bot: Client):
    """
    Recovers all pending posts from SQLite upon bot startup to survive restarts.
    """
    pending_posts = await database.get_all_pending_posts()
    now_utc = datetime.now(pytz.utc)

    for p in pending_posts:
        run_dt = datetime.fromisoformat(p["scheduled_time"]).astimezone(pytz.utc)
        if run_dt <= now_utc:
            # Execute overdue post immediately
            await execute_scheduled_post(bot, p["id"])
        else:
            scheduler.add_job(
                execute_scheduled_post,
                trigger="date",
                run_date=run_dt,
                args=[bot, p["id"]],
                id=f"post_{p['id']}",
                replace_existing=True
            )

def init_scheduler(bot: Client):
    scheduler.add_job(audit_vip_expirations, "interval", hours=1, args=[bot])
    scheduler.start()
