"""
Partner API (Instant Delivery) — python-telegram-bot v20+ handler
"""
import uuid
import json
import logging
from html import escape

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

from api import partner_api as papi
from api.partner_api import PartnerAPIError
from config import (
    PARTNER_ENABLED, PARTNER_DELIVERY_ICONS,
    MAX_ORDERS_PER_DAY, PARTNER_CACHE_TTL, ADMIN_IDS,
)
from database import (
    create_partner_order, get_user_partner_orders,
    get_partner_order_by_code, user_partner_orders_today,
    update_partner_order_status, get_unrecovered_partner_orders,
    get_partner_stats,
)
from keyboards.reply import (
    main_keyboard, service_menu_keyboard, cancel_keyboard,
)
from utils.partner_cache import get_cache, set_cache, invalidate as cache_invalidate

log = logging.getLogger(__name__)

# Conversation state
WAITING_QTY = 1


# ─────────────────────────────────────────────────────
#  KEYBOARD BUILDERS
# ─────────────────────────────────────────────────────
def _providers_kb(providers: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for p in providers:
        emoji = (p.get("emoji") or {}).get("normal") or "📦"
        rows.append([InlineKeyboardButton(
            text=f"{emoji} {p['name']}",
            callback_data=f"pprov:{p['key']}:1",
        )])
    return InlineKeyboardMarkup(rows)


def _products_kb(products: list[dict], provider_key: str,
                 page: int, per_page: int = 8) -> InlineKeyboardMarkup:
    start = (page - 1) * per_page
    chunk = products[start:start + per_page]
    rows = []
    for p in chunk:
        price = p.get("yourPrice", "?")
        stock = (p.get("stock") or {}).get("count", 0)
        icon = "✅" if stock > 0 else "❌"
        rows.append([InlineKeyboardButton(
            text=f"{icon} {p['name']} — ${price}",
            callback_data=f"pprod:{p['slug']}",
        )])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"pprov:{provider_key}:{page-1}"))
    if start + per_page < len(products):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"pprov:{provider_key}:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 Categories", callback_data="pcat")])
    return InlineKeyboardMarkup(rows)


def _delivery_messages(res: dict) -> list[str]:
    """ডেলিভারি মেসেজ। delivery.content কখনো log-এ যাবে না।"""
    out = []
    d = res.get("delivery") or {}

    if d.get("link"):
        out.append(f"🔗 <b>Activation Link</b>\n{d['link']}")
    if d.get("code"):
        out.append(f"🎟 <b>Coupon Code</b>\n<code>{d['code']}</code>")
    if d.get("content"):
        out.append(
            "🔐 <b>Login Credentials (গোপন রাখুন)</b>\n"
            f"<code>{escape(d['content'])}</code>"
        )
    for ln in res.get("lines") or []:
        if ln.get("code"):
            out.append(f"🎟 <code>{ln['code']}</code>")
        elif ln.get("link"):
            out.append(f"🔗 {ln['link']}")
    if d.get("instructions"):
        out.append(f"ℹ️ {d['instructions']}")
    return out


# ─────────────────────────────────────────────────────
#  ENTRY: /partner  বা  "🛍 ᴘᴀʀᴛɴᴇʀ ꜱʜᴏᴘ"
# ─────────────────────────────────────────────────────
async def partner_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not PARTNER_ENABLED:
        await update.message.reply_text("⚠️ Partner Shop এখন নিষ্ক্রিয়।")
        return ConversationHandler.END

    providers = get_cache("partner:providers")
    if not providers:
        try:
            providers = await papi.providers()
            set_cache("partner:providers", providers, PARTNER_CACHE_TTL)
        except PartnerAPIError as e:
            await update.message.reply_text(f"❌ {e.code}: {e.message}")
            return ConversationHandler.END

    if not providers:
        await update.message.reply_text("এই মুহূর্তে কোনো ক্যাটাগরি নেই।")
        return ConversationHandler.END

    await update.message.reply_text(
        "🛍 <b>Instant Delivery Shop</b>\n\nএকটি ক্যাটাগরি বেছে নিন:",
        reply_markup=_providers_kb(providers),
        parse_mode="HTML",
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────────────
#  CALLBACKS
# ─────────────────────────────────────────────────────
async def partner_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    # ── ক্যাটাগরি লিস্ট ──
    if data == "pcat":
        providers = get_cache("partner:providers")
        if not providers:
            try:
                providers = await papi.providers()
                set_cache("partner:providers", providers, PARTNER_CACHE_TTL)
            except PartnerAPIError as e:
                await q.edit_message_text(f"❌ {e.code}")
                return
        await q.edit_message_text(
            "🛍 <b>Instant Delivery Shop</b>\n\nএকটি ক্যাটাগরি বেছে নিন:",
            reply_markup=_providers_kb(providers),
            parse_mode="HTML",
        )
        return

    # ── প্রোডাক্ট লিস্ট ──
    if data.startswith("pprov:"):
        _, key, page = data.split(":")
        page = int(page)
        cache_key = f"partner:products:{key}"
        products = get_cache(cache_key)
        if not products:
            try:
                products = await papi.products(provider=key)
                set_cache(cache_key, products, PARTNER_CACHE_TTL)
            except PartnerAPIError as e:
                await q.edit_message_text(f"❌ {e.code}: {e.message}")
                return

        if not products:
            await q.edit_message_text("এই ক্যাটাগরিতে কোনো পণ্য নেই।")
            return

        try:
            await q.edit_message_text(
                f"📦 <b>{key.title()} — Products</b> (পৃষ্ঠা {page})",
                reply_markup=_products_kb(products, key, page),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    # ── প্রোডাক্ট ডিটেইল → পরিমাণ জিজ্ঞাসা ──
    if data.startswith("pprod:"):
        slug = data.split(":", 1)[1]
        cache_key = f"partner:product:{slug}"
        p = get_cache(cache_key)
        if not p:
            try:
                p = await papi.product(slug)
                set_cache(cache_key, p, PARTNER_CACHE_TTL)
            except PartnerAPIError as e:
                await q.message.reply_text(f"❌ {e.code}: {e.message}")
                return

        stock = p.get("stock") or {}
        if not stock.get("inStock"):
            await q.message.reply_text("❌ স্টকে নেই।")
            return

        dtype = p.get("deliveryType", "LINK")
        icon = PARTNER_DELIVERY_ICONS.get(dtype, "📦")

        text = (
            f"<b>{p.get('name', slug)}</b>\n\n"
            f"💰 মূল্য: <b>${p.get('yourPrice', '?')}</b>\n"
            f"📦 স্টক: <b>{stock.get('count', 0)}</b>\n"
            f"{icon} ডেলিভারি: <b>{dtype}</b>\n"
        )
        if p.get("durationDays"):
            text += f"⏱ সময়কাল: {p['durationDays']} দিন\n"
        if (p.get("warranty") or {}).get("enabled"):
            text += f"🛡 ওয়ারেন্টি: {p['warranty']['days']} দিন\n"
        if p.get("description"):
            text += f"\n<i>{escape(p['description'][:200])}</i>\n"
        text += f"\nকত পিস নিতে চান? (1–{stock.get('maxQuantity', 1)})\nশুধু সংখ্যাটি পাঠান।"

        await q.message.reply_text(text, parse_mode="HTML")

        # state → user_data
        context.user_data["partner_pending"] = {
            "slug": slug,
            "name": p.get("name", slug),
            "delivery_type": dtype,
            "unit_price": float(p.get("yourPrice") or 0),
            "max_qty": int(stock.get("maxQuantity") or 1),
        }
        # Conversation state সেট (আলাদা হ্যান্ডলারের মাধ্যমে)
        context.user_data["_await_partner_qty"] = True
        return

    # ── পুরনো অর্ডার আবার দেখাও ──
    if data.startswith("pget:"):
        code = data.split(":", 1)[1]
        record = await get_partner_order_by_code(code)
        if not record or record["user_id"] != q.from_user.id:
            await q.message.reply_text("❌ এই অর্ডার আপনার নয়।")
            return
        try:
            res = await papi.get_order(code)
        except PartnerAPIError as e:
            await q.message.reply_text(f"❌ {e.code}: {e.message}")
            return
        chunks = _delivery_messages(res)
        if not chunks:
            await q.message.reply_text("ℹ️ এই অর্ডারে ডেলিভারি নেই।")
            return
        await q.message.reply_text(f"🧾 <b>{code}</b> — {res.get('status', '?')}", parse_mode="HTML")
        for ch in chunks:
            try:
                await q.message.reply_text(ch, parse_mode="HTML")
            except Exception:
                await q.message.reply_text(ch)
        return


# ─────────────────────────────────────────────────────
#  QUANTITY INPUT  (ConversationHandler state)
# ─────────────────────────────────────────────────────
async def partner_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data.get("partner_pending")
    if not data:
        return ConversationHandler.END

    try:
        qty = int(update.message.text.strip())
        if qty < 1 or qty > data["max_qty"]:
            raise ValueError
    except Exception:
        await update.message.reply_text(
            f"❌ 1 থেকে {data['max_qty']} এর মধ্যে সংখ্যা পাঠান।"
        )
        return WAITING_QTY

    user_id = update.effective_user.id

    # ডেইলি লিমিট
    used = await user_partner_orders_today(user_id)
    if used >= MAX_ORDERS_PER_DAY:
        await update.message.reply_text(
            f"⛔ আজকের অর্ডার লিমিট শেষ ({MAX_ORDERS_PER_DAY})।",
            reply_markup=main_keyboard(),
        )
        context.user_data.pop("partner_pending", None)
        return ConversationHandler.END

    # API ব্যালেন্স চেক
    try:
        await papi.balance()
    except PartnerAPIError as e:
        await update.message.reply_text(f"❌ {e.code}: {e.message}")
        context.user_data.pop("partner_pending", None)
        return ConversationHandler.END

    await update.message.reply_text("⏳ অর্ডার প্রসেস হচ্ছে...")

    ext_id = f"tg-{user_id}-{uuid.uuid4().hex[:12]}"

    try:
        res = await papi.create_order(data["slug"], qty, ext_id)
    except PartnerAPIError as e:
        msg = f"❌ <b>{e.code}</b>\n{escape(e.message)}"
        if e.code == "INSUFFICIENT_BALANCE":
            msg += (
                f"\n\nদরকার: <b>${e.extra.get('required')}</b>"
                f"\nআছে: <b>${e.extra.get('balance')}</b>"
            )
        if e.request_id:
            msg += f"\n<code>reqId: {e.request_id}</code>"
        log.error("Partner order failed user=%s code=%s req=%s",
                  user_id, e.code, e.request_id)
        await update.message.reply_text(msg, parse_mode="HTML")
        context.user_data.pop("partner_pending", None)
        return ConversationHandler.END

    # DB সেভ
    lines_meta = json.dumps(
        [{"orderCode": ln.get("orderCode")} for ln in res.get("lines", []) or []]
    ) if res.get("lines") else None

    await create_partner_order(
        user_id=user_id,
        external_id=ext_id,
        order_code=res.get("orderCode", ""),
        product_slug=data["slug"],
        product_name=data["name"],
        delivery_type=data["delivery_type"],
        quantity=qty,
        unit_price=float(res.get("unitPrice") or data["unit_price"]),
        total_charged=float(res.get("totalCharged") or data["unit_price"] * qty),
        status=res.get("status", "COMPLETED"),
        lines_json=lines_meta,
    )

    cache_invalidate("partner:product:")
    cache_invalidate("partner:products:")

    head = (
        f"✅ <b>অর্ডার সম্পন্ন</b>\n"
        f"🧾 <code>{res.get('orderCode', '')}</code>\n"
        f"💵 চার্জ: <b>${res.get('totalCharged', '?')}</b>"
    )
    if res.get("balanceAfter"):
        head += f"\n💰 API ব্যালেন্স: <b>${res['balanceAfter']}</b>"
    await update.message.reply_text(head, parse_mode="HTML")

    for chunk in _delivery_messages(res):
        try:
            await update.message.reply_text(chunk, parse_mode="HTML")
        except Exception:
            await update.message.reply_text(chunk)

    context.user_data.pop("partner_pending", None)
    return ConversationHandler.END


async def partner_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("partner_pending", None)
    await update.message.reply_text("বাতিল করা হলো।", reply_markup=main_keyboard())
    return ConversationHandler.END


# ─────────────────────────────────────────────────────
#  MY PARTNER ORDERS
# ─────────────────────────────────────────────────────
async def my_partner_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = await get_user_partner_orders(update.effective_user.id, limit=10)
    if not orders:
        await update.message.reply_text("📭 আপনার কোনো Partner অর্ডার নেই।")
        return

    lines = ["📦 <b>সর্বশেষ Partner অর্ডার:</b>\n"]
    rows = []
    for i, o in enumerate(orders, 1):
        lines.append(
            f"{i}. <code>{o['order_code']}</code>\n"
            f"   {escape(o['product_name'] or o['product_slug'])} · "
            f"${o['total_charged']} · {o['status']}"
        )
        rows.append([InlineKeyboardButton(
            text=f"🔍 {o['order_code']}",
            callback_data=f"pget:{o['order_code']}",
        )])

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="HTML",
    )


# ─────────────────────────────────────────────────────
#  ADMIN STATS
# ─────────────────────────────────────────────────────
async def partner_stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    stats = await get_partner_stats()
    api_info = ""
    try:
        u = await papi.usage()
        api_info = (
            f"\n\n🌐 <b>Live API</b>\n"
            f"ব্যালেন্স: <b>${u.get('balance')}</b>\n"
            f"24h অর্ডার: {u.get('apiOrders24h')}\n"
            f"24h খরচ: ${u.get('apiSpend24h')}\n"
            f"আজ রিকোয়েস্ট: {u.get('requestCountToday')}\n"
            f"আজ এরর: {u.get('errorCountToday')}"
        )
    except PartnerAPIError as e:
        api_info = f"\n\n⚠️ API: {e.code}"

    await update.message.reply_text(
        f"📊 <b>Partner Stats</b>\n\n"
        f"মোট অর্ডার: <b>{stats['total_orders']}</b>\n"
        f"মোট খরচ: <b>${stats['total_spend']}</b>\n"
        f"আজ অর্ডার: <b>{stats['today_orders']}</b>\n"
        f"আজ খরচ: <b>${stats['today_spend']}</b>"
        f"{api_info}",
        parse_mode="HTML",
    )


# ─────────────────────────────────────────────────────
#  RECONCILE (startup-এ কল করুন)
# ─────────────────────────────────────────────────────
async def reconcile_partner_orders(application):
    """bot startup-এ চালান। bot = application.bot দিয়ে মেসেজ পাঠায়।"""
    pending = await get_unrecovered_partner_orders()
    if not pending:
        return
    log.info("Reconciling %d partner orders...", len(pending))
    bot = application.bot
    for o in pending:
        code = o.get("order_code")
        if not code:
            continue
        try:
            res = await papi.get_order(code)
        except PartnerAPIError as e:
            log.warning("Reconcile %s failed: %s", code, e.code)
            continue

        await update_partner_order_status(code, res.get("status", "COMPLETED"), recovered=1)
        chunks = _delivery_messages(res)
        if not chunks:
            continue
        try:
            await bot.send_message(
                o["user_id"],
                f"🔄 <b>পুনরুদ্ধার করা অর্ডার</b>\n🧾 <code>{code}</code>",
                parse_mode="HTML",
            )
            for ch in chunks:
                try:
                    await bot.send_message(o["user_id"], ch, parse_mode="HTML")
                except Exception:
                    await bot.send_message(o["user_id"], ch)
        except Exception as e:
            log.warning("Notify user %s failed: %s", o["user_id"], e)


# ─────────────────────────────────────────────────────
#  CONVERSATION HANDLER FACTORY
# ─────────────────────────────────────────────────────
def build_partner_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("partner", partner_entry),
            MessageHandler(
                filters.Regex("^🛍 ᴘᴀʀᴛɴᴇʀ ꜱʜᴏᴘ$") | filters.Regex("^🛍 ᴘᴀʀᴛɴᴇʀ ᴏʀᴅᴇʀ$"),
                partner_entry,
            ),
        ],
        states={
            WAITING_QTY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND
                    & ~filters.Regex("^❌ ᴄᴀɴᴄᴇʟ$")
                    & ~filters.Regex("^🔙 ʙᴀᴄᴋ$"),
                    partner_qty,
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", partner_cancel),
            MessageHandler(filters.Regex("^❌ ᴄᴀɴᴄᴇʟ$"), partner_cancel),
        ],
        per_user=True,
        per_chat=True,
    )