import time
import asyncio
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError
from config import RATE_LIMIT_SECONDS, CATEGORY_ICONS, BOT_USERNAME

# ── Anti-Spam ─────────────────────────────────────────────────────
_last_action: dict[int, float] = {}

def is_rate_limited(user_id: int) -> bool:
    now  = time.monotonic()
    last = _last_action.get(user_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        return True
    _last_action[user_id] = now
    return False

# ── Force-Join Check ──────────────────────────────────────────────
async def check_force_join(bot: Bot, user_id: int, channels: list[dict]) -> list[dict]:
    """Return list of channels the user has NOT joined."""
    not_joined = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch["channel_id"], user_id)
            if member.status in ("left", "kicked"):
                not_joined.append(ch)
        except TelegramError:
            not_joined.append(ch)
    return not_joined

# ── Formatters ────────────────────────────────────────────────────
# Conversion rates
COIN_TO_BDT = 1.0      # 1 coin = ৳1
BDT_TO_USD  = 1/135    # 1 BDT  = $0.0074

def fmt_coins(amount: float) -> str:
    """Just the number — for calculations/internal use."""
    return f"{amount:,.2f}"

def fmt_coins_full(amount: float) -> str:
    """Coins + BDT + USD — for display to users."""
    bdt = float(amount) * COIN_TO_BDT
    usd = bdt * BDT_TO_USD
    return f"{float(amount):,.2f} Coins (≈ ৳{bdt:.1f} / ${usd:.3f})"

def fmt_status(status: str) -> str:
    icons = {
        "Pending":     "⏳",
        "Processing":  "🔄",
        "In progress": "⚙️",
        "Completed":   "✅",
        "Partial":     "⚠️",
        "Cancelled":   "❌",
        "Refunded":    "💸",
    }
    return f"{icons.get(status, '❓')} {status}"

def fmt_date(dt_str: str) -> str:
    if not dt_str:
        return "—"
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%d %b %Y %H:%M")
    except Exception:
        return dt_str

def category_icon(category: str) -> str:
    cat_lower = category.lower()
    for key, icon in CATEGORY_ICONS.items():
        if key in cat_lower:
            return icon
    return "🔹"

def referral_link(user_id: int) -> str:
    return f"https://t.me/{BOT_USERNAME}?start={user_id}"

def vip_badge(plan: str | None) -> str:
    if not plan:
        return ""
    badges = {"bronze": "⭐", "silver": "💎", "gold": "👑", "diamond": "🔥"}
    return badges.get(plan, "⭐")

# ── Broadcast Helper ──────────────────────────────────────────────
async def broadcast_message(bot: Bot, user_ids: list[int],
                             text: str = None, photo_id: str = None,
                             video_id: str = None, doc_id: str = None,
                             caption: str = None) -> tuple[int, int]:
    sent = failed = 0
    for uid in user_ids:
        try:
            if photo_id:
                await bot.send_photo(uid, photo_id, caption=caption or text)
            elif video_id:
                await bot.send_video(uid, video_id, caption=caption or text)
            elif doc_id:
                await bot.send_document(uid, doc_id, caption=caption or text)
            elif text:
                await bot.send_message(uid, text)
            else:
                continue
            sent += 1
        except TelegramError:
            failed += 1
        await asyncio.sleep(0.05)  # 20 msg/sec limit
    return sent, failed