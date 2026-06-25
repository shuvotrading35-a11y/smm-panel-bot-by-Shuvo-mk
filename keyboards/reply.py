from telegram import ReplyKeyboardMarkup, KeyboardButton


def service_menu_keyboard() -> ReplyKeyboardMarkup:
    """📊 Services List বাটনে ক্লিক করলে এই sub-menu আসবে"""
    return ReplyKeyboardMarkup([
        ["🌐 ꜱᴍᴍ ꜱᴇʀᴠɪᴄᴇ"],
        ["🎮 ᴛᴏᴘ ᴜᴘ ꜱᴇʀᴠɪᴄᴇ"],
        ["✈️ ᴛᴇʟᴇɢʀᴀᴍ ꜱᴇʀᴠɪᴄᴇ"],
        ["🔙 ʙᴀᴄᴋ"],
    ], resize_keyboard=True)


def order_menu_keyboard() -> ReplyKeyboardMarkup:
    """🛒 New Order বাটনে ক্লিক করলে এই sub-menu আসবে"""
    return ReplyKeyboardMarkup([
        ["🌐 ꜱᴍᴍ ᴏʀᴅᴇʀ"],
        ["🎮 ᴛᴏᴘ ᴜᴘ ᴏʀᴅᴇʀ"],
        ["✈️ ᴛᴇʟᴇɢʀᴀᴍ ᴏʀᴅᴇʀ"],
        ["🔙 ʙᴀᴄᴋ"],
    ], resize_keyboard=True)


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        ["📊 ꜱᴇʀᴠɪᴄᴇꜱ ʟɪꜱᴛ"],
        ["👤 ᴍʏ ᴀᴄᴄᴏᴜɴᴛ", "💳 ʙᴜʏ ᴄᴏɪɴꜱ"],
        ["🛒 ɴᴇᴡ ᴏʀᴅᴇʀ", "📦 ᴍʏ ᴏʀᴅᴇʀꜱ"],
        ["🔎 ᴏʀᴅᴇʀ ᴛʀᴀᴄᴋᴇʀ", "💰 ᴡᴀʟʟᴇᴛ"],
        ["🎁 ʀᴇᴅᴇᴇᴍ ᴄᴏᴅᴇ", "🎯 ᴅᴀɪʟʏ ʙᴏɴᴜꜱ"],
        ["👥 ʀᴇꜰᴇʀʀᴀʟ", "🏆 ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ"],
        ["📈 ᴍʏ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ", "🔍 ꜱᴇᴀʀᴄʜ ꜱᴇʀᴠɪᴄᴇ"],
        ["🎮 ɢᴀᴍᴇ ᴛᴏᴘᴜᴘ", "📢 ᴜᴘᴅᴀᴛᴇꜱ"],
        ["☎️ ꜱᴜᴘᴘᴏʀᴛ"],
    ], resize_keyboard=True)


def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        ["👥 ᴜꜱᴇʀ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ"],
        ["📢 ʙʀᴏᴀᴅᴄᴀꜱᴛ", "🔔 ɴᴏᴛɪꜰɪᴄᴀᴛɪᴏɴ"],
        ["💰 ʙᴀʟᴀɴᴄᴇ ᴍᴀɴᴀɢᴇʀ", "🎁 ᴄᴏᴅᴇ ᴍᴀɴᴀɢᴇʀ"],
        ["📦 ᴏʀᴅᴇʀ ᴍᴀɴᴀɢᴇʀ", "📊 ʙᴏᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ"],
        ["📣 ꜰᴏʀᴄᴇ ᴊᴏɪɴ", "🚫 ʙᴀɴ ꜱʏꜱᴛᴇᴍ"],
        ["☎️ ꜱᴜᴘᴘᴏʀᴛ ᴍᴀɴᴀɢᴇʀ", "⚙️ ᴀᴘɪ ᴍᴀɴᴀɢᴇʀ"],
        ["🛒 ꜱᴇʀᴠɪᴄᴇ ᴍᴀɴᴀɢᴇʀ"],
        ["🏆 ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ", "📤 ᴇxᴘᴏʀᴛ ᴅᴀᴛᴀ"],
        ["🗄 ᴅᴀᴛᴀʙᴀꜱᴇ ᴍᴀɴᴀɢᴇʀ"],
        ["🧹 ᴄʟᴇᴀɴ ᴜᴘ", "🔄 ʀᴇꜱᴛᴀʀᴛ ʙᴏᴛ"],
        ["🏠 ᴍᴀɪɴ ᴍᴇɴᴜ"],
    ], resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["❌ ᴄᴀɴᴄᴇʟ"]], resize_keyboard=True)


def back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["🔙 ʙᴀᴄᴋ"]], resize_keyboard=True)