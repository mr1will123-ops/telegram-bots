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
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

# ========== НАСТРОЙКИ ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токены ботов
BOT1_TOKEN = os.getenv("BOT1_TOKEN")          # Бот для сбора данных (@ManagerTeem_bot)
BOT2_TOKEN = "8882199116:AAG1Ia9owULUQXM9zJ9lYjnyMDbcOP7D6v4"  # Бот для админ-команд в канале

LOG_CHANNEL = -1004464117954
CHANNEL_LINK = "https://t.me/managers_stack"
PORT = int(os.getenv("PORT", 8080))
RENDER = os.getenv("RENDER", "false").lower() == "true"

# ID админов (кто может писать команды в канале)
ADMIN_IDS = [
    5791631996,   # Вы
    5240956863,   # Второй админ
    7640732474,   # Третий админ
]

# ========== НИКИ (начальные) ==========
NICKNAMES = ["Dobry_p2p"]

# ========== БАЗА ДАННЫХ SQLITE ==========
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
        for nick in NICKNAMES:
            cursor.execute("INSERT OR IGNORE INTO nicknames (nickname) VALUES (?)", (nick,))
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С НИКАМИ ==========
def get_all_nicknames():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT nickname FROM nicknames ORDER BY nickname")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def add_nickname(nickname):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO nicknames (nickname) VALUES (?)", (nickname,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_nickname(nickname):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM nicknames WHERE nickname = ?", (nickname,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ==========
def save_user(user_id, username, nickname):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (user_id, username, nickname, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, username, nickname, datetime.now().strftime("%d.%m.%Y %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, nickname, timestamp FROM users ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"user_id": r[0], "username": r[1], "nickname": r[2], "timestamp": r[3]} for r in rows]

def get_stats():
    users = get_all_users()
    total = len(users)
    nicknames = [u["nickname"] for u in users]
    popular = Counter(nicknames).most_common(5)
    return total, popular

def find_user_by_id(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, nickname, timestamp FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "username": row[1], "nickname": row[2], "timestamp": row[3]}
    return None

def find_user_by_username(username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, nickname, timestamp FROM users WHERE username LIKE ?", (f"%{username}%",))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "username": row[1], "nickname": row[2], "timestamp": row[3]}
    return None

def export_csv():
    users = get_all_users()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["User ID", "Username", "Nickname", "Timestamp"])
    for u in users:
        writer.writerow([u["user_id"], u["username"], u["nickname"], u["timestamp"]])
    return output.getvalue()

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ============================================================
# ========== БОТ №1 (СБОР ДАННЫХ В ЛИЧКЕ) ==========
# ============================================================
bot1 = Bot(token=BOT1_TOKEN)
dp1 = Dispatcher()

@dp1.message(Command("start"))
async def start_bot1(message: Message):
    if message.chat.type != "private":
        return
    
    nicks = get_all_nicknames()
    if not nicks:
        await message.answer("😕 Ники закончились. Обратитесь к администратору.")
        return
    
    keyboard_buttons = []
    for nickname in nicks:
        keyboard_buttons.append([InlineKeyboardButton(text=nickname, callback_data=f"nick_{nickname}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(
        "👇 Выбери, от кого ты пришел:",
        reply_markup=keyboard
    )

@dp1.callback_query(F.data.startswith("nick_"))
async def choose_nickname(callback: CallbackQuery):
    nickname = callback.data.replace("nick_", "")
    user_id = callback.from_user.id
    username = callback.from_user.username or "без юзернейма"
    
    save_user(user_id, username, nickname)
    
    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y")
    time_str = now.strftime("%H:%M:%S")
    
    log_message = (
        f"🔔 НОВЫЙ ВЫБОР НИКА!\n\n"
        f"👤 Юзернейм: @{username}\n"
        f"🆔 ID: {user_id}\n"
        f"📛 Выбрал ник: {nickname}\n"
        f"🕐 Время: {date_str} | {time_str}"
    )
    
    # Отправляем в канал-логер
    try:
        await bot1.send_message(chat_id=LOG_CHANNEL, text=log_message)
        logger.info(f"Отправлено в канал {LOG_CHANNEL}")
    except Exception as e:
        logger.error(f"Не удалось отправить в канал: {e}")
    
    await callback.answer(f"✅ Ты выбрал ник: {nickname}")
    await callback.message.delete()
    await callback.message.answer(
        f"✅ Отлично! Ты выбрал ник: {nickname}\n\n"
        f"🔗 Переходи в канал:\n{CHANNEL_LINK}"
    )

# ============================================================
# ========== БОТ №2 (АДМИН-КОМАНДЫ В КАНАЛЕ) ==========
# ============================================================
bot2 = Bot(token=BOT2_TOKEN)
dp2 = Dispatcher()

# Список команд для помощи
HELP_TEXT = (
    "👑 **Доступные команды в канале:**\n\n"
    "📊 `/stats` — Статистика\n"
    "📁 `/export` — Скачать CSV\n"
    "🔍 `/search @username` — Поиск по username\n"
    "🔍 `/search 123456789` — Поиск по ID\n"
    "➕ `/add Ник` — Добавить ник\n"
    "➖ `/delete Ник` — Удалить ник\n"
    "📋 `/list` — Список ников\n"
    "👥 `/users` — Последние 10 пользователей\n"
    "🏆 `/top` — Топ-5 популярных ников\n"
    "❓ `/help` — Эта справка"
)

@dp2.message()
async def admin_commands(message: Message):
    """Обрабатывает команды админов в канале-логере"""
    
    # Проверяем, что это канал-логер
    if message.chat.id != LOG_CHANNEL:
        return
    
    # Проверяем, что админ
    if not is_admin(message.from_user.id):
        await message.reply("⛔ У вас нет прав для использования команд в этом канале.")
        return
    
    text = message.text.strip() if message.text else ""
    
    # Если это не команда или пусто — игнорируем
    if not text or not text.startswith("/"):
        return
    
    logger.info(f"Админ-команда в канале от {message.from_user.id}: {text}")
    
    # Разбираем команду
    parts = text.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    
    # ===== /help =====
    if command == "/help":
        await message.reply(HELP_TEXT, parse_mode="Markdown")
        return
    
    # ===== /stats =====
    if command == "/stats":
        total, popular = get_stats()
        response = f"📊 **Статистика**\n\n👥 Всего пользователей: {total}\n"
        if popular:
            response += "\n🏆 **Топ-5 ников:**\n"
            for i, (nick, count) in enumerate(popular, 1):
                emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                response += f"{emoji} {nick} — {count} чел.\n"
        await message.reply(response, parse_mode="Markdown")
        return
    
    # ===== /export =====
    if command == "/export":
        users = get_all_users()
        if not users:
            await message.reply("📭 Нет данных для экспорта.")
            return
        
        csv_data = export_csv()
        await message.reply_document(
            document=("users_export.csv", csv_data.encode("utf-8")),
            caption=f"📁 Экспорт ({len(users)} пользователей)"
        )
        return
    
    # ===== /top =====
    if command == "/top":
        total, popular = get_stats()
        if not popular:
            await message.reply("📭 Пока нет данных.")
            return
        
        response = "🏆 **Топ-5 популярных ников:**\n\n"
        for i, (nick, count) in enumerate(popular, 1):
            emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
            response += f"{emoji} {nick} — {count} чел.\n"
        
        await message.reply(response, parse_mode="Markdown")
        return
    
    # ===== /list =====
    if command == "/list":
        nicks = get_all_nicknames()
        if not nicks:
            await message.reply("📭 Ники отсутствуют.")
            return
        
        response = "📋 **Список ников:**\n\n" + "\n".join(f"• {n}" for n in nicks)
        await message.reply(response, parse_mode="Markdown")
        return
    
    # ===== /users =====
    if command == "/users":
        users = get_all_users()
        if not users:
            await message.reply("📭 Пока нет пользователей.")
            return
        
        response = "👥 **Последние 10 пользователей:**\n\n"
        for i, u in enumerate(users[:10], 1):
            response += f"{i}. @{u['username']} → {u['nickname']} ({u['timestamp']})\n"
        
        if len(users) > 10:
            response += f"\n... и еще {len(users) - 10} пользователей. Используй `/export` для полного списка."
        
        await message.reply(response, parse_mode="Markdown")
        return
    
    # ===== /search =====
    if command == "/search":
        if not args:
            await message.reply("❌ Введите: `/search @username` или `/search ID`", parse_mode="Markdown")
            return
        
        query = args.strip()
        user = None
        
        if query.isdigit():
            user = find_user_by_id(int(query))
        else:
            if query.startswith("@"):
                query = query[1:]
            user = find_user_by_username(query)
        
        if user:
            response = (
                f"👤 **Найден пользователь:**\n\n"
                f"🆔 ID: {user['user_id']}\n"
                f"👤 Username: @{user['username']}\n"
                f"📛 Ник: {user['nickname']}\n"
                f"🕐 Время: {user['timestamp']}"
            )
            await message.reply(response, parse_mode="Markdown")
        else:
            await message.reply(f"❌ Пользователь не найден.")
        return
    
    # ===== /add =====
    if command == "/add":
        if not args:
            await message.reply("❌ Введите: `/add Ник`", parse_mode="Markdown")
            return
        
        nickname = args.strip()
        if add_nickname(nickname):
            await message.reply(f"✅ Ник `{nickname}` добавлен!", parse_mode="Markdown")
        else:
            await message.reply(f"❌ Ник `{nickname}` уже существует!", parse_mode="Markdown")
        return
    
    # ===== /delete =====
    if command == "/delete":
        if not args:
            await message.reply("❌ Введите: `/delete Ник`", parse_mode="Markdown")
            return
        
        nickname = args.strip()
        if delete_nickname(nickname):
            await message.reply(f"✅ Ник `{nickname}` удалён!", parse_mode="Markdown")
        else:
            await message.reply(f"❌ Ник `{nickname}` не найден!", parse_mode="Markdown")
        return
    
    # ===== Неизвестная команда =====
    await message.reply(f"❌ Неизвестная команда. Используйте `/help` для списка команд.", parse_mode="Markdown")

# ============================================================
# ========== ВЕБХУКИ ==========
# ============================================================
WEBHOOK_PATH1 = "/webhook/bot1"
WEBHOOK_PATH2 = "/webhook/bot2"

async def on_startup(app):
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
    
    logger.info(f"Webhook bot1: {base_url}{WEBHOOK_PATH1}")
    logger.info(f"Webhook bot2: {base_url}{WEBHOOK_PATH2}")
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
