from telegram import ReplyKeyboardMarkup, KeyboardButton


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [{"text": "📊 ꜱᴇʀᴠɪᴄᴇꜱ ʟɪꜱᴛ", "style": "primary"}],
        [{"text": "👤 ᴍʏ ᴀᴄᴄᴏᴜɴᴛ", "style": "success"}, {"text": "💳 ʙᴜʏ ᴄᴏɪɴꜱ", "style": "danger"}],
    [{"text": "🛒 ɴᴇᴡ ᴏʀᴅᴇʀ", "style": "primary"}, {"text": "📦 ᴍʏ ᴏʀᴅᴇʀꜱ", "style": "danger"}],
    [{"text": "🔎 ᴏʀᴅᴇʀ ᴛʀᴀᴄᴋᴇʀ", "style": "success"}, {"text": "💰 ᴡᴀʟʟᴇᴛ", "style": "danger"}],
    [{"text": "🎁 ʀᴇᴅᴇᴇᴍ ᴄᴏᴅᴇ", "style": "primary"}, {"text": "🎯 ᴅᴀɪʟʏ ʙᴏɴᴜꜱ", "style": "success"}],
    [{"text": "👥 ʀᴇꜰᴇʀʀᴀʟ", "style": "primary"}, {"text": "🏆 ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ", "style": "success"}],
    [{"text": "📈 ᴍʏ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ", "style": "danger"}, {"text": "⭐ ᴠɪᴘ ᴍᴇᴍʙᴇʀꜱʜɪᴘ", "style": "success"}],
    [{"text": "📢 ᴜᴘᴅᴀᴛᴇꜱ", "style": "primary"}, {"text": "☎️ ꜱᴜᴘᴘᴏʀᴛ", "style": "danger"}],
    ], resize_keyboard=True)


def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [{"text": "👥 ᴜꜱᴇʀ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ", "style": "primary"}],
    [{"text": "📢 ʙʀᴏᴀᴅᴄᴀꜱᴛ", "style": "danger"}, {"text": "🔔 ɴᴏᴛɪꜰɪᴄᴀᴛɪᴏɴ", "style": "success"}],
    [{"text": "💰 ʙᴀʟᴀɴᴄᴇ ᴍᴀɴᴀɢᴇʀ", "style": "danger"}, {"text": "🎁 ᴄᴏᴅᴇ ᴍᴀɴᴀɢᴇʀ", "style": "success"}],
    [{"text": "📦 ᴏʀᴅᴇʀ ᴍᴀɴᴀɢᴇʀ", "style": "danger"}, {"text": "📊 ʙᴏᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ", "style": "success"}],
    [{"text": "📣 ꜰᴏʀᴄᴇ ᴊᴏɪɴ", "style": "danger"}, {"text": "🚫 ʙᴀɴ ꜱʏꜱᴛᴇᴍ", "style": "success"}],
    [{"text": "☎️ ꜱᴜᴘᴘᴏʀᴛ ᴍᴀɴᴀɢᴇʀ", "style": "danger"}, {"text": "⚙️ ᴀᴘɪ ᴍᴀɴᴀɢᴇʀ", "style": "success"}],
    [{"text": "🛒 ꜱᴇʀᴠɪᴄᴇ ᴍᴀɴᴀɢᴇʀ", "style": "danger"}, {"text": "💎 ᴠɪᴘ ᴍᴀɴᴀɢᴇʀ", "style": "success"}],
    [{"text": "🏆 ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ", "style": "danger"}, {"text": "📤 ᴇxᴘᴏʀᴛ ᴅᴀᴛᴀ", "style": "success"}],
    [{"text": "🗄 ᴅᴀᴛᴀʙᴀꜱᴇ ᴍᴀɴᴀɢᴇʀ", "style": "primary"}],
    [{"text": "🧹 ᴄʟᴇᴀɴ ᴜᴘ", "style": "danger"}, {"text": "🔄 ʀᴇꜱᴛᴀʀᴛ ʙᴏᴛ", "style": "success"}],
    [{"text": "🏠 ᴍᴀɪɴ ᴍᴇɴᴜ", "style": "primary"}],
    ], resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["❌ ᴄᴀɴᴄᴇʟ"]], resize_keyboard=True)


def back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["🔙 ʙᴀᴄᴋ"]], resize_keyboard=True)