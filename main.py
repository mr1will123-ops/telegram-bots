import os
import logging
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

# ========== НАСТРОЙКИ ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT1_TOKEN = os.getenv("BOT1_TOKEN")
BOT2_TOKEN = os.getenv("BOT2_TOKEN")

# СПИСОК АДМИНОВ (кому приходят уведомления)
ADMIN_IDS = [
    5791631996,   # Ваш ID
    5240956863,   # Второй админ
    7640732474,   # Третий админ
]

LOG_CHANNEL = -1004359363247  # ID канала
CHANNEL_LINK = "https://t.me/managers_stack"
PORT = int(os.getenv("PORT", 8080))
RENDER = os.getenv("RENDER", "false").lower() == "true"

# ========== НИКИ (ХРАНЯТСЯ В КОДЕ) ==========
NICKNAMES = ["Dobry_p2p"]  # Добавляйте ники сюда через запятую

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
    await message.answer(
        "👋 Привет! Нажми кнопку, чтобы выбрать ник:",
        reply_markup=keyboard
    )

@dp1.callback_query(F.data == "go_next")
async def go_next(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🔗 Переходи в бота для выбора ника:\nhttps://t.me/ManagerTeem_bot"
    )

# ========== БОТ №2 (ВЫБОР НИКА) ==========
bot2 = Bot(token=BOT2_TOKEN)
dp2 = Dispatcher()

@dp2.message(Command("start"))
async def start_bot2(message: Message):
    """Показываем список ников"""
    if not NICKNAMES:
        await message.answer("😕 Ники закончились. Обратитесь к администратору.")
        return
    
    # Создаем кнопки с никами
    keyboard_buttons = []
    for nickname in NICKNAMES:
        keyboard_buttons.append([InlineKeyboardButton(text=nickname, callback_data=f"nick_{nickname}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(
        "👇 Выбери, от кого ты пришел:",
        reply_markup=keyboard
    )

@dp2.callback_query(F.data.startswith("nick_"))
async def choose_nickname(callback: CallbackQuery):
    """Выбор ника"""
    nickname = callback.data.replace("nick_", "")
    user_id = callback.from_user.id
    username = callback.from_user.username or "без юзернейма"
    
    # Отправляем сообщение ВСЕМ админам
    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y")
    time_str = now.strftime("%H:%M:%S")
    
    admin_message = (
        f"🔔 НОВЫЙ ВЫБОР НИКА!\n\n"
        f"👤 Юзернейм: @{username}\n"
        f"🆔 ID: {user_id}\n"
        f"📛 Выбрал ник: {nickname}\n"
        f"🕐 Время: {date_str} | {time_str}"
    )
    
    # Отправляем КАЖДОМУ админу
    for admin_id in ADMIN_IDS:
        try:
            await bot2.send_message(chat_id=admin_id, text=admin_message)
            logger.info(f"Отправлено админу {admin_id}")
        except Exception as e:
            logger.error(f"Не удалось отправить админу {admin_id}: {e}")
    
    # Отправляем в канал-логер
    try:
        await bot2.send_message(chat_id=LOG_CHANNEL, text=admin_message)
        logger.info(f"Отправлено в канал")
    except Exception as e:
        logger.error(f"Не удалось отправить в канал: {e}")
    
    # Ответ пользователю
    await callback.answer(f"✅ Ты выбрал ник: {nickname}")
    await callback.message.delete()
    await callback.message.answer(
        f"✅ Отлично! Ты выбрал ник: {nickname}\n\n"
        f"🔗 Переходи в канал:\n{CHANNEL_LINK}"
    )

# ========== ВЕБХУКИ И СЕРВЕР ==========
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
    
    webhook_url1 = f"{base_url}{WEBHOOK_PATH1}"
    webhook_url2 = f"{base_url}{WEBHOOK_PATH2}"
    
    logger.info(f"Setting webhook bot1: {webhook_url1}")
    logger.info(f"Setting webhook bot2: {webhook_url2}")
    
    await bot1.set_webhook(url=webhook_url1)
    await bot2.set_webhook(url=webhook_url2)
    logger.info("Webhooks set!")

async def on_shutdown():
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
