import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
from config import TON_WALLET, PAYPAL_LINK, TEMP_DIR

def generate_qr(data: str, filename: str) -> str:
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#000000", back_color="#ffffff")
    save_path = str(TEMP_DIR / filename)
    img.save(save_path)
    return save_path

def generate_ton_invoice_qr() -> str:
    return generate_qr(f"ton://transfer/{TON_WALLET}", "ton_qr.png")

def generate_paypal_invoice_qr() -> str:
    return generate_qr(PAYPAL_LINK, "paypal_qr.png")

def generate_vip_card(
    user_name: str,
    user_id: int,
    vip_count: int,
    channel_name: str,
    join_date: str,
    expiry_date: str,
    logo_path: str = None
) -> str:
    """
    Generates a 900x520 VIP Membership Graphic Card in Dark Modern theme.
    """
    width, height = 900, 520
    card = Image.new("RGBA", (width, height), (15, 23, 42, 255))
    draw = ImageDraw.Draw(card)

    # Accent Top Stripe
    draw.rectangle([(0, 0), (width, 10)], fill=(59, 130, 246, 255))

    # Font Setup with safe OS fallbacks
    font_large = ImageFont.load_default()
    font_bold = ImageFont.load_default()
    font_regular = ImageFont.load_default()
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf"
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                font_large = ImageFont.truetype(p, 28)
                font_bold = ImageFont.truetype(p, 20)
                font_regular = ImageFont.truetype(p.replace("-Bold", "").replace("bd", ""), 17)
                break
            except Exception:
                pass

    # Dynamic Top Counter Badge: e.g. "ARUN #01"
    badge_label = f"{user_name.upper()} #{vip_count:02d}"
    draw.rounded_rectangle([(50, 45), (480, 105)], radius=10, fill=(30, 41, 59, 255), outline=(59, 130, 246, 255), width=2)
    draw.text((70, 62), f"⭐ VIP PASS | {badge_label}", fill=(255, 255, 255, 255), font=font_bold)

    # Insert Channel Logo if present
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA").resize((110, 110))
            mask = Image.new("L", (110, 110), 0)
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.ellipse((0, 0, 110, 110), fill=255)
            card.paste(logo, (730, 45), mask)
        except Exception:
            pass

    # Meta Table
    fields = [
        ("DESTINATION CHANNEL", channel_name),
        ("TELEGRAM USER ID", str(user_id)),
        ("SUBSCRIPTION DATE", join_date),
        ("EXPIRATION DATE", expiry_date),
        ("PASS STATUS", "AUTHENTICATED & ACTIVE"),
    ]

    y_pos = 150
    for label, val in fields:
        draw.text((50, y_pos), label, fill=(148, 163, 184, 255), font=font_regular)
        draw.text((310, y_pos), val, fill=(255, 255, 255, 255), font=font_bold)
        draw.line([(50, y_pos + 35), (850, y_pos + 35)], fill=(30, 41, 59, 255), width=1)
        y_pos += 60

    # Bottom Signoff Note
    draw.text((50, 465), "Verified Pass • Access is single-user and strictly non-transferable.", fill=(96, 165, 250, 255), font=font_regular)

    output_file = str(TEMP_DIR / f"vip_pass_{user_id}_{vip_count}.png")
    card.convert("RGB").save(output_file, "PNG")
    return output_file
