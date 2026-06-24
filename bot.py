import asyncio
import logging
import os
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters
)
from config import BOT_TOKEN, ADMIN_IDS
import database as db

# ── Import handlers ───────────────────────────────────────────────
from handlers.user import (
    start, my_account, account_callback, wallet, wallet_callback,
    global_force_join_check, check_banned,
    buy_coins, payment_method_callback, deposit_amount_handler,
    deposit_txn_handler, package_callback, services_list, search_service_prompt, category_callback,
    service_callback, new_order, order_start_callback,
    order_platform_handler, order_category_handler, order_service_handler, order_link_handler,
    order_quantity_handler, order_confirm_callback, my_orders,
    order_refresh_callback, order_refill_callback,
    order_cancel_api_callback, order_tracker, tracker_input_handler,
    daily_bonus, redeem_code, redeem_input_handler, referral,
    leaderboard, leaderboard_callback, my_statistics, vip_membership,
    vip_buy_callback, support, ticket_subject_handler,
    ticket_message_handler, updates_channel, cancel_handler,
    force_join_check,
    ORDER_PLATFORM, ORDER_CATEGORY, ORDER_SERVICE, ORDER_LINK, ORDER_QUANTITY,
    ORDER_CONFIRM, REDEEM_INPUT, TICKET_SUBJECT, TICKET_MESSAGE,
    DEPOSIT_METHOD, DEPOSIT_AMOUNT, DEPOSIT_TXN, TRACKER_INPUT,
)
from handlers.topup import (
    topup_start, topup_game_selected, topup_package_selected,
    topup_player_id, topup_server_id, topup_confirm,
    TOPUP_GAME_SELECT, TOPUP_PACKAGE_SELECT, TOPUP_PLAYER_ID,
    TOPUP_SERVER_ID, TOPUP_CONFIRM,
)
from handlers.admin import (
    admin_panel, bot_stats, user_management, search_user_handler,
    balance_manager, add_bal_id_handler, add_bal_amount_handler,
    admin_user_callback, code_manager, create_code_handler,
    create_code_amount_handler, create_code_uses_handler,
    broadcast, broadcast_type_callback, broadcast_content_handler,
    order_manager, admin_order_search_handler, api_manager,
    sync_services, test_api, service_search, force_join_admin, set_updates_channel,
    add_channel_cmd, remove_channel_cmd, list_channels_cmd,
    ban_system, ban_id_handler, support_manager,
    ticket_reply_callback, ticket_reply_text_handler,
    ticket_close_callback, deposit_approve_callback,
    deposit_reject_callback, vip_manager, set_vip_id_handler,
    set_vip_plan_handler, notification, notification_text_handler,
    export_data, export_callback, database_manager, restart_bot,
    admin_leaderboard, cancel_admin,
    SEARCH_USER, ADD_BAL_ID, ADD_BAL_AMOUNT, BAN_ID,
    CREATE_CODE, CREATE_CODE_AMOUNT, CREATE_CODE_USES,
    BC_TYPE, BC_TEXT, TICKET_REPLY_STATE, ADMIN_ORDER_SEARCH,
    SET_VIP_ID, SET_VIP_PLAN, NOTIFICATION_TEXT,
)

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/bot.log"),
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ── Shared filters ────────────────────────────────────────────────
CANCEL_FILTER = filters.Regex(r"^(❌ ᴄᴀɴᴄᴇʟ|❌ Cancel|/cancel)$")
ADMIN_FILTER  = filters.User(user_id=ADMIN_IDS)


# ─────────────────────────────────────────────────────────────────
#  ERROR HANDLER
# ─────────────────────────────────────────────────────────────────
async def error_handler(update: object, context) -> None:
    import traceback
    err = context.error

    # Harmless Telegram errors — silently ignore, no admin alert needed
    harmless = (
        "Message is not modified",
        "Query is too old",
        "message to edit not found",
        "Message to delete not found",
    )
    if any(h in str(err) for h in harmless):
        return

    tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
    logger.error(f"Exception: {tb}")

    # Admin-কে error জানাও
    from config import ADMIN_IDS
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"🔴 <b>Bot Error</b>\n\n<code>{str(err)[:300]}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────
#  BUILD APPLICATION
# ─────────────────────────────────────────────────────────────────
def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    # ── Global middlewares (run BEFORE every other handler) ────────
    from telegram.ext import MessageHandler as _MH, CallbackQueryHandler as _CQH, filters as _filters
    app.add_handler(_MH(_filters.ALL, check_banned), group=-2)
    app.add_handler(_CQH(check_banned), group=-2)
    app.add_handler(_MH(_filters.ALL, global_force_join_check), group=-1)
    app.add_handler(_CQH(global_force_join_check), group=-1)

    # Register global error handler
    # ── Game Topup ConversationHandler ───────────────────────────
    topup_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^🎮 ɢᴀᴍᴇ ᴛᴏᴘᴜᴘ$"), topup_start),
        ],
        states={
            TOPUP_GAME_SELECT:    [CallbackQueryHandler(topup_game_selected,    pattern=r"^(tg:.+|topup_cancel)$")],
            TOPUP_PACKAGE_SELECT: [CallbackQueryHandler(topup_package_selected, pattern=r"^(tp:.+|topup_game_back|topup_cancel)$")],
            TOPUP_PLAYER_ID:      [MessageHandler(filters.TEXT & ~filters.COMMAND, topup_player_id)],
            TOPUP_SERVER_ID:      [MessageHandler(filters.TEXT & ~filters.COMMAND, topup_server_id)],
            TOPUP_CONFIRM:        [CallbackQueryHandler(topup_confirm, pattern=r"^(topup_confirm|topup_cancel)$")],
        },
        fallbacks=[MessageHandler(filters.Regex(r"^❌ ᴄᴀɴᴄᴇʟ$"), cancel_handler)],
        allow_reentry=True,
        per_message=False,
        conversation_timeout=300,
    )
    app.add_handler(topup_conv)

    app.add_error_handler(error_handler)

    # ── /start ────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", start))

    # ── Admin commands ────────────────────────────────────────────
    app.add_handler(CommandHandler("admin",          admin_panel))
    app.add_handler(CommandHandler("syncservices",   sync_services))
    app.add_handler(CommandHandler("testapi",        test_api))
    app.add_handler(CommandHandler("search",         service_search))
    app.add_handler(CommandHandler("setupdates",     set_updates_channel))
    app.add_handler(CommandHandler("addchannel",     add_channel_cmd))
    app.add_handler(CommandHandler("removechannel",  remove_channel_cmd))
    app.add_handler(CommandHandler("channels",       list_channels_cmd))
    app.add_handler(CommandHandler("export",         export_data))
    app.add_handler(CommandHandler("stats",          bot_stats))

    # ── Standalone CallbackQuery handlers (outside ConversationHandlers) ──
    app.add_handler(CallbackQueryHandler(force_join_check,            pattern=r"^fj_check$"))
    app.add_handler(CallbackQueryHandler(account_callback,            pattern=r"^acc_"))
    # wallet_callback handled inside deposit_conv ConversationHandler
    app.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer("📩 যোগাযোগ: @shuvo_9882", show_alert=True), pattern=r"^contact_admin$"))
    app.add_handler(CallbackQueryHandler(leaderboard_callback,        pattern=r"^lb:"))
    app.add_handler(CallbackQueryHandler(vip_buy_callback,            pattern=r"^vip_buy:"))
    app.add_handler(CallbackQueryHandler(order_refresh_callback,      pattern=r"^order_refresh:"))
    app.add_handler(CallbackQueryHandler(order_refill_callback,       pattern=r"^order_refill:"))
    app.add_handler(CallbackQueryHandler(order_cancel_api_callback,   pattern=r"^order_cancel_api:"))
    app.add_handler(CallbackQueryHandler(category_callback,           pattern=r"^(cat(_back|:.+)|svc_list_back|platform(:.+|_back)|catidx:\d+)$"))
    app.add_handler(CallbackQueryHandler(service_callback,            pattern=r"^svc(_back|:.+)$"))  # svc_back = service detail → service list
    app.add_handler(CallbackQueryHandler(admin_user_callback,         pattern=r"^adm_(ban|unban|bal_add|bal_rem|msg):"))
    app.add_handler(CallbackQueryHandler(deposit_approve_callback,    pattern=r"^dep_approve:"))
    app.add_handler(CallbackQueryHandler(deposit_reject_callback,     pattern=r"^dep_reject:"))
    app.add_handler(CallbackQueryHandler(ticket_close_callback,       pattern=r"^ticket_close:"))
    app.add_handler(CallbackQueryHandler(export_callback,             pattern=r"^export:"))

    # ═══════════════════════════════════════════════════════════════
    #  USER CONVERSATIONS
    # ═══════════════════════════════════════════════════════════════

    # ── New Order ─────────────────────────────────────────────────
    order_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^🛒 ɴᴇᴡ ᴏʀᴅᴇʀ$"), new_order),
            CallbackQueryHandler(order_start_callback, pattern=r"^order_start:"),
        ],
        states={
            ORDER_PLATFORM: [CallbackQueryHandler(order_platform_handler, pattern=r"^(platform(:.+|_back)|catidx:\d+)$")],
            ORDER_CATEGORY: [CallbackQueryHandler(order_category_handler, pattern=r"^cat:.+")],
            ORDER_SERVICE:  [CallbackQueryHandler(order_service_handler,  pattern=r"^svc:.+")],
            ORDER_LINK:     [MessageHandler(filters.TEXT & ~CANCEL_FILTER, order_link_handler)],
            ORDER_QUANTITY: [MessageHandler(filters.TEXT & ~CANCEL_FILTER, order_quantity_handler)],
            ORDER_CONFIRM:  [CallbackQueryHandler(order_confirm_callback,  pattern=r"^order_(confirm|cancel)")],
        },
        fallbacks=[MessageHandler(CANCEL_FILTER, cancel_handler)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(order_conv)

    # ── Order Tracker ─────────────────────────────────────────────
    tracker_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^🔎 ᴏʀᴅᴇʀ ᴛʀᴀᴄᴋᴇʀ$"), order_tracker)],
        states={
            TRACKER_INPUT: [MessageHandler(filters.TEXT & ~CANCEL_FILTER, tracker_input_handler)],
        },
        fallbacks=[MessageHandler(CANCEL_FILTER, cancel_handler)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(tracker_conv)

    # ── Redeem Code ───────────────────────────────────────────────
    redeem_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^🎁 ʀᴇᴅᴇᴇᴍ ᴄᴏᴅᴇ$"), redeem_code)],
        states={
            REDEEM_INPUT: [MessageHandler(filters.TEXT & ~CANCEL_FILTER, redeem_input_handler)],
        },
        fallbacks=[MessageHandler(CANCEL_FILTER, cancel_handler)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(redeem_conv)

    # ── Support Ticket ────────────────────────────────────────────
    support_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^☎️ ꜱᴜᴘᴘᴏʀᴛ$"), support)],
        states={
            TICKET_SUBJECT: [MessageHandler(filters.TEXT & ~CANCEL_FILTER, ticket_subject_handler)],
            TICKET_MESSAGE: [MessageHandler(filters.TEXT & ~CANCEL_FILTER, ticket_message_handler)],
        },
        fallbacks=[MessageHandler(CANCEL_FILTER, cancel_handler)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(support_conv)

    # ── Deposit / Buy Coins ───────────────────────────────────────
    deposit_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^💳 ʙᴜʏ ᴄᴏɪɴꜱ$"), buy_coins),
            CallbackQueryHandler(wallet_callback, pattern=r"^wallet_(add|history|refresh)$"),
        ],
        states={
            DEPOSIT_METHOD: [
                CallbackQueryHandler(package_callback,        pattern=r"^(pkg:.+|pkg_back|contact_admin)$"),
                CallbackQueryHandler(payment_method_callback, pattern=r"^pay_method:.+$"),
            ],
            DEPOSIT_AMOUNT: [
                MessageHandler(filters.TEXT & ~CANCEL_FILTER, deposit_amount_handler),
            ],
            DEPOSIT_TXN: [
                MessageHandler(filters.TEXT & ~CANCEL_FILTER, deposit_txn_handler),
            ],
        },
        fallbacks=[
            MessageHandler(CANCEL_FILTER, cancel_handler),
        ],
        allow_reentry=True,
        per_message=False,
        conversation_timeout=120,
    )
    app.add_handler(deposit_conv)

    # ═══════════════════════════════════════════════════════════════
    #  ADMIN CONVERSATIONS
    # ═══════════════════════════════════════════════════════════════

    # ── User Management ───────────────────────────────────────────
    user_mgmt_conv = ConversationHandler(
        entry_points=[MessageHandler(
            filters.Regex(r"^👥 ᴜꜱᴇʀ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ$") & ADMIN_FILTER,
            user_management
        )],
        states={
            SEARCH_USER: [MessageHandler(filters.TEXT & ~CANCEL_FILTER, search_user_handler)],
        },
        fallbacks=[MessageHandler(CANCEL_FILTER, cancel_admin)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(user_mgmt_conv)

    # ── Balance Manager ───────────────────────────────────────────
    bal_conv = ConversationHandler(
        entry_points=[MessageHandler(
            filters.Regex(r"^💰 ʙᴀʟᴀɴᴄᴇ ᴍᴀɴᴀɢᴇʀ$") & ADMIN_FILTER,
            balance_manager
        )],
        states={
            ADD_BAL_ID:     [MessageHandler(filters.TEXT & ~CANCEL_FILTER, add_bal_id_handler)],
            ADD_BAL_AMOUNT: [MessageHandler(filters.TEXT & ~CANCEL_FILTER, add_bal_amount_handler)],
        },
        fallbacks=[MessageHandler(CANCEL_FILTER, cancel_admin)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(bal_conv)

    # ── Code Manager ─────────────────────────────────────────────
    code_conv = ConversationHandler(
        entry_points=[MessageHandler(
            filters.Regex(r"^🎁 ᴄᴏᴅᴇ ᴍᴀɴᴀɢᴇʀ$") & ADMIN_FILTER,
            code_manager
        )],
        states={
            CREATE_CODE:        [MessageHandler(filters.TEXT & ~CANCEL_FILTER, create_code_handler)],
            CREATE_CODE_AMOUNT: [MessageHandler(filters.TEXT & ~CANCEL_FILTER, create_code_amount_handler)],
            CREATE_CODE_USES:   [MessageHandler(filters.TEXT & ~CANCEL_FILTER, create_code_uses_handler)],
        },
        fallbacks=[MessageHandler(CANCEL_FILTER, cancel_admin)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(code_conv)

    # ── Broadcast ─────────────────────────────────────────────────
    bc_conv = ConversationHandler(
        entry_points=[MessageHandler(
            filters.Regex(r"^📢 ʙʀᴏᴀᴅᴄᴀꜱᴛ$") & ADMIN_FILTER,
            broadcast
        )],
        states={
            BC_TYPE: [CallbackQueryHandler(broadcast_type_callback, pattern=r"^bc_type:")],
            BC_TEXT: [MessageHandler(
                (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL)
                & ~CANCEL_FILTER,
                broadcast_content_handler
            )],
        },
        fallbacks=[MessageHandler(CANCEL_FILTER, cancel_admin)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(bc_conv)

    # ── Ban System ────────────────────────────────────────────────
    ban_conv = ConversationHandler(
        entry_points=[MessageHandler(
            filters.Regex(r"^🚫 ʙᴀɴ ꜱʏꜱᴛᴇᴍ$") & ADMIN_FILTER,
            ban_system
        )],
        states={
            BAN_ID: [MessageHandler(filters.TEXT & ~CANCEL_FILTER, ban_id_handler)],
        },
        fallbacks=[MessageHandler(CANCEL_FILTER, cancel_admin)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(ban_conv)

    # ── Support Manager (ticket reply) ────────────────────────────
    ticket_reply_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ticket_reply_callback, pattern=r"^ticket_reply:")],
        states={
            TICKET_REPLY_STATE: [MessageHandler(filters.TEXT & ~CANCEL_FILTER, ticket_reply_text_handler)],
        },
        fallbacks=[MessageHandler(CANCEL_FILTER, cancel_admin)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(ticket_reply_conv)

    # ── Order Manager ─────────────────────────────────────────────
    order_mgr_conv = ConversationHandler(
        entry_points=[MessageHandler(
            filters.Regex(r"^📦 ᴏʀᴅᴇʀ ᴍᴀɴᴀɢᴇʀ$") & ADMIN_FILTER,
            order_manager
        )],
        states={
            ADMIN_ORDER_SEARCH: [MessageHandler(filters.TEXT & ~CANCEL_FILTER, admin_order_search_handler)],
        },
        fallbacks=[MessageHandler(CANCEL_FILTER, cancel_admin)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(order_mgr_conv)

    # ── VIP Manager ───────────────────────────────────────────────
    vip_conv = ConversationHandler(
        entry_points=[MessageHandler(
            filters.Regex(r"^💎 ᴠɪᴘ ᴍᴀɴᴀɢᴇʀ$") & ADMIN_FILTER,
            vip_manager
        )],
        states={
            SET_VIP_ID:   [MessageHandler(filters.TEXT & ~CANCEL_FILTER, set_vip_id_handler)],
            SET_VIP_PLAN: [MessageHandler(filters.TEXT & ~CANCEL_FILTER, set_vip_plan_handler)],
        },
        fallbacks=[MessageHandler(CANCEL_FILTER, cancel_admin)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(vip_conv)

    # ── Notification ──────────────────────────────────────────────
    notif_conv = ConversationHandler(
        entry_points=[MessageHandler(
            filters.Regex(r"^🔔 ɴᴏᴛɪꜰɪᴄᴀᴛɪᴏɴ$") & ADMIN_FILTER,
            notification
        )],
        states={
            NOTIFICATION_TEXT: [MessageHandler(filters.TEXT & ~CANCEL_FILTER, notification_text_handler)],
        },
        fallbacks=[MessageHandler(CANCEL_FILTER, cancel_admin)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(notif_conv)

    # ═══════════════════════════════════════════════════════════════
    #  SIMPLE REPLY KEYBOARD HANDLERS (MessageHandlers)
    # ═══════════════════════════════════════════════════════════════
    app.add_handler(MessageHandler(filters.Regex(r"^📊 ꜱᴇʀᴠɪᴄᴇꜱ ʟɪꜱᴛ$"),  services_list))
    app.add_handler(MessageHandler(filters.Regex(r"^🔍 ꜱᴇᴀʀᴄʜ ꜱᴇʀᴠɪᴄᴇ$"), search_service_prompt))
    app.add_handler(MessageHandler(filters.Regex(r"^👤 ᴍʏ ᴀᴄᴄᴏᴜɴᴛ$"),     my_account))
    app.add_handler(MessageHandler(filters.Regex(r"^📦 ᴍʏ ᴏʀᴅᴇʀꜱ$"),      my_orders))
    app.add_handler(MessageHandler(filters.Regex(r"^💰 ᴡᴀʟʟᴇᴛ$"),         wallet))
    app.add_handler(MessageHandler(filters.Regex(r"^🎯 ᴅᴀɪʟʏ ʙᴏɴᴜꜱ$"),   daily_bonus))
    app.add_handler(MessageHandler(filters.Regex(r"^👥 ʀᴇꜰᴇʀʀᴀʟ$"),       referral))
    app.add_handler(MessageHandler(filters.Regex(r"^🏆 ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ$"),    leaderboard))
    app.add_handler(MessageHandler(filters.Regex(r"^📈 ᴍʏ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ$"), my_statistics))
    app.add_handler(MessageHandler(filters.Regex(r"^⭐ ᴠɪᴘ ᴍᴇᴍʙᴇʀꜱʜɪᴘ$"), vip_membership))
    app.add_handler(MessageHandler(filters.Regex(r"^📢 ᴜᴘᴅᴀᴛᴇꜱ$"),        updates_channel))

    # ── Admin reply keyboard ──────────────────────────────────────
    app.add_handler(MessageHandler(
        filters.Regex(r"^📊 ʙᴏᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ$") & ADMIN_FILTER,   bot_stats))
    app.add_handler(MessageHandler(
        filters.Regex(r"^⚙️ ᴀᴘɪ ᴍᴀɴᴀɢᴇʀ$") & ADMIN_FILTER,      api_manager))
    app.add_handler(MessageHandler(
        filters.Regex(r"^📣 ꜰᴏʀᴄᴇ ᴊᴏɪɴ$") & ADMIN_FILTER,        force_join_admin))
    app.add_handler(MessageHandler(
        filters.Regex(r"^☎️ ꜱᴜᴘᴘᴏʀᴛ ᴍᴀɴᴀɢᴇʀ$") & ADMIN_FILTER,  support_manager))
    app.add_handler(MessageHandler(
        filters.Regex(r"^🛒 ꜱᴇʀᴠɪᴄᴇ ᴍᴀɴᴀɢᴇʀ$") & ADMIN_FILTER,  sync_services))
    app.add_handler(MessageHandler(
        filters.Regex(r"^🏆 ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ$") & ADMIN_FILTER,       admin_leaderboard))
    app.add_handler(MessageHandler(
        filters.Regex(r"^📤 ᴇxᴘᴏʀᴛ ᴅᴀᴛᴀ$") & ADMIN_FILTER,       export_data))
    app.add_handler(MessageHandler(
        filters.Regex(r"^🗄 ᴅᴀᴛᴀʙᴀꜱᴇ ᴍᴀɴᴀɢᴇʀ$") & ADMIN_FILTER,  database_manager))
    app.add_handler(MessageHandler(
        filters.Regex(r"^🔄 ʀᴇꜱᴛᴀʀᴛ ʙᴏᴛ$") & ADMIN_FILTER,       restart_bot))
    app.add_handler(MessageHandler(
        filters.Regex(r"^🧹 ᴄʟᴇᴀɴ ᴜᴘ$") & ADMIN_FILTER,
        lambda u, c: u.message.reply_text("🧹 Clean up not implemented yet.")
    ))
    app.add_handler(MessageHandler(
        filters.Regex(r"^🏠 ᴍᴀɪɴ ᴍᴇɴᴜ$") & ADMIN_FILTER,
        lambda u, c: u.message.reply_text(
            "🏠 Main Menu",
            reply_markup=__import__(
                "keyboards.reply", fromlist=["main_keyboard"]
            ).main_keyboard()
        )
    ))

    return app


# ─────────────────────────────────────────────────────────────────
#  STARTUP / SHUTDOWN HOOKS
# ─────────────────────────────────────────────────────────────────
async def on_startup(app: Application):
    logger.info("Initialising database...")
    await db.init_db()
    logger.info("Database ready.")
    for admin_id in ADMIN_IDS:
        try:
            await app.bot.send_message(admin_id, "🚀 Bot started successfully!")
        except Exception:
            pass


async def on_shutdown(app: Application):
    from api.smm_api import smm_api
    await smm_api.close()
    logger.info("API session closed.")


# ─────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set. Check your .env file.")

    os.makedirs("data", exist_ok=True)

    app = build_app()
    app.post_init     = on_startup
    app.post_shutdown = on_shutdown

    logger.info("Starting Shuvo SMM Bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
