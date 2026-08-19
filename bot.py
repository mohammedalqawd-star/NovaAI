import asyncio
import ast
import logging
import operator as op
import os
import sqlite3
from datetime import datetime

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.environ.get("BOT_TOKEN") or ""
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or ""
MODEL = os.environ.get("OPENAI_MODEL") or "gpt-5-mini"
ADMIN_ID = int(os.environ.get("ADMIN_ID") or "0")
DB_PATH = os.environ.get("DB_PATH") or "novaai.db"
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN)
dp = Dispatcher()


def db():
    c = sqlite3.connect(DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,username TEXT,name TEXT,messages_left INTEGER DEFAULT 50,created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,role TEXT,content TEXT,created_at TEXT)")
    c.commit(); return c


def ensure_user(m):
    c=db(); u=m.from_user
    c.execute("INSERT OR IGNORE INTO users VALUES(?,?,?,?,?)",(u.id,u.username,u.full_name,50,datetime.utcnow().isoformat()))
    c.execute("UPDATE users SET username=?,name=? WHERE user_id=?",(u.username,u.full_name,u.id)); c.commit()
    n=c.execute("SELECT messages_left FROM users WHERE user_id=?",(u.id,)).fetchone()[0]; c.close(); return n


def balance(uid):
    c=db(); r=c.execute("SELECT messages_left FROM users WHERE user_id=?",(uid,)).fetchone(); c.close(); return r[0] if r else 0


def consume(uid):
    c=db(); c.execute("UPDATE users SET messages_left=messages_left-1 WHERE user_id=? AND messages_left>0",(uid,)); c.commit(); c.close()


def save(uid,role,text):
    c=db(); c.execute("INSERT INTO chats(user_id,role,content,created_at) VALUES(?,?,?,?)",(uid,role,text,datetime.utcnow().isoformat())); c.commit(); c.close()


def history(uid):
    c=db(); r=c.execute("SELECT role,content FROM chats WHERE user_id=? ORDER BY id DESC LIMIT 12",(uid,)).fetchall(); c.close(); return list(reversed(r))


def calc(expr):
    ops={ast.Add:op.add,ast.Sub:op.sub,ast.Mult:op.mul,ast.Div:op.truediv,ast.Pow:op.pow,ast.Mod:op.mod,ast.USub:op.neg,ast.UAdd:op.pos}
    def w(n):
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)): return n.value
        if isinstance(n,ast.BinOp) and type(n.op) in ops: return ops[type(n.op)](w(n.left),w(n.right))
        if isinstance(n,ast.UnaryOp) and type(n.op) in ops: return ops[type(n.op)](w(n.operand))
        raise ValueError()
    return w(ast.parse(expr.replace("^","**"),mode="eval").body)


def free_ai(uid,text):
    t=text.strip(); l=t.lower()
    if l in {"مرحبا","هلا","السلام عليكم","hello","hi"}: return "أهلًا بك 👋 أنا NovaBiz AI. البوت يعمل بنجاح، وأنا جاهز لمساعدتك."
    if any(x in t for x in ("كيف حالك","كيفك","كيف حالكم")): return "بخير والحمد لله 🤖❤️ وجاهز لمساعدتك!"
    if "من أنت" in t or "من انت" in t: return "🤖 أنا NovaBiz AI. أعمل حاليًا في الوضع المجاني بدون مفتاح API."
    if t.startswith("احسب "):
        try:return f"🧮 النتيجة: {calc(t[5:])}"
        except:return "❌ مثال صحيح: احسب 250*4+100"
    if t.startswith("كرر "): return t[5:]
    if t.startswith("اكتب "): return "✍️ مسودة مجانية:\n\n"+t[5:].strip()+"\n\nيمكنك تطويرها وإضافة التفاصيل التي تريدها."
    return "🧠 استلمت رسالتك بنجاح!\n\nهذا هو الوضع المجاني. الأدوات المجانية تعمل بدون API، أما نموذج AI خارجي حقيقي فيحتاج مزودًا يقدم حصة مجانية.\n\nرسالتك: "+t


async def ask_ai(uid,text):
    if not OPENAI_API_KEY: return free_ai(uid,text)
    payload={"model":MODEL,"input":[{"role":r,"content":c} for r,c in history(uid)]+[{"role":"user","content":text}],"instructions":"أنت NovaBiz AI، مساعد عربي مفيد وودود. أجب بالعربية عند استخدام العربية."}
    headers={"Authorization":f"Bearer {OPENAI_API_KEY}","Content-Type":"application/json"}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as s:
        async with s.post("https://api.openai.com/v1/responses",headers=headers,json=payload) as r:
            data=await r.json()
            if r.status>=400: raise RuntimeError(data.get("error",{}).get("message","AI error"))
            return data.get("output_text","لم أستطع توليد رد الآن.")


kb=ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🧠 الذكاء الاصطناعي"),KeyboardButton(text="💰 رصيدي")],
    [KeyboardButton(text="🧮 حاسبة"),KeyboardButton(text="✍️ كتابة")],
    [KeyboardButton(text="👤 حسابي"),KeyboardButton(text="ℹ️ المساعدة")]
],resize_keyboard=True)


@dp.message(CommandStart())
async def start(m:Message):
    ensure_user(m)
    await m.answer("🤖 أهلاً بك في *NovaBiz AI*\n\n🆓 نظام مجاني للتجربة\n🎁 رصيدك: 50 رسالة\n\nأرسل أي رسالة أو اختر خدمة من القائمة.",parse_mode="Markdown",reply_markup=kb)

@dp.message(Command("balance"))
@dp.message(F.text=="💰 رصيدي")
async def bal(m:Message):
    ensure_user(m); await m.answer(f"💰 رصيدك: *{balance(m.from_user.id)}* رسالة",parse_mode="Markdown")

@dp.message(F.text=="👤 حسابي")
async def profile(m:Message):
    ensure_user(m); u=m.from_user
    await m.answer(f"👤 حسابي\n\nID: `{u.id}`\nالاسم: {u.full_name}\nالرصيد: {balance(u.id)} رسالة",parse_mode="Markdown")

@dp.message(F.text=="🧮 حاسبة")
async def calc_help(m:Message): await m.answer("🧮 اكتب مثلًا:\nاحسب 250*4+100\n\nيدعم + - * / % **")

@dp.message(F.text=="✍️ كتابة")
async def write_help(m:Message): await m.answer("✍️ اكتب طلبك بهذا الشكل:\nاكتب إعلان لمحلات القعود\nأو أرسل نصًا تريد تحسينه.")

@dp.message(Command("help"))
@dp.message(F.text=="ℹ️ المساعدة")
async def help_(m:Message): await m.answer("🆓 NovaBiz AI\n\n🧠 ذكاء اصطناعي\n🧮 حاسبة\n✍️ كتابة\n💰 الرصيد\n👤 الحساب\n\n/start\n/balance\n/help")

@dp.message(Command("stats"))
async def stats(m:Message):
    if ADMIN_ID and m.from_user.id!=ADMIN_ID:return
    c=db(); u=c.execute("SELECT COUNT(*) FROM users").fetchone()[0]; q=c.execute("SELECT COUNT(*) FROM chats").fetchone()[0]; c.close()
    await m.answer(f"📊 المستخدمون: {u}\n💬 الرسائل: {q}")

@dp.message(F.text=="🧠 الذكاء الاصطناعي")
async def ai_btn(m:Message): await m.answer("🧠 اكتب سؤالك الآن.")

@dp.message(F.text)
async def chat(m:Message):
    ensure_user(m)
    if balance(m.from_user.id)<=0: await m.answer("❌ انتهى رصيدك المجاني."); return
    await m.bot.send_chat_action(m.chat.id,"typing")
    try:
        ans=await ask_ai(m.from_user.id,m.text); save(m.from_user.id,"user",m.text); save(m.from_user.id,"assistant",ans); consume(m.from_user.id); await m.answer(ans)
    except Exception:
        logging.exception("chat error"); await m.answer("⚠️ حدث خطأ مؤقت. حاول مرة أخرى.")

async def main():
    db().close(); await dp.start_polling(bot)

if __name__=="__main__": asyncio.run(main())
