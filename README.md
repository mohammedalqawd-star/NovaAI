# NovaBiz AI 🚀

مساعد ذكاء اصطناعي متقدم داخل Telegram، مبني بشكل modular وقابل للتوسع.

## الموجود حالياً

- 🤖 Telegram Bot باستخدام aiogram 3
- 🧠 طبقة AI مستقلة ومتوافقة مع مزودات OpenAI-compatible مثل Groq
- 🔀 Intent Router للطلبات الطبيعية
- 🔎 بحث متعدد المصادر: DuckDuckGo + Google News RSS + Wikipedia
- 📚 إظهار روابط المصادر وبيانات النشر عندما تتوفر
- 🛡️ طبقة تحقق بسيطة ودرجة ثقة للمخرجات المعتمدة على البحث
- 🧮 حاسبة آمنة بدون تنفيذ كود
- 👤 حسابات المستخدمين ورصيد مجاني ابتدائي
- 💾 SQLite غير متزامنة عبر aiosqlite
- 🧠 ذاكرة محادثة قصيرة محفوظة في قاعدة البيانات
- 👑 إدارة: `/status` `/ban` `/unban` `/credit` `/broadcast`
- 🛡️ حظر المستخدمين وحدود الرسائل
- 💳 إعادة الرصيد تلقائياً إذا فشل استدعاء AI بعد خصمه
- 📊 إحصائيات أساسية
- 🔐 Secrets عبر متغيرات البيئة
- 🧪 اختبارات للحاسبة والموجه
- ⚙️ GitHub Actions للـsyntax والاختبارات

## Secrets المطلوبة

`TELEGRAM_BOT_TOKEN` و `AI_API_KEY`.

اختياري: `AI_BASE_URL`, `AI_MODEL`, `ADMIN_ID`, `FREE_CREDITS`, `MAX_MESSAGE_CHARS`, `REQUEST_TIMEOUT`, `SEARCH_ENABLED`.

> لا تضع أي Token أو API key داخل Git.

## التشغيل

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN='...'
export AI_API_KEY='...'
python bot.py
```

## مبادئ الأمان

- لا يتم تشغيل كود المستخدم من خلال الحاسبة.
- نتائج البحث تعامل كبيانات خارجية وليست تعليمات للنموذج.
- لا يتم استخدام HTML parse mode مع إجابات AI، لمنع كسر Telegram بسبب محتوى غير متوقع.
- أسرار التشغيل تبقى في Environment Variables / GitHub Secrets.
- عند فشل AI بعد خصم رصيد، تتم إعادة الرصيد للمستخدم.

## ما لم يكتمل بعد

Vision، Speech-to-Text، PDF/DOCX، تحليل CSV المتقدم، الذاكرة طويلة الأجل بإدارة المستخدم، Agent متعدد الخطوات، نظام اشتراكات ودفع متكامل، ولوحة إدارة ويب كاملة. هذه المكونات يمكن إضافتها فوق البنية الحالية دون إعادة كتابة النواة.
