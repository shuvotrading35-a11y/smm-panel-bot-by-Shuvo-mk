import aiosqlite
import asyncio
from datetime import datetime, timedelta
from config import DB_PATH
import os

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ─────────────────────────────────────────────────────────────────
#  INIT
# ─────────────────────────────────────────────────────────────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS users (
            user_id         INTEGER PRIMARY KEY,
            username        TEXT,
            full_name       TEXT,
            balance         REAL    DEFAULT 0.0,
            total_spent     REAL    DEFAULT 0.0,
            total_deposited REAL    DEFAULT 0.0,
            total_orders    INTEGER DEFAULT 0,
            referral_count  INTEGER DEFAULT 0,
            referral_earned REAL    DEFAULT 0.0,
            referred_by     INTEGER DEFAULT NULL,
            vip_plan        TEXT    DEFAULT NULL,
            vip_expires     TEXT    DEFAULT NULL,
            is_banned       INTEGER DEFAULT 0,
            last_daily      TEXT    DEFAULT NULL,
            join_date       TEXT    DEFAULT (datetime('now')),
            last_seen       TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            api_order_id    TEXT,
            service_id      TEXT    NOT NULL,
            service_name    TEXT,
            category        TEXT,
            link            TEXT    NOT NULL,
            quantity        INTEGER NOT NULL,
            charge          REAL    NOT NULL,
            status          TEXT    DEFAULT 'Pending',
            start_count     INTEGER DEFAULT 0,
            remains         INTEGER DEFAULT 0,
            created_at      TEXT    DEFAULT (datetime('now')),
            updated_at      TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            type        TEXT    NOT NULL,
            amount      REAL    NOT NULL,
            description TEXT,
            ref_id      TEXT,
            created_at  TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS deposits (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            amount          REAL    NOT NULL,
            method          TEXT    NOT NULL,
            txn_id          TEXT,
            status          TEXT    DEFAULT 'Pending',
            admin_note      TEXT,
            screenshot_id   TEXT,
            created_at      TEXT    DEFAULT (datetime('now')),
            approved_at     TEXT    DEFAULT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS redeem_codes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT    UNIQUE NOT NULL,
            amount      REAL    NOT NULL,
            max_uses    INTEGER DEFAULT 1,
            used_count  INTEGER DEFAULT 0,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS redeem_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            code        TEXT    NOT NULL,
            amount      REAL    NOT NULL,
            redeemed_at TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS support_tickets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            subject     TEXT,
            message     TEXT    NOT NULL,
            status      TEXT    DEFAULT 'Open',
            admin_reply TEXT,
            msg_id      INTEGER,
            created_at  TEXT    DEFAULT (datetime('now')),
            updated_at  TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS force_channels (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id  TEXT    UNIQUE NOT NULL,
            channel_name TEXT,
            invite_link TEXT,
            added_at    TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS banned_users (
            user_id     INTEGER PRIMARY KEY,
            reason      TEXT,
            banned_at   TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS vip_users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            plan        TEXT    NOT NULL,
            started_at  TEXT    DEFAULT (datetime('now')),
            expires_at  TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key         TEXT PRIMARY KEY,
            value       TEXT
        );

        CREATE TABLE IF NOT EXISTS services_cache (
            service_id      TEXT PRIMARY KEY,
            name            TEXT,
            category        TEXT,
            rate            REAL,
            min_order       INTEGER,
            max_order       INTEGER,
            refill          INTEGER DEFAULT 0,
            cancel          INTEGER DEFAULT 0,
            description     TEXT,
            synced_at       TEXT    DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_orders_user   ON orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        CREATE INDEX IF NOT EXISTS idx_txn_user      ON transactions(user_id);
        CREATE INDEX IF NOT EXISTS idx_deposits_user ON deposits(user_id);
        """)
        await db.commit()

# ─────────────────────────────────────────────────────────────────
#  USERS
# ─────────────────────────────────────────────────────────────────
async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def create_user(user_id: int, username: str, full_name: str, referred_by: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO users (user_id, username, full_name, referred_by)
               VALUES (?, ?, ?, ?)""",
            (user_id, username, full_name, referred_by)
        )
        await db.commit()

async def update_user(user_id: int, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k}=?" for k in kwargs)
    vals   = list(kwargs.values()) + [user_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {fields} WHERE user_id=?", vals)
        await db.commit()

async def get_all_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY join_date DESC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_user_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

async def search_user(query: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        like = f"%{query}%"
        async with db.execute(
            "SELECT * FROM users WHERE username LIKE ? OR full_name LIKE ? OR CAST(user_id AS TEXT)=?",
            (like, like, query)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def add_balance(user_id: int, amount: float, description: str = "Admin Add", ref_id: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        await db.execute(
            "INSERT INTO transactions (user_id, type, amount, description, ref_id) VALUES (?,?,?,?,?)",
            (user_id, "credit", amount, description, ref_id)
        )
        await db.commit()

async def deduct_balance(user_id: int, amount: float, description: str = "Order") -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
        if not row or row[0] < amount:
            return False
        await db.execute("UPDATE users SET balance = balance - ?, total_spent = total_spent + ? WHERE user_id=?",
                         (amount, amount, user_id))
        await db.execute(
            "INSERT INTO transactions (user_id, type, amount, description) VALUES (?,?,?,?)",
            (user_id, "debit", amount, description)
        )
        await db.commit()
        return True

# ─────────────────────────────────────────────────────────────────
#  BAN SYSTEM
# ─────────────────────────────────────────────────────────────────
async def ban_user(user_id: int, reason: str = "No reason"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
        await db.execute(
            "INSERT OR REPLACE INTO banned_users (user_id, reason) VALUES (?,?)",
            (user_id, reason)
        )
        await db.commit()

async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
        await db.execute("DELETE FROM banned_users WHERE user_id=?", (user_id,))
        await db.commit()

# ─────────────────────────────────────────────────────────────────
#  ORDERS
# ─────────────────────────────────────────────────────────────────
async def create_order(user_id: int, service_id: str, service_name: str,
                       category: str, link: str, quantity: int, charge: float,
                       api_order_id: str = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO orders (user_id, api_order_id, service_id, service_name,
               category, link, quantity, charge) VALUES (?,?,?,?,?,?,?,?)""",
            (user_id, api_order_id, service_id, service_name, category, link, quantity, charge)
        )
        await db.execute("UPDATE users SET total_orders = total_orders + 1 WHERE user_id=?", (user_id,))
        await db.commit()
        return cur.lastrowid

async def get_order(order_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE id=?", (order_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def get_user_orders(user_id: int, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def update_order_status(order_id: int, status: str, start_count: int = 0, remains: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET status=?, start_count=?, remains=?, updated_at=datetime('now') WHERE id=?",
            (status, start_count, remains, order_id)
        )
        await db.commit()

async def get_all_orders(limit: int = 20) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT o.*, u.username, u.full_name FROM orders o "
            "LEFT JOIN users u ON o.user_id=u.user_id "
            "ORDER BY o.created_at DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_order_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM orders") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

async def get_total_revenue() -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COALESCE(SUM(charge),0) FROM orders") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0.0

async def get_orders_today() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM orders WHERE DATE(created_at)=DATE('now')"
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

async def user_orders_today(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM orders WHERE user_id=? AND DATE(created_at)=DATE('now')",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

# ─────────────────────────────────────────────────────────────────
#  TRANSACTIONS
# ─────────────────────────────────────────────────────────────────
async def get_transactions(user_id: int, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

# ─────────────────────────────────────────────────────────────────
#  DEPOSITS
# ─────────────────────────────────────────────────────────────────
async def create_deposit(user_id: int, amount: float, method: str,
                         txn_id: str = None, screenshot_id: str = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO deposits (user_id, amount, method, txn_id, screenshot_id) VALUES (?,?,?,?,?)",
            (user_id, amount, method, txn_id, screenshot_id)
        )
        await db.commit()
        return cur.lastrowid

async def get_deposit(dep_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT d.*, u.username, u.full_name FROM deposits d "
            "LEFT JOIN users u ON d.user_id=u.user_id WHERE d.id=?", (dep_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def get_pending_deposits() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT d.*, u.username, u.full_name FROM deposits d "
            "LEFT JOIN users u ON d.user_id=u.user_id "
            "WHERE d.status='Pending' ORDER BY d.created_at DESC"
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def approve_deposit(dep_id: int) -> dict | None:
    dep = await get_deposit(dep_id)
    if not dep or dep["status"] != "Pending":
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE deposits SET status='Approved', approved_at=datetime('now') WHERE id=?",
            (dep_id,)
        )
        await db.execute(
            "UPDATE users SET balance=balance+?, total_deposited=total_deposited+? WHERE user_id=?",
            (dep["amount"], dep["amount"], dep["user_id"])
        )
        await db.execute(
            "INSERT INTO transactions (user_id, type, amount, description, ref_id) VALUES (?,?,?,?,?)",
            (dep["user_id"], "deposit", dep["amount"], f"Deposit via {dep['method']}", str(dep_id))
        )
        await db.commit()
    return dep

async def reject_deposit(dep_id: int) -> dict | None:
    dep = await get_deposit(dep_id)
    if not dep or dep["status"] != "Pending":
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE deposits SET status='Rejected' WHERE id=?", (dep_id,))
        await db.commit()
    return dep

async def get_user_deposits(user_id: int, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM deposits WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_deposit_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM deposits WHERE status='Approved'") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

# ─────────────────────────────────────────────────────────────────
#  REDEEM CODES
# ─────────────────────────────────────────────────────────────────
async def create_redeem_code(code: str, amount: float, max_uses: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO redeem_codes (code, amount, max_uses) VALUES (?,?,?)",
            (code.upper(), amount, max_uses)
        )
        await db.commit()

async def use_redeem_code(user_id: int, code: str) -> tuple[bool, str, float]:
    code = code.upper().strip()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM redeem_codes WHERE code=?", (code,)) as cur:
            rc = await cur.fetchone()
        if not rc:
            return False, "❌ Invalid code.", 0
        rc = dict(rc)
        if not rc["is_active"]:
            return False, "❌ Code is inactive.", 0
        if rc["used_count"] >= rc["max_uses"]:
            return False, "❌ Code has expired.", 0
        async with db.execute(
            "SELECT id FROM redeem_history WHERE user_id=? AND code=?", (user_id, code)
        ) as cur:
            used = await cur.fetchone()
        if used:
            return False, "❌ Already redeemed.", 0
        await db.execute("UPDATE redeem_codes SET used_count=used_count+1 WHERE code=?", (code,))
        await db.execute(
            "INSERT INTO redeem_history (user_id, code, amount) VALUES (?,?,?)",
            (user_id, code, rc["amount"])
        )
        await db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (rc["amount"], user_id))
        await db.execute(
            "INSERT INTO transactions (user_id, type, amount, description) VALUES (?,?,?,?)",
            (user_id, "redeem", rc["amount"], f"Redeem: {code}")
        )
        if rc["used_count"] + 1 >= rc["max_uses"]:
            await db.execute("UPDATE redeem_codes SET is_active=0 WHERE code=?", (code,))
        await db.commit()
    return True, f"✅ Redeemed +{rc['amount']} coins!", rc["amount"]

async def get_all_codes() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM redeem_codes ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def delete_redeem_code(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM redeem_codes WHERE code=?", (code.upper(),))
        await db.commit()

async def get_redeem_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM redeem_history") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

# ─────────────────────────────────────────────────────────────────
#  DAILY BONUS
# ─────────────────────────────────────────────────────────────────
async def claim_daily(user_id: int, amount: float) -> tuple[bool, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT last_daily FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            return False, "User not found."
        last = row["last_daily"]
        now  = datetime.utcnow()
        if last:
            last_dt = datetime.fromisoformat(last)
            diff = now - last_dt
            if diff < timedelta(hours=24):
                remaining = timedelta(hours=24) - diff
                h, rem = divmod(int(remaining.total_seconds()), 3600)
                m = rem // 60
                return False, f"⏳ Come back in {h}h {m}m."
        await db.execute(
            "UPDATE users SET balance=balance+?, last_daily=? WHERE user_id=?",
            (amount, now.isoformat(), user_id)
        )
        await db.execute(
            "INSERT INTO transactions (user_id, type, amount, description) VALUES (?,?,?,?)",
            (user_id, "daily", amount, "Daily Bonus")
        )
        await db.commit()
    return True, f"✅ +{amount} coins claimed!"

# ─────────────────────────────────────────────────────────────────
#  REFERRAL
# ─────────────────────────────────────────────────────────────────
async def process_referral(new_user_id: int, referrer_id: int, reward: float):
    if new_user_id == referrer_id:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM transactions WHERE user_id=? AND type='referral' AND ref_id=?",
            (referrer_id, str(new_user_id))
        ) as cur:
            existing = await cur.fetchone()
        if existing:
            return
        await db.execute(
            "UPDATE users SET balance=balance+?, referral_count=referral_count+1, "
            "referral_earned=referral_earned+? WHERE user_id=?",
            (reward, reward, referrer_id)
        )
        await db.execute(
            "INSERT INTO transactions (user_id, type, amount, description, ref_id) VALUES (?,?,?,?,?)",
            (referrer_id, "referral", reward, f"Referral reward for user {new_user_id}", str(new_user_id))
        )
        await db.commit()

# ─────────────────────────────────────────────────────────────────
#  LEADERBOARD
# ─────────────────────────────────────────────────────────────────
async def top_referrers(limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, full_name, username, referral_count, referral_earned "
            "FROM users ORDER BY referral_count DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def top_buyers(limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, full_name, username, total_spent "
            "FROM users ORDER BY total_spent DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def top_orders(limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, full_name, username, total_orders "
            "FROM users ORDER BY total_orders DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_user_rank(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE total_spent > "
            "(SELECT total_spent FROM users WHERE user_id=?)", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return (row[0] if row else 0) + 1

# ─────────────────────────────────────────────────────────────────
#  SUPPORT TICKETS
# ─────────────────────────────────────────────────────────────────
async def create_ticket(user_id: int, subject: str, message: str, msg_id: int = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO support_tickets (user_id, subject, message, msg_id) VALUES (?,?,?,?)",
            (user_id, subject, message, msg_id)
        )
        await db.commit()
        return cur.lastrowid

async def get_open_tickets() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT t.*, u.username, u.full_name FROM support_tickets t "
            "LEFT JOIN users u ON t.user_id=u.user_id "
            "WHERE t.status='Open' ORDER BY t.created_at DESC"
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_ticket(ticket_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT t.*, u.username, u.full_name FROM support_tickets t "
            "LEFT JOIN users u ON t.user_id=u.user_id WHERE t.id=?", (ticket_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def close_ticket(ticket_id: int, reply: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE support_tickets SET status='Closed', admin_reply=?, updated_at=datetime('now') WHERE id=?",
            (reply, ticket_id)
        )
        await db.commit()

# ─────────────────────────────────────────────────────────────────
#  FORCE JOIN CHANNELS
# ─────────────────────────────────────────────────────────────────
async def add_force_channel(channel_id: str, name: str, invite_link: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO force_channels (channel_id, channel_name, invite_link) VALUES (?,?,?)",
            (channel_id, name, invite_link)
        )
        await db.commit()

async def remove_force_channel(channel_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM force_channels WHERE channel_id=?", (channel_id,))
        await db.commit()

async def get_force_channels() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM force_channels") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

# ─────────────────────────────────────────────────────────────────
#  VIP
# ─────────────────────────────────────────────────────────────────
async def set_vip(user_id: int, plan: str, days: int):
    expires = (datetime.utcnow() + timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET vip_plan=?, vip_expires=? WHERE user_id=?",
            (plan, expires, user_id)
        )
        await db.execute(
            "INSERT INTO vip_users (user_id, plan, expires_at) VALUES (?,?,?)",
            (user_id, plan, expires)
        )
        await db.commit()

async def is_vip_active(user: dict) -> bool:
    if not user.get("vip_plan"):
        return False
    exp = user.get("vip_expires")
    if not exp:
        return False
    return datetime.fromisoformat(exp) > datetime.utcnow()

async def get_vip_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE vip_plan IS NOT NULL AND vip_expires > datetime('now')"
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

# ─────────────────────────────────────────────────────────────────
#  SERVICES CACHE
# ─────────────────────────────────────────────────────────────────
async def upsert_services(services: list[dict]):
    async with aiosqlite.connect(DB_PATH) as db:
        for s in services:
            await db.execute(
                """INSERT OR REPLACE INTO services_cache
                   (service_id, name, category, rate, min_order, max_order,
                    refill, cancel, description, synced_at)
                   VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))""",
                (
                    str(s.get("service", "")),
                    s.get("name", ""),
                    s.get("category", ""),
                    float(s.get("rate", 0)),
                    int(s.get("min", 0)),
                    int(s.get("max", 0)),
                    1 if s.get("refill") else 0,
                    1 if s.get("cancel") else 0,
                    s.get("description", ""),
                )
            )
        await db.commit()

async def get_categories() -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT DISTINCT category FROM services_cache ORDER BY category"
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]

async def get_services_by_category(category: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM services_cache WHERE category=? ORDER BY name", (category,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_service(service_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM services_cache WHERE service_id=?", (service_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

# ─────────────────────────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────────────────────────
async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else default

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
        await db.commit()

# ─────────────────────────────────────────────────────────────────
#  EXPORT
# ─────────────────────────────────────────────────────────────────
async def export_users_csv() -> str:
    users = await get_all_users()
    lines = ["id,username,full_name,balance,total_spent,total_deposited,total_orders,referral_count,vip_plan,is_banned,join_date"]
    for u in users:
        lines.append(
            f"{u['user_id']},{u.get('username','')},{u.get('full_name','')},"
            f"{u['balance']},{u['total_spent']},{u['total_deposited']},"
            f"{u['total_orders']},{u['referral_count']},{u.get('vip_plan','none')},"
            f"{u['is_banned']},{u['join_date']}"
        )
    return "\n".join(lines)

async def export_orders_csv() -> str:
    orders = await get_all_orders(limit=99999)
    lines = ["id,user_id,api_order_id,service_name,link,quantity,charge,status,created_at"]
    for o in orders:
        lines.append(
            f"{o['id']},{o['user_id']},{o.get('api_order_id','')},"
            f"\"{o.get('service_name','')}\",{o['link']},"
            f"{o['quantity']},{o['charge']},{o['status']},{o['created_at']}"
        )
    return "\n".join(lines)
