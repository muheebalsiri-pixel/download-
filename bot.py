import asyncio
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import yt_dlp

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("video-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "49"))
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "2"))
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "300"))

SUPPORTED_HOSTS = {
    "youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com",
    "tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com",
    "instagram.com", "www.instagram.com",
    "facebook.com", "www.facebook.com", "fb.watch",
}

URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)


def normalize_url(url: str) -> str:
    return url.strip().rstrip(".,!?)]}>\"'")


def is_supported_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower().lstrip(".")
    except ValueError:
        return False
    return any(host == h or host.endswith("." + h) for h in SUPPORTED_HOSTS)


def extract_url(text: str) -> str | None:
    match = URL_RE.search(text or "")
    if not match:
        return None
    url = normalize_url(match.group(0))
    return url if is_supported_url(url) else None


def human_size(num_bytes: int | None) -> str:
    if not num_bytes:
        return "غير معروف"
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def download_video(url: str, output_dir: str) -> tuple[Path, dict]:
    output_template = str(Path(output_dir) / "%(title).120s-%(id)s.%(ext)s")
    ydl_opts = {
        "outtmpl": output_template,
        "noplaylist": True,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 2,
        "fragment_retries": 2,
        "socket_timeout": 30,
        "merge_output_format": "mp4",
        "format": f"bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            )
        },
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        requested = info.get("requested_downloads") or []
        filepath = None
        for item in requested:
            fp = item.get("filepath")
            if fp:
                filepath = Path(fp)
                break
        if filepath is None:
            prepared = Path(ydl.prepare_filename(info))
            candidates = list(Path(output_dir).glob(prepared.stem + ".*"))
            filepath = candidates[0] if candidates else prepared

        if not filepath.exists():
            files = [p for p in Path(output_dir).iterdir() if p.is_file()]
            if not files:
                raise FileNotFoundError("Downloaded file was not found")
            filepath = max(files, key=lambda p: p.stat().st_mtime)

        return filepath, info


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🎬 أهلاً بك!\n\n"
        "أرسل رابط فيديو عام من TikTok أو Instagram أو YouTube أو Facebook، "
        "وسأحاول تنزيله وإرساله لك.\n\n"
        "ملاحظة: لا يدعم البوت المحتوى الخاص أو المحمي بـ DRM أو أي تجاوز لقيود الوصول."
    )
    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "الاستخدام بسيط:\n"
        "1) انسخ رابط الفيديو.\n"
        "2) أرسله هنا.\n"
        "3) انتظر حتى يكتمل التنزيل.\n\n"
        f"الحد الافتراضي لحجم الملف: {MAX_FILE_SIZE_MB} MB."
    )


def friendly_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "login required" in msg or "sign in" in msg or "private" in msg:
        return "هذا الفيديو يتطلب تسجيل دخول أو أنه خاص، ولا يمكن للبوت الوصول إليه."
    if "unsupported url" in msg:
        return "الرابط غير مدعوم أو غير صالح."
    if "requested format is not available" in msg:
        return "تعذر العثور على صيغة فيديو مناسبة لهذا الرابط."
    if "timed out" in msg or "timeout" in msg:
        return "انتهت مهلة التنزيل. جرّب رابطًا آخر أو أعد الإرسال."
    if "sign in to confirm" in msg:
        return "المنصة تطلب تحققًا أو تسجيل دخول، لذلك تعذر تنزيل الفيديو من هذا الرابط."
    return "تعذر تنزيل الفيديو. تأكد أن الرابط عام ويعمل من المتصفح، ثم حاول مرة أخرى."


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    url = extract_url(update.message.text)
    if not url:
        await update.message.reply_text(
            "أرسل رابطًا مباشرًا عامًا من TikTok أو Instagram أو YouTube أو Facebook."
        )
        return

    status = await update.message.reply_text("⏳ جارٍ فحص الرابط وبدء التنزيل...")
    await update.message.chat.send_action(ChatAction.TYPING)

    async with _semaphore_context(DOWNLOAD_SEMAPHORE):
        temp_dir = tempfile.mkdtemp(prefix="video_bot_")
        try:
            loop = asyncio.get_running_loop()
            await status.edit_text("⬇️ جارٍ تنزيل الفيديو...")
            filepath, info = await asyncio.wait_for(
                loop.run_in_executor(None, download_video, url, temp_dir),
                timeout=DOWNLOAD_TIMEOUT,
            )

            size = filepath.stat().st_size
            max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
            if size > max_bytes:
                await status.edit_text(
                    f"❌ حجم الفيديو {human_size(size)} ويتجاوز الحد الحالي "
                    f"({MAX_FILE_SIZE_MB} MB)."
                )
                return

            title = (info.get("title") or "الفيديو").strip()
            if len(title) > 900:
                title = title[:897] + "..."

            await status.edit_text("📤 اكتمل التنزيل، جارٍ الإرسال...")
            await update.message.chat.send_action(ChatAction.UPLOAD_VIDEO)
            with filepath.open("rb") as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=title,
                    supports_streaming=True,
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=60,
                    pool_timeout=60,
                )
            await status.delete()
        except asyncio.TimeoutError:
            await status.edit_text("❌ انتهت مهلة التنزيل. جرّب مرة أخرى أو استخدم رابطًا آخر.")
        except Exception as exc:
            logger.exception("Download failed for %s", url)
            await status.edit_text(f"❌ {friendly_error(exc)}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class _semaphore_context:
    def __init__(self, semaphore: asyncio.Semaphore):
        self.semaphore = semaphore

    async def __aenter__(self):
        await self.semaphore.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.semaphore.release()
        return False


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is required")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
