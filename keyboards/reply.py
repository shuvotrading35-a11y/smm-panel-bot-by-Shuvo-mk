from telegram import ReplyKeyboardMarkup, KeyboardButton


def service_menu_keyboard() -> ReplyKeyboardMarkup:
    """📊 Services List বাটনে ক্লিক করলে এই sub-menu আসবে"""
    return ReplyKeyboardMarkup([
       [{"text": "🌐 ꜱᴍᴍ ꜱᴇʀᴠɪᴄᴇ", "style": "success"}],
  [{"text": "🎮 ᴛᴏᴘ ᴜᴘ ꜱᴇʀᴠɪᴄᴇ", "style": "danger"}],
  [{"text": "✈️ ᴛᴇʟᴇɢʀᴀᴍ ꜱᴇʀᴠɪᴄᴇ", "style": "primary"}],
  [{"text": "🔙 ʙᴀᴄᴋ", "style": "success"}]
    ], resize_keyboard=True)


def order_menu_keyboard() -> ReplyKeyboardMarkup:
    """🛒 New Order বাটনে ক্লিক করলে এই sub-menu আসবে"""
    return ReplyKeyboardMarkup([
          [{"text": "🌐 ꜱᴍᴍ ᴏʀᴅᴇʀ", "style": "success"}],
  [{"text": "🎮 ᴛᴏᴘ ᴜᴘ ᴏʀᴅᴇʀ", "style": "danger"}],
  [{"text": "✈️ ᴛᴇʟᴇɢʀᴀᴍ ᴏʀᴅᴇʀ", "style": "primary"}],
  [{"text": "🔙 ʙᴀᴄᴋ", "style": "success"}]
    ], resize_keyboard=True)


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
          [{"text": "📊 ꜱᴇʀᴠɪᴄᴇꜱ ʟɪꜱᴛ", "style": "success"}],
  [{"text": "👤 ᴍʏ ᴀᴄᴄᴏᴜɴᴛ", "style": "danger"}, {"text": "💳 ʙᴜʏ ᴄᴏɪɴꜱ", "style": "primary"}],
  [{"text": "🛒 ɴᴇᴡ ᴏʀᴅᴇʀ", "style": "success"}, {"text": "📦 ᴍʏ ᴏʀᴅᴇʀꜱ", "style": "danger"}],
  [{"text": "🔎 ᴏʀᴅᴇʀ ᴛʀᴀᴄᴋᴇʀ", "style": "primary"}, {"text": "💰 ᴡᴀʟʟᴇᴛ", "style": "success"}],
  [{"text": "🎁 ʀᴇᴅᴇᴇᴍ ᴄᴏᴅᴇ", "style": "danger"}, {"text": "🎯 ᴅᴀɪʟʏ ʙᴏɴᴜꜱ", "style": "primary"}],
  [{"text": "👥 ʀᴇꜰᴇʀʀᴀʟ", "style": "success"}, {"text": "🏆 ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ", "style": "danger"}],
  [{"text": "📈 ᴍʏ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ", "style": "primary"}, {"text": "🔍 ꜱᴇᴀʀᴄʜ ꜱᴇʀᴠɪᴄᴇ", "style": "success"}],
  [{"text": "🎮 ɢᴀᴍᴇ ᴛᴏᴘᴜᴘ", "style": "danger"}, {"text": "📢 ᴜᴘᴅᴀᴛᴇꜱ", "style": "primary"}],
  [{"text": "☎️ ꜱᴜᴘᴘᴏʀᴛ", "style": "success"}]
    ], resize_keyboard=True)


def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [{"text": "👥 ᴜꜱᴇʀ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ", "style": "success"}],
  [{"text": "📢 ʙʀᴏᴀᴅᴄᴀꜱᴛ", "style": "danger"}, {"text": "🔔 ɴᴏᴛɪꜰɪᴄᴀᴛɪᴏɴ", "style": "primary"}],
  [{"text": "💰 ʙᴀʟᴀɴᴄᴇ ᴍᴀɴᴀɢᴇʀ", "style": "success"}, {"text": "🎁 ᴄᴏᴅᴇ ᴍᴀɴᴀɢᴇʀ", "style": "danger"}],
  [{"text": "📦 ᴏʀᴅᴇʀ ᴍᴀɴᴀɢᴇʀ", "style": "primary"}, {"text": "📊 ʙᴏᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ", "style": "success"}],
  [{"text": "📣 ꜰᴏʀᴄᴇ ᴊᴏɪɴ", "style": "danger"}, {"text": "🚫 ʙᴀɴ ꜱʏꜱᴛᴇᴍ", "style": "primary"}],
  [{"text": "☎️ ꜱᴜᴘᴘᴏʀᴛ ᴍᴀɴᴀɢᴇʀ", "style": "success"}, {"text": "⚙️ ᴀᴘɪ ᴍᴀɴᴀɢᴇʀ", "style": "danger"}],
  [{"text": "🛒 ꜱᴇʀᴠɪᴄᴇ ᴍᴀɴᴀɢᴇʀ", "style": "primary"}],
  [{"text": "🏆 ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ", "style": "success"}, {"text": "📤 ᴇxᴘᴏʀᴛ ᴅᴀᴛᴀ", "style": "danger"}],
  [{"text": "🗄 ᴅᴀᴛᴀʙᴀꜱᴇ ᴍᴀɴᴀɢᴇʀ", "style": "primary"}],
  [{"text": "🧹 ᴄʟᴇᴀɴ ᴜᴘ", "style": "success"}, {"text": "🔄 ʀᴇꜱᴛᴀʀᴛ ʙᴏᴛ", "style": "danger"}],
  [{"text": "🏠 ᴍᴀɪɴ ᴍᴇɴᴜ", "style": "primary"}]
    ], resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[{"text": "❌ ᴄᴀɴᴄᴇʟ", "style": "success"}]], resize_keyboard=True)


def back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["🔙 ʙᴀᴄᴋ"]], resize_keyboard=True)