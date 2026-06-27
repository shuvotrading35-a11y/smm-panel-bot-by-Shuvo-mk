import logging
import io
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from telegram.constants import ParseMode

import database as db
from config import ADMIN_IDS, VIP_PLANS, BOT_NAME
from keyboards.reply import admin_keyboard, main_keyboard, cancel_keyboard
from keyboards.inline import (
    broadcast_type_kb, export_kb, admin_user_kb,
    deposit_approve_kb, ticket_reply_kb, vip_plans_kb
)
from utils.helpers import fmt_coins, fmt_date, broadcast_message
from api.smm_api import smm_api
from api.flashtopup_api import get_balance as ft_get_balance

logger = logging.getLogger(__name__)

# ── Conversation states ───────────────────────────────────────────
(
    BC_TYPE, BC_TEXT, BC_PHOTO, BC_VIDEO, BC_DOCUMENT,
    SEARCH_USER, ADD_BAL_ID, ADD_BAL_AMOUNT,
    REM_BAL_ID, REM_BAL_AMOUNT,
    BAN_ID, UNBAN_ID, MSG_USER_ID, MSG_USER_TEXT,
    CREATE_CODE, CREATE_CODE_AMOUNT, CREATE_CODE_USES,
    TICKET_REPLY_STATE,
    ADD_CHANNEL, REMOVE_CHANNEL,
    API_URL, API_KEY,
    NOTIFICATION_TEXT,
    SET_VIP_ID, SET_VIP_PLAN,
    ADMIN_ORDER_SEARCH,
) = range(26)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ═══════════════════════════════════════════════════════════════════
#  ADMIN PANEL ENTRY
# ═══════════════════════════════════════════════════════════════════
async def admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Access denied.")
        return
    await update.message.reply_text(
        f"👑 <b>Admin Panel</b>\n\nWelcome, Admin!",
        reply_markup=admin_keyboard(),
        parse_mode=ParseMode.HTML
    )


# ═══════════════════════════════════════════════════════════════════
#  BOT STATISTICS
# ═══════════════════════════════════════════════════════════════════
async def bot_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    total_users   = await db.get_user_count()
    total_orders  = await db.get_order_count()
    total_revenue = await db.get_total_revenue()
    total_deps    = await db.get_deposit_count()
    total_redeems = await db.get_redeem_count()
    vip_count     = await db.get_vip_count()
    orders_today  = await db.get_orders_today()

    text = (
        f"📊 <b>Bot Statistics</b>\n"
        f"{'─'*28}\n"
        f"👥 Total Users: <code>{total_users:,}</code>\n"
        f"📦 Total Orders: <code>{total_orders:,}</code>\n"
        f"📦 Orders Today: <code>{orders_today:,}</code>\n"
        f"💰 Total Revenue: <code>{fmt_coins(total_revenue)} coins</code>\n"
        f"💳 Approved Deposits: <code>{total_deps:,}</code>\n"
        f"🎁 Total Redeems: <code>{total_redeems:,}</code>\n"
        f"👑 VIP Users: <code>{vip_count:,}</code>\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ═══════════════════════════════════════════════════════════════════
#  USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════
async def user_management(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "👥 <b>User Management</b>\n\nEnter a User ID or @username to search:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard()
    )
    return SEARCH_USER


async def search_user_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip().lstrip("@")
    users = await db.search_user(query)

    if not users:
        await update.message.reply_text("❌ No user found.", reply_markup=admin_keyboard())
        return ConversationHandler.END

    for user in users[:5]:
        vip_ok  = await db.is_vip_active(user)
        vip_str = user.get("vip_plan", "None") if vip_ok else "None"
        text = (
            f"👤 <b>User Info</b>\n"
            f"{'─'*28}\n"
            f"🆔 ID: <code>{user['user_id']}</code>\n"
            f"👤 Name: <code>{user['full_name']}</code>\n"
            f"📱 Username: <code>@{user.get('username','')}</code>\n"
            f"💰 Balance: <code>{fmt_coins(user['balance'])} coins</code>\n"
            f"📦 Orders: <code>{user['total_orders']}</code>\n"
            f"💸 Total Spent: <code>{fmt_coins(user['total_spent'])} coins</code>\n"
            f"👥 Referrals: <code>{user['referral_count']}</code>\n"
            f"⭐ VIP: <code>{vip_str}</code>\n"
            f"🚫 Banned: <code>{'Yes' if user['is_banned'] else 'No'}</code>\n"
            f"📅 Joined: <code>{fmt_date(user['join_date'])}</code>"
        )
        await update.message.reply_text(
            text, reply_markup=admin_user_kb(user["user_id"]),
            parse_mode=ParseMode.HTML
        )

    await update.message.reply_text("Done.", reply_markup=admin_keyboard())
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════
#  BALANCE MANAGER
# ═══════════════════════════════════════════════════════════════════
async def balance_manager(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "💰 <b>Balance Manager</b>\n\nEnter User ID to add balance:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard()
    )
    return ADD_BAL_ID


async def add_bal_id_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()
    if not uid.isdigit():
        await update.message.reply_text("❌ Invalid User ID:")
        return ADD_BAL_ID
    ctx.user_data["adm_target_id"] = int(uid)
    await update.message.reply_text("Enter amount to add:")
    return ADD_BAL_AMOUNT


async def add_bal_amount_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.replace(".", "", 1).isdigit():
        await update.message.reply_text("❌ Invalid amount:")
        return ADD_BAL_AMOUNT
    amount  = float(text)
    uid     = ctx.user_data["adm_target_id"]
    await db.add_balance(uid, amount, "Admin Add")
    udata = await db.get_user(uid)
    await update.message.reply_text(
        f"✅ Added <code>{fmt_coins(amount)} coins</code> to user <code>{uid}</code>.\n"
        f"New balance: <code>{fmt_coins(udata['balance']) if udata else '?'} coins</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard()
    )
    # Notify user
    try:
        await ctx.bot.send_message(uid, f"💰 Admin added <b>{fmt_coins(amount)} coins</b> to your balance!", parse_mode=ParseMode.HTML)
    except Exception:
        pass
    ctx.user_data.clear()
    return ConversationHandler.END


# Admin inline callbacks for user actions
async def admin_user_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    parts  = query.data.split(":")
    action = parts[0]
    uid    = int(parts[1])

    if action == "adm_ban":
        await db.ban_user(uid)
        await query.edit_message_reply_markup(reply_markup=admin_user_kb(uid))
        await query.answer(f"🚫 User {uid} banned.", show_alert=True)
        try:
            await ctx.bot.send_message(uid, "🚫 You have been banned from this bot.")
        except Exception:
            pass

    elif action == "adm_unban":
        await db.unban_user(uid)
        await query.answer(f"✅ User {uid} unbanned.", show_alert=True)
        try:
            await ctx.bot.send_message(uid, "✅ Your ban has been lifted. You can use the bot again.")
        except Exception:
            pass

    elif action == "adm_bal_add":
        ctx.user_data["adm_target_id"] = uid
        ctx.user_data["adm_action"]    = "add"
        await query.edit_message_text(
            f"➕ Add balance to user <code>{uid}</code>\n\nEnter amount:",
            parse_mode=ParseMode.HTML
        )

    elif action == "adm_bal_rem":
        ctx.user_data["adm_target_id"] = uid
        ctx.user_data["adm_action"]    = "remove"
        await query.edit_message_text(
            f"➖ Remove balance from user <code>{uid}</code>\n\nEnter amount:",
            parse_mode=ParseMode.HTML
        )

    elif action == "adm_msg":
        ctx.user_data["msg_target"] = uid
        await query.edit_message_text(
            f"📩 Send message to user <code>{uid}</code>\n\nType your message:",
            parse_mode=ParseMode.HTML
        )


# ═══════════════════════════════════════════════════════════════════
#  CODE MANAGER
# ═══════════════════════════════════════════════════════════════════
async def code_manager(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    codes = await db.get_all_codes()
    if codes:
        lines = ["🎁 <b>Redeem Codes</b>\n"]
        for c in codes:
            status = "✅" if c["is_active"] else "❌"
            lines.append(
                f"{status} <code>{c['code']}</code> — {fmt_coins(c['amount'])} coins "
                f"({c['used_count']}/{c['max_uses']} uses)"
            )
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    await update.message.reply_text(
        "Enter new code name (or /skip to skip):",
        reply_markup=cancel_keyboard()
    )
    return CREATE_CODE


async def create_code_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/skip":
        await update.message.reply_text("Skipped.", reply_markup=admin_keyboard())
        return ConversationHandler.END
    ctx.user_data["new_code"] = text.upper()
    await update.message.reply_text("Enter reward amount (coins):")
    return CREATE_CODE_AMOUNT


async def create_code_amount_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.replace(".", "", 1).isdigit():
        await update.message.reply_text("❌ Invalid amount:")
        return CREATE_CODE_AMOUNT
    ctx.user_data["new_code_amount"] = float(text)
    await update.message.reply_text("Enter max uses (default 1):")
    return CREATE_CODE_USES


async def create_code_uses_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uses = int(text) if text.isdigit() else 1
    code   = ctx.user_data["new_code"]
    amount = ctx.user_data["new_code_amount"]
    await db.create_redeem_code(code, amount, uses)
    await update.message.reply_text(
        f"✅ Code <code>{code}</code> created!\n"
        f"💰 Amount: <code>{fmt_coins(amount)} coins</code>\n"
        f"🔢 Max Uses: <code>{uses}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard()
    )
    ctx.user_data.clear()
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════
#  BROADCAST
# ═══════════════════════════════════════════════════════════════════
async def broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "📢 <b>Broadcast</b>\n\nChoose message type:",
        reply_markup=broadcast_type_kb(),
        parse_mode=ParseMode.HTML
    )
    return BC_TYPE


async def broadcast_type_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bc_type = query.data.split(":")[1]

    if bc_type == "cancel":
        await query.edit_message_text("❌ Broadcast cancelled.")
        return ConversationHandler.END

    ctx.user_data["bc_type"] = bc_type
    await query.edit_message_text(
        f"📝 Send your {bc_type} message now:"
    )
    return BC_TEXT


async def broadcast_content_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    bc_type = ctx.user_data.get("bc_type", "text")
    msg     = update.message
    users   = await db.get_all_users()
    ids     = [u["user_id"] for u in users if not u["is_banned"]]

    await update.message.reply_text(f"📢 Broadcasting to {len(ids)} users...")

    if bc_type == "text":
        sent, failed = await broadcast_message(ctx.bot, ids, text=msg.text)
    elif bc_type == "photo" and msg.photo:
        sent, failed = await broadcast_message(ctx.bot, ids,
                                                photo_id=msg.photo[-1].file_id,
                                                caption=msg.caption)
    elif bc_type == "video" and msg.video:
        sent, failed = await broadcast_message(ctx.bot, ids,
                                                video_id=msg.video.file_id,
                                                caption=msg.caption)
    elif bc_type == "document" and msg.document:
        sent, failed = await broadcast_message(ctx.bot, ids,
                                                doc_id=msg.document.file_id,
                                                caption=msg.caption)
    else:
        sent, failed = 0, 0

    await update.message.reply_text(
        f"📢 <b>Broadcast Complete!</b>\n\n"
        f"✅ Sent: <code>{sent}</code>\n"
        f"❌ Failed: <code>{failed}</code>\n"
        f"📊 Total: <code>{len(ids)}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard()
    )
    ctx.user_data.clear()
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════
#  ORDER MANAGER
# ═══════════════════════════════════════════════════════════════════
async def order_manager(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    orders = await db.get_all_orders(20)
    lines  = ["📦 <b>Recent Orders</b> (Last 20)\n"]
    for o in orders:
        lines.append(
            f"#{o['id']} | {o.get('username','?')} | "
            f"{o.get('service_name','?')[:20]} | "
            f"{o['status']} | {fmt_coins(o['charge'])}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    await update.message.reply_text(
        "Enter Order ID to check / manage (or /skip):",
        reply_markup=cancel_keyboard()
    )
    return ADMIN_ORDER_SEARCH


async def admin_order_search_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lstrip("#")
    if text.lower() == "/skip":
        await update.message.reply_text("OK.", reply_markup=admin_keyboard())
        return ConversationHandler.END

    if not text.isdigit():
        await update.message.reply_text("❌ Invalid order ID.", reply_markup=admin_keyboard())
        return ConversationHandler.END

    order = await db.get_order(int(text))
    if not order:
        await update.message.reply_text("❌ Order not found.", reply_markup=admin_keyboard())
        return ConversationHandler.END

    reply = (
        f"📦 <b>Order #{order['id']}</b>\n"
        f"{'─'*28}\n"
        f"👤 User: <code>{order['user_id']}</code>\n"
        f"📦 Service: <code>{order.get('service_name','?')}</code>\n"
        f"🔗 Link: <code>{order['link']}</code>\n"
        f"📊 Qty: <code>{order['quantity']:,}</code>\n"
        f"💵 Charge: <code>{fmt_coins(order['charge'])} coins</code>\n"
        f"📊 Status: <code>{order['status']}</code>\n"
        f"🆔 API ID: <code>{order.get('api_order_id','N/A')}</code>\n"
        f"📅 Date: <code>{fmt_date(order['created_at'])}</code>"
    )
    from keyboards.inline import order_actions_kb
    await update.message.reply_text(
        reply, parse_mode=ParseMode.HTML,
        reply_markup=order_actions_kb(order["id"], order.get("api_order_id",""), True, True)
    )
    await update.message.reply_text("Done.", reply_markup=admin_keyboard())
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════
#  API MANAGER
# ═══════════════════════════════════════════════════════════════════
async def api_manager(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    # SMM Panel API status
    ok, msg = await smm_api.test_connection()
    smm_status = "✅ Connected" if ok else "❌ Not Connected"

    # FlashTopup API balance
    ft_result  = await ft_get_balance()
    ft_data    = ft_result.get("data") or {}
    if ft_result.get("success") and ft_data:
        ft_balance = ft_data.get("balance", "N/A")
        ft_currency = ft_data.get("currency", "")
        ft_status  = f"✅ {ft_balance} {ft_currency}"
    else:
        err = (ft_result.get("error") or {})
        ft_status = f"❌ {err.get('message', 'Error')}"

    text = (
        f"⚙️ <b>API Manager</b>\n"
        f"{'─'*28}\n"
        f"📊 <b>SMM Panel API</b>\n"
        f"Status: {smm_status}\n"
        f"Info: <code>{msg}</code>\n\n"
        f"✈️ <b>FlashTopup API</b>\n"
        f"Balance: {ft_status}\n\n"
        f"Use /syncservices to sync all services.\n"
        f"Use /testapi to test connection."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def sync_services(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("🔄 Syncing services from API...")
    services = await smm_api.get_services()
    if not services:
        await update.message.reply_text("❌ No services received. Check API config.")
        return
    await db.upsert_services(services)
    cats = await db.get_categories()
    await update.message.reply_text(
        f"✅ <b>Synced {len(services)} services!</b>\n"
        f"📂 Categories: <code>{len(cats)}</code>",
        parse_mode=ParseMode.HTML
    )


async def test_api(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    ok, msg = await smm_api.test_connection()
    await update.message.reply_text(
        f"{'✅' if ok else '❌'} API Test: <code>{msg}</code>",
        parse_mode=ParseMode.HTML
    )


# ═══════════════════════════════════════════════════════════════════
#  SERVICE SEARCH BY ID
# ═══════════════════════════════════════════════════════════════════
async def service_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Search service by ID — available to all users."""
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "🔍 <b>Service Search</b>\n\n"
            "Service ID দিয়ে খুঁজো:\n"
            "/search 6370",
            parse_mode=ParseMode.HTML
        )
        return

    service_id = args[0].strip()
    svc = await db.get_service(service_id)

    if not svc:
        await update.message.reply_text(
            f"❌ Service ID <code>{service_id}</code> পাওয়া যায়নি।",
            parse_mode=ParseMode.HTML
        )
        return

    USD_TO_BDT  = 135
    from config import SERVICE_MARKUP_PCT
    rate_usd    = float(svc.get("rate", 0))
    rate_bdt    = round(rate_usd * (1 + SERVICE_MARKUP_PCT/100) * USD_TO_BDT, 2)
    is_admin_   = is_admin(update.effective_user.id)
    refill      = "✅" if svc.get("refill") else "❌"
    cancel_s    = "✅" if svc.get("cancel") else "❌"

    # Admin দেখবে API rate, user দেখবে শুধু তাদের rate
    rate_line = (
        f"💵 API Rate: <code>${rate_usd} per 1000</code>\n"
        f"💰 তোমার Rate: <code>৳{rate_bdt} per 1000</code>\n"
        if is_admin_ else
        f"💰 Rate: <code>৳{rate_bdt} per 1000</code>\n"
    )

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    order_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🛒 Order Now", callback_data=f"order_start:{svc['service_id']}")
    ]])

    await update.message.reply_text(
        f"🔍 <b>Service Found</b>\n"
        f"{'─'*28}\n"
        f"🆔 ID: <code>{svc['service_id']}</code>\n"
        f"📦 Name: <code>{svc['name']}</code>\n"
        f"📂 Category: <code>{svc['category']}</code>\n"
        f"{rate_line}"
        f"📊 Min: <code>{svc['min_order']}</code> | Max: <code>{svc['max_order']}</code>\n"
        f"🔄 Refill: {refill} | Cancel: {cancel_s}",
        reply_markup=order_kb,
        parse_mode=ParseMode.HTML
    )


# ═══════════════════════════════════════════════════════════════════
#  FORCE JOIN ADMIN
# ═══════════════════════════════════════════════════════════════════
async def force_join_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    channels = await db.get_force_channels()
    lines    = ["📣 <b>Force Join Channels</b>\n"]
    if channels:
        for ch in channels:
            link = ch.get("invite_link") or "<i>(no link set!)</i>"
            lines.append(
                f"• ID: <code>{ch['channel_id']}</code>\n"
                f"  Name: <code>{ch.get('channel_name','')}</code>\n"
                f"  Link: <code>{link}</code>\n"
            )
    else:
        lines.append("<i>No channels set.</i>")
    lines.append("\n/addchannel @channel link [name] — Add\n/removechannel @channel — Remove")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def add_channel_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /addchannel @channel invite_link [name]")
        return
    ch_id = args[0]
    link  = args[1] if len(args) > 1 else ""
    name  = args[2] if len(args) > 2 else ""

    # name না দিলে bot দিয়ে channel title fetch করো
    if not name:
        try:
            chat = await ctx.bot.get_chat(ch_id)
            name = chat.title or ch_id
        except Exception:
            name = ch_id

    await db.add_force_channel(ch_id, name, link)
    await update.message.reply_text(
        f"✅ Channel <code>{ch_id}</code> added.\n"
        f"📛 Name: <b>{name}</b>",
        parse_mode=ParseMode.HTML
    )


async def topup_debug(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin: /topupdebug — show full FlashTopup products API response"""
    if not is_admin(update.effective_user.id):
        return
    from api.flashtopup_api import get_products, get_services
    await update.message.reply_text("⏳ Fetching products...")

    # Get products list
    prod_result = await get_products()
    prod_data   = prod_result.get("data") or []
    if isinstance(prod_data, list):
        ff_products = [p for p in prod_data if "free" in str(p).lower() or "fire" in str(p).lower() or "FF" in str(p)]
    else:
        ff_products = []

    await update.message.reply_text(
        f"📋 FF Products found: {len(ff_products)}\n"
        f"<code>{str(ff_products[:2])[:600]}</code>",
        parse_mode=ParseMode.HTML
    )

    # Test check_player_id directly
    from api.flashtopup_api import check_player_id
    await update.message.reply_text("⏳ Testing check-id with UID 2296094466...")
    result = await check_player_id("2296094466", "", "freefire_bd")
    await update.message.reply_text(
        f"🔍 check_player_id response:\n<code>{str(result)[:800]}</code>",
        parse_mode=ParseMode.HTML
    )


async def set_updates_channel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin command: /setupdates https://t.me/modapk_allappps"""
    if not is_admin(update.effective_user.id):
        return
    args = ctx.args
    if not args:
        current = await db.get_setting("updates_channel", "")
        await update.message.reply_text(
            f"📢 <b>Updates Channel</b>\n\n"
            f"বর্তমান: <code>{current or 'সেট করা নেই'}</code>\n\n"
            f"Usage: /setupdates https://t.me/your_channel",
            parse_mode=ParseMode.HTML
        )
        return
    link = args[0].strip()
    await db.set_setting("updates_channel", link)
    await update.message.reply_text(
        f"✅ Updates Channel সেট হয়েছে:\n<code>{link}</code>",
        parse_mode=ParseMode.HTML
    )


async def remove_channel_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /removechannel @channel")
        return
    await db.remove_force_channel(args[0])
    await update.message.reply_text(f"✅ Channel <code>{args[0]}</code> removed.", parse_mode=ParseMode.HTML)


async def list_channels_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await force_join_admin(update, ctx)


# ═══════════════════════════════════════════════════════════════════
#  BAN SYSTEM
# ═══════════════════════════════════════════════════════════════════
async def ban_system(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "🚫 <b>Ban System</b>\n\nEnter User ID to ban:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard()
    )
    return BAN_ID


async def ban_id_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ Invalid ID.", reply_markup=admin_keyboard())
        return ConversationHandler.END
    uid = int(text)
    await db.ban_user(uid, "Banned by admin")
    await update.message.reply_text(f"🚫 User <code>{uid}</code> banned.", parse_mode=ParseMode.HTML, reply_markup=admin_keyboard())
    try:
        await ctx.bot.send_message(uid, "🚫 You have been banned from this bot.")
    except Exception:
        pass
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════
#  SUPPORT MANAGER
# ═══════════════════════════════════════════════════════════════════
async def support_manager(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    tickets = await db.get_open_tickets()
    if not tickets:
        await update.message.reply_text("☎️ No open tickets.", reply_markup=admin_keyboard())
        return
    for t in tickets[:5]:
        text = (
            f"☎️ <b>Ticket #{t['id']}</b>\n"
            f"👤 User: <code>{t['full_name']}</code> (<code>{t['user_id']}</code>)\n"
            f"📋 Subject: <code>{t['subject']}</code>\n"
            f"💬 Message: {t['message']}\n"
            f"📅 {fmt_date(t['created_at'])}"
        )
        await update.message.reply_text(
            text, reply_markup=ticket_reply_kb(t["id"], t["user_id"]),
            parse_mode=ParseMode.HTML
        )


async def ticket_reply_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    parts     = query.data.split(":")
    ticket_id = int(parts[1])
    user_id   = int(parts[2])

    ctx.user_data["reply_ticket_id"] = ticket_id
    ctx.user_data["reply_user_id"]   = user_id
    await query.edit_message_text(
        f"💬 Reply to ticket #{ticket_id}:\n\nType your reply:"
    )
    return TICKET_REPLY_STATE


async def ticket_reply_text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    reply     = update.message.text.strip()
    ticket_id = ctx.user_data.get("reply_ticket_id")
    user_id   = ctx.user_data.get("reply_user_id")

    if not ticket_id or not user_id:
        await update.message.reply_text("Error: missing ticket data.", reply_markup=admin_keyboard())
        return ConversationHandler.END

    await db.close_ticket(ticket_id, reply)
    try:
        await ctx.bot.send_message(
            user_id,
            f"☎️ <b>Support Reply — Ticket #{ticket_id}</b>\n\n{reply}",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

    await update.message.reply_text(
        f"✅ Reply sent & ticket #{ticket_id} closed.",
        reply_markup=admin_keyboard()
    )
    ctx.user_data.clear()
    return ConversationHandler.END


async def ticket_close_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    ticket_id = int(query.data.split(":")[1])
    await db.close_ticket(ticket_id)
    await query.edit_message_text(f"✅ Ticket #{ticket_id} closed.")


# ═══════════════════════════════════════════════════════════════════
#  DEPOSIT CALLBACKS
# ═══════════════════════════════════════════════════════════════════
async def deposit_approve_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    dep_id = int(query.data.split(":")[1])
    dep    = await db.approve_deposit(dep_id)
    if not dep:
        await query.answer("Already processed.", show_alert=True)
        return
    await query.edit_message_text(
        f"✅ Deposit #{dep_id} approved!\n"
        f"User {dep['user_id']} received {fmt_coins(dep['amount'])} coins."
    )
    try:
        await ctx.bot.send_message(
            dep["user_id"],
            f"✅ <b>Deposit Approved!</b>\n\n"
            f"💰 +<code>{fmt_coins(dep['amount'])} coins</code> added to your balance!",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass


async def deposit_reject_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    dep_id = int(query.data.split(":")[1])
    dep    = await db.reject_deposit(dep_id)
    if not dep:
        await query.answer("Already processed.", show_alert=True)
        return
    await query.edit_message_text(f"❌ Deposit #{dep_id} rejected.")
    try:
        await ctx.bot.send_message(
            dep["user_id"],
            f"❌ <b>Deposit Rejected</b>\n\n"
            f"Deposit #{dep_id} was rejected by admin.\n"
            f"Contact support if you believe this is an error.",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
#  VIP MANAGER
# ═══════════════════════════════════════════════════════════════════
async def vip_manager(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "💎 <b>VIP Manager</b>\n\nEnter User ID to assign VIP:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard()
    )
    return SET_VIP_ID


async def set_vip_id_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ Invalid ID.", reply_markup=admin_keyboard())
        return ConversationHandler.END
    ctx.user_data["vip_target"] = int(text)
    lines = ["Choose a VIP plan:\n"]
    for key, plan in VIP_PLANS.items():
        lines.append(f"Type <code>{key}</code> for {plan['name']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    return SET_VIP_PLAN


async def set_vip_plan_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    plan_key = update.message.text.strip().lower()
    if plan_key not in VIP_PLANS:
        await update.message.reply_text(f"❌ Invalid plan. Options: {', '.join(VIP_PLANS.keys())}")
        return SET_VIP_PLAN
    uid  = ctx.user_data["vip_target"]
    plan = VIP_PLANS[plan_key]
    await db.set_vip(uid, plan_key, plan["days"])
    await update.message.reply_text(
        f"✅ VIP <code>{plan['name']}</code> assigned to user <code>{uid}</code>!",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard()
    )
    try:
        await ctx.bot.send_message(
            uid,
            f"🎉 <b>{plan['name']} Activated!</b>\n\nAdmin granted you VIP membership!",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass
    ctx.user_data.clear()
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════
#  NOTIFICATION
# ═══════════════════════════════════════════════════════════════════
async def notification(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "🔔 <b>Send Notification</b>\n\nEnter message to broadcast to all users:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard()
    )
    return NOTIFICATION_TEXT


async def notification_text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text  = update.message.text.strip()
    users = await db.get_all_users()
    ids   = [u["user_id"] for u in users if not u["is_banned"]]
    sent, failed = await broadcast_message(ctx.bot, ids, text=f"🔔 <b>Notification</b>\n\n{text}")
    await update.message.reply_text(
        f"🔔 Notification sent!\n✅ {sent} | ❌ {failed}",
        reply_markup=admin_keyboard()
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════
#  EXPORT DATA
# ═══════════════════════════════════════════════════════════════════
async def export_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "📤 <b>Export Data</b>\n\nChoose what to export:",
        reply_markup=export_kb(),
        parse_mode=ParseMode.HTML
    )


async def export_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    export_type = query.data.split(":")[1]
    await query.edit_message_text("⏳ Generating export...")

    if export_type == "users":
        csv_data = await db.export_users_csv()
        fname    = "users_export.csv"
    else:
        csv_data = await db.export_orders_csv()
        fname    = "orders_export.csv"

    file = io.BytesIO(csv_data.encode())
    file.name = fname
    await ctx.bot.send_document(query.from_user.id, file, caption=f"📄 {fname}")


# ═══════════════════════════════════════════════════════════════════
#  DATABASE MANAGER
# ═══════════════════════════════════════════════════════════════════
async def database_manager(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    users  = await db.get_user_count()
    orders = await db.get_order_count()
    text = (
        f"🗄 <b>Database Manager</b>\n"
        f"{'─'*28}\n"
        f"👥 Users: <code>{users}</code>\n"
        f"📦 Orders: <code>{orders}</code>\n\n"
        f"Use /syncservices to sync API services.\n"
        f"Use /export to export data."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ═══════════════════════════════════════════════════════════════════
#  RESTART BOT
# ═══════════════════════════════════════════════════════════════════
async def restart_bot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("🔄 Restarting bot...")
    import os, sys
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ═══════════════════════════════════════════════════════════════════
#  ADMIN LEADERBOARD
# ═══════════════════════════════════════════════════════════════════
async def admin_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    from keyboards.inline import leaderboard_kb
    await update.message.reply_text(
        "🏆 <b>Leaderboard</b>",
        reply_markup=leaderboard_kb(),
        parse_mode=ParseMode.HTML
    )


# ═══════════════════════════════════════════════════════════════════
#  CANCEL
# ═══════════════════════════════════════════════════════════════════
async def cancel_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Cancelled.", reply_markup=admin_keyboard())
    return ConversationHandler.END