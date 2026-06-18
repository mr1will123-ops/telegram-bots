import os
import logging
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
import sqlite3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT1_TOKEN = os.getenv("BOT1_TOKEN")
BOT2_TOKEN = os.getenv("BOT2_TOKEN")

LOG_CHANNEL = -1004464117954
CHANNEL_LINK = "https://t.me/managers_stack"
PORT = int(os.getenv("PORT", 8080))
RENDER = os.getenv("RENDER", "false").lower() == "true"

DB_NAME = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            nickname TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nicknames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname TEXT UNIQUE NOT NULL
        )
    """)
    cursor.execute("SELECT COUNT(*) FROM nicknames")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO nicknames (nickname) VALUES (?)", ("Dobry_p2p",))
    conn.commit()
    conn.close()

def get_all_nicknames():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT nickname FROM nicknames ORDER BY nickname")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def save_user(user_id, username, nickname):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (user_id, username, nickname, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, username, nickname, datetime.now().strftime("%d.%m.%Y %H:%M:%S"))
    )
    conn.commit()
    conn.close()

init_db()

# ========== БОТ №1 (ПЕРЕХОДНИК) ==========
bot1 = Bot(token=BOT1_TOKEN)
dp1 = Dispatcher()

@dp1.message(Command("start"))
async def start_bot1(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Перейти дальше", callback_data="go_next")]
        ]
    )
    await message.answer("👋 Привет! Нажми кнопку, чтобы выбрать ник:", reply_markup=keyboard)

@dp1.callback_query(F.data == "go_next")
async def go_next(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("🔗 Переходи в бота для выбора ника:\nhttps://t.me/ManagerTeem_bot")

# ========== БОТ №2 (ВЫБОР НИКА) ==========
bot2 = Bot(token=BOT2_TOKEN)
dp2 = Dispatcher()

@dp2.message(Command("start"))
async def start_bot2(message: Message):
    nicks = get_all_nicknames()
    if not nicks:
        await message.answer("😕 Ники закончились.")
        return
    
    keyboard_buttons = []
    for nickname in nicks:
        keyboard_buttons.append([InlineKeyboardButton(text=nickname, callback_data=f"nick_{nickname}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer("👇 Выбери, от кого ты пришел:", reply_markup=keyboard)

@dp2.callback_query(F.data.startswith("nick_"))
async def choose_nickname(callback: CallbackQuery):
    nickname = callback.data.replace("nick_", "")
    user_id = callback.from_user.id
    username = callback.from_user.username or "без юзернейма"
    
    save_user(user_id, username, nickname)
    
    now = datetime.now()
    log_message = (
        f"🔔 НОВЫЙ ВЫБОР НИКА!\n\n"
        f"👤 Юзернейм: @{username}\n"
        f"🆔 ID: {user_id}\n"
        f"📛 Выбрал ник: {nickname}\n"
        f"🕐 Время: {now.strftime('%d.%m.%Y')} | {now.strftime('%H:%M:%S')}"
    )
    
    try:
        await bot2.send_message(chat_id=LOG_CHANNEL, text=log_message)
    except Exception as e:
        logger.error(f"Не удалось отправить в канал: {e}")
    
    await callback.answer(f"✅ Ты выбрал ник: {nickname}")
    await callback.message.delete()
    await callback.message.answer(
        f"✅ Отлично! Ты выбрал ник: {nickname}\n\n🔗 Переходи в канал:\n{CHANNEL_LINK}"
    )

# ========== ВЕБХУКИ ==========
WEBHOOK_PATH1 = "/webhook/bot1"
WEBHOOK_PATH2 = "/webhook/bot2"

async def on_startup(app):
    if RENDER:
        base_url = os.getenv("RENDER_EXTERNAL_URL", "")
        if not base_url:
            logger.error("RENDER_EXTERNAL_URL not set!")
            return
    else:
        base_url = "https://your-domain.com"
    
    await bot1.set_webhook(url=f"{base_url}{WEBHOOK_PATH1}")
    await bot2.set_webhook(url=f"{base_url}{WEBHOOK_PATH2}")
    logger.info("Webhooks set!")

async def on_shutdown(app):
    await bot1.delete_webhook()
    await bot2.delete_webhook()

async def health_check(request):
    return web.Response(text="OK", status=200)

async def webhook_bot1(request):
    return await SimpleRequestHandler(dispatcher=dp1, bot=bot1).handle(request)

async def webhook_bot2(request):
    return await SimpleRequestHandler(dispatcher=dp2, bot=bot2).handle(request)

def main():
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_post(WEBHOOK_PATH1, webhook_bot1)
    app.router.add_post(WEBHOOK_PATH2, webhook_bot2)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    logger.info(f"Server starting on port {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
