from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def format_wzml_post(title: str, sections: list, footer_url: str = None, footer_label: str = None) -> str:
    """
    Renders expandable blockquote formatting matching Telegram's latest UI layout.
    sections = [
        {"title": "How to make own Marketplace ?", "emoji": "🧐", "content": "..."},
        {"title": "How to make own Plugins ?", "emoji": "🤓", "content": "..."}
    ]
    """
    formatted_text = f"🥷 <b>{title}</b>\n\n"
    for sec in sections:
        emoji = sec.get("emoji", "💡")
        subtitle = sec.get("title", "Question / Section")
        body = sec.get("content", "")
        formatted_text += f"⌃ {emoji} <i>{subtitle}</i>\n"
        formatted_text += f"<blockquote expandable>{body}</blockquote>\n\n"

    if footer_url:
        label = footer_label or footer_url
        formatted_text += f"Follow Simple : <a href=\"{footer_url}\">{label}</a>\n"

    return formatted_text.strip()

def build_glass_buttons(buttons_data: list, layout: str = "vertical") -> InlineKeyboardMarkup | None:
    """
    Constructs Telegram inline keyboards with colored glass status indicators.
    buttons_data = [{"text": "Stream Online", "url": "https://...", "color": "blue"}]
    layout = "horizontal" or "vertical"
    """
    if not buttons_data:
        return None

    color_gems = {
        "blue": "🔵",
        "green": "🟢",
        "red": "🔴",
        "yellow": "🟡",
        "purple": "🟣",
        "neutral": "⚪",
        "default": "🔹"
    }

    button_objects = []
    for btn in buttons_data:
        color = btn.get("color", "").lower()
        gem = color_gems.get(color, color_gems["default"])
        label = f"{gem} {btn['text']}"
        button_objects.append(InlineKeyboardButton(text=label, url=btn["url"]))

    if layout == "horizontal":
        keyboard = [button_objects]
    else:
        keyboard = [[btn] for btn in button_objects]

    return InlineKeyboardMarkup(keyboard)

def parse_button_input(raw_text: str) -> list:
    """
    Parses user multiline string: 'Text | URL | Color'
    """
    buttons = []
    for line in raw_text.strip().split("\n"):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2:
            label = parts[0]
            url = parts[1]
            color = parts[2].lower() if len(parts) > 2 else "blue"
            buttons.append({"text": label, "url": url, "color": color})
    return buttons
