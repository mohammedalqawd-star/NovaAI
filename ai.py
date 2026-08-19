from openai import AsyncOpenAI
from config import settings

SYSTEM_PROMPT = """أنت NovaBiz AI، مساعد عربي ذكي داخل Telegram.
افهم الطلب قبل الإجابة. لا تدّعي أنك بحثت أو استخدمت أداة ما لم يحدث ذلك فعلاً. لا تخترع مصادر أو روابط أو أرقاماً. أجب بلغة المستخدم، وكن واضحاً ومختصراً افتراضياً. إذا كانت المعلومة متغيرة أو حديثة، نبّه إلى ضرورة البحث الخارجي عندما لا تتوفر أداة بحث. عند عدم اليقين، صرّح به بوضوح."""

class AIEngine:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.ai_api_key, base_url=settings.ai_base_url) if settings.ai_api_key else None

    async def answer(self, messages, model=None):
        if not self.client:
            return "⚠️ محرك الذكاء الاصطناعي غير مُفعّل بعد. أضف AI_API_KEY إلى Secrets."
        response = await self.client.chat.completions.create(
            model=model or settings.ai_model,
            messages=[{"role":"system", "content": SYSTEM_PROMPT}, *messages],
            temperature=0.4,
        )
        return response.choices[0].message.content or "لم أتمكن من توليد إجابة."
