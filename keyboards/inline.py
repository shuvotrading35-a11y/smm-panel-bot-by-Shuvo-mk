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
        "freefire":  "🔥 FREE FIRE",
    }

    rows = []
    row = []

    platforms_to_show = ["facebook", "telegram", "tiktok", "instagram", "youtube", "twitter", "freefire", "spotify"]

    for p in platforms_to_show:
        label = PLATFORM_LABELS.get(p, f"🔹 {p.upper()}")
        row.append(StyledButton(label, style="success", callback_data=f"platform:{p}"))
        if len(row) == 2:
            rows.append(row)
            row = []

    row.append(StyledButton("📦 OTHER SERVICE", style="success", callback_data="platform:other"))
    rows.append(row)

    if updates_channel:
        rows.append([InlineKeyboardButton("📢 Join Updates Channel", url=updates_channel)])

    return InlineKeyboardMarkup(rows)


def platform_categories_kb(platform: str, categories: list[str], icons: dict) -> InlineKeyboardMarkup:
    # 🔥 FIX: এখানে কোনো ফিল্টার নেই, সরাসরি পাস করা লিস্ট দেখাবে। ফলে index ঠিক থাকবে।
    rows = []
    current_row = [] 

    for idx, cat in enumerate(categories):
        icon = next((v for k, v in icons.items() if k.lower() in cat.lower()), "🔹")
        current_row.append(StyledButton(
            f"{icon}  {cat.upper()}",
            style="success",
            callback_data=f"catidx:{idx}"
        ))
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = [] 

    if current_row:
        rows.append(current_row)

    rows.append([StyledButton("◀ Back", style="danger", callback_data="platform_back")])
    return InlineKeyboardMarkup(rows)


def services_kb(services: list[dict], category: str, page: int = 0) -> InlineKeyboardMarkup:
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

    rows = []
    for svc in page_svcs:
        em = get_emoji(svc["name"])
        rows.append([StyledButton(
            f"{em}  {svc['name']}",
            style="success",
            callback_data=f"svc:{svc['service_id']}"
        )])

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(StyledButton("◀ Back", style="primary",
                                    callback_data=f"svc_page|{page-1}|{category}"))
        nav.append(InlineKeyboardButton(
            f"📄 {page+1}/{total_pages}", callback_data="noop"
        ))
        if end < total:
            nav.append(StyledButton("Next ▶", style="primary",
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