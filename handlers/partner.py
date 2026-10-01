"""
Partner API — Instant Delivery Shop
ক্যাটালগ, কেনা, ডেলিভারি, অর্ডার হিস্ট্রি, রিকভারি।
"""
import json
import uuid
import logging
from html import escape

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from api import partner_api as papi
from api.partner_api import PartnerAPIError
from config import PARTNER_ENABLED, PARTNER_DELIVERY_ICONS, MAX_ORDERS_PER_DAY
from database import (
    create_partner_order, get_user_partner_orders,
    get_partner_order_by_code, user_partner_orders_today,
    update_partner_order_status,
)
from utils.partner_cache import get_cache, set_cache
from utils.partner_cache import invalidate as cache_invalidate
from config import PARTNER_CACHE_TTL

log = logging.getLogger(__name__)
router = Router()


class PartnerSG(StatesGroup):
    waiting_qty = State()


# ─────────────────────────────────────────────────────
#  KBD HELPERS
# ─────────────────────────────────────────────────────
def _providers_kb(providers: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for p in providers:
        emoji = (p.get("emoji") or {}).get("normal") or "📦"
        rows.append([InlineKeyboardButton(
            text=f"{emoji} {p['name']}",
            callback_data=f"pprov:{p['key']}:1",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
        nav.append(InlineKeyboardButton(
            text="⬅️", callback_data=f"pprov:{provider_key}:{page-1}"
        ))
    if start + per_page < len(products):
        nav.append(InlineKeyboardButton(
            text="➡️", callback_data=f"pprov:{provider_key}:{page+1}"
        ))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔙 Categories", callback_data="pcat")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _delivery_text(res: dict) -> list[str]:
    """ডেলিভারি মেসেজ তৈরি। delivery.content কখনো log-এ যাবে না।"""
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

    # বাল্ক → lines[]
    for ln in res.get("lines", []) or []:
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
@router.message(Command("partner"))
@router.message(F.text == "🛍 Partner Shop")
async def cmd_partner(m: types.Message, state: FSMContext):
    if not PARTNER_ENABLED:
        return await m.answer("⚠️ Partner Shop এখন নিষ্ক্রিয়।")
    await state.clear()

    cached = get_cache("partner:providers")
    if cached:
        providers = cached
    else:
        try:
            providers = await papi.providers()
            set_cache("partner:providers", providers, PARTNER_CACHE_TTL)
        except PartnerAPIError as e:
            return await m.answer(f"❌ {e.code}: {e.message}")

    if not providers:
        return await m.answer("এই মুহূর্তে কোনো ক্যাটাগরি নেই।")

    await m.answer(
        "🛍 <b>Instant Delivery Shop</b>\n\nএকটি ক্যাটাগরি বেছে নিন:",
        reply_markup=_providers_kb(providers),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "pcat")
async def cb_categories(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    cached = get_cache("partner:providers")
    if not cached:
        try:
            cached = await papi.providers()
            set_cache("partner:providers", cached, PARTNER_CACHE_TTL)
        except PartnerAPIError as e:
            return await cb.answer(f"{e.code}", show_alert=True)

    await cb.message.edit_text(
        "🛍 <b>Instant Delivery Shop</b>\n\nএকটি ক্যাটাগরি বেছে নিন:",
        reply_markup=_providers_kb(cached),
        parse_mode="HTML",
    )
    await cb.answer()


# ─────────────────────────────────────────────────────
#  PROVIDER → PRODUCTS
# ─────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("pprov:"))
async def cb_provider(cb: types.CallbackQuery):
    _, key, page = cb.data.split(":")
    page = int(page)

    cache_key = f"partner:products:{key}"
    products = get_cache(cache_key)
    if not products:
        try:
            products = await papi.products(provider=key)
            set_cache(cache_key, products, PARTNER_CACHE_TTL)
        except PartnerAPIError as e:
            return await cb.answer(f"{e.code}: {e.message}", show_alert=True)

    if not products:
        return await cb.answer("এই ক্যাটাগরিতে কোনো পণ্য নেই।", show_alert=True)

    title = f"📦 <b>{key.title()} — Products</b>\nপৃষ্ঠা {page}"
    try:
        await cb.message.edit_text(
            title,
            reply_markup=_products_kb(products, key, page),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


# ─────────────────────────────────────────────────────
#  PRODUCT DETAIL
# ─────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("pprod:"))
async def cb_product(cb: types.CallbackQuery, state: FSMContext):
    slug = cb.data.split(":", 1)[1]

    cache_key = f"partner:product:{slug}"
    p = get_cache(cache_key)
    if not p:
        try:
            p = await papi.product(slug)
            set_cache(cache_key, p, PARTNER_CACHE_TTL)
        except PartnerAPIError as e:
            return await cb.answer(f"{e.code}: {e.message}", show_alert=True)

    stock = p.get("stock") or {}
    if not stock.get("inStock"):
        return await cb.answer("❌ স্টকে নেই", show_alert=True)

    dtype = p.get("deliveryType", "LINK")
    icon  = PARTNER_DELIVERY_ICONS.get(dtype, "📦")

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
    text += f"\nকত পিস নিতে চান? (1–{stock.get('maxQuantity', 1)})\n" \
            f"নিচে শুধু সংখ্যাটি পাঠান।"

    await cb.message.answer(text, parse_mode="HTML")

    await state.set_state(PartnerSG.waiting_qty)
    await state.update_data(
        slug=slug,
        name=p.get("name", slug),
        delivery_type=dtype,
        unit_price=float(p.get("yourPrice") or 0),
        max_qty=int(stock.get("maxQuantity") or 1),
    )
    await cb.answer()


# ─────────────────────────────────────────────────────
#  QUANTITY → ORDER
# ─────────────────────────────────────────────────────
@router.message(PartnerSG.waiting_qty)
async def do_order(m: types.Message, state: FSMContext):
    data = await state.get_data()
    slug   = data.get("slug")
    name   = data.get("name", slug)
    dtype  = data.get("delivery_type", "LINK")
    price  = data.get("unit_price", 0.0)
    maxq   = data.get("max_qty", 1)

    try:
        qty = int(m.text.strip())
        if qty < 1 or qty > maxq:
            raise ValueError
    except Exception:
        return await m.answer(f"❌ 1 থেকে {maxq} এর মধ্যে সংখ্যা পাঠান।")

    # ডেইলি লিমিট
    used = await user_partner_orders_today(m.from_user.id)
    if used >= MAX_ORDERS_PER_DAY:
        await state.clear()
        return await m.answer(
            f"⛔ আজকের অর্ডার লিমিট শেষ ({MAX_ORDERS_PER_DAY})।"
        )

    # ব্যালেন্স প্রি-চেক (ইউজার-সাইড কয়েন নয়, API-সাইড USD)
    try:
        bal = await papi.balance()
    except PartnerAPIError as e:
        await state.clear()
        return await m.answer(f"❌ {e.code}: {e.message}")

    await m.answer("⏳ অর্ডার প্রসেস হচ্ছে...")

    ext_id = f"tg-{m.from_user.id}-{uuid.uuid4().hex[:12]}"

    try:
        res = await papi.create_order(slug, qty, ext_id)
    except PartnerAPIError as e:
        msg = f"❌ <b>{e.code}</b>\n{escape(e.message)}"
        if e.code == "INSUFFICIENT_BALANCE":
            req = e.extra.get("required")
            have = e.extra.get("balance")
            msg += f"\n\nদরকার: <b>${req}</b>\nআছে: <b>${have}</b>"
        if e.request_id:
            msg += f"\n<code>reqId: {e.request_id}</code>"
        log.error("Partner order failed user=%s code=%s req=%s",
                  m.from_user.id, e.code, e.request_id)
        await state.clear()
        return await m.answer(msg, parse_mode="HTML")

    # DB-তে সেভ (ডেলিভারি নয় — শুধু মেটাডেটা)
    lines_meta = json.dumps(
        [{"orderCode": ln.get("orderCode")} for ln in res.get("lines", []) or []]
    ) if res.get("lines") else None

    await create_partner_order(
        user_id=m.from_user.id,
        external_id=ext_id,
        order_code=res.get("orderCode", ""),
        product_slug=slug,
        product_name=name,
        delivery_type=dtype,
        quantity=qty,
        unit_price=float(res.get("unitPrice") or price),
        total_charged=float(res.get("totalCharged") or price * qty),
        status=res.get("status", "COMPLETED"),
        lines_json=lines_meta,
    )

    # ইনভেন্টরি ক্যাশ ক্লিয়ার
    cache_invalidate("partner:product:")
    cache_invalidate("partner:products:")

    # হেডার মেসেজ
    head = (
        f"✅ <b>অর্ডার সম্পন্ন</b>\n"
        f"🧾 <code>{res.get('orderCode', '')}</code>\n"
        f"💵 চার্জ: <b>${res.get('totalCharged', '?')}</b>"
    )
    if res.get("balanceAfter"):
        head += f"\n💰 API ব্যালেন্স: <b>${res['balanceAfter']}</b>"
    await m.answer(head, parse_mode="HTML")

    # ডেলিভারি (sensitive content এখানে সরাসরি ইউজারকে)
    for chunk in _delivery_text(res):
        try:
            await m.answer(chunk, parse_mode="HTML")
        except Exception:
            await m.answer(chunk)

    await state.clear()


# ─────────────────────────────────────────────────────
#  MY ORDERS
# ─────────────────────────────────────────────────────
@router.message(Command("myorders"))
async def my_orders(m: types.Message):
    orders = await get_user_partner_orders(m.from_user.id, limit=10)
    if not orders:
        return await m.answer("📭 আপনার কোনো Partner অর্ডার নেই।")

    rows = []
    lines = ["📦 <b>সর্বশেষ Partner অর্ডার:</b>\n"]
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

    await m.answer("\n".join(lines),
                   reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
                   parse_mode="HTML")


@router.callback_query(F.data.startswith("pget:"))
async def cb_get_order(cb: types.CallbackQuery):
    code = cb.data.split(":", 1)[1]

    # ownership চেক
    record = await get_partner_order_by_code(code)
    if not record or record["user_id"] != cb.from_user.id:
        return await cb.answer("❌ এই অর্ডার আপনার নয়।", show_alert=True)

    try:
        res = await papi.get_order(code)
    except PartnerAPIError as e:
        return await cb.answer(f"{e.code}: {e.message}", show_alert=True)

    chunks = _delivery_text(res)
    if not chunks:
        return await cb.answer("ℹ️ এই অর্ডারে ডেলিভারি নেই।", show_alert=True)

    await cb.message.answer(
        f"🧾 <b>{code}</b> — {res.get('status', '?')}",
        parse_mode="HTML",
    )
    for chunk in chunks:
        try:
            await cb.message.answer(chunk, parse_mode="HTML")
        except Exception:
            await cb.message.answer(chunk)
    await cb.answer("পাঠানো হলো ✅")


# ─────────────────────────────────────────────────────
#  ADMIN STATS
# ─────────────────────────────────────────────────────
from config import ADMIN_IDS  # noqa: E402


@router.message(Command("partnerstats"))
async def cmd_stats(m: types.Message):
    if m.from_user.id not in ADMIN_IDS:
        return

    from database import get_partner_stats
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

    await m.answer(
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
async def reconcile_partner_orders(bot):
    """যেসব অর্ডার COMPLETED নয় — API থেকে সত্যি অবস্থা জেনে ইউজারকে ডেলিভারি।"""
    from database import get_unrecovered_partner_orders
    pending = await get_unrecovered_partner_orders()
    if not pending:
        return

    log.info("Reconciling %d partner orders...", len(pending))
    for o in pending:
        code = o.get("order_code")
        if not code:
            continue
        try:
            res = await papi.get_order(code)
        except PartnerAPIError as e:
            log.warning("Reconcile %s failed: %s", code, e.code)
            continue

        await update_partner_order_status(
            code, res.get("status", "COMPLETED"), recovered=1
        )

        chunks = _delivery_text(res)
        if not chunks:
            continue

        try:
            await bot.send_message(
                o["user_id"],
                f"🔄 <b>পুনরুদ্ধার করা অর্ডার</b>\n"
                f"🧾 <code>{code}</code>",
                parse_mode="HTML",
            )
            for chunk in chunks:
                try:
                    await bot.send_message(o["user_id"], chunk, parse_mode="HTML")
                except Exception:
                    await bot.send_message(o["user_id"], chunk)
        except Exception as e:
            log.warning("Could not notify user %s: %s", o["user_id"], e)