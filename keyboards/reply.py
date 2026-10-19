from telegram import ReplyKeyboardMarkup, KeyboardButton


def service_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [{"text": "🌐 ꜱᴍᴍ ꜱᴇʀᴠɪᴄᴇ (1)", "style": "danger"},
         {"text": "🌐 ꜱᴍᴍ ꜱᴇʀᴠɪᴄᴇ (2)", "style": "primary"}],
        
        [{"text": "🎮 GAME TOPUP (1)", "style": "danger"},
         {"text": "🎮 GAME TOPUP (2)", "style": "success"}],
        
        [{"text": "✈️ ᴛᴇʟᴇɢʀᴀᴍ ꜱᴇʀᴠɪᴄᴇ", "style": "primary"}],
        [{"text": "🛍 ᴘᴀʀᴛɴᴇʀ ꜱʜᴏᴘ", "style": "success"}],
        [{"text": "🔙 ʙᴀᴄᴋ", "style": "danger"}],
    ], resize_keyboard=True, input_field_placeholder="📊 BY SHUVO......")


def order_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [{"text": "🌐 ꜱᴍᴍ ᴏʀᴅᴇʀ (1)", "style": "danger"},
         {"text": "🌐 ꜱᴍᴍ ᴏʀᴅᴇʀ (2)", "style": "primary"}],
        
        [{"text": "🎮 GAME TOPUP (1)", "style": "danger"},
         {"text": "🎮 GAME TOPUP (2)", "style": "success"}],
        
        [{"text": "✈️ ᴛᴇʟᴇɢʀᴀᴍ ᴏʀᴅᴇʀ", "style": "primary"}],
        [{"text": "🛍 ᴘᴀʀᴛɴᴇʀ ᴏʀᴅᴇʀ", "style": "success"}],
        [{"text": "🔙 ʙᴀᴄᴋ", "style": "danger"}],
    ], resize_keyboard=True, input_field_placeholder="🛒 BY SHUVO......")


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [{"text": "📊 ꜱᴇʀᴠɪᴄᴇꜱ ʟɪꜱᴛ", "style": "primary"}],
        [{"text": "🛒 ɴᴇᴡ ᴏʀᴅᴇʀ", "style": "success"},
         {"text": "📦 ᴍʏ ᴏʀᴅᴇʀꜱ", "style": "danger"}],
        [{"text": "👤 ᴍʏ ᴀᴄᴄᴏᴜɴᴛ", "style": "danger"},
         {"text": "💳 ʙᴜʏ ᴄᴏɪɴꜱ", "style": "primary"}],
        [{"text": "👥 ʀᴇꜰᴇʀʀᴀʟ", "style": "success"},
         {"text": "🏆 ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ", "style": "danger"}],
        [{"text": "☎️ ꜱᴜᴘᴘᴏʀᴛ", "style": "success"}],
    ], resize_keyboard=True, input_field_placeholder="⚡ BY SHUVO......")


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