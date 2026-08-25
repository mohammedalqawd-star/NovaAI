# NovaBiz AI 🚀

مساعد ذكاء اصطناعي متقدم داخل Telegram، مبني ببنية modular وقابلة للتوسع.

## 🎬 AI‑Sharari Video Studio

يحتوي المشروع الآن على استوديو فيديو سينمائي داخل Telegram:

- `/video` يبدأ مشروع فيديو جديد.
- أرسل **فيديو مرجعي** لتعلّم اللغة البصرية (بدون نسخ حرفي للمحتوى).
- أرسل **الأغنية/الصوت** الذي تريد استخدامه.
- أرسل **النص** الذي تريد ظهوره على الفيديو.
- يحلل النظام مدة الصوت والإيقاع ويضع نقاط القطع على حدود موسيقية مناسبة.
- يستخرج عينات من الفيديو المرجعي ويرسلها إلى نموذج reference-to-video لتوليد لقطات أصلية.
- يطبّق مظهرًا سينمائيًا موحدًا: تباين مضبوط، إضاءة ليلية، انعكاسات، عمق مجال، حركة كاميرا هادئة وFilm Grain خفيف.
- يركّب النص العربي كـ ASS subtitles فوق الفيديو ويضمّن الصوت الأصلي.
- يدعم الإخراج العمودي 9:16 افتراضيًا مع إعدادات قابلة للتغيير.
- الحد الافتراضي للمدة 120 ثانية، وعدد اللقطات 8، وحجم تنزيل Telegram للفيديو المرجعي 20MB.

### متغيرات الفيديو

- `FAL_KEY` — مفتاح fal.ai، مطلوب للتوليد.
- `VIDEO_MODEL` — افتراضيًا `alibaba/wan-3.0/reference-to-video`.
- `VIDEO_ASPECT_RATIO` — افتراضيًا `9:16`.
- `VIDEO_RESOLUTION` — افتراضيًا `1080p`.
- `VIDEO_MAX_SHOTS` — افتراضيًا `8`.
- `VIDEO_MAX_TELEGRAM_MB` — افتراضيًا `20`.
- `VIDEO_FONT_NAME` — افتراضيًا `DejaVu Sans`.

## 🤖 الميزات العامة

- Telegram Bot باستخدام aiogram 3
- AI Provider مستقل ومتوافق مع OpenAI-compatible APIs
- مزود AI احتياطي عند فشل المزود الأساسي
- Intent Router للبحث والحساب والكتابة والترجمة والبرمجة وغيرها
- Planner حتمي يختار الأدوات الداخلية المسموح بها فقط
- بحث متعدد المصادر: DuckDuckGo + Google News RSS + Wikipedia
- إظهار المصادر ودرجة التحقق عند البحث
- حاسبة آمنة لا تنفذ كود المستخدم
- حسابات المستخدمين + رصيد مجاني قابل للضبط
- SQLite غير متزامنة
- سياق محادثة + ذاكرة مستخدم قابلة للحذف
- تحليل الصور عبر Vision AI عند توفر مزود يدعم الصور
- تحويل الصوت إلى نص ثم تمريره إلى AI
- تحليل PDF وDOCX وTXT وMD وJSON والكود
- تحليل CSV أساسي
- الإدارة: `/status` `/ban` `/unban` `/credit` `/broadcast`
- `/memory_clear` لحذف ذاكرة المستخدم
- إعادة الرصيد تلقائيًا عند فشل استدعاء AI
- Rate limiting لكل مستخدم
- حدود حجم الملفات والرسائل
- Secrets عبر Environment Variables / GitHub Secrets
- اختبارات + GitHub Actions

## 🔑 Secrets ومتغيرات البيئة

مطلوب للتشغيل الكامل:

- `TELEGRAM_BOT_TOKEN`
- `AI_API_KEY`
- `ADMIN_ID`
- `FAL_KEY`

اختياري للمزود الاحتياطي:

- `FALLBACK_AI_API_KEY`
- `FALLBACK_AI_BASE_URL`
- `FALLBACK_AI_MODEL`

اختياري للرؤية والصوت والحماية:

- `VISION_MODEL`
- `SPEECH_MODEL`
- `RATE_LIMIT_PER_MINUTE`
- `AI_BASE_URL`
- `AI_MODEL`
- `FREE_CREDITS`
- `MAX_MESSAGE_CHARS`
- `REQUEST_TIMEOUT`
- `SEARCH_ENABLED`

لا تضع أي Token أو API key داخل Git.

## ▶️ التشغيل محليًا

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN='...'
export AI_API_KEY='...'
export ADMIN_ID='...'
export FAL_KEY='...'
python bot.py
```

للتشغيل بالفيديو يجب توفر `ffmpeg` و`ffprobe`.

## 🧩 الملفات الرئيسية

- `bot.py` — Telegram handlers، الحماية، rate limit، الإدارة
- `video_bot.py` — واجهة مشروع الفيديو داخل Telegram
- `video_engine.py` — تحليل الصوت، نقاط الإيقاع، توليد اللقطات، FFmpeg والترجمة
- `ai.py` — AI، fallback، Speech-to-Text
- `core.py` — Intent Router + Calculator
- `planner.py` — مخطط المهام الآمن
- `search.py` — البحث وتجميع المصادر
- `verifier.py` — التحقق ودرجة الثقة
- `file_engine.py` — الملفات وCSV
- `vision.py` — تحليل الصور
- `memory.py` — خدمة الذاكرة
- `database.py` — SQLite persistence

## 🛡️ مبادئ الأمان

- الحاسبة لا تنفذ كود المستخدم.
- نتائج البحث تعامل كبيانات خارجية وليست تعليمات للنموذج.
- لا يتم وضع Secrets في السجلات أو Git.
- الملفات محدودة الحجم ويتم تحليل الأنواع المدعومة فقط.
- يوجد حد طلبات لكل مستخدم لمنع Flood وإساءة الاستخدام.
- عند فشل استدعاء AI بعد خصم الرصيد، تتم إعادة الرصيد.
- المرجع المرئي للفيديو يستخدم كدليل أسلوبي؛ لا يطلب النظام نسخ الفيديو حرفيًا.

