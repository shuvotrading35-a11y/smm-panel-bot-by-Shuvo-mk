from telegram import ReplyKeyboardMarkup, KeyboardButton


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [{"text": "📊 ꜱᴇʀᴠɪᴄᴇꜱ ʟɪꜱᴛ", "style": "primary"}],
        ["👤 ᴍʏ ᴀᴄᴄᴏᴜɴᴛ", "💳 ʙᴜʏ ᴄᴏɪɴꜱ"],
        ["🛒 ɴᴇᴡ ᴏʀᴅᴇʀ", "📦 ᴍʏ ᴏʀᴅᴇʀꜱ"],
        ["🔎 ᴏʀᴅᴇʀ ᴛʀᴀᴄᴋᴇʀ", "💰 ᴡᴀʟʟᴇᴛ"],
        ["🎁 ʀᴇᴅᴇᴇᴍ ᴄᴏᴅᴇ", "🎯 ᴅᴀɪʟʏ ʙᴏɴᴜꜱ"],
        ["👥 ʀᴇꜰᴇʀʀᴀʟ", "🏆 ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ"],
        ["📈 ᴍʏ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ", "⭐ ᴠɪᴘ ᴍᴇᴍʙᴇʀꜱʜɪᴘ"],
        ["📢 ᴜᴘᴅᴀᴛᴇꜱ", "☎️ ꜱᴜᴘᴘᴏʀᴛ"],
    ], resize_keyboard=True)


def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        ["👥 ᴜꜱᴇʀ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ"],
        ["📢 ʙʀᴏᴀᴅᴄᴀꜱᴛ", "🔔 ɴᴏᴛɪꜰɪᴄᴀᴛɪᴏɴ"],
        ["💰 ʙᴀʟᴀɴᴄᴇ ᴍᴀɴᴀɢᴇʀ", "🎁 ᴄᴏᴅᴇ ᴍᴀɴᴀɢᴇʀ"],
        ["📦 ᴏʀᴅᴇʀ ᴍᴀɴᴀɢᴇʀ", "📊 ʙᴏᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ"],
        ["📣 ꜰᴏʀᴄᴇ ᴊᴏɪɴ", "🚫 ʙᴀɴ ꜱʏꜱᴛᴇᴍ"],
        ["☎️ ꜱᴜᴘᴘᴏʀᴛ ᴍᴀɴᴀɢᴇʀ", "⚙️ ᴀᴘɪ ᴍᴀɴᴀɢᴇʀ"],
        ["🛒 ꜱᴇʀᴠɪᴄᴇ ᴍᴀɴᴀɢᴇʀ", "💎 ᴠɪᴘ ᴍᴀɴᴀɢᴇʀ"],
        ["🏆 ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ", "📤 ᴇxᴘᴏʀᴛ ᴅᴀᴛᴀ"],
        ["🗄 ᴅᴀᴛᴀʙᴀꜱᴇ ᴍᴀɴᴀɢᴇʀ"],
        ["🧹 ᴄʟᴇᴀɴ ᴜᴘ", "🔄 ʀᴇꜱᴛᴀʀᴛ ʙᴏᴛ"],
        ["🏠 ᴍᴀɪɴ ᴍᴇɴᴜ"],
    ], resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["❌ ᴄᴀɴᴄᴇʟ"]], resize_keyboard=True)


def back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["🔙 ʙᴀᴄᴋ"]], resize_keyboard=True)