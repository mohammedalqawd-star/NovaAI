from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from video_engine import build_video

router = Router(name="ai_sharari_video")

# Per-user short-lived project state. Media itself is stored only in the temporary job folder.
PROJECTS: dict[int, dict[str, str]] = {}
JOBS: dict[int, asyncio.Task] = {}

MAX_TELEGRAM_DOWNLOAD = int(os.getenv("VIDEO_MAX_TELEGRAM_MB", "20")) * 1024 * 1024


def _state(uid: int) -> dict[str, str]:
    return PROJECTS.setdefault(uid, {})


async def _download(bot, file_id: str, dst: Path) -> None:
    info = await bot.get_file(file_id)
    if info.file_size and info.file_size > MAX_TELEGRAM_DOWNLOAD:
        raise ValueError("الملف أكبر من الحد المسموح للتنزيل عبر Telegram Bot API.")
    await bot.download(info, destination=dst)


@router.message(Command("video"))
async def video_help(message: Message):
    _state(message.from_user.id).clear()
    await message.answer(
        "🎬 <b>AI‑Sharari Video Studio</b>\n\n"
        "أرسل لي بالترتيب:\n"
        "1️⃣ فيديو مرجعي للأسلوب\n"
        "2️⃣ الصوت/الأغنية\n"
        "3️⃣ النص الذي تريد ظهوره على الفيديو\n\n"
        "وسيتم بناء فيديو سينمائي جديد، مع مزامنة اللقطات مع الإيقاع والنص.\n\n"
        "الأمر /video يعيد بدء مشروع جديد."
    )


@router.message(F.video)
async def reference_video(message: Message):
    uid = message.from_user.id
    state = _state(uid)
    if state.get("video"):
        await message.answer("🎬 لديك فيديو مرجعي بالفعل. أرسل الصوت الآن، أو استخدم /video لبدء مشروع جديد.")
        return
    work = Path(tempfile.mkdtemp(prefix=f"sharari_{uid}_"))
    path = work / "reference.mp4"
    try:
        await _download(message.bot, message.video.file_id, path)
    except Exception as exc:
        shutil.rmtree(work, ignore_errors=True)
        await message.answer(f"⚠️ تعذر استلام الفيديو: {exc}")
        return
    state.update({"video": str(path), "work": str(work)})
    await message.answer("✅ تم استلام الفيديو المرجعي.\n\n🎵 الآن أرسل الصوت أو الأغنية.")


@router.message(F.audio)
async def reference_audio(message: Message):
    uid = message.from_user.id
    state = _state(uid)
    if not state.get("video"):
        await message.answer("أرسل الفيديو المرجعي أولاً. استخدم /video لمعرفة الترتيب.")
        return
    if state.get("audio"):
        await message.answer("🎵 الصوت موجود بالفعل. أرسل النص الآن.")
        return
    work = Path(state["work"])
    path = work / "music.m4a"
    try:
        await _download(message.bot, message.audio.file_id, path)
    except Exception as exc:
        await message.answer(f"⚠️ تعذر استلام الصوت: {exc}")
        return
    state["audio"] = str(path)
    await message.answer(
        "✅ تم استلام الصوت.\n\n"
        "✍️ الآن أرسل <b>النص الذي تريد ظهوره على الفيديو</b>.\n"
        "يمكنك كتابة عدة أسطر؛ سيحافظ النظام على النص كاملًا ويضعه بتنسيق سينمائي."
    )


@router.message(F.text)
async def video_text(message: Message):
    uid = message.from_user.id
    state = _state(uid)
    if not state.get("video") or not state.get("audio"):
        return
    if uid in JOBS and not JOBS[uid].done():
        await message.answer("⏳ يوجد فيديو قيد الإنشاء بالفعل.")
        return
    text = message.text.strip()
    if not text:
        return
    state["text"] = text
    await message.answer(
        "🚀 <b>بدأت صناعة الفيديو.</b>\n\n"
        "🎧 تحليل الإيقاع\n🎬 تحليل أسلوب المرجع\n🤖 توليد اللقطات\n📝 تركيب النص\n🎞️ المونتاج النهائي\n\n"
        "قد يستغرق التوليد عدة دقائق لأن اللقطات تُنشأ بالذكاء الاصطناعي."
    )
    task = asyncio.create_task(_render(message))
    JOBS[uid] = task


async def _render(message: Message):
    uid = message.from_user.id
    state = _state(uid)
    work = Path(state["work"])
    try:
        output = await build_video(Path(state["video"]), Path(state["audio"]), state["text"], work)
        await message.answer_video(FSInputFile(output), caption="🎬 AI‑Sharari — تم إنشاء الفيديو السينمائي بنجاح 🔥")
    except Exception as exc:
        await message.answer(f"❌ تعذر إنشاء الفيديو.\n\n{str(exc)[:1200]}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
        PROJECTS.pop(uid, None)
        JOBS.pop(uid, None)


def register_video_handlers(dp):
    dp.include_router(router)
