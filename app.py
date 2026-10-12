import os
import re
import time
import html
import logging
import asyncio
from urllib.parse import quote

import aiohttp
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

# -------------------- CONFIG --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "7960973925:AAG0oWr8NDrj0m3AOnWPAzfC1Q1AC7c_kms").strip()   # Termux: export BOT_TOKEN="..."
API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "https://arjun-bheel-aip.vercel.app/"
).strip().rstrip("/")

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)
REGION_PATTERN = re.compile(r"^[A-Z]{2,5}$")
UID_PATTERN = re.compile(r"^[0-9]{1,20}$")
RATE_LIMIT_SECONDS = 5       # har user ke beech 5 sec gap
MAX_TEXT_LEN = 500           # Telegram 4096 limit se pehle truncate

# -------------------- LOGGING --------------------
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("ARJUN_ZONE_BOT")


def h(value) -> str:
    """Untrusted text ko Telegram HTML ke liye escape karo."""
    s = html.escape(str(value), quote=True)
    return s[:MAX_TEXT_LEN]


def safe_str(value, default="N/A"):
    """API se aaye kisi bhi type ko safe string banao."""
    if value is None:
        return default
    if isinstance(value, dict):
        return str(value)
    return str(value)


# -------------------- RATE LIMIT --------------------
last_call = {}  # user_id -> timestamp

def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    last = last_call.get(user_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        return True
    last_call[user_id] = now
    return False


# -------------------- API CALL --------------------
async def call_visit_api(region: str, uid: str) -> dict:
    """API ko call karo aur safe dict result return karo."""
    url = f"{API_BASE_URL}/{quote(region, safe='')}/{quote(uid, safe='')}"
    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(url) as response:
                body = await response.text()

                if response.status < 200 or response.status >= 300:
                    logger.warning("API HTTP %s", response.status)
                    return {"error": f"API returned HTTP {response.status}"}

                try:
                    data = await response.json(content_type=None)
                except (ValueError, aiohttp.ContentTypeError):
                    logger.error("API non-JSON response")
                    return {"error": "API se invalid response aaya. API URL check karo."}

                if not isinstance(data, dict):
                    return {"error": "API response format samajh nahi aaya."}

                return data

    except asyncio.TimeoutError:
        return {"error": "Request timeout. Thodi der baad try karo."}
    except aiohttp.ClientError:
        logger.exception("Network error")
        return {"error": "API se connect nahi ho paya. Internet ya server check karo."}
    except Exception:
        logger.exception("Unexpected API error")
        return {"error": "Unexpected error. Logs check karo."}


# -------------------- COMMANDS --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    name = update.effective_user.first_name if update.effective_user else "Player"

    text = (
        "╔════════════════════╗\n"
        "  ⚡ <b>ARJUN ZONE</b> ⚡\n"
        "╚════════════════════╝\n\n"
        f"🔥 Welcome, <b>{h(name)}</b>!\n"
        "🤖 <b>VISIT BOT ONLINE</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📌 <b>Commands</b>\n"
        "▪ /start — Panel kholo\n"
        "▪ /help — Guide dekho\n"
        "▪ /info — Bot status\n"
        "▪ /visit <code>&lt;region&gt; &lt;uid&gt;</code> — Visit report lo\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⚡ API ka result configured service pe depend karta hai.\n"
        "👑 <b>Powered by ARJUN ZONE</b>"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    text = (
        "🛠 <b>ARJUN ZONE | GUIDE</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Use:\n<code>/visit IN 123456789</code>\n\n"
        "🌍 Region: 2–5 letters (IN, SG, US…)\n"
        "🆔 UID: sirf digits\n"
        "⏳ Rate limit: 5 second gap har user ke beech\n\n"
        "⚡ <b>Valid UID use karo, stay legendary.</b>"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    # API health ping
    alive = "❓"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as s:
            async with s.get(API_BASE_URL) as r:
                alive = "🟢 Online" if r.status < 500 else "🟠 Issue"
    except Exception:
        alive = "🔴 Offline"

    text = (
        "ℹ️ <b>ARJUN ZONE | STATUS</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🌐 API: <code>{h(API_BASE_URL)}</code>\n"
        f"📡 API Health: <b>{alive}</b>\n"
        f"⏳ Rate Limit: <code>{RATE_LIMIT_SECONDS}s</code>\n"
        f"🕐 Server Time: <code>{time.strftime('%Y-%m-%d %H:%M:%S')}</code>"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def visit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    if message is None:
        return

    if user and is_rate_limited(user.id):
        await message.reply_text(
            f"⏳ <b>Slow down!</b> Har {RATE_LIMIT_SECONDS} second mein ek request.",
            parse_mode=ParseMode.HTML,
        )
        return

    if len(context.args) != 2:
        await message.reply_text(
            "❌ <b>GALAT COMMAND</b>\n\n"
            "Use: <code>/visit &lt;region&gt; &lt;uid&gt;</code>\n"
            "Example: <code>/visit IN 123456789</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    region = context.args[0].upper().strip()
    uid = context.args[1].strip()

    if not REGION_PATTERN.fullmatch(region):
        await message.reply_text(
            "❌ Region 2–5 letters hona chahiye, jaise <code>IN</code>.",
            parse_mode=ParseMode.HTML,
        )
        return

    if not UID_PATTERN.fullmatch(uid):
        await message.reply_text(
            "❌ UID mein sirf digits hon.",
            parse_mode=ParseMode.HTML,
        )
        return

    processing = await message.reply_text(
        "╔════════════════════╗\n"
        "  ⏳ <b>REQUEST IN PROGRESS</b>\n"
        "╚════════════════════╝\n"
        f"🌍 Region: <code>{h(region)}</code>\n"
        f"🆔 UID: <code>{h(uid)}</code>\n\n"
        "⚡ API se connect ho raha hai…",
        parse_mode=ParseMode.HTML,
    )

    result = await call_visit_api(region, uid)

    if result.get("error"):
        await processing.edit_text(
            "╔════════════════════╗\n"
            "  🚫 <b>REQUEST FAILED</b>\n"
            "╚════════════════════╝\n\n"
            f"Reason: {h(result['error'])}\n\n"
            "API URL, connection, region aur UID check karo.\n"
            "🕐 Try again in a few seconds.",
            parse_mode=ParseMode.HTML,
        )
        return

    success_count = safe_str(result.get("success"))
    fail_count = safe_str(result.get("fail"))
    player_name = safe_str(result.get("nickname"), "Unknown")
    player_level = safe_str(result.get("level"))
    player_likes = safe_str(result.get("likes"))
    player_region = safe_str(result.get("region"), region)
    player_uid = safe_str(result.get("uid"), uid)

    report = (
        "╔════════════════════╗\n"
        "  🏆 <b>VISIT REPORT</b>\n"
        "╚════════════════════╝\n\n"
        f"👤 <b>Player:</b> <code>{h(player_name)}</code>\n"
        f"🆔 <b>UID:</b> <code>{h(player_uid)}</code>\n"
        f"🌍 <b>Region:</b> <code>{h(player_region)}</code>\n"
        f"📊 <b>Level:</b> <code>{h(player_level)}</code>\n"
        f"❤️ <b>Likes:</b> <code>{h(player_likes)}</code>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Successful:</b> <code>{h(success_count)}</code>\n"
        f"❌ <b>Failed:</b> <code>{h(fail_count)}</code>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⚡ <b>ARJUN ZONE</b> | <i>Stay legendary.</i>"
    )
    await processing.edit_text(report, parse_mode=ParseMode.HTML)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Update caused error", exc_info=context.error)


# -------------------- MAIN --------------------
def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN missing! Termux mein run karo:\n"
            '  export BOT_TOKEN="apna_token"\n'
            "  python bot.py"
        )

    if not API_BASE_URL.startswith(("https://", "http://")):
        raise SystemExit("API_BASE_URL must start with https:// or http://")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("visit", visit))
    app.add_error_handler(error_handler)

    logger.info("ARJUN ZONE bot start ho raha hai…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()