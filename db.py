"""
Storage layer — works with BOTH engines:
  • SQLite (default, local dev / DATA_DIR)
  • PostgreSQL (set DATABASE_URL — survives Render restarts, which is why
    generated/imported wallets must be remembered across deploys)

Same API everywhere; callers don't know which engine is active.
"""
import json
import os
import random
import string
import time

DATABASE_URL = (os.getenv("DATABASE_URL", "") or "").strip()
ENGINE = "postgres" if DATABASE_URL.startswith("postgres") else "sqlite"
DB_PATH = os.path.join(os.getenv("DATA_DIR", "."), "runner.db")

_pg_pool = None

if ENGINE == "postgres":
    import asyncpg
else:
    import aiosqlite

SCHEMA_SQLITE = """
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

SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    wallet_priv TEXT,
    wallet_pub TEXT,
    free_used INTEGER DEFAULT 0,
    default_buy DOUBLE PRECISION,
    default_sell DOUBLE PRECISION,
    default_slippage DOUBLE PRECISION DEFAULT 10,
    ref_code TEXT UNIQUE,
    referred_by BIGINT,
    credits_lamports BIGINT DEFAULT 0,
    created_at BIGINT
);
CREATE TABLE IF NOT EXISTS payments (
    tx_sig TEXT PRIMARY KEY,
    user_id BIGINT,
    item TEXT,
    price_lamports BIGINT,
    payer TEXT,
    ts BIGINT
);
CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    kind TEXT,
    item_key TEXT,
    label TEXT,
    price_lamports BIGINT,
    start_ts BIGINT,
    end_ts BIGINT,
    status TEXT DEFAULT 'active',
    tx_sig TEXT,
    payer TEXT,
    invite_link TEXT,
    channel_id TEXT,
    notified TEXT DEFAULT '[]',
    created_at BIGINT
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS positions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    mint TEXT,
    symbol TEXT,
    qty DOUBLE PRECISION,
    decimals INTEGER DEFAULT 6,
    spent_sol DOUBLE PRECISION,
    buy_sigs TEXT DEFAULT '[]',
    created_at BIGINT,
    updated_at BIGINT
);
CREATE TABLE IF NOT EXISTS limit_orders (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    mint TEXT,
    symbol TEXT,
    side TEXT,
    target_price DOUBLE PRECISION,
    amount DOUBLE PRECISION,
    slippage_bps INTEGER DEFAULT 1000,
    attempts INTEGER DEFAULT 0,
    status TEXT DEFAULT 'open',
    note TEXT DEFAULT '',
    created_at BIGINT
);
CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_subs_end ON subscriptions(end_ts);
CREATE INDEX IF NOT EXISTS idx_positions_user ON positions(user_id, mint);
CREATE INDEX IF NOT EXISTS idx_limits_status ON limit_orders(status);
"""


async def init_db():
    global _pg_pool
    if ENGINE == "postgres":
        pool = await _pg()
        async with pool.acquire() as con:
            await con.execute(SCHEMA_PG)
        # Force new connections after schema rebuild to avoid cached statement errors
        try:
            await pool.terminate()
        except Exception:
            pass
        _pg_pool = None
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executescript(SCHEMA_SQLITE)
            await db.commit()


async def _pg():
    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=4)
        except Exception as e:
            raise RuntimeError(
                f"❌ Could not connect to DATABASE_URL. Check the connection "
                f"string in .env / Render. ({str(e)[:160]})"
            ) from e
    return _pg_pool


def _q(sql: str, params):
    """Convert '?' placeholders to $1..$n for PostgreSQL."""
    if ENGINE != "postgres":
        return sql, params
    out, i = [], 0
    for ch in sql:
        if ch == "?":
            i += 1
            out.append(f"${i}")
        else:
            out.append(ch)
    return "".join(out), tuple(params)


async def _fetchone(sql, params=()):
    sql2, p2 = _q(sql, params)
    if ENGINE == "postgres":
        pool = await _pg()
        async with pool.acquire() as con:
            r = await con.fetchrow(sql2, *p2)
        return dict(r) if r else None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(sql2, p2)
        r = await cur.fetchone()
        return dict(r) if r else None


async def _fetchall(sql, params=()):
    sql2, p2 = _q(sql, params)
    if ENGINE == "postgres":
        pool = await _pg()
        async with pool.acquire() as con:
            rows = await con.fetch(sql2, *p2)
        return [dict(r) for r in rows]
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(sql2, p2)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def _execute(sql, params=()):
    sql2, p2 = _q(sql, params)
    if ENGINE == "postgres":
        pool = await _pg()
        async with pool.acquire() as con:
            await con.execute(sql2, *p2)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(sql2, p2)
        await db.commit()


async def _insert(sql, params=()):
    """INSERT ... RETURNING id — returns the new row id on both engines."""
    sql2, p2 = _q(sql, params)
    if ENGINE == "postgres":
        pool = await _pg()
        async with pool.acquire() as con:
            return await con.fetchval(sql2, *p2)
    # sqlite: strip the RETURNING clause (lastrowid works natively)
    if " RETURNING " in sql2:
        sql2 = sql2.split(" RETURNING ")[0]
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(sql2, p2)
        await db.commit()
        return cur.lastrowid


def _is_dup(err) -> bool:
    if ENGINE == "postgres":
        return isinstance(err, asyncpg.UniqueViolationError)
    return isinstance(err, (aiosqlite.IntegrityError, __import__("sqlite3").IntegrityError))


# ------------------------------------------------------------------ users
async def ensure_user(user_id: int, username: str = None, first_name: str = None,
                      referred_by: int = None) -> dict:
    try:
        row = await _fetchone("SELECT * FROM users WHERE id=?", (user_id,))
        if row is None:
            code = f"{user_id:x}{''.join(random.choices(string.ascii_lowercase + string.digits, k=4))}"
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    if ENGINE == "postgres":
                        await _execute(
                            "INSERT INTO users (id, username, first_name, ref_code, referred_by, created_at) "
                            "VALUES (?, ?, ?, ?, ?, ?) "
                            "ON CONFLICT (id) DO UPDATE SET username = EXCLUDED.username, first_name = EXCLUDED.first_name, ref_code = EXCLUDED.ref_code, referred_by = EXCLUDED.referred_by, created_at = EXCLUDED.created_at",
                            (user_id, username, first_name, code, referred_by, int(time.time())),
                        )
                    else:
                        await _execute(
                            "INSERT INTO users (id, username, first_name, ref_code, referred_by, created_at) "
                            "VALUES (?, ?, ?, ?, ?, ?) "
                            "ON CONFLICT(id) DO UPDATE SET username = EXCLUDED.username, first_name = EXCLUDED.first_name, ref_code = EXCLUDED.ref_code, referred_by = EXCLUDED.referred_by, created_at = EXCLUDED.created_at",
                            (user_id, username, first_name, code, referred_by, int(time.time())),
                        )
                    break
                except Exception as e:
                    import logging
                    logging.getLogger("runner").warning(f"ensure_user insert conflict retry {attempt}: {e}")
                    if attempt == max_attempts - 1:
                        raise
                    code = f"{user_id:x}{''.join(random.choices(string.ascii_lowercase + string.digits, k=4))}"
            return await _fetchone("SELECT * FROM users WHERE id=?", (user_id,))
        await _execute(
            "UPDATE users SET username=?, first_name=? WHERE id=?",
            (username or row["username"], first_name or row["first_name"], user_id),
        )
        return await _fetchone("SELECT * FROM users WHERE id=?", (user_id,))
    except Exception as e:
        import logging
        logging.getLogger("runner").error(f"ensure_user failed for user_id={user_id}: {e}", exc_info=True)
        raise


async def get_user(user_id: int):
    return await _fetchone("SELECT * FROM users WHERE id=?", (user_id,))


async def get_user_by_ref(code: str):
    return await _fetchone("SELECT * FROM users WHERE ref_code=?", (code,))


async def count_users():
    r = await _fetchone("SELECT COUNT(*) AS n FROM users")
    return r["n"] if r else 0


async def count_refs(user_id: int):
    r = await _fetchone("SELECT COUNT(*) AS n FROM users WHERE referred_by=?", (user_id,))
    return r["n"] if r else 0


async def set_wallet(user_id: int, priv: str, pub: str):
    """Persist a wallet. Raises if the user row is missing or the write didn't
    stick, so handlers can tell the user instead of failing silently."""
    await _execute("UPDATE users SET wallet_priv=?, wallet_pub=? WHERE id=?",
                   (priv, pub, user_id))
    row = await _fetchone("SELECT wallet_pub FROM users WHERE id=?", (user_id,))
    if not row or row["wallet_pub"] != pub:
        raise RuntimeError(f"set_wallet: wallet did not persist for user {user_id}")


async def bump_free(user_id: int):
    await _execute("UPDATE users SET free_used = free_used + 1 WHERE id=?", (user_id,))


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
    await _execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", vals)


async def add_credits(user_id: int, lamports: int):
    await _execute("UPDATE users SET credits_lamports = credits_lamports + ? WHERE id=?",
                   (lamports, user_id))


async def spend_credits(user_id: int, lamports: int):
    await _execute("UPDATE users SET credits_lamports = credits_lamports - ? WHERE id=?",
                   (lamports, user_id))


# ------------------------------------------------------------------ payments
async def payment_exists(tx_sig: str) -> bool:
    r = await _fetchone("SELECT 1 AS x FROM payments WHERE tx_sig=?", (tx_sig,))
    return r is not None


async def payment_sigs() -> set:
    rows = await _fetchall("SELECT tx_sig FROM payments")
    return {r["tx_sig"] for r in rows}


async def register_payment(tx_sig: str, user_id: int, item: str, lamports: int,
                           payer: str) -> bool:
    try:
        await _execute(
            "INSERT INTO payments (tx_sig, user_id, item, price_lamports, payer, ts) "
            "VALUES (?,?,?,?,?,?)",
            (tx_sig, user_id, item, lamports, payer, int(time.time())),
        )
        return True
    except Exception as e:
        if _is_dup(e):
            return False
        raise


async def total_revenue_lamports():
    r = await _fetchone("SELECT COALESCE(SUM(price_lamports),0) AS s, COUNT(*) AS n FROM payments")
    return r["s"] or 0, r["n"] or 0


# ------------------------------------------------------------------ subscriptions
async def add_subscription(user_id: int, kind: str, item_key: str, label: str,
                           lamports: int, days: int, tx_sig: str, payer: str,
                           invite_link: str = "", channel_id: str = "") -> dict:
    now = int(time.time())
    end_ts = 0 if days == 0 else now + days * 86400
    row = await _fetchone(
        "SELECT * FROM subscriptions WHERE user_id=? AND kind=? AND item_key=? "
        "AND status='active' ORDER BY end_ts DESC LIMIT 1",
        (user_id, kind, item_key),
    )
    if row and days > 0 and row["end_ts"]:
        base = max(row["end_ts"], now)
        end_ts = base + days * 86400
        await _execute(
            "UPDATE subscriptions SET end_ts=?, invite_link=?, status='active' WHERE id=?",
            (end_ts, invite_link or row["invite_link"], row["id"]),
        )
        sub_id = row["id"]
    else:
        sub_id = await _insert(
            "INSERT INTO subscriptions (user_id, kind, item_key, label, price_lamports, "
            "start_ts, end_ts, status, tx_sig, payer, invite_link, channel_id, created_at) "
            "VALUES (?,?,?,?,?,?,?,'active',?,?,?,?,?) RETURNING id",
            (user_id, kind, item_key, label, lamports, now, end_ts, tx_sig, payer,
             invite_link, channel_id, now),
        )
    return await _fetchone("SELECT * FROM subscriptions WHERE id=?", (sub_id,))


async def get_active_subs(user_id: int):
    return await _fetchall(
        "SELECT * FROM subscriptions WHERE user_id=? AND status='active' ORDER BY kind, end_ts",
        (user_id,),
    )


async def has_active(user_id: int) -> bool:
    subs = await get_active_subs(user_id)
    return any(s["end_ts"] == 0 or s["end_ts"] > time.time() for s in subs)


async def get_active_plan(user_id: int):
    for s in await get_active_subs(user_id):
        if s["kind"] == "plan" and (s["end_ts"] == 0 or s["end_ts"] > time.time()):
            return s
    return None


async def set_sub_status(sub_id: int, status: str):
    await _execute("UPDATE subscriptions SET status=? WHERE id=?", (status, sub_id))


async def update_sub_end(sub_id: int, end_ts: int):
    await _execute("UPDATE subscriptions SET end_ts=?, status='active' WHERE id=?",
                   (end_ts, sub_id))


async def mark_notified(sub_id: int, hours: float):
    row = await _fetchone("SELECT notified FROM subscriptions WHERE id=?", (sub_id,))
    lst = json.loads(row["notified"] or "[]")
    if hours not in lst:
        lst.append(hours)
        await _execute("UPDATE subscriptions SET notified=? WHERE id=?",
                       (json.dumps(lst), sub_id))
        return True
    return False


async def active_subs_all():
    return await _fetchall("SELECT * FROM subscriptions WHERE status='active'")


async def all_users():
    return await _fetchall("SELECT * FROM users")


# ------------------------------------------------------------------ settings
async def get_setting(key: str, default=None):
    row = await _fetchone("SELECT value FROM settings WHERE key=?", (key,))
    return row["value"] if row else default


async def set_setting(key: str, value: str):
    if ENGINE == "postgres":
        await _execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
    else:
        await _execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


# ------------------------------------------------------------------ positions
async def get_position(user_id: int, mint: str):
    return await _fetchone(
        "SELECT * FROM positions WHERE user_id=? AND mint=? ORDER BY id DESC LIMIT 1",
        (user_id, mint),
    )


async def get_positions(user_id: int):
    return await _fetchall(
        "SELECT * FROM positions WHERE user_id=? AND qty > 0 ORDER BY updated_at DESC",
        (user_id,),
    )


async def add_position_trade(user_id: int, mint: str, symbol: str, qty: float,
                             decimals: int, spent_sol: float, sig: str):
    now = int(time.time())
    row = await get_position(user_id, mint)
    if row:
        new_qty = (row["qty"] or 0) + qty
        new_spent = (row["spent_sol"] or 0) + spent_sol
        sigs = json.loads(row["buy_sigs"] or "[]") + [sig]
        await _execute(
            "UPDATE positions SET qty=?, spent_sol=?, buy_sigs=?, symbol=?, updated_at=? WHERE id=?",
            (new_qty, new_spent, json.dumps(sigs), symbol or row["symbol"], now, row["id"]),
        )
    else:
        await _execute(
            "INSERT INTO positions (user_id, mint, symbol, qty, decimals, spent_sol, "
            "buy_sigs, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (user_id, mint, symbol, qty, decimals, spent_sol, json.dumps([sig]), now, now),
        )


async def reduce_position(user_id: int, mint: str, sold_qty: float) -> bool:
    row = await get_position(user_id, mint)
    if not row:
        return False
    new_qty = (row["qty"] or 0) - sold_qty
    if new_qty <= 1e-9:
        await _execute("DELETE FROM positions WHERE id=?", (row["id"],))
    else:
        await _execute("UPDATE positions SET qty=?, updated_at=? WHERE id=?",
                       (new_qty, int(time.time()), row["id"]))
    return True


async def clear_user_trades(user_id: int):
    await _execute("DELETE FROM positions WHERE user_id=?", (user_id,))
    await _execute(
        "UPDATE limit_orders SET status='cancelled' WHERE user_id=? AND status='open'",
        (user_id,),
    )


# ------------------------------------------------------------------ limit orders
async def create_limit_order(user_id: int, mint: str, symbol: str, side: str,
                             target_price: float, amount: float, slippage_bps: int) -> int:
    return await _insert(
        "INSERT INTO limit_orders (user_id, mint, symbol, side, target_price, "
        "amount, slippage_bps, status, created_at) VALUES (?,?,?,?,?,?,?,'open',?) RETURNING id",
        (user_id, mint, symbol, side, target_price, amount, slippage_bps, int(time.time())),
    )


async def open_limit_orders():
    return await _fetchall("SELECT * FROM limit_orders WHERE status='open'")


async def user_limit_orders(user_id: int):
    return await _fetchall(
        "SELECT * FROM limit_orders WHERE user_id=? AND status='open' ORDER BY id DESC",
        (user_id,),
    )


async def cancel_limit_order(order_id: int, user_id: int) -> bool:
    await _execute(
        "UPDATE limit_orders SET status='cancelled' WHERE id=? AND user_id=? AND status='open'",
        (order_id, user_id),
    )
    row = await _fetchone("SELECT status FROM limit_orders WHERE id=?", (order_id,))
    return row is not None and row["status"] == "cancelled"


async def bump_limit_attempt(order_id: int) -> int:
    await _execute("UPDATE limit_orders SET attempts = attempts + 1 WHERE id=?", (order_id,))
    row = await _fetchone("SELECT attempts FROM limit_orders WHERE id=?", (order_id,))
    return row["attempts"] if row else 0


async def mark_limit(order_id: int, status: str, note: str = ""):
    await _execute("UPDATE limit_orders SET status=?, note=? WHERE id=?",
                   (status, note, order_id))
