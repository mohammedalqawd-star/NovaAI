from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from smart_montage import build_smart_montage

router = Router(name="ai_sharari_smart_montage")
PROJECTS: dict[int, dict[str, object]] = {}
JOBS: dict[int, asyncio.Task] = {}
MAX_TELEGRAM_DOWNLOAD = int(os.getenv("VIDEO_MAX_TELEGRAM_MB", "20")) * 1024 * 1024
MAX_INPUTS = int(os.getenv("VIDEO_MAX_INPUTS", "20"))


def _state(uid: int) -> dict[str, object]:
    return PROJECTS.setdefault(uid, {"videos": []})


async def _download(bot, file_id: str, dst: Path) -> None:
    info = await bot.get_file(file_id)
    if info.file_size and info.file_size > MAX_TELEGRAM_DOWNLOAD:
        raise ValueError("الملف أكبر من الحد المسموح للتنزيل عبر Telegram Bot API.")
    await bot.download(info, destination=dst)


@router.message(Command("video"))
async def video_help(message: Message):
    uid = message.from_user.id
    old = PROJECTS.pop(uid, None)
    if old and old.get("work"):
        shutil.rmtree(str(old["work"]), ignore_errors=True)
    work = Path(tempfile.mkdtemp(prefix=f"sharari_{uid}_"))
    PROJECTS[uid] = {"videos": [], "work": str(work)}
    await message.answer(
        "🎬 <b>AI‑Sharari Smart Montage</b>\n\n"
        "أرسل الآن فيديوهاتك واحدًا تلو الآخر.\n"
        "⭐ سأحللها وأقسمها إلى لقطات، وأختار أفضل اللقطات من كل فيديو، ثم أرتبها سينمائيًا.\n\n"
        "بعد الانتهاء أرسل: <b>/finish</b>\n"
        "ثم أرسل الأغنية، وبعدها النص الاختياري.\n\n"
        f"الحد الأقصى: {MAX_INPUTS} فيديو."
    )


@router.message(Command("finish"))
async def finish_videos(message: Message):
    state = _state(message.from_user.id)
    videos = state.get("videos") or []
    if not videos:
        await message.answer("⚠️ أرسل فيديو واحدًا على الأقل أولًا.")
        return
    state["waiting_audio"] = True
    await message.answer(
        f"✅ تم استلام {len(videos)} فيديو.\n\n🎵 الآن أرسل الأغنية أو الملف الصوتي."
    )


@router.message(F.video)
async def reference_video(message: Message):
    uid = message.from_user.id
    state = _state(uid)
    if not state.get("work"):
        await message.answer("استخدم /video لبدء مشروع جديد.")
        return
    videos: list[str] = state.setdefault("videos", [])  # type: ignore[assignment]
    if len(videos) >= MAX_INPUTS:
        await message.answer("⚠️ وصلت للحد الأقصى من الفيديوهات. أرسل /finish الآن.")
        return
    path = Path(str(state["work"])) / f"input_{len(videos):02d}.mp4"
    try:
        await _download(message.bot, message.video.file_id, path)
    except Exception as exc:
        await message.answer(f"⚠️ تعذر استلام الفيديو: {exc}")
        return
    videos.append(str(path))
    await message.answer(
        f"✅ الفيديو {len(videos)} تم استلامه.\n"
        "أرسل فيديو آخر أو /finish للانتقال إلى الأغنية."
    )


@router.message(F.audio)
async def reference_audio(message: Message):
    uid = message.from_user.id
    state = _state(uid)
    videos = state.get("videos") or []
    if not videos:
        await message.answer("أرسل الفيديوهات أولًا باستخدام /video.")
        return
    if state.get("audio"):
        await message.answer("🎵 الصوت موجود بالفعل. أرسل النص الآن.")
        return
    work = Path(str(state["work"]))
    path = work / "music.m4a"
    try:
        await _download(message.bot, message.audio.file_id, path)
    except Exception as exc:
        await message.answer(f"⚠️ تعذر استلام الصوت: {exc}")
        return
    state["audio"] = str(path)
    await message.answer(
        "✅ تم استلام الصوت.\n\n"
        "✍️ أرسل النص الذي تريد ظهوره على الفيديو، أو أرسل <b>/nonetext</b> بدون نص."
    )


@router.message(Command("nonetext"))
async def no_text(message: Message):
    state = _state(message.from_user.id)
    if not state.get("audio"):
        await message.answer("أرسل الفيديوهات ثم الصوت أولًا.")
        return
    state["text"] = ""
    await _start_render(message)


@router.message(F.text)
async def montage_text(message: Message):
    uid = message.from_user.id
    state = _state(uid)
    if not state.get("audio") or not state.get("videos"):
        return
    if uid in JOBS and not JOBS[uid].done():
        await message.answer("⏳ يوجد فيديو قيد الإنشاء بالفعل.")
        return
    text = message.text.strip()
    if not text:
        return
    state["text"] = text
    await _start_render(message)


async def _start_render(message: Message):
    uid = message.from_user.id
    state = _state(uid)
    if uid in JOBS and not JOBS[uid].done():
        await message.answer("⏳ يوجد فيديو قيد الإنشاء بالفعل.")
        return
    await message.answer(
        "🚀 <b>بدأت صناعة الفيديو الذكي.</b>\n\n"
        "🔍 تحليل جودة جميع الفيديوهات\n"
        "✂️ اكتشاف وتقسيم المشاهد\n"
        "⭐ اختيار أفضل اللقطات\n"
        "🎵 مزامنة القصات مع الإيقاع\n"
        "🎨 توحيد الصورة والمعالجة السينمائية\n"
        "📝 إضافة النص\n"
        "🎞️ إخراج الفيديو النهائي\n\n"
        "قد يستغرق التحليل والمونتاج عدة دقائق."
    )
    task = asyncio.create_task(_render(message))
    JOBS[uid] = task


async def _render(message: Message):
    uid = message.from_user.id
    state = _state(uid)
    work = Path(str(state["work"]))
    try:
        videos = [Path(x) for x in state.get("videos", [])]  # type: ignore[arg-type]
        output = await build_smart_montage(videos, Path(str(state["audio"])), str(state.get("text", "")), work)
        await message.answer_video(
            FSInputFile(output),
            caption="🎬 AI‑Sharari — تم اختيار أفضل اللقطات وصناعة المونتاج السينمائي 🔥",
        )
    except Exception as exc:
        await message.answer(f"❌ تعذر إنشاء الفيديو.\n\n{str(exc)[:1500]}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
        PROJECTS.pop(uid, None)
        JOBS.pop(uid, None)


def register_video_handlers(dp):
    dp.include_router(router)
