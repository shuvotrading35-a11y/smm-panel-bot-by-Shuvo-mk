from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from config import VIP_PLANS, PAYMENT_METHODS


def confirm_order_kb(service_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data=f"order_confirm:{service_id}"),
            InlineKeyboardButton("❌ Cancel",  callback_data="order_cancel"),
        ]
    ])


def order_actions_kb(order_id: int, api_order_id: str, refill: bool = False, cancel: bool = False) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton("🔄 Refresh", callback_data=f"order_refresh:{order_id}")]
    if refill:
        row.append(InlineKeyboardButton("♻️ Refill",  callback_data=f"order_refill:{order_id}"))
    if cancel:
        row.append(InlineKeyboardButton("❌ Cancel",   callback_data=f"order_cancel_api:{order_id}"))
    return InlineKeyboardMarkup([row])


def payment_methods_kb() -> InlineKeyboardMarkup:
    rows = []
    methods = list(PAYMENT_METHODS.items())
    for i in range(0, len(methods), 2):
        row = []
        for key, label in methods[i:i+2]:
            row.append(InlineKeyboardButton(label, callback_data=f"pay_method:{key}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def coin_packages_kb() -> InlineKeyboardMarkup:
    """Coin package selection — shown first in buy coins flow."""
    from config import COIN_PACKAGES
    rows = []
    # Badge for popular/best packages
    badges = {1500: " ⭐ POPULAR", 3000: " 🔥 BEST VALUE", 7000: " 💎 PREMIUM"}
    for coins, price in COIN_PACKAGES:
        badge = badges.get(coins, "")
        rows.append([InlineKeyboardButton(
            f"🛍️  {coins:,} Coins  —  {price}{badge}",
            callback_data=f"pkg:{coins}:{price}"
        )])
    rows.append([InlineKeyboardButton("✏️  Custom Amount", callback_data="pkg:custom")])
    rows.append([InlineKeyboardButton("💬  Contact: @shuvo_9882", callback_data="contact_admin")])
    return InlineKeyboardMarkup(rows)


def pkg_payment_kb() -> InlineKeyboardMarkup:
    """Payment method selection — shown after package is chosen."""
    from config import PAYMENT_METHODS
    rows = []
    methods = list(PAYMENT_METHODS.items())
    for key, label in methods:
        rows.append([InlineKeyboardButton(f"{label}", callback_data=f"pay_method:{key}")])
    rows.append([InlineKeyboardButton("⬅️  Back", callback_data="pkg_back")])
    return InlineKeyboardMarkup(rows)


def deposit_approve_kb(dep_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"dep_approve:{dep_id}"),
        InlineKeyboardButton("❌ Reject",  callback_data=f"dep_reject:{dep_id}"),
    ]])


def vip_plans_kb() -> InlineKeyboardMarkup:
    rows = []
    for key, plan in VIP_PLANS.items():
        rows.append([InlineKeyboardButton(
            f"{plan['name']} — ${plan['price']}/mo",
            callback_data=f"vip_buy:{key}"
        )])
    return InlineKeyboardMarkup(rows)


def leaderboard_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🥇 Referrers", callback_data="lb:referrers"),
        InlineKeyboardButton("🥈 Buyers",    callback_data="lb:buyers"),
        InlineKeyboardButton("🥉 Orders",    callback_data="lb:orders"),
    ]])


def wallet_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Add Funds", callback_data="wallet_add")],
        [InlineKeyboardButton("📜 History",   callback_data="wallet_history")],
    ])


def account_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 Deposit History",     callback_data="acc_deposits"),
            InlineKeyboardButton("📤 Transactions",        callback_data="acc_transactions"),
        ],
        [InlineKeyboardButton("🔄 Refresh", callback_data="acc_refresh")],
    ])


def ticket_reply_kb(ticket_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("💬 Reply",       callback_data=f"ticket_reply:{ticket_id}:{user_id}"),
        InlineKeyboardButton("✅ Close",        callback_data=f"ticket_close:{ticket_id}"),
    ]])


def broadcast_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Text",     callback_data="bc_type:text"),
            InlineKeyboardButton("🖼 Photo",    callback_data="bc_type:photo"),
        ],
        [
            InlineKeyboardButton("🎥 Video",    callback_data="bc_type:video"),
            InlineKeyboardButton("📄 Document", callback_data="bc_type:document"),
        ],
        [InlineKeyboardButton("❌ Cancel",      callback_data="bc_type:cancel")],
    ])


def export_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Users CSV",   callback_data="export:users")],
        [InlineKeyboardButton("📦 Orders CSV",  callback_data="export:orders")],
    ])


def admin_user_kb(target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add Balance",    callback_data=f"adm_bal_add:{target_id}"),
            InlineKeyboardButton("➖ Remove Balance",  callback_data=f"adm_bal_rem:{target_id}"),
        ],
        [
            InlineKeyboardButton("🚫 Ban",            callback_data=f"adm_ban:{target_id}"),
            InlineKeyboardButton("✅ Unban",           callback_data=f"adm_unban:{target_id}"),
        ],
        [InlineKeyboardButton("📩 Message",           callback_data=f"adm_msg:{target_id}")],
    ])


def force_join_kb(channels: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        name = ch.get("channel_name") or ch["channel_id"]
        link = ch.get("invite_link") or f"https://t.me/{ch['channel_id'].lstrip('@')}"
        rows.append([InlineKeyboardButton(f"📢 {name}", url=link)])
    rows.append([InlineKeyboardButton("✅ I've Joined — Check", callback_data="fj_check")])
    return InlineKeyboardMarkup(rows)


def categories_kb(categories: list[str], icons: dict) -> InlineKeyboardMarkup:
    # Group categories by platform (first word / keyword match)
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
    # Show one button per platform (clicking opens sub-categories or direct services)
    platforms_present = [p for p in PLATFORM_ORDER if p in grouped]
    if "other" in grouped:
        platforms_present.append("other")

    for i in range(0, len(platforms_present), 2):
        row = []
        for p in platforms_present[i:i+2]:
            label = PLATFORM_LABELS.get(p, f"🔹 {p.title()}")
            row.append(InlineKeyboardButton(label, callback_data=f"platform:{p}"))
        rows.append(row)

    return InlineKeyboardMarkup(rows)


def platform_categories_kb(platform: str, categories: list[str], icons: dict) -> InlineKeyboardMarkup:
    """Sub-menu: all categories under a platform. Full-width buttons, back goes to platform list."""
    rows = []
    for idx, cat in enumerate(categories):
        icon = next((v for k, v in icons.items() if k.lower() in cat.lower()), "\U0001f539")
        # Show full name — one button per row (full width)
        rows.append([InlineKeyboardButton(f"{icon}  {cat}", callback_data=f"catidx:{idx}")])
    rows.append([InlineKeyboardButton("\U00002B05\uFE0F  Back", callback_data="platform_back")])
    return InlineKeyboardMarkup(rows)


def services_kb(services: list[dict], category: str) -> InlineKeyboardMarkup:
    rows = []
    for svc in services[:25]:
        # Full service name, one per row
        rows.append([InlineKeyboardButton(
            f"\U0001f4e6  {svc['name']}",
            callback_data=f"svc:{svc['service_id']}"
        )])
    rows.append([InlineKeyboardButton("\U00002B05\uFE0F  Back", callback_data="svc_list_back")])
    return InlineKeyboardMarkup(rows)


def service_detail_kb(service_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f6d2  Order Now", callback_data=f"order_start:{service_id}")],
        [InlineKeyboardButton("\U00002B05\uFE0F  Back",      callback_data="svc_back")],
    ])


def order_categories_kb(categories: list[str], icons: dict) -> InlineKeyboardMarkup:
    """Used in New Order flow — direct category buttons (no platform grouping)."""
    rows = []
    for i in range(0, len(categories), 2):
        row = []
        for cat in categories[i:i+2]:
            icon = next((v for k, v in icons.items() if k.lower() in cat.lower()), "\U0001f539")
            row.append(InlineKeyboardButton(f"{icon} {cat}", callback_data=f"cat:{cat[:30]}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)