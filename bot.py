import asyncio
import ast
import logging
import operator as op
import os
import re
import sqlite3
import math
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


# Safe local calculator: parses only arithmetic AST nodes, never eval().
CALC_BINOPS={ast.Add:op.add,ast.Sub:op.sub,ast.Mult:op.mul,ast.Div:op.truediv,ast.FloorDiv:op.floordiv,ast.Pow:op.pow,ast.Mod:op.mod}
CALC_UNARY={ast.USub:op.neg,ast.UAdd:op.pos}

def calc(expr):
    expr=expr.replace("^","**").replace("×","*").replace("÷","/")
    if len(expr)>120 or not re.fullmatch(r"[0-9+\-*/().%\s]+",expr): raise ValueError()
    def w(n):
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)) and not isinstance(n.value,bool):
            if abs(n.value)>10**12: raise ValueError()
            return n.value
        if isinstance(n,ast.BinOp) and type(n.op) in CALC_BINOPS:
            left,right=w(n.left),w(n.right)
            if isinstance(n.op,ast.Pow) and abs(right)>10: raise ValueError()
            value=CALC_BINOPS[type(n.op)](left,right)
            if not math.isfinite(value) or abs(value)>10**15: raise ValueError()
            return value
        if isinstance(n,ast.UnaryOp) and type(n.op) in CALC_UNARY: return CALC_UNARY[type(n.op)](w(n.operand))
        raise ValueError()
    return w(ast.parse(expr,mode="eval").body)


def fmt_num(v):
    if isinstance(v,float) and v.is_integer(): return str(int(v))
    return f"{v:.10g}" if isinstance(v,float) else str(v)


def extract_calc(t):
    for p in ("احسب","حاسبة","حساب","calculate","calc"):
        if t.lower().startswith(p.lower()):
            x=t[len(p):].strip(" :：")
            if x:return x
    if re.fullmatch(r"[0-9+\-*/().%^×÷\s]+",t) and any(ch.isdigit() for ch in t): return t
    return None


def writing(t):
    req=re.sub(r"^(اكتب|اكتب لي|اكتبلي|صياغة|صغ|حسن|حسّن|write|draft)\s*","",t,flags=re.I).strip()
    l=req.lower()
    if any(k in l for k in ("إعلان","اعلان","تسويق","محل","متجر")):
        subject=req or "محلات القعود"
        return f"📣 إعلان احترافي\n\n🔥 {subject}\n\nجودة مضمونة، خدمة ممتازة وأسعار مناسبة.\nنوفر لكم ما تحتاجونه بكل ثقة واهتمام.\n\n📍 زورونا اليوم\n📞 تواصلوا معنا لمعرفة التفاصيل\n\n⭐ محلات القعود — ثقة وجودة في كل تعامل"
    if "تهنئة" in l or "مبارك" in l:
        return "🎉 تهنئة جميلة\n\nألف مبارك! نسأل الله لكم دوام الفرح والنجاح والتوفيق. 🌷"
    if "رسالة" in l or "واتساب" in l:
        return "💬 رسالة جاهزة:\n\nالسلام عليكم، نرحب بكم ونسعد بخدمتكم. لأي استفسار أو طلب، تواصلوا معنا وسنكون سعيدين بمساعدتكم. 🌟"
    if "سيرة" in l or "cv" in l:
        return "📄 قالب سيرة ذاتية:\n\nالاسم:\nرقم الهاتف:\nالبريد الإلكتروني:\nالمهارات:\nالخبرات:\nالتعليم:\nالهدف المهني:"
    return f"✍️ صياغة مجانية:\n\n{req or 'اكتب إعلان لمحلات القعود'}\n\nأرسل نوع النص والهدف والجمهور للحصول على صياغة أدق."


def free_tool(uid,t):
    x=t.strip(); l=x.lower(); expr=extract_calc(x)
    if expr:
        try:return f"🧮 النتيجة: {fmt_num(calc(expr))}"
        except ZeroDivisionError:return "❌ لا يمكن القسمة على صفر."
        except:return "❌ العملية غير صحيحة. مثال: احسب 250*4+100"
    if re.match(r"^(اكتب|اكتب لي|اكتبلي|صياغة|صغ|حسن|حسّن|write|draft)\b",x,re.I): return writing(x)
    if l.startswith("عدد الكلمات:") or l.startswith("احسب الكلمات:"):
        text=x.split(":",1)[1].strip(); return f"🔢 عدد الكلمات: {len(text.split())}\n🔤 عدد الأحرف: {len(text)}"
    if l.startswith("اعكس:") or l.startswith("اعكس "):
        text=x.split(":",1)[1].strip() if ":" in x else x[5:].strip(); return f"🔄 النص المعكوس:\n{text[::-1]}"
    if l.startswith("كرر "):
        parts=x[5:].rsplit(" ",1)
        if len(parts)==2 and parts[1].isdigit() and int(parts[1])<=20:return "\n".join([parts[0]]*int(parts[1]))
    if x in ("مرحبا","هلا","السلام عليكم") or l in ("hello","hi"): return "🤖 أهلاً بك! أنا NovaBiz AI، وجاهز لمساعدتك."
    if any(k in x for k in ("كيف حالك","كيفك","كيف حالكم")): return "بخير والحمد لله 🤖❤️ وجاهز لمساعدتك!"
    if "من أنت" in x or "من انت" in x: return "🤖 أنا NovaBiz AI. أعمل حاليًا بأدوات مجانية محلية بدون API."
    return None


async def ask_ai(uid,text):
    if OPENAI_API_KEY:
        payload={"model":MODEL,"input":[{"role":r,"content":c} for r,c in history(uid)]+[{"role":"user","content":text}],"instructions":"أنت NovaBiz AI، مساعد عربي مفيد وودود. أجب بالعربية عند استخدام العربية."}
        headers={"Authorization":f"Bearer {OPENAI_API_KEY}","Content-Type":"application/json"}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as s:
            async with s.post("https://api.openai.com/v1/responses",headers=headers,json=payload) as r:
                data=await r.json()
                if r.status>=400: raise RuntimeError(data.get("error",{}).get("message","AI error"))
                return data.get("output_text","لم أستطع توليد رد الآن.")
    result=free_tool(uid,text)
    if result:return result
    return "🆓 الأدوات المجانية متاحة الآن:\n\n🧮 احسب 250*4+100\n✍️ اكتب إعلان لمحلات القعود\n🔢 عدد الكلمات: هذا نص\n🔄 اعكس: مرحباً\n🔁 كرر مرحبا 3"


kb=ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🧠 الذكاء الاصطناعي"),KeyboardButton(text="💰 رصيدي")],
    [KeyboardButton(text="🧮 حاسبة"),KeyboardButton(text="✍️ كتابة")],
    [KeyboardButton(text="🔧 الأدوات المجانية"),KeyboardButton(text="👤 حسابي")],
    [KeyboardButton(text="ℹ️ المساعدة")]
],resize_keyboard=True)


@dp.message(CommandStart())
async def start(m:Message):
    ensure_user(m); await m.answer("🤖 أهلاً بك في *NovaBiz AI*\n\n🆓 أدوات مجانية تعمل بدون API.\n🎁 رصيدك: 50 رسالة\n\nأرسل طلبك أو اختر خدمة من القائمة.",parse_mode="Markdown",reply_markup=kb)

@dp.message(Command("balance"))
@dp.message(F.text=="💰 رصيدي")
async def bal(m:Message):
    ensure_user(m); await m.answer(f"💰 رصيدك: *{balance(m.from_user.id)}* رسالة",parse_mode="Markdown")

@dp.message(F.text=="👤 حسابي")
async def profile(m:Message):
    ensure_user(m); u=m.from_user; await m.answer(f"👤 حسابي\n\nID: `{u.id}`\nالاسم: {u.full_name}\nالرصيد: {balance(u.id)} رسالة",parse_mode="Markdown")

@dp.message(F.text=="🧮 حاسبة")
async def calc_help(m:Message): await m.answer("🧮 اكتب مثلًا:\nاحسب 250*4+100\nأو أرسل 25*4+10")

@dp.message(F.text=="✍️ كتابة")
async def write_help(m:Message): await m.answer("✍️ اكتب طلبك، مثل:\nاكتب إعلان لمحلات القعود\nاكتب رسالة ترحيب للزبائن\nاكتب تهنئة")

@dp.message(F.text=="🔧 الأدوات المجانية")
async def tools(m:Message): await m.answer("🔧 الأدوات المجانية:\n\n🧮 احسب 250*4+100\n✍️ اكتب إعلان لمحلات القعود\n🔢 عدد الكلمات: هذا نص\n🔄 اعكس: مرحباً\n🔁 كرر مرحبا 3\n\nتعمل محليًا بدون API.")

@dp.message(Command("help"))
@dp.message(F.text=="ℹ️ المساعدة")
async def help_(m:Message): await m.answer("🆓 NovaBiz AI\n\n🧠 ذكاء اصطناعي\n🧮 حاسبة\n✍️ كتابة\n🔧 أدوات مجانية\n💰 الرصيد\n👤 الحساب\n\n/start\n/balance\n/help")

@dp.message(Command("stats"))
async def stats(m:Message):
    if ADMIN_ID and m.from_user.id!=ADMIN_ID:return
    c=db(); u=c.execute("SELECT COUNT(*) FROM users").fetchone()[0]; q=c.execute("SELECT COUNT(*) FROM chats").fetchone()[0]; c.close(); await m.answer(f"📊 المستخدمون: {u}\n💬 الرسائل: {q}")

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

async def main(): db().close(); await dp.start_polling(bot)
if __name__=="__main__": asyncio.run(main())
