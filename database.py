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
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            UNIQUE(user_id, key)
        );
        """)
        await db.commit()

async def ensure_user(user):
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users(id, username, first_name, created_at) VALUES (?, ?, ?, ?)", (user.id, user.username, user.first_name, now))
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

async def add_usage(user_id, kind):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO usage(user_id, kind, created_at) VALUES (?, ?, ?)", (user_id, kind, datetime.now(timezone.utc).isoformat()))
        await db.commit()

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
