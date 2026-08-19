# NovaBiz AI 🚀

مساعد ذكاء اصطناعي متقدم داخل Telegram، مبني ببنية modular وقابلة للتوسع.

## ✅ الميزات الحالية

- 🤖 Telegram Bot باستخدام aiogram 3
- 🧠 AI Provider مستقل ومتوافق مع OpenAI-compatible APIs
- 🔀 Intent Router للبحث والحساب والكتابة والترجمة والبرمجة وغيرها
- 🔎 بحث متعدد المصادر: DuckDuckGo + Google News RSS + Wikipedia
- 📚 إظهار المصادر ودرجة التحقق عند البحث
- 🧮 حاسبة آمنة لا تنفذ كود المستخدم
- 👤 حسابات المستخدمين + رصيد مجاني قابل للضبط
- 💾 SQLite غير متزامنة
- 🧠 سياق محادثة + ذاكرة مستخدم قابلة للحذف
- 🖼️ تحليل الصور عبر Vision AI عند توفر مزود يدعم الصور
- 🎙️ تحويل الصوت إلى نص ثم تمريره إلى AI
- 📄 تحليل PDF وDOCX وTXT وMD وJSON والكود
- 📊 تحليل CSV أساسي بدون استهلاك AI للملخص الإحصائي المحلي
- 👑 الإدارة: `/status` `/ban` `/unban` `/credit` `/broadcast`
- 🧹 `/memory_clear` لحذف ذاكرة المستخدم
- 💳 إعادة الرصيد تلقائياً عند فشل استدعاء AI
- 🛡️ حدود حجم الملفات والرسائل
- 🔐 Secrets عبر Environment Variables / GitHub Secrets
- 🧪 اختبارات + GitHub Actions

## 🔑 Secrets

مطلوب:

- `TELEGRAM_BOT_TOKEN`
- `AI_API_KEY`

اختياري:

- `AI_BASE_URL`
- `AI_MODEL`
- `ADMIN_ID`
- `FREE_CREDITS`
- `MAX_MESSAGE_CHARS`
- `REQUEST_TIMEOUT`
- `SEARCH_ENABLED`

لا تضع أي Token أو API key داخل Git.

## ▶️ التشغيل

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN='...'
export AI_API_KEY='...'
python bot.py
```

## 🧩 الملفات الرئيسية

- `bot.py` — Telegram handlers
- `ai.py` — AI + Speech-to-Text
- `core.py` — Intent Router + Calculator
- `search.py` — البحث وتجميع المصادر
- `verifier.py` — التحقق ودرجة الثقة
- `file_engine.py` — الملفات وCSV
- `vision.py` — تحليل الصور
- `memory.py` — خدمة الذاكرة
- `database.py` — SQLite persistence
- `planner.py` — مخطط المهام الأولي

## 🛡️ مبادئ الأمان

- الحاسبة لا تنفذ كود المستخدم.
- نتائج البحث تعامل كبيانات خارجية وليست تعليمات.
- لا يتم وضع Secrets في السجلات أو Git.
- الملفات محدودة الحجم ويتم تحليل الأنواع المدعومة فقط.
- عند فشل AI بعد خصم الرصيد، تتم إعادة الرصيد.

## 🚧 الخطوات التالية

المرحلة التالية تشمل: تحسين Agent متعدد الخطوات، ذاكرة طويلة الأجل أكثر ذكاءً، استخراج جداول PDF/DOCX، تحليل CSV متقدم، مزودات AI احتياطية، اشتراكات ودفع، ولوحة إدارة ويب.
