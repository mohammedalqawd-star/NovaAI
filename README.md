# NovaBiz AI 🚀

مساعد ذكاء اصطناعي متقدم داخل Telegram، مبني بشكل modular وقابل للتوسع.

## الموجود حالياً

- 🤖 Telegram Bot باستخدام aiogram 3
- 🧠 طبقة AI مستقلة قابلة لتغيير المزود
- 🔀 Intent Router للطلبات الطبيعية
- 🔎 بحث متعدد المصادر: DuckDuckGo + Wikipedia
- 🧮 حاسبة آمنة بدون تنفيذ كود
- 👤 حسابات المستخدمين ورصيد مجاني ابتدائي
- 💾 SQLite غير متزامنة عبر aiosqlite
- 👑 إدارة: `/status` `/ban` `/unban` `/credit` `/broadcast`
- 🛡️ حظر المستخدمين وحدود الرسائل
- 📊 إحصائيات أساسية
- 🔐 Secrets عبر متغيرات البيئة
- ⚙️ GitHub Actions لفحص البنية

## Secrets المطلوبة

`TELEGRAM_BOT_TOKEN` و `AI_API_KEY`.

اختياري: `AI_BASE_URL`, `AI_MODEL`, `ADMIN_ID`, `FREE_CREDITS`.

> لا تضع أي Token أو API key داخل Git.

## التشغيل

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN='...'
export AI_API_KEY='...'
python bot.py
```

## ملاحظة مهمة

هذا هو الأساس التشغيلي لـ NovaBiz AI Ultra Max، وليس ادعاءً بأن جميع الميزات المتقدمة مثل Vision وSpeech وPDF/DOCX وتحليل CSV والذاكرة طويلة الأجل والـAgent متعدد الخطوات مكتملة بعد. البنية الحالية مصممة لإضافتها تدريجياً دون إعادة كتابة البوت بالكامل.
