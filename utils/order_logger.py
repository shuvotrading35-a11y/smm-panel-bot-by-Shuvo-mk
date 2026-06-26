"""
order_logger.py
───────────────
Sends a beautifully formatted order notification to a log bot / channel
whenever a new order is placed.

Uses a *separate* bot token (LOG_BOT_TOKEN) so the notification arrives
from a different bot than the main SMM bot.

If LOG_BOT_TOKEN or LOG_CHAT_ID is not set, the module silently does nothing.
"""

import logging
import aiohttp
from config import (
    LOG_BOT_TOKEN, LOG_CHAT_ID,
    LOG_BOT_USERNAME, LOG_OFFICIAL_NAME, LOG_PAYMENT_NAME,
)

logger = logging.getLogger(__name__)

_TG_URL = "https://api.telegram.org/bot{token}/sendMessage"


async def send_order_log(
    order_id:     int | str,
    user_id:      int | str,
    service_name: str,
    quantity:     int,
    link:         str,
    status:       str = "Processing",
    order_type:   str = "smm",       # "smm" অথবা "topup"
    player_id:    str = "",
    nickname:     str = "",
) -> bool:
    if not LOG_BOT_TOKEN or not LOG_CHAT_ID:
        return False

    status_icon = {
        "Processing": "⏳",
        "Pending":    "🕐",
        "Completed":  "✅",
        "Cancelled":  "❌",
        "Partial":    "⚠️",
    }.get(status, "⏳")

    if order_type == "topup":
        is_telegram = "telegram" in service_name.lower() or "✈️" in service_name
        if is_telegram:
            text = (
                f"✈️ 𝗧𝗲𝗹𝗲𝗴𝗿𝗮𝗺 𝗢𝗿𝗱𝗲𝗿 𝗦𝘂𝗯𝗺𝗶𝘁𝘁𝗲𝗱\n"
                f"\n"
                f"🆔 𝗢𝗿𝗱𝗲𝗿 𝗜𝗗: SHUVO-{order_id}\n"
                f"✅ 𝗦𝘁𝗮𝘁𝘂𝘀: {status} {status_icon}\n"
                f"🆔 𝗨𝘀𝗲𝗿 𝗜𝗗: {user_id}\n"
                f"🎯 𝗦𝗲𝗿𝘃𝗶𝗰𝗲: {service_name}\n"
                f"👤 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲: {player_id}\n"
                f"🏷️ 𝗡𝗮𝗺𝗲: {nickname or 'N/A'}\n"
                f"\n"
                f"👮🏻‍♂ 𝗕𝗼𝘁: <a href='https://t.me/{LOG_BOT_USERNAME.lstrip('@')}'>𝗖𝗹𝗶𝗰𝗸 𝗛𝗲𝗿𝗲</a>\n"
                f"📢 𝗢𝗳𝗳𝗶𝗰𝗶𝗮𝗹: <a href='{LOG_OFFICIAL_NAME}'>𝗖𝗹𝗶𝗰𝗸 𝗛𝗲𝗿𝗲</a>\n"
                f"📢 𝗣𝗮𝘆𝗺𝗲𝗻𝘁 𝗣𝗿𝗼𝗼𝗳: <a href='{LOG_PAYMENT_NAME}'>𝗖𝗹𝗶𝗰𝗸 𝗛𝗲𝗿𝗲</a>"
            )
        else:
            text = (
                f"🎮 𝗧𝗼𝗽𝘂𝗽 𝗢𝗿𝗱𝗲𝗿 𝗦𝘂𝗯𝗺𝗶𝘁𝘁𝗲𝗱\n"
                f"\n"
                f"🆔 𝗢𝗿𝗱𝗲𝗿 𝗜𝗗: SHUVO-{order_id}\n"
                f"✅ 𝗦𝘁𝗮𝘁𝘂𝘀: {status} {status_icon}\n"
                f"🆔 𝗨𝘀𝗲𝗿 𝗜𝗗: {user_id}\n"
                f"🎯 𝗦𝗲𝗿𝘃𝗶𝗰𝗲: {service_name}\n"
                f"👤 𝗣𝗹𝗮𝘆𝗲𝗿 𝗜𝗗: {player_id}\n"
                f"🏷️ 𝗡𝗶𝗰𝗸𝗻𝗮𝗺𝗲: {nickname or 'N/A'}\n"
                f"\n"
                f"👮🏻‍♂ 𝗕𝗼𝘁: <a href='https://t.me/{LOG_BOT_USERNAME.lstrip('@')}'>𝗖𝗹𝗶𝗰𝗸 𝗛𝗲𝗿𝗲</a>\n"
                f"📢 𝗢𝗳𝗳𝗶𝗰𝗶𝗮𝗹: <a href='{LOG_OFFICIAL_NAME}'>𝗖𝗹𝗶𝗰𝗸 𝗛𝗲𝗿𝗲</a>\n"
                f"📢 𝗣𝗮𝘆𝗺𝗲𝗻𝘁 𝗣𝗿𝗼𝗼𝗳: <a href='{LOG_PAYMENT_NAME}'>𝗖𝗹𝗶𝗰𝗸 𝗛𝗲𝗿𝗲</a>"
            )
    else:
        text = (
            f"📄 𝗡𝗲𝘄 𝗢𝗿𝗱𝗲𝗿 𝗦𝘂𝗯𝗺𝗶𝘁𝘁𝗲𝗱\n"
            f"\n"
            f"🆔 𝗢𝗿𝗱𝗲𝗿 𝗜𝗗: SHUVO-{order_id}\n"
            f"✅ 𝗦𝘁𝗮𝘁𝘂𝘀: 𝗣𝗿𝗼𝗰𝗲𝘀𝘀𝗶𝗻𝗴 {status_icon}\n"
            f"🆔 𝗨𝘀𝗲𝗿 𝗜𝗗: {user_id}\n"
            f"👍 𝗔𝗺𝗼𝘂𝗻𝘁: {quantity:,} {service_name}\n"
            f"🔗 𝗣𝗼𝘀𝘁 𝗟𝗶𝗻𝗸:\n{link}\n"
            f"\n"
            f"👮🏻‍♂ 𝗕𝗼𝘁: <a href='https://t.me/{LOG_BOT_USERNAME.lstrip('@')}'>𝗖𝗹𝗶𝗰𝗸 𝗛𝗲𝗿𝗲</a>\n"
            f"📢 𝗢𝗳𝗳𝗶𝗰𝗶𝗮𝗹: <a href='{LOG_OFFICIAL_NAME}'>𝗖𝗹𝗶𝗰𝗸 𝗛𝗲𝗿𝗲</a>\n"
            f"📢 𝗣𝗮𝘆𝗺𝗲𝗻𝘁 𝗣𝗿𝗼𝗼𝗳: <a href='{LOG_PAYMENT_NAME}'>𝗖𝗹𝗶𝗰𝗸 𝗛𝗲𝗿𝗲</a>"
        )

    url     = _TG_URL.format(token=LOG_BOT_TOKEN)
    payload = {
        "chat_id":    LOG_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    logger.info(f"[OrderLogger] Order #{order_id} logged to {LOG_CHAT_ID}")
                    return True
                else:
                    logger.warning(f"[OrderLogger] Telegram error: {data.get('description')}")
                    return False
    except Exception as e:
        logger.error(f"[OrderLogger] Failed to send log: {e}")
        return False