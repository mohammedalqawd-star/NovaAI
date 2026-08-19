import aiosqlite
from datetime import datetime, timezone

DB_PATH = "novabiz.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TEXT NOT NULL,
            credits INTEGER NOT NULL DEFAULT 50,
            banned INTEGER NOT NULL DEFAULT 0,
            language TEXT DEFAULT 'ar'
        );
        CREATE TABLE IF NOT EXISTS usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            UNIQUE(user_id, key)
        );
        CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id, id);
        CREATE INDEX IF NOT EXISTS idx_usage_user_id ON usage(user_id, created_at);
        """)
        await db.commit()

async def ensure_user(user):
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users(id, username, first_name, created_at, credits) VALUES (?, ?, ?, ?, ?)", (user.id, user.username, user.first_name, now, 50))
        await db.execute("UPDATE users SET username=?, first_name=? WHERE id=?", (user.username, user.first_name, user.id))
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE id=?", (user_id,))
        return await cur.fetchone()

async def consume_credit(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("UPDATE users SET credits=credits-1 WHERE id=? AND credits>0 AND banned=0", (user_id,))
        await db.commit()
        return cur.rowcount == 1

async def refund_credit(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET credits=credits+1 WHERE id=?", (user_id,))
        await db.commit()

async def add_usage(user_id, kind):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO usage(user_id, kind, created_at) VALUES (?, ?, ?)", (user_id, kind, datetime.now(timezone.utc).isoformat()))
        await db.commit()

async def save_message(user_id, role, content):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO messages(user_id, role, content, created_at) VALUES (?, ?, ?, ?)", (user_id, role, content, datetime.now(timezone.utc).isoformat()))
        await db.commit()

async def get_history(user_id, limit=12):
    limit = max(1, min(int(limit), 30))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT role, content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))
        rows = await cur.fetchall()
    return list(reversed(rows))

async def set_credits(user_id, amount):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET credits=? WHERE id=?", (max(0, amount), user_id))
        await db.commit()

async def set_banned(user_id, banned):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET banned=? WHERE id=?", (1 if banned else 0, user_id))
        await db.commit()

async def list_user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM users WHERE banned=0")
        return [row[0] for row in await cur.fetchall()]

async def stats():
    async with aiosqlite.connect(DB_PATH) as db:
        users = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        active = (await (await db.execute("SELECT COUNT(DISTINCT user_id) FROM usage WHERE created_at >= datetime('now','-7 days')")).fetchone())[0]
        messages = (await (await db.execute("SELECT COUNT(*) FROM usage")).fetchone())[0]
        return users, active, messages
