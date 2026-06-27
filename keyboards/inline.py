from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram._utils.types import JSONDict
from config import VIP_PLANS, PAYMENT_METHODS
from typing import Optional


class StyledButton(InlineKeyboardButton):
    """Bot API 9.4 style parameter support"""

    def __init__(self, text: str, style: Optional[str] = None, **kwargs):
        super().__init__(text=text, **kwargs)
        self._style = style

    def to_dict(self, recursive: bool = True) -> JSONDict:
        data = super().to_dict(recursive=recursive)
        if self._style:
            data["style"] = self._style
        return data


def confirm_order_kb(service_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            StyledButton("✅ Confirm", style="success", callback_data=f"order_confirm:{service_id}"),
            StyledButton("❌ Cancel",  style="danger",  callback_data="order_cancel"),
        ]
    ])


def order_actions_kb(order_id: int, api_order_id: str, refill: bool = False, cancel: bool = False) -> InlineKeyboardMarkup:
    row = [StyledButton("🔄 Refresh", style="primary", callback_data=f"order_refresh:{order_id}")]
    if refill:
        row.append(StyledButton("♻️ Refill", style="success", callback_data=f"order_refill:{order_id}"))
    return InlineKeyboardMarkup([row])


def payment_methods_kb() -> InlineKeyboardMarkup:
    rows = []
    methods = list(PAYMENT_METHODS.items())
    for i in range(0, len(methods), 2):
        row = []
        for key, label in methods[i:i+2]:
            row.append(StyledButton(label, style="primary", callback_data=f"pay_method:{key}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def coin_packages_kb() -> InlineKeyboardMarkup:
    from config import COIN_PACKAGES
    rows = []
    badges = {1500: " ⭐ POPULAR", 3000: " 🔥 BEST VALUE", 7000: " 💎 PREMIUM"}
    for coins, price in COIN_PACKAGES:
        badge = badges.get(coins, "")
        rows.append([StyledButton(
            f"🛍️  {coins:,} Coins  —  {price}{badge}",
            style="success",
            callback_data=f"pkg:{coins}:{price}"
        )])
    rows.append([StyledButton("✏️  Custom Amount", style="primary", callback_data="pkg:custom")])
    rows.append([InlineKeyboardButton("💬  Contact Admin", url="https://t.me/shuvo_9882")])
    return InlineKeyboardMarkup(rows)


def pkg_payment_kb() -> InlineKeyboardMarkup:
    from config import PAYMENT_METHODS
    rows = []
    methods = list(PAYMENT_METHODS.items())
    for key, label in methods:
        rows.append([StyledButton(f"{label}", style="success", callback_data=f"pay_method:{key}")])
    rows.append([StyledButton("⬅️  Back", style="danger", callback_data="pkg_back")])
    return InlineKeyboardMarkup(rows)


def deposit_approve_kb(dep_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        StyledButton("✅ Approve", style="success", callback_data=f"dep_approve:{dep_id}"),
        StyledButton("❌ Reject",  style="danger",  callback_data=f"dep_reject:{dep_id}"),
    ]])


def vip_plans_kb() -> InlineKeyboardMarkup:
    rows = []
    for key, plan in VIP_PLANS.items():
        rows.append([StyledButton(
            f"{plan['name']} — ${plan['price']}/mo",
            style="primary",
            callback_data=f"vip_buy:{key}"
        )])
    return InlineKeyboardMarkup(rows)


def leaderboard_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        StyledButton("🥇 Referrers", style="primary", callback_data="lb:referrers"),
        StyledButton("🥈 Buyers",    style="success", callback_data="lb:buyers"),
        StyledButton("🥉 Orders",    style="danger", callback_data="lb:orders"),
    ]])


def wallet_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [StyledButton("💳 Add Funds", style="success", callback_data="wallet_add")],
        [StyledButton("📜 History",   style="primary", callback_data="wallet_history")],
    ])


def account_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            StyledButton("💳 Deposit History",  style="danger", callback_data="acc_deposits"),
            StyledButton("📤 Transactions",     style="primary", callback_data="acc_transactions"),
        ],
        [StyledButton("🔄 Refresh", style="success", callback_data="acc_refresh")],
    ])


def ticket_reply_kb(ticket_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        StyledButton("💬 Reply", style="primary", callback_data=f"ticket_reply:{ticket_id}:{user_id}"),
        StyledButton("✅ Close", style="success", callback_data=f"ticket_close:{ticket_id}"),
    ]])


def broadcast_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            StyledButton("📝 Text",     style="success", callback_data="bc_type:text"),
            StyledButton("🖼 Photo",    style="primary", callback_data="bc_type:photo"),
        ],
        [
            StyledButton("🎥 Video",    style="danger", callback_data="bc_type:video"),
            StyledButton("📄 Document", style="primary", callback_data="bc_type:document"),
        ],
        [StyledButton("❌ Cancel", style="danger", callback_data="bc_type:cancel")],
    ])


def export_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [StyledButton("👥 Users CSV",  style="success", callback_data="export:users")],
        [StyledButton("📦 Orders CSV", style="primary", callback_data="export:orders")],
    ])


def admin_user_kb(target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            StyledButton("➕ Add Balance",    style="success", callback_data=f"adm_bal_add:{target_id}"),
            StyledButton("➖ Remove Balance",  style="danger",  callback_data=f"adm_bal_rem:{target_id}"),
        ],
        [
            StyledButton("🚫 Ban",   style="danger",  callback_data=f"adm_ban:{target_id}"),
            StyledButton("✅ Unban", style="success", callback_data=f"adm_unban:{target_id}"),
        ],
        [StyledButton("📩 Message", style="primary", callback_data=f"adm_msg:{target_id}")],
    ])


def force_join_kb(channels: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        name = ch.get("channel_name") or ch["channel_id"]
        link = ch.get("invite_link") or f"https://t.me/{ch['channel_id'].lstrip('@')}"
        rows.append([InlineKeyboardButton(f"📢 {name}", url=link)])
    rows.append([StyledButton("✅ I've Joined — Check", style="danger", callback_data="fj_check")])
    return InlineKeyboardMarkup(rows)


def categories_kb(categories: list[str], icons: dict, updates_channel: str = "") -> InlineKeyboardMarkup:
    PLATFORM_ORDER = [
        "facebook", "instagram", "tiktok", "youtube",
        "telegram", "twitter", "spotify", "website",
    ]
    PLATFORM_LABELS = {
        "facebook":  "📘 Facebook",
        "instagram": "📱 Instagram",
        "tiktok":    "🎵 TikTok",
        "youtube":   "📺 YouTube",
        "telegram":  "✈️ Telegram",
        "twitter":   "🐦 Twitter / X",
        "spotify":   "🎧 Spotify",
        "website":   "🌐 Website",
    }

    def get_platform(cat: str) -> str:
        cl = cat.lower()
        for p in PLATFORM_ORDER:
            if p in cl:
                return p
        return "other"

    grouped: dict[str, list[str]] = {}
    for cat in categories:
        p = get_platform(cat)
        grouped.setdefault(p, [])
        if cat not in grouped[p]:
            grouped[p].append(cat)

    rows = []
    platforms_present = [p for p in PLATFORM_ORDER if p in grouped]
    if "other" in grouped:
        platforms_present.append("other")

    for i in range(0, len(platforms_present), 2):
        row = []
        for p in platforms_present[i:i+2]:
            label = PLATFORM_LABELS.get(p, f"🔹 {p.title()}")
            row.append(StyledButton(label, style="success", callback_data=f"platform:{p}"))
        rows.append(row)

    if updates_channel:
        rows.append([InlineKeyboardButton("📢 Join Updates Channel", url=updates_channel)])

    return InlineKeyboardMarkup(rows)


def platform_categories_kb(platform: str, categories: list[str], icons: dict) -> InlineKeyboardMarkup:
    rows = []
    for idx, cat in enumerate(categories):
        icon = next((v for k, v in icons.items() if k.lower() in cat.lower()), "\U0001f539")
        rows.append([StyledButton(f"{icon}  {cat}", style="success", callback_data=f"catidx:{idx}")])
    rows.append([StyledButton("⬅️  Back", style="danger", callback_data="platform_back")])
    return InlineKeyboardMarkup(rows)


def services_kb(services: list[dict], category: str) -> InlineKeyboardMarkup:
    rows = []
    for svc in services[:25]:
        rows.append([StyledButton(
            f"\U0001f4e6  {svc['name']}",
            style="danger",
            callback_data=f"svc:{svc['service_id']}"
        )])
    rows.append([StyledButton("⬅️  Back", style="success", callback_data="svc_list_back")])
    return InlineKeyboardMarkup(rows)


def service_detail_kb(service_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [StyledButton("🛒  Order Now", style="success", callback_data=f"order_start:{service_id}")],
        [StyledButton("⬅️  Back",      style="danger",  callback_data="svc_back")],
    ])


def order_categories_kb(categories: list[str], icons: dict) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(categories), 2):
        row = []
        for cat in categories[i:i+2]:
            icon = next((v for k, v in icons.items() if k.lower() in cat.lower()), "\U0001f539")
            row.append(StyledButton(f"{icon} {cat}", style="primary", callback_data=f"cat:{cat[:30]}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)