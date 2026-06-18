import os
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT3_TOKEN = "8882199116:AAG1Ia9owULUQXM9zJ9lYjnyMDbcOP7D6v4"
LOG_CHANNEL = -1004464117954
PORT = int(os.getenv("PORT", 8080))
RENDER = os.getenv("RENDER", "false").lower() == "true"

ADMIN_IDS = [5791631996, 5240956863, 7640732474]

db.init_db()

bot3 = Bot(token=BOT3_TOKEN)
dp3 = Dispatcher()

HELP_TEXT = (
    "👑 **Доступные команды в канале:**\n\n"
    "📊 /stats — Статистика\n"
    "📁 /export — Скачать CSV\n"
    "🔍 /search @username — Поиск по username\n"
    "🔍 /search 123456789 — Поиск по ID\n"
    "➕ /add Ник — Добавить ник\n"
    "➖ /delete Ник — Удалить ник\n"
    "📋 /list — Список ников\n"
    "👥 /users — Последние 10 пользователей\n"
    "🏆 /top — Топ-5 популярных ников\n"
    "❓ /help — Эта справка"
)

@dp3.message()
async def admin_commands(message: Message):
    if message.chat.id != LOG_CHANNEL:
        return
    
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("⛔ Нет прав.")
        return
    
    text = message.text.strip() if message.text else ""
    if not text or not text.startswith("/"):
        return
    
    parts = text.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    
    if command == "/help":
        await message.reply(HELP_TEXT, parse_mode="Markdown")
    elif command == "/stats":
        total, popular = db.get_stats()
        response = f"📊 Всего: {total}\n"
        for nick, count in popular:
            response += f"• {nick}: {count}\n"
        await message.reply(response)
    elif command == "/export":
        csv_data = db.export_csv()
        await message.reply_document(
            document=("users_export.csv", csv_data.encode("utf-8")),
            caption="📁 Экспорт"
        )
    elif command == "/list":
        nicks = db.get_all_nicknames()
        await message.reply("📋 " + "\n".join(nicks) if nicks else "Пусто")
    elif command == "/add" and args:
        if db.add_nickname(args):
            await message.reply(f"✅ {args} добавлен")
        else:
            await message.reply(f"❌ {args} уже есть")
    elif command == "/delete" and args:
        if db.delete_nickname(args):
            await message.reply(f"✅ {args} удалён")
        else:
            await message.reply(f"❌ {args} не найден")
    else:
        await message.reply("Неизвестная команда. /help")

# ========== ВЕБХУК ==========
WEBHOOK_PATH = "/webhook/bot3"

async def on_startup(app):
    if RENDER:
        base_url = os.getenv("RENDER_EXTERNAL_URL", "")
        if not base_url:
            logger.error("RENDER_EXTERNAL_URL not set!")
            return
    else:
        base_url = "https://your-domain.com"
    
    await bot3.set_webhook(url=f"{base_url}{WEBHOOK_PATH}")
    logger.info(f"Admin bot webhook set!")

async def on_shutdown(app):
    await bot3.delete_webhook()

async def health_check(request):
    return web.Response(text="OK", status=200)

async def webhook_bot3(request):
    return await SimpleRequestHandler(dispatcher=dp3, bot=bot3).handle(request)

def main():
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_post(WEBHOOK_PATH, webhook_bot3)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    logger.info(f"Admin bot starting on port {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()