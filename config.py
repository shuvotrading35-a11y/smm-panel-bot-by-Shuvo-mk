import os
from dotenv import load_dotenv

load_dotenv()

# ── Bot ──────────────────────────────────────────────
BOT_TOKEN      = os.getenv("BOT_TOKEN", "")
BOT_USERNAME   = os.getenv("BOT_USERNAME", "ShuvoSMMBot")
BOT_NAME       = os.getenv("BOT_NAME", "Shuvo SMM Bot")
DEVELOPER      = os.getenv("DEVELOPER", "@shuvo_9882")

# ── Admins ───────────────────────────────────────────
_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [int(x.strip()) for x in _raw.split(",") if x.strip().isdigit()]

# ── SMM API ──────────────────────────────────────────
SMM_API_URL = os.getenv("SMM_API_URL", "")
SMM_API_KEY = os.getenv("SMM_API_KEY", "")

# ── FlashTopup API (Game Topup) ───────────────────────
FLASHTOPUP_API_ID  = os.getenv("FLASHTOPUP_API_ID", "")
FLASHTOPUP_API_KEY = os.getenv("FLASHTOPUP_API_KEY", "")

# ── Database ─────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "data/database.db")

# ── Economy ──────────────────────────────────────────
DAILY_BONUS_AMOUNT = float(os.getenv("DAILY_BONUS_AMOUNT", "1"))
REFERRAL_REWARD    = float(os.getenv("REFERRAL_REWARD", "5"))
MIN_DEPOSIT        = float(os.getenv("MIN_DEPOSIT", "1.00"))
COIN_RATE          = float(os.getenv("COIN_RATE", "0.0074"))  # 1 coin = 1 BDT

# ── VIP Plans ────────────────────────────────────────
VIP_PLANS = {
    "bronze":  {"name": "Bronze VIP",  "price": 5.0,  "discount": 5,  "bonus_coins": 10,  "days": 30},
    "silver":  {"name": "Silver VIP",  "price": 10.0, "discount": 10, "bonus_coins": 25,  "days": 30},
    "gold":    {"name": "Gold VIP",    "price": 20.0, "discount": 15, "bonus_coins": 60,  "days": 30},
    "diamond": {"name": "Diamond VIP", "price": 40.0, "discount": 25, "bonus_coins": 150, "days": 30},
}

# ── Payment Methods ───────────────────────────────────
PAYMENT_METHODS = {
    "binance":  "Binance Pay",
    "usdt_trc": "USDT TRC20",
    "usdt_bep": "USDT BEP20",
    "mobile":   "Mobile Banking",
}

# ── Service Categories ────────────────────────────────
CATEGORY_ICONS = {
    "instagram": "📱",
    "tiktok":    "🎵",
    "youtube":   "📺",
    "facebook":  "📘",
    "telegram":  "✈️",
    "twitter":   "🐦",
    "spotify":   "🎧",
    "website":   "🌐",
}

# ── Order Log Bot ────────────────────────────────────
LOG_BOT_TOKEN     = os.getenv("LOG_BOT_TOKEN", "")
LOG_CHAT_ID       = os.getenv("LOG_CHAT_ID",   "")
LOG_BOT_USERNAME  = os.getenv("LOG_BOT_USERNAME",  "@csbsmmbot")
LOG_OFFICIAL_NAME = os.getenv("LOG_OFFICIAL_NAME", "CSB HUB")
LOG_PAYMENT_NAME  = os.getenv("LOG_PAYMENT_NAME",  "CSB")

# ── Spam Protection ───────────────────────────────────
RATE_LIMIT_SECONDS = 1
MAX_ORDERS_PER_DAY = 50


# ── Pricing Markup ────────────────────────────────────
SERVICE_MARKUP_PCT = float(os.getenv("SERVICE_MARKUP_PCT", "30"))   # SMM services markup
TOPUP_MARKUP_PCT   = float(os.getenv("TOPUP_MARKUP_PCT",   "20"))   # Game topup markup

# ── Coin Packages ─────────────────────────────────────
COIN_PACKAGES = [
    (50,   "৳50"),
    (100,   "৳100"),
    (200,  "৳200"),
    (300,  "৳300"),
    (500,  "৳500"),
    (700,  "৳700"),
				(1000,   "৳1000")
]
