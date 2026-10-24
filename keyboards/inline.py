from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from config import VIP_PLANS, PAYMENT_METHODS
from typing import Optional


class StyledButton(InlineKeyboardButton):
    """Wrapper — style param accepted but NOT sent to Telegram (unsupported)"""

    def __init__(self, text: str, style: Optional[str] = None, **kwargs):
        super().__init__(text=text, **kwargs)
        # style is intentionally ignored — Telegram rejects unknown button fields


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
    for item in COIN_PACKAGES:
        amount, price = item[0], item[1]
        bonus = item[2] if len(item) > 2 else 0
        bonus_str = f"  +৳{bonus} বোনাস 🎁" if bonus > 0 else ""
        rows.append([StyledButton(
            f"💳  {price}  ডিপোজিট{bonus_str}",
            callback_data=f"pkg:{amount}:{price}:{bonus}"
        )])
    rows.append([StyledButton("✏️  নিজে পরিমাণ লিখুন", callback_data="pkg:custom")])
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
        StyledButton("🥉 Orders",    style="danger",  callback_data="lb:orders"),
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
            StyledButton("🎥 Video",    style="danger",  callback_data="bc_type:video"),
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
    PLATFORM_LABELS = {
        "facebook":  "📘 FACEBOOK",
        "instagram": "📸 INSTAGRAM",
        "tiktok":    "🎵 TIK TOK",
        "youtube":   "▶️ YOUTUBE",
        "telegram":  "✈️ TELEGRAM",
        "twitter":   "𝕏 TWITTER",
        "spotify":   "🎧 SPOTIFY",
        "whatsapp":  "💬 WHATSAPP",  # 🔥 Free Fire বাদ দিয়ে WhatsApp যোগ করা হলো
    }

    rows = []
    row = []

    platforms_to_show = ["facebook", "telegram", "tiktok", "instagram", "youtube", "twitter", "whatsapp", "spotify"]

    # 2 per row for platform buttons
    for p in platforms_to_show:
        label = PLATFORM_LABELS.get(p, f"🔹 {p.upper()}")
        row.append(StyledButton(label, callback_data=f"platform:{p}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    # OTHER SERVICE — full width
    rows.append([StyledButton("📦 OTHER SERVICE", callback_data="platform:other")])

    if updates_channel:
        rows.append([InlineKeyboardButton("📢 Join Updates Channel", url=updates_channel)])

    return InlineKeyboardMarkup(rows)


def platform_categories_kb(platform: str, categories: list[str], icons: dict) -> InlineKeyboardMarkup:
    rows = []
    current_row = [] 

    for idx, cat in enumerate(categories):
        icon = next((v for k, v in icons.items() if k.lower() in cat.lower()), "🔹")
        rows.append([StyledButton(
            f"{icon}  {cat.upper()}",
            callback_data=f"catidx:{idx}"
        )])

    rows.append([StyledButton("◀ Back", callback_data="platform_back")])
    return InlineKeyboardMarkup(rows)


def services_kb(services: list[dict], category: str, page: int = 0, markup_pct: float = 20.0) -> InlineKeyboardMarkup:
    PAGE_SIZE = 8
    total     = len(services)
    start     = page * PAGE_SIZE
    end       = start + PAGE_SIZE
    page_svcs = services[start:end]
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    EMOJI_MAP = {
        "view":     "👁️",  "views":    "👁️",
        "follow":   "👥",  "member":   "👥",  "members":  "👥",
        "like":     "❤️",  "likes":    "❤️",
        "comment":  "💬",  "comments": "💬",
        "share":    "🔁",  "shares":   "🔁",
        "reaction": "💝",  "reactions":"💝",
        "story":    "📖",  "stories":  "📖",
        "sub":      "🔔",  "subscriber":"🔔",
        "watch":    "⏱️",
        "group":    "👥",
        "boost":    "🚀",
        "post":     "📝",
        "real":     "✅",
        "non":      "💎",
        "premium":  "👑",
    }

    def get_emoji(name: str) -> str:
        nl = name.lower()
        for kw, em in EMOJI_MAP.items():
            if kw in nl:
                return em
        return "🔹"

    def is_game_svc(name: str) -> bool:
        nl = name.lower()
        return any(kw in nl for kw in ["free fire", "freefire", "diamond", "uc", "unipin"])

    # Arrow prefix like CSB bot style
    ARROWS = ["▶️", "▶️", "▶️", "▶️", "▶️", "▶️", "▶️", "▶️"]

    rows = []
    for i, svc in enumerate(page_svcs):
        em   = get_emoji(svc["name"])
        rate = float(svc.get("rate", 0)) * (1 + markup_pct / 100)
        name_short = svc["name"][:30] + "…" if len(svc["name"]) > 30 else svc["name"]
        if is_game_svc(svc["name"]):
            price_str = f"৳{rate:,.2f}/pkg"
        else:
            price_str = f"৳{rate:,.2f}/1k"
        rows.append([StyledButton(
            f"▶️ {em} {name_short}  |  {price_str}",
            callback_data=f"svc:{svc['service_id']}"
        )])

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(StyledButton("◀️ Prev", style="warning",
                                    callback_data=f"svc_page|{page-1}|{category}"))
        nav.append(InlineKeyboardButton(
            f"📄 {page+1}/{total_pages}", callback_data="noop"
        ))
        if end < total:
            nav.append(StyledButton("Next ▶️", style="primary",
                                    callback_data=f"svc_page|{page+1}|{category}"))
        rows.append(nav)

    rows.append([StyledButton("◀ Back", style="danger", callback_data="svc_list_back")])
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