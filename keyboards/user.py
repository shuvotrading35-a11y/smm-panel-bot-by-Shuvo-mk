import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from telegram.constants import ParseMode

import database as db
from config import (ADMIN_IDS, BOT_NAME, DEVELOPER, DAILY_BONUS_AMOUNT,
                    REFERRAL_REWARD, VIP_PLANS, COIN_RATE, BOT_USERNAME)
from keyboards.reply import main_keyboard, cancel_keyboard, back_keyboard
from keyboards.inline import (
    leaderboard_kb, wallet_kb, account_kb, vip_plans_kb,
    categories_kb, services_kb, service_detail_kb, force_join_kb,
    payment_methods_kb, confirm_order_kb, order_actions_kb
)
from utils.helpers import (
    fmt_coins, fmt_status, fmt_date, referral_link,
    vip_badge, is_rate_limited, check_force_join, category_icon
)
from utils.order_logger import send_order_log
from api.smm_api import smm_api
from config import CATEGORY_ICONS, MAX_ORDERS_PER_DAY

logger = logging.getLogger(__name__)

# ── Conversation states ───────────────────────────────────────────
(
    ORDER_CATEGORY, ORDER_SERVICE, ORDER_LINK, ORDER_QUANTITY,
    ORDER_CONFIRM, REDEEM_INPUT, TICKET_SUBJECT, TICKET_MESSAGE,
    DEPOSIT_METHOD, DEPOSIT_AMOUNT, DEPOSIT_TXN, TRACKER_INPUT,
) = range(12)


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
        if ref_id and ref_id != user.id:
            await db.process_referral(user.id, ref_id, REFERRAL_REWARD)

    # Force-join check
    channels = await db.get_force_channels()
    if channels:
        bot       = ctx.bot
        not_joined = await check_force_join(bot, user.id, channels)
        if not_joined:
            await update.message.reply_text(
                "📢 *Please join our channels to use this bot:*",
                reply_markup=force_join_kb(not_joined),
                parse_mode=ParseMode.MARKDOWN
            )
            return

    udata = await db.get_user(user.id)
    if udata and udata["is_banned"]:
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return

    text = (
        f"🚀 *Welcome To {BOT_NAME}*\n\n"
        "💎 *Cheapest Prices*\n"
        "⚡ *Instant Delivery*\n"
        "🔒 *Secure Payments*\n"
        "📈 *High Quality Services*\n\n"
        "Choose an option below to continue.\n\n"
        f"👨‍💻 Developer: {DEVELOPER}\n"
        f"🤖 Powered By Shuvo SMM"
    )
    await update.message.reply_text(
        text,
        reply_markup=main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )


# ═══════════════════════════════════════════════════════════════════
#  FORCE JOIN CALLBACK CHECK
# ═══════════════════════════════════════════════════════════════════
async def force_join_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    user     = query.from_user
    channels = await db.get_force_channels()
    not_joined = await check_force_join(ctx.bot, user.id, channels)
    if not_joined:
        await query.edit_message_text(
            "❌ You haven't joined all channels yet!\n\n"
            "📢 Please join all required channels and try again.",
            reply_markup=force_join_kb(not_joined)
        )
    else:
        await query.edit_message_text("✅ Verified! You can now use the bot.")
        await ctx.bot.send_message(user.id, f"🚀 Welcome to {BOT_NAME}!", reply_markup=main_keyboard())


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
        f"👤 *My Account*\n"
        f"{'─'*28}\n"
        f"👤 Name: `{udata['full_name']}`\n"
        f"🆔 User ID: `{user_id}`\n"
        f"💰 Balance: `{fmt_coins(udata['balance'])} coins`\n"
        f"📦 Total Orders: `{udata['total_orders']}`\n"
        f"💸 Total Spent: `{fmt_coins(udata['total_spent'])} coins`\n"
        f"💳 Total Deposited: `{fmt_coins(udata['total_deposited'])} coins`\n"
        f"👥 Referrals: `{udata['referral_count']}`\n"
        f"💎 Referral Earned: `{fmt_coins(udata['referral_earned'])} coins`\n"
        f"🏆 Rank: `#{rank}`\n"
        f"⭐ VIP: `{vip_str}`\n"
        f"📅 Joined: `{fmt_date(udata['join_date'])}`\n"
    )
    await update.message.reply_text(text, reply_markup=account_kb(), parse_mode=ParseMode.MARKDOWN)


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
            f"👤 *My Account*\n"
            f"{'─'*28}\n"
            f"👤 Name: `{udata['full_name']}`\n"
            f"🆔 User ID: `{user_id}`\n"
            f"💰 Balance: `{fmt_coins(udata['balance'])} coins`\n"
            f"📦 Total Orders: `{udata['total_orders']}`\n"
            f"💸 Total Spent: `{fmt_coins(udata['total_spent'])} coins`\n"
            f"👥 Referrals: `{udata['referral_count']}`\n"
            f"🏆 Rank: `#{rank}`\n"
            f"⭐ VIP: `{vip_str}`\n"
        )
        await query.edit_message_text(text, reply_markup=account_kb(), parse_mode=ParseMode.MARKDOWN)

    elif action == "acc_deposits":
        deps  = await db.get_user_deposits(user_id)
        if not deps:
            await query.answer("No deposits yet.", show_alert=True)
            return
        lines = ["💳 *Deposit History*\n"]
        for d in deps:
            lines.append(
                f"#{d['id']} | {d['method']} | {fmt_coins(d['amount'])} coins | "
                f"{d['status']} | {fmt_date(d['created_at'])}"
            )
        await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    elif action == "acc_transactions":
        txns = await db.get_transactions(user_id)
        if not txns:
            await query.answer("No transactions yet.", show_alert=True)
            return
        lines = ["📤 *Transaction History*\n"]
        for t in txns:
            sign = "+" if t["type"] in ("credit", "deposit", "redeem", "daily", "referral") else "-"
            lines.append(
                f"{sign}{fmt_coins(t['amount'])} | {t['type'].title()} | "
                f"{t.get('description','')} | {fmt_date(t['created_at'])}"
            )
        await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════
#  WALLET
# ═══════════════════════════════════════════════════════════════════
async def wallet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    udata   = await db.get_user(user_id)
    if not udata:
        await update.message.reply_text("⚠️ Use /start first.")
        return
    txns = await db.get_transactions(user_id, limit=50)
    total_in  = sum(t["amount"] for t in txns if t["type"] in ("credit","deposit","redeem","daily","referral"))
    total_out = sum(t["amount"] for t in txns if t["type"] in ("debit","order"))
    text = (
        f"💰 *My Wallet*\n"
        f"{'─'*28}\n"
        f"💰 Balance: `{fmt_coins(udata['balance'])} coins`\n"
        f"📈 Total Deposits: `{fmt_coins(udata['total_deposited'])} coins`\n"
        f"📉 Total Spent: `{fmt_coins(udata['total_spent'])} coins`\n"
    )
    await update.message.reply_text(text, reply_markup=wallet_kb(), parse_mode=ParseMode.MARKDOWN)


async def wallet_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "wallet_add":
        await query.edit_message_text(
            "💳 *Add Funds*\n\nChoose a payment method:",
            reply_markup=payment_methods_kb(),
            parse_mode=ParseMode.MARKDOWN
        )
    elif query.data == "wallet_history":
        user_id = query.from_user.id
        txns    = await db.get_transactions(user_id, 10)
        if not txns:
            await query.answer("No transactions yet.", show_alert=True)
            return
        lines = ["📜 *Transaction History*\n"]
        for t in txns:
            sign = "+" if t["type"] in ("credit","deposit","redeem","daily","referral") else "-"
            lines.append(f"{sign}{fmt_coins(t['amount'])} | {t['type'].title()} | {fmt_date(t['created_at'])}")
        await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════
#  BUY COINS / DEPOSIT
# ═══════════════════════════════════════════════════════════════════
async def buy_coins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💳 *Buy Coins*\n\nChoose a payment method:",
        reply_markup=payment_methods_kb(),
        parse_mode=ParseMode.MARKDOWN
    )


async def payment_method_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    method = query.data.split(":")[1]

    from config import PAYMENT_METHODS
    method_name = PAYMENT_METHODS.get(method, method)

    payment_info = {
        "binance":  "💵 *Binance Pay ID:* `your_binance_id`\n*Min:* $1",
        "usdt_trc": "🟢 *USDT TRC20 Address:*\n`TYourWalletAddressHere`\n*Min:* $1",
        "usdt_bep": "🟡 *USDT BEP20 Address:*\n`0xYourWalletAddressHere`\n*Min:* $1",
        "stripe":   "💳 *Stripe Payment Link:*\nhttps://buy.stripe.com/your_link\n*Min:* $1",
        "bank":     "🏦 *Bank Details:*\nBank: Your Bank\nAccount: 1234567890\nRouting: 021000021\n*Min:* $5",
        "mobile":   "📱 *Mobile Banking:*\nbKash: 01XXXXXXXXX\nNagad: 01XXXXXXXXX\n*Min:* ৳50",
    }

    info = payment_info.get(method, "Contact admin for payment details.")
    ctx.user_data["deposit_method"] = method

    await query.edit_message_text(
        f"💳 *{method_name}*\n\n{info}\n\n"
        f"After payment, send the amount and transaction ID to get verified.\n\n"
        f"👇 Reply with your deposit amount (numbers only):",
        parse_mode=ParseMode.MARKDOWN
    )
    return DEPOSIT_AMOUNT


async def deposit_amount_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.replace(".", "", 1).isdigit():
        await update.message.reply_text("❌ Invalid amount. Enter numbers only (e.g. 10 or 5.50):")
        return DEPOSIT_AMOUNT

    amount = float(text)
    from config import MIN_DEPOSIT
    if amount < MIN_DEPOSIT:
        await update.message.reply_text(f"❌ Minimum deposit is {MIN_DEPOSIT} coins.")
        return DEPOSIT_AMOUNT

    ctx.user_data["deposit_amount"] = amount
    await update.message.reply_text(
        f"✅ Amount: *{fmt_coins(amount)} coins*\n\n"
        f"📝 Now send your *Transaction ID / Reference Number*:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=cancel_keyboard()
    )
    return DEPOSIT_TXN


async def deposit_txn_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txn_id  = update.message.text.strip()
    user_id = update.effective_user.id
    method  = ctx.user_data.get("deposit_method", "unknown")
    amount  = ctx.user_data.get("deposit_amount", 0)

    dep_id = await db.create_deposit(user_id, amount, method, txn_id)

    await update.message.reply_text(
        f"✅ *Deposit Request Submitted!*\n\n"
        f"🆔 Request ID: `#{dep_id}`\n"
        f"💰 Amount: `{fmt_coins(amount)} coins`\n"
        f"💳 Method: `{method}`\n"
        f"📋 TXN ID: `{txn_id}`\n\n"
        f"⏳ Admin will verify and approve within 24h.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )

    # Notify admins
    udata = await db.get_user(user_id)
    admin_msg = (
        f"💳 *New Deposit Request*\n"
        f"{'─'*28}\n"
        f"👤 User: `{udata['full_name']}` (`@{udata.get('username','')}`)\n"
        f"🆔 User ID: `{user_id}`\n"
        f"💰 Amount: `{fmt_coins(amount)} coins`\n"
        f"💳 Method: `{method}`\n"
        f"📋 TXN ID: `{txn_id}`\n"
        f"🆔 Request ID: `#{dep_id}`"
    )
    from keyboards.inline import deposit_approve_kb
    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_message(admin_id, admin_msg,
                                       reply_markup=deposit_approve_kb(dep_id),
                                       parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass

    ctx.user_data.clear()
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════
#  SERVICES LIST
# ═══════════════════════════════════════════════════════════════════
async def services_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cats = await db.get_categories()
    if not cats:
        await update.message.reply_text(
            "⚠️ No services synced yet.\n"
            "Admin needs to sync services from the API panel."
        )
        return
    await update.message.reply_text(
        "📊 *Services List*\n\nChoose a category:",
        reply_markup=categories_kb(cats, CATEGORY_ICONS),
        parse_mode=ParseMode.MARKDOWN
    )


async def category_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    data     = query.data

    if data == "cat_back":
        cats = await db.get_categories()
        await query.edit_message_text(
            "📊 *Services List*\n\nChoose a category:",
            reply_markup=categories_kb(cats, CATEGORY_ICONS),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    category = data[4:]  # strip "cat:"
    services = await db.get_services_by_category(category)
    if not services:
        await query.answer("No services in this category.", show_alert=True)
        return

    ctx.user_data["current_category"] = category
    icon = category_icon(category)
    await query.edit_message_text(
        f"{icon} *{category}*\n\nChoose a service:",
        reply_markup=services_kb(services, category),
        parse_mode=ParseMode.MARKDOWN
    )


async def service_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query      = update.callback_query
    await query.answer()
    data       = query.data

    if data == "svc_back":
        category = ctx.user_data.get("current_category", "")
        services = await db.get_services_by_category(category)
        icon     = category_icon(category)
        await query.edit_message_text(
            f"{icon} *{category}*\n\nChoose a service:",
            reply_markup=services_kb(services, category),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    service_id = data[4:]  # strip "svc:"
    svc        = await db.get_service(service_id)
    if not svc:
        await query.answer("Service not found.", show_alert=True)
        return

    refill_str  = "✅ Yes" if svc.get("refill")  else "❌ No"
    cancel_str  = "✅ Yes" if svc.get("cancel")  else "❌ No"
    icon        = category_icon(svc.get("category", ""))
    text = (
        f"{icon} *{svc['name']}*\n"
        f"{'─'*28}\n"
        f"🆔 Service ID: `{svc['service_id']}`\n"
        f"💵 Rate: `{fmt_coins(svc['rate'])} coins / 1000`\n"
        f"📊 Min: `{svc['min_order']:,}`\n"
        f"📈 Max: `{svc['max_order']:,}`\n"
        f"♻️ Refill: {refill_str}\n"
        f"❌ Cancel: {cancel_str}\n"
    )
    if svc.get("description"):
        text += f"\n📝 _{svc['description']}_"

    ctx.user_data["viewing_service"] = service_id
    await query.edit_message_text(
        text,
        reply_markup=service_detail_kb(service_id),
        parse_mode=ParseMode.MARKDOWN
    )


# ═══════════════════════════════════════════════════════════════════
#  NEW ORDER FLOW
# ═══════════════════════════════════════════════════════════════════
async def new_order(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cats = await db.get_categories()
    if not cats:
        await update.message.reply_text("⚠️ No services available. Try again later.")
        return ConversationHandler.END
    await update.message.reply_text(
        "🛒 *New Order*\n\nStep 1 — Choose a category:",
        reply_markup=categories_kb(cats, CATEGORY_ICONS),
        parse_mode=ParseMode.MARKDOWN
    )
    return ORDER_CATEGORY


async def order_start_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Start order from service detail button."""
    query      = update.callback_query
    await query.answer()
    service_id = query.data.split(":")[1]
    svc        = await db.get_service(service_id)
    if not svc:
        await query.answer("Service not found.", show_alert=True)
        return ORDER_LINK

    ctx.user_data["order_service_id"]   = service_id
    ctx.user_data["order_service_name"] = svc["name"]
    ctx.user_data["order_service"]      = svc
    ctx.user_data["order_category"]     = svc["category"]

    await query.edit_message_text(
        f"🔗 *Step — Enter Link*\n\n"
        f"Service: *{svc['name']}*\n\n"
        f"Please send the target link/username:",
        parse_mode=ParseMode.MARKDOWN
    )
    return ORDER_LINK


async def order_category_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Inline category selection during order flow."""
    query    = update.callback_query
    await query.answer()
    category = query.data[4:]
    services = await db.get_services_by_category(category)
    if not services:
        await query.answer("No services.", show_alert=True)
        return ORDER_CATEGORY

    ctx.user_data["order_category"] = category
    icon = category_icon(category)
    await query.edit_message_text(
        f"{icon} *{category}*\n\nStep 2 — Choose a service:",
        reply_markup=services_kb(services, category),
        parse_mode=ParseMode.MARKDOWN
    )
    return ORDER_SERVICE


async def order_service_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query      = update.callback_query
    await query.answer()
    service_id = query.data[4:]
    svc        = await db.get_service(service_id)
    if not svc:
        await query.answer("Service not found.", show_alert=True)
        return ORDER_SERVICE

    ctx.user_data["order_service_id"]   = service_id
    ctx.user_data["order_service_name"] = svc["name"]
    ctx.user_data["order_service"]      = svc

    await query.edit_message_text(
        f"🔗 *Step 3 — Enter Link*\n\n"
        f"Service: *{svc['name']}*\n"
        f"📊 Min: `{svc['min_order']:,}` | Max: `{svc['max_order']:,}`\n\n"
        f"Please send the target URL / username:",
        parse_mode=ParseMode.MARKDOWN
    )
    return ORDER_LINK


async def order_link_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    if len(link) < 3:
        await update.message.reply_text("❌ Invalid link. Please try again:")
        return ORDER_LINK
    ctx.user_data["order_link"] = link
    svc = ctx.user_data.get("order_service", {})
    await update.message.reply_text(
        f"📊 *Step 4 — Enter Quantity*\n\n"
        f"Min: `{svc.get('min_order',1):,}` | Max: `{svc.get('max_order',1000000):,}`\n\n"
        f"How many?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=cancel_keyboard()
    )
    return ORDER_QUANTITY


async def order_quantity_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ Enter a valid number:")
        return ORDER_QUANTITY

    qty = int(text)
    svc = ctx.user_data.get("order_service", {})
    min_q = svc.get("min_order", 1)
    max_q = svc.get("max_order", 1_000_000)

    if qty < min_q or qty > max_q:
        await update.message.reply_text(
            f"❌ Quantity must be between `{min_q:,}` and `{max_q:,}`.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ORDER_QUANTITY

    # Calculate cost
    rate    = svc.get("rate", 0)
    charge  = round((qty / 1000) * rate, 4)
    user_id = update.effective_user.id

    # VIP discount
    udata   = await db.get_user(user_id)
    vip_ok  = await db.is_vip_active(udata)
    discount = 0
    if vip_ok and udata.get("vip_plan"):
        from config import VIP_PLANS
        discount = VIP_PLANS.get(udata["vip_plan"], {}).get("discount", 0)
        charge   = round(charge * (1 - discount / 100), 4)

    ctx.user_data["order_quantity"] = qty
    ctx.user_data["order_charge"]   = charge

    link = ctx.user_data.get("order_link", "")
    name = ctx.user_data.get("order_service_name", "")
    disc_str = f"\n🏷️ VIP Discount: `{discount}%`" if discount else ""

    text = (
        f"📋 *Order Confirmation*\n"
        f"{'─'*28}\n"
        f"📦 Service: `{name}`\n"
        f"🔗 Link: `{link}`\n"
        f"📊 Quantity: `{qty:,}`\n"
        f"💵 Cost: `{fmt_coins(charge)} coins`"
        f"{disc_str}\n\n"
        f"💰 Your Balance: `{fmt_coins(udata['balance'])} coins`\n\n"
        f"✅ Confirm order?"
    )
    service_id = ctx.user_data.get("order_service_id", "")
    await update.message.reply_text(
        text,
        reply_markup=confirm_order_kb(service_id),
        parse_mode=ParseMode.MARKDOWN
    )
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

    # Check daily limit
    today_orders = await db.user_orders_today(user_id)
    if today_orders >= MAX_ORDERS_PER_DAY:
        await query.edit_message_text(
            f"❌ Daily order limit ({MAX_ORDERS_PER_DAY}) reached. Try tomorrow."
        )
        ctx.user_data.clear()
        return ConversationHandler.END

    service_id = ctx.user_data.get("order_service_id")
    service_name = ctx.user_data.get("order_service_name")
    category   = ctx.user_data.get("order_category", "")
    link       = ctx.user_data.get("order_link")
    qty        = ctx.user_data.get("order_quantity")
    charge     = ctx.user_data.get("order_charge")

    # Deduct balance
    ok = await db.deduct_balance(user_id, charge, f"Order: {service_name}")
    if not ok:
        await query.edit_message_text(
            "❌ Insufficient balance!\n\n💳 Use *Buy Coins* to add funds.",
            parse_mode=ParseMode.MARKDOWN
        )
        ctx.user_data.clear()
        return ConversationHandler.END

    # Place API order
    api_order_id = None
    api_status   = "Pending"
    api_result   = await smm_api.add_order(service_id, link, qty)
    if "order" in api_result:
        api_order_id = str(api_result["order"])
        api_status   = "Processing"
    elif "error" in api_result:
        # Refund on API error
        await db.add_balance(user_id, charge, "Refund: API error")
        await query.edit_message_text(
            f"❌ Order failed: {api_result['error']}\n\nBalance refunded."
        )
        ctx.user_data.clear()
        return ConversationHandler.END

    order_id = await db.create_order(
        user_id, service_id, service_name, category,
        link, qty, charge, api_order_id
    )

    # ── Send order log notification to log bot / channel ──────────
    await send_order_log(
        order_id     = order_id,
        user_id      = user_id,
        service_name = service_name,
        quantity     = qty,
        link         = link,
        status       = api_status,
    )

    svc = ctx.user_data.get("order_service", {})
    await query.edit_message_text(
        f"✅ *Order Placed Successfully!*\n"
        f"{'─'*28}\n"
        f"🆔 Order ID: `#{order_id}`\n"
        f"📦 Service: `{service_name}`\n"
        f"🔗 Link: `{link}`\n"
        f"📊 Quantity: `{qty:,}`\n"
        f"💵 Charged: `{fmt_coins(charge)} coins`\n"
        f"📊 Status: `{api_status}`\n\n"
        f"Use 🔎 *Order Tracker* to check status.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=order_actions_kb(order_id, api_order_id or "",
                                       bool(svc.get("refill")), bool(svc.get("cancel")))
    )
    ctx.user_data.clear()
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════
#  MY ORDERS
# ═══════════════════════════════════════════════════════════════════
async def my_orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    orders  = await db.get_user_orders(user_id, 10)
    if not orders:
        await update.message.reply_text("📦 No orders yet.\n\nUse 🛒 *New Order* to place one!", parse_mode=ParseMode.MARKDOWN)
        return
    text = "📦 *My Orders* (Last 10)\n\n"
    for o in orders:
        text += (
            f"🆔 `#{o['id']}` | {fmt_status(o['status'])}\n"
            f"📦 {o.get('service_name','—')[:30]}\n"
            f"💵 {fmt_coins(o['charge'])} | 📊 {o['quantity']:,}\n"
            f"📅 {fmt_date(o['created_at'])}\n"
            f"{'─'*24}\n"
        )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def order_refresh_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer("🔄 Refreshing...")
    parts    = query.data.split(":")
    order_id = int(parts[1])
    order    = await db.get_order(order_id)
    if not order or not order.get("api_order_id"):
        await query.answer("Cannot refresh — no API order ID.", show_alert=True)
        return
    result = await smm_api.order_status(order["api_order_id"])
    if "status" in result:
        await db.update_order_status(
            order_id, result["status"],
            int(result.get("start_count", 0)),
            int(result.get("remains", 0))
        )
        await query.edit_message_text(
            f"📦 *Order #{order_id} Updated*\n"
            f"📊 Status: `{result['status']}`\n"
            f"📈 Start Count: `{result.get('start_count',0):,}`\n"
            f"📉 Remains: `{result.get('remains',0):,}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=query.message.reply_markup
        )
    else:
        await query.answer(f"Error: {result.get('error','Unknown')}", show_alert=True)


async def order_refill_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    order_id = int(query.data.split(":")[1])
    order    = await db.get_order(order_id)
    if not order or not order.get("api_order_id"):
        await query.answer("Cannot refill.", show_alert=True)
        return
    result = await smm_api.refill_order(order["api_order_id"])
    if "refill" in result:
        await query.answer("✅ Refill submitted!", show_alert=True)
    else:
        await query.answer(f"Error: {result.get('error','Unknown')}", show_alert=True)


async def order_cancel_api_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    order_id = int(query.data.split(":")[1])
    order    = await db.get_order(order_id)
    if not order or not order.get("api_order_id"):
        await query.answer("Cannot cancel.", show_alert=True)
        return
    result = await smm_api.cancel_order(order["api_order_id"])
    if "cancel" in result or result.get("status") == "1":
        await db.update_order_status(order_id, "Cancelled")
        await query.edit_message_text(f"❌ Order #{order_id} cancelled.")
    else:
        await query.answer(f"Error: {result.get('error','Unknown')}", show_alert=True)


# ═══════════════════════════════════════════════════════════════════
#  ORDER TRACKER
# ═══════════════════════════════════════════════════════════════════
async def order_tracker(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔎 *Order Tracker*\n\nEnter your Order ID:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=cancel_keyboard()
    )
    return TRACKER_INPUT


async def tracker_input_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lstrip("#")
    if not text.isdigit():
        await update.message.reply_text("❌ Invalid Order ID. Enter a number:")
        return TRACKER_INPUT

    order_id = int(text)
    user_id  = update.effective_user.id
    order    = await db.get_order(order_id)

    if not order or order["user_id"] != user_id:
        await update.message.reply_text("❌ Order not found or doesn't belong to you.", reply_markup=main_keyboard())
        return ConversationHandler.END

    # Try refreshing from API
    if order.get("api_order_id"):
        result = await smm_api.order_status(order["api_order_id"])
        if "status" in result:
            await db.update_order_status(
                order_id, result["status"],
                int(result.get("start_count", 0)),
                int(result.get("remains", 0))
            )
            order = await db.get_order(order_id)

    text = (
        f"🔎 *Order Details*\n"
        f"{'─'*28}\n"
        f"🆔 Order ID: `#{order['id']}`\n"
        f"📦 Service: `{order.get('service_name','—')}`\n"
        f"🔗 Link: `{order['link']}`\n"
        f"📊 Quantity: `{order['quantity']:,}`\n"
        f"💵 Charge: `{fmt_coins(order['charge'])} coins`\n"
        f"📊 Status: {fmt_status(order['status'])}\n"
        f"📈 Start Count: `{order.get('start_count',0):,}`\n"
        f"📉 Remains: `{order.get('remains',0):,}`\n"
        f"📅 Created: `{fmt_date(order['created_at'])}`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard())
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════
#  DAILY BONUS
# ═══════════════════════════════════════════════════════════════════
async def daily_bonus(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ok, msg = await db.claim_daily(user_id, DAILY_BONUS_AMOUNT)
    if ok:
        await update.message.reply_text(
            f"🎁 *Daily Bonus Claimed!*\n\n{msg}\n\n"
            f"Come back tomorrow for another bonus!",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(f"🎯 *Daily Bonus*\n\n{msg}", parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════
#  REDEEM CODE
# ═══════════════════════════════════════════════════════════════════
async def redeem_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎁 *Redeem Code*\n\nEnter your redeem code:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=cancel_keyboard()
    )
    return REDEEM_INPUT


async def redeem_input_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    code    = update.message.text.strip()
    user_id = update.effective_user.id
    ok, msg, amount = await db.use_redeem_code(user_id, code)
    await update.message.reply_text(
        f"🎁 *Redeem Result*\n\n{msg}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════
#  REFERRAL
# ═══════════════════════════════════════════════════════════════════
async def referral(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    udata   = await db.get_user(user_id)
    link    = referral_link(user_id)
    text = (
        f"👥 *Referral System*\n"
        f"{'─'*28}\n"
        f"🔗 Your Link:\n`{link}`\n\n"
        f"👥 Total Referrals: `{udata.get('referral_count',0)}`\n"
        f"💰 Earned: `{fmt_coins(udata.get('referral_earned',0))} coins`\n\n"
        f"💎 Earn *{REFERRAL_REWARD} coins* for each new user!"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════
#  LEADERBOARD
# ═══════════════════════════════════════════════════════════════════
async def leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏆 *Leaderboard*\n\nChoose a category:",
        reply_markup=leaderboard_kb(),
        parse_mode=ParseMode.MARKDOWN
    )


async def leaderboard_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    board = query.data.split(":")[1]

    if board == "referrers":
        rows = await db.top_referrers(10)
        title = "🥇 Top Referrers"
        lines = [f"{i+1}. `{r['full_name']}` — {r['referral_count']} referrals" for i, r in enumerate(rows)]
    elif board == "buyers":
        rows  = await db.top_buyers(10)
        title = "🥈 Top Buyers"
        lines = [f"{i+1}. `{r['full_name']}` — {fmt_coins(r['total_spent'])} coins" for i, r in enumerate(rows)]
    else:
        rows  = await db.top_orders(10)
        title = "🥉 Top Orders"
        lines = [f"{i+1}. `{r['full_name']}` — {r['total_orders']} orders" for i, r in enumerate(rows)]

    medals = ["🥇","🥈","🥉"] + ["🔹"]*7
    result_lines = [f"{medals[i]} {line[3:]}" for i, line in enumerate(lines)]
    text = f"🏆 *{title}*\n{'─'*28}\n" + "\n".join(result_lines)
    await query.edit_message_text(text, reply_markup=leaderboard_kb(), parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════
#  MY STATISTICS
# ═══════════════════════════════════════════════════════════════════
async def my_statistics(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    udata   = await db.get_user(user_id)
    rank    = await db.get_user_rank(user_id)
    avg     = round(udata.get("total_spent", 0) / max(udata.get("total_orders", 1), 1), 2)
    text = (
        f"📈 *My Statistics*\n"
        f"{'─'*28}\n"
        f"📦 Total Orders: `{udata.get('total_orders',0)}`\n"
        f"💰 Total Spent: `{fmt_coins(udata.get('total_spent',0))} coins`\n"
        f"📊 Avg per Order: `{fmt_coins(avg)} coins`\n"
        f"💳 Total Deposited: `{fmt_coins(udata.get('total_deposited',0))} coins`\n"
        f"👥 Referrals Made: `{udata.get('referral_count',0)}`\n"
        f"🏆 Global Rank: `#{rank}`\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


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
            f"⭐ *VIP Membership*\n"
            f"{'─'*28}\n"
            f"✅ Active Plan: `{badge} {udata['vip_plan'].title()} VIP`\n"
            f"📅 Expires: `{fmt_date(udata.get('vip_expires',''))}`\n\n"
            f"🎉 Enjoy your premium benefits!"
        )
    else:
        lines = ["⭐ *VIP Membership*\n\nChoose a plan:\n"]
        for key, plan in VIP_PLANS.items():
            lines.append(
                f"{plan['name']}\n"
                f"💵 Price: `${plan['price']}/month`\n"
                f"🏷️ Discount: `{plan['discount']}%`\n"
                f"🎁 Bonus Coins: `{plan['bonus_coins']}`\n"
                f"🌟 Priority Support: ✅\n"
            )
        text = "\n".join(lines)
    await update.message.reply_text(text, reply_markup=vip_plans_kb(), parse_mode=ParseMode.MARKDOWN)


async def vip_buy_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    plan_key = query.data.split(":")[1]
    plan    = VIP_PLANS.get(plan_key)
    if not plan:
        await query.answer("Plan not found.", show_alert=True)
        return

    user_id = query.from_user.id
    udata   = await db.get_user(user_id)
    cost    = plan["price"] / COIN_RATE  # convert $ to coins

    ok = await db.deduct_balance(user_id, cost, f"VIP: {plan['name']}")
    if not ok:
        await query.edit_message_text(
            f"❌ Insufficient balance!\n\n"
            f"Required: `{fmt_coins(cost)} coins`\n"
            f"Your balance: `{fmt_coins(udata['balance'])} coins`\n\n"
            f"💳 Use *Buy Coins* to add funds.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await db.set_vip(user_id, plan_key, plan["days"])
    await db.add_balance(user_id, plan["bonus_coins"], f"VIP Bonus: {plan['name']}")

    await query.edit_message_text(
        f"🎉 *VIP Activated!*\n"
        f"{'─'*28}\n"
        f"✅ Plan: `{plan['name']}`\n"
        f"🏷️ Discount: `{plan['discount']}%`\n"
        f"🎁 Bonus Coins: `+{plan['bonus_coins']}`\n"
        f"📅 Valid: `{plan['days']} days`\n\n"
        f"Enjoy your premium benefits! 🚀",
        parse_mode=ParseMode.MARKDOWN
    )


# ═══════════════════════════════════════════════════════════════════
#  SUPPORT TICKETS
# ═══════════════════════════════════════════════════════════════════
async def support(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "☎️ *Support*\n\nDescribe your issue and we'll help you!\n\nEnter your subject:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=cancel_keyboard()
    )
    return TICKET_SUBJECT


async def ticket_subject_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["ticket_subject"] = update.message.text.strip()
    await update.message.reply_text(
        "📝 Now describe your issue in detail:",
        reply_markup=cancel_keyboard()
    )
    return TICKET_MESSAGE


async def ticket_message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subject = ctx.user_data.get("ticket_subject", "No subject")
    message = update.message.text.strip()

    ticket_id = await db.create_ticket(user_id, subject, message, update.message.message_id)

    await update.message.reply_text(
        f"✅ *Ticket Submitted!*\n\n"
        f"🆔 Ticket ID: `#{ticket_id}`\n"
        f"📋 Subject: `{subject}`\n\n"
        f"Our team will reply soon.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )

    # Notify admins
    udata = await db.get_user(user_id)
    admin_msg = (
        f"☎️ *New Support Ticket #{ticket_id}*\n"
        f"{'─'*28}\n"
        f"👤 User: `{udata['full_name']}` (`@{udata.get('username','')}`)\n"
        f"🆔 ID: `{user_id}`\n"
        f"📋 Subject: `{subject}`\n"
        f"💬 Message: {message}"
    )
    from keyboards.inline import ticket_reply_kb
    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_message(
                admin_id, admin_msg,
                reply_markup=ticket_reply_kb(ticket_id, user_id),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            pass

    ctx.user_data.clear()
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════
#  UPDATES CHANNEL
# ═══════════════════════════════════════════════════════════════════
async def updates_channel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    channel = await db.get_setting("updates_channel", "")
    if channel:
        await update.message.reply_text(
            f"📢 *Updates Channel*\n\n{channel}",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text("📢 No updates channel set yet.")


# ═══════════════════════════════════════════════════════════════════
#  CANCEL
# ═══════════════════════════════════════════════════════════════════
async def cancel_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text(
        "❌ Cancelled.",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════
#  BANNED CHECK MIDDLEWARE
# ═══════════════════════════════════════════════════════════════════
async def check_banned(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    user_id = update.effective_user.id
    udata   = await db.get_user(user_id)
    if udata and udata.get("is_banned"):
        if update.message:
            await update.message.reply_text("🚫 You are banned from this bot.")
        return
