import os
import logging
import csv
from datetime import datetime
from io import StringIO
from collections import Counter
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
import random

# ========== НАСТРОЙКИ ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT1_TOKEN = os.getenv("BOT1_TOKEN")
BOT2_TOKEN = os.getenv("BOT2_TOKEN")

# СПИСОК АДМИНОВ
ADMIN_IDS = [
    5791631996,   # Ваш ID
    5240956863,   # Второй админ
    7640732474,   # Третий админ
]

# ПАРОЛЬ ДЛЯ ВХОДА В АДМИН-ПАНЕЛЬ
ADMIN_PASSWORD = "3536"

LOG_CHANNEL = -1004359363247
CHANNEL_LINK = "https://t.me/managers_stack"
PORT = int(os.getenv("PORT", 8080))
RENDER = os.getenv("RENDER", "false").lower() == "true"

# ========== НИКИ ==========
NICKNAMES = ["Dobry_p2p"]

# ========== БАЗА ДАННЫХ ==========
user_data = []  # Список словарей: {user_id, username, nickname, timestamp}
waiting_states = {}  # Для состояний админов
notifications = {admin_id: True for admin_id in ADMIN_IDS}  # Уведомления включены по умолчанию

# ========== ФУНКЦИИ РАБОТЫ С ДАННЫМИ ==========
def save_user(user_id, username, nickname):
    user_data.append({
        "user_id": user_id,
        "username": username,
        "nickname": nickname,
        "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })

def get_stats():
    total = len(user_data)
    # Считаем популярность ников
    nick_counts = Counter([u["nickname"] for u in user_data])
    popular = nick_counts.most_common(5)  # Топ-5 самых популярных
    return total, popular

def find_user_by_id(user_id):
    for u in user_data:
        if u["user_id"] == user_id:
            return u
    return None

def find_user_by_username(username):
    for u in user_data:
        if u["username"].lower() == username.lower():
            return u
    return None

def export_csv():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["User ID", "Username", "Nickname", "Timestamp"])
    for u in user_data:
        writer.writerow([u["user_id"], u["username"], u["nickname"], u["timestamp"]])
    return output.getvalue()

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_random_emoji():
    emojis = ["🌟", "🎉", "✨", "🌈", "🔥", "💫", "⭐", "🎊"]
    return random.choice(emojis)

# ========== КЛАВИАТУРА ДЛЯ АДМИНА ==========
def get_admin_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="📁 Экспорт CSV")],
            [KeyboardButton(text="🔍 Поиск пользователя")],
            [KeyboardButton(text="🔔 Уведомления")],
            [KeyboardButton(text="❌ Закрыть админ-панель")]
        ],
        resize_keyboard=True
    )
    return keyboard

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
    emoji = get_random_emoji()
    await message.answer(
        f"{emoji} 👋 Привет! Нажми кнопку, чтобы выбрать ник:",
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
    if not NICKNAMES:
        await message.answer("😕 Ники закончились. Обратитесь к администратору.")
        return
    
    keyboard_buttons = []
    for nickname in NICKNAMES:
        keyboard_buttons.append([InlineKeyboardButton(text=nickname, callback_data=f"nick_{nickname}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    emoji = get_random_emoji()
    
    await message.answer(
        f"{emoji} 👇 Выбери, от кого ты пришел:",
        reply_markup=keyboard
    )

@dp2.callback_query(F.data.startswith("nick_"))
async def choose_nickname(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "без юзернейма"
    nickname = callback.data.replace("nick_", "")
    
    # Сохраняем данные
    save_user(user_id, username, nickname)
    
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
    
    # Отправляем уведомления админам (у кого включены)
    for admin_id in ADMIN_IDS:
        if notifications.get(admin_id, True):
            try:
                await bot2.send_message(chat_id=admin_id, text=admin_message)
            except:
                pass
    
    # Отправляем в канал-логер
    try:
        await bot2.send_message(chat_id=LOG_CHANNEL, text=admin_message)
    except:
        pass
    
    emoji = get_random_emoji()
    await callback.answer(f"✅ Ты выбрал ник: {nickname}")
    await callback.message.delete()
    await callback.message.answer(
        f"{emoji} ✅ Отлично! Ты выбрал ник: {nickname}\n\n"
        f"🔗 Переходи в канал:\n{CHANNEL_LINK}"
    )

# ========== АДМИН-ПАНЕЛЬ ==========
@dp2.message(Command("admin"))
async def admin_panel(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("⛔ У вас нет прав администратора.")
        return
    
    waiting_states[user_id] = "waiting_admin_password"
    await message.answer(
        "🔐 **Введите пароль для доступа к админ-панели:**",
        parse_mode="Markdown"
    )

# ========== ОБРАБОТЧИКИ КНОПОК АДМИН-ПАНЕЛИ ==========
@dp2.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    total, popular = get_stats()
    
    text = f"📊 **Статистика**\n\n"
    text += f"👥 Всего пользователей: {total}\n"
    text += f"📝 Всего ников в списке: {len(NICKNAMES)}\n\n"
    
    if popular:
        text += "🏆 **Самые популярные ники:**\n"
        for i, (nick, count) in enumerate(popular, 1):
            emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
            text += f"{emoji} {nick} — {count} чел.\n"
    else:
        text += "📭 Пока нет данных."
    
    await message.answer(text, parse_mode="Markdown")

@dp2.message(F.text == "📁 Экспорт CSV")
async def export_csv_handler(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    if not user_data:
        await message.answer("📭 Нет данных для экспорта.")
        return
    
    csv_data = export_csv()
    await message.answer_document(
        document=("users_export.csv", csv_data.encode("utf-8")),
        caption=f"📁 Экспорт данных ({len(user_data)} пользователей)"
    )

@dp2.message(F.text == "🔍 Поиск пользователя")
async def search_user_start(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    waiting_states[message.from_user.id] = "waiting_search"
    await message.answer(
        "🔍 Введите ID или @username пользователя:",
        reply_markup=None
    )

@dp2.message(F.text == "🔔 Уведомления")
async def notifications_settings(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    current = notifications.get(message.from_user.id, True)
    status = "🔔 Включены" if current else "🔕 Отключены"
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔕 Отключить уведомления" if current else "🔔 Включить уведомления")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        f"**Настройка уведомлений**\n\n"
        f"Текущий статус: {status}\n\n"
        f"Выберите действие:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp2.message(F.text == "🔔 Включить уведомления")
async def enable_notifications(message: Message):
    if not is_admin(message.from_user.id):
        return
    notifications[message.from_user.id] = True
    await message.answer("✅ Уведомления включены!", reply_markup=get_admin_keyboard())

@dp2.message(F.text == "🔕 Отключить уведомления")
async def disable_notifications(message: Message):
    if not is_admin(message.from_user.id):
        return
    notifications[message.from_user.id] = False
    await message.answer("✅ Уведомления отключены!", reply_markup=get_admin_keyboard())

@dp2.message(F.text == "🔙 Назад")
async def back_to_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    await admin_panel_after_password(message)

async def admin_panel_after_password(message: Message):
    """Открывает админ-панель после ввода пароля"""
    total, popular = get_stats()
    await message.answer(
        f"👑 **Админ-панель**\n\n"
        f"📊 Всего пользователей: {total}\n"
        f"🏆 Самый популярный ник: {popular[0][0] if popular else 'Нет данных'}\n\n"
        f"Выберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown"
    )

@dp2.message(F.text == "❌ Закрыть админ-панель")
async def close_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    waiting_states.pop(message.from_user.id, None)
    await message.answer("👋 Админ-панель закрыта.", reply_markup=None)

# ========== ОБРАБОТЧИКИ ТЕКСТОВОГО ВВОДА ==========
@dp2.message(F.text)
async def handle_text_input(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    state = waiting_states.get(user_id)
    
    # Проверка пароля для входа в админку
    if state == "waiting_admin_password":
        if text == ADMIN_PASSWORD:
            waiting_states.pop(user_id, None)
            await message.answer("✅ Доступ разрешен!", reply_markup=get_admin_keyboard())
            total, popular = get_stats()
            await message.answer(
                f"👑 **Админ-панель**\n\n"
                f"📊 Всего пользователей: {total}\n"
                f"🏆 Самый популярный ник: {popular[0][0] if popular else 'Нет данных'}\n\n"
                f"Выберите действие:",
                parse_mode="Markdown"
            )
        else:
            await message.answer("❌ Неверный пароль!")
        return
    
    # Поиск пользователя
    if state == "waiting_search":
        waiting_states.pop(user_id, None)
        
        if not text:
            await message.answer("❌ Введите ID или username.", reply_markup=get_admin_keyboard())
            return
        
        user = None
        if text.isdigit():
            user = find_user_by_id(int(text))
        elif text.startswith("@"):
            user = find_user_by_username(text[1:])
        else:
            user = find_user_by_username(text)
        
        if user:
            await message.answer(
                f"👤 **Найден пользователь:**\n\n"
                f"🆔 ID: {user['user_id']}\n"
                f"👤 Username: @{user['username']}\n"
                f"📛 Выбрал ник: {user['nickname']}\n"
                f"🕐 Время: {user['timestamp']}",
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard()
            )
        else:
            await message.answer(
                f"❌ Пользователь не найден.",
                reply_markup=get_admin_keyboard()
            )
        return
    
    # Если сообщение не распознано
    if is_admin(user_id):
        await message.answer("Используйте кнопки меню.", reply_markup=get_admin_keyboard())

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
