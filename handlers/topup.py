"""
Free Fire / MLBB / PUBG / Telegram — Game Topup Handler
FlashTopup API v2 integration (product_code based)
"""
import json
import logging
import uuid
from typing import Optional, Dict, Any

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram._utils.types import JSONDict

import database as db
from api.flashtopup_api import (
    get_services, get_products, check_player_id, place_order,
)
from keyboards.reply import main_keyboard
from config import ADMIN_IDS, TOPUP_MARKUP_PCT
from utils.order_logger import send_order_log

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


# ══════════════════════════════════════════════════════════════════
#  GAME CONFIGS
#  product_code  : FlashTopup stable code (Products API)
#  product_type  : from Products API
#  order_fields  : exact field names from Products API `fields[]`
#                  (user_id, server_id, target_id, zone_id, ...)
#  need_server   : convenience flag → player flow asks for server
# ══════════════════════════════════════════════════════════════════
GAME_CONFIGS: Dict[str, Dict[str, Any]] = {
    "TOPUP_FREE_FIRE_BANGLADESH": {
        "name":            "🔥 Free Fire Bangladesh",
        "product_code":    "TOPUP_FREE_FIRE_BANGLADESH",
        "product_type":    "topup",
        "validation_code": "freefire_bd",          # ← /products থেকে যাচাই করুন
        "order_fields":    ["user_id"],
        "need_server_id":  False,
        "player_label":    "Free Fire UID",
    },
    "TOPUP_MOBILE_LEGENDS": {
        "name":            "⚔️ Mobile Legends",
        "product_code":    "TOPUP_MOBILE_LEGENDS",
        "product_type":    "topup",
        "validation_code": "mlbb",
        "order_fields":    ["user_id", "server_id"],
        "need_server_id":  True,
        "player_label":    "MLBB User ID",
        "server_label":    "Zone ID",
    },
    "TOPUP_PUBG_MOBILE": {
        "name":            "🎯 PUBG Mobile",
        "product_code":    "TOPUP_PUBG_MOBILE",
        "product_type":    "topup",
        "validation_code": "pubgm",
        "order_fields":    ["user_id"],
        "need_server_id":  False,
        "player_label":    "PUBG Player ID",
    },
}

TELEGRAM_CONFIG: Dict[str, Any] = {
    "name":            "✈️ Telegram",
    "product_code":    "TOPUP_TELEGRAM",           # ← /products থেকে সঠিক কোড বসান
    "product_type":    "topup",
    "validation_code": "telegram",
    "order_fields":    ["user_id"],
    "need_server_id":  False,
    "player_label":    "Telegram Username (যেমন: shuvo বা @shuvo)",
    "allow_text_id":   True,
}


# ── StyledButton ──────────────────────────────────────────────────
class StyledButton(InlineKeyboardButton):
    def __init__(self, text: str, style: Optional[str] = None, **kwargs):
        super().__init__(text=text, **kwargs)
        self._style = style

    def to_dict(self, recursive: bool = True) -> JSONDict:
        data = super().to_dict(recursive=recursive)
        if self._style:
            data["style"] = self._style
        return data


def _markup_price(cost_usd: float) -> float:
    cost_bdt  = cost_usd * USD_TO_BDT
    after_mkp = cost_bdt * (1 + TOPUP_MARKUP_PCT / 100)
    return round(after_mkp, 2)


def _games_kb() -> InlineKeyboardMarkup:
    rows = []
    for code, cfg in GAME_CONFIGS.items():
        rows.append([StyledButton(cfg["name"], style="primary",
                                  callback_data=f"tg:{code}")])
    rows.append([StyledButton("❌ Cancel", style="danger",
                              callback_data="topup_cancel")])
    return InlineKeyboardMarkup(rows)


def _extract_services(result: dict) -> list:
    """API রেসপন্স থেকে packages লিস্ট বের করে — সব সম্ভাব্য শেপ হ্যান্ডেল করে।"""
    if not result:
        return []
    data = result.get("data")
    if isinstance(data, dict):
        return list(data.get("service") or data.get("services") or [])
    if isinstance(data, list):
        return data
    return []


async def _admin_alert(ctx, text: str):
    for aid in ADMIN_IDS:
        try:
            await ctx.bot.send_message(aid, text, parse_mode="HTML")
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════
#  ENTRY POINTS
# ══════════════════════════════════════════════════════════════════
async def topup_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 <b>Game Topup</b>\n\nকোন game-এর জন্য topup করতে চাও?",
        reply_markup=_games_kb(),
        parse_mode=ParseMode.HTML,
    )
    return TOPUP_GAME_SELECT


async def topup_start_telegram(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_cfg = TELEGRAM_CONFIG
    ctx.user_data.clear()
    ctx.user_data["topup_game_code"]       = tg_cfg["product_code"]
    ctx.user_data["topup_game_cfg"]        = tg_cfg
    ctx.user_data["topup_validation_code"] = tg_cfg["validation_code"]

    msg = await update.message.reply_text(
        "✈️ <b>Telegram Topup</b>\n\n⏳ Packages লোড হচ্ছে...",
        parse_mode=ParseMode.HTML,
    )

    try:
        result   = await get_services(
            product_code=tg_cfg["product_code"],
            product_type=tg_cfg.get("product_type", "topup"),
        )
        packages = _extract_services(result)

        if not packages:
            await _admin_alert(
                ctx,
                f"⚠️ Telegram topup packages error\n"
                f"<code>{json.dumps(result, ensure_ascii=False)[:500]}</code>",
            )
            await msg.edit_text("⚠️ কোনো Telegram package পাওয়া যায়নি। পরে চেষ্টা করো।")
            return ConversationHandler.END

        ctx.user_data["topup_packages"] = packages

        rows = []
        for pkg in packages[:20]:
            label        = pkg.get("service_name") or pkg.get("name") or "Package"
            price        = _markup_price(float(pkg.get("price") or 0))
            service_code = pkg.get("service_code") or str(pkg.get("id", ""))
            rows.append([StyledButton(
                f"{label} — ৳{price:.0f}",
                style="primary",
                callback_data=f"tp:{service_code[:40]}",
            )])
        rows.append([StyledButton("❌ Cancel", style="danger",
                                  callback_data="topup_cancel")])

        await msg.edit_text(
            "✈️ <b>Telegram Packages</b>\n\n👇 Package বেছে নাও:",
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=ParseMode.HTML,
        )
        return TOPUP_PACKAGE_SELECT

    except Exception as e:
        logger.exception("topup_start_telegram error")
        await _admin_alert(ctx, f"⚠️ topup_start_telegram exception\n<code>{e}</code>")
        await msg.edit_text("❌ Error loading packages. Try again later.")
        return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════
#  GAME SELECT → PACKAGE LIST
# ══════════════════════════════════════════════════════════════════
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
        parse_mode=ParseMode.HTML,
    )

    result   = {}
    packages = []
    try:
        result = await get_services(
            product_code=cfg["product_code"],
            product_type=cfg.get("product_type", "topup"),
        )
        packages = _extract_services(result)
        ctx.user_data["topup_validation_code"] = cfg.get("validation_code", "")
    except Exception as e:
        logger.exception("get_services error")
        await _admin_alert(
            ctx,
            f"⚠️ get_services exception for {cfg['product_code']}\n"
            f"<code>{e}</code>",
        )

    if not packages:
        await _admin_alert(
            ctx,
            f"⚠️ Topup packages error — {cfg['product_code']}\n"
            f"<code>{json.dumps(result, ensure_ascii=False)[:500]}</code>",
        )
        await query.edit_message_text(
            "❌ Packages লোড করা যায়নি। কিছুক্ষণ পরে আবার চেষ্টা করো।"
        )
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        return ConversationHandler.END

    # service_code → pkg ম্যাপ (ক trimming এড়াতে)
    ctx.user_data["topup_packages"] = {
        (p.get("service_code") or str(p.get("id", ""))): p for p in packages
    }

    rows = []
    for pkg in packages[:30]:
        service_code = pkg.get("service_code") or str(pkg.get("id", ""))
        cost         = _markup_price(float(pkg.get("price") or 0))
        label        = pkg.get("service_name") or pkg.get("name") or service_code
        rows.append([StyledButton(
            f"💎 {label} — ৳{cost:.0f}",
            style="primary",
            callback_data=f"tp:{service_code[:40]}",
        )])
    rows.append([StyledButton("❌ Cancel", style="danger",
                              callback_data="topup_cancel")])

    await query.edit_message_text(
        f"{cfg['name']}\n\n💎 Package বেছে নাও:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.HTML,
    )
    return TOPUP_PACKAGE_SELECT


# ══════════════════════════════════════════════════════════════════
#  PACKAGE SELECT → PLAYER ID
# ══════════════════════════════════════════════════════════════════
async def topup_package_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "topup_cancel":
        await query.edit_message_text("❌ Cancelled.")
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        return ConversationHandler.END

    short_code = query.data[3:]
    packages   = ctx.user_data.get("topup_packages", {})

    pkg          = None
    service_code = short_code
    if isinstance(packages, dict):
        for code, p in packages.items():
            if code[:40] == short_code:
                pkg          = p
                service_code = code
                break
    elif isinstance(packages, list):
        for p in packages:
            code = str(p.get("service_code") or p.get("id", ""))
            if code[:40] == short_code:
                pkg          = p
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
        f"✅ Selected: <b>{pkg.get('service_name') or pkg.get('name') or service_code}</b>\n"
        f"💰 Cost: <code>৳{cost:.0f} ({cost:.0f} Coins)</code>\n\n"
        f"👇 তোমার <b>{cfg.get('player_label', 'Player ID')}</b> লেখো:",
        parse_mode=ParseMode.HTML,
    )
    return TOPUP_PLAYER_ID


# ══════════════════════════════════════════════════════════════════
#  PLAYER ID / SERVER ID INPUT
# ══════════════════════════════════════════════════════════════════
async def topup_player_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    player_id = (update.message.text or "").strip()
    cfg       = ctx.user_data.get("topup_game_cfg", {})

    if not cfg.get("allow_text_id") and not player_id.isdigit():
        await update.message.reply_text(
            "❌ শুধু সংখ্যা দাও (উদাহরণ: 123456789)\n\n"
            f"👇 তোমার {cfg.get('player_label', 'Player ID')} লেখো:"
        )
        return TOPUP_PLAYER_ID

    if cfg.get("allow_text_id") and not player_id.startswith("@") and not player_id.isdigit():
        player_id = "@" + player_id

    ctx.user_data["topup_player_id"] = player_id

    if cfg.get("need_server_id"):
        await update.message.reply_text(
            f"👇 তোমার <b>{cfg.get('server_label', 'Server ID')}</b> লেখো:",
            parse_mode=ParseMode.HTML,
        )
        return TOPUP_SERVER_ID

    ctx.user_data["topup_server_id"] = "0"
    return await _verify_and_confirm(update, ctx)


async def topup_server_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["topup_server_id"] = (update.message.text or "").strip()
    return await _verify_and_confirm(update, ctx)


# ══════════════════════════════════════════════════════════════════
#  VERIFY + CONFIRM SCREEN
# ══════════════════════════════════════════════════════════════════
async def _verify_and_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.effective_message.reply_text("⏳ Order confirm হচ্ছে...")

    player_id = ctx.user_data["topup_player_id"]
    server_id = ctx.user_data["topup_server_id"]
    cfg       = ctx.user_data["topup_game_cfg"]
    pkg       = ctx.user_data["topup_pkg"]
    cost      = ctx.user_data["topup_cost"]
    val_code  = ctx.user_data.get("topup_validation_code", "")

    nickname = player_id

    if val_code:
        try:
            check = await check_player_id(
                user_id=player_id,
                validation_code=val_code,
                server_id=(server_id if cfg.get("need_server_id") else None),
            )
        except Exception as e:
            logger.exception("check_player_id error")
            check = {"success": False, "error": {"message": str(e)}}

        data = (check.get("data") or {}) if isinstance(check, dict) else {}

        await _admin_alert(
            update.effective_message.bot,
            f"🔍 <b>check_player_id DEBUG</b>\n"
            f"📤 user_id={player_id} server_id={server_id} code={val_code}\n"
            f"📥 <code>{json.dumps(check, ensure_ascii=False)[:500]}</code>",
        ) if False else None  # ডিবাগ বন্ধ রাখতে চাইলে এভাবে; চাইলে True করে দিন

        # সফলতা যাচাই — API valid ফিল্ড না দিলেও account_name থাকলে সফল ধরি
        is_ok = (
            isinstance(check, dict)
            and check.get("success")
            and (
                data.get("valid") is True
                or data.get("account_name")
                or data.get("nickname")
                or data.get("username")
            )
        )

        if not is_ok:
            err_msg = (
                (data.get("message") if isinstance(data, dict) else None)
                or (check.get("error", {}).get("message")
                    if isinstance(check.get("error"), dict) else None)
                or "ID সঠিক নয়।"
            )
            cfg_label = cfg.get("player_label", "ID")
            await msg.edit_text(
                f"❌ <b>ভুল {cfg_label}!</b>\n\n<i>{err_msg}</i>\n\n"
                f"👇 সঠিক <b>{cfg_label}</b> দাও:",
                parse_mode=ParseMode.HTML,
            )
            return TOPUP_PLAYER_ID

        nickname = (
            data.get("account_name")
            or data.get("nickname")
            or data.get("username")
            or data.get("name")
            or player_id
        )

    ctx.user_data["topup_nickname"] = nickname

    user_id = update.effective_user.id
    udata   = await db.get_user(user_id)
    balance = float(udata["balance"]) if udata else 0
    bal_ok  = "✅" if balance >= cost else "❌"

    confirm_kb = InlineKeyboardMarkup([
        [StyledButton("✅ Confirm", style="success", callback_data="topup_confirm")],
        [StyledButton("❌ Cancel",  style="danger",  callback_data="topup_cancel")],
    ])

    await msg.edit_text(
        f"📋 <b>Topup Confirmation</b>\n"
        f"{'─' * 28}\n"
        f"🎮 Game: <b>{cfg['name']}</b>\n"
        f"💎 Package: <code>{pkg.get('service_name') or pkg.get('name', '')}</code>\n"
        f"👤 {cfg.get('player_label', 'ID')}: <code>{player_id}</code>\n"
        + (f"🌐 {cfg.get('server_label', 'Server')}: <code>{server_id}</code>\n"
           if cfg.get("need_server_id") else "")
        + f"🏷️ Nickname: <b>{nickname}</b>\n"
        f"💵 Cost: <code>৳{cost:.0f} ({cost:.0f} Coins)</code>\n"
        f"💰 Balance: <code>{balance:,.0f} Coins</code> {bal_ok}\n\n"
        f"{'✅ Confirm করো?' if balance >= cost else '❌ Balance কম! Buy Coins থেকে বাড়াও।'}",
        reply_markup=confirm_kb if balance >= cost else None,
        parse_mode=ParseMode.HTML,
    )
    return TOPUP_CONFIRM


# ══════════════════════════════════════════════════════════════════
#  FINAL CONFIRM → PLACE ORDER
# ══════════════════════════════════════════════════════════════════
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

    # ── ব্যালেন্স কাটা ────────────────────────────────────────────
    ok = await db.deduct_balance(
        user_id, cost, f"Topup: {pkg.get('service_name', service_code)}"
    )
    if not ok:
        await query.edit_message_text(
            "❌ <b>Balance কম!</b>\n\n💳 Buy Coins থেকে balance বাড়াও।",
            parse_mode=ParseMode.HTML,
        )
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        ctx.user_data.clear()
        return ConversationHandler.END

    await query.edit_message_text("⏳ Order দেওয়া হচ্ছে...")

    # ── ডাইনামিক account_fields তৈরি ─────────────────────────────
    order_fields   = cfg.get("order_fields", ["user_id"])
    account_fields: Dict[str, str] = {}
    for field in order_fields:
        if field in ("user_id", "player_id", "target_id"):
            account_fields[field] = player_id
        elif field in ("server_id", "zone_id", "server"):
            account_fields[field] = server_id
        # অন্য কাস্টম ফিল্ড লাগলে এখানে হ্যান্ডেল করুন

    reference_id = f"TG_{user_id}_{uuid.uuid4().hex[:10]}"

    try:
        result = await place_order(
            service_code=service_code,
            reference_id=reference_id,
            account_fields=account_fields,
        )
    except Exception as e:
        logger.exception("place_order exception")
        result = {"success": False, "error": {"message": str(e)}}

    # ── ব্যর্থ হলে রিফান্ড ────────────────────────────────────────
    if not result or not result.get("success"):
        await db.add_balance(user_id, cost, "Refund: Topup failed")
        err = (result or {}).get("error") or {}
        err_msg = err.get("message") if isinstance(err, dict) else str(err)

        await query.edit_message_text(
            "⚠️ Order টি process করা যায়নি — ব্যালেন্স ফেরত দেওয়া হয়েছে।\n"
            "সমস্যা হলে যোগাযোগ করো: @shuvo_9882"
        )
        await _admin_alert(
            query.get_bot(),
            f"⚠️ <b>Topup Failed</b>\n"
            f"User: <code>{user_id}</code>\n"
            f"Service: <code>{service_code}</code>\n"
            f"Ref: <code>{reference_id}</code>\n"
            f"Error: <code>{str(err_msg)[:300]}</code>",
        )
        await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
        ctx.user_data.clear()
        return ConversationHandler.END

    # ── সফল অর্ডার ───────────────────────────────────────────────
    resp_data = result.get("data") or {}
    order_id  = resp_data.get("order_id") or reference_id
    status    = resp_data.get("order_status") or resp_data.get("status") or "Processing"

    await db.save_topup_order(
        user_id      = user_id,
        order_id     = order_id,
        reference_id = reference_id,
        game         = cfg["name"],
        package      = pkg.get("service_name") or service_code,
        player_id    = player_id,
        nickname     = nickname,
        cost         = cost,
        status       = status,
    )

    try:
        await send_order_log(
            order_id     = order_id,
            user_id      = user_id,
            service_name = f"{cfg['name']} — {pkg.get('service_name', service_code)}",
            quantity     = 1,
            link         = "",
            status       = status,
            order_type   = "topup",
            player_id    = player_id,
            nickname     = nickname,
        )
    except Exception:
        logger.exception("send_order_log failed")

    is_telegram = cfg.get("validation_code") == "telegram"
    delivery_note = (
        "⏳ ৫-১৫ মিনিটের মধ্যে সম্পন্ন হবে!" if is_telegram
        else "⏳ ৫-১০ মিনিটের মধ্যে সম্পন্ন হবে!"
    )

    await query.edit_message_text(
        f"✅ <b>Order Successful!</b>\n"
        f"{'─' * 28}\n"
        f"🎮 Service: <b>{cfg['name']}</b>\n"
        f"💎 Package: <code>{pkg.get('service_name', '')}</code>\n"
        f"👤 {'Username' if is_telegram else 'Nickname'}: <b>{nickname or player_id}</b>\n"
        f"🆔 Order ID: <code>{order_id}</code>\n\n"
        f"{delivery_note}\n"
        f"❓ সমস্যা হলে: @shuvo_9882",
        parse_mode=ParseMode.HTML,
    )
    await query.message.reply_text("👇 Menu:", reply_markup=main_keyboard())
    ctx.user_data.clear()
    return ConversationHandler.END