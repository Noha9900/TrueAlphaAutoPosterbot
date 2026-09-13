import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "temp"

DATA_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Telegram Bot Credentials
API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "your_api_hash_here")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token_here")
ADMIN_ID = int(os.getenv("ADMIN_ID", "987654321"))

# Timezone Defaults
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Kolkata")

# Payment Credentials
TON_WALLET = os.getenv("TON_WALLET", "EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N")
PAYPAL_LINK = os.getenv("PAYPAL_LINK", "https://paypal.me/yourusername")

# Target VIP Channels: {channel_id: {"name": "Display Title", "price": "Pricing Details"}}
VIP_CHANNELS = {
    -1001234567890: {"name": "⚡ TrueAlpha Network", "price": "₹499 / 2 TON / $6 USD"},
    -1009876543210: {"name": "💎 Ultra HD Media Vault", "price": "₹799 / 3 TON / $10 USD"}
}

# Managed Channels for Auto-Posting
MANAGED_CHANNELS = {
    -1001234567890: "⚡ TrueAlpha Main Channel",
    -1009876543210: "📢 News & Announcements Hub"
}

DB_PATH = DATA_DIR / "bot_database.db"
