from __future__ import annotations
import base64

from config import settings


async def analyze_image(ai, image_bytes: bytes, prompt: str = "حلل الصورة واشرح محتواها بدقة.") -> str:
    if len(image_bytes) > 8 * 1024 * 1024:
        raise ValueError("الصورة أكبر من الحد المسموح (8MB).")
    if not settings.vision_model:
        raise RuntimeError("VISION_MODEL is not configured")

    encoded = base64.b64encode(image_bytes).decode("ascii")
    messages = [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
    ]}]
    return await ai.answer(messages, model=settings.vision_model)
