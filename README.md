# Telegram Video Downloader Bot

بوت Telegram بسيط لتنزيل الفيديوهات العامة من:

- TikTok
- Instagram
- YouTube
- Facebook

يعتمد المشروع على Python و `python-telegram-bot` و `yt-dlp`.

## مهم قبل التشغيل

هذا المشروع مخصص للروابط والمحتوى الذي يسمح لك صاحبه أو المنصة بتنزيله. لا يحاول تجاوز الحسابات الخاصة، الحماية بـ DRM، أو متطلبات تسجيل الدخول/قيود الوصول.

## 1. إنشاء بوت Telegram

1. افتح Telegram.
2. تحدث مع `@BotFather`.
3. استخدم `/newbot`.
4. اختر اسمًا وusername للبوت.
5. انسخ الـ Bot Token.

## 2. التشغيل محليًا

متطلبات النظام:

- Python 3.12 أو أحدث
- FFmpeg

ثم:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\\Scripts\\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

ثبّت المكتبات:

```bash
pip install -r requirements.txt
```

انسخ `.env.example` إلى `.env` وأدخل التوكن، ثم شغّل:

```bash
python bot.py
```

> يمكن أيضًا تمرير المتغيرات مباشرة في النظام بدل ملف `.env`.

## 3. تشغيل Docker

أنشئ `.env`:

```env
BOT_TOKEN=ضع_توكن_البوت_هنا
MAX_FILE_SIZE_MB=49
MAX_CONCURRENT_DOWNLOADS=2
DOWNLOAD_TIMEOUT=300
```

ثم:

```bash
docker compose up -d --build
```

## 4. رفع المشروع إلى GitHub

أنشئ مستودعًا جديدًا ثم:

```bash
git init
git add .
git commit -m "Initial Telegram video downloader bot"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git
git push -u origin main
```

**لا ترفع ملف `.env` أو Bot Token إلى GitHub.**

## 5. التشغيل المستمر

GitHub مستودع للكود، وليس خدمة تشغيل مستمرة لبوت Telegram. للبقاء شغالًا 24/7 شغّل المشروع على VPS أو خدمة استضافة تدعم Docker/عمليات طويلة التشغيل.

## الإعدادات

| المتغير | الافتراضي | الوظيفة |
|---|---:|---|
| `BOT_TOKEN` | — | توكن Telegram، مطلوب |
| `MAX_FILE_SIZE_MB` | `49` | الحد الأقصى لحجم الفيديو الذي يقبله البوت |
| `MAX_CONCURRENT_DOWNLOADS` | `2` | عدد التنزيلات المتزامنة |
| `DOWNLOAD_TIMEOUT` | `300` | مهلة التنزيل بالثواني |

## ملاحظات تقنية

- يدعم الروابط المباشرة العامة.
- يستخدم `yt-dlp` لاختيار أفضل صيغة MP4 متاحة.
- يستخدم FFmpeg لدمج الفيديو والصوت عند الحاجة.
- يحذف الملفات المؤقتة بعد الإرسال أو عند حدوث خطأ.
- يمنع تشغيل أكثر من عدد محدد من التنزيلات في الوقت نفسه.

## تطويرات مستقبلية مقترحة

- زر اختيار الجودة.
- دعم إرسال الصوت فقط.
- قائمة انتظار للتنزيلات.
- Redis وقاعدة بيانات للمستخدمين.
- لوحة تحكم للمشرف.
- دعم Cookies للحالات المسموح بها والتي تتطلب تسجيل الدخول، مع مراعاة شروط المنصة.
