 import logging
import re
import asyncio
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, ApplicationHandlerStop
from telegram.constants import ParseMode

import database as db
from config import (ADMIN_IDS, BOT_NAME, DEVELOPER, DAILY_BONUS_AMOUNT,
                    REFERRAL_REWARD, VIP_PLANS, COIN_RATE, BOT_USERNAME, SERVICE_MARKUP_PCT)
from keyboards.reply import main_keyboard, cancel_keyboard, back_keyboard, service_menu_keyboard, order_menu_keyboard
from keyboards.inline import (
    StyledButton,
    leaderboard_kb, wallet_kb, account_kb, vip_plans_kb,
    categories_kb, platform_categories_kb, order_categories_kb, services_kb, service_detail_kb, force_join_kb,
    coin_packages_kb, pkg_payment_kb,
    payment_methods_kb, confirm_order_kb, order_actions_kb
)
from utils.helpers import (
    fmt_coins, fmt_coins_full, fmt_status, fmt_date, referral_link,
    vip_badge, is_rate_limited, check_force_join, category_icon
)
from utils.order_logger import send_order_log
from api.smm_api import smm_api
from api.csb_api import csb_api
from config import CATEGORY_ICONS, MAX_ORDERS_PER_DAY

logger = logging.getLogger(__name__)

(
    ORDER_PLATFORM, ORDER_CATEGORY, ORDER_SERVICE, ORDER_LINK, ORDER_QUANTITY,
    ORDER_CONFIRM, REDEEM_INPUT, TICKET_SUBJECT, TICKET_MESSAGE,
    DEPOSIT_METHOD, DEPOSIT_AMOUNT, DEPOSIT_TXN, TRACKER_INPUT,
) = range(13)

USD_TO_BDT  = 135.0
COIN_TO_BDT = 1.0

# 🔥 Helper: Detect if it's a Game Service
def is_game_service(svc_name: str) -> bool:
    nl = svc_name.lower()
    return any(kw in nl for kw in ["free fire", "freefire", "free_fire", "diamond", "uc", "unipin"])

# 🔥 Global helper to get platform name from category string
def get_platform_name(cat: str) -> str:
    cl = cat.lower()
    if "free fire" in cl or "freefire" in cl or "free_fire" in cl: return "freefire"
    if "tik tok" in cl or "tiktok" in cl or "tik_tok" in cl: return "tiktok"
    for p in ["facebook", "instagram", "youtube", "telegram", "twitter", "spotify"]:
        if p in cl: return p
    return "other"

# ═══════════════════════════════════════════════════════════════════
#  AUTO-DELETE HELPERS
# ═══════════════════════════════════════════════════════════════════
async def _send_replacing(update, ctx, key: str, text: str, **kwargs):
    prev = ctx.chat_data.get(key)
    if prev:
        try: await ctx.bot.delete_message(chat_id=update.effective_chat.id, message_id=prev)
        except Exception: pass
        ctx.chat_data.pop(key, None)
    sent = await update.effective_message.reply_text(text, **kwargs)
    ctx.chat_data[key] = sent.message_id
    return sent

async def _delete_menu_msg(update, ctx, key: str):
    prev = ctx.chat_data.get(key)
    if prev:
        try: await ctx.bot.delete_message(update.effective_chat.id, prev)
        except Exception: pass
        ctx.chat_data.pop(key, None)

async def _restore_service_menu(update, ctx):
    try:
        await update.effective_message.reply_text("👇 Services Menu:", reply_markup=service_menu_keyboard())
    except Exception: pass

async def _schedule_delete(bot, chat_id: int, message_id: int, delay: int):
    await asyncio.sleep(delay)
    try: await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception: pass

# ═══════════════════════════════════════════════════════════════════
#  SUB-CATEGORY AUTO-DETECTION
# ═══════════════════════════════════════════════════════════════════
_SUBCAT_RULES = {
    "facebook": [
        (r'\bgroup\s*members?\b', "👨‍👩‍👧 Group Members"),
        (r'\bstory\s*views?\b', "📖 Story Views"),
        (r'\bvideo\s*views?\b|\bviews?\b|\bplays?\b|\bvideo\b', "👁 Views/Plays"),
        (r'\breactions?\b', "❤️ Reactions"),
        (r'\bcomments?\b', "💬 Comments"),
        (r'\bfollowers?\b', "👥 Followers"),
        (r'\bshares?\b', "🔄 Shares"),
        (r'\bpost\s*likes?\b', "👍 Post Likes"),
        (r'\blikes?\b', "👍 Likes"),
        (r'\bbangladesh\b', "🇧🇩 Bangladesh"),
    ],
    "instagram": [
        (r'\bstory\b', "📖 Story"),
        (r'\breels?\b', "🎬 Reels"),
        (r'\bviews?\b|\bplays?\b', "👁 Views"),
        (r'\bfollowers?\b', "👥 Followers"),
        (r'\blikes?\b', "👍 Likes"),
        (r'\bcomments?\b', "💬 Comments"),
        (r'\bsaves?\b', "🔖 Saves"),
    ],
    "youtube": [
        (r'\bsubscribers?\b', "🔔 Subscribers"),
        (r'\bwatch\s*hours?\b', "⏱ Watch Hours"),
        (r'\bshorts?\b', "🎬 Shorts"),
        (r'\bviews?\b', "👁 Views"),
        (r'\blikes?\b', "👍 Likes"),
        (r'\bcomments?\b', "💬 Comments"),
        (r'\blive\b', "📡 Live Stream"),
    ],
    "tiktok": [
        (r'\bfollowers?\b', "👥 Followers"),
        (r'\blikes?\b', "👍 Likes"),
        (r'\bviews?\b', "👁 Views"),
        (r'\bshares?\b', "🔄 Shares"),
        (r'\bcomments?\b', "💬 Comments"),
        (r'\blive\b', "📡 Live"),
    ],
    "freefire": [
        (r'\bdiamond\b', "💎 Diamonds"),
        (r'\buc\b', "🪙 UC"),
        (r'\bweekly\b', "📅 Weekly"),
        (r'\bmonthly\b', "📅 Monthly"),
        (r'\blevel\b', "⬆️ Level Up"),
    ],
    "telegram": [
        (r'\bmembers?\b', "👥 Members"),
        (r'\bsubscribers?\b', "🔔 Subscribers"),
        (r'\bviews?\b', "👁 Views"),
        (r'\breactions?\b', "❤️ Reactions"),
        (r'\bvotes?\b', "🗳 Votes"),
    ],
    "twitter": [
        (r'\bfollowers?\b', "👥 Followers"),
        (r'\blikes?\b', "❤️ Likes"),
        (r'\bviews?\b|\bimpressions?\b', "👁 Views"),
        (r'\bretweets?\b|\breposts?\b', "🔁 Retweets"),
        (r'\bcomments?\b|\breplies?\b', "💬 Comments"),
    ],
    "spotify": [
        (r'\bplays?\b', "▶️ Plays"),
        (r'\bfollowers?\b', "👥 Followers"),
        (r'\bmonthly\b|\blisteners?\b', "🎧 Monthly Listeners"),
    ],
    "discord": [
        (r'\bmembers?\b', "👥 Members"),
        (r'\breactions?\b', "❤️ Reactions"),
        (r'\bboosts?\b', "🚀 Server Boosts"),
    ],
    "whatsapp": [(r'\bmembers?\b', "👥 Members")],
    "linkedin": [(r'\bfollowers?\b', "👥 Followers"), (r'\breactions?\b', "❤️ Reactions")],
    "threads": [(r'\bfollowers?\b', "👥 Followers"), (r'\blikes?\b', "👍 Likes")],
    "reddit": [(r'\bmembers?\b', "👥 Members"), (r'\bupvotes?\b', "⬆️ Upvotes")]
}

def _detect_platform(services: list[dict]) -> str | None:
    if not services: return None
    for s in services[:5]:
        name = (s.get("name") or "").lower()
        if "free fire" in name or "freefire" in name or "free_fire" in name: return "freefire"
        if "tik tok" in name or "tiktok" in name or "tik_tok" in name: return "tiktok"
        for plat in _SUBCAT_RULES.keys():
            if plat in name: return plat
    return None

def _get_subcat(platform: str, service_name: str) -> str:
    rules = _SUBCAT_RULES.get(platform)
    if not rules: return "📦 Others"
    name = service_name or ""
    for pattern, label in rules:
        if re.search(pattern, name, re.IGNORECASE): return label
    return "📦 Others"

def _group_services(services: list[dict], platform: str) -> dict[str, list[dict]]:
    grouped: dict[str, list] = {}
    for s in services:
        label = _get_subcat(platform, s.get("name", ""))
        grouped.setdefault(label, []).append(s)
    return grouped

def _should_show_subcat(services: list[dict], grouped: dict[str, list]) -> bool:
    return len(grouped) >= 2

# ═══════════════════════════════════════════════════════════════════
#  SHUVOPAY — AUTOMATIC PAYMENT GATEWAY
# ═══════════════════════════════════════════════════════════════════
SHUVOPAY_API = "https://shuvopaycom-production.up.railway.app/api/v1"
SHUVOPAY_CHECKOUT = "https://shuvopay.vercel.app"
SHUVOPAY_API_KEY = "spk_4jwdScgIqRvPgYNABohcyBy179mQR0zMg7-7oixZgR_55pot4if8KiNGqTxhnYi7"

async def create_shuvopay_invoice(amount: float, provider: str = "bkash") -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{SHUVOPAY_API}/invoice",
                json={"amount": amount, "provider": provider, "receiver_account": "01336650725", "time_window_minutes": 30},
                headers={"X-Api-Key": SHUVOPAY_API_KEY},
            )
            if resp.status_code == 200: return resp.json()
            return {"error": f"HTTP {resp.status_code}: {resp.text[:300]}"}
    except Exception as e: return {"error": f"{type(e).__name__}: {e}"}

async def check_shuvopay_invoice(invoice_id: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{SHUVOPAY_API}/invoice/public/{invoice_id}")
            if resp.status_code == 200: return resp.json().get("status", "pending")
    except Exception: pass
    return "pending"

# ═══════════════════════════════════════════════════════════════════
#  START / WELCOME
# ═══════════════════════════════════════════════════════════════════
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    args    = ctx.args
    ref_id  = int(args[0]) if args and args[0].isdigit() else None

    existing = await db.get_user(user.id)
    if not existing:
        await db.create_user(user.id, user.username or "", user.full_name or "", ref_id)
        if ref_id and ref_id != user.id: await db.process_referral(user.id, ref_id, REFERRAL_REWARD)
        try:
            from telegram.helpers import escape_markdown
            total_users = await db.get_user_count()
            safe_name = escape_markdown(user.full_name or "Unknown", version=2)
            username_text = f"@{escape_markdown(user.username, version=2)}" if user.username else "No username"
            referral_text = f"`{ref_id}`" if ref_id else "None"
            notification = (
                "🆕 *NEW USER JOINED*\n" "━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 *Name:* {safe_name}\n" f"🔹 *Username:* {username_text}\n"
                f"🆔 *User ID:* `{user.id}`\n" f"🔗 [Open Profile](tg://user?id={user.id})\n"
                f"🎁 *Referral ID:* {referral_text}\n" f"👥 *Total Users:* `{total_users}`\n"
                "━━━━━━━━━━━━━━━━━━━━\n" f"🤖 *{escape_markdown(BOT_NAME, version=2)}*"
            )
            for admin_id in ADMIN_IDS:
                try: await ctx.bot.send_message(chat_id=admin_id, text=notification, parse_mode="MarkdownV2", disable_web_page_preview=True)
                except Exception: pass
        except Exception: pass

    channels = await db.get_force_channels()
    if channels and update.effective_user.id not in ADMIN_IDS:
        not_joined = await check_force_join(ctx.bot, user.id, channels)
        if not_joined:
            sent = await update.message.reply_text(
                "📢 <b>Join our channels to unlock the bot:</b>",
                reply_markup=force_join_kb(not_joined), parse_mode=ParseMode.HTML)
            ctx.user_data["force_join_msg_id"] = sent.message_id
            asyncio.create_task(_schedule_delete(ctx.bot, user.id, sent.message_id, 300))
            return

    udata = await db.get_user(user.id)
    if udata and udata["is_banned"]:
        await update.message.reply_text(
            "🚫 <b>Access Denied</b>\n\nYou have been banned from using this bot.\n"
            f"Contact support: {DEVELOPER}", parse_mode=ParseMode.HTML)
        return

    first_name = user.first_name or "Friend"
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n" f"👋 Welcome, <b>{first_name}</b>!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n" f"🤖 You're now inside <b>{BOT_NAME}</b> —\n"
        f"your all-in-one digital services bot! 🚀\n\n" f"🛒 <b>What we offer:</b>\n"
        f"┣ 📱 Social Media Services\n" f"┣ 🎮 Game Top-Up\n"
        f"┣ 📞 Virtual Phone Numbers\n" f"┣ ⚡ Instant Delivery\n"
        f"┣ 💎 Cheapest Prices\n" f"┗ 🔒 Secure Payments\n\n"
        f"👇 Use the menu below to get started!\n\n" f"👨‍💻 Developer: {DEVELOPER}\n"
        f"⚙️ Powered by <b>Shuvo SMM</b>"
    )
    await update.message.reply_text(text, reply_markup=main_keyboard(), parse_mode=ParseMode.HTML)

async def force_join_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    channels = await db.get_force_channels()
    not_joined = await check_force_join(ctx.bot, user.id, channels)

    if not_joined:
        await query.edit_message_text(
            "❌ *You haven't joined all channels yet!*\n\n📢 Please join all required channels below, then try again.",
            parse_mode="Markdown", reply_markup=force_join_kb(not_joined))
    else:
        first_name = user.first_name or "Friend"
        await query.edit_message_text("✅ *Verification successful!*\n\nYou're all set — enjoy using the bot! 🎉", parse_mode="Markdown")
        welcome_text = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n" f"👋 Welcome, *{first_name}*!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n" f"🤖 You've joined *{BOT_NAME}* —\n"
            f"your all-in-one digital services bot! 🚀\n\n" f"🛒 *What you can do here:*\n"
            f"┣ 📱 Social Media Services\n" f"┣ 🎮 Game Top-Up\n"
            f"┣ 📞 Virtual Phone Numbers\n" f"┗ 💳 Fast & Easy Payments\n\n"
            f"👇 Use the menu below to get started!"
        )
        await ctx.bot.send_message(user.id, welcome_text, parse_mode="Markdown", reply_markup=main_keyboard())

# ═══════════════════════════════════════════════════════════════════
#  MY ACCOUNT
# ═══════════════════════════════════════════════════════════════════
async def my_account(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    udata   = await db.get_user(user_id)
    if not udata:
        await update.message.reply_text("⚠️ Account not found. Use /start first.")
        return
    rank   = await db.get_user_rank(user_id)
    vip_ok = await db.is_vip_active(udata)
    badge  = vip_badge(udata.get("vip_plan")) if vip_ok else "—"
    vip_str = f"{badge} {udata['vip_plan'].title()} VIP" if vip_ok else "None"
    text = (
        f"👤 <b>My Account</b>\n" f"{'─'*28}\n"
        f"👤 Name: <code>{udata['full_name']}</code>\n"
        f"🆔 User ID: <code>{user_id}</code>\n"
        f"💰 Balance: <code>{fmt_coins_full(udata['balance'])}</code>\n"
        f"📦 Total Orders: <code>{udata['total_orders']}</code>\n"
        f"💸 Total Spent: <code>{fmt_coins_full(udata['total_spent'])}</code>\n"
        f"💳 Total Deposited: <code>{fmt_coins_full(udata['total_deposited'])}</code>\n"
        f"👥 Referrals: <code>{udata['referral_count']}</code>\n"
        f"💎 Referral Earned: <code>{fmt_coins_full(udata['referral_earned'])}</code>\n"
        f"🏆 Rank: <code>#{rank}</code>\n" f"⭐ VIP: <code>{vip_str}</code>\n"
        f"📅 Joined: <code>{fmt_date(udata['join_date'])}</code>\n"
    )
    await update.message.reply_text(text, reply_markup=account_kb(), parse_mode=ParseMode.HTML)

async def account_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    action  = query.data
    if action == "acc_refresh":
        await query.answer("🔄 Refreshed!", show_alert=False)
        udata  = await db.get_user(user_id)
        rank   = await db.get_user_rank(user_id)
        vip_ok = await db.is_vip_active(udata)
        badge  = vip_badge(udata.get("vip_plan")) if vip_ok else "—"
        vip_str = f"{badge} {udata['vip_plan'].title()} VIP" if vip_ok else "None"
        text = (
            f"👤 <b>My Account</b>\n" f"{'─'*28}\n"
            f"👤 Name: <code>{udata['full_name']}</code>\n" f"🆔 User ID: <code>{user_id}</code>\n"
            f"💰 Balance: <code>{fmt_coins_full(udata['balance'])}</code>\n"
            f"📦 Total Orders: <code>{udata['total_orders']}</code>\n"
            f"💸 Total Spent: <code>{fmt_coins_full(udata['total_spent'])}</code>\n"
            f"👥 Referrals: <code>{udata['referral_count']}</code>\n"
            f"🏆 Rank: <code>#{rank}</code>\n" f"⭐ VIP: <code>{vip_str}</code>\n"
        )
        await query.edit_message_text(text, reply_markup=account_kb(), parse_mode=ParseMode.HTML)
    elif action == "acc_deposits":
        deps  = await db.get_user_deposits(user_id)
        if not deps:
            await query.answer("No deposits yet.", show_alert=True); return
        lines = ["💳 <b>Deposit History</b>\n"]
        for d in deps:
            lines.append(f"#{d['id']} | {d['method']} | {fmt_coins_full(d['amount'])} | {d['status']} | {fmt_date(d['created_at'])}")
        await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML)
    elif action == "acc_transactions":
        txns = await db.get_transactions(user_id)
        if not txns:
            await query.answer("No transactions yet.", show_alert=True); return
        lines = ["📤 <b>Transaction History</b>\n"]
        for t in txns:
            sign = "+" if t["type"] in ("credit", "deposit", "redeem", "daily", "referral") else "-"
            lines.append(f"{sign}{fmt_coins_full(t['amount'])} | {t['type'].title()} | {t.get('description','')} | {fmt_date(t['created_at'])}")
        await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════════
#  WALLET & BUY COINS
# ═══════════════════════════════════════════════════════════════════
async def wallet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    udata   = await db.get_user(user_id)
    if not udata:
        await update.message.reply_text("⚠️ Use /start first."); return
    text = (
        f"💰 <b>My Wallet</b>\n" f"{'─'*28}\n"
        f"💰 Balance: <code>{fmt_coins_full(udata['balance'])}</code>\n"
        f"📈 Total Deposits: <code>{fmt_coins_full(udata['total_deposited'])}</code>\n"
        f"📉 Total Spent: <code>{fmt_coins_full(udata['total_spent'])}</code>\n"
    )
    await update.message.reply_text(text, reply_markup=wallet_kb(), parse_mode=ParseMode.HTML)

async def wallet_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "wallet_add":
        text = ("╔══════════════════════╗\n" "      💎 <b>COIN MARKET</b> 💎\n" "╚══════════════════════╝\n\n"
                "নিচের প্যাকেজ থেকে পছন্দেরটি বেছে নাও\n" "অথবা নিজের ইচ্ছামতো পরিমাণ লিখে কিনো।\n\n"
                "──────────────────────\n" "⚡ <b>INSTANT DELIVERY</b>\n" "🔒 <b>TRUSTED SERVICE</b>\n"
                "💬 <b>SUPPORT 24/7</b>\n" "──────────────────────\n\n" "❓ সাহায্য: @shuvo_9882")
        await query.message.reply_text(text, reply_markup=coin_packages_kb(), parse_mode=ParseMode.HTML)
        return DEPOSIT_METHOD
    elif query.data == "wallet_history":
        user_id = query.from_user.id
        txns    = await db.get_transactions(user_id, 10)
        if not txns:
            await query.answer("No transactions yet.", show_alert=True); return ConversationHandler.END
        lines = ["📜 <b>Transaction History</b>\n"]
        for t in txns:
            sign = "+" if t["type"] in ("credit","deposit","redeem","daily","referral") else "-"
            lines.append(f"{sign}{fmt_coins_full(t['amount'])} | {t['type'].title()} | {fmt_date(t['created_at'])}")
        await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    return ConversationHandler.END

async def buy_coins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = ("╔══════════════════════╗\n" "      💎 <b>COIN MARKET</b> 💎\n" "╚══════════════════════╝\n\n"
            "নিচের প্যাকেজ থেকে পছন্দেরটি বেছে নাও\n" "অথবা নিজের ইচ্ছামতো পরিমাণ লিখে কিনো।\n\n"
            "──────────────────────\n" "⚡ <b>INSTANT DELIVERY</b>\n" "🔒 <b>TRUSTED SERVICE</b>\n"
            "💬 <b>SUPPORT 24/7</b>\n" "──────────────────────\n\n" "❓ সাহায্য: @shuvo_9882")
    if update.message:
        await update.message.reply_text(text, reply_markup=coin_packages_kb(), parse_mode=ParseMode.HTML)
    else:
        query = update.callback_query
        await query.message.reply_text(text, reply_markup=coin_packages_kb(), parse_mode=ParseMode.HTML)
    return DEPOSIT_METHOD

async def package_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    if data == "pkg_back":
        text = ("╔══════════════════════╗\n" "      💎 <b>COIN MARKET</b> 💎\n" "╚══════════════════════╝\n\n"
                "নিচের প্যাকেজ থেকে পছন্দেরটি বেছে নাও\n" "অথবা নিজের ইচ্ছামতো পরিমাণ লিখে কিনো।\n\n"
                "──────────────────────\n" "⚡ <b>INSTANT DELIVERY</b>\n" "🔒 <b>TRUSTED SERVICE</b>\n"
                "💬 <b>SUPPORT 24/7</b>\n" "──────────────────────\n\n" "❓ সাহায্য: @shuvo_9882")
        await query.edit_message_text(text, reply_markup=coin_packages_kb(), parse_mode=ParseMode.HTML)
        return DEPOSIT_METHOD
    if data == "contact_admin":
        await query.answer("Contact: @shuvo_9882", show_alert=True); return DEPOSIT_METHOD
    if data == "pkg:custom":
        ctx.user_data["deposit_package"] = "custom"
        ctx.user_data["deposit_coins"]   = None
        await query.edit_message_text(
            "✏️ <b>Custom Amount</b>\n\nকত Coins কিনতে চাও লেখো:\n<i>(শুধু সংখ্যা, উদাহরণ: 1500)</i>\n\n⬅️ /cancel লিখলে বাতিল হবে।",
            reply_markup=pkg_payment_kb(), parse_mode=ParseMode.HTML)
        return DEPOSIT_METHOD
    parts  = data.split(":")
    coins  = parts[1]
    price  = parts[2] if len(parts) > 2 else "?"
    ctx.user_data["deposit_package"] = coins
    ctx.user_data["deposit_coins"]   = coins
    ctx.user_data["deposit_price"]   = price
    await query.edit_message_text(
        f"🛍️ <b>{int(coins):,} Coins — {price}</b>\n\n💳 পেমেন্ট পদ্ধতি বেছে নাও:",
        reply_markup=pkg_payment_kb(), parse_mode=ParseMode.HTML)
    return DEPOSIT_METHOD

async def payment_method_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    method = query.data.split(":")[1]
    from config import PAYMENT_METHODS
    method_name = PAYMENT_METHODS.get(method, method)
    coins  = ctx.user_data.get("deposit_coins", "?")
    price  = ctx.user_data.get("deposit_price", "")

    if method == "mobile":
        await query.edit_message_text("⏳ <b>Secure Payment Gateway প্রস্তুত করা হচ্ছে...</b>\nঅনুগ্রহ করে কয়েক সেকেন্ড অপেক্ষা করুন।", parse_mode=ParseMode.HTML)
        price_str = str(price).replace("৳", "").replace(",", "").strip()
        try: amount = float(price_str)
        except ValueError: amount = float(ctx.user_data.get("deposit_amount", 0))
        invoice = await create_shuvopay_invoice(amount, provider="bkash")
        if not invoice or "id" not in invoice:
            error_detail = invoice.get("error", "Unknown error") if invoice else "No response"
            await query.edit_message_text("❌ Payment gateway সংযোগ করা যায়নি।\nঅনুগ্রহ করে @shuvo_9882 এ যোগাযোগ করুন।", parse_mode=ParseMode.HTML)
            user = query.from_user
            for admin_id in ADMIN_IDS:
                try: await ctx.bot.send_message(admin_id, f"🔴 <b>ShuvoPay Gateway Error</b>\n{'─'*28}\n👤 User: <code>{user.full_name}</code>\n🆔 User ID: <code>{user.id}</code>\n💰 Amount: <code>{amount}</code>\n⚠️ Error: <code>{error_detail}</code>", parse_mode=ParseMode.HTML)
                except Exception: pass
            return DEPOSIT_METHOD
        invoice_id = invoice["id"]
        pay_url = f"{SHUVOPAY_CHECKOUT}?id={invoice_id}"
        ctx.user_data["shuvopay_invoice_id"] = invoice_id
        ctx.user_data["deposit_amount"] = amount
        ctx.user_data["deposit_method"] = "mobile"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💳 Pay Now", url=pay_url)], [InlineKeyboardButton("✅ আমি পেমেন্ট করেছি", callback_data=f"check_pay:{invoice_id}")]])
        await query.edit_message_text(
            f"✅ <b>পেমেন্ট লিংক প্রস্তুত করা হয়েছে!</b>\n\n──────────────────────\n💰 Amount: <b>{price}</b>\n🆔 Order ID: <code>{invoice['invoice_number']}</code>\n──────────────────────\n\nনিচের <b>Pay Now</b> বাটনে ক্লিক করে পেমেন্ট সম্পন্ন করুন।",
            reply_markup=kb, parse_mode=ParseMode.HTML)
        return DEPOSIT_METHOD

    payment_info = {
        "binance":  "💵 <b>Binance Pay ID:</b> <code>your_binance_id</code>\n<b>Min:</b> $1",
        "usdt_trc": "🟢 <b>USDT TRC20 Address:</b>\n<code>TYourWalletAddressHere</code>\n<b>Min:</b> $1",
        "usdt_bep": "🟡 <b>USDT BEP20 Address:</b>\n<code>0xYourWalletAddressHere</code>\n<b>Min:</b> $1",
    }
    if method not in payment_info:
        await query.answer("This method is not available.", show_alert=True); return DEPOSIT_METHOD
    pkg_line = f"🛍️ Package: <b>{int(coins):,} Coins — {price}</b>\n\n" if coins and coins != "?" else ""
    ctx.user_data["deposit_method"] = method
    await query.edit_message_text(
        f"💳 <b>{method_name}</b>\n\n{pkg_line}{payment_info[method]}\n\n✅ পেমেন্ট করার পর Transaction ID পাঠাও।\n❓ সাহায্য: @shuvo_9882\n\n👇 Deposit amount লেখো (শুধু সংখ্যা):",
        parse_mode=ParseMode.HTML)
    return DEPOSIT_AMOUNT

async def check_payment_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("যাচাই করা হচ্ছে...")
    invoice_id = query.data.split(":")[1]
    status = await check_shuvopay_invoice(invoice_id)
    if status == "paid":
        user_id = update.effective_user.id
        amount  = ctx.user_data.get("deposit_amount", 0)
        coins   = ctx.user_data.get("deposit_coins", amount)
        await db.add_coins(user_id, float(coins), method="ShuvoPay (bKash)", txn_id=invoice_id)
        await query.edit_message_text(f"🎉 <b>পেমেন্ট সফল!</b>\n\n✅ <b>{fmt_coins_full(float(coins))} Coins</b> তোমার account এ যোগ হয়েছে।\n\nধন্যবাদ! 🙏", parse_mode=ParseMode.HTML, reply_markup=None)
        udata = await db.get_user(user_id)
        for admin_id in ADMIN_IDS:
            try: await ctx.bot.send_message(admin_id, f"✅ <b>Auto Payment Verified</b>\n👤 {udata['full_name']} (@{udata.get('username','')})\n💰 {fmt_coins_full(float(coins))}\n🆔 Invoice: <code>{invoice_id}</code>", parse_mode=ParseMode.HTML)
            except Exception: pass
        ctx.user_data.clear()
    else:
        pay_url = f"{SHUVOPAY_CHECKOUT}?id={invoice_id}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💳 Pay Now", url=pay_url)], [InlineKeyboardButton("✅ আমি পেমেন্ট করেছি", callback_data=f"check_pay:{invoice_id}")]])
        await query.edit_message_text(
            f"⏳ <b>পেমেন্ট এখনো confirm হয়নি।</b>\n\nপেমেন্ট করে থাকলে কিছুক্ষণ অপেক্ষা করুন।\nতারপর আবার <b>আমি পেমেন্ট করেছি</b> বাটনে চাপুন।\n\n❓ সমস্যা হলে: @shuvo_9882",
            reply_markup=kb, parse_mode=ParseMode.HTML)

async def deposit_amount_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.replace(".", "", 1).isdigit():
        await update.message.reply_text("❌ Invalid amount. Enter numbers only (e.g. 10 or 5.50):"); return DEPOSIT_AMOUNT
    amount = float(text)
    from config import MIN_DEPOSIT
    if amount < MIN_DEPOSIT:
        await update.message.reply_text(f"❌ Minimum deposit is {MIN_DEPOSIT} coins."); return DEPOSIT_AMOUNT
    ctx.user_data["deposit_amount"] = amount
    await update.message.reply_text(f"✅ Amount: <b>{fmt_coins_full(amount)}</b>\n\n📝 Now send your <b>Transaction ID / Reference Number</b>:", parse_mode=ParseMode.HTML, reply_markup=cancel_keyboard())
    return DEPOSIT_TXN

async def deposit_txn_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txn_id  = update.message.text.strip()
    user_id = update.effective_user.id
    method  = ctx.user_data.get("deposit_method", "unknown")
    amount  = ctx.user_data.get("deposit_amount", 0)
    dep_id = await db.create_deposit(user_id, amount, method, txn_id)
    await update.message.reply_text(
        f"✅ <b>Deposit Request Submitted!</b>\n\n🆔 Request ID: <code>#{dep_id}</code>\n💰 Amount: <code>{fmt_coins_full(amount)}</code>\n💳 Method: <code>{method}</code>\n📋 TXN ID: <code>{txn_id}</code>\n\n⏳ Admin will verify and approve within 24h.",
        parse_mode=ParseMode.HTML, reply_markup=main_keyboard())
    udata = await db.get_user(user_id)
    admin_msg = (
        f"💳 <b>New Deposit Request</b>\n{'─'*28}\n"
        f"👤 User: <code>{udata['full_name']}</code> (<code>@{udata.get('username','')}</code>)\n"
        f"🆔 User ID: <code>{user_id}</code>\n💰 Amount: <code>{fmt_coins_full(amount)}</code>\n"
        f"💳 Method: <code>{method}</code>\n📋 TXN ID: <code>{txn_id}</code>\n🆔 Request ID: <code>#{dep_id}</code>"
    )
    from keyboards.inline import deposit_approve_kb
    for admin_id in ADMIN_IDS:
        try: await ctx.bot.send_message(admin_id, admin_msg, reply_markup=deposit_approve_kb(dep_id), parse_mode=ParseMode.HTML)
        except Exception: pass
    ctx.user_data.clear()
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════
#  SERVICES LIST & CATEGORY CALLBACK
# ═══════════════════════════════════════════════════════════════════
async def search_service_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 <b>Service Search</b>\n\nService ID লেখো এভাবে:\n<code>/search 6370</code>", parse_mode=ParseMode.HTML)

async def services_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _delete_menu_msg(update, ctx, "new_order_msg_id")
    await _delete_menu_msg(update, ctx, "partner_entry_msg_id")
    await _send_replacing(update, ctx, "services_list_msg_id", "📊 <b>Services List</b>\n\nকোন সার্ভিস দেখতে চাও?", reply_markup=service_menu_keyboard(), parse_mode=ParseMode.HTML)

async def services_list_smm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _delete_menu_msg(update, ctx, "services_list_msg_id")
    await _delete_menu_msg(update, ctx, "partner_entry_msg_id")
    ctx.user_data["current_api_source"] = "smm1"
    cats = await db.get_categories(api_source="smm1")
    if not cats:
        await update.message.reply_text("⚠️ No services synced yet.\nAdmin needs to sync services from the API panel.")
        await _restore_service_menu(update, ctx); return
    upd_ch = await db.get_setting("updates_channel", "")
    await update.message.reply_text("🛒 <b>Select Service Category:</b>\n\nআপনি কোন ক্যাটাগরির সার্ভিস নিতে চান নিচে নির্বাচন করুন 👇", reply_markup=categories_kb(cats, CATEGORY_ICONS, upd_ch), parse_mode=ParseMode.HTML)
    await _restore_service_menu(update, ctx)

async def services_list_smm2(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _delete_menu_msg(update, ctx, "services_list_msg_id")
    await _delete_menu_msg(update, ctx, "partner_entry_msg_id")
    ctx.user_data["current_api_source"] = "smm2"
    cats = await db.get_categories(api_source="smm2")
    if not cats:
        await update.message.reply_text("⚠️ CSB SMM services synced হয়নি।\nAdmin /syncservices দিয়ে sync করুন।")
        await _restore_service_menu(update, ctx); return
    upd_ch = await db.get_setting("updates_channel", "")
    await update.message.reply_text("🛒 <b>Select Service Category:</b>\n\nআপনি কোন ক্যাটাগরির সার্ভিস নিতে চান নিচে নির্বাচন করুন 👇", reply_markup=categories_kb(cats, CATEGORY_ICONS, upd_ch), parse_mode=ParseMode.HTML)
    await _restore_service_menu(update, ctx)

async def services_list_telegram(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _delete_menu_msg(update, ctx, "services_list_msg_id")
    await _delete_menu_msg(update, ctx, "partner_entry_msg_id")
    from handlers.topup import topup_start_telegram
    await topup_start_telegram(update, ctx)
    await _restore_service_menu(update, ctx)

PLATFORM_LABELS = {
    "facebook": "📘 FACEBOOK", "instagram": "📸 INSTAGRAM", "tiktok": "🎵 TIK TOK",
    "youtube": "▶️ YOUTUBE", "telegram": "✈️ TELEGRAM", "twitter": "𝕏 TWITTER",
    "spotify": "🎧 SPOTIFY", "freefire": "🔥 FREE FIRE",
}

async def category_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    api_src = ctx.user_data.get("current_api_source", "smm1")

    if data.startswith("svc_page|"):
        parts    = data.split("|", 2)
        page     = int(parts[1])
        category = parts[2]
        services = await db.get_services_by_category(category, api_source=api_src)
        if not services:
            await query.answer("No services found.", show_alert=True); return
        total_pages = max(1, (len(services) + 7) // 8)
        await query.edit_message_text(f"📋 <b>Select Service:</b> (Page {page+1}/{total_pages})\n\nনিচের বাটন থেকে আপনার প্রয়োজনীয় সার্ভিসটি বেছে নিন 👇", reply_markup=services_kb(services, category, page=page), parse_mode=ParseMode.HTML)
        return

    if data in ("cat_back", "svc_list_back"):
        platform = ctx.user_data.get("current_platform", "")
        all_cats = await db.get_categories(api_source=api_src)
        
        if platform == "other":
            filtered = [c for c in all_cats if get_platform_name(c) == "other"]
        elif platform:
            filtered = [c for c in all_cats if get_platform_name(c) == platform]
        else:
            filtered = all_cats
            
        if not filtered or len(filtered) <= 1:
            cats   = await db.get_categories(api_source=api_src)
            upd_ch = await db.get_setting("updates_channel", "")
            await query.edit_message_text("🛒 <b>Select Service Category:</b>\n\nআপনি কোন ক্যাটাগরির সার্ভিস নিতে চান নিচে নির্বাচন করুন 👇", reply_markup=categories_kb(cats, CATEGORY_ICONS, upd_ch), parse_mode=ParseMode.HTML)
            return
            
        label = PLATFORM_LABELS.get(platform, f"🔹 {platform.title()}")
        await query.edit_message_text(f"{label}\n\nChoose a category:", reply_markup=platform_categories_kb(platform, filtered, CATEGORY_ICONS), parse_mode=ParseMode.HTML)
        return

    if data == "platform_back":
        cats   = await db.get_categories(api_source=api_src)
        upd_ch = await db.get_setting("updates_channel", "")
        await query.edit_message_text("🛒 <b>Select Service Category:</b>\n\nআপনি কোন ক্যাটাগরির সার্ভিস নিতে চান নিচে নির্বাচন করুন 👇", reply_markup=categories_kb(cats, CATEGORY_ICONS, upd_ch), parse_mode=ParseMode.HTML)
        return

    if data.startswith("platform:"):
        platform = data[9:]
        ctx.user_data["current_platform"] = platform
        all_cats = await db.get_categories(api_source=api_src)
        
        if platform == "other":
            filtered = [c for c in all_cats if get_platform_name(c) == "other"]
        else:
            filtered = [c for c in all_cats if get_platform_name(c) == platform]
            
        if not filtered:
            await query.answer("⚠️ এই ক্যাটাগরিতে এখনো কোনো সার্ভিস নেই।", show_alert=True); return
        if len(filtered) == 1:
            await _show_category_services(query, ctx, filtered[0], api_src); return
        label = PLATFORM_LABELS.get(platform, f"🔹 {platform.title()}")
        await query.edit_message_text(f"{label}\n\nChoose a category:", reply_markup=platform_categories_kb(platform, filtered, CATEGORY_ICONS), parse_mode=ParseMode.HTML)
        return

    if data == "sub_back":
        category = ctx.user_data.get("current_category", "")
        grouped  = ctx.user_data.get("current_grouped", {})
        platform = ctx.user_data.get("sub_platform") or ctx.user_data.get("current_platform", "")
        if not grouped:
            services = await db.get_services_by_category(category)
            platform = platform or (_detect_platform(services) or "")
            grouped  = _group_services(services, platform)
        rows = []
        for label, items in sorted(grouped.items(), key=lambda x: -len(x[1])):
            rows.append([StyledButton(text=f"{label} ({len(items)})", callback_data=f"subcat:{label}", style="success")])
        rows.append([StyledButton(text="🔙 Back", callback_data="cat_back", style="danger")])
        icon = category_icon(category)
        await query.edit_message_text(f"{icon} <b>{category}</b>\n\nকোন ধরনের সার্ভিস চান?", reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)
        return

    if data.startswith("subcat:"):
        label    = data[7:]
        category = ctx.user_data.get("current_category", "")
        services = await db.get_services_by_category(category)
        platform = ctx.user_data.get("sub_platform") or ctx.user_data.get("current_platform", "")
        if not platform: platform = _detect_platform(services) or ""
        filtered = [s for s in services if _get_subcat(platform, s.get("name", "")) == label]
        if not filtered:
            await query.answer("এই সাব-ক্যাটাগরিতে কিছু নেই।", show_alert=True); return
        ctx.user_data["current_subcat"] = label
        ctx.user_data["current_subcat_services"] = filtered
        icon = category_icon(category)
        await query.edit_message_text(f"{icon} <b>{label}</b> — {len(filtered)}টি সার্ভিস\n\nChoose one:", reply_markup=services_kb(filtered, f"{category}::{label}"), parse_mode=ParseMode.HTML)
        return

    if data.startswith("catidx:"):
        idx      = int(data[7:])
        platform = ctx.user_data.get("current_platform", "")
        all_cats = await db.get_categories(api_source=api_src)
        
        if platform == "other":
            filtered = [c for c in all_cats if get_platform_name(c) == "other"]
        elif platform:
            filtered = [c for c in all_cats if get_platform_name(c) == platform]
        else:
            filtered = all_cats
            
        if idx >= len(filtered):
            await query.answer("Category not found.", show_alert=True); return
        category = filtered[idx]
        await _show_category_services(query, ctx, category, api_src)
        return

    if data.startswith("cat:"):
        category = data[4:]
        await _show_category_services(query, ctx, category, api_src)
        return

    if data == "noop":
        await query.answer(); return

async def _show_category_services(query, ctx, category: str, api_source: str = None):
    src      = api_source or ctx.user_data.get("current_api_source", "smm1")
    services = await db.get_services_by_category(category, api_source=src)
    if not services:
        await query.answer("No services in this category.", show_alert=True); return
    ctx.user_data["current_category"]   = category
    ctx.user_data["current_api_source"] = src
    ctx.user_data.pop("current_subcat", None)
    ctx.user_data.pop("current_subcat_services", None)
    
    platform = _detect_platform(services) or get_platform_name(category)
    ctx.user_data["sub_platform"] = platform
    grouped = _group_services(services, platform) if platform else {}
    
    if platform and _should_show_subcat(services, grouped):
        ctx.user_data["current_grouped"] = grouped
        rows = []
        for label, items in sorted(grouped.items(), key=lambda x: -len(x[1])):
            rows.append([StyledButton(text=f"{label} ({len(items)})", callback_data=f"subcat:{label}", style="success")])
        rows.append([StyledButton(text="◀ Back", callback_data="cat_back", style="danger")])
        icon = category_icon(category)
        await query.edit_message_text(f"{icon} <b>{category}</b>\n\nকোন ধরনের সার্ভিস চান?", reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)
    else:
        total_pages = max(1, (len(services) + 7) // 8)
        icon = category_icon(category)
        await query.edit_message_text(f"📋 <b>Select Service:</b> (Page 1/{total_pages})\n\nনিচের বাটন থেকে আপনার প্রয়োজনীয় সার্ভিসটি বেছে নিন 👇", reply_markup=services_kb(services, category, page=0), parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════════
#  SERVICE DETAIL & ORDER FLOW
# ═══════════════════════════════════════════════════════════════════
async def service_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data

    if data == "svc_back":
        subcat = ctx.user_data.get("current_subcat")
        if subcat:
            services = ctx.user_data.get("current_subcat_services") or []
            category = ctx.user_data.get("current_category", "")
            if services:
                icon = category_icon(category)
                await query.edit_message_text(f"{icon} <b>{subcat}</b> — {len(services)}টি সার্ভিস\n\nChoose one:", reply_markup=services_kb(services, f"{category}::{subcat}"), parse_mode=ParseMode.HTML)
                return
        category = ctx.user_data.get("current_category", "")
        grouped  = ctx.user_data.get("current_grouped", {})
        platform = ctx.user_data.get("sub_platform", "")
        if grouped and platform:
            rows = []
            for label, items in sorted(grouped.items(), key=lambda x: -len(x[1])):
                rows.append([StyledButton(text=f"{label} ({len(items)})", callback_data=f"subcat:{label}", style="success")])
            rows.append([StyledButton(text="🔙 Back", callback_data="cat_back", style="danger")])
            icon = category_icon(category)
            await query.edit_message_text(f"{icon} <b>{category}</b>\n\nকোন ধরনের সার্ভিস চান?", reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)
            return
        services = await db.get_services_by_category(category)
        if not services:
            await query.answer("No services.", show_alert=True); return
        icon = category_icon(category)
        await query.edit_message_text(f"{icon} <b>{category}</b>\n\nChoose a service:", reply_markup=services_kb(services, category), parse_mode=ParseMode.HTML)
        return

    service_id = data[4:]
    svc = await db.get_service(service_id)
    if not svc:
        await query.answer("Service not found.", show_alert=True); return
    refill_str  = "✅ Yes" if svc.get("refill")  else "❌ No"
    cancel_str  = "✅ Yes" if svc.get("cancel")  else "❌ No"
    icon = category_icon(svc.get("category", ""))
    
    api_rate_bdt = float(svc['rate']) * (1 + SERVICE_MARKUP_PCT / 100)
    api_rate_usd = api_rate_bdt / USD_TO_BDT
    
    if is_game_service(svc.get("name", "")):
        rate_text = f"💵 Rate: <code>৳{api_rate_bdt:,.2f} per Package</code>\n"
    else:
        rate_text = f"💵 Rate: <code>৳{api_rate_bdt:,.2f} per 1000 (≈ ${api_rate_usd:,.4f})</code>\n"
    
    text = (
        f"{icon} <b>{svc['name']}</b>\n" f"{'─'*28}\n"
        f"🆔 Service ID: <code>{svc['service_id']}</code>\n"
        f"{rate_text}"
        f"📊 Min: <code>{svc['min_order']:,}</code>\n"
        f"📈 Max: <code>{svc['max_order']:,}</code>\n"
        f"♻️ Refill: {refill_str}\n" f"❌ Cancel: {cancel_str}\n"
    )
    if svc.get("description"):
        text += f"\n📝 <i>{svc['description']}</i>"
    ctx.user_data["viewing_service"] = service_id
    await query.edit_message_text(text, reply_markup=service_detail_kb(service_id), parse_mode=ParseMode.HTML)

async def new_order(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _delete_menu_msg(update, ctx, "services_list_msg_id")
    await _delete_menu_msg(update, ctx, "partner_entry_msg_id")
    await _send_replacing(update, ctx, "new_order_msg_id", "🛒 <b>New Order</b>\n\nকোন ধরনের অর্ডার দিতে চাও?", reply_markup=order_menu_keyboard(), parse_mode=ParseMode.HTML)
    return ConversationHandler.END

async def new_order_smm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["current_api_source"] = "smm1"
    cats = await db.get_categories(api_source="smm1")
    if not cats:
        await update.message.reply_text("⚠️ No services available. Try again later.")
        return ConversationHandler.END
    upd_ch = await db.get_setting("updates_channel", "")
    await update.message.reply_text("🛒 <b>Select Service Category:</b>\n\nআপনি কোন ক্যাটাগরির সার্ভিস নিতে চান নিচে নির্বাচন করুন 👇", reply_markup=categories_kb(cats, CATEGORY_ICONS, upd_ch), parse_mode=ParseMode.HTML)
    return ORDER_PLATFORM

async def new_order_smm2(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["current_api_source"] = "smm2"
    cats = await db.get_categories(api_source="smm2")
    if not cats:
        await update.message.reply_text("⚠️ CSB SMM services নেই।\nAdmin /syncservices দিয়ে sync করুন।")
        return ConversationHandler.END
    upd_ch = await db.get_setting("updates_channel", "")
    await update.message.reply_text("🛒 <b>Select Service Category:</b>\n\nআপনি কোন ক্যাটাগরির সার্ভিস নিতে চান নিচে নির্বাচন করুন 👇", reply_markup=categories_kb(cats, CATEGORY_ICONS, upd_ch), parse_mode=ParseMode.HTML)
    return ORDER_PLATFORM

# 🔥 NEW: Game Topup 2 (CSB API Free Fire only)
async def new_order_game2(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["current_api_source"] = "smm2"
    cats = await db.get_categories(api_source="smm2")
    
    # Filter only Free Fire categories
    ff_cats = [c for c in cats if any(kw in c.lower() for kw in ["free fire", "freefire", "free_fire", "diamond", "uc"])]
    
    if not ff_cats:
        await update.message.reply_text("⚠️ Free Fire services not found in CSB API.")
        return ConversationHandler.END
        
    upd_ch = await db.get_setting("updates_channel", "")
    await update.message.reply_text(
        "🎮 <b>Game TopUp (2) - Free Fire</b>\n\nSelect a package category:",
        reply_markup=categories_kb(ff_cats, CATEGORY_ICONS, upd_ch), 
        parse_mode=ParseMode.HTML
    )
    return ORDER_PLATFORM

async def new_order_telegram(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from handlers.topup import topup_start_telegram
    return await topup_start_telegram(update, ctx)

async def order_start_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    service_id = query.data.split(":")[1]
    svc = await db.get_service(service_id)
    if not svc:
        await query.answer("Service not found.", show_alert=True); return ORDER_LINK
    ctx.user_data["order_service_id"]   = service_id
    ctx.user_data["order_service_name"] = svc["name"]
    ctx.user_data["order_service"]      = svc
    ctx.user_data["order_category"]     = svc["category"]
    
    if is_game_service(svc.get("name", "")):
        prompt = f"🔗 <b>Step — Enter UID</b>\n\nService: <b>{svc['name']}</b>\n\nPlease send your Free Fire UID:"
    else:
        prompt = f"🔗 <b>Step — Enter Link</b>\n\nService: <b>{svc['name']}</b>\n\nPlease send the target link/username:"
        
    await query.edit_message_text(prompt, parse_mode=ParseMode.HTML)
    return ORDER_LINK

async def order_platform_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    api_src = ctx.user_data.get("current_api_source", "smm1")

    if data == "platform_back" or data == "order_platform_back":
        cats   = await db.get_categories(api_source=api_src)
        upd_ch = await db.get_setting("updates_channel", "")
        await query.edit_message_text("🛒 <b>Select Service Category:</b>\n\nআপনি কোন ক্যাটাগরির সার্ভিস নিতে চান নিচে নির্বাচন করুন 👇", reply_markup=categories_kb(cats, CATEGORY_ICONS, upd_ch), parse_mode=ParseMode.HTML)
        return ORDER_PLATFORM

    if data.startswith("platform:"):
        platform = data[9:]
        ctx.user_data["order_platform"] = platform
        all_cats = await db.get_categories(api_source=api_src)
        
        if platform == "other":
            filtered = [c for c in all_cats if get_platform_name(c) == "other"]
        else:
            filtered = [c for c in all_cats if get_platform_name(c) == platform]
            
        if not filtered:
            await query.answer("⚠️ এই ক্যাটাগরিতে এখনো কোনো সার্ভিস নেই।", show_alert=True); return ORDER_PLATFORM
        if len(filtered) == 1:
            category = filtered[0]
            ctx.user_data["order_category"] = category
            services = await db.get_services_by_category(category, api_source=api_src)
            if not services:
                await query.answer("No services in this category.", show_alert=True); return ORDER_PLATFORM
            platform_detected = _detect_platform(services) or platform
            grouped = _group_services(services, platform_detected) if platform_detected else {}
            if platform_detected and _should_show_subcat(services, grouped):
                ctx.user_data["current_grouped"] = grouped
                ctx.user_data["sub_platform"] = platform_detected
                rows = []
                for label, items in sorted(grouped.items(), key=lambda x: -len(x[1])):
                    rows.append([StyledButton(text=f"{label} ({len(items)})", callback_data=f"subcat:{label}", style="success")])
                rows.append([StyledButton(text="◀ Back", callback_data="platform_back", style="danger")])
                await query.edit_message_text(f"📦 <b>{category}</b>\n\nকোন ধরনের সার্ভিস চান?", reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)
            else:
                total_pages = max(1, (len(services) + 7) // 8)
                await query.edit_message_text(f"📋 <b>Select Service:</b> (Page 1/{total_pages})\n\nনিচের বাটন থেকে আপনার প্রয়োজনীয় সার্ভিসটি বেছে নিন 👇", reply_markup=services_kb(services, category), parse_mode=ParseMode.HTML)
            return ORDER_SERVICE
        label = PLATFORM_LABELS.get(platform, f"🔹 {platform.title()}")
        await query.edit_message_text(f"{label}\n\nStep 2 — Choose a category:", reply_markup=platform_categories_kb(platform, filtered, CATEGORY_ICONS), parse_mode=ParseMode.HTML)
        return ORDER_PLATFORM

    if data.startswith("catidx:"):
        idx      = int(data[7:])
        platform = ctx.user_data.get("order_platform", "")
        all_cats = await db.get_categories(api_source=api_src)
        if platform == "other":
            filtered = [c for c in all_cats if get_platform_name(c) == "other"]
        elif platform:
            filtered = [c for c in all_cats if get_platform_name(c) == platform]
        else:
            filtered = all_cats
        if idx >= len(filtered):
            await query.answer("Category not found.", show_alert=True); return ORDER_PLATFORM
        category = filtered[idx]
        ctx.user_data["order_category"] = category
        services = await db.get_services_by_category(category, api_source=api_src)
        if not services:
            await query.answer("No services in this category.", show_alert=True); return ORDER_PLATFORM
        total_pages = max(1, (len(services) + 7) // 8)
        icon = category_icon(category)
        await query.edit_message_text(f"📋 <b>Select Service:</b> (Page 1/{total_pages})\n\nনিচের বাটন থেকে আপনার প্রয়োজনীয় সার্ভিসটি বেছে নিন 👇", reply_markup=services_kb(services, category), parse_mode=ParseMode.HTML)
        return ORDER_SERVICE

    if data.startswith("subcat:"):
        label    = data[7:]
        category = ctx.user_data.get("order_category", "")
        services = await db.get_services_by_category(category, api_source=api_src)
        platform = ctx.user_data.get("sub_platform", "")
        if not platform: platform = _detect_platform(services) or ""
        filtered = [s for s in services if _get_subcat(platform, s.get("name", "")) == label]
        if not filtered:
            await query.answer("এই সাব-ক্যাটাগরিতে কিছু নেই।", show_alert=True); return ORDER_SERVICE
        ctx.user_data["order_subcat"] = label
        ctx.user_data["order_subcat_services"] = filtered
        icon = category_icon(category)
        await query.edit_message_text(f"{icon} <b>{label}</b> — {len(filtered)}টি সার্ভিস\n\nChoose one:", reply_markup=services_kb(filtered, f"{category}::{label}"), parse_mode=ParseMode.HTML)
        return ORDER_SERVICE

    if data == "sub_back":
        category = ctx.user_data.get("order_category", "")
        grouped  = ctx.user_data.get("current_grouped", {})
        platform = ctx.user_data.get("sub_platform", "")
        if grouped and platform:
            rows = []
            for label, items in sorted(grouped.items(), key=lambda x: -len(x[1])):
                rows.append([StyledButton(text=f"{label} ({len(items)})", callback_data=f"subcat:{label}", style="success")])
            rows.append([StyledButton(text="◀ Back", callback_data="platform_back", style="danger")])
            icon = category_icon(category)
            await query.edit_message_text(f"{icon} <b>{category}</b>\n\nকোন ধরনের সার্ভিস চান?", reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)
            return ORDER_SERVICE
    return ORDER_PLATFORM

async def order_category_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    api_src  = ctx.user_data.get("current_api_source", "smm1")
    category = query.data[4:]
    services = await db.get_services_by_category(category, api_source=api_src)
    if not services:
        await query.answer("No services.", show_alert=True); return ORDER_CATEGORY
    ctx.user_data["order_category"] = category
    total_pages = max(1, (len(services) + 7) // 8)
    icon = category_icon(category)
    await query.edit_message_text(f"📋 <b>Select Service:</b> (Page 1/{total_pages})\n\nনিচের বাটন থেকে আপনার প্রয়োজনীয় সার্ভিসটি বেছে নিন 👇", reply_markup=services_kb(services, category), parse_mode=ParseMode.HTML)
    return ORDER_SERVICE

async def order_service_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    
    if data.startswith("svc_page|"):
        parts    = data.split("|", 2)
        page     = int(parts[1])
        category = parts[2]
        api_src  = ctx.user_data.get("current_api_source", "smm1")
        services = await db.get_services_by_category(category, api_source=api_src)
        if not services:
            await query.answer("No services found.", show_alert=True); return ORDER_SERVICE
        total_pages = max(1, (len(services) + 7) // 8)
        icon = category_icon(category)
        await query.edit_message_text(f"📋 <b>Select Service:</b> (Page {page+1}/{total_pages})\n\nনিচের বাটন থেকে আপনার প্রয়োজনীয় সার্ভিসটি বেছে নিন 👇", reply_markup=services_kb(services, category, page=page), parse_mode=ParseMode.HTML)
        return ORDER_SERVICE

    service_id = data[4:]
    svc = await db.get_service(service_id)
    if not svc:
        await query.answer("Service not found.", show_alert=True); return ORDER_SERVICE
    ctx.user_data["order_service_id"]   = service_id
    ctx.user_data["order_service_name"] = svc["name"]
    ctx.user_data["order_service"]      = svc
    
    if is_game_service(svc.get("name", "")):
        prompt = f"🔗 <b>Step 3 — Enter UID</b>\n\nService: <b>{svc['name']}</b>\n📊 Min: <code>{svc['min_order']:,}</code> | Max: <code>{svc['max_order']:,}</code>\n\nPlease send your Free Fire UID:"
    else:
        prompt = f"🔗 <b>Step 3 — Enter Link</b>\n\nService: <b>{svc['name']}</b>\n📊 Min: <code>{svc['min_order']:,}</code> | Max: <code>{svc['max_order']:,}</code>\n\nPlease send the target URL / username:"
        
    await query.edit_message_text(prompt, parse_mode=ParseMode.HTML)
    return ORDER_LINK

async def order_link_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    if len(link) < 3:
        await update.message.reply_text("❌ Invalid. Please try again:"); return ORDER_LINK
    ctx.user_data["order_link"] = link
    svc = ctx.user_data.get("order_service", {})
    
    # 🔥 If Game Service, skip quantity step and set to 1
    if is_game_service(svc.get("name", "")):
        qty = 1
        ctx.user_data["order_quantity"] = qty
        
        rate_bdt = float(svc.get("rate", 0)) * (1 + SERVICE_MARKUP_PCT / 100)
        charge = rate_bdt # 1 package
        ctx.user_data["order_charge"] = charge
        
        user_id = update.effective_user.id
        udata   = await db.get_user(user_id)
        bal_coins = float(udata['balance'])
        
        text = (
            f"📋 <b>Order Confirmation</b>\n" f"{'─'*28}\n"
            f"📦 Service: <code>{svc['name']}</code>\n" f"🔗 UID: <code>{link}</code>\n"
            f"📊 Quantity: <code>1 Package</code>\n"
            f"💵 Cost: <code>{charge:,.2f} Coins</code>\n\n"
            f"💰 Balance: <code>{bal_coins:,.2f} Coins</code>\n\n"
            f"✅ Confirm order?"
        )
        service_id = ctx.user_data.get("order_service_id", "")
        await update.message.reply_text(text, reply_markup=confirm_order_kb(service_id), parse_mode=ParseMode.HTML)
        return ORDER_CONFIRM
        
    # Regular flow for SMM services
    await update.message.reply_text(f"📊 <b>Step 4 — Enter Quantity</b>\n\nMin: <code>{svc.get('min_order',1):,}</code> | Max: <code>{svc.get('max_order',1000000):,}</code>\n\nHow many?", parse_mode=ParseMode.HTML, reply_markup=cancel_keyboard())
    return ORDER_QUANTITY

async def order_quantity_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ Enter a valid number:"); return ORDER_QUANTITY
    qty = int(text)
    svc = ctx.user_data.get("order_service", {})
    min_q = svc.get("min_order", 1)
    max_q = svc.get("max_order", 1_000_000)
    if qty < min_q or qty > max_q:
        await update.message.reply_text(f"❌ Quantity must be between <code>{min_q:,}</code> and <code>{max_q:,}</code>.", parse_mode=ParseMode.HTML)
        return ORDER_QUANTITY

    rate_bdt = float(svc.get("rate", 0)) * (1 + SERVICE_MARKUP_PCT / 100)
    charge_bdt = round((qty / 1000) * rate_bdt, 2)
    charge     = charge_bdt

    user_id = update.effective_user.id
    udata   = await db.get_user(user_id)
    vip_ok  = await db.is_vip_active(udata)
    discount = 0
    if vip_ok and udata.get("vip_plan"):
        discount   = VIP_PLANS.get(udata["vip_plan"], {}).get("discount", 0)
        charge_bdt = round(charge_bdt * (1 - discount / 100), 2)
        charge     = charge_bdt

    ctx.user_data["order_quantity"]   = qty
    ctx.user_data["order_charge"]     = charge
    link = ctx.user_data.get("order_link", "")
    name = ctx.user_data.get("order_service_name", "")
    disc_str = f"\n🏷️ VIP Discount: <code>{discount}%</code>" if discount else ""

    bal_coins = float(udata['balance'])
    
    if bal_coins < charge:
        needed = round(charge - bal_coins, 2)
        await update.effective_message.reply_text(
            f"❌ <b>Balance কম!</b>\n\n"
            f"💵 Cost: <code>{charge:,.2f} Coins</code>\n"
            f"💰 তোমার Balance: <code>{bal_coins:,.2f} Coins</code>\n"
            f"⚠️ আরও <code>{needed:,.2f} Coins</code> দরকার\n\n"
            f"💳 <b>Buy Coins</b> থেকে balance বাড়াও।",
            reply_markup=main_keyboard(), parse_mode=ParseMode.HTML)
        ctx.user_data.clear()
        return ConversationHandler.END

    text = (
        f"📋 <b>Order Confirmation</b>\n" f"{'─'*28}\n"
        f"📦 Service: <code>{name}</code>\n" f"🔗 Link: <code>{link}</code>\n"
        f"📊 Quantity: <code>{qty:,}</code>\n"
        f"💵 Cost: <code>{charge:,.2f} Coins</code>{disc_str}\n\n"
        f"💰 Balance: <code>{bal_coins:,.2f} Coins</code>\n\n"
        f"✅ Confirm order?"
    )
    service_id = ctx.user_data.get("order_service_id", "")
    await update.message.reply_text(text, reply_markup=confirm_order_kb(service_id), parse_mode=ParseMode.HTML)
    return ORDER_CONFIRM

async def order_confirm_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "order_cancel":
        await query.edit_message_text("❌ Order cancelled.")
        await ctx.bot.send_message(user_id, "Main menu:", reply_markup=main_keyboard())
        ctx.user_data.clear()
        return ConversationHandler.END
    
    today_orders = await db.user_orders_today(user_id)
    if today_orders >= MAX_ORDERS_PER_DAY:
        await query.edit_message_text(f"❌ Daily order limit ({MAX_ORDERS_PER_DAY}) reached. Try tomorrow.")
        ctx.user_data.clear()
        return ConversationHandler.END
    
    service_id = ctx.user_data.get("order_service_id")
    service_name = ctx.user_data.get("order_service_name")
    category   = ctx.user_data.get("order_category", "")
    link       = ctx.user_data.get("order_link")
    qty        = ctx.user_data.get("order_quantity")
    charge     = ctx.user_data.get("order_charge")
    if not charge or charge <= 0:
        await query.edit_message_text("⚠️ Order data lost. Please start again.")
        ctx.user_data.clear()
        return ConversationHandler.END

    ok = await db.deduct_balance(user_id, charge, f"Order: {service_name}")
    if not ok:
        udata = await db.get_user(user_id)
        bal   = float(udata['balance']) if udata else 0
        need  = round(charge - bal, 2)
        await query.edit_message_text(f"❌ <b>Balance কম!</b>\n\n💵 Cost: <code>{charge:,.2f} Coins</code>\n💰 তোমার Balance: <code>{bal:,.2f} Coins</code>\n⚠️ আরও <code>{need:,.2f} Coins</code> দরকার\n\n💳 <b>Buy Coins</b> থেকে balance বাড়াও।", parse_mode=ParseMode.HTML)
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        ctx.user_data.clear()
        return ConversationHandler.END

    svc_data   = await db.get_service(service_id)
    api_source = (svc_data or {}).get("api_source", "smm1")
    chosen_api = csb_api if api_source == "smm2" else smm_api
    api_order_id = None
    api_status   = "Pending"
    api_result   = await chosen_api.add_order(service_id, link, qty)
    if "order" in api_result:
        api_order_id = str(api_result["order"])
        api_status   = "Processing"
    elif "error" in api_result:
        await db.add_balance(user_id, charge, "Refund: API error")
        error_msg = str(api_result.get("error", ""))
        if "balance" in error_msg.lower() or "insufficient" in error_msg.lower():
            await query.edit_message_text("⏳ <b>Order queued!</b>\n\nতোমার order টি process হচ্ছে।\nকিছুক্ষণ পরে আবার check করো।\n\n❓ সমস্যা হলে যোগাযোগ: @shuvo_9882", parse_mode=ParseMode.HTML)
            for admin_id in ADMIN_IDS:
                try: await ctx.bot.send_message(admin_id, f"⚠️ <b>API Balance কম!</b>\n\nUser: <code>{user_id}</code>\nService: <code>{service_name}</code>\nAPI: <code>{api_source}</code>\nQty: <code>{qty}</code>\nError: <code>{error_msg}</code>\n\n🔴 API-তে balance add করো!", parse_mode=ParseMode.HTML)
                except Exception: pass
        else:
            await query.edit_message_text("⚠️ Order টি process হচ্ছে।\nসমস্যা হলে যোগাযোগ করো: @shuvo_9882")
        ctx.user_data.clear()
        return ConversationHandler.END

    order_id = await db.create_order(user_id, service_id, service_name, category, link, qty, charge, api_order_id, api_source)
    await send_order_log(order_id=order_id, user_id=user_id, service_name=service_name, quantity=qty, link=link, status=api_status)
    svc = ctx.user_data.get("order_service", {})
    await query.edit_message_text(
        f"✅ <b>Order Placed Successfully!</b>\n" f"{'─'*28}\n"
        f"🆔 Order ID: <code>#{order_id}</code>\n" f"📦 Service: <code>{service_name}</code>\n"
        f"🔗 Link/UID: <code>{link}</code>\n" f"📊 Quantity: <code>{qty:,}</code>\n"
        f"💵 Charged: <code>{fmt_coins_full(charge)}</code>\n" f"📊 Status: <code>{api_status}</code>\n\n"
        f"Use 🔎 <b>Order Tracker</b> to check status.",
        parse_mode=ParseMode.HTML,
        reply_markup=order_actions_kb(order_id, api_order_id or "", bool(svc.get("refill")), bool(svc.get("cancel"))))
    await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
    ctx.user_data.clear()
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════
#  MY ORDERS
# ═══════════════════════════════════════════════════════════════════
async def my_orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    orders  = await db.get_user_orders(user_id, 10)
    if not orders:
        await update.message.reply_text("📦 No orders yet.\n\nUse 🛒 <b>New Order</b> to place one!", parse_mode=ParseMode.HTML)
        return
    for o in orders:
        status_icon = {"Pending": "🕐", "Processing": "⏳", "In progress": "⏳", "Completed": "✅", "Partial": "⚠️", "Cancelled": "❌"}.get(o["status"], "⏳")
        text = (
            f"📦 <b>Order #{o['id']}</b>\n" f"{'─'*24}\n"
            f"📌 {o.get('service_name', '—')[:35]}\n"
            f"📊 Status: {status_icon} <code>{o['status']}</code>\n"
            f"💰 Charge: {fmt_coins_full(o['charge'])}\n"
            f"📈 Quantity: {o['quantity']:,}\n" f"📅 {fmt_date(o['created_at'])}\n"
        )
        buttons = [[InlineKeyboardButton("🔄 Refresh", callback_data=f"orefresh:{o['id']}")]]
        if o.get("refill"):
            buttons[0].append(InlineKeyboardButton("♻️ Refill", callback_data=f"orefill:{o['id']}"))
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

async def order_refresh_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔄 Refreshing...")
    parts = query.data.split(":")
    order_id = int(parts[1])
    order = await db.get_order(order_id)
    if not order or not order.get("api_order_id"):
        await query.answer("Cannot refresh — no API order ID.", show_alert=True); return
    _src = order.get("api_source", "smm1")
    _api = csb_api if _src == "smm2" else smm_api
    result = await _api.order_status(order["api_order_id"])
    if "status" in result:
        await db.update_order_status(order_id, result["status"], int(result.get("start_count", 0)), int(result.get("remains", 0)))
        await query.edit_message_text(
            f"📦 <b>Order #{order_id} Updated</b>\n📊 Status: <code>{result['status']}</code>\n"
            f"📈 Start Count: <code>{result.get('start_count',0):,}</code>\n📉 Remains: <code>{result.get('remains',0):,}</code>",
            parse_mode=ParseMode.HTML, reply_markup=query.message.reply_markup)
    else:
        await query.answer(f"Error: {result.get('error','Unknown')}", show_alert=True)

async def order_refill_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or not order.get("api_order_id"):
        await query.answer("Cannot refill.", show_alert=True); return
    _src = order.get("api_source", "smm1")
    _api = csb_api if _src == "smm2" else smm_api
    result = await _api.refill_order(order["api_order_id"])
    if "refill" in result:
        await query.answer("✅ Refill submitted!", show_alert=True)
    else:
        await query.answer(f"Error: {result.get('error','Unknown')}", show_alert=True)

async def order_cancel_api_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or not order.get("api_order_id"):
        await query.answer("Cannot cancel.", show_alert=True); return
    _src = order.get("api_source", "smm1")
    _api = csb_api if _src == "smm2" else smm_api
    result = await _api.cancel_order(order["api_order_id"])
    if "cancel" in result or result.get("status") == "1":
        await db.update_order_status(order_id, "Cancelled")
        charge   = float(order.get("charge", 0))
        quantity = int(order.get("quantity", 1))
        remains  = int(order.get("remains", 0))
        refund = round(charge * (remains / quantity), 2) if remains > 0 and quantity > 0 else charge
        if refund > 0:
            await db.add_balance(order["user_id"], refund, f"Refund: Order #{order_id} cancelled")
            refund_text = f"\n💰 Refunded: <b>{refund:.2f} Coins</b>"
        else: refund_text = ""
        await query.edit_message_text(f"❌ <b>Order #{order_id} Cancelled</b>{refund_text}", parse_mode=ParseMode.HTML)
    else:
        await query.answer(f"Error: {result.get('error','Unknown')}", show_alert=True)

# ═══════════════════════════════════════════════════════════════════
#  ORDER TRACKER
# ═══════════════════════════════════════════════════════════════════
async def order_tracker(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 <b>Order Tracker</b>\n\nEnter your Order ID:", parse_mode=ParseMode.HTML, reply_markup=cancel_keyboard())
    return TRACKER_INPUT

async def tracker_input_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lstrip("#")
    if not text.isdigit():
        await update.message.reply_text("❌ Invalid Order ID. Enter a number:"); return TRACKER_INPUT
    order_id = int(text)
    user_id  = update.effective_user.id
    order    = await db.get_order(order_id)
    if not order or order["user_id"] != user_id:
        await update.message.reply_text("❌ Order not found or doesn't belong to you.", reply_markup=main_keyboard())
        return ConversationHandler.END
    if order.get("api_order_id"):
        _src = order.get("api_source", "smm1")
        _api = csb_api if _src == "smm2" else smm_api
        result = await _api.order_status(order["api_order_id"])
        if "status" in result:
            await db.update_order_status(order_id, result["status"], int(result.get("start_count", 0)), int(result.get("remains", 0)))
            order = await db.get_order(order_id)
    text = (
        f"🔎 <b>Order Details</b>\n" f"{'─'*28}\n"
        f"🆔 Order ID: <code>#{order['id']}</code>\n" f"📦 Service: <code>{order.get('service_name','—')}</code>\n"
        f"🔗 Link/UID: <code>{order['link']}</code>\n" f"📊 Quantity: <code>{order['quantity']:,}</code>\n"
        f"💵 Charge: <code>{fmt_coins_full(order['charge'])}</code>\n" f"📊 Status: {fmt_status(order['status'])}\n"
        f"📈 Start Count: <code>{order.get('start_count',0):,}</code>\n" f"📉 Remains: <code>{order.get('remains',0):,}</code>\n"
        f"📅 Created: <code>{fmt_date(order['created_at'])}</code>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=main_keyboard())
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════
#  REFERRAL & LEADERBOARD
# ═══════════════════════════════════════════════════════════════════
async def referral(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    udata   = await db.get_user(user_id)
    link    = referral_link(user_id)
    text = (
        f"👥 <b>Referral System</b>\n" f"{'─'*28}\n"
        f"🔗 Your Link:\n<code>{link}</code>\n\n"
        f"👥 Total Referrals: <code>{udata.get('referral_count',0)}</code>\n"
        f"💰 Earned: <code>{fmt_coins_full(udata.get('referral_earned',0))}</code>\n\n"
        f"💎 Earn <b>{REFERRAL_REWARD} coins</b> for each new user!"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏆 <b>Leaderboard</b>\n\nChoose a category:", reply_markup=leaderboard_kb(), parse_mode=ParseMode.HTML)

async def leaderboard_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    board = query.data.split(":")[1]
    if board == "referrers":
        rows = await db.top_referrers(10)
        title = "🥇 Top Referrers"
        lines = [f"{i+1}. <code>{r['full_name']}</code> — {r['referral_count']} referrals" for i, r in enumerate(rows)]
    elif board == "buyers":
        rows  = await db.top_buyers(10)
        title = "🥈 Top Buyers"
        lines = [f"{i+1}. <code>{r['full_name']}</code> — {fmt_coins_full(r['total_spent'])}" for i, r in enumerate(rows)]
    else:
        rows  = await db.top_orders(10)
        title = "🥉 Top Orders"
        lines = [f"{i+1}. <code>{r['full_name']}</code> — {r['total_orders']} orders" for i, r in enumerate(rows)]
    medals = ["🥇","🥈","🥉"] + ["🔹"]*7
    result_lines = [f"{medals[i]} {line[3:]}" for i, line in enumerate(lines)]
    text = f"🏆 <b>{title}</b>\n{'─'*28}\n" + "\n".join(result_lines)
    await query.edit_message_text(text, reply_markup=leaderboard_kb(), parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════════
#  VIP MEMBERSHIP
# ═══════════════════════════════════════════════════════════════════
async def vip_membership(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    udata   = await db.get_user(user_id)
    vip_ok  = await db.is_vip_active(udata)
    if vip_ok:
        badge = vip_badge(udata["vip_plan"])
        text  = (
            f"⭐ <b>VIP Membership</b>\n" f"{'─'*28}\n"
            f"✅ Active Plan: <code>{badge} {udata['vip_plan'].title()} VIP</code>\n"
            f"📅 Expires: <code>{fmt_date(udata.get('vip_expires',''))}</code>\n\n"
            f"🎉 Enjoy your premium benefits!"
        )
    else:
        lines = ["⭐ <b>VIP Membership</b>\n\nChoose a plan:\n"]
        for key, plan in VIP_PLANS.items():
            lines.append(f"{plan['name']}\n" f"💵 Price: <code>${plan['price']}/month</code>\n"
                         f"🏷️ Discount: <code>{plan['discount']}%</code>\n"
                         f"🎁 Bonus Coins: <code>{plan['bonus_coins']}</code>\n" f"🌟 Priority Support: ✅\n")
        text = "\n".join(lines)
    await update.message.reply_text(text, reply_markup=vip_plans_kb(), parse_mode=ParseMode.HTML)

async def vip_buy_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_key = query.data.split(":")[1]
    plan = VIP_PLANS.get(plan_key)
    if not plan:
        await query.answer("Plan not found.", show_alert=True); return
    user_id = query.from_user.id
    udata   = await db.get_user(user_id)
    cost    = plan["price"] / COIN_RATE
    ok = await db.deduct_balance(user_id, cost, f"VIP: {plan['name']}")
    if not ok:
        await query.edit_message_text(
            f"❌ Insufficient balance!\n\nRequired: <code>{fmt_coins_full(cost)}</code>\n"
            f"Your balance: <code>{fmt_coins_full(udata['balance'])}</code>\n\n💳 Use <b>Buy Coins</b> to add funds.",
            parse_mode=ParseMode.HTML)
        return
    await db.set_vip(user_id, plan_key, plan["days"])
    await db.add_balance(user_id, plan["bonus_coins"], f"VIP Bonus: {plan['name']}")
    await query.edit_message_text(
        f"🎉 <b>VIP Activated!</b>\n" f"{'─'*28}\n"
        f"✅ Plan: <code>{plan['name']}</code>\n" f"🏷️ Discount: <code>{plan['discount']}%</code>\n"
        f"🎁 Bonus Coins: <code>+{plan['bonus_coins']}</code>\n" f"📅 Valid: <code>{plan['days']} days</code>\n\n"
        f"Enjoy your premium benefits! 🚀", parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════════
#  SUPPORT TICKETS & UPDATES CHANNEL
# ═══════════════════════════════════════════════════════════════════
async def support(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("☎️ <b>Support</b>\n\nDescribe your issue and we'll help you!\n\nEnter your subject:", parse_mode=ParseMode.HTML, reply_markup=cancel_keyboard())
    return TICKET_SUBJECT

async def ticket_subject_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["ticket_subject"] = update.message.text.strip()
    await update.message.reply_text("📝 Now describe your issue in detail:", reply_markup=cancel_keyboard())
    return TICKET_MESSAGE

async def ticket_message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subject = ctx.user_data.get("ticket_subject", "No subject")
    message = update.message.text.strip()
    ticket_id = await db.create_ticket(user_id, subject, message, update.message.message_id)
    await update.message.reply_text(f"✅ <b>Ticket Submitted!</b>\n\n🆔 Ticket ID: <code>#{ticket_id}</code>\n📋 Subject: <code>{subject}</code>\n\nOur team will reply soon.", parse_mode=ParseMode.HTML, reply_markup=main_keyboard())
    udata = await db.get_user(user_id)
    admin_msg = (
        f"☎️ <b>New Support Ticket #{ticket_id}</b>\n{'─'*28}\n"
        f"👤 User: <code>{udata['full_name']}</code> (<code>@{udata.get('username','')}</code>)\n"
        f"🆔 ID: <code>{user_id}</code>\n📋 Subject: <code>{subject}</code>\n💬 Message: {message}"
    )
    from keyboards.inline import ticket_reply_kb
    for admin_id in ADMIN_IDS:
        try: await ctx.bot.send_message(admin_id, admin_msg, reply_markup=ticket_reply_kb(ticket_id, user_id), parse_mode=ParseMode.HTML)
        except Exception: pass
    ctx.user_data.clear()
    return ConversationHandler.END

async def updates_channel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    channel = await db.get_setting("updates_channel", "")
    if channel:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Updates Channel", url=channel)]])
        await update.message.reply_text(
            "📢 <b>Updates Channel</b>\n\n"
            "নিচের বাটনে ক্লিক করে আমাদের Updates Channel-এ জয়েন করো:",
            reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("📢 No updates channel set yet.")

async def back_to_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("🏠 Main Menu", reply_markup=main_keyboard())

async def cancel_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Cancelled.", reply_markup=main_keyboard())
    return ConversationHandler.END

async def check_banned(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    user_id = update.effective_user.id
    udata   = await db.get_user(user_id)
    if udata and udata.get("is_banned"):
        if update.message: await update.message.reply_text("🚫 You are banned from this bot.")
        raise ApplicationHandlerStop

async def global_force_join_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    if update.message and update.message.text and update.message.text.startswith("/start"): return
    if update.callback_query and update.callback_query.data == "fj_check": return
    if update.effective_user.id in ADMIN_IDS: return
    channels = await db.get_force_channels()
    if not channels: return
    not_joined = await check_force_join(ctx.bot, update.effective_user.id, channels)
    if not_joined:
        text = "📢 <b>প্রথমে আমাদের channel(s)-এ জয়েন করো!</b>\n\nজয়েন করার পর নিচের ✅ বাটনে ক্লিক করো।"
        if update.message:
            await update.message.reply_text(text, reply_markup=force_join_kb(not_joined), parse_mode=ParseMode.HTML)
        elif update.callback_query:
            await update.callback_query.answer("⚠️ প্রথমে channel(s)-এ জয়েন করো!", show_alert=True)
            await update.callback_query.message.reply_text(text, reply_markup=force_join_kb(not_joined), parse_mode=ParseMode.HTML)
        raise ApplicationHandlerStop