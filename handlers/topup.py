"""
Free Fire (ও অন্যান্য) Game Topup Handler
FlashTopup API v2 integration
"""
import logging
import uuid
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

import database as db
from api.flashtopup_api import (
    get_products, get_services, check_player_id, place_order, get_order_status
)
from keyboards.reply import main_keyboard
from utils.helpers import fmt_coins_full
from config import ADMIN_IDS, SERVICE_MARKUP_PCT

logger = logging.getLogger(__name__)

# ── Conversation States ───────────────────────────────────────────
(
    TOPUP_GAME_SELECT,
    TOPUP_PACKAGE_SELECT,
    TOPUP_PLAYER_ID,
    TOPUP_SERVER_ID,
    TOPUP_CONFIRM,
) = range(100, 105)

# Free Fire-এর validation_code (FlashTopup-এর fixed value)
GAME_CONFIGS = {
    "TOPUP_FREE_FIRE": {
        "name":            "🔥 Free Fire",
        "validation_code": "ff",
        "need_server_id":  False,
        "player_label":    "Free Fire UID",
    },
    "TOPUP_MOBILE_LEGENDS": {
        "name":            "⚔️ Mobile Legends",
        "validation_code": "mlbb",
        "need_server_id":  True,
        "player_label":    "MLBB User ID",
        "server_label":    "Zone ID",
    },
    "TOPUP_PUBG_MOBILE": {
        "name":            "🎯 PUBG Mobile",
        "validation_code": "pubgm",
        "need_server_id":  False,
        "player_label":    "PUBG UID",
    },
}

USD_TO_BDT  = 135
COIN_TO_BDT = 1.0


def _markup_price(cost_usd: float) -> float:
    """Apply markup and convert to coins (1 coin = ৳1)."""
    cost_bdt  = cost_usd * USD_TO_BDT
    after_mkp = cost_bdt * (1 + SERVICE_MARKUP_PCT / 100)
    return round(after_mkp, 2)


# ── Helper: game select keyboard ──────────────────────────────────
def _games_kb() -> InlineKeyboardMarkup:
    rows = []
    for code, cfg in GAME_CONFIGS.items():
        rows.append([InlineKeyboardButton(cfg["name"], callback_data=f"tg:{code}")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="topup_cancel")])
    return InlineKeyboardMarkup(rows)


def _extract_services(result: dict) -> list:
    """
    FlashTopup API response থেকে services list বের করো।
    সম্ভাব্য structures:
      1. {"data": [list of services]}
      2. {"data": {"service": [list], ...}}
      3. {"data": {"services": [list], ...}}
      4. [list of services]  (top-level)
    """
    if not result or "error" in result:
        return []

    raw = result.get("data")

    # Case 1: data is already a list
    if isinstance(raw, list):
        return raw

    # Case 2 & 3: data is a dict with "service" or "services" key
    if isinstance(raw, dict):
        services = raw.get("service") or raw.get("services") or []
        if isinstance(services, list):
            return services

    # Case 4: top-level list
    if isinstance(result, list):
        return result

    return []


# ─────────────────────────────────────────────────────────────────
#  ENTRY: Game Topup button → choose game
# ─────────────────────────────────────────────────────────────────
async def topup_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 <b>Game Topup</b>\n\n"
        "কোন game-এর জন্য topup করতে চাও?",
        reply_markup=_games_kb(),
        parse_mode=ParseMode.HTML
    )
    return TOPUP_GAME_SELECT


# ─────────────────────────────────────────────────────────────────
#  Game selected → show packages
# ─────────────────────────────────────────────────────────────────
async def topup_game_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "topup_cancel":
        await query.edit_message_text("❌ Cancelled.")
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        return ConversationHandler.END

    game_code = query.data[3:]   # strip "tg:"
    cfg       = GAME_CONFIGS.get(game_code)
    if not cfg:
        await query.answer("Unknown game.", show_alert=True)
        return TOPUP_GAME_SELECT

    ctx.user_data["topup_game_code"] = game_code
    ctx.user_data["topup_game_cfg"]  = cfg

    await query.edit_message_text(
        f"{cfg['name']}\n\n⏳ Packages লোড হচ্ছে...",
        parse_mode=ParseMode.HTML
    )

    # ── Step 1: products list থেকে সব matching product_code খোঁজো ──
    products_result = await get_products()
    logger.warning(f"FlashTopup products: {str(products_result)[:300]}")

    products_data = []
    raw_prod = products_result.get("data")
    if isinstance(raw_prod, list):
        products_data = raw_prod
    elif isinstance(raw_prod, dict):
        products_data = (
            raw_prod.get("products")
            or raw_prod.get("product")
            or list(raw_prod.values()) if raw_prod else []
        )
        # যদি values()-তে list পাই সেটা নাও
        if products_data and not isinstance(products_data[0], dict):
            products_data = []

    keywords = {
        "TOPUP_FREE_FIRE":       ["free fire", "freefire", "ff"],
        "TOPUP_MOBILE_LEGENDS":  ["mobile legends", "mlbb", "ml"],
        "TOPUP_PUBG_MOBILE":     ["pubg mobile", "pubg"],
    }
    search_terms = keywords.get(game_code, [game_code.lower()])

    # সব matching products collect করো (regional variants সহ)
    matched_products = []
    for prod in products_data:
        prod_name = (prod.get("name") or prod.get("product_name") or "").lower()
        prod_code = (prod.get("product_code") or prod.get("code") or "").lower()
        if any(term in prod_name or term in prod_code for term in search_terms):
            matched_products.append(prod)
            logger.warning(f"Matched product: {prod.get('product_code')} / {prod.get('product_type')}")

    # ── Step 2: সব matched products-এর services একসাথে load করো ──
    all_packages = []

    if matched_products:
        for prod in matched_products:
            p_code = prod.get("product_code") or prod.get("code") or game_code
            p_type = prod.get("product_type") or prod.get("type") or "topup"
            result = await get_services(p_code, p_type)
            logger.warning(f"Services for {p_code}: {str(result)[:200]}")
            svcs = _extract_services(result)
            all_packages.extend(svcs)
    else:
        # fallback: game_code দিয়ে সরাসরি চেষ্টা করো
        result = await get_services(game_code, "topup")
        logger.warning(f"Fallback services result: {str(result)[:300]}")
        all_packages = _extract_services(result)

    # duplicate service_code সরাও
    seen = set()
    packages = []
    for pkg in all_packages:
        sc = pkg.get("service_code", "")
        if sc not in seen:
            seen.add(sc)
            packages.append(pkg)

    # price অনুযায়ী sort করো
    packages.sort(key=lambda p: float(p.get("price") or p.get("price_usd") or 0))

    if not packages:
        # Admin-কে actual response দেখাও
        for aid in ADMIN_IDS:
            try:
                await ctx.bot.send_message(
                    aid,
                    f"🔴 FlashTopup API Response (no packages):\n"
                    f"<code>{str(result)[:800]}</code>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        await query.edit_message_text(
            "❌ Packages লোড করা যায়নি। কিছুক্ষণ পরে আবার চেষ্টা করো।"
        )
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        return ConversationHandler.END

    # service_code দিয়ে index করো
    ctx.user_data["topup_packages"] = {p["service_code"]: p for p in packages}

    # ── Show packages keyboard ──
    rows = []
    for pkg in packages[:30]:
        price_raw = pkg.get("price_usd") or pkg.get("price") or 0
        cost      = _markup_price(float(price_raw))
        label     = pkg.get("name") or pkg.get("service_name") or pkg["service_code"]
        emoji     = "💎" if "diamond" in label.lower() else "🔶"
        rows.append([InlineKeyboardButton(
            f"{emoji} {label} — ৳{cost:.0f}",
            callback_data=f"tp:{pkg['service_code'][:40]}"
        )])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="topup_game_back")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="topup_cancel")])

    await query.edit_message_text(
        f"{cfg['name']}\n\n💎 Package বেছে নাও:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.HTML
    )
    return TOPUP_PACKAGE_SELECT


# ─────────────────────────────────────────────────────────────────
#  Package selected → ask Player ID
# ─────────────────────────────────────────────────────────────────
async def topup_package_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "topup_cancel":
        await query.edit_message_text("❌ Cancelled.")
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        return ConversationHandler.END

    if query.data == "topup_game_back":
        await query.edit_message_text(
            "🎮 <b>Game Topup</b>\n\nকোন game-এর জন্য topup করতে চাও?",
            reply_markup=_games_kb(),
            parse_mode=ParseMode.HTML
        )
        return TOPUP_GAME_SELECT

    service_code = query.data[3:]   # strip "tp:"
    packages     = ctx.user_data.get("topup_packages", {})

    # button-এ code truncate হয়েছিল, তাই prefix match করো
    pkg = None
    for code, p in packages.items():
        if code == service_code or code[:40] == service_code:
            pkg = p
            service_code = code
            break

    if not pkg:
        await query.answer("Package পাওয়া যায়নি।", show_alert=True)
        return TOPUP_PACKAGE_SELECT

    price_raw = pkg.get("price_usd") or pkg.get("price") or 0
    cost      = _markup_price(float(price_raw))
    label     = pkg.get("name") or pkg.get("service_name") or service_code

    ctx.user_data["topup_service_code"] = service_code
    ctx.user_data["topup_pkg"]          = pkg
    ctx.user_data["topup_cost"]         = cost

    cfg = ctx.user_data.get("topup_game_cfg", {})
    await query.edit_message_text(
        f"✅ Selected: <b>{label}</b>\n"
        f"💰 Cost: <code>{cost:.0f} Coins (৳{cost:.0f})</code>\n\n"
        f"👇 তোমার <b>{cfg.get('player_label', 'Player ID')}</b> লেখো:",
        parse_mode=ParseMode.HTML
    )
    return TOPUP_PLAYER_ID


# ─────────────────────────────────────────────────────────────────
#  Player ID entered
# ─────────────────────────────────────────────────────────────────
async def topup_player_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    player_id = update.message.text.strip()
    if not player_id.isdigit():
        await update.message.reply_text(
            "❌ শুধু সংখ্যা দাও (উদাহরণ: 123456789)\n\n"
            "👇 তোমার Player ID লেখো:"
        )
        return TOPUP_PLAYER_ID

    ctx.user_data["topup_player_id"] = player_id
    cfg = ctx.user_data.get("topup_game_cfg", {})

    if cfg.get("need_server_id"):
        await update.message.reply_text(
            f"👇 তোমার <b>{cfg.get('server_label', 'Server ID')}</b> লেখো:"
            f"\n\n<i>(Game profile-এ পাবে)</i>",
            parse_mode=ParseMode.HTML
        )
        return TOPUP_SERVER_ID
    else:
        ctx.user_data["topup_server_id"] = "0"
        return await _verify_and_confirm(update, ctx)


# ─────────────────────────────────────────────────────────────────
#  Server ID entered (MLBB etc.)
# ─────────────────────────────────────────────────────────────────
async def topup_server_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    server_id = update.message.text.strip()
    ctx.user_data["topup_server_id"] = server_id
    return await _verify_and_confirm(update, ctx)


# ─────────────────────────────────────────────────────────────────
#  Internal: verify player ID then show confirmation
# ─────────────────────────────────────────────────────────────────
async def _verify_and_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.effective_message.reply_text(
        "⏳ Player ID verify হচ্ছে..."
    )

    player_id = ctx.user_data["topup_player_id"]
    server_id = ctx.user_data["topup_server_id"]
    cfg       = ctx.user_data["topup_game_cfg"]
    pkg       = ctx.user_data["topup_pkg"]
    cost      = ctx.user_data["topup_cost"]

    result = await check_player_id(player_id, server_id, cfg["validation_code"])

    # valid check — "valid" key না থাকলে nickname থাকলেই valid ধরো
    data      = result.get("data") or {}
    is_valid  = data.get("valid") or bool(data.get("nickname"))

    if result.get("error") or not is_valid:
        err_msg = data.get("message") or "Player ID সঠিক নয়।"
        await msg.edit_text(
            f"❌ <b>Player ID ভুল!</b>\n\n{err_msg}\n\n"
            f"👇 সঠিক Player ID লেখো:",
            parse_mode=ParseMode.HTML
        )
        return TOPUP_PLAYER_ID

    nickname = data.get("nickname") or data.get("username") or "Unknown"
    ctx.user_data["topup_nickname"] = nickname

    user_id  = update.effective_user.id
    udata    = await db.get_user(user_id)
    balance  = float(udata["balance"]) if udata else 0

    confirm_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm", callback_data="topup_confirm")],
        [InlineKeyboardButton("❌ Cancel",  callback_data="topup_cancel")],
    ])

    label  = pkg.get("name") or pkg.get("service_name") or ctx.user_data["topup_service_code"]
    bal_ok = "✅" if balance >= cost else "❌"

    await msg.edit_text(
        f"📋 <b>Topup Confirmation</b>\n"
        f"{'─'*28}\n"
        f"🎮 Game: <b>{cfg['name']}</b>\n"
        f"💎 Package: <code>{label}</code>\n"
        f"👤 {cfg.get('player_label', 'ID')}: <code>{player_id}</code>\n"
        f"🏷️ Nickname: <b>{nickname}</b>\n"
        f"💵 Cost: <code>{cost:.0f} Coins (৳{cost:.0f})</code>\n"
        f"💰 Balance: <code>{balance:,.0f} Coins</code> {bal_ok}\n\n"
        f"{'✅ Confirm করো?' if balance >= cost else '❌ Balance কম! Buy Coins থেকে বাড়াও।'}",
        reply_markup=confirm_kb if balance >= cost else None,
        parse_mode=ParseMode.HTML
    )
    return TOPUP_CONFIRM


# ─────────────────────────────────────────────────────────────────
#  Confirm → place order
# ─────────────────────────────────────────────────────────────────
async def topup_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "topup_cancel":
        await query.edit_message_text("❌ Cancelled.")
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        ctx.user_data.clear()
        return ConversationHandler.END

    user_id      = query.from_user.id
    service_code = ctx.user_data["topup_service_code"]
    player_id    = ctx.user_data["topup_player_id"]
    server_id    = ctx.user_data["topup_server_id"]
    cost         = ctx.user_data["topup_cost"]
    pkg          = ctx.user_data["topup_pkg"]
    cfg          = ctx.user_data["topup_game_cfg"]
    nickname     = ctx.user_data.get("topup_nickname", "")
    label        = pkg.get("name") or pkg.get("service_name") or service_code

    # Deduct balance
    ok = await db.deduct_balance(user_id, cost, f"Topup: {label}")
    if not ok:
        await query.edit_message_text(
            "❌ <b>Balance কম!</b>\n\n💳 Buy Coins থেকে balance বাড়াও।",
            parse_mode=ParseMode.HTML
        )
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        ctx.user_data.clear()
        return ConversationHandler.END

    await query.edit_message_text("⏳ Order দেওয়া হচ্ছে...")

    # Place order
    reference_id = f"TG_{user_id}_{uuid.uuid4().hex[:10]}"
    result       = await place_order(service_code, player_id, server_id, reference_id)

    order_ok = result.get("success") is True or result.get("code") in (None, "SUCCESS", "200")

    if not order_ok:
        # Refund
        await db.add_balance(user_id, cost, "Refund: Topup failed")
        err = result.get("message") or str(result.get("error", "Unknown error"))

        for admin_id in ADMIN_IDS:
            try:
                await query.message.bot.send_message(
                    admin_id,
                    f"⚠️ <b>Topup Order Failed</b>\n"
                    f"User: <code>{user_id}</code>\n"
                    f"Service: <code>{service_code}</code>\n"
                    f"Error: <code>{err}</code>",
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass

        await query.edit_message_text(
            "⚠️ Order টি process করা যায়নি। Balance refund হয়ে গেছে।\n"
            "সমস্যা হলে যোগাযোগ করো: @shuvo_9882",
        )
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        ctx.user_data.clear()
        return ConversationHandler.END

    order_data = result.get("data") or {}
    order_id   = order_data.get("order_id") or reference_id
    status     = order_data.get("status") or "Processing"

    await db.save_topup_order(
        user_id      = user_id,
        order_id     = order_id,
        reference_id = reference_id,
        game         = cfg["name"],
        package      = label,
        player_id    = player_id,
        nickname     = nickname,
        cost         = cost,
        status       = status,
    )

    await query.edit_message_text(
        f"✅ <b>Order Successful!</b>\n"
        f"{'─'*28}\n"
        f"🎮 Game: <b>{cfg['name']}</b>\n"
        f"💎 Package: <code>{label}</code>\n"
        f"👤 Nickname: <b>{nickname}</b>\n"
        f"🆔 Order ID: <code>{order_id}</code>\n\n"
        f"⏳ ৫-১০ মিনিটের মধ্যে diamonds পাবে!\n"
        f"❓ সমস্যা হলে: @shuvo_9882",
        parse_mode=ParseMode.HTML
    )
    await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
    ctx.user_data.clear()
    return ConversationHandler.END
