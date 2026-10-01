"""
Partner API (Instant Delivery) — python-telegram-bot v20+
LINK / COUPON / READY_ACCOUNT

⚠️ Security:
   - delivery.link / code / content কখনো log/DB-তে যায় না
   - API ব্যালেন্স, error code, reqId ইউজারকে দেখানো হয় না
   - সব internal detail শুধু অ্যাডমিন PM-এ
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
from keyboards.reply import main_keyboard
from utils.partner_cache import get_cache, set_cache, invalidate as cache_invalidate

log = logging.getLogger(__name__)

WAITING_ACTION = 1
WAITING_QTY    = 2


# ─────────────────────────────────────────────────────
#  FRIENDLY ERROR MAP  (ইউজার-facing)
# ─────────────────────────────────────────────────────
_FRIENDLY_ERRORS = {
    "INSUFFICIENT_BALANCE": "⚠️ সাময়িকভাবে অর্ডার নেওয়া যাচ্ছে না। কিছুক্ষণ পরে চেষ্টা করুন অথবা সাপোর্টে যোগাযোগ করুন।",
    "OUT_OF_STOCK":         "❌ এই প্রোডাক্টটি এইমাত্র স্টক আউট হয়ে গেছে।",
    "PRODUCT_NOT_FOUND":    "❌ প্রোডাক্টটি খুঁজে পাওয়া যায়নি।",
    "PRODUCT_UNAVAILABLE":  "⚠️ প্রোডাক্টটি এই মুহূর্তে unavailable।",
    "PRODUCT_NOT_ALLOWED":  "⚠️ প্রোডাক্টটি এই মুহূর্তে unavailable।",
    "INVALID_QUANTITY":     "❌ পরিমাণ সঠিক নয়।",
    "RATE_LIMIT_EXCEEDED":  "⏳ অনেক দ্রুত চেষ্টা করছেন। একটু পরে আবার দিন।",
    "MAINTENANCE":          "🛠 সার্ভার রক্ষণাবেক্ষণ চলছে। একটু পরে চেষ্টা করুন।",
    "PARTNER_SUSPENDED":    "🚫 সাময়িকভাবে অর্ডার বন্ধ। সাপোর্টে যোগাযোগ করুন।",
    "API_ACCESS_DISABLED":  "🚫 সার্ভিস সাময়িক বন্ধ। সাপোর্টে যোগাযোগ করুন।",
    "USER_BLOCKED":         "🚫 আপনার অ্যাকাউন্ট ব্লকড। সাপোর্টে যোগাযোগ করুন।",
    "NETWORK":              "📡 নেটওয়ার্ক সমস্যা। আবার চেষ্টা করুন।",
    "NO_KEY":               "⚠️ সার্ভিসে সাময়িক সমস্যা হচ্ছে। কিছুক্ষণ পরে চেষ্টা করুন।",
    "BAD_JSON":             "⚠️ সার্ভিসে সাময়িক সমস্যা হচ্ছে। কিছুক্ষণ পরে চেষ্টা করুন।",
    "INVALID_API_KEY":      "⚠️ সার্ভিসে সাময়িক সমস্যা হচ্ছে। কিছুক্ষণ পরে চেষ্টা করুন।",
    "API_KEY_EXPIRED":      "⚠️ সার্ভিসে সাময়িক সমস্যা হচ্ছে। কিছুক্ষণ পরে চেষ্টা করুন।",
}

_GENERIC_ERROR = "⚠️ সার্ভিসে সাময়িক সমস্যা হচ্ছে। কিছুক্ষণ পরে আবার চেষ্টা করুন।"


def _friendly_error(code: str) -> str:
    """ইউজার-ফ্রেন্ডলি মেসেজ — কোনো internal detail ছাড়া।"""
    return _FRIENDLY_ERRORS.get(code, _GENERIC_ERROR)


async def _notify_admins_of_error(context, where: str, e: PartnerAPIError):
    """শুধু অ্যাডমিনদের কাছে বিস্তারিত এরর পাঠায়। Silent fail-safe।"""
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"⚠️ <b>Partner API Error</b>\n"
                f"📍 Where: <code>{where}</code>\n"
                f"❌ Code: <code>{e.code}</code>\n"
                f"💬 {escape(e.message or '')}\n"
                f"🆔 <code>reqId: {e.request_id or '—'}</code>",
                parse_mode="HTML",
            )
        except Exception:
            pass


# ─────────────────────────────────────────────────────
#  KEYBOARDS
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


def _products_kb(products, provider_key, page, per_page=8) -> InlineKeyboardMarkup:
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
    """⚠️ delivery.content কখনো log-এ যাবে না।"""
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
#  ENTRY
# ─────────────────────────────────────────────────────
async def partner_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not PARTNER_ENABLED:
        await update.effective_message.reply_text("⚠️ Partner Shop এখন নিষ্ক্রিয়।")
        return ConversationHandler.END

    providers = get_cache("partner:providers")
    if not providers:
        try:
            providers = await papi.providers()
            set_cache("partner:providers", providers, PARTNER_CACHE_TTL)
        except PartnerAPIError as e:
            log.error("Partner providers failed: code=%s req=%s msg=%s",
                      e.code, e.request_id, e.message)
            await _notify_admins_of_error(context, "providers", e)
            await update.effective_message.reply_text(
                _friendly_error(e.code), parse_mode="HTML"
            )
            return ConversationHandler.END

    if not providers:
        await update.effective_message.reply_text("এই মুহূর্তে কোনো ক্যাটাগরি নেই।")
        return ConversationHandler.END

    await update.effective_message.reply_text(
        "🛍 <b>Instant Delivery Shop</b>\n\nএকটি ক্যাটাগরি বেছে নিন:",
        reply_markup=_providers_kb(providers),
        parse_mode="HTML",
    )
    return WAITING_ACTION


# ─────────────────────────────────────────────────────
#  STATE: WAITING_ACTION — nav + category
# ─────────────────────────────────────────────────────
async def partner_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    # ── ক্যাটাগরি তালিকায় ফেরা ──
    if data == "pcat":
        providers = get_cache("partner:providers")
        if not providers:
            try:
                providers = await papi.providers()
                set_cache("partner:providers", providers, PARTNER_CACHE_TTL)
            except PartnerAPIError as e:
                log.error("Partner pcat providers failed: code=%s req=%s msg=%s",
                          e.code, e.request_id, e.message)
                await _notify_admins_of_error(context, "pcat_providers", e)
                await q.edit_message_text(_friendly_error(e.code))
                return WAITING_ACTION
        await q.edit_message_text(
            "🛍 <b>Instant Delivery Shop</b>\n\nএকটি ক্যাটাগরি বেছে নিন:",
            reply_markup=_providers_kb(providers),
            parse_mode="HTML",
        )
        return WAITING_ACTION

    # ── নির্দিষ্ট প্রোভাইডারের প্রোডাক্ট লিস্ট ──
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
                log.error("Partner products(%s) failed: code=%s req=%s msg=%s",
                          key, e.code, e.request_id, e.message)
                await _notify_admins_of_error(context, f"products:{key}", e)
                await q.edit_message_text(_friendly_error(e.code))
                return WAITING_ACTION
        if not products:
            await q.edit_message_text("এই ক্যাটাগরিতে কোনো পণ্য নেই।")
            return WAITING_ACTION
        try:
            await q.edit_message_text(
                f"📦 <b>{key.title()} — Products</b> (পৃষ্ঠা {page})",
                reply_markup=_products_kb(products, key, page),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return WAITING_ACTION

    # ── পুরনো অর্ডার রি-ডেলিভারি ──
    if data.startswith("pget:"):
        code = data.split(":", 1)[1]
        record = await get_partner_order_by_code(code)
        if not record or record["user_id"] != q.from_user.id:
            await q.message.reply_text("❌ এই অর্ডার আপনার নয়।")
            return WAITING_ACTION
        try:
            res = await papi.get_order(code)
        except PartnerAPIError as e:
            log.error("Partner get_order(%s) failed: code=%s req=%s msg=%s",
                      code, e.code, e.request_id, e.message)
            await _notify_admins_of_error(context, f"get_order:{code}", e)
            await q.message.reply_text(_friendly_error(e.code), parse_mode="HTML")
            return WAITING_ACTION
        chunks = _delivery_messages(res)
        if not chunks:
            await q.message.reply_text("ℹ️ এই অর্ডারে ডেলিভারি নেই।")
            return WAITING_ACTION
        await q.message.reply_text(
            f"🧾 <b>{code}</b> — {res.get('status', '?')}",
            parse_mode="HTML",
        )
        for ch in chunks:
            try:
                await q.message.reply_text(ch, parse_mode="HTML")
            except Exception:
                await q.message.reply_text(ch)
        return WAITING_ACTION

    return WAITING_ACTION


# ─────────────────────────────────────────────────────
#  STATE: WAITING_ACTION → WAITING_QTY (product chosen)
# ─────────────────────────────────────────────────────
async def partner_product_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    slug = q.data.split(":", 1)[1]

    cache_key = f"partner:product:{slug}"
    p = get_cache(cache_key)
    if not p:
        try:
            p = await papi.product(slug)
            set_cache(cache_key, p, PARTNER_CACHE_TTL)
        except PartnerAPIError as e:
            log.error("Partner product(%s) failed: code=%s req=%s msg=%s",
                      slug, e.code, e.request_id, e.message)
            await _notify_admins_of_error(context, f"product:{slug}", e)
            await q.message.reply_text(_friendly_error(e.code), parse_mode="HTML")
            return WAITING_ACTION

    stock = p.get("stock") or {}
    if not stock.get("inStock"):
        await q.message.reply_text("❌ স্টকে নেই।")
        return WAITING_ACTION

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
    text += (
        f"\nকত পিস নিতে চান? (1–{stock.get('maxQuantity', 1)})\n"
        f"শুধু সংখ্যাটি পাঠান। বাতিল করতে <code>/cancel</code>।"
    )

    await q.message.reply_text(text, parse_mode="HTML")

    context.user_data["partner_pending"] = {
        "slug": slug,
        "name": p.get("name", slug),
        "delivery_type": dtype,
        "unit_price": float(p.get("yourPrice") or 0),
        "max_qty": int(stock.get("maxQuantity") or 1),
    }
    return WAITING_QTY


# ─────────────────────────────────────────────────────
#  STATE: WAITING_QTY — order execution
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

    # API ব্যালেন্স প্রি-চেক (ইউজারকে দেখানো হয় না, শুধু যাচাই)
    try:
        await papi.balance()
    except PartnerAPIError as e:
        log.error("Partner balance precheck failed: code=%s req=%s msg=%s",
                  e.code, e.request_id, e.message)
        await _notify_admins_of_error(context, "balance_precheck", e)
        await update.message.reply_text(_friendly_error(e.code), parse_mode="HTML")
        context.user_data.pop("partner_pending", None)
        return ConversationHandler.END

    await update.message.reply_text("⏳ অর্ডার প্রসেস হচ্ছে...")

    ext_id = f"tg-{user_id}-{uuid.uuid4().hex[:12]}"

    try:
        res = await papi.create_order(data["slug"], qty, ext_id)
    except PartnerAPIError as e:
        log.error("Partner create_order failed user=%s code=%s req=%s msg=%s",
                  user_id, e.code, e.request_id, e.message)
        await _notify_admins_of_error(
            context,
            f"create_order:{data['slug']}",
            e,
        )
        await update.message.reply_text(_friendly_error(e.code), parse_mode="HTML")
        context.user_data.pop("partner_pending", None)
        return ConversationHandler.END

    # DB সেভ (delivery নয়, শুধু মেটাডেটা)
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

    # ── ইউজারের কাছে সাকসেস মেসেজ (API ব্যালেন্স হাইড) ──
    head = (
        f"✅ <b>অর্ডার সম্পন্ন</b>\n"
        f"🧾 <code>{res.get('orderCode', '')}</code>\n"
        f"💵 চার্জ: <b>${res.get('totalCharged', '?')}</b>"
    )
    await update.message.reply_text(head, parse_mode="HTML")

    for chunk in _delivery_messages(res):
        try:
            await update.message.reply_text(chunk, parse_mode="HTML")
        except Exception:
            await update.message.reply_text(chunk)

    # ── লগ বটে fire-and-forget (API ব্যালেন্স ছাড়া) ──
    try:
        import asyncio
        from utils.order_logger import send_partner_order_log
        asyncio.create_task(send_partner_order_log(
            order_code=res.get("orderCode", ""),
            user_id=user_id,
            product_name=data["name"],
            delivery_type=data["delivery_type"],
            quantity=qty,
            unit_price=float(res.get("unitPrice") or data["unit_price"]),
            total_charged=float(res.get("totalCharged") or data["unit_price"] * qty),
            status=res.get("status", "COMPLETED"),
        ))
    except Exception as e:
        log.warning("Partner log dispatch failed: %s", e)

    context.user_data.pop("partner_pending", None)
    return ConversationHandler.END


async def partner_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("partner_pending", None)
    await update.effective_message.reply_text(
        "❌ বাতিল করা হলো।", reply_markup=main_keyboard()
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────────────
#  STANDALONE — MY PARTNER ORDERS
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
#  ADMIN STATS  (API ব্যালেন্স হাইড)
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
            f"24h অর্ডার: {u.get('apiOrders24h')}\n"
            f"24h খরচ: ${u.get('apiSpend24h')}\n"
            f"আজ রিকোয়েস্ট: {u.get('requestCountToday')}\n"
            f"আজ এরর: {u.get('errorCountToday')}"
        )
    except PartnerAPIError as e:
        api_info = f"\n\n⚠️ API: <code>{e.code}</code>"

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
#  STARTUP RECONCILE
# ─────────────────────────────────────────────────────
async def reconcile_partner_orders(application):
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
#  CONVERSATION FACTORY
# ─────────────────────────────────────────────────────
PARTNER_CANCEL = filters.Regex(r"^(❌ ᴄᴀɴᴄᴇʟ|❌ Cancel|/cancel)$")


def build_partner_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("partner", partner_entry),
            MessageHandler(filters.Regex(r"^🛍 ᴘᴀʀᴛɴᴇʀ ꜱʜᴏᴘ$"), partner_entry),
            MessageHandler(filters.Regex(r"^🛍 ᴘᴀʀᴛɴᴇʀ ᴏʀᴅᴇʀ$"), partner_entry),
        ],
        states={
            WAITING_ACTION: [
                CallbackQueryHandler(
                    partner_action,
                    pattern=r"^(pcat$|pprov:.+|pget:.+)",
                ),
                CallbackQueryHandler(
                    partner_product_selected,
                    pattern=r"^pprod:.+",
                ),
            ],
            WAITING_QTY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~PARTNER_CANCEL,
                    partner_qty,
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", partner_cancel),
            MessageHandler(PARTNER_CANCEL, partner_cancel),
        ],
        allow_reentry=True,
        per_message=False,
        conversation_timeout=300,
    )