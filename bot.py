import asyncio
import logging
import os
import sqlite3

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = os.environ.get("OPENAI_MODEL") or "gpt-5.6-luna"
ADMIN_ID = int(os.environ.get("ADMIN_ID") or "0")
DB_PATH = os.environ.get("DB_PATH") or "novaai.db"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing")

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, name TEXT, messages_left INTEGER DEFAULT 50)")
    conn.execute("CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT, content TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    return conn

def ensure_user(message: Message):
    conn = db(); u = message.from_user
    conn.execute("INSERT OR IGNORE INTO users(user_id,username,name,messages_left) VALUES(?,?,?,50)", (u.id, u.username, u.full_name))
    conn.execute("UPDATE users SET username=?, name=? WHERE user_id=?", (u.username, u.full_name, u.id))
    conn.commit(); row = conn.execute("SELECT messages_left FROM users WHERE user_id=?", (u.id,)).fetchone(); conn.close()
    return row[0]

def balance(user_id: int):
    conn = db(); row = conn.execute("SELECT messages_left FROM users WHERE user_id=?", (user_id,)).fetchone(); conn.close()
    return row[0] if row else 0

def consume(user_id: int):
    conn = db(); conn.execute("UPDATE users SET messages_left=messages_left-1 WHERE user_id=? AND messages_left>0", (user_id,)); conn.commit(); conn.close()

def save_chat(user_id: int, role: str, content: str):
    conn = db(); conn.execute("INSERT INTO chats(user_id,role,content) VALUES(?,?,?)", (user_id, role, content)); conn.commit(); conn.close()

def recent_chat(user_id: int, limit: int = 12):
    conn = db(); rows = conn.execute("SELECT role,content FROM chats WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall(); conn.close()
    return list(reversed(rows))

async def ask_ai(user_id: int, text: str) -> str:
    history = recent_chat(user_id)
    input_items = [{"role": role, "content": content} for role, content in history]
    input_items.append({"role": "user", "content": text})
    payload = {"model": MODEL, "input": input_items, "instructions": "أنت Nova AI، مساعد ذكاء اصطناعي عربي مفيد وودود. أجب بالعربية عند استخدام العربية، وباختصار مفيد. لا تدّعي أنك إنسان."}
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    timeout = aiohttp.ClientTimeout(total=90)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post("https://api.openai.com/v1/responses", headers=headers, json=payload) as r:
            data = await r.json()
            if r.status >= 400:
                logging.error("OpenAI error: %s", data)
                raise RuntimeError(data.get("error", {}).get("message", "AI request failed"))
            return data.get("output_text", "لم أستطع توليد رد الآن.")

keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🧠 ذكاء اصطناعي"), KeyboardButton(text="💰 رصيدي")], [KeyboardButton(text="ℹ️ المساعدة")]], resize_keyboard=True)

@dp.message(CommandStart())
async def start(message: Message):
    ensure_user(message)
    await message.answer("🤖 أهلاً بك في *Nova AI*\n\nأنا مساعدك بالذكاء الاصطناعي. أرسل أي سؤال أو فكرة وسأساعدك.\n\n🎁 رصيدك المجاني: 50 رسالة.", parse_mode="Markdown", reply_markup=keyboard)

@dp.message(Command("balance"))
@dp.message(F.text == "💰 رصيدي")
async def show_balance(message: Message):
    ensure_user(message)
    await message.answer(f"💰 رصيدك الحالي: *{balance(message.from_user.id)}* رسالة.", parse_mode="Markdown")

@dp.message(Command("help"))
@dp.message(F.text == "ℹ️ المساعدة")
async def help_cmd(message: Message):
    await message.answer("🧠 أرسل رسالتك مباشرة وسيرد عليك Nova AI.\n\n/balance — عرض الرصيد\n/start — بدء البوت")

@dp.message(F.text == "🧠 ذكاء اصطناعي")
async def ai_button(message: Message):
    await message.answer("🧠 اكتب سؤالك الآن وسأجيبك.")

@dp.message(F.text)
async def chat(message: Message):
    ensure_user(message)
    if balance(message.from_user.id) <= 0:
        await message.answer("❌ انتهى رصيدك المجاني.")
        return
    await message.bot.send_chat_action(message.chat.id, "typing")
    try:
        answer = await ask_ai(message.from_user.id, message.text)
        save_chat(message.from_user.id, "user", message.text); save_chat(message.from_user.id, "assistant", answer); consume(message.from_user.id)
        await message.answer(answer)
    except Exception:
        logging.exception("AI failure")
        await message.answer("⚠️ حدث خطأ مؤقت أثناء الاتصال بالذكاء الاصطناعي. حاول مرة أخرى.")

async def main():
    db().close(); await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
