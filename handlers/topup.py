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
    get_services, check_player_id, place_order
)
from keyboards.reply import main_keyboard
from config import ADMIN_IDS, TOPUP_MARKUP_PCT

logger = logging.getLogger(__name__)

# ── Conversation States ───────────────────────────────────────────
(
    TOPUP_GAME_SELECT,
    TOPUP_PACKAGE_SELECT,
    TOPUP_PLAYER_ID,
    TOPUP_SERVER_ID,
    TOPUP_CONFIRM,
) = range(100, 105)

USD_TO_BDT  = 135
COIN_TO_BDT = 1.0

GAME_CONFIGS = {
    "TOPUP_FREE_FIRE_BANGLADESH_18": {
        "name":            "🔥 Free Fire Bangladesh",
        "product_id":      18,
        "validation_code": "freefire_bd",
        "need_server_id":  False,
        "player_label":    "Free Fire UID",
        "product_type":    "topup",
    },
    "TOPUP_MOBILE_LEGENDS": {
        "name":            "⚔️ Mobile Legends",
        "product_id":      3,
        "validation_code": "mlbb",
        "need_server_id":  True,
        "player_label":    "MLBB User ID",
        "server_label":    "Zone ID",
        "product_type":    "topup",
    },
    "TOPUP_PUBG_MOBILE": {
        "name":            "🎯 PUBG Mobile",
        "product_id":      7,
        "validation_code": "pubgm",
        "need_server_id":  False,
        "player_label":    "PUBG Player ID",
        "product_type":    "topup",
    },
}

# Telegram config — GAME_CONFIGS এর বাইরে, শুধু reply menu button থেকে access
TELEGRAM_CONFIG = {
    "name":            "✈️ Telegram",
    "product_id":      191,
    "validation_code": "telegram",
    "need_server_id":  False,
    "player_label":    "Telegram Username (যেমন: shuvo বা @shuvo)",
    "allow_text_id":   True,
    "product_type":    "topup",
}


def _markup_price(cost_usd: float) -> float:
    cost_bdt  = cost_usd * USD_TO_BDT
    after_mkp = cost_bdt * (1 + TOPUP_MARKUP_PCT / 100)
    return round(after_mkp, 2)


def _games_kb() -> InlineKeyboardMarkup:
    rows = []
    for code, cfg in GAME_CONFIGS.items():
        rows.append([InlineKeyboardButton(cfg["name"], callback_data=f"tg:{code}")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="topup_cancel")])
    return InlineKeyboardMarkup(rows)


async def topup_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 <b>Game Topup</b>\n\nকোন game-এর জন্য topup করতে চাও?",
        reply_markup=_games_kb(),
        parse_mode=ParseMode.HTML
    )
    return TOPUP_GAME_SELECT


async def topup_start_telegram(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """সরাসরি Telegram product (ID 191) এর packages দেখায়"""
    tg_cfg = TELEGRAM_CONFIG
    ctx.user_data["topup_game_code"] = "TOPUP_TELEGRAM"
    ctx.user_data["topup_game_cfg"]  = tg_cfg

    msg = await update.message.reply_text(
        "✈️ <b>Telegram Topup</b>\n\n⏳ Packages লোড হচ্ছে...",
        parse_mode=ParseMode.HTML
    )

    try:
        result   = await get_services(tg_cfg["product_id"], tg_cfg.get("product_type", "topup"))
        result   = result or {}
        raw_data = result.get("data") or {}
        packages = list(raw_data.get("service") or []) if isinstance(raw_data, dict) else []

        if not packages:
            await msg.edit_text("⚠️ কোনো Telegram package পাওয়া যায়নি। পরে চেষ্টা করো।")
            return ConversationHandler.END

        ctx.user_data["topup_packages"] = packages

        rows = []
        for pkg in packages[:20]:
            label = pkg.get("name") or pkg.get("service_name", "Package")
            price = _markup_price(float(pkg.get("price", 0)))
            rows.append([InlineKeyboardButton(
                f"{label} — ৳{price}",
                callback_data=f"tp:{pkg.get('service_code', pkg.get('id', ''))}"
            )])
        rows.append([InlineKeyboardButton("❌ Cancel", callback_data="topup_cancel")])

        await msg.edit_text(
            f"✈️ <b>Telegram Packages</b>\n\n👇 Package বেছে নাও:",
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=ParseMode.HTML
        )
        return TOPUP_PACKAGE_SELECT

    except Exception as e:
        logger.error(f"topup_start_telegram error: {e}")
        await msg.edit_text("❌ Error loading packages. Try again later.")
        return ConversationHandler.END




async def topup_game_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "topup_cancel":
        await query.edit_message_text("❌ Cancelled.")
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        return ConversationHandler.END

    game_code = query.data[3:]
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

    try:
        product_id  = cfg.get("product_id")
        result      = await get_services(product_id, cfg.get("product_type", "topup"))
        result      = result or {}
        raw_data    = result.get("data") or {}
        packages    = list(raw_data.get("service") or []) if isinstance(raw_data, dict) else []
        api_success = bool(result.get("success", False))
        ctx.user_data["topup_validation_code"] = cfg.get("validation_code", "")
    except Exception as e:
        logger.error(f"get_services error: {e}")
        result      = {}
        packages    = []
        api_success = False

    if not api_success or not packages:
        for aid in ADMIN_IDS:
            try:
                await ctx.bot.send_message(
                    aid,
                    f"⚠️ Topup packages error\n<code>{str(result)[:500]}</code>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        await query.edit_message_text("❌ Packages লোড করা যায়নি। কিছুক্ষণ পরে আবার চেষ্টা করো।")
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        return ConversationHandler.END

    ctx.user_data["topup_packages"] = {p["service_code"]: p for p in packages}

    rows = []
    for pkg in packages[:30]:
        cost  = _markup_price(float(pkg.get("price") or 0))
        label = pkg.get("service_name") or pkg["service_code"]
        rows.append([InlineKeyboardButton(
            f"💎 {label} — ৳{cost:.0f}",
            callback_data=f"tp:{pkg['service_code'][:40]}"
        )])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="topup_cancel")])

    await query.edit_message_text(
        f"{cfg['name']}\n\n💎 Package বেছে নাও:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.HTML
    )
    return TOPUP_PACKAGE_SELECT


async def topup_package_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "topup_cancel":
        await query.edit_message_text("❌ Cancelled.")
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        return ConversationHandler.END

    service_code = query.data[3:]
    packages     = ctx.user_data.get("topup_packages", {})

    pkg = None
    # dict format (game topup)
    if isinstance(packages, dict):
        for code, p in packages.items():
            if code[:40] == service_code:
                pkg = p
                service_code = code
                break
    # list format (telegram topup)
    elif isinstance(packages, list):
        for p in packages:
            code = str(p.get("service_code", p.get("id", "")))
            if code[:40] == service_code:
                pkg = p
                service_code = code
                break

    if not pkg:
        await query.answer("Package পাওয়া যায়নি।", show_alert=True)
        return TOPUP_PACKAGE_SELECT

    cost = _markup_price(float(pkg.get("price") or 0))
    ctx.user_data["topup_service_code"] = service_code
    ctx.user_data["topup_pkg"]          = pkg
    ctx.user_data["topup_cost"]         = cost

    cfg = ctx.user_data.get("topup_game_cfg", {})
    await query.edit_message_text(
        f"✅ Selected: <b>{pkg.get('service_name', pkg.get('name', service_code))}</b>\n"
        f"💰 Cost: <code>{cost:.0f} Coins (৳{cost:.0f})</code>\n\n"
        f"👇 তোমার <b>{cfg.get('player_label', 'Player ID')}</b> লেখো:",
        parse_mode=ParseMode.HTML
    )
    return TOPUP_PLAYER_ID


async def topup_player_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    player_id = update.message.text.strip()
    cfg       = ctx.user_data.get("topup_game_cfg", {})

    # Telegram এর জন্য text ID allow, বাকিদের জন্য শুধু digit
    if not cfg.get("allow_text_id") and not player_id.isdigit():
        await update.message.reply_text(
            "❌ শুধু সংখ্যা দাও (উদাহরণ: 123456789)\n\n"
            f"👇 তোমার {cfg.get('player_label', 'Player ID')} লেখো:"
        )
        return TOPUP_PLAYER_ID

    # Telegram username — @ ছাড়া দিলে @ যোগ করো
    if cfg.get("allow_text_id") and not player_id.startswith("@") and not player_id.isdigit():
        player_id = "@" + player_id

    ctx.user_data["topup_player_id"] = player_id

    if cfg.get("need_server_id"):
        await update.message.reply_text(
            f"👇 তোমার <b>{cfg.get('server_label', 'Server ID')}</b> লেখো:",
            parse_mode=ParseMode.HTML
        )
        return TOPUP_SERVER_ID
    else:
        ctx.user_data["topup_server_id"] = "0"
        return await _verify_and_confirm(update, ctx)


async def topup_server_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["topup_server_id"] = update.message.text.strip()
    return await _verify_and_confirm(update, ctx)


async def _verify_and_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.effective_message.reply_text("⏳ Order confirm হচ্ছে...")

    player_id = ctx.user_data["topup_player_id"]
    server_id = ctx.user_data["topup_server_id"]
    cfg       = ctx.user_data["topup_game_cfg"]
    pkg       = ctx.user_data["topup_pkg"]
    cost      = ctx.user_data["topup_cost"]
    val_code  = ctx.user_data.get("topup_validation_code", "")

    # Telegram এর জন্য skip_validation নেই — API দিয়ে validate করো
    if not val_code:
        nickname = player_id
    else:
        result = await check_player_id(player_id, server_id, val_code)
        result = result or {}
        data   = result.get("data") or {}

        # DEBUG — সাময়িক, response দেখার জন্য
        await update.effective_message.reply_text(
            f"🔍 <b>DEBUG</b>\n"
            f"📤 <code>user_id={player_id}</code>\n"
            f"📤 <code>val_code={val_code}</code>\n"
            f"📥 <code>{str(result)[:400]}</code>",
            parse_mode="HTML"
        )

        for aid in ADMIN_IDS:
            try:
                await update.effective_message.bot.send_message(
                    aid,
                    f"🔍 <b>check_player_id DEBUG</b>\n"
                    f"📤 Request:\n<code>user_id={player_id}\nserver_id={server_id}\nvalidation_code={val_code}</code>\n\n"
                    f"📥 Response:\n<code>{str(result)[:500]}</code>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        if not result.get("success") or not data.get("valid"):
            err_msg = (
                data.get("message") or
                (result.get("error", {}).get("message")
                 if isinstance(result.get("error"), dict) else None) or
                "ID সঠিক নয়।"
            )
            cfg_label = cfg.get("player_label", "ID")
            await msg.edit_text(
                f"❌ <b>ভুল {cfg_label}!</b>\n\n"
                f"<i>{err_msg}</i>\n\n"
                f"👇 সঠিক <b>{cfg_label}</b> দাও:",
                parse_mode=ParseMode.HTML
            )
            return TOPUP_PLAYER_ID

        logger.warning(f"check_player_id data fields: {list(data.keys()) if isinstance(data, dict) else data}")
        nickname = (
            data.get("account_name") or data.get("nickname") or
            data.get("username") or data.get("name") or
            player_id
        )

    ctx.user_data["topup_nickname"] = nickname

    user_id = update.effective_user.id
    udata   = await db.get_user(user_id)
    balance = float(udata["balance"]) if udata else 0
    bal_ok  = "✅" if balance >= cost else "❌"

    confirm_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm", callback_data="topup_confirm")],
        [InlineKeyboardButton("❌ Cancel",  callback_data="topup_cancel")],
    ])

    await msg.edit_text(
        f"📋 <b>Topup Confirmation</b>\n"
        f"{'─'*28}\n"
        f"🎮 Game: <b>{cfg['name']}</b>\n"
        f"💎 Package: <code>{pkg.get('service_name', '')}</code>\n"
        f"👤 {cfg.get('player_label', 'ID')}: <code>{player_id}</code>\n"
        f"🏷️ Nickname: <b>{nickname}</b>\n"
        f"💵 Cost: <code>{cost:.0f} Coins (৳{cost:.0f})</code>\n"
        f"💰 Balance: <code>{balance:,.0f} Coins</code> {bal_ok}\n\n"
        f"{'✅ Confirm করো?' if balance >= cost else '❌ Balance কম! Buy Coins থেকে বাড়াও।'}",
        reply_markup=confirm_kb if balance >= cost else None,
        parse_mode=ParseMode.HTML
    )
    return TOPUP_CONFIRM


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

    ok = await db.deduct_balance(user_id, cost, f"Topup: {pkg.get('service_name', service_code)}")
    if not ok:
        await query.edit_message_text(
            "❌ <b>Balance কম!</b>\n\n💳 Buy Coins থেকে balance বাড়াও।",
            parse_mode=ParseMode.HTML
        )
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        ctx.user_data.clear()
        return ConversationHandler.END

    await query.edit_message_text("⏳ Order দেওয়া হচ্ছে...")

    reference_id = f"TG_{user_id}_{uuid.uuid4().hex[:10]}"
    result       = await place_order(service_code, player_id, server_id, reference_id)

    if not result.get("success"):
        await db.add_balance(user_id, cost, "Refund: Topup failed")
        err = result.get("error", {}).get("message") or str(result)
        await query.edit_message_text(
            "⚠️ Order টি process হচ্ছে।\n"
            "সমস্যা হলে যোগাযোগ করো: @shuvo_9882"
        )
        for aid in ADMIN_IDS:
            try:
                await ctx.bot.send_message(
                    aid,
                    f"⚠️ <b>Topup Failed</b>\nUser: <code>{user_id}</code>\n"
                    f"Error: <code>{err[:300]}</code>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        ctx.user_data.clear()
        return ConversationHandler.END

    order_id = result.get("data", {}).get("order_id") or reference_id
    await db.save_topup_order(
        user_id=user_id, order_id=order_id, reference_id=reference_id,
        game=cfg["name"], package=pkg.get("service_name", service_code),
        player_id=player_id, nickname=nickname, cost=cost,
        status=result.get("data", {}).get("status", "Processing"),
    )

    await query.edit_message_text(
        f"✅ <b>Order Successful!</b>\n"
        f"{'─'*28}\n"
        f"🎮 Game: <b>{cfg['name']}</b>\n"
        f"💎 Package: <code>{pkg.get('service_name', '')}</code>\n"
        f"👤 Nickname: <b>{nickname}</b>\n"
        f"🆔 Order ID: <code>{order_id}</code>\n\n"
        f"⏳ ৫-১০ মিনিটের মধ্যে diamonds পাবে!\n"
        f"❓ সমস্যা হলে: @shuvo_9882",
        parse_mode=ParseMode.HTML
    )
    await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
    ctx.user_data.clear()
    return ConversationHandler.END