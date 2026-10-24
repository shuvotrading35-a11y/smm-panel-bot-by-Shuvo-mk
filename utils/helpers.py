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
import logging
_fj_logger = logging.getLogger("force_join")

async def check_force_join(bot: Bot, user_id: int, channels: list[dict]) -> list[dict]:
    not_joined = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch["channel_id"], user_id)
            if member.status in ("left", "kicked"):
                not_joined.append(ch)
        except TelegramError as e:
            _fj_logger.warning(f"Force-join check failed for channel {ch.get('channel_id')}: {e}")
            continue
    return not_joined

# ── Formatters ────────────────────────────────────────────────────
# 🔥 রেট সেটিং: ১ কয়েন = ১ টাকা, ১ ডলার = ১৩৫ টাকা
COIN_TO_BDT = 1.0      
USD_TO_BDT  = 135.0    # আপনি চাইলে এখানে রেট পরিবর্তন করতে পারেন (যেমন 120 বা 135)

def fmt_coins(amount: float) -> str:
    """শুধু টাকার পরিমাণ"""
    try:
        return f"৳{float(amount):,.2f}"
    except (ValueError, TypeError):
        return "৳0.00"

def fmt_coins_full(amount: float) -> str:
    """টাকা — সব জায়গায় ৳ দেখাবে"""
    try:
        amount = float(amount)
        return f"৳{amount:,.2f}"
    except (ValueError, TypeError):
        return "৳0.00"

def fmt_status(status: str) -> str:
    icons = {
        "Pending":     "⏳", "Processing":  "🔄", "In progress": "⚙️",
        "Completed":   "✅", "Partial":     "⚠️", "Cancelled":   "❌", "Refunded":    "💸",
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
        await asyncio.sleep(0.05)
    return sent, failed