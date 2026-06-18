
# updated 2026
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

# СПИСОК АДМИНОВ (только они видят панель)
ADMIN_IDS = [
    5791631996,   # Ваш ID
    5240956863,   # Второй админ
    7640732474,   # Третий админ
]

ADMIN_PASSWORD = "3536"   # Пароль для входа в админку

LOG_CHANNEL = -1004359363247
CHANNEL_LINK = "https://t.me/managers_stack"
PORT = int(os.getenv("PORT", 8080))
RENDER = os.getenv("RENDER", "false").lower() == "true"

# ========== НИКИ ==========
NICKNAMES = ["Dobry_p2p"]

# ========== БАЗА ДАННЫХ ==========
user_data = []          # Все записи
waiting_states = {}     # Для состояний админов
notifications = {admin_id: True for admin_id in ADMIN_IDS}  # Уведомления вкл по умолчанию

# ========== ФУНКЦИИ ==========
def save_user(user_id, username, nickname):
    user_data.append({
        "user_id": user_id,
        "username": username,
        "nickname": nickname,
        "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })

def get_stats():
    total = len(user_data)
    counter = Counter(u["nickname"] for u in user_data)
    popular = counter.most_common(5)   # топ‑5
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

def random_emoji():
    return random.choice(["🌟", "🎉", "✨", "🌈", "🔥", "💫", "⭐", "🎊"])

# ========== КЛАВИАТУРА АДМИНА ==========
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

# ========== БОТ №1 (ПЕРЕХОДНИК) ==========
bot1 = Bot(token=BOT1_TOKEN)
dp1 = Dispatcher()

@dp1.message(Command("start"))
async def start_bot1(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="➡️ Перейти дальше", callback_data="go_next")]]
    )
    await message.answer(f"{random_emoji()} 👋 Привет! Нажми кнопку, чтобы выбрать ник:", reply_markup=keyboard)

@dp1.callback_query(F.data == "go_next")
async def go_next(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("🔗 Переходи в бота для выбора ника:\nhttps://t.me/ManagerTeem_bot")

# ========== БОТ №2 (ВЫБОР НИКА) ==========
bot2 = Bot(token=BOT2_TOKEN)
dp2 = Dispatcher()

@dp2.message(Command("start"))
async def start_bot2(message: Message):
    if not NICKNAMES:
        await message.answer("😕 Ники закончились. Обратитесь к администратору.")
        return
    buttons = []
    for nick in NICKNAMES:
        buttons.append([InlineKeyboardButton(text=nick, callback_data=f"nick_{nick}")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(f"{random_emoji()} 👇 Выбери, от кого ты пришел:", reply_markup=keyboard)

@dp2.callback_query(F.data.startswith("nick_"))
async def choose_nickname(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "без юзернейма"
    nickname = callback.data.replace("nick_", "")
    save_user(user_id, username, nickname)

    now = datetime.now()
    msg = (
        f"🔔 НОВЫЙ ВЫБОР НИКА!\n\n"
        f"👤 Юзернейм: @{username}\n"
        f"🆔 ID: {user_id}\n"
        f"📛 Выбрал ник: {nickname}\n"
        f"🕐 Время: {now.strftime('%d.%m.%Y')} | {now.strftime('%H:%M:%S')}"
    )

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
    await callback.message.answer(
        f"{random_emoji()} ✅ Отлично! Ты выбрал ник: {nickname}\n\n🔗 Переходи в канал:\n{CHANNEL_LINK}"
    )

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
    if not user_data:
        await message.answer("📭 Нет данных для экспорта.")
        return
    csv_data = export_csv()
    await message.answer_document(
        document=("users_export.csv", csv_data.encode("utf-8")),
        caption=f"📁 Экспорт ({len(user_data)} пользователей)"
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
            [KeyboardButton(text="🔙 Назад")]
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

@dp2.message(F.text == "🔙 Назад")
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

# ========== ОБРАБОТКА ТЕКСТОВОГО ВВОДА ==========
@dp2.message(F.text)
async def text_input(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    state = waiting_states.get(user_id)

    # Ввод пароля
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

    # Поиск
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
                f"👤 **Найден пользователь:**\n\n🆔 ID: {user['user_id']}\n👤 Username: @{user['username']}\n📛 Ник: {user['nickname']}\n🕐 Время: {user['timestamp']}",
                parse_mode="Markdown",
                reply_markup=admin_keyboard()
            )
        else:
            await message.answer("❌ Пользователь не найден.", reply_markup=admin_keyboard())
        return

    # Если админ ввел что-то непонятное
    if is_admin(user_id):
        await message.answer("Используйте кнопки меню.", reply_markup=admin_keyboard())

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
    await bot1.set_webhook(url=f"{base_url}{WEBHOOK_PATH1}")
    await bot2.set_webhook(url=f"{base_url}{WEBHOOK_PATH2}")
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
