"""
SQLite storage (aiosqlite): users, wallets, payments, subscriptions, settings.
"""
import json
import os
import random
import string
import time

import aiosqlite

# DATA_DIR lets you keep runner.db on a persistent disk (e.g. Render /var/data)
DB_PATH = os.path.join(os.getenv("DATA_DIR", "."), "runner.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    wallet_priv TEXT,
    wallet_pub TEXT,
    free_used INTEGER DEFAULT 0,
    default_buy REAL,
    default_sell REAL,
    default_slippage REAL DEFAULT 10,
    ref_code TEXT UNIQUE,
    referred_by INTEGER,
    credits_lamports INTEGER DEFAULT 0,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS payments (
    tx_sig TEXT PRIMARY KEY,
    user_id INTEGER,
    item TEXT,
    price_lamports INTEGER,
    payer TEXT,
    ts INTEGER
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    kind TEXT,
    item_key TEXT,
    label TEXT,
    price_lamports INTEGER,
    start_ts INTEGER,
    end_ts INTEGER,
    status TEXT DEFAULT 'active',
    tx_sig TEXT,
    payer TEXT,
    invite_link TEXT,
    channel_id TEXT,
    notified TEXT DEFAULT '[]',
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    mint TEXT,
    symbol TEXT,
    qty REAL,
    decimals INTEGER DEFAULT 6,
    spent_sol REAL,
    buy_sigs TEXT DEFAULT '[]',
    created_at INTEGER,
    updated_at INTEGER
);

CREATE TABLE IF NOT EXISTS limit_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    mint TEXT,
    symbol TEXT,
    side TEXT,
    target_price REAL,
    amount REAL,
    slippage_bps INTEGER DEFAULT 1000,
    attempts INTEGER DEFAULT 0,
    status TEXT DEFAULT 'open',
    note TEXT DEFAULT '',
    created_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_subs_end ON subscriptions(end_ts);
CREATE INDEX IF NOT EXISTS idx_positions_user ON positions(user_id, mint);
CREATE INDEX IF NOT EXISTS idx_limits_status ON limit_orders(status);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


# ------------------------------------------------------------------ users
async def ensure_user(user_id: int, username: str = None, first_name: str = None,
                      referred_by: int = None) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM users WHERE id=?", (user_id,))
        row = await cur.fetchone()
        if row is None:
            code = f"{user_id:x}{''.join(random.choices(string.ascii_lowercase + string.digits, k=4))}"
            await db.execute(
                "INSERT INTO users (id, username, first_name, ref_code, referred_by, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (user_id, username, first_name, code, referred_by, int(time.time())),
            )
            await db.commit()
            cur = await db.execute("SELECT * FROM users WHERE id=?", (user_id,))
            row = await cur.fetchone()
        else:
            await db.execute(
                "UPDATE users SET username=?, first_name=? WHERE id=?",
                (username or row[1], first_name or row[2], user_id),
            )
            await db.commit()
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM users WHERE id=?", (user_id,))
        row = await cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))


async def get_user_by_ref(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM users WHERE ref_code=?", (code,))
        row = await cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))


async def count_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        return (await cur.fetchone())[0]


async def count_refs(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,))
        return (await cur.fetchone())[0]


async def set_wallet(user_id: int, priv: str, pub: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET wallet_priv=?, wallet_pub=? WHERE id=?",
                         (priv, pub, user_id))
        await db.commit()


async def bump_free(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET free_used = free_used + 1 WHERE id=?", (user_id,))
        await db.commit()


async def set_defaults(user_id: int, buy=None, sell=None, slip=None):
    sets, vals = [], []
    if buy is not None:
        sets.append("default_buy=?"); vals.append(buy)
    if sell is not None:
        sets.append("default_sell=?"); vals.append(sell)
    if slip is not None:
        sets.append("default_slippage=?"); vals.append(slip)
    if not sets:
        return
    vals.append(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", vals)
        await db.commit()


async def add_credits(user_id: int, lamports: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET credits_lamports = credits_lamports + ? WHERE id=?",
                         (lamports, user_id))
        await db.commit()


async def spend_credits(user_id: int, lamports: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET credits_lamports = credits_lamports - ? WHERE id=?",
                         (lamports, user_id))
        await db.commit()


# ------------------------------------------------------------------ payments
async def payment_exists(tx_sig: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM payments WHERE tx_sig=?", (tx_sig,))
        return await cur.fetchone() is not None


async def payment_sigs() -> set:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT tx_sig FROM payments")
        return {r[0] for r in await cur.fetchall()}


async def register_payment(tx_sig: str, user_id: int, item: str, lamports: int, payer: str) -> bool:
    """Returns False if this tx signature was already used by someone."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO payments (tx_sig, user_id, item, price_lamports, payer, ts) "
                "VALUES (?,?,?,?,?,?)",
                (tx_sig, user_id, item, lamports, payer, int(time.time())),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def total_revenue_lamports():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COALESCE(SUM(price_lamports),0), COUNT(*) FROM payments")
        row = await cur.fetchone()
        return row[0], row[1]


# ------------------------------------------------------------------ subscriptions
async def add_subscription(user_id: int, kind: str, item_key: str, label: str,
                           lamports: int, days: int, tx_sig: str, payer: str,
                           invite_link: str = "", channel_id: str = "") -> dict:
    now = int(time.time())
    end_ts = 0 if days == 0 else now + days * 86400
    async with aiosqlite.connect(DB_PATH) as db:
        # extend an active sub of the same item instead of duplicating
        cur = await db.execute(
            "SELECT * FROM subscriptions WHERE user_id=? AND kind=? AND item_key=? "
            "AND status='active' ORDER BY end_ts DESC LIMIT 1",
            (user_id, kind, item_key),
        )
        row = await cur.fetchone()
        if row and days > 0 and row[7]:
            base = max(row[7], now)
            end_ts = base + days * 86400
            await db.execute(
                "UPDATE subscriptions SET end_ts=?, invite_link=?, status='active' WHERE id=?",
                (end_ts, invite_link or row[11], row[0]),
            )
            await db.commit()
            sub_id = row[0]
        else:
            cur = await db.execute(
                "INSERT INTO subscriptions (user_id, kind, item_key, label, price_lamports, "
                "start_ts, end_ts, status, tx_sig, payer, invite_link, channel_id, created_at) "
                "VALUES (?,?,?,?,?,?,?, 'active', ?,?,?,?,?)",
                (user_id, kind, item_key, label, lamports, now, end_ts, tx_sig, payer,
                 invite_link, channel_id, now),
            )
            await db.commit()
            sub_id = cur.lastrowid
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM subscriptions WHERE id=?", (sub_id,))
        row = await cur.fetchone()
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))


async def get_active_subs(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT * FROM subscriptions WHERE user_id=? AND status='active' ORDER BY kind, end_ts",
            (user_id,),
        )
        rows = await cur.fetchall()
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in rows]


async def has_active(user_id: int) -> bool:
    subs = await get_active_subs(user_id)
    return any(s["end_ts"] == 0 or s["end_ts"] > time.time() for s in subs)


async def get_active_plan(user_id: int):
    for s in await get_active_subs(user_id):
        if s["kind"] == "plan" and (s["end_ts"] == 0 or s["end_ts"] > time.time()):
            return s
    return None


async def set_sub_status(sub_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE subscriptions SET status=? WHERE id=?", (status, sub_id))
        await db.commit()


async def update_sub_end(sub_id: int, end_ts: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE subscriptions SET end_ts=?, status='active' WHERE id=?",
                         (end_ts, sub_id))
        await db.commit()


async def mark_notified(sub_id: int, hours: float):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT notified FROM subscriptions WHERE id=?", (sub_id,))
        row = await cur.fetchone()
        lst = json.loads(row[0] or "[]")
        if hours not in lst:
            lst.append(hours)
            await db.execute("UPDATE subscriptions SET notified=? WHERE id=?",
                             (json.dumps(lst), sub_id))
            await db.commit()
            return True
        return False


async def active_subs_all():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM subscriptions WHERE status='active'")
        rows = await cur.fetchall()
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in rows]


async def all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM users")
        rows = await cur.fetchall()
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in rows]


# ------------------------------------------------------------------ settings
async def get_setting(key: str, default=None):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await db.commit()


# ------------------------------------------------------------------ positions
async def get_position(user_id: int, mint: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT * FROM positions WHERE user_id=? AND mint=? ORDER BY id DESC LIMIT 1",
            (user_id, mint),
        )
        row = await cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))


async def get_positions(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT * FROM positions WHERE user_id=? AND qty > 0 ORDER BY updated_at DESC",
            (user_id,),
        )
        rows = await cur.fetchall()
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in rows]


async def add_position_trade(user_id: int, mint: str, symbol: str, qty: float,
                             decimals: int, spent_sol: float, sig: str):
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT * FROM positions WHERE user_id=? AND mint=? ORDER BY id DESC LIMIT 1",
            (user_id, mint),
        )
        row = await cur.fetchone()
        if row:
            new_qty = (row[4] or 0) + qty
            new_spent = (row[6] or 0) + spent_sol
            sigs = json.loads(row[7] or "[]") + [sig]
            await db.execute(
                "UPDATE positions SET qty=?, spent_sol=?, buy_sigs=?, symbol=?, updated_at=? WHERE id=?",
                (new_qty, new_spent, json.dumps(sigs), symbol or row[3], now, row[0]),
            )
        else:
            await db.execute(
                "INSERT INTO positions (user_id, mint, symbol, qty, decimals, spent_sol, "
                "buy_sigs, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (user_id, mint, symbol, qty, decimals, spent_sol, json.dumps([sig]), now, now),
            )
        await db.commit()


async def reduce_position(user_id: int, mint: str, sold_qty: float) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT * FROM positions WHERE user_id=? AND mint=? ORDER BY id DESC LIMIT 1",
            (user_id, mint),
        )
        row = await cur.fetchone()
        if not row:
            return False
        new_qty = (row[4] or 0) - sold_qty
        if new_qty <= 1e-9:
            await db.execute("DELETE FROM positions WHERE id=?", (row[0],))
        else:
            await db.execute(
                "UPDATE positions SET qty=?, updated_at=? WHERE id=?",
                (new_qty, int(time.time()), row[0]),
            )
        await db.commit()
        return True


# ------------------------------------------------------------------ clear trades
async def clear_user_trades(user_id: int):
    """Drop positions and cancel open limit orders (used when a user
    replaces their trading wallet)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM positions WHERE user_id=?", (user_id,))
        await db.execute(
            "UPDATE limit_orders SET status='cancelled' WHERE user_id=? AND status='open'",
            (user_id,))
        await db.commit()


# ------------------------------------------------------------------ limit orders
async def create_limit_order(user_id: int, mint: str, symbol: str, side: str,
                             target_price: float, amount: float, slippage_bps: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO limit_orders (user_id, mint, symbol, side, target_price, "
            "amount, slippage_bps, status, created_at) VALUES (?,?,?,?,?,?,?,'open',?)",
            (user_id, mint, symbol, side, target_price, amount, slippage_bps, int(time.time())),
        )
        await db.commit()
        return cur.lastrowid


async def open_limit_orders():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM limit_orders WHERE status='open'")
        rows = await cur.fetchall()
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in rows]


async def user_limit_orders(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT * FROM limit_orders WHERE user_id=? AND status='open' ORDER BY id DESC",
            (user_id,),
        )
        rows = await cur.fetchall()
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in rows]


async def cancel_limit_order(order_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE limit_orders SET status='cancelled' WHERE id=? AND user_id=? AND status='open'",
            (order_id, user_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def bump_limit_attempt(order_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE limit_orders SET attempts = attempts + 1 WHERE id=?", (order_id,))
        await db.commit()
        cur = await db.execute("SELECT attempts FROM limit_orders WHERE id=?", (order_id,))
        row = await cur.fetchone()
        return row[0] if row else 0


async def mark_limit(order_id: int, status: str, note: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE limit_orders SET status=?, note=? WHERE id=?",
                         (status, note, order_id))
        await db.commit()
