import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import settings
from database import init_db, ensure_user, get_user, consume_credit, add_usage, set_credits, set_banned, list_user_ids, stats
from core import route, safe_calculate
from ai import AIEngine
from search import search_web, format_sources

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("novabiz")
bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
ai = AIEngine()

async def guard(message: Message):
    await ensure_user(message.from_user)
    user = await get_user(message.from_user.id)
    if user and user["banned"]:
        await message.answer("🚫 حسابك محظور من استخدام NovaBiz AI.")
        return None
    return user

@dp.message(CommandStart())
async def start(message: Message):
    await ensure_user(message.from_user)
    await message.answer("👋 <b>مرحباً بك في NovaBiz AI</b>\n\n🧠 اكتب طلبك مباشرة. أفهم البحث، الحساب، الترجمة، الكتابة، البرمجة والمحادثة.\n🔎 أستطيع جمع مصادر ويب عندما يكون الطلب حديثاً أو يحتاج بحثاً.\n\n💡 مثال: <i>احسب 500*20</i>")

@dp.message(Command("me"))
async def me(message: Message):
    user = await guard(message)
    if not user: return
    await message.answer(f"👤 <b>حسابك</b>\nID: <code>{message.from_user.id}</code>\nالرصيد: <b>{user['credits']}</b>\nالتسجيل: {user['created_at']}")

@dp.message(Command("status"))
async def status(message: Message):
    if message.from_user.id != settings.admin_id:
        return await message.answer("🚫 غير مصرح.")
    users, active, messages = await stats()
    await message.answer(f"📊 <b>NovaBiz Status</b>\nUsers: {users}\nActive 7d: {active}\nRequests: {messages}\nTelegram: 🟢\nDatabase: 🟢\nSearch: {'🟢' if settings.search_enabled else '🔴'}\nAI: {'🟢' if ai.client else '🔴'}")

@dp.message(Command("ban"))
async def ban(message: Message):
    if message.from_user.id != settings.admin_id: return await message.answer("🚫 غير مصرح.")
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit(): return await message.answer("الاستخدام: /ban USER_ID")
    await set_banned(int(parts[1]), True)
    await message.answer("✅ تم الحظر.")

@dp.message(Command("unban"))
async def unban(message: Message):
    if message.from_user.id != settings.admin_id: return await message.answer("🚫 غير مصرح.")
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit(): return await message.answer("الاستخدام: /unban USER_ID")
    await set_banned(int(parts[1]), False)
    await message.answer("✅ تم فك الحظر.")

@dp.message(Command("credit"))
async def credit(message: Message):
    if message.from_user.id != settings.admin_id: return await message.answer("🚫 غير مصرح.")
    parts = message.text.split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit(): return await message.answer("الاستخدام: /credit USER_ID AMOUNT")
    await set_credits(int(parts[1]), int(parts[2]))
    await message.answer("✅ تم تحديث الرصيد.")

@dp.message(Command("broadcast"))
async def broadcast(message: Message):
    if message.from_user.id != settings.admin_id: return await message.answer("🚫 غير مصرح.")
    text = message.text.partition(" ")[2].strip()
    if not text: return await message.answer("الاستخدام: /broadcast الرسالة")
    ok = failed = 0
    for uid in await list_user_ids():
        try:
            await bot.send_message(uid, text)
            ok += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.04)
    await message.answer(f"📢 اكتمل الإرسال. ناجح: {ok} | فشل: {failed}")

@dp.message(F.text)
async def chat(message: Message):
    user = await guard(message)
    if not user: return
    text = message.text.strip()
    if len(text) > settings.max_message_chars:
        return await message.answer("⚠️ الرسالة طويلة جداً.")
    intent = await route(text)
    if "CALCULATOR" in intent.kinds:
        expr = re.sub(r"[^0-9+\-*/%^(). ]", "", text)
        try:
            result = safe_calculate(expr)
            await add_usage(message.from_user.id, "calculator")
            return await message.answer(f"🧮 <b>النتيجة:</b> <code>{result}</code>")
        except Exception:
            pass
    if not await consume_credit(message.from_user.id):
        return await message.answer("💳 انتهى رصيدك المجاني. اطلب من المدير إضافة رصيد.")
    await add_usage(message.from_user.id, "+".join(intent.kinds))
    await message.bot.send_chat_action(message.chat.id, "typing")
    sources = []
    if "SEARCH" in intent.kinds or "NEWS" in intent.kinds:
        sources = await search_web(text)
        if not sources:
            await message.answer("🔎 لم أجد مصادر كافية للتحقق من الطلب، لذلك لن أدّعي أنني بحثت بنجاح.")
            return
    prompt = text
    if sources:
        prompt += "\n\nهذه نتائج بحث فعلية. استخدمها فقط فيما تدعمه، واذكر المصادر والاختلافات إن وجدت:\n" + format_sources(sources)
    try:
        answer = await ai.answer([{"role": "user", "content": prompt}])
    except Exception as exc:
        log.exception("AI request failed: %s", exc)
        return await message.answer("⚠️ تعذر الوصول إلى محرك الذكاء الاصطناعي حالياً. حاول لاحقاً.")
    if sources:
        answer += "\n\n📚 <b>المصادر:</b>\n" + "\n".join(f"{i}. <a href=\"{s['url']}\">{s['title']}</a>" for i, s in enumerate(sources[:5], 1) if s.get('url'))
    await message.answer(answer, disable_web_page_preview=True)

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())