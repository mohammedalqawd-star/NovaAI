import asyncio
import logging
import re
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from config import settings, validate_runtime_config
from database import (
    init_db, ensure_user, get_user, consume_credit, refund_credit, add_usage,
    save_message, get_history, set_credits, set_banned, list_user_ids, stats,
)
from core import route, safe_calculate
from ai import AIEngine
from search import search_web, format_sources

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("novabiz")

validate_runtime_config()
bot = Bot(settings.bot_token)
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
    user = await guard(message)
    if not user:
        return
    await message.answer(
        "👋 أهلاً بك في NovaBiz AI\n\n"
        "🧠 اكتب طلبك مباشرة. أفهم البحث والحساب والترجمة والكتابة والبرمجة والمحادثة.\n"
        "🔎 للأسئلة الحديثة أبحث في مصادر متعددة عندما يطلب السؤال ذلك.\n\n"
        "💡 مثال: احسب 500*20"
    )

@dp.message(Command("me"))
async def me(message: Message):
    user = await guard(message)
    if not user:
        return
    await message.answer(
        f"👤 حسابك\nID: {message.from_user.id}\nالرصيد: {user['credits']}\nالتسجيل: {user['created_at']}"
    )

@dp.message(Command("status"))
async def status(message: Message):
    if message.from_user.id != settings.admin_id:
        return await message.answer("🚫 غير مصرح.")
    users, active, requests = await stats()
    await message.answer(
        f"📊 NovaBiz Status\nالمستخدمون: {users}\nالنشطون خلال 7 أيام: {active}\n"
        f"الطلبات: {requests}\nTelegram: 🟢\nDatabase: 🟢\n"
        f"Search: {'🟢' if settings.search_enabled else '🔴'}\n"
        f"AI: {'🟢' if ai.client else '🔴'}"
    )

@dp.message(Command("ban"))
async def ban(message: Message):
    if message.from_user.id != settings.admin_id:
        return await message.answer("🚫 غير مصرح.")
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.answer("الاستخدام: /ban USER_ID")
    await set_banned(int(parts[1]), True)
    await message.answer("✅ تم الحظر.")

@dp.message(Command("unban"))
async def unban(message: Message):
    if message.from_user.id != settings.admin_id:
        return await message.answer("🚫 غير مصرح.")
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.answer("الاستخدام: /unban USER_ID")
    await set_banned(int(parts[1]), False)
    await message.answer("✅ تم فك الحظر.")

@dp.message(Command("credit"))
async def credit(message: Message):
    if message.from_user.id != settings.admin_id:
        return await message.answer("🚫 غير مصرح.")
    parts = message.text.split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        return await message.answer("الاستخدام: /credit USER_ID AMOUNT")
    await set_credits(int(parts[1]), int(parts[2]))
    await message.answer("✅ تم تحديث الرصيد.")

@dp.message(Command("broadcast"))
async def broadcast(message: Message):
    if message.from_user.id != settings.admin_id:
        return await message.answer("🚫 غير مصرح.")
    text = message.text.partition(" ")[2].strip()
    if not text:
        return await message.answer("الاستخدام: /broadcast الرسالة")
    ok = failed = 0
    for uid in await list_user_ids():
        try:
            await bot.send_message(uid, text)
            ok += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await message.answer(f"📢 اكتمل الإرسال. ناجح: {ok} | فشل: {failed}")

@dp.message(F.text)
async def chat(message: Message):
    user = await guard(message)
    if not user:
        return

    text = message.text.strip()
    if not text:
        return
    if len(text) > settings.max_message_chars:
        return await message.answer("⚠️ الرسالة طويلة جداً.")

    intent = await route(text)

    # Local calculator: no AI credit consumed.
    if "CALCULATOR" in intent.kinds:
        expr = re.sub(r"[^0-9+\-*/%^(). ]", "", text)
        try:
            result = safe_calculate(expr)
            await add_usage(message.from_user.id, "calculator")
            return await message.answer(f"🧮 النتيجة: {result}")
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError):
            pass

    sources = []
    if "SEARCH" in intent.kinds or "NEWS" in intent.kinds:
        sources = await search_web(text)
        if not sources:
            return await message.answer(
                "🔎 لم أجد مصادر كافية للتحقق من هذا الطلب، لذلك لن أدّعي أن لدي نتيجة بحث موثوقة."
            )

    if not await consume_credit(message.from_user.id):
        return await message.answer("💳 انتهى رصيدك. اطلب من المدير إضافة رصيد.")

    await message.bot.send_chat_action(message.chat.id, "typing")
    await save_message(message.from_user.id, "user", text)

    history = await get_history(message.from_user.id, limit=12)
    messages = [{"role": row[0], "content": row[1]} for row in history]

    now = datetime.now(timezone.utc).isoformat()
    prompt = f"الوقت الحالي UTC: {now}\n\nطلب المستخدم الحالي:\n{text}"
    if sources:
        prompt += (
            "\n\nنتائج بحث فعلية. استخدمها فقط فيما تدعمه، ولا تخترع معلومات. "
            "إذا تعارضت النتائج فاذكر التعارض:\n" + format_sources(sources)
        )
    messages[-1] = {"role": "user", "content": prompt}

    try:
        answer = await ai.answer(messages)
    except Exception as exc:
        await refund_credit(message.from_user.id)
        log.exception("AI request failed: %s", exc)
        return await message.answer("⚠️ تعذر الوصول إلى محرك الذكاء الاصطناعي حالياً. تمت إعادة الرصيد لهذه المحاولة.")

    await save_message(message.from_user.id, "assistant", answer)
    await add_usage(message.from_user.id, "+".join(intent.kinds))

    if sources:
        source_lines = [
            f"{i}. {s['title']}\n{s['url']}"
            for i, s in enumerate(sources[:5], 1) if s.get("url")
        ]
        if source_lines:
            answer += "\n\n📚 المصادر:\n" + "\n".join(source_lines)

    # Telegram text messages are sent without HTML parse mode so AI output cannot
    # break the Telegram parser with arbitrary <tags>.
    await message.answer(answer, disable_web_page_preview=True)

async def main():
    await init_db()
    log.info("NovaBiz AI starting")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
