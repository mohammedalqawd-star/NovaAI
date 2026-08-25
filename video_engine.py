from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

import aiohttp
import fal_client


VIDEO_MODEL = os.getenv("VIDEO_MODEL", "alibaba/wan-3.0/reference-to-video")
ASPECT = os.getenv("VIDEO_ASPECT_RATIO", "9:16")
RESOLUTION = os.getenv("VIDEO_RESOLUTION", "1080p")
MAX_SHOTS = int(os.getenv("VIDEO_MAX_SHOTS", "8"))
FONT_NAME = os.getenv("VIDEO_FONT_NAME", "DejaVu Sans")


def _run(*args: str) -> None:
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr[-3000:] or "ffmpeg failed")


def probe(path: Path) -> dict:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-show_entries",
           "stream=width,height,r_frame_rate", "-of", "json", str(path)]
    out = subprocess.check_output(cmd, text=True)
    data = json.loads(out)
    duration = float(data.get("format", {}).get("duration") or 0)
    stream = next((s for s in data.get("streams", []) if s.get("width")), {})
    return {"duration": duration, "width": int(stream.get("width") or 0),
            "height": int(stream.get("height") or 0), "fps": stream.get("r_frame_rate", "30/1")}


def extract_reference_clips(video: Path, out_dir: Path, count: int = 5) -> list[Path]:
    meta = probe(video)
    duration = max(1.0, meta["duration"])
    count = max(1, min(count, MAX_SHOTS))
    clip_len = min(4.0, max(2.0, duration / count))
    paths = []
    for i in range(count):
        start = max(0.0, min(duration - clip_len, (duration - clip_len) * i / max(1, count - 1)))
        dst = out_dir / f"ref_{i:02d}.mp4"
        _run("ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{clip_len:.3f}",
             "-an", "-vf", "fps=24", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", str(dst))
        paths.append(dst)
    return paths


def extract_audio(path: Path, out: Path) -> None:
    _run("ffmpeg", "-y", "-i", str(path), "-vn", "-ac", "2", "-ar", "44100", "-c:a", "aac", "-b:a", "192k", str(out))


def audio_duration(path: Path) -> float:
    return probe(path)["duration"]


def beat_boundaries(audio: Path, duration: float, max_shots: int = MAX_SHOTS) -> list[float]:
    """Prefer musical beats for cuts; fall back to evenly spaced cinematic cuts."""
    try:
        import librosa
        y, sr = librosa.load(str(audio), sr=22050, mono=True)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
        times = [float(x) for x in beats if 0.15 < float(x) < duration - 0.15]
        # Keep cuts readable: choose beat-aligned points roughly every 2-6 seconds.
        chosen = [0.0]
        for t in times:
            if t - chosen[-1] >= 2.0 and t - chosen[-1] <= 6.0:
                chosen.append(t)
            if len(chosen) >= max_shots:
                break
        if duration - chosen[-1] > 1.0:
            chosen.append(duration)
        if len(chosen) >= 2:
            return chosen
    except Exception:
        pass
    n = max(2, min(max_shots, round(duration / 4.0)))
    return [round(duration * i / n, 3) for i in range(n)] + [duration]


def write_ass(text: str, duration: float, path: Path) -> None:
    safe = text.replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")
    ass = f'''[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Main,{FONT_NAME},58,&H00FFFFFF,&H00FFFFFF,&H90000000,&H50000000,1,0,0,0,100,100,0,0,1,3,1,2,70,70,150,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:00.00,0:59:59.00,Main,,0,0,0,,{safe}\n'''
    path.write_text(ass, encoding="utf-8")


async def _download(url: str, dst: Path) -> None:
    timeout = aiohttp.ClientTimeout(total=900)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            with dst.open("wb") as f:
                while True:
                    chunk = await resp.content.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)


async def _generate_clip(ref_url: str, prompt: str, seconds: float, dst: Path) -> None:
    duration = 5 if seconds <= 5 else 10
    args = {
        "prompt": prompt,
        "reference_video_urls": [ref_url],
        "resolution": RESOLUTION,
        "aspect_ratio": ASPECT,
        "duration": duration,
        "audio": False,
        "enable_prompt_expansion": True,
        "enable_safety_checker": True,
    }
    result = await fal_client.subscribe_async(
        VIDEO_MODEL,
        arguments=args,
        with_logs=False,
        client_timeout=900,
        headers={"X-Fal-Store-IO": "0"},
    )
    video = result.get("video") if isinstance(result, dict) else None
    url = video.get("url") if isinstance(video, dict) else None
    if not url:
        raise RuntimeError(f"Video provider returned no video: {result}")
    await _download(url, dst)


def _concat(files: Iterable[Path], out: Path) -> None:
    manifest = out.parent / "concat.txt"
    manifest.write_text("\n".join(f"file '{p.as_posix().replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'" for p in files), encoding="utf-8")
    _run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest), "-c", "copy", str(out))


def _normalize_clip(src: Path, dst: Path, seconds: float) -> None:
    # Cinematic crop/pad to a clean vertical canvas with subtle motion.
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    _run("ffmpeg", "-y", "-i", str(src), "-t", f"{seconds:.3f}", "-vf", vf,
         "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", str(dst))


def _finalize(clips: list[Path], audio: Path, subtitle: str, out: Path, duration: float, work: Path) -> None:
    silent = work / "silent.mp4"
    _concat(clips, silent)
    ass = work / "captions.ass"
    write_ass(subtitle, duration, ass)
    _run("ffmpeg", "-y", "-i", str(silent), "-i", str(audio), "-vf", f"subtitles={ass}:fontsdir=/usr/share/fonts/truetype/dejavu",
         "-map", "0:v:0", "-map", "1:a:0", "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out))


async def build_video(reference: Path, audio: Path, text: str, work_root: Path) -> Path:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg/ffprobe are required")
    work = work_root / "render"
    work.mkdir(parents=True, exist_ok=True)
    duration = min(audio_duration(audio), 120.0)
    if duration < 1:
        raise ValueError("Audio is too short")

    refs = extract_reference_clips(reference, work / "refs", count=min(5, MAX_SHOTS)) if (work / "refs").mkdir(exist_ok=True) is None else []
    # The expression above intentionally creates the directory first; rebuild if needed.
    if not refs:
        refs = extract_reference_clips(reference, work / "refs", count=min(5, MAX_SHOTS))

    ref_urls = []
    for p in refs:
        ref_urls.append(await fal_client.upload_file(str(p)))

    boundaries = beat_boundaries(audio, duration)
    segments = list(zip(boundaries[:-1], boundaries[1:]))
    # Keep the workload reasonable while preserving beat-aligned structure.
    if len(segments) > MAX_SHOTS:
        segments = segments[:MAX_SHOTS - 1] + [(boundaries[MAX_SHOTS - 1], duration)]

    clips = []
    style = ("cinematic night photography, monochrome or deep charcoal palette, premium film look, "
             "soft practical lights, realistic reflections, controlled contrast, shallow depth of field, "
             "slow deliberate camera movement, elegant composition, subtle film grain, no logos, no watermark")
    for i, (start, end) in enumerate(segments):
        seconds = max(1.5, end - start)
        ref = ref_urls[i % len(ref_urls)]
        prompt = f"{style}. Create a new original scene inspired by the visual language of the reference, not a copy. " \
                 f"Scene {i + 1}: visually match the emotional meaning of this text: {text[:500]}. " \
                 "Use cinematic establishing shots, roads, architecture, water reflections, trees or night lights when appropriate. " \
                 "No readable text inside the generated scene."
        raw = work / f"generated_{i:02d}.mp4"
        await _generate_clip(ref, prompt, seconds, raw)
        norm = work / f"normalized_{i:02d}.mp4"
        _normalize_clip(raw, norm, seconds)
        clips.append(norm)

    output = work_root / "AI-Sharari-final.mp4"
    _finalize(clips, audio, text, output, duration, work)
    return output
