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

# ── Database ─────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "data/database.db")

# ── Economy ──────────────────────────────────────────
DAILY_BONUS_AMOUNT = float(os.getenv("DAILY_BONUS_AMOUNT", "1"))
REFERRAL_REWARD    = float(os.getenv("REFERRAL_REWARD", "5"))
MIN_DEPOSIT        = float(os.getenv("MIN_DEPOSIT", "1.00"))
COIN_RATE          = float(os.getenv("COIN_RATE", "0.0074"))  # 1 coin = $0.0074 ≈ ৳1

# ── Pricing Markup ────────────────────────────────────────────────
# API থেকে যে rate আসে তার উপর এই % profit যোগ হবে
# উদাহরণ: 30 মানে API rate × 1.30 — user থেকে 30% বেশি নেবে
SERVICE_MARKUP_PCT = float(os.getenv("SERVICE_MARKUP_PCT", "30"))  # 30% profit

# ── VIP Plans ────────────────────────────────────────
VIP_PLANS = {
    "bronze":  {"name": "⭐ Bronze VIP",  "price": 5.0,  "discount": 5,  "bonus_coins": 10,  "days": 30},
    "silver":  {"name": "💎 Silver VIP",  "price": 10.0, "discount": 10, "bonus_coins": 25,  "days": 30},
    "gold":    {"name": "👑 Gold VIP",    "price": 20.0, "discount": 15, "bonus_coins": 60,  "days": 30},
    "diamond": {"name": "🔥 Diamond VIP", "price": 40.0, "discount": 25, "bonus_coins": 150, "days": 30},
}

# ── Payment Methods ───────────────────────────────────
PAYMENT_METHODS = {
    "binance":  "💵 Binance Pay",
    "usdt_trc": "🟢 USDT TRC20",
    "usdt_bep": "🟡 USDT BEP20",
    "mobile":   "📱 Mobile Banking",
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
# Set LOG_BOT_TOKEN to a separate bot token (the "log bot")
# Set LOG_CHAT_ID  to the chat/channel/group ID where orders will be sent
# Leave blank to disable order log notifications
LOG_BOT_TOKEN = os.getenv("LOG_BOT_TOKEN", "")   # separate bot token
LOG_CHAT_ID   = os.getenv("LOG_CHAT_ID",   "")   # e.g. -1001234567890 or @yourchannel

# Branding shown inside the order log message
LOG_BOT_USERNAME  = os.getenv("LOG_BOT_USERNAME",  "@csbsmmbot")   # shown as 👮 Bot:
LOG_OFFICIAL_NAME = os.getenv("LOG_OFFICIAL_NAME", "CSB HUB")      # shown as 📢 Official:
LOG_PAYMENT_NAME  = os.getenv("LOG_PAYMENT_NAME",  "CSB")          # shown as 📢 Payment Proof:

# ── Spam Protection ───────────────────────────────────
RATE_LIMIT_SECONDS = 1   # min seconds between commands per user
MAX_ORDERS_PER_DAY = 50  # max orders a user can place per day

# ── Coin Packages ─────────────────────────────────────────────────
# (coins, price_bdt) — ইচ্ছামতো পরিবর্তন করো
# বড় package-এ প্রতি coin সস্তা — user বেশি কিনতে উৎসাহিত হবে
COIN_PACKAGES = [
    (100,  "৳100"),    # ৳0.15/coin  — starter
    (300,  "৳300"),    # ৳0.13/coin  — small
    (700,  "৳700"),    # ৳0.12/coin  — medium
    (1500, "৳1500"),   # ৳0.11/coin  — popular ⭐
    (3000, "৳3000"),   # ৳0.11/coin  — best value 🔥
    (7000, "৳7000"),   # ৳0.10/coin  — premium 💎
]