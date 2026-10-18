from telegram import ReplyKeyboardMarkup, KeyboardButton


# ─────────────────────────────────────────────────────
#  SERVICE MENU  (📊 ꜱᴇʀᴠɪᴄᴇꜱ ʟɪꜱᴛ)
# ─────────────────────────────────────────────────────
def service_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [{"text": "🌐 ꜱᴍᴍ ꜱᴇʀᴠɪᴄᴇ (1)", "style": "danger"},
         {"text": "🌐 ꜱᴍᴍ ꜱᴇʀᴠɪᴄᴇ (2)", "style": "primary"}],
        
        # 🔥 Free Fire / Game Topup বাটন দুটি এখানে যোগ করা হলো
        [{"text": "🎮 ɢᴀᴍᴇ ᴛᴏᴘᴜᴘ (1)", "style": "danger"},
         {"text": "🎮 ɢᴀᴍᴇ ᴛᴏᴘᴜᴘ (2)", "style": "success"}],
        
        [{"text": "✈️ ᴛᴇʟᴇɢʀᴀᴍ ꜱᴇʀᴠɪᴄᴇ", "style": "primary"}],
        [{"text": "🛍 ᴘᴀʀᴛɴᴇʀ ꜱʜᴏᴘ", "style": "success"}],
        [{"text": "🔙 ʙᴀᴄᴋ", "style": "danger"}],
    ], resize_keyboard=True, input_field_placeholder="📊 BY SHUVO......")


# ─────────────────────────────────────────────────────
#  ORDER MENU  (🛒 ɴᴇᴡ ᴏʀᴅᴇʀ)
# ─────────────────────────────────────────────────────
def order_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [{"text": "🌐 ꜱᴍᴍ ᴏʀᴅᴇʀ (1)", "style": "danger"},
         {"text": "🌐 ꜱᴍᴍ ᴏʀᴅᴇʀ (2)", "style": "primary"}],
        
        # 🔥 Free Fire / Game Topup বাটন দুটি এখানে যোগ করা হলো
        [{"text": "🎮 ɢᴀᴍᴇ ᴛᴏᴘᴜᴘ (1)", "style": "danger"},
         {"text": "🎮 ɢᴀᴍᴇ ᴛᴏᴘᴜᴘ (2)", "style": "success"}],
        
        [{"text": "✈️ ᴛᴇʟᴇɢʀᴀᴍ ᴏʀᴅᴇʀ", "style": "primary"}],
        [{"text": "🛍 ᴘᴀʀᴛɴᴇʀ ᴏʀᴅᴇʀ", "style": "success"}],
        [{"text": "🔙 ʙᴀᴄᴋ", "style": "danger"}],
    ], resize_keyboard=True, input_field_placeholder="🛒 BY SHUVO......")


# ─────────────────────────────────────────────────────
#  MAIN MENU  (Clean — 8 buttons)
# ─────────────────────────────────────────────────────
def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        # Row 1
        [{"text": "📊 ꜱᴇʀᴠɪᴄᴇꜱ ʟɪꜱᴛ", "style": "primary"}],
        # Row 2
        [{"text": "🛒 ɴᴇᴡ ᴏʀᴅᴇʀ", "style": "success"},
         {"text": "📦 ᴍʏ ᴏʀᴅᴇʀꜱ", "style": "danger"}],
        # Row 3
        [{"text": "👤 ᴍʏ ᴀᴄᴄᴏᴜɴᴛ", "style": "danger"},
         {"text": "💳 ʙᴜʏ ᴄᴏɪɴꜱ", "style": "primary"}],
        # Row 4
        [{"text": "👥 ʀᴇꜰᴇʀʀᴀʟ", "style": "success"},
         {"text": "🏆 ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ", "style": "danger"}],
        # Row 5
        [{"text": "☎️ ꜱᴜᴘᴘᴏʀᴛ", "style": "success"}],
    ], resize_keyboard=True, input_field_placeholder="⚡ BY SHUVO......")


# ─────────────────────────────────────────────────────
#  ADMIN  (Clean — essential only)
# ─────────────────────────────────────────────────────
def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [{"text": "👥 ᴜꜱᴇʀ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ", "style": "success"}],
        [{"text": "💰 ʙᴀʟᴀɴᴄᴇ ᴍᴀɴᴀɢᴇʀ", "style": "success"},
         {"text": "🎁 ᴄᴏᴅᴇ ᴍᴀɴᴀɢᴇʀ", "style": "danger"}],
        [{"text": "📦 ᴏʀᴅᴇʀ ᴍᴀɴᴀɢᴇʀ", "style": "primary"},
         {"text": "📊 ʙᴏᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ", "style": "success"}],
        [{"text": "📊 ᴘᴀʀᴛɴᴇʀ ꜱᴛᴀᴛꜱ", "style": "primary"},
         {"text": "🛒 ꜱᴇʀᴠɪᴄᴇ ᴍᴀɴᴀɢᴇʀ", "style": "primary"}],
        [{"text": "📢 ʙʀᴏᴀᴅᴄᴀꜱᴛ", "style": "danger"},
         {"text": "🔔 ɴᴏᴛɪꜰɪᴄᴀᴛɪᴏɴ", "style": "primary"}],
        [{"text": "📣 ꜰᴏʀᴄᴇ ᴊᴏɪɴ", "style": "danger"},
         {"text": "🚫 ʙᴀɴ ꜱʏꜱᴛᴇᴍ", "style": "primary"}],
        [{"text": "☎️ ꜱᴜᴘᴘᴏʀᴛ ᴍᴀɴᴀɢᴇʀ", "style": "success"},
         {"text": "⚙️ ᴀᴘɪ ᴍᴀɴᴀɢᴇʀ", "style": "danger"}],
        [{"text": "📤 ᴇxᴘᴏʀᴛ ᴅᴀᴛᴀ", "style": "danger"},
         {"text": "🗄 ᴅᴀᴛᴀʙᴀꜱᴇ ᴍᴀɴᴀɢᴇʀ", "style": "primary"}],
        [{"text": "🧹 ᴄʟᴇᴀɴ ᴜᴘ", "style": "success"},
         {"text": "🔄 ʀᴇꜱᴛᴀʀᴛ ʙᴏᴛ", "style": "danger"}],
        [{"text": "🏠 ᴍᴀɪɴ ᴍᴇɴᴜ", "style": "primary"}],
    ], resize_keyboard=True, input_field_placeholder="🔥 BY SHUVO......")


# ─────────────────────────────────────────────────────
#  UTILITY
# ─────────────────────────────────────────────────────
def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[{"text": "❌ ᴄᴀɴᴄᴇʟ", "style": "success"}]],
        resize_keyboard=True, input_field_placeholder="❌ BY SHUVO......"
    )


def back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[{"text": "🔙 ʙᴀᴄᴋ", "style": "success"}]],
        resize_keyboard=True, input_field_placeholder="⭐ BY SHUVO......"
    )