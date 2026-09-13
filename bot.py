import os
import shutil
import pytz
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, InputMediaPhoto
)

import config
import database
import formatter
import media_tools
import receipt_engine
import scheduler_jobs

app = Client(
    "CentralPublishBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

# In-Memory State Machine: user_id -> {"action": ..., "data": ...}
USER_SESSIONS = {}

# ----------------- BEAUTIFUL WELCOME ENTRY -----------------
@app.on_message(filters.command("start") & filters.private)
async def start_entry(client: Client, message: Message):
    uid = message.from_user.id
    USER_SESSIONS.pop(uid, None)

    welcome_text = (
        "✨ <b>WELCOME TO CENTRAL DISPATCH &amp; VIP AUTOMATION</b> ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Hello, <b>{message.from_user.first_name}</b>!\n\n"
        "⚡ <b>Core Engine Capabilities:</b>\n"
        "• <b>Expandable Formatter:</b> Interactive TrueAlpha dropdown blocks\n"
        "• <b>Glass Button Builder:</b> Colored action gems (Horizontal / Vertical)\n"
        "• <b>Smart Scheduling:</b> Date &amp; timezone publishing with IST quickset\n"
        "• <b>Dynamic Covers:</b> Single and sequential episode thumbnail mappers\n"
        "• <b>Frame Grabber:</b> Instant extraction of up to 100 screenshots\n"
        "• <b>VIP System:</b> Automated TON &amp; PayPal billing with branded card passes\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Select an operation from the menu below to begin:</i>"
    )

    buttons = [
        [InlineKeyboardButton("💎 VIP Membership Directory", callback_data="vip_directory")],
        [InlineKeyboardButton("📸 Extract Video Screenshots", callback_data="tool_screens")],
    ]
    if uid == config.ADMIN_ID:
        buttons.append([InlineKeyboardButton("📝 Create & Schedule Post", callback_data="post_wizard")])
        buttons.append([InlineKeyboardButton("🗂️ Manage Scheduled Queue", callback_data="list_schedules")])

    await message.reply(welcome_text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

# ----------------- VIP PURCHASE & GATEWAYS -----------------
@app.on_callback_query(filters.regex("^vip_directory$"))
async def vip_directory(client: Client, query: CallbackQuery):
    buttons = []
    for cid, data in config.VIP_CHANNELS.items():
        buttons.append([InlineKeyboardButton(f"{data['name']} ({data['price']})", callback_data=f"buyvip_{cid}")])
    buttons.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")])
    await query.message.edit_text(
        "💎 <b>VIP Membership Access Hub</b>\n\n"
        "Select a channel below to subscribe and unlock instant exclusive access:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r"^buyvip_(-?\d+)"))
async def vip_checkout_selection(client: Client, query: CallbackQuery):
    cid = int(query.matches[0].group(1))
    chan_info = config.VIP_CHANNELS.get(cid)
    USER_SESSIONS[query.from_user.id] = {"action": "VIP_CHECKOUT", "channel_id": cid}

    buttons = [
        [InlineKeyboardButton("💳 Pay via PayPal (QR & Link)", callback_data="pay_paypal")],
        [InlineKeyboardButton("💎 Pay via TON Crypto (QR & Wallet)", callback_data="pay_ton")],
        [InlineKeyboardButton("🔙 Back to Directory", callback_data="vip_directory")]
    ]
    await query.message.edit_text(
        f"🌟 <b>Channel:</b> <code>{chan_info['name']}</code>\n"
        f"💰 <b>Subscription Cost:</b> <code>{chan_info['price']}</code>\n"
        f"👤 <b>Subscriber Tag:</b> @{query.from_user.username or 'User'}\n"
        f"🆔 <b>Account ID:</b> <code>{query.from_user.id}</code>\n\n"
        "Select your payment method below:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex("^pay_ton$"))
async def pay_ton_handler(client: Client, query: CallbackQuery):
    qr_file = receipt_engine.generate_ton_invoice_qr()
    caption = (
        "💎 <b>TON Payment Gateway</b>\n\n"
        f"<b>Destination Wallet Address:</b>\n<code>{config.TON_WALLET}</code>\n\n"
        "1. Scan the QR code or copy the address above.\n"
        "2. Complete the payment transfer in your TON wallet.\n"
        "3. <b>Reply to this bot with your payment proof</b> (Transaction hash or screenshot)."
    )
    await query.message.reply_photo(photo=qr_file, caption=caption)
    if os.path.exists(qr_file):
        os.remove(qr_file)

@app.on_callback_query(filters.regex("^pay_paypal$"))
async def pay_paypal_handler(client: Client, query: CallbackQuery):
    qr_file = receipt_engine.generate_paypal_invoice_qr()
    caption = (
        "💳 <b>PayPal Payment Gateway</b>\n\n"
        f"<b>Direct Payment Link:</b> <a href=\"{config.PAYPAL_LINK}\">Click here to pay</a>\n\n"
        "1. Scan the QR or open the link to complete payment.\n"
        "2. <b>Reply to this bot with your payment proof</b> (Screenshot or Transaction ID)."
    )
    await query.message.reply_photo(photo=qr_file, caption=caption)
    if os.path.exists(qr_file):
        os.remove(qr_file)

# ----------------- ADMIN VERIFICATION & PASS ISSUANCE -----------------
@app.on_callback_query(filters.regex(r"^appr_(\d+)_(-?\d+)"))
async def admin_approve_vip(client: Client, query: CallbackQuery):
    uid = int(query.matches[0].group(1))
    cid = int(query.matches[0].group(2))

    existing_record = await database.get_vip_record_by_user(uid, cid)
    user_info = await client.get_users(uid)
    join_dt = datetime.now().strftime("%Y-%m-%d")
    expiry_dt = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    # Download channel logo if available
    logo_file = None
    try:
        chat = await client.get_chat(cid)
        if chat.photo:
            logo_file = await client.download_media(chat.photo.big_file_id, file_name=str(config.TEMP_DIR / f"logo_{cid}.jpg"))
    except Exception:
        pass

    if existing_record:
        seq_no = existing_record["vip_sequence"]
        await database.renew_vip_member(existing_record["id"], (datetime.now() + timedelta(days=30)).isoformat())
    else:
        seq_no = await database.get_next_vip_sequence()
        await database.add_vip_member(
            user_id=uid,
            username=user_info.username or str(uid),
            channel_id=cid,
            seq=seq_no,
            join_date=datetime.now().isoformat(),
            expiry_date=(datetime.now() + timedelta(days=30)).isoformat()
        )

    # Generate Image Receipt Pass
    card_path = receipt_engine.generate_vip_card(
        user_name=user_info.first_name or "Subscriber",
        user_id=uid,
        vip_count=seq_no,
        channel_name=config.VIP_CHANNELS.get(cid, {}).get("name", "VIP Channel"),
        join_date=join_dt,
        expiry_date=expiry_dt,
        logo_path=logo_file
    )

    # Generate Single-Use Invite Link
    invite_link = await client.create_chat_invite_link(chat_id=cid, member_limit=1)

    caption = (
        "🎉 <b>PAYMENT VERIFIED! WELCOME TO VIP MEMBERSHIP</b>\n\n"
        f"🏷️ <b>VIP Member Tag:</b> <code>{user_info.first_name.upper()} #{seq_no:02d}</code>\n"
        f"📅 <b>Expiry Date:</b> <code>{expiry_dt}</code>\n"
        f"🔗 <b>Single-Use Channel Link:</b> {invite_link.invite_link}\n\n"
        "Enjoy your VIP access! Please do not share your link; it expires upon first use."
    )
    await client.send_photo(chat_id=uid, photo=card_path, caption=caption)

    if card_path and os.path.exists(card_path):
        os.remove(card_path)
    if logo_file and os.path.exists(logo_file):
        os.remove(logo_file)

    await query.message.edit_text(f"✅ Approved user `{uid}`. VIP Pass `#{seq_no:02d}` dispatched.")

@app.on_callback_query(filters.regex(r"^rjct_(\d+)"))
async def admin_reject_vip(client: Client, query: CallbackQuery):
    uid = int(query.matches[0].group(1))
    await client.send_message(uid, "❌ <b>Payment Submission Declined.</b> Please check transaction details and try again.")
    await query.message.edit_text(f"Declined payment verification for user `{uid}`.")

# ----------------- HIGH-SPEED SCREENSHOT EXTRACTOR -----------------
@app.on_message(filters.command("screenshot") & filters.private)
@app.on_callback_query(filters.regex("^tool_screens$"))
async def tool_screens(client: Client, event: Message | CallbackQuery):
    uid = event.from_user.id
    USER_SESSIONS[uid] = {"action": "WAIT_SCREEN_MEDIA"}
    prompt = (
        "📸 <b>High-Speed Screenshot Extractor</b>\n\n"
        "Send the video file or ZIP archive containing video.\n"
        "<i>(Supports extracting up to 100 equidistant frames).</i>"
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(prompt)
    else:
        await event.reply(prompt)

@app.on_message(filters.private & (filters.video | filters.document))
async def handle_media_incoming(client: Client, message: Message):
    uid = message.from_user.id
    session = USER_SESSIONS.get(uid, {})

    # Frame Extraction Pipeline
    if session.get("action") == "WAIT_SCREEN_MEDIA":
        status_msg = await message.reply("⏳ <i>Downloading media for frame extraction...</i>")
        downloaded = await message.download(file_name=str(config.TEMP_DIR / f"raw_{uid}.mp4"))

        target_file = downloaded
        if str(downloaded).endswith(".zip"):
            extracted = media_tools.extract_video_from_archive(downloaded, str(config.TEMP_DIR / f"unzip_{uid}"))
            if extracted:
                target_file = extracted

        USER_SESSIONS[uid] = {"action": "WAIT_SCREEN_COUNT", "video_path": target_file}
        await status_msg.edit_text("🎞️ How many frames to extract? (Enter a number between <b>1 and 100</b>):")
        return

    # Post Creator Media Collectors
    if session.get("action") == "WAIT_POST_MEDIA":
        file_id = message.video.file_id if message.video else message.document.file_id
        session.setdefault("media_files", []).append(file_id)
        count = len(session["media_files"])
        btn = [[InlineKeyboardButton(f"✅ Finished Media Upload ({count} Added)", callback_data="post_media_done")]]
        await message.reply(f"📁 Media file #{count} recorded. Send another or click finished:", reply_markup=InlineKeyboardMarkup(btn))
        return

    # Multiple Thumbnail Collectors
    if session.get("action") == "WAIT_MULTI_THUMBS":
        thumb_file = await message.download(file_name=str(config.TEMP_DIR / f"thumb_{uid}_{len(session['thumb_files'])}.jpg"))
        session["thumb_files"].append(thumb_file)
        count = len(session["thumb_files"])
        btn = [
            [InlineKeyboardButton(f"✅ Finished Thumbnails ({count} Uploaded)", callback_data="post_thumbs_done")],
            [InlineKeyboardButton("🚫 Cancel Thumbnails", callback_data="cancel_thumbs")]
        ]
        await message.reply(f"🖼️ Thumbnail #{count} mapped. Send next or click finished:", reply_markup=InlineKeyboardMarkup(btn))
        return

    # Single Thumbnail Upload
    if session.get("action") == "WAIT_SINGLE_THUMB":
        thumb_file = await message.download(file_name=str(config.TEMP_DIR / f"single_thumb_{uid}.jpg"))
        session["thumb_files"] = [thumb_file]
        await message.reply("✅ Single thumbnail configured.")
        await ask_button_strategy(client, message)
        return

    # User Payment Proof
    if session.get("action") == "VIP_CHECKOUT":
        cid = session["channel_id"]
        buttons = [
            [
                InlineKeyboardButton("Approve", callback_data=f"appr_{uid}_{cid}"),
                InlineKeyboardButton("Reject", callback_data=f"rjct_{uid}")
            ]
        ]
        await message.forward(config.ADMIN_ID)
        await client.send_message(
            config.ADMIN_ID,
            f"🔔 <b>New Payment Verification Request</b>\n\n"
            f"User: {message.from_user.mention} (<code>{uid}</code>)\n"
            f"Username: @{message.from_user.username}\n"
            f"Target Channel: <code>{config.VIP_CHANNELS[cid]['name']}</code>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await message.reply("✅ <b>Payment submission forwarded.</b> Admin will verify and issue your VIP pass shortly.")
        USER_SESSIONS.pop(uid, None)

# ----------------- UNIVERSAL TEXT ROUTER -----------------
@app.on_message(filters.private & filters.text & ~filters.command(["start", "screenshot"]))
async def handle_text_incoming(client: Client, message: Message):
    uid = message.from_user.id
    session = USER_SESSIONS.get(uid, {})
    action = session.get("action")

    # Screenshot Extraction Processing
    if action == "WAIT_SCREEN_COUNT":
        try:
            count = int(message.text.strip())
            count = max(1, min(100, count))
        except ValueError:
            await message.reply("❌ Please enter a valid number between 1 and 100.")
            return

        status = await message.reply(f"⚙️ <i>Extracting {count} frames via FFmpeg...</i>")
        out_dir = str(config.TEMP_DIR / f"frames_{uid}")
        frames = media_tools.extract_screenshots(session["video_path"], out_dir, count=count)

        if not frames:
            await status.edit_text("❌ Failed to decode video frames.")
        else:
            await status.edit_text(f"📤 <i>Dispatching {len(frames)} frames in albums...</i>")
            for i in range(0, len(frames), 10):
                batch = [InputMediaPhoto(f) for f in frames[i:i+10]]
                await client.send_media_group(chat_id=message.chat.id, media=batch)

            btn = InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ Delete Previews", callback_data=f"del_dir_{uid}")]])
            await client.send_message(message.chat.id, "✅ Frame extraction complete.", reply_markup=btn)

        if os.path.exists(session["video_path"]):
            os.remove(session["video_path"])
        USER_SESSIONS.pop(uid, None)
        return

    # Custom Description for Post
    if action == "WAIT_POST_CAPTION":
        session["caption"] = message.text.html
        buttons = [
            [InlineKeyboardButton("🔘 Setup Glass Buttons", callback_data="post_btn_setup")],
            [InlineKeyboardButton("⏭️ Skip Buttons", callback_data="post_skip_buttons")]
        ]
        await message.reply("Caption registered. Configure interactive buttons:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    # Edit Scheduled Caption
    if action == "EDIT_POST_CAPTION":
        pid = session["edit_post_id"]
        await database.update_post_caption(pid, message.text.html)
        await message.reply(f"✅ Caption for post <code>#{pid}</code> successfully updated.")
        USER_SESSIONS.pop(uid, None)
        return

    # Button Specifications
    if action == "WAIT_POST_BUTTONS":
        parsed = formatter.parse_button_input(message.text)
        session["buttons"] = parsed

        # Ask Button Layout: Horizontal or Vertical
        layout_btns = [
            [InlineKeyboardButton("↔️ Horizontal Alignment", callback_data="layout_horizontal")],
            [InlineKeyboardButton("↕️ Vertical Alignment", callback_data="layout_vertical")]
        ]
        await message.reply("Choose layout alignment for your buttons:", reply_markup=InlineKeyboardMarkup(layout_btns))
        return

    # Schedule Timestamp Parser
    if action == "WAIT_POST_TIME":
        text = message.text.strip()
        tz_str = session.get("timezone", config.DEFAULT_TIMEZONE)
        try:
            user_tz = pytz.timezone(tz_str)
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
            localized_dt = user_tz.localize(dt)
            utc_dt = localized_dt.astimezone(pytz.utc)

            post_id = await database.add_scheduled_post(
                channel_id=session["channel_id"],
                content_type=session.get("content_type", "text"),
                file_ids=session.get("media_files", []),
                thumb_paths=session.get("thumb_files", []),
                caption=session.get("caption", ""),
                buttons=session.get("buttons", []),
                layout=session.get("button_layout", "vertical"),
                scheduled_time=utc_dt.isoformat(),
                tz=tz_str
            )

            scheduler_jobs.scheduler.add_job(
                scheduler_jobs.execute_scheduled_post,
                trigger="date",
                run_date=utc_dt,
                args=[client, post_id],
                id=f"post_{post_id}"
            )

            await message.reply(
                f"✅ <b>Post Scheduled Successfully!</b>\n\n"
                f"📅 <b>Target Time:</b> <code>{text}</code> ({tz_str})\n"
                f"🆔 <b>Queue Task ID:</b> <code>#{post_id}</code>\n"
                f"📢 <b>Target Channel:</b> <code>{session['channel_id']}</code>"
            )
            USER_SESSIONS.pop(uid, None)
        except ValueError:
            await message.reply("❌ Invalid format. Use: <code>YYYY-MM-DD HH:MM</code> (e.g., <code>2026-10-25 14:30</code>)")
        return

# ----------------- POST CREATOR WIZARD -----------------
@app.on_callback_query(filters.regex("^post_wizard$"))
async def post_wizard_entry(client: Client, query: CallbackQuery):
    buttons = []
    for cid, name in config.MANAGED_CHANNELS.items():
        buttons.append([InlineKeyboardButton(name, callback_data=f"postchan_{cid}")])
    await query.message.edit_text("Select target channel for publication:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^postchan_(-?\d+)"))
async def select_post_template(client: Client, query: CallbackQuery):
    cid = int(query.matches[0].group(1))
    USER_SESSIONS[query.from_user.id] = {"channel_id": cid}

    buttons = [
        [InlineKeyboardButton("🥷 WZML-X Expandable Layout", callback_data="type_wzml")],
        [InlineKeyboardButton("📁 Media / Document Upload", callback_data="type_media")],
        [InlineKeyboardButton("✍️ Custom Formatted Text Post", callback_data="type_custom_text")]
    ]
    await query.message.edit_text("Choose post format and structure:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("^type_wzml$"))
async def create_wzml_template(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    sections = [
        {"title": "How to make own Marketplace ?", "emoji": "🧐", "content": "Marketplace is an Author who can release multiple Plugins and keep it up accordingly to Versions !"},
        {"title": "How to make own Plugins ?", "emoji": "🤓", "content": "Refer to official developer specs at the repository tree below."},
        {"title": "Why / How to create ?", "emoji": "🧑‍💻", "content": "Create modular add-ons to streamline media transcoding and dispatch."}
    ]
    formatted = formatter.format_wzml_post(
        title="Introducing Experimental WZ Marketplace !",
        sections=sections,
        footer_url="https://github.com/SilentDemonSD/WZML-X/tree/wzv3-dev/plugins"
    )
    USER_SESSIONS[uid]["caption"] = formatted
    USER_SESSIONS[uid]["content_type"] = "text"

    buttons = [
        [InlineKeyboardButton("🔘 Configure Glass Buttons", callback_data="post_btn_setup")],
        [InlineKeyboardButton("⏭️ Skip Buttons", callback_data="post_skip_buttons")]
    ]
    await query.message.edit_text(
        f"📝 <b>WZML-X Dropdown Layout Preview:</b>\n\n{formatted}\n\nProceed to button settings:",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

@app.on_callback_query(filters.regex("^type_custom_text$"))
async def custom_text_entry(client: Client, query: CallbackQuery):
    USER_SESSIONS[query.from_user.id]["action"] = "WAIT_POST_CAPTION"
    USER_SESSIONS[query.from_user.id]["content_type"] = "text"
    await query.message.edit_text("Send the text description for the post (HTML styling supported):")

@app.on_callback_query(filters.regex("^type_media$"))
async def init_media_upload(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    USER_SESSIONS[uid]["action"] = "WAIT_POST_MEDIA"
    USER_SESSIONS[uid]["content_type"] = "media_batch"
    USER_SESSIONS[uid]["media_files"] = []
    await query.message.edit_text("📤 Send the video, audio, image, zip, or pdf files. Click finished when done.")

@app.on_callback_query(filters.regex("^post_media_done$"))
async def ask_thumbnail_options(client: Client, query: CallbackQuery):
    buttons = [
        [InlineKeyboardButton("🖼️ Single Thumbnail", callback_data="thumb_single")],
        [InlineKeyboardButton("🗂️ Multiple Thumbnails", callback_data="thumb_multi")],
        [InlineKeyboardButton("⏭️ Skip Thumbnails", callback_data="ask_media_caption")]
    ]
    await query.message.edit_text("Configure thumbnail options for uploaded media:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("^thumb_single$"))
async def single_thumb_entry(client: Client, query: CallbackQuery):
    USER_SESSIONS[query.from_user.id]["action"] = "WAIT_SINGLE_THUMB"
    USER_SESSIONS[query.from_user.id]["thumb_files"] = []
    await query.message.edit_text("🖼️ Send the single thumbnail image to apply:")

@app.on_callback_query(filters.regex("^thumb_multi$"))
async def multi_thumb_entry(client: Client, query: CallbackQuery):
    USER_SESSIONS[query.from_user.id]["action"] = "WAIT_MULTI_THUMBS"
    USER_SESSIONS[query.from_user.id]["thumb_files"] = []
    await query.message.edit_text("🗂️ Send thumbnails sequentially. Each one maps to the corresponding file in order:")

@app.on_callback_query(filters.regex("^cancel_thumbs$"))
@app.on_callback_query(filters.regex("^post_thumbs_done$"))
@app.on_callback_query(filters.regex("^ask_media_caption$"))
async def prompt_for_media_caption(client: Client, query: CallbackQuery):
    USER_SESSIONS[query.from_user.id]["action"] = "WAIT_POST_CAPTION"
    await query.message.edit_text("✍️ Send the caption/description for this media batch:")

@app.on_callback_query(filters.regex("^post_btn_setup$"))
async def ask_button_strategy(client: Client, event: Message | CallbackQuery):
    uid = event.from_user.id
    USER_SESSIONS[uid]["action"] = "WAIT_POST_BUTTONS"
    instructions = (
        "🔘 <b>Custom Glass Button Builder</b>\n\n"
        "Send your buttons in this format (one per line):\n"
        "<code>Label | URL | Color</code>\n\n"
        "<b>Available Glass Colors:</b>\n"
        "• <code>blue</code> (🔵) | <code>green</code> (🟢) | <code>red</code> (🔴)\n"
        "• <code>yellow</code> (🟡) | <code>purple</code> (🟣) | <code>neutral</code> (⚪)\n\n"
        "<b>Example Input:</b>\n"
        "<code>Download Mirror | https://github.com | blue</code>\n"
        "<code>VIP Network | https://t.me/yourchannel | green</code>"
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(instructions)
    else:
        await event.reply(instructions)

@app.on_callback_query(filters.regex(r"^layout_(horizontal|vertical)"))
async def set_layout_and_ask_tz(client: Client, query: CallbackQuery):
    layout = query.matches[0].group(1)
    USER_SESSIONS[query.from_user.id]["button_layout"] = layout
    await select_timezone_menu(query)

@app.on_callback_query(filters.regex("^post_skip_buttons$"))
async def skip_buttons_entry(client: Client, query: CallbackQuery):
    USER_SESSIONS[query.from_user.id]["buttons"] = []
    await select_timezone_menu(query)

async def select_timezone_menu(query: CallbackQuery):
    btn = [
        [InlineKeyboardButton("🇮🇳 Asia/Kolkata (IST)", callback_data="settz_Asia/Kolkata")],
        [InlineKeyboardButton("🌐 UTC Standard", callback_data="settz_UTC")],
        [InlineKeyboardButton("🇺🇸 US Eastern (EST)", callback_data="settz_US/Eastern")]
    ]
    await query.message.edit_text("Select execution timezone:", reply_markup=InlineKeyboardMarkup(btn))

@app.on_callback_query(filters.regex(r"^settz_(.+)"))
async def ask_post_timestamp(client: Client, query: CallbackQuery):
    tz = query.matches[0].group(1)
    USER_SESSIONS[query.from_user.id]["timezone"] = tz
    USER_SESSIONS[query.from_user.id]["action"] = "WAIT_POST_TIME"
    await query.message.edit_text(
        f"Selected Timezone: <code>{tz}</code>\n\n"
        "Send target date and time to publish:\n"
        "<b>Format:</b> <code>YYYY-MM-DD HH:MM</code>\n"
        "<b>Example:</b> <code>2026-10-15 18:30</code>"
    )

# ----------------- SCHEDULED POST QUEUE CONTROLS -----------------
@app.on_callback_query(filters.regex("^list_schedules$"))
async def list_pending_schedules(client: Client, query: CallbackQuery):
    posts = await database.get_all_pending_posts()
    if not posts:
        await query.message.edit_text("📭 No scheduled posts currently pending.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]))
        return

    buttons = []
    for p in posts:
        buttons.append([InlineKeyboardButton(f"#{p['id']} | Channel: {p['channel_id']} | {p['scheduled_time']}", callback_data=f"viewpost_{p['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])
    await query.message.edit_text("📋 <b>Pending Scheduled Posts:</b>", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^viewpost_(\d+)"))
async def view_post_actions(client: Client, query: CallbackQuery):
    pid = int(query.matches[0].group(1))
    post = await database.get_scheduled_post(pid)
    if not post:
        await query.message.edit_text("Post not found.")
        return

    buttons = [
        [InlineKeyboardButton("✏️ Edit Caption", callback_data=f"editcaption_{pid}")],
        [InlineKeyboardButton("❌ Cancel Schedule", callback_data=f"cancelpost_{pid}")],
        [InlineKeyboardButton("🗑️ Delete Permanently", callback_data=f"delpost_{pid}")],
        [InlineKeyboardButton("🔙 Back to Queue", callback_data="list_schedules")]
    ]
    await query.message.edit_text(
        f"📌 <b>Scheduled Post #{pid}</b>\n\n"
        f"📢 <b>Channel:</b> <code>{post['channel_id']}</code>\n"
        f"⏰ <b>Scheduled Time (UTC):</b> <code>{post['scheduled_time']}</code>\n"
        f"🏷️ <b>Format:</b> <code>{post['content_type']}</code>\n"
        f"📊 <b>Status:</b> <code>{post['status']}</code>",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r"^editcaption_(\d+)"))
async def edit_caption_trigger(client: Client, query: CallbackQuery):
    pid = int(query.matches[0].group(1))
    USER_SESSIONS[query.from_user.id] = {"action": "EDIT_POST_CAPTION", "edit_post_id": pid}
    await query.message.edit_text(f"Send the new caption for post <code>#{pid}</code>:")

@app.on_callback_query(filters.regex(r"^cancelpost_(\d+)"))
async def cancel_post_trigger(client: Client, query: CallbackQuery):
    pid = int(query.matches[0].group(1))
    try:
        scheduler_jobs.scheduler.remove_job(f"post_{pid}")
    except Exception:
        pass
    await database.update_post_status(pid, "CANCELLED")
    await query.message.edit_text(f"❌ Schedule for post <code>#{pid}</code> has been cancelled.")

@app.on_callback_query(filters.regex(r"^delpost_(\d+)"))
async def delete_post_trigger(client: Client, query: CallbackQuery):
    pid = int(query.matches[0].group(1))
    try:
        scheduler_jobs.scheduler.remove_job(f"post_{pid}")
    except Exception:
        pass
    await database.delete_scheduled_post(pid)
    await query.message.edit_text(f"🗑️ Post <code>#{pid}</code> permanently removed.")

@app.on_callback_query(filters.regex(r"^del_dir_(\d+)"))
async def cleanup_user_frames(client: Client, query: CallbackQuery):
    uid = query.matches[0].group(1)
    target = config.TEMP_DIR / f"frames_{uid}"
    if target.exists():
        shutil.rmtree(target)
    await query.message.edit_text("🗑️ Frame preview cache wiped clean.")

@app.on_callback_query(filters.regex("^main_menu$"))
async def back_to_main(client: Client, query: CallbackQuery):
    await start_entry(client, query.message)

# ----------------- APPLICATION BOOTSTRAP -----------------
if __name__ == "__main__":
    import asyncio
    asyncio.get_event_loop().run_until_complete(database.init_db())
    scheduler_jobs.init_scheduler(app)
    asyncio.get_event_loop().run_until_complete(scheduler_jobs.load_persistent_jobs(app))
    print("Bot is fully operational. System ready.")
    app.run()
