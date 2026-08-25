from __future__ import annotations

import asyncio
import math
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import librosa
import numpy as np


MAX_INPUTS = int(os.getenv("VIDEO_MAX_INPUTS", "20"))
MAX_OUTPUT_SECONDS = float(os.getenv("VIDEO_MAX_OUTPUT_SECONDS", "60"))
MAX_CLIPS = int(os.getenv("VIDEO_MAX_CLIPS", "18"))
TARGET_W = int(os.getenv("VIDEO_WIDTH", "1080"))
TARGET_H = int(os.getenv("VIDEO_HEIGHT", "1920"))


@dataclass
class Candidate:
    source: Path
    start: float
    end: float
    score: float
    sharpness: float
    exposure: float
    motion: float


def run(*args: str) -> None:
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr[-3000:] or "ffmpeg failed")


def duration(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        text=True,
    )
    return max(0.1, float(out.strip()))


def _sample_times(total: float, step: float = 0.75) -> list[float]:
    if total <= 1:
        return [0.0]
    return np.arange(0, max(0.01, total - 0.05), step).tolist()


def score_video(path: Path) -> list[Candidate]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path.name}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    total = total_frames / fps if total_frames else duration(path)

    samples: list[tuple[float, float, float, float]] = []
    prev = None
    for t in _sample_times(total):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        sharp = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        mean = float(gray.mean())
        # Prefer usable exposure, avoiding near-black and blown-out frames.
        exposure = max(0.0, 1.0 - abs(mean - 128.0) / 128.0)
        motion = 0.0 if prev is None else float(cv2.absdiff(gray, prev).mean())
        prev = gray
        samples.append((t, sharp, exposure, motion))
    cap.release()
    if not samples:
        return []

    sharp_vals = np.array([x[1] for x in samples], dtype=float)
    motion_vals = np.array([x[3] for x in samples], dtype=float)
    sharp_scale = max(float(np.percentile(sharp_vals, 90)), 1.0)
    motion_scale = max(float(np.percentile(motion_vals, 80)), 1.0)

    candidates: list[Candidate] = []
    for i, (t, sharp, exposure, motion) in enumerate(samples):
        # Around each good sample, create a short cinematic shot. 2.0-4.5s is readable and beat-friendly.
        length = 3.0
        start = max(0.0, min(t - 0.7, total - length))
        end = min(total, start + length)
        sharp_n = min(1.0, math.log1p(sharp) / math.log1p(sharp_scale * 4.0))
        motion_n = min(1.0, motion / motion_scale)
        score = 0.60 * sharp_n + 0.25 * exposure + 0.15 * motion_n
        candidates.append(Candidate(path, start, end, score, sharp_n, exposure, motion_n))

    # Non-maximum suppression: don't select overlapping moments from the same source.
    candidates.sort(key=lambda c: c.score, reverse=True)
    selected: list[Candidate] = []
    for c in candidates:
        if any(c.source == s.source and c.start < s.end and c.end > s.start for s in selected):
            continue
        selected.append(c)
        if len(selected) >= max(8, MAX_CLIPS * 2):
            break
    return selected


def beat_times(audio: Path, max_seconds: float) -> list[float]:
    try:
        y, sr = librosa.load(str(audio), sr=22050, mono=True, duration=max_seconds)
        _, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
        return [float(t) for t in beats if 0.15 < float(t) < max_seconds - 0.15]
    except Exception:
        return []


def assign_durations(candidates: list[Candidate], audio: Path, total: float) -> list[float]:
    beats = beat_times(audio, total)
    if not beats:
        n = max(1, len(candidates))
        return [total / n] * n
    # Beat spacing gives natural cut durations; clamp for readability.
    points = [0.0] + beats + [total]
    gaps = [b - a for a, b in zip(points[:-1], points[1:]) if 1.2 <= b - a <= 6.0]
    if not gaps:
        return [total / len(candidates)] * len(candidates)
    out = []
    for i in range(len(candidates)):
        out.append(max(1.5, min(5.0, gaps[i % len(gaps)])))
    scale = total / sum(out)
    return [x * scale for x in out]


def render_clip(c: Candidate, dst: Path, target_seconds: float) -> None:
    # Vertical crop, cinematic contrast, mild sharpening; no generated content.
    vf = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},"
        "eq=contrast=1.06:saturation=0.88:brightness=0.01,"
        "unsharp=5:5:0.35:5:5:0"
    )
    run(
        "ffmpeg", "-y", "-ss", f"{c.start:.3f}", "-i", str(c.source),
        "-t", f"{target_seconds:.3f}", "-an", "-vf", vf,
        "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", str(dst),
    )


def concat_and_mix(clips: list[Path], audio: Path, text: str, out: Path, work: Path, total: float) -> None:
    manifest = work / "concat.txt"
    manifest.write_text("\n".join(f"file '{p.as_posix().replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'" for p in clips), encoding="utf-8")
    silent = work / "silent.mp4"
    run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest), "-c", "copy", str(silent))

    # Keep the user's text readable and optional. Use drawtext instead of ASS so the bot has no extra subtitle dependency.
    if text.strip():
        escaped = text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")
        vf = (
            "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            f"text='{escaped}':fontcolor=white:fontsize=48:borderw=3:bordercolor=black@0.75:"
            "x=(w-text_w)/2:y=h-260:alpha='if(lt(t,0.4),t/0.4,if(gt(t," + f"{max(0.4, total-0.5):.2f}" + "),(1-t)/0.5,1))'"
        )
    else:
        vf = "null"

    run(
        "ffmpeg", "-y", "-i", str(silent), "-stream_loop", "-1", "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0", "-t", f"{total:.3f}", "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out),
    )


def build_smart_montage(videos: list[Path], audio: Path, text: str, work_root: Path) -> Path:
    if not videos:
        raise ValueError("أرسل فيديو واحدًا على الأقل")
    if len(videos) > MAX_INPUTS:
        videos = videos[:MAX_INPUTS]
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg و ffprobe مطلوبان")

    work = work_root / "smart_montage"
    work.mkdir(parents=True, exist_ok=True)
    candidates: list[Candidate] = []
    for video in videos:
        candidates.extend(score_video(video))
    if not candidates:
        raise RuntimeError("لم أستطع استخراج لقطات صالحة من الفيديوهات")

    # Mix sources rather than taking every best shot from a single clip.
    candidates.sort(key=lambda c: c.score, reverse=True)
    chosen: list[Candidate] = []
    source_counts: dict[Path, int] = {}
    for c in candidates:
        count = source_counts.get(c.source, 0)
        if count >= max(2, math.ceil(MAX_CLIPS / max(1, len(videos))) + 1):
            continue
        chosen.append(c)
        source_counts[c.source] = count + 1
        if len(chosen) >= MAX_CLIPS:
            break

    audio_total = min(MAX_OUTPUT_SECONDS, duration(audio))
    if audio_total < 1.0:
        raise ValueError("الصوت قصير جدًا")
    chosen = chosen[:max(1, min(len(chosen), math.ceil(audio_total / 1.8)))]
    lengths = assign_durations(chosen, audio, audio_total)

    clips: list[Path] = []
    for i, (candidate, length) in enumerate(zip(chosen, lengths)):
        dst = work / f"clip_{i:02d}.mp4"
        render_clip(candidate, dst, length)
        clips.append(dst)

    out = work_root / "AI-Sharari-Smart-Montage.mp4"
    concat_and_mix(clips, audio, text, out, work, audio_total)
    return out


async def build_smart_montage(videos: list[Path], audio: Path, text: str, work_root: Path) -> Path:
    return await asyncio.to_thread(build_smart_montage, videos, audio, text, work_root)
