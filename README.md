# 🤖 Shuvo SMM Panel Bot

A professional, fully async Telegram SMM Panel Bot built with Python 3.12+ and python-telegram-bot v21+.

---

## ✨ Features

- 📊 Auto service sync from any SMM Panel API
- 🛒 Full order placement flow with confirmation
- 💰 Wallet system with coin balance
- 💳 Multi-method deposit with admin approval
- 🎁 Redeem codes system
- 🎯 Daily bonus (24h cooldown)
- 👥 Referral system with coin rewards
- 🏆 Leaderboard (referrers, buyers, orders)
- ⭐ VIP membership tiers (Bronze/Silver/Gold/Diamond)
- ☎️ Support ticket system with admin reply
- 📣 Force join channel verification
- 👑 Full admin panel with all management tools
- 📢 Broadcast system (text/photo/video/document)
- 📤 CSV export (users/orders)
- 🚫 Ban/unban system
- 🛡️ Anti-spam rate limiting
- 📦 Order refresh/refill/cancel via API
- 🔄 Async SQLite with WAL mode

---

## 📁 Project Structure

```
shuvo_smm_bot/
├── bot.py                  # Main entry point
├── config.py               # All configuration
├── database.py             # Full async DB layer
├── requirements.txt
├── .env                    # Your secrets (never commit)
│
├── handlers/
│   ├── user.py             # All user-facing handlers
│   └── admin.py            # Full admin panel
│
├── api/
│   └── smm_api.py          # SMM Panel API client
│
├── keyboards/
│   ├── reply.py            # ReplyKeyboardMarkup
│   └── inline.py           # InlineKeyboardMarkup
│
├── utils/
│   ├── helpers.py          # Formatting, anti-spam, broadcast
│   └── filters.py          # Custom PTB filters
│
└── data/
    ├── database.db         # SQLite DB (auto-created)
    └── bot.log             # Log file (auto-created)
```

---

## ⚡ Quick Setup

### 1. Clone / extract the project

```bash
cd shuvo_smm_bot
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure `.env`

```env
BOT_TOKEN=your_bot_token_from_BotFather
BOT_USERNAME=YourBotUsername
ADMIN_IDS=your_telegram_id
SMM_API_URL=https://your-smm-panel.com/api/v2
SMM_API_KEY=your_api_key
```

> Get your Telegram ID from [@userinfobot](https://t.me/userinfobot)  
> Get your bot token from [@BotFather](https://t.me/BotFather)

### 5. Run the bot

```bash
python bot.py
```

---

## 🔧 First-Time Admin Setup

After the bot starts, send `/admin` to open the admin panel, then:

1. **Sync services** — Press `🛒 ꜱᴇʀᴠɪᴄᴇ ᴍᴀɴᴀɢᴇʀ` or send `/syncservices`
2. **Test API** — Send `/testapi`
3. **Add force-join channels** (optional):
   ```
   /addchannel @yourchannel https://t.me/yourchannel ChannelName
   ```

---

## 👑 Admin Panel Commands

| Command | Description |
|---|---|
| `/admin` | Open admin panel |
| `/syncservices` | Sync services from SMM API |
| `/testapi` | Test API connection |
| `/addchannel @ch link name` | Add force-join channel |
| `/removechannel @ch` | Remove force-join channel |
| `/channels` | List force-join channels |
| `/stats` | Bot statistics |
| `/export` | Export data menu |

---

## 💳 Payment Setup

Edit `handlers/user.py` → `payment_method_callback()` to add your real payment addresses:

```python
payment_info = {
    "binance":  "💵 *Binance Pay ID:* `YOUR_BINANCE_ID`",
    "usdt_trc": "🟢 *USDT TRC20:* `YOUR_TRC20_ADDRESS`",
    "usdt_bep": "🟡 *USDT BEP20:* `YOUR_BEP20_ADDRESS`",
    "mobile":   "📱 *bKash:* `01XXXXXXXXX`\n*Nagad:* `01XXXXXXXXX`",
    ...
}
```

---

## 🗄️ Database Tables

| Table | Purpose |
|---|---|
| `users` | All user data, balances, VIP |
| `orders` | All orders with API IDs |
| `transactions` | Credit/debit history |
| `deposits` | Deposit requests + approval |
| `redeem_codes` | Codes and usage tracking |
| `redeem_history` | Who redeemed what |
| `support_tickets` | Open/closed support tickets |
| `force_channels` | Required join channels |
| `banned_users` | Banned user list |
| `vip_users` | VIP assignments |
| `services_cache` | Synced services from API |
| `settings` | Key-value bot settings |

---

## ⚙️ Configuration (`config.py`)

| Variable | Default | Description |
|---|---|---|
| `DAILY_BONUS_AMOUNT` | `1` | Daily bonus coins |
| `REFERRAL_REWARD` | `5` | Coins per referral |
| `COIN_RATE` | `0.01` | 1 coin = $0.01 USD |
| `MIN_DEPOSIT` | `1.00` | Minimum deposit |
| `MAX_ORDERS_PER_DAY` | `50` | Anti-abuse order limit |
| `RATE_LIMIT_SECONDS` | `1` | Anti-spam cooldown |

---

## 📦 SMM API Compatibility

Compatible with any panel using the standard SMM API v2 format:

```
POST https://panel.com/api/v2
key=API_KEY&action=services
key=API_KEY&action=add&service=1&link=URL&quantity=1000
key=API_KEY&action=status&order=12345
key=API_KEY&action=refill&order=12345
key=API_KEY&action=cancel&orders=12345
key=API_KEY&action=balance
```

Works with: **JustAnotherPanel, Peakerr, Growr, Followiz, SMMKings**, and most others.

---

## 🚀 Running on a Server (systemd)

Create `/etc/systemd/system/smmbot.service`:

```ini
[Unit]
Description=Shuvo SMM Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/path/to/shuvo_smm_bot
ExecStart=/path/to/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable smmbot
sudo systemctl start smmbot
sudo systemctl status smmbot
```

---

## 👨‍💻 Developer

**@shuvo_9882** — Telegram  
🤖 Powered By Shuvo SMM
