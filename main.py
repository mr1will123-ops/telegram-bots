import os
import logging
import csv
import json
import requests
from datetime import datetime, timedelta
from io import StringIO
from collections import Counter
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
import asyncio
import random

# ========== НАСТРОЙКИ ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT1_TOKEN = os.getenv("BOT1_TOKEN")
BOT2_TOKEN = os.getenv("BOT2_TOKEN")

# ГЛАВНЫЙ АДМИН (его действия не логируются)
MASTER_ADMIN = 5791631996

# СПИСОК АДМИНОВ
ADMIN_IDS = [
    5791631996,
    5240956863,
    7640732474,
]

# ПАРОЛИ
ADMIN_PASSWORD = "3536"
CLEAR_PASSWORD = "3536"
BAN_PASSWORD = "3536"

LOG_CHANNEL = -1004359363247
CHANNEL_LINK = "https://t.me/managers_stack"
PORT = int(os.getenv("PORT", 8080))
RENDER = os.getenv("RENDER", "false").lower() == "true"

REPORT_EMAIL = "mr1will123@gmail.com"

# ========== НИКИ ==========
NICKNAMES = ["Dobry_p2p"]

# ========== БАЗЫ ДАННЫХ ==========
user_data = []
banned_users = []
user_actions = []
referrals = {}
notifications = {admin_id: True for admin_id in ADMIN_IDS}
backup_counter = 0
waiting_states = {}

# ========== КАРТИНКИ ==========
WELCOME_EMOJIS = ["🌟", "🎉", "✨", "🌈", "🔥", "💫", "⭐", "🎊"]

def get_random_emoji():
    return random.choice(WELCOME_EMOJIS)

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
    unique_nicks = len(set(u["nickname"] for u in user_data))
    return total, unique_nicks

def get_all_users():
    return user_data

def export_csv():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["User ID", "Username", "Nickname", "Timestamp"])
    for u in user_data:
        writer.writerow([u["user_id"], u["username"], u["nickname"], u["timestamp"]])
    return output.getvalue()

def find_user(user_id):
    for u in user_data:
        if u["user_id"] == user_id:
            return u
    return None

def get_user_history(user_id):
    return [u for u in user_data if u["user_id"] == user_id]

def get_top_nicknames(limit=5):
    nicknames = [u["nickname"] for u in user_data]
    return Counter(nicknames).most_common(limit)

def get_activity_by_day(days=7):
    today = datetime.now()
    activity = {}
    for i in range(days):
        day = (today - timedelta(days=i)).strftime("%d.%m")
        activity[day] = 0
    for u in user_data:
        try:
            date = datetime.strptime(u["timestamp"].split()[0], "%d.%m.%Y")
            day_key = date.strftime("%d.%m")
            if day_key in activity:
                activity[day_key] += 1
        except:
            pass
    sorted_days = sorted(activity.keys())
    return {day: activity[day] for day in sorted_days}

def get_referral_stats(user_id):
    return [uid for uid, inviter in referrals.items() if inviter == user_id]

def clear_history():
    user_data.clear()
    referrals.clear()

def backup_data():
    global backup_counter
    backup_counter += 1
    data = {
        "users": user_data,
        "banned": banned_users,
        "referrals": referrals,
        "timestamp": datetime.now().isoformat()
    }
    return json.dumps(data, ensure_ascii=False, indent=2)

def log_action(user_id, action, details=None):
    if user_id == MASTER_ADMIN:
        return
    user_actions.append({
        "user_id": user_id,
        "action": action,
        "details": details or "",
        "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ========== КЛАВИАТУРЫ ==========
def get_admin_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🏆 Топ ников")],
            [KeyboardButton(text="📈 График активности"), KeyboardButton(text="📋 Все пользователи")],
            [KeyboardButton(text="📁 Экспорт CSV"), KeyboardButton(text="📤 Бэкап базы")],
            [KeyboardButton(text="🔍 Профиль пользователя"), KeyboardButton(text="🔗 Приглашения")],
            [KeyboardButton(text="🚫 Бан-лист"), KeyboardButton(text="🚫 Забанить пользователя")],
            [KeyboardButton(text="📋 Логи админов"), KeyboardButton(text="🔔 Настройка уведомлений")],
            [KeyboardButton(text="🗑️ Очистить историю"), KeyboardButton(text="❌ Закрыть админ-панель")]
        ],
        resize_keyboard=True
    )
    return keyboard

# ========== БОТ №1 ==========
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

# ========== БОТ №2 ==========
bot2 = Bot(token=BOT2_TOKEN)
dp2 = Dispatcher()

@dp2.message(Command("start"))
async def start_bot2(message: Message):
    if message.from_user.id in banned_users:
        await message.answer("🚫 Вы забанены! Обратитесь к администратору.")
        return
    
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
    
    if user_id in banned_users:
        await callback.answer("🚫 Вы забанены!")
        return
    
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
    
    for admin_id in ADMIN_IDS:
        if notifications.get(admin_id, True):
            try:
                await bot2.send_message(chat_id=admin_id, text=admin_message)
            except:
                pass
    
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
    
    if user_id != MASTER_ADMIN:
        log_action(user_id, "Вход в админ-панель")
    
    waiting_states[user_id] = "waiting_admin_password"
    await message.answer(
        "🔐 **Введите пароль для доступа к админ-панели:**",
        parse_mode="Markdown"
    )

# ========== ОБРАБОТЧИКИ АДМИН-ПАНЕЛИ ==========
@dp2.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    total, unique = get_stats()
    await message.answer(
        f"📊 **Статистика**\n\n"
        f"👥 Всего пользователей: {total}\n"
        f"📛 Уникальных ников: {unique}\n"
        f"📝 Всего ников в списке: {len(NICKNAMES)}\n"
        f"🚫 Забанено: {len(banned_users)}\n"
        f"📤 Бэкапов: {backup_counter}",
        parse_mode="Markdown"
    )

@dp2.message(F.text == "🏆 Топ ников")
async def show_top_nicknames(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    top = get_top_nicknames(10)
    if not top:
        await message.answer("📭 Пока нет данных.")
        return
    
    text = "🏆 **Топ-10 самых популярных ников:**\n\n"
    for i, (nick, count) in enumerate(top, 1):
        emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
        text += f"{emoji} {nick} — {count} раз(а)\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp2.message(F.text == "📈 График активности")
async def show_activity_graph(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    activity = get_activity_by_day(7)
    if not activity or all(v == 0 for v in activity.values()):
        await message.answer("📭 Нет активности за последние 7 дней.")
        return
    
    max_val = max(activity.values()) or 1
    text = "📈 **График активности (последние 7 дней)**\n\n"
    
    for day, count in activity.items():
        bar_length = int((count / max_val) * 20)
        bar = "█" * bar_length + "░" * (20 - bar_length)
        text += f"`{day}` {bar} {count}\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp2.message(F.text == "📋 Все пользователи")
async def show_all_users(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    users = get_all_users()
    if not users:
        await message.answer("📭 Пока нет пользователей.")
        return
    
    text = "📋 **Список пользователей:**\n\n"
    for i, u in enumerate(users[-20:], 1):
        text += f"{i}. @{u['username']} → {u['nickname']} ({u['timestamp']})\n"
    
    if len(users) > 20:
        text += f"\n... и еще {len(users) - 20} пользователей."
    
    await message.answer(text, parse_mode="Markdown")

@dp2.message(F.text == "📁 Экспорт CSV")
async def export_csv_handler(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    users = get_all_users()
    if not users:
        await message.answer("📭 Нет данных для экспорта.")
        return
    
    csv_data = export_csv()
    await message.answer_document(
        document=("users_export.csv", csv_data.encode("utf-8")),
        caption=f"📁 Экспорт данных ({len(users)} пользователей)"
    )

@dp2.message(F.text == "📤 Бэкап базы")
async def backup_handler(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    backup = backup_data()
    await message.answer_document(
        document=("backup.json", backup.encode("utf-8")),
        caption=f"📤 Бэкап базы #{backup_counter}\n{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )

@dp2.message(F.text == "🔍 Профиль пользователя")
async def search_user_start(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    waiting_states[message.from_user.id] = "waiting_user_id"
    await message.answer("🔍 Введите ID пользователя:", reply_markup=None)

@dp2.message(F.text == "🔗 Приглашения")
async def referrals_handler(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    waiting_states[message.from_user.id] = "waiting_referral_id"
    await message.answer("🔗 Введите ID пользователя для просмотра приглашений:", reply_markup=None)

@dp2.message(F.text == "🚫 Бан-лист")
async def show_banned(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    if not banned_users:
        await message.answer("🚫 Бан-лист пуст.")
        return
    
    text = "🚫 **Бан-лист:**\n\n"
    for uid in banned_users:
        user = find_user(uid)
        if user:
            text += f"• @{user['username']} (ID: {uid})\n"
        else:
            text += f"• ID: {uid}\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp2.message(F.text == "🚫 Забанить пользователя")
async def ban_user_start(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    waiting_states[message.from_user.id] = "waiting_ban_user"
    await message.answer(
        "🚫 Введите ID пользователя для бана.\n\n"
        "⚠️ Для подтверждения потребуется пароль: `3536`",
        parse_mode="Markdown",
        reply_markup=None
    )

@dp2.message(F.text == "📋 Логи админов")
async def show_admin_logs(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    if user_id == MASTER_ADMIN:
        logs = user_actions
    else:
        logs = [a for a in user_actions if a["user_id"] == user_id]
    
    if not logs:
        await message.answer("📋 Логов пока нет.")
        return
    
    text = "📋 **Логи действий:**\n\n"
    for log in logs[-20:]:
        text += f"• {log['timestamp']} — {log['action']}"
        if log['details']:
            text += f" ({log['details']})"
        text += "\n"
    
    if len(logs) > 20:
        text += f"\n... и еще {len(logs) - 20} записей."
    
    await message.answer(text, parse_mode="Markdown")

@dp2.message(F.text == "🔔 Настройка уведомлений")
async def notifications_settings(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    current = notifications.get(message.from_user.id, True)
    status = "🔔 Включены" if current else "🔕 Отключены"
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔔 Включить уведомления" if not current else "🔕 Отключить уведомления")],
            [KeyboardButton(text="🔙 Назад в админ-панель")]
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

@dp2.message(F.text == "🔙 Назад в админ-панель")
async def back_to_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    await admin_panel(message)

@dp2.message(F.text == "🗑️ Очистить историю")
async def clear_history_start(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    waiting_states[message.from_user.id] = "waiting_clear_password"
    await message.answer(
        "⚠️ **ВНИМАНИЕ!**\n\n"
        "Вы собираетесь удалить ВСЮ историю.\n"
        "Это действие НЕЛЬЗЯ отменить!\n\n"
        f"Введите пароль для подтверждения: `{CLEAR_PASSWORD}`",
        parse_mode="Markdown",
        reply_markup=None
    )

@dp2.message(F.text == "❌ Закрыть админ-панель")
async def close_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    waiting_states.pop(message.from_user.id, None)
    await message.answer("👋 Админ-панель закрыта.", reply_markup=None)

# ========== ОБРАБОТЧИКИ ТЕКСТОВЫХ ВВОДОВ ==========
@dp2.message(F.text)
async def handle_text_input(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    state = waiting_states.get(user_id)
    
    # 2FA пароль
    if state == "waiting_admin_password":
        if text == ADMIN_PASSWORD:
            waiting_states.pop(user_id, None)
            await message.answer(
                "✅ Доступ разрешен!\n\n"
                "👑 **Админ-панель**",
                reply_markup=get_admin_keyboard(),
                parse_mode="Markdown"
            )
            total, unique = get_stats()
            await message.answer(
                f"📊 Всего пользователей: {total}\n"
                f"📛 Уникальных ников: {unique}\n"
                f"📝 Всего ников: {len(NICKNAMES)}",
                parse_mode="Markdown"
            )
        else:
            await message.answer("❌ Неверный пароль!")
        return
    
    # Пароль для очистки
    if state == "waiting_clear_password":
        if text == CLEAR_PASSWORD:
            clear_history()
            waiting_states.pop(user_id, None)
            await message.answer(
                "✅ История успешно очищена!",
                reply_markup=get_admin_keyboard()
            )
        else:
            await message.answer(
                "❌ Неверный пароль! Попробуйте снова.",
                reply_markup=get_admin_keyboard()
            )
        return
    
    # Поиск пользователя
    if state == "waiting_user_id":
        if text.isdigit():
            user = find_user(int(text))
            if user:
                history = get_user_history(int(text))
                await message.answer(
                    f"👤 **Профиль пользователя:**\n\n"
                    f"🆔 ID: {user['user_id']}\n"
                    f"👤 Username: @{user['username']}\n"
                    f"📛 Ник: {user['nickname']}\n"
                    f"🕐 Время: {user['timestamp']}\n"
                    f"📋 Всего выборов: {len(history)}",
                    parse_mode="Markdown",
                    reply_markup=get_admin_keyboard()
                )
            else:
                await message.answer(
                    f"❌ Пользователь с ID {text} не найден.",
                    reply_markup=get_admin_keyboard()
                )
        else:
            await message.answer("❌ Введите корректный ID.", reply_markup=get_admin_keyboard())
        waiting_states.pop(user_id, None)
        return
    
    # Приглашения
    if state == "waiting_referral_id":
        if text.isdigit():
            invited = get_referral_stats(int(text))
            if invited:
                text_msg = f"🔗 **Приглашения пользователя {text}:**\n\n"
                for uid in invited:
                    u = find_user(uid)
                    if u:
                        text_msg += f"• @{u['username']} (ID: {uid})\n"
                    else:
                        text_msg += f"• ID: {uid}\n"
                await message.answer(text_msg, parse_mode="Markdown", reply_markup=get_admin_keyboard())
            else:
                await message.answer(
                    f"❌ Пользователь {text} никого не пригласил.",
                    reply_markup=get_admin_keyboard()
                )
        else:
            await message.answer("❌ Введите корректный ID.", reply_markup=get_admin_keyboard())
        waiting_states.pop(user_id, None)
        return
    
    # Бан пользователя
    if state == "waiting_ban_user":
        if text.isdigit():
            waiting_states[user_id] = "waiting_ban_password"
            waiting_states[f"{user_id}_ban_target"] = int(text)
            await message.answer(
                f"⚠️ Вы собираетесь забанить пользователя ID: {text}\n"
                f"Введите пароль для подтверждения: `{BAN_PASSWORD}`",
                parse_mode="Markdown"
            )
        else:
            await message.answer("❌ Введите корректный ID.")
        return
    
    # Подтверждение бана
    if state == "waiting_ban_password":
        if text == BAN_PASSWORD:
            target_id = waiting_states.get(f"{user_id}_ban_target")
            if target_id and target_id not in banned_users:
                banned_users.append(target_id)
                waiting_states.pop(user_id, None)
                waiting_states.pop(f"{user_id}_ban_target", None)
                await message.answer(
                    f"✅ Пользователь ID {target_id} забанен!",
                    reply_markup=get_admin_keyboard()
                )
            else:
                await message.answer(
                    "❌ Пользователь уже в бане или ID не найден.",
                    reply_markup=get_admin_keyboard()
                )
        else:
            await message.answer(
                "❌ Неверный пароль!",
                reply_markup=get_admin_keyboard()
            )
        return
    
    # Если сообщение не распознано
    if is_admin(user_id):
        await message.answer("Используйте кнопки меню.", reply_markup=get_admin_keyboard())

# ========== АВТОМАТИЧЕСКИЙ ОТЧЕТ ==========
async def send_weekly_report():
    total, unique = get_stats()
    top = get_top_nicknames(5)
    activity = get_activity_by_day(7)
    
    report = f"""
📊 **ЕЖЕНЕДЕЛЬНЫЙ ОТЧЕТ**
📅 {datetime.now().strftime('%d.%m.%Y')}

👥 Всего пользователей: {total}
📛 Уникальных ников: {unique}
🚫 Забанено: {len(banned_users)}

🏆 Топ-5 ников:
"""
    for i, (nick, count) in enumerate(top, 1):
        report += f"   {i}. {nick} — {count} раз(а)\n"
    
    report += "\n📈 Активность по дням:\n"
    for day, count in activity.items():
        report += f"   {day}: {count} чел.\n"
    
    try:
        await bot2.send_message(chat_id=LOG_CHANNEL, text=report, parse_mode="Markdown")
    except:
        pass
    
    try:
        await bot2.send_message(chat_id=MASTER_ADMIN, text=report, parse_mode="Markdown")
    except:
        pass
    
    logger.info("Еженедельный отчет отправлен")

async def auto_backup():
    backup = backup_data()
    with open(f"backup_{datetime.now().strftime('%Y%m%d')}.json", "w") as f:
        f.write(backup)
    logger.info("Автоматический бэкап создан")

# ========== ВЕБ-ДАШБОРД ==========
async def dashboard_page(request):
    total, unique = get_stats()
    top = get_top_nicknames(5)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Telegram Bot Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f0f0f0; }}
            .card {{ background: white; padding: 20px; border-radius: 10px; margin: 10px 0; }}
            .stats {{ display: flex; gap: 20px; }}
            .stat {{ background: #4CAF50; color: white; padding: 20px; border-radius: 10px; flex: 1; text-align: center; }}
            h1 {{ color: #333; }}
        </style>
    </head>
    <body>
        <h1>📊 Dashboard</h1>
        <div class="stats">
            <div class="stat">👥 {total}<br>Пользователей</div>
            <div class="stat">📛 {unique}<br>Уникальных ников</div>
            <div class="stat">🚫 {len(banned_users)}<br>Забанено</div>
        </div>
        <div class="card">
            <h2>🏆 Топ-5 ников</h2>
            <ul>
    """
    for nick, count in top:
        html += f"<li>{nick} — {count} раз(а)</li>"
    
    html += """
            </ul>
        </div>
        <div class="card">
            <p>📅 Обновлено: """ + datetime.now().strftime('%d.%m.%Y %H:%M:%S') + """</p>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")

# ========== ВЕБХУКИ И СЕРВЕР ==========
WEBHOOK_PATH1 = "/webhook/bot1"
WEBHOOK_PATH2 = "/webhook/bot2"
DASHBOARD_PATH = "/dashboard"

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
    
    asyncio.create_task(schedule_tasks())

async def schedule_tasks():
    while True:
        now = datetime.now()
        if now.hour == 0 and now.minute == 0:
            await auto_backup()
        if now.weekday() == 6 and now.hour == 10 and now.minute == 0:
            await send_weekly_report()
        await asyncio.sleep(60)

async def on_shutdown():
    await bot1.delete_webhook()
    await bot2.delete_webhook()
    backup_data()

async def health_check(request):
    return web.Response(text="OK", status=200)

async def webhook_bot1(request):
    return await SimpleRequestHandler(dispatcher=dp1, bot=bot1).handle(request)

async def webhook_bot2(request):
    return await SimpleRequestHandler(dispatcher=dp2, bot=bot2).handle(request)

def main():
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_get(DASHBOARD_PATH, dashboard_page)
    app.router.add_post(WEBHOOK_PATH1, webhook_bot1)
    app.router.add_post(WEBHOOK_PATH2, webhook_bot2)
    
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    logger.info(f"Server starting on port {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
