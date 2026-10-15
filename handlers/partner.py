"""
Partner API (Instant Delivery) — python-telegram-bot v20+
LINK / COUPON / READY_ACCOUNT

Features:
   ✔ Inline quantity buttons (1/2/3/5/10 + Custom)
   ✔ Confirm screen
   ✔ Search across all providers
   ✔ Refresh from live API
   ✔ Back navigation
   ✔ Stock Alert (subscribe + auto notify)
   ✔ Price History (sparkline trend)
   ✔ Related Products (same category)
   ✔ Smart stock label (✅ 48 | ✅ 1.2k | 🟡 5 left | ⚠️ মাত্র 3 | ❌ শেষ)
   ✔ Brand emoji mapping (auto-detect from product name/key)
   ✔ Colored buttons — 🟢 success (in stock) | 🔴 danger (out of stock)
   ✔ API HTML cleaner (<tg-emoji> → unicode, <blockquote> preserved)
   ✔ DUAL BALANCE CHECK — bot wallet + API balance

⚠️ Security:
   - delivery.link / code / content কখনো log/DB-তে যায় না
   - API ব্যালেন্স, error code, reqId ইউজারকে দেখানো হয় না
   - সব internal detail শুধু অ্যাডমিন PM-এ
"""
import uuid
import json
import logging
import re
from html import escape
from typing import Optional

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram._utils.types import JSONDict
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
    add_stock_alert, remove_stock_alert, has_stock_alert,
    get_pending_stock_alerts, mark_alert_notified, get_user_alerts,
    record_price, get_price_history,
    # ── Dual balance support ──
    get_user, deduct_balance, add_balance,
)
from keyboards.reply import main_keyboard
from utils.partner_cache import get_cache, set_cache, invalidate as cache_invalidate

log = logging.getLogger(__name__)

# ── States ──
WAITING_ACTION      = 1
WAITING_CUSTOM_QTY  = 2
WAITING_SEARCH      = 3


# ─────────────────────────────────────────────────────
#  STYLE CONSTANTS  (Bot API 9.4)
# ─────────────────────────────────────────────────────
STYLE_PRIMARY = "primary"
STYLE_SUCCESS = "success"
STYLE_DANGER  = "danger"


# ─────────────────────────────────────────────────────
#  STYLED BUTTON  (custom emoji + style support)
# ─────────────────────────────────────────────────────
class StyledButton(InlineKeyboardButton):
    """InlineKeyboardButton with optional `style` and `icon_custom_emoji_id`."""

    __slots__ = ("_style", "_icon_custom_emoji_id")

    def __init__(
        self,
        text: str,
        style: Optional[str] = None,
        icon_custom_emoji_id: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(text=text, **kwargs)
        object.__setattr__(self, "_style", style)
        object.__setattr__(self, "_icon_custom_emoji_id", icon_custom_emoji_id)

    def to_dict(self, recursive: bool = True) -> JSONDict:
        data = super().to_dict(recursive=recursive)
        if self._style:
            data["style"] = self._style
        if self._icon_custom_emoji_id:
            data["icon_custom_emoji_id"] = self._icon_custom_emoji_id
        return data


def _btn(
    text: str,
    callback_data: str,
    style: str | None = None,
    icon_custom_emoji_id: str | None = None,
) -> StyledButton:
    """Styled inline button helper."""
    return StyledButton(
        text=text,
        callback_data=callback_data,
        style=style,
        icon_custom_emoji_id=icon_custom_emoji_id,
    )


# ─────────────────────────────────────────────────────
#  FRIENDLY ERROR MAP
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

_BACK_TEXTS = {
    "back", "🔙 back", "⬅️ back", "⬅ back", "« back",
    "❌ cancel", "❌ ᴄᴀɴᴄᴇʟ", "cancel", "/cancel",
}


def _friendly_error(code: str) -> str:
    return _FRIENDLY_ERRORS.get(code, _GENERIC_ERROR)


def _is_back_or_cancel(text: str) -> bool:
    return (text or "").strip().lower() in _BACK_TEXTS


async def _notify_admins_of_error(context, where: str, e: PartnerAPIError):
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
#  API HTML CLEANER
# ─────────────────────────────────────────────────────
_TG_EMOJI_RE = re.compile(
    r'<tg-emoji[^>]*>(.*?)</tg-emoji>',
    re.DOTALL | re.IGNORECASE,
)
_MULTI_NL_RE = re.compile(r'\n{3,}')


def _clean_api_html(raw: str) -> str:
    """
    Partner API-র description/instructions পরিষ্কার করে।
    """
    if not raw:
        return ""
    cleaned = _TG_EMOJI_RE.sub(r'\1', raw)
    cleaned = _MULTI_NL_RE.sub('\n\n', cleaned)
    return cleaned.strip()


# ─────────────────────────────────────────────────────
#  PROVIDER EMOJI MAP
# ─────────────────────────────────────────────────────
_PROVIDER_EMOJI = [
    ("gemini",       "✦"),
    ("google ai",    "✦"),
    ("official",     "֎"),
    ("portal",       "֎"),
    ("chatgpt",      "⚡"),
    ("openai",       "⚡"),
    ("gpt",          "⚡"),
    ("claude",       "🧠"),
    ("anthropic",    "🧠"),
    ("grok",         "🤖"),
    ("copilot",      "🧩"),
    ("perplexity",   "🔎"),
    ("mistral",      "🌪"),
    ("llama",        "🦙"),
    ("cursor",       "🖱"),
    ("manus",        "🤖"),
    ("wiktor",       "🤖"),
    ("leonardo",     "🎨"),
    ("midjourney",   "🎨"),
    ("dalle",        "🎨"),
    ("dall-e",       "🎨"),
    ("stable diffusion", "🎨"),
    ("elevenlabs",   "🎙"),
    ("eleven labs",  "🎙"),
    ("whisper",      "🎙"),
    ("wisper",       "🎙"),
    ("heygen",       "🎬"),
    ("sora",         "🎬"),
    ("netflix",      "🎬"),
    ("prime video",  "🎬"),
    ("primevideo",   "🎬"),
    ("disney",       "🏰"),
    ("hulu",         "📺"),
    ("hbo",          "🐉"),
    ("crunchyroll",  "🍿"),
    ("youtube",      "▶️"),
    ("spotify",      "🎵"),
    ("apple music",  "🎵"),
    ("deezer",       "🎵"),
    ("soundcloud",   "🎵"),
    ("telegram",     "✈️"),
    ("instagram",    "📸"),
    ("tiktok",       "🎵"),
    ("facebook",     "📘"),
    ("twitter",      "🐦"),
    ("linkedin",     "💼"),
    ("reddit",       "👽"),
    ("discord",      "🎮"),
    ("snapchat",     "👻"),
    ("pinterest",    "📌"),
    ("canva",        "🎨"),
    ("figma",        "🎨"),
    ("adobe",        "🅰"),
    ("photoshop",    "🖼"),
    ("illustrator",  "🖌"),
    ("premiere",     "🎬"),
    ("after effects","🎞"),
    ("capcut",       "✂️"),
    ("filmora",      "🎞"),
    ("davinci",      "🎞"),
    ("sketch",       "✏️"),
    ("notion",       "📝"),
    ("evernote",     "📓"),
    ("obsidian",     "🗒"),
    ("microsoft",    "🪟"),
    ("office",       "📊"),
    ("word",         "📄"),
    ("excel",        "📊"),
    ("powerpoint",   "📽"),
    ("google",       "🔍"),
    ("dropbox",      "📦"),
    ("drive",        "☁️"),
    ("slack",        "💬"),
    ("zoom",         "📹"),
    ("trello",       "📋"),
    ("asana",        "✅"),
    ("clickup",      "🖱"),
    ("duolingo",     "🦉"),
    ("coursera",     "🎓"),
    ("udemy",        "🎓"),
    ("udacity",      "🎓"),
    ("edx",          "🎓"),
    ("skillshare",   "🎓"),
    ("khan",         "🎓"),
    ("vpn",          "🔒"),
    ("nordvpn",      "🛡"),
    ("expressvpn",   "🛡"),
    ("surfshark",    "🦈"),
    ("ilovepdf",     "📄"),
    ("smallpdf",     "📄"),
    ("pdf",          "📄"),
    ("grammarly",    "✏️"),
    ("quillbot",     "✍️"),
    ("notion ai",    "✨"),
    ("mails",        "📧"),
    ("gmail",        "📧"),
    ("outlook",      "📧"),
    ("bolt",         "⚡"),
    ("hosting",      "🌐"),
    ("website",      "🌐"),
    ("domain",       "🌐"),
    ("seo",          "📈"),
    ("semrush",      "📈"),
    ("ahrefs",       "📈"),
    ("subscription", "⭐"),
    ("premium",      "💎"),
    ("bundle",       "🎁"),
]


def _provider_emoji(key: str, name: str, api_emoji: str | None) -> str:
    if api_emoji and api_emoji not in ("📦", "❓", "?", "", None):
        return api_emoji
    hay = f"{key or ''} {name or ''}".lower()
    for kw, emoji in _PROVIDER_EMOJI:
        if kw in hay:
            return emoji
    return "🛍"


# ─────────────────────────────────────────────────────
#  SMART STOCK FORMATTER
# ─────────────────────────────────────────────────────
def _stock_label(stock: int) -> tuple[str, str]:
    try:
        s = int(stock)
    except Exception:
        s = 0

    if s <= 0:
        return ("❌", "শেষ")
    if s <= 4:
        return ("⚠️", f"মাত্র {s}")
    if s <= 9:
        return ("🟡", f"{s} left")
    if s < 1000:
        return ("✅", str(s))
    if s < 10000:
        val = s / 1000
        if val == int(val):
            return ("✅", f"{int(val)}k")
        return ("✅", f"{val:.1f}k")
    if s < 100000:
        return ("✅", f"{s // 1000}k")
    return ("✅", "999k+")


def _stock_style(stock: int) -> str:
    if stock <= 0:
        return STYLE_DANGER
    return STYLE_SUCCESS


# ─────────────────────────────────────────────────────
#  SPARKLINE + TREND HELPERS
# ─────────────────────────────────────────────────────
def _sparkline(values: list[float]) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        return "▄" * len(values)
    bars = "▁▂▃▄▅▆▇█"
    out = []
    for v in values:
        idx = int((v - lo) / (hi - lo) * (len(bars) - 1))
        out.append(bars[idx])
    return "".join(out)


def _price_trend(history: list[dict]) -> str:
    if not history:
        return ""
    prices = [h["price"] for h in history]
    if len(prices) < 2:
        return ""

    current = prices[-1]
    first   = prices[0]
    lo      = min(prices)
    hi      = max(prices)
    diff    = current - first
    pct     = (diff / first * 100) if first else 0

    if diff > 0:
        arrow = f"🔺 +{pct:.1f}%"
    elif diff < 0:
        arrow = f"🔻 {pct:.1f}%"
    else:
        arrow = "➖ অপরিবর্তিত"

    spark = _sparkline(prices[-15:])
    return (
        f"\n📈 <b>দামের ট্রেন্ড</b>\n"
        f"<code>{spark}</code>\n"
        f"সর্বনিম্ন: ${lo:.2f} | সর্বোচ্চ: ${hi:.2f}\n"
        f"শেষ পরিবর্তন: {arrow}"
    )


async def _related_products_kb(slug: str, provider_key: str | None,
                               current_slug: str,
                               limit: int = 4) -> InlineKeyboardMarkup | None:
    if not provider_key:
        return None
    products = get_cache(f"partner:products:{provider_key}")
    if not products:
        return None

    rows = []
    for p in products:
        if p.get("slug") == current_slug:
            continue
        stock  = (p.get("stock") or {}).get("count", 0)
        price  = p.get("yourPrice", "?")
        name   = p["name"]
        if len(name) > 28:
            name = name[:27] + "…"

        api_emoji = (p.get("emoji") or {}).get("normal")
        p_emoji = _provider_emoji(p.get("slug", ""), name, api_emoji)

        _s_icon, stock_str = _stock_label(stock)
        style = _stock_style(stock)

        rows.append([_btn(
            f"{p_emoji} {name} — ${price} | {stock_str}",
            f"pprod:{p['slug']}",
            style,
        )])
        if len(rows) >= limit:
            break
    return InlineKeyboardMarkup(rows) if rows else None


# ─────────────────────────────────────────────────────
#  KEYBOARD BUILDERS
# ─────────────────────────────────────────────────────
def _trim(text: str, limit: int = 16) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _providers_kb(providers: list[dict]) -> InlineKeyboardMarkup:
    rows, row = [], []
    for p in providers:
        api_emoji = (p.get("emoji") or {}).get("normal")
        emoji = _provider_emoji(p.get("key", ""), p.get("name", ""), api_emoji)

        row.append(_btn(
            f"{emoji} {_trim(p['name'], 14)}",
            f"pprov:{p['key']}:1",
            STYLE_SUCCESS,
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([
        _btn("🔍 Search",  "psearch",           STYLE_PRIMARY),
        _btn("🔄 Refresh", "prefresh:_all:1",   STYLE_PRIMARY),
    ])
    return InlineKeyboardMarkup(rows)


def _products_kb(products, provider_key, page, per_page=8) -> InlineKeyboardMarkup:
    start = (page - 1) * per_page
    chunk = products[start:start + per_page]
    rows = []

    for p in chunk:
        stock = (p.get("stock") or {}).get("count", 0)
        price = p.get("yourPrice", "?")
        name  = p["name"]
        if len(name) > 38:
            name = name[:37] + "…"

        api_emoji = (p.get("emoji") or {}).get("normal")
        p_emoji = _provider_emoji(p.get("slug", ""), name, api_emoji)

        _s_icon, stock_str = _stock_label(stock)
        style = _stock_style(stock)

        label = f"{p_emoji} {name} — ${price} | {stock_str}"
        rows.append([_btn(label, f"pprod:{p['slug']}", style)])

    nav = []
    if page > 1:
        nav.append(_btn("⬅️", f"pprov:{provider_key}:{page-1}", STYLE_PRIMARY))
    if start + per_page < len(products):
        nav.append(_btn("➡️", f"pprov:{provider_key}:{page+1}", STYLE_PRIMARY))
    if nav:
        rows.append(nav)

    rows.append([
        _btn("🔄 Refresh",     f"prefresh:{provider_key}:{page}", STYLE_PRIMARY),
        _btn("🔙 Categories",  "pcat",                            STYLE_DANGER),
    ])
    return InlineKeyboardMarkup(rows)


def _confirm_kb(slug: str, qty: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("✅ Confirm",     f"pconfirm:{slug}:{qty}", STYLE_SUCCESS)],
        [_btn("✏️ Change qty",  f"pcustom:{slug}",         STYLE_PRIMARY)],
        [_btn("❌ Cancel",      f"pback:{slug}",           STYLE_DANGER)],
    ])


def _delivery_messages(res: dict) -> list[str]:
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
        out.append(f"ℹ️ {_clean_api_html(d['instructions'])}")
    return out


# ─────────────────────────────────────────────────────
#  ENTRY
# ─────────────────────────────────────────────────────
async def partner_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not PARTNER_ENABLED:
        await update.effective_message.reply_text("⚠️ Partner Shop এখন নিষ্ক্রিয়।")
        return ConversationHandler.END

    context.user_data.pop("partner_pending", None)
    context.user_data.pop("partner_search_results", None)

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
        "🛍 <b>Choose a service:</b>",
        reply_markup=_providers_kb(providers),
        parse_mode="HTML",
    )
    return WAITING_ACTION


# ─────────────────────────────────────────────────────
#  CALLBACK ROUTER — main navigation
# ─────────────────────────────────────────────────────
async def partner_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "pcat":
        context.user_data.pop("partner_pending", None)
        context.user_data.pop("partner_search_results", None)

        providers = get_cache("partner:providers")
        if not providers:
            try:
                providers = await papi.providers()
                set_cache("partner:providers", providers, PARTNER_CACHE_TTL)
            except PartnerAPIError as e:
                log.error("pcat providers failed: %s", e.code)
                await _notify_admins_of_error(context, "pcat_providers", e)
                await q.edit_message_text(_friendly_error(e.code))
                return WAITING_ACTION
        await q.edit_message_text(
            "🛍 <b>Choose a service:</b>",
            reply_markup=_providers_kb(providers),
            parse_mode="HTML",
        )
        return WAITING_ACTION

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
                log.error("products(%s): %s", key, e.code)
                await _notify_admins_of_error(context, f"products:{key}", e)
                await q.edit_message_text(_friendly_error(e.code))
                return WAITING_ACTION

        if not products:
            await q.edit_message_text("এই ক্যাটাগরিতে কোনো পণ্য নেই।")
            return WAITING_ACTION

        try:
            await q.edit_message_text(
                f"🛍 <b>{key.title()}</b>\n"
                f"নিচ থেকে একটি সার্ভিস বেছে নিন:",
                reply_markup=_products_kb(products, key, page),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return WAITING_ACTION

    if data.startswith("prefresh:"):
        _, key, page = data.split(":")
        page = int(page)

        if key == "_all":
            cache_invalidate("partner:providers")
            try:
                providers = await papi.providers()
                set_cache("partner:providers", providers, PARTNER_CACHE_TTL)
                await q.edit_message_text(
                    "🛍 <b>Choose a service:</b>",
                    reply_markup=_providers_kb(providers),
                    parse_mode="HTML",
                )
            except PartnerAPIError as e:
                await _notify_admins_of_error(context, "refresh_providers", e)
                await q.answer(_friendly_error(e.code), show_alert=True)
            return WAITING_ACTION

        cache_invalidate(f"partner:products:{key}")
        try:
            products = await papi.products(provider=key)
            set_cache(f"partner:products:{key}", products, PARTNER_CACHE_TTL)
            await q.edit_message_text(
                f"🛍 <b>{key.title()}</b>\n"
                f"নিচ থেকে একটি সার্ভিস বেছে নিন:",
                reply_markup=_products_kb(products, key, page),
                parse_mode="HTML",
            )
            await q.answer("✅ Refreshed")
        except PartnerAPIError as e:
            await _notify_admins_of_error(context, f"refresh_products:{key}", e)
            await q.answer(_friendly_error(e.code), show_alert=True)
        return WAITING_ACTION

    if data == "psearch":
        context.user_data.pop("partner_search_results", None)
        await q.message.reply_text(
            "🔍 <b>Search products</b>\n\n"
            "প্রোডাক্টের নামের কিছু অংশ লিখুন।\n"
            "বাতিল করতে /cancel।",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        return WAITING_SEARCH

    if data.startswith("pget:"):
        code = data.split(":", 1)[1]
        record = await get_partner_order_by_code(code)
        if not record or record["user_id"] != q.from_user.id:
            await q.message.reply_text("❌ এই অর্ডার আপনার নয়।")
            return WAITING_ACTION
        try:
            res = await papi.get_order(code)
        except PartnerAPIError as e:
            log.error("get_order(%s): %s", code, e.code)
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
#  PRODUCT DETAIL
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
            log.error("product(%s): %s", slug, e.code)
            await _notify_admins_of_error(context, f"product:{slug}", e)
            await q.message.reply_text(_friendly_error(e.code), parse_mode="HTML")
            return WAITING_ACTION

    stock = p.get("stock") or {}
    stock_count = stock.get("count", 0)
    in_stk = bool(stock.get("inStock"))
    max_qty = int(stock.get("maxQuantity") or 1)

    try:
        price = float(p.get("yourPrice") or 0)
        await record_price(slug, price, stock_count)
    except Exception as e:
        log.warning("record_price failed: %s", e)

    provider_key = None
    providers = get_cache("partner:providers") or []
    for prov in providers:
        prods = get_cache(f"partner:products:{prov['key']}") or []
        if any(x.get("slug") == slug for x in prods):
            provider_key = prov["key"]
            break

    dtype = p.get("deliveryType", "LINK")
    icon  = PARTNER_DELIVERY_ICONS.get(dtype, "📦")

    api_emoji = (p.get("emoji") or {}).get("normal")
    brand_emoji = _provider_emoji(slug, p.get("name", ""), api_emoji)

    s_icon, s_str = _stock_label(stock_count)

    text = (
        f"{brand_emoji} <b>{p.get('name', slug)}</b>\n\n"
        f"💵 <b>{p.get('yourPrice', '?')}</b> USD\n"
    )
    if p.get("durationDays"):
        text += f"⏱ Duration: <b>{p['durationDays']} days</b>\n"

    if in_stk:
        text += f"📦 স্টক: <b>{s_icon} {s_str}</b>\n"
    else:
        text += "📦 স্টক: <b>❌ শেষ</b>\n"

    text += f"{icon} ডেলিভারি: <b>{dtype}</b>\n"

    if (p.get("warranty") or {}).get("enabled"):
        text += f"🛡 ওয়ারেন্টি: {p['warranty']['days']} দিন\n"

    if p.get("description"):
        desc = _clean_api_html(p["description"])
        if desc:
            if len(desc) > 2000:
                desc = desc[:1997] + "…"
            text += f"\n{desc}\n"

    if p.get("instructions"):
        ins = _clean_api_html(p["instructions"])
        if ins:
            if len(ins) > 400:
                ins = ins[:397] + "…"
            text += f"\nℹ️ {ins}\n"

    try:
        history = await get_price_history(slug, limit=30)
        trend = _price_trend(history)
        if trend:
            text += trend
    except Exception as e:
        log.warning("price history failed: %s", e)

    related_kb = None
    try:
        related_kb = await _related_products_kb(slug, provider_key, slug, limit=4)
    except Exception as e:
        log.warning("related products failed: %s", e)

    rows = []

    if in_stk:
        quick = [1, 2, 3, 5, 10]
        row = []
        for n in quick:
            if n > max_qty:
                break
            row.append(_btn(f"{n} pcs", f"pqty:{slug}:{n}", STYLE_PRIMARY))
            if len(row) == 3:
                rows.append(row); row = []
        if row:
            rows.append(row)
        rows.append([
            _btn("✏️ Custom", f"pcustom:{slug}", STYLE_PRIMARY),
            _btn("🔙 Back",   f"pback:{slug}",   STYLE_DANGER),
        ])
        text += f"\n<b>পরিমাণ বেছে নিন</b> (1–{max_qty}):"
    else:
        already = await has_stock_alert(q.from_user.id, slug)
        if already:
            rows.append([_btn(
                "🔔 Alert চালু আছে — বন্ধ করুন",
                f"punalert:{slug}",
                STYLE_DANGER,
            )])
            text += "\n🔔 স্টক এলে আপনাকে জানানো হবে।"
        else:
            rows.append([_btn(
                "🔔 Stock এলে জানান",
                f"palert:{slug}",
                STYLE_SUCCESS,
            )])
            text += "\n🔔 স্টক এলে নোটিফিকেশন পেতে বাটনে ক্লিক করুন।"

        rows.append([_btn("🔙 Back", f"pback:{slug}", STYLE_DANGER)])

    if related_kb:
        text += "\n\n🔎 <b>একই ক্যাটাগরির আরো:</b>"
        rows.extend(related_kb.inline_keyboard)

    context.user_data["partner_pending"] = {
        "slug": slug,
        "name": p.get("name", slug),
        "delivery_type": dtype,
        "unit_price": float(p.get("yourPrice") or 0),
        "max_qty": max_qty,
        "provider_key": provider_key,
    }

    try:
        await q.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows),
        )
    except Exception:
        try:
            await q.message.reply_text(
                text[:4000],
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(rows),
            )
        except Exception:
            await q.message.reply_text(
                text[:4000],
                reply_markup=InlineKeyboardMarkup(rows),
            )
    return WAITING_ACTION


# ─────────────────────────────────────────────────────
#  QUANTITY — inline buttons
# ─────────────────────────────────────────────────────
async def partner_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, slug, qty_s = q.data.split(":")
    qty = int(qty_s)

    data = context.user_data.get("partner_pending") or {}
    if data.get("slug") != slug:
        try:
            p = await papi.product(slug)
        except PartnerAPIError as e:
            await q.message.reply_text(_friendly_error(e.code))
            return WAITING_ACTION
        data = {
            "slug": slug,
            "name": p.get("name", slug),
            "delivery_type": p.get("deliveryType", "LINK"),
            "unit_price": float(p.get("yourPrice") or 0),
            "max_qty": int((p.get("stock") or {}).get("maxQuantity") or 1),
        }
        context.user_data["partner_pending"] = data

    if qty < 1 or qty > data["max_qty"]:
        await q.answer(f"❌ 1 থেকে {data['max_qty']} এর মধ্যে দিন", show_alert=True)
        return WAITING_ACTION

    total = qty * data["unit_price"]
    text = (
        f"🧾 <b>অর্ডার কনফার্ম করুন</b>\n\n"
        f"📦 <b>{escape(data['name'])}</b>\n"
        f"🔢 পরিমাণ: <b>{qty}</b>\n"
        f"💵 দাম (প্রতি পিস): <b>${data['unit_price']:.2f}</b>\n"
        f"💰 মোট চার্জ: <b>${total:.2f}</b>\n\n"
        f"কনফার্ম করলে সাথে সাথেই ডেলিভারি পাবেন।"
    )
    try:
        await q.edit_message_text(
            text, parse_mode="HTML",
            reply_markup=_confirm_kb(slug, qty),
        )
    except Exception:
        await q.message.reply_text(
            text, parse_mode="HTML",
            reply_markup=_confirm_kb(slug, qty),
        )
    return WAITING_ACTION


# ─────────────────────────────────────────────────────
#  CUSTOM QUANTITY
# ─────────────────────────────────────────────────────
async def partner_custom_qty_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    slug = q.data.split(":", 1)[1]

    data = context.user_data.get("partner_pending") or {}
    max_qty = data.get("max_qty", 1)

    await q.message.reply_text(
        f"✏️ কত পিস চান? (1–{max_qty})\n"
        f"শুধু সংখ্যাটি পাঠান।\n"
        f"বাতিল করতে /cancel।",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    return WAITING_CUSTOM_QTY


async def partner_custom_qty_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data.get("partner_pending")
    if not data:
        return ConversationHandler.END

    raw = (update.message.text or "").strip()
    if _is_back_or_cancel(raw):
        return await partner_show_categories(update, context)

    try:
        qty = int(raw)
        if qty < 1 or qty > data["max_qty"]:
            raise ValueError
    except Exception:
        await update.message.reply_text(
            f"❌ 1 থেকে {data['max_qty']} এর মধ্যে সংখ্যা পাঠান।\n"
            f"বাতিল করতে /cancel।",
        )
        return WAITING_CUSTOM_QTY

    total = qty * data["unit_price"]
    await update.message.reply_text(
        f"🧾 <b>অর্ডার কনফার্ম করুন</b>\n\n"
        f"📦 <b>{escape(data['name'])}</b>\n"
        f"🔢 পরিমাণ: <b>{qty}</b>\n"
        f"💵 দাম (প্রতি পিস): <b>${data['unit_price']:.2f}</b>\n"
        f"💰 মোট চার্জ: <b>${total:.2f}</b>",
        parse_mode="HTML",
        reply_markup=_confirm_kb(data["slug"], qty),
    )
    return WAITING_ACTION


async def partner_show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("partner_pending", None)
    context.user_data.pop("partner_search_results", None)

    providers = get_cache("partner:providers")
    if not providers:
        try:
            providers = await papi.providers()
            set_cache("partner:providers", providers, PARTNER_CACHE_TTL)
        except PartnerAPIError as e:
            await _notify_admins_of_error(context, "show_categories", e)
            await update.effective_message.reply_text(_friendly_error(e.code))
            return ConversationHandler.END

    msg = update.effective_message
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                "🛍 <b>Choose a service:</b>",
                reply_markup=_providers_kb(providers),
                parse_mode="HTML",
            )
            return WAITING_ACTION
        except Exception:
            pass
    await msg.reply_text(
        "🛍 <b>Choose a service:</b>",
        reply_markup=_providers_kb(providers),
        parse_mode="HTML",
    )
    return WAITING_ACTION


# ─────────────────────────────────────────────────────
#  BACK
# ─────────────────────────────────────────────────────
async def partner_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    slug = q.data.split(":", 1)[1]

    providers = get_cache("partner:providers") or []
    found_key = None
    found_products = None
    found_page = 1

    for prov in providers:
        key = prov["key"]
        products = get_cache(f"partner:products:{key}")
        if not products:
            continue
        for i, prod in enumerate(products):
            if prod.get("slug") == slug:
                found_key = key
                found_products = products
                found_page = (i // 8) + 1
                break
        if found_key:
            break

    if not found_key:
        for prov in providers:
            key = prov["key"]
            try:
                products = await papi.products(provider=key)
                set_cache(f"partner:products:{key}", products, PARTNER_CACHE_TTL)
                for i, prod in enumerate(products):
                    if prod.get("slug") == slug:
                        found_key = key
                        found_products = products
                        found_page = (i // 8) + 1
                        break
                if found_key:
                    break
            except PartnerAPIError:
                continue

    if not found_key or not found_products:
        return await partner_show_categories(update, context)

    try:
        await q.edit_message_text(
            f"🛍 <b>{found_key.title()}</b>\n"
            f"নিচ থেকে একটি সার্ভিস বেছে নিন:",
            parse_mode="HTML",
            reply_markup=_products_kb(found_products, found_key, found_page),
        )
    except Exception:
        pass
    return WAITING_ACTION


# ─────────────────────────────────────────────────────
#  STOCK ALERT — ON / OFF / LIST
# ─────────────────────────────────────────────────────
async def partner_alert_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    slug = q.data.split(":", 1)[1]

    data = context.user_data.get("partner_pending") or {}
    name = data.get("name", slug)
    prov = data.get("provider_key")

    added = await add_stock_alert(q.from_user.id, slug, name, prov or "")
    if added:
        await q.answer("🔔 Stock alert চালু হয়েছে", show_alert=True)
    else:
        await q.answer("ℹ️ আগেই চালু আছে", show_alert=True)

    return await partner_product_selected(update, context)


async def partner_alert_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    slug = q.data.split(":", 1)[1]

    removed = await remove_stock_alert(q.from_user.id, slug)
    if removed:
        await q.answer("🔕 Stock alert বন্ধ হয়েছে", show_alert=True)
    else:
        await q.answer("ℹ️ চালু ছিল না", show_alert=True)

    return await partner_product_selected(update, context)


async def my_stock_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alerts = await get_user_alerts(update.effective_user.id)
    if not alerts:
        await update.message.reply_text("📭 আপনার কোনো Stock Alert নেই।")
        return

    lines = ["🔔 <b>আপনার Stock Alerts:</b>\n"]
    rows = []
    for i, a in enumerate(alerts[:15], 1):
        status = "✅ notified" if a["notified"] else "⏳ waiting"
        lines.append(f"{i}. {escape(a['product_name'] or a['product_slug'])} — {status}")
        rows.append([_btn(
            f"❌ Remove: {_trim(a['product_name'] or a['product_slug'], 22)}",
            f"punalert:{a['product_slug']}",
            STYLE_DANGER,
        )])

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="HTML",
    )


# ─────────────────────────────────────────────────────
#  STOCK CHECK JOB
# ─────────────────────────────────────────────────────
async def check_stock_alerts_job(application):
    pending = await get_pending_stock_alerts(limit=100)
    if not pending:
        return

    log.info("Checking %d stock alerts...", len(pending))
    bot = application.bot

    checked: dict[str, dict] = {}
    for a in pending:
        slug = a["product_slug"]
        if slug not in checked:
            try:
                p = await papi.product(slug)
                checked[slug] = p
                try:
                    await record_price(
                        slug,
                        float(p.get("yourPrice") or 0),
                        int((p.get("stock") or {}).get("count", 0)),
                    )
                except Exception:
                    pass
            except PartnerAPIError as e:
                log.warning("alert check %s: %s", slug, e.code)
                checked[slug] = {}

        p = checked[slug]
        stock = (p.get("stock") or {})
        if not stock.get("inStock") or stock.get("count", 0) <= 0:
            continue

        try:
            kb = InlineKeyboardMarkup([[
                _btn("🛒 এখনই কিনুন", f"pprod:{slug}", STYLE_SUCCESS)
            ]])
            await bot.send_message(
                a["user_id"],
                f"🔔 <b>স্টক এসেছে!</b>\n\n"
                f"📦 {escape(a['product_name'] or slug)}\n"
                f"💰 দাম: <b>${p.get('yourPrice', '?')}</b>\n"
                f"📊 স্টক: <b>{stock.get('count', 0)}</b>",
                parse_mode="HTML",
                reply_markup=kb,
            )
            await mark_alert_notified(a["id"])
        except Exception as e:
            log.warning("alert notify user=%s failed: %s", a["user_id"], e)


# ═════════════════════════════════════════════════════
#  CONFIRM + PLACE ORDER  —  DUAL BALANCE CHECK
# ═════════════════════════════════════════════════════
async def partner_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, slug, qty_s = q.data.split(":")
    qty = int(qty_s)

    data = context.user_data.get("partner_pending") or {}
    if data.get("slug") != slug:
        await q.answer("❌ সেশন শেষ। আবার শুরু করুন।", show_alert=True)
        return ConversationHandler.END

    user_id = q.from_user.id

    # ── ডেইলি লিমিট ──
    used = await user_partner_orders_today(user_id)
    if used >= MAX_ORDERS_PER_DAY:
        await q.message.reply_text(
            f"⛔ আজকের অর্ডার লিমিট শেষ ({MAX_ORDERS_PER_DAY})।",
            reply_markup=main_keyboard(),
        )
        context.user_data.pop("partner_pending", None)
        return ConversationHandler.END

    # ── প্রয়োজন কত ──
    unit_price = float(data["unit_price"])
    total_required = round(unit_price * qty, 2)

    # ══════════════════════════════════════════════════
    #  ১) ইউজারের BOT WALLET ব্যালেন্স চেক
    # ══════════════════════════════════════════════════
    udata = await get_user(user_id)
    if not udata:
        await q.message.reply_text("⚠️ অ্যাকাউন্ট পাওয়া যায়নি। /start দিন।")
        context.user_data.pop("partner_pending", None)
        return ConversationHandler.END

    bot_balance = float(udata.get("balance") or 0)

    if bot_balance < total_required:
        need = round(total_required - bot_balance, 2)
        await q.message.reply_text(
            f"❌ <b>পর্যাপ্ত ব্যালেন্স নেই</b>\n\n"
            f"💵 প্রয়োজন: <b>${total_required:.2f}</b>\n"
            f"💰 আপনার ব্যালেন্স: <b>${bot_balance:.2f}</b>\n"
            f"⚠️ আরও দরকার: <b>${need:.2f}</b>\n\n"
            f"💳 <b>Buy Coins</b> থেকে ব্যালেন্স বাড়ান।",
            parse_mode="HTML",
        )
        context.user_data.pop("partner_pending", None)
        return ConversationHandler.END

    # ══════════════════════════════════════════════════
    #  ২) API (GGSoma) ব্যালেন্স চেক — আসল মান
    # ══════════════════════════════════════════════════
    try:
        bal_resp = await papi.balance()
        api_balance = float(bal_resp.get("balance", 0) or 0)
        log.info(
            "Order precheck | user=%s bot=$%.2f api=$%.2f need=$%.2f",
            user_id, bot_balance, api_balance, total_required,
        )
    except PartnerAPIError as e:
        log.error("API balance check failed: code=%s req=%s", e.code, e.request_id)
        await _notify_admins_of_error(context, "balance_precheck", e)
        await q.message.reply_text(_friendly_error(e.code), parse_mode="HTML")
        context.user_data.pop("partner_pending", None)
        return ConversationHandler.END
    except (ValueError, TypeError) as e:
        log.error("API balance parse error: %s", e)
        await q.message.reply_text(
            "⚠️ সার্ভিসে সাময়িক সমস্যা। কিছুক্ষণ পরে আবার চেষ্টা করুন।",
            parse_mode="HTML",
        )
        context.user_data.pop("partner_pending", None)
        return ConversationHandler.END

    if api_balance < total_required:
        log.warning("Blocked: api=$%.2f < need=$%.2f", api_balance, total_required)

        await q.message.reply_text(
            f"❌ <b>সাময়িকভাবে অর্ডার নেওয়া যাচ্ছে না</b>\n\n"
            f"⏳ অনুগ্রহ করে কিছুক্ষণ পরে চেষ্টা করুন।\n"
            f"❓ সমস্যা থাকলে সাপোর্টে যোগাযোগ করুন।",
            parse_mode="HTML",
        )

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"⚠️ <b>Partner API ব্যালেন্স কম!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🛍 <code>{data['name']}</code>\n"
                    f"🔢 Qty: <code>{qty}</code>\n"
                    f"💵 প্রয়োজন: <code>${total_required:.2f}</code>\n"
                    f"💰 আছে: <code>${api_balance:.2f}</code>\n"
                    f"👤 ইউজার: <code>{user_id}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔴 API-তে টাকা রিচার্জ করুন!",
                    parse_mode="HTML",
                )
            except Exception:
                pass

        context.user_data.pop("partner_pending", None)
        return ConversationHandler.END

    # ══════════════════════════════════════════════════
    #  ৩) দুই balance ঠিক → bot wallet থেকে কাটো
    # ══════════════════════════════════════════════════
    deducted = await deduct_balance(
        user_id,
        total_required,
        description=f"Partner: {data['name']} x{qty}",
    )
    if not deducted:
        await q.message.reply_text(
            "❌ ব্যালেন্স কাটা যায়নি। আবার চেষ্টা করুন।",
            parse_mode="HTML",
        )
        context.user_data.pop("partner_pending", None)
        return ConversationHandler.END

    # ══════════════════════════════════════════════════
    #  ৪) এখন API-তে অর্ডার পাঠাও
    # ══════════════════════════════════════════════════
    await q.message.reply_text("⏳ অর্ডার প্রসেস হচ্ছে...")

    ext_id = f"tg-{user_id}-{uuid.uuid4().hex[:12]}"

    try:
        res = await papi.create_order(data["slug"], qty, ext_id)
    except PartnerAPIError as e:
        log.error("create_order user=%s code=%s req=%s",
                  user_id, e.code, e.request_id)

        # ── API অর্ডার ফেল → ইউজারের টাকা ফেরত ──
        try:
            await add_balance(
                user_id,
                total_required,
                description=f"Refund: {data['name']} x{qty}",
            )
            log.info("Refunded $%.2f to user %s", total_required, user_id)
        except Exception as ref_err:
            log.error("Refund failed for user %s: %s", user_id, ref_err)

        await _notify_admins_of_error(context, f"create_order:{data['slug']}", e)
        await q.message.reply_text(
            _friendly_error(e.code) + "\n\n💵 আপনার পেমেন্ট ফেরত দেওয়া হয়েছে।",
            parse_mode="HTML",
        )
        context.user_data.pop("partner_pending", None)
        return ConversationHandler.END

    # ── DB-তে সেভ ──
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
        unit_price=float(res.get("unitPrice") or unit_price),
        total_charged=float(res.get("totalCharged") or total_required),
        status=res.get("status", "COMPLETED"),
        lines_json=lines_meta,
    )

    cache_invalidate("partner:product:")
    cache_invalidate("partner:products:")

    head = (
        f"✅ <b>অর্ডার সম্পন্ন</b>\n"
        f"🧾 <code>{res.get('orderCode', '')}</code>\n"
        f"💵 চার্জ: <b>${res.get('totalCharged', total_required)}</b>"
    )
    await q.message.reply_text(head, parse_mode="HTML")

    for chunk in _delivery_messages(res):
        try:
            await q.message.reply_text(chunk, parse_mode="HTML")
        except Exception:
            await q.message.reply_text(chunk)

    try:
        import asyncio
        from utils.order_logger import send_partner_order_log
        asyncio.create_task(send_partner_order_log(
            order_code=res.get("orderCode", ""),
            user_id=user_id,
            product_name=data["name"],
            delivery_type=data["delivery_type"],
            quantity=qty,
            unit_price=float(res.get("unitPrice") or unit_price),
            total_charged=float(res.get("totalCharged") or total_required),
            status=res.get("status", "COMPLETED"),
        ))
    except Exception as e:
        log.warning("log dispatch failed: %s", e)

    context.user_data.pop("partner_pending", None)
    await q.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
    return ConversationHandler.END


# ─────────────────────────────────────────────────────
#  SEARCH
# ─────────────────────────────────────────────────────
async def partner_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = (update.message.text or "").strip()

    if _is_back_or_cancel(raw):
        return await partner_show_categories(update, context)

    if len(raw) < 2:
        await update.message.reply_text("❌ কমপক্ষে ২ অক্ষর লিখুন।")
        return WAITING_SEARCH

    needle = raw.lower()

    providers = get_cache("partner:providers") or []
    if not providers:
        try:
            providers = await papi.providers()
            set_cache("partner:providers", providers, PARTNER_CACHE_TTL)
        except PartnerAPIError as e:
            await _notify_admins_of_error(context, "search_providers", e)
            await update.message.reply_text(_friendly_error(e.code))
            return WAITING_SEARCH

    results = []
    for prov in providers:
        key = prov["key"]
        products = get_cache(f"partner:products:{key}")
        if not products:
            try:
                products = await papi.products(provider=key)
                set_cache(f"partner:products:{key}", products, PARTNER_CACHE_TTL)
            except PartnerAPIError:
                continue
        for p in products:
            name = (p.get("name") or "").lower()
            slug = (p.get("slug") or "").lower()
            code = (p.get("productCode") or "").lower()
            if needle in name or needle in slug or needle in code:
                results.append((key, p))

    if not results:
        await update.message.reply_text(
            f"🔍 <b>'{escape(raw)}'</b> — কোনো প্রোডাক্ট পাওয়া যায়নি।\n"
            f"আবার চেষ্টা করুন বা /cancel দিয়ে ফিরে যান।",
            parse_mode="HTML",
        )
        return WAITING_SEARCH

    results = results[:20]
    context.user_data["partner_search_results"] = [
        {"key": k, **p} for k, p in results
    ]

    rows = []
    for k, p in results:
        stock = (p.get("stock") or {}).get("count", 0)
        price = p.get("yourPrice", "?")
        name  = p["name"]
        if len(name) > 38:
            name = name[:37] + "…"

        api_emoji = (p.get("emoji") or {}).get("normal")
        p_emoji = _provider_emoji(p.get("slug", ""), name, api_emoji)

        _s_icon, stock_str = _stock_label(stock)
        style = _stock_style(stock)

        label = f"{p_emoji} {name} — ${price} | {stock_str}"
        rows.append([_btn(label, f"pprod:{p['slug']}", style)])

    rows.append([_btn("🔙 Categories", "pcat", STYLE_DANGER)])

    await update.message.reply_text(
        f"🔍 <b>'{escape(raw)}'</b> — {len(results)} রেজাল্ট:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return WAITING_ACTION


# ─────────────────────────────────────────────────────
#  CANCEL
# ─────────────────────────────────────────────────────
async def partner_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("partner_pending", None)
    context.user_data.pop("partner_search_results", None)
    await update.effective_message.reply_text(
        "❌ বাতিল করা হলো।", reply_markup=main_keyboard()
    )
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
        rows.append([_btn(
            f"🔍 {o['order_code']}",
            f"pget:{o['order_code']}",
            STYLE_PRIMARY,
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
            f"💰 ব্যালেন্স: <b>${u.get('balance')}</b>\n"
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
        f"আজ খরচ: <b>{stats['today_spend']}</b>"
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
PARTNER_CANCEL = filters.Regex(r"^(❌ ᴄᴀɴᴄᴇʟ|❌ Cancel|cancel|/cancel|BACK|🔙 BACK)$")


def build_partner_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("partner", partner_entry),
            MessageHandler(filters.Regex(r"^🛍 ᴘᴀʀᴛɴᴇʀ ꜱʜᴏᴘ$"), partner_entry),
            MessageHandler(filters.Regex(r"^🛍 ᴘᴀʀᴛɴᴇʀ ᴏʀᴅᴇʀ$"), partner_entry),
        ],
        states={
            WAITING_ACTION: [
                CallbackQueryHandler(partner_nav,
                    pattern=r"^(pcat$|pprov:.+|prefresh:.+|psearch$|pget:.+)$"),
                CallbackQueryHandler(partner_product_selected,
                    pattern=r"^pprod:.+$"),
                CallbackQueryHandler(partner_quantity,
                    pattern=r"^pqty:.+$"),
                CallbackQueryHandler(partner_custom_qty_prompt,
                    pattern=r"^pcustom:.+$"),
                CallbackQueryHandler(partner_back,
                    pattern=r"^pback:.+$"),
                CallbackQueryHandler(partner_confirm,
                    pattern=r"^pconfirm:.+$"),
                CallbackQueryHandler(partner_alert_on,
                    pattern=r"^palert:.+$"),
                CallbackQueryHandler(partner_alert_off,
                    pattern=r"^punalert:.+$"),
            ],
            WAITING_CUSTOM_QTY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                    partner_custom_qty_input),
            ],
            WAITING_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                    partner_search_input),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", partner_cancel),
            MessageHandler(PARTNER_CANCEL, partner_cancel),
        ],
        allow_reentry=True,
        per_message=False,
        conversation_timeout=600,
    )