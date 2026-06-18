import os
import logging
import csv
import sqlite3
from datetime import datetime
from io import StringIO
from collections import Counter
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT1_TOKEN = os.getenv("BOT1_TOKEN")
BOT2_TOKEN = os.getenv("BOT2_TOKEN")
ADMIN_IDS = [5791631996, 5240956863, 7640732474]
ADMIN_PASSWORD = "3536"
LOG_CHANNEL = -1004359363247
CHANNEL_LINK = "https://t.me/managers_stack"
PORT = int(os.getenv("PORT", 8080))
RENDER = os.getenv("RENDER", "false").lower() == "true"
NICKNAMES = ["Dobry_p2p"]

# ========== БАЗА ДАННЫХ SQLITE ==========
DB_NAME = "bot_database.db"

def init_db():
    """Создаёт таблицу при первом запуске"""
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
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

def save_user(user_id, username, nickname):
    """Сохраняет пользователя в БД"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (user_id, username, nickname, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, username, nickname, datetime.now().strftime("%d.%m.%Y %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def get_all_users():
    """Возвращает всех пользователей из БД"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, nickname, timestamp FROM users ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"user_id": r[0], "username": r[1], "nickname": r[2], "timestamp": r[3]} for r in rows]

def get_stats():
    """Возвращает статистику"""
    users = get_all_users()
    total = len(users)
    nicknames = [u["nickname"] for u in users]
    popular = Counter(nicknames).most_common(5)
    return total, popular

def find_user_by_id(user_id):
    """Поиск пользователя по ID"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, nickname, timestamp FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "username": row[1], "nickname": row[2], "timestamp": row[3]}
    return None

def find_user_by_username(username):
    """Поиск пользователя по username"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, nickname, timestamp FROM users WHERE username LIKE ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "username": row[1], "nickname": row[2], "timestamp": row[3]}
    return None

def export_csv():
    """Экспортирует данные в CSV"""
    users = get_all_users()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["User ID", "Username", "Nickname", "Timestamp"])
    for u in users:
        writer.writerow([u["user_id"], u["username"], u["nickname"], u["timestamp"]])
    return output.getvalue()

# ========== НАСТРОЙКИ УВЕДОМЛЕНИЙ (хранятся в памяти) ==========
notifications = {admin_id: True for admin_id in ADMIN_IDS}
waiting_states = {}

# ========== КЛАВИАТУРЫ ==========
def admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="📁 Экспорт CSV")],
            [KeyboardButton(text="🔍 Поиск пользователя")],
            [KeyboardButton(text="🔔 Уведомления")],
            [KeyboardButton(text="❌ Закрыть админ-панель")]
        ],
        resize_keyboard=True
    )

def is_admin(user_id):
    return user_id in ADMIN_IDS

def random_emoji():
    return random.choice(["🌟", "🎉", "✨", "🌈", "🔥", "💫", "⭐", "🎊"])

# ========== БОТ №1 ==========
bot1 = Bot(token=BOT1_TOKEN)
dp1 = Dispatcher()

@dp1.message(Command("start"))
async def start_bot1(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➡️ Перейти дальше", callback_data="go_next")]])
    await message.answer(f"{random_emoji()} 👋 Привет! Нажми кнопку, чтобы выбрать ник:", reply_markup=keyboard)

@dp1.callback_query(F.data == "go_next")
async def go_next(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("🔗 Переходи в бота для выбора ника:\nhttps://t.me/ManagerTeem_bot")

# ========== БОТ №2 ==========
bot2 = Bot(token=BOT2_TOKEN)
dp2 = Dispatcher()

@dp2.message(Command("start"))
async def start_bot2(message: Message):
    if not NICKNAMES:
        await message.answer("😕 Ники закончились. Обратитесь к администратору.")
        return
    buttons = [[InlineKeyboardButton(text=nick, callback_data=f"nick_{nick}")] for nick in NICKNAMES]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(f"{random_emoji()} 👇 Выбери, от кого ты пришел:", reply_markup=keyboard)

@dp2.callback_query(F.data.startswith("nick_"))
async def choose_nickname(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "без юзернейма"
    nickname = callback.data.replace("nick_", "")
    
    # Сохраняем в БД
    save_user(user_id, username, nickname)
    
    msg = f"🔔 НОВЫЙ ВЫБОР НИКА!\n\n👤 Юзернейм: @{username}\n🆔 ID: {user_id}\n📛 Выбрал ник: {nickname}\n🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    
    for admin_id in ADMIN_IDS:
        if notifications.get(admin_id, True):
            try:
                await bot2.send_message(chat_id=admin_id, text=msg)
            except:
                pass
    try:
        await bot2.send_message(chat_id=LOG_CHANNEL, text=msg)
    except:
        pass
    
    await callback.answer(f"✅ Ты выбрал ник: {nickname}")
    await callback.message.delete()
    await callback.message.answer(f"{random_emoji()} ✅ Отлично! Ты выбрал ник: {nickname}\n\n🔗 Переходи в канал:\n{CHANNEL_LINK}")

# ========== АДМИН-ПАНЕЛЬ ==========
@dp2.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора.")
        return
    waiting_states[message.from_user.id] = "waiting_admin_password"
    await message.answer("🔐 **Введите пароль для доступа к админ-панели:**", parse_mode="Markdown")

@dp2.message(F.text == "📊 Статистика")
async def stats_handler(message: Message):
    if not is_admin(message.from_user.id):
        return
    total, popular = get_stats()
    text = f"📊 **Статистика**\n\n👥 Всего пользователей: {total}\n📝 Всего ников: {len(NICKNAMES)}\n\n"
    if popular:
        text += "🏆 **Самые популярные ники:**\n"
        for i, (nick, count) in enumerate(popular, 1):
            emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
            text += f"{emoji} {nick} — {count} чел.\n"
    else:
        text += "📭 Пока нет данных."
    await message.answer(text, parse_mode="Markdown")

@dp2.message(F.text == "📁 Экспорт CSV")
async def export_handler(message: Message):
    if not is_admin(message.from_user.id):
        return
    users = get_all_users()
    if not users:
        await message.answer("📭 Нет данных для экспорта.")
        return
    csv_data = export_csv()
    await message.answer_document(
        document=("users_export.csv", csv_data.encode("utf-8")),
        caption=f"📁 Экспорт ({len(users)} пользователей)"
    )

@dp2.message(F.text == "🔍 Поиск пользователя")
async def search_start(message: Message):
    if not is_admin(message.from_user.id):
        return
    waiting_states[message.from_user.id] = "waiting_search"
    await message.answer("🔍 Введите ID или @username пользователя:", reply_markup=None)

@dp2.message(F.text == "🔔 Уведомления")
async def notif_menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    current = notifications.get(message.from_user.id, True)
    status = "🔔 Включены" if current else "🔕 Отключены"
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔕 Отключить уведомления" if current else "🔔 Включить уведомления")],
            [KeyboardButton(text="🔙 Назад в админ-панель")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        f"**Настройка уведомлений**\n\nТекущий статус: {status}",
        parse_mode="Markdown",
        reply_markup=kb
    )

@dp2.message(F.text == "🔔 Включить уведомления")
async def enable_notif(message: Message):
    if not is_admin(message.from_user.id):
        return
    notifications[message.from_user.id] = True
    await message.answer("✅ Уведомления включены!", reply_markup=admin_keyboard())

@dp2.message(F.text == "🔕 Отключить уведомления")
async def disable_notif(message: Message):
    if not is_admin(message.from_user.id):
        return
    notifications[message.from_user.id] = False
    await message.answer("✅ Уведомления отключены!", reply_markup=admin_keyboard())

@dp2.message(F.text == "🔙 Назад в админ-панель")
async def back_to_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    total, popular = get_stats()
    await message.answer(
        f"👑 **Админ-панель**\n\n📊 Всего пользователей: {total}\n🏆 Популярный ник: {popular[0][0] if popular else 'Нет данных'}",
        parse_mode="Markdown",
        reply_markup=admin_keyboard()
    )

@dp2.message(F.text == "❌ Закрыть админ-панель")
async def close_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    waiting_states.pop(message.from_user.id, None)
    await message.answer("👋 Админ-панель закрыта.", reply_markup=None)

# ========== ОБРАБОТКА ТЕКСТА ==========
@dp2.message(F.text)
async def text_input(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    state = waiting_states.get(user_id)

    if state == "waiting_admin_password":
        if text == ADMIN_PASSWORD:
            waiting_states.pop(user_id, None)
            total, popular = get_stats()
            await message.answer("✅ Доступ разрешен!", reply_markup=admin_keyboard())
            await message.answer(
                f"👑 **Админ-панель**\n\n📊 Всего пользователей: {total}\n🏆 Популярный ник: {popular[0][0] if popular else 'Нет данных'}",
                parse_mode="Markdown"
            )
        else:
            await message.answer("❌ Неверный пароль!")
        return

    if state == "waiting_search":
        waiting_states.pop(user_id, None)
        if not text:
            await message.answer("❌ Введите ID или username.", reply_markup=admin_keyboard())
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
                f"📛 Ник: {user['nickname']}\n"
                f"🕐 Время: {user['timestamp']}",
                parse_mode="Markdown",
                reply_markup=admin_keyboard()
            )
        else:
            await message.answer("❌ Пользователь не найден.", reply_markup=admin_keyboard())
        return

    if is_admin(user_id):
        await message.answer("Используйте кнопки меню.", reply_markup=admin_keyboard())

# ========== ВЕБХУКИ ==========
WEBHOOK_PATH1 = "/webhook/bot1"
WEBHOOK_PATH2 = "/webhook/bot2"

async def on_startup(app):
    # Инициализируем БД при старте
    init_db()
    
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
    logger.info("Webhooks deleted!")

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
