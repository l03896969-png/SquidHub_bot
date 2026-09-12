# -*- coding: utf-8 -*-
import logging
import re
import requests
import random
import string
import socket
import phonenumbers
from datetime import datetime
from phonenumbers import carrier, geocoder, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

TELEGRAM_TOKEN = "8476291431:AAElHgmZT92_GIBIchbnQ3AxCxu98HEQjx4"
OWNER_ID = 1100862483
OWNER_USERNAME = "zxcelite"

PROTECTED = ["zxcelite", "1100862483", "@zxcelite"]

USERS = {}
USERNAMES = {}
BLOCKED = {}
PENDING = {}
PROMOCODES = {}
GLOBAL_BLOCK = False
FORWARD_MESSAGES = True
STATS = {"queries": 0}
BROADCAST_MODE = {}
BROADCAST_TARGET = {}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

GREETINGS = [
    "🛸 SquidHub на связи\n\nВыбери, что хочешь проверить:",
    "⚡ Система активна\n\nЧто будем пробивать сегодня?",
    "🔮 Готов к работе\n\nВыбери инструмент:",
    "🎯 SquidHub Bot\n\nКуда направим запрос?",
    "🧠 Все инструменты под рукой\n\nВыбирай:",
]

DENY_MESSAGES = [
    "⛔ Доступ заблокирован администратором",
    "🚫 Админ приостановил твой доступ",
    "🔒 Бот закрыт для тебя. Обратись к владельцу",
]

GLOBAL_DENY = [
    "⛔ Бот временно выключен администратором\n\nЗаходи позже",
    "🔒 Технический перерыв\n\nАдмин скоро вернёт доступ",
    "⚠️ SquidHub остановлен\n\nОжидай включения",
]

WAIT_MESSAGES = [
    "📨 Заявка улетела админу\n\nЖди вердикта",
    "⏳ Запрос отправлен\n\nАдмин скоро ответит",
    "✉️ Заявка на рассмотрении\n\nНе спамь, жди",
]

def rnd_greet():
    return random.choice(GREETINGS)

def rnd_deny():
    return random.choice(DENY_MESSAGES)

def rnd_gdeny():
    return random.choice(GLOBAL_DENY)

def rnd_wait():
    return random.choice(WAIT_MESSAGES)

def now_str():
    return datetime.now().strftime("%d.%m.%Y %H:%M")

def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def is_owner(user_id):
    return user_id == OWNER_ID

def is_blocked(user_id):
    return user_id in BLOCKED

def is_allowed(user_id):
    u = USERS.get(user_id)
    return bool(u and u.get("approved"))

def register_user(user_id, username, first_name=""):
    if user_id not in USERS:
        USERS[user_id] = {
            "id": user_id,
            "username": username or "",
            "first_name": first_name or "",
            "registered": now_str(),
            "xp": 0,
            "level": 1,
            "balance": 0,
            "daily_claimed": "",
            "referrals": [],
            "queries": 0,
            "approved": False,
        }
    else:
        if username:
            USERS[user_id]["username"] = username
        if first_name:
            USERS[user_id]["first_name"] = first_name
    if username:
        USERNAMES[username.lower()] = user_id

def add_xp(user_id, amount):
    u = USERS.get(user_id)
    if not u:
        return
    u["xp"] += amount
    while u["xp"] >= u["level"] * 100:
        u["xp"] -= u["level"] * 100
        u["level"] += 1

def set_level(user_id, level):
    u = USERS.get(user_id)
    if not u:
        return
    u["level"] = level

def level_progress(user_id):
    u = USERS.get(user_id)
    if not u:
        return 0, 100
    return u["xp"], u["level"] * 100

def contains_protected(text):
    low = text.lower()
    for p in PROTECTED:
        if p.lower() in low:
            return True
    return False

def get_phone_info(phone):
    try:
        parsed = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed):
            return {"error": "Неверный номер телефона"}
        country = geocoder.description_for_number(parsed, "ru")
        operator = carrier.name_for_number(parsed, "ru")
        tz = timezone.time_zones_for_number(parsed)
        return {
            "phone": phone,
            "country": country or "Неизвестно",
            "operator": operator or "Неизвестно",
            "timezone": ", ".join(tz) if tz else "Неизвестно",
            "valid": True,
        }
    except Exception as e:
        return {"error": str(e)}

def get_telegram_info(username):
    try:
        resp = requests.get("https://t.me/" + username, timeout=5)
        if resp.status_code == 200:
            title = re.search(r"<title>(.*?)</title>", resp.text)
            title_text = title.group(1) if title else "Неизвестно"
            return {"username": username, "exists": True, "title": title_text, "url": "https://t.me/" + username}
        return {"username": username, "exists": False}
    except Exception:
        return {"error": "Не удалось проверить"}

def get_domain_info(domain):
    try:
        ip = socket.gethostbyname(domain)
        return {"domain": domain, "ip": ip, "resolved": True}
    except Exception as e:
        return {"error": "Домен не резолвится: " + str(e)}

def generate_password(length=16):
    chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}"
    return "".join(random.choice(chars) for _ in range(length))

NICK_ADJ = ["Silent", "Dark", "Frost", "Crimson", "Shadow", "Iron", "Neon", "Wild",
            "Swift", "Golden", "Hollow", "Lucid", "Vivid", "Ancient", "Calm", "Mystic"]
NICK_NOUN = ["River", "Storm", "Wolf", "Hawk", "Ember", "Vale", "Echo", "Flame",
             "Knight", "Moon", "Ocean", "Sage", "Thorn", "Wave", "Rain", "Pine"]
NICK_SUF = ["", "x", "z", "ex", "ix", "on", "er"]

def generate_nickname():
    return random.choice(NICK_ADJ) + random.choice(NICK_NOUN) + random.choice(NICK_SUF)

def back_main():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")]])

def back_admin():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ В админ-панель", callback_data="admin_panel")]])

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Проверить номер", callback_data="menu_phone")],
        [InlineKeyboardButton("👤 Проверить юзернейм", callback_data="menu_username")],
        [InlineKeyboardButton("🔍 Whois домена", callback_data="menu_domain")],
        [InlineKeyboardButton("🎲 Инструменты", callback_data="menu_tools")],
        [InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")],
    ])

def tools_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Генератор пароля", callback_data="tool_password")],
        [InlineKeyboardButton("🎭 Генератор ника", callback_data="tool_nickname")],
        [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")],
    ])

def profile_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Ежедневный бонус", callback_data="daily_bonus")],
        [InlineKeyboardButton("👥 Рефералы", callback_data="my_referrals")],
        [InlineKeyboardButton("🎟 Активировать промокод", callback_data="enter_promo")],
        [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")],
    ])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Пользователи", callback_data="adm_users")],
        [InlineKeyboardButton("📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton("📨 Рассылка", callback_data="adm_broadcast")],
        [InlineKeyboardButton("🚫 Блокировки", callback_data="adm_blocks")],
        [InlineKeyboardButton("🎟 Промокоды", callback_data="adm_promos")],
        [InlineKeyboardButton("💰 Экономика", callback_data="adm_economy")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="adm_settings")],
        [InlineKeyboardButton("📋 Заявки", callback_data="adm_pending")],
        [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")],
    ])

def broadcast_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Всем", callback_data="bc_all")],
        [InlineKeyboardButton("👤 Одному", callback_data="bc_one")],
        [InlineKeyboardButton("⬅️ В админ-панель", callback_data="admin_panel")],
    ])

def admin_settings_menu():
    gs = "🔴 ВЫКЛ" if GLOBAL_BLOCK else "🟢 ВКЛ"
    fs = "🔔 ВКЛ" if FORWARD_MESSAGES else "🔕 ВЫКЛ"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Глобальный доступ: " + gs, callback_data="global_toggle")],
        [InlineKeyboardButton("🔔 Уведомления: " + fs, callback_data="forward_toggle")],
        [InlineKeyboardButton("⬅️ В админ-панель", callback_data="admin_panel")],
    ])

def approval_buttons(user_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Одобрить", callback_data="approve_" + str(user_id)),
        InlineKeyboardButton("❌ Отклонить", callback_data="deny_" + str(user_id)),
    ]])

def user_manage_buttons(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Заблокировать", callback_data="block_" + str(user_id))],
        [InlineKeyboardButton("✅ Разблокировать", callback_data="unblock_" + str(user_id))],
        [InlineKeyboardButton("💰 Изменить баланс", callback_data="edit_balance_" + str(user_id))],
        [InlineKeyboardButton("⭐ Выдать XP", callback_data="give_xp_" + str(user_id))],
        [InlineKeyboardButton("🏆 Выдать уровень", callback_data="give_lvl_" + str(user_id))],
        [InlineKeyboardButton("📩 Написать", callback_data="dm_" + str(user_id))],
        [InlineKeyboardButton("⬅️ К списку", callback_data="adm_users")],
    ])

# ═══ /start ═══
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or ""
    first_name = user.first_name or ""
    register_user(user_id, username, first_name)

    if context.args and context.args[0].startswith("ref"):
        try:
            ref_id = int(context.args[0][3:])
            if ref_id != user_id and ref_id in USERS:
                if user_id not in USERS[ref_id]["referrals"]:
                    USERS[ref_id]["referrals"].append(user_id)
        except Exception:
            pass

    if is_owner(user_id):
        await update.message.reply_text("👑 ADMIN PANEL\n\nДобро пожаловать, владелец.\nВыбери раздел:", reply_markup=admin_menu())
        return

    if GLOBAL_BLOCK:
        await update.message.reply_text(rnd_gdeny())
        return

    if is_blocked(user_id):
        await update.message.reply_text(rnd_deny())
        return

    if is_allowed(user_id):
        await update.message.reply_text(rnd_greet(), reply_markup=main_menu())
        return

    if user_id in PENDING:
        await update.message.reply_text("⏳ Заявка уже на рассмотрении\n\nНе спамь.")
        return

    PENDING[user_id] = {"username": username, "time": now_str()}
    await update.message.reply_text(rnd_wait())
    await context.bot.send_message(
        chat_id=OWNER_ID,
        text="🔔 Новая заявка\n\n👤 @" + (username or "без_юзернейма") + "\n🆔 " + str(user_id) + "\n📅 " + now_str(),
        reply_markup=approval_buttons(user_id),
    )

# ═══ КНОПКИ ═══
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GLOBAL_BLOCK, FORWARD_MESSAGES
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    is_adm = is_owner(user_id)

    if data.startswith("approve_") or data.startswith("deny_"):
        if not is_adm:
            return
        action, target_str = data.split("_", 1)
        target_id = int(target_str)
        if target_id not in PENDING:
            await query.edit_message_text("❌ Заявка не найдена.")
            return
        if action == "approve":
            u = USERS.get(target_id)
            if u:
                u["approved"] = True
            PENDING.pop(target_id, None)
            await query.edit_message_text("✅ Заявка одобрена.")
            try:
                await context.bot.send_message(chat_id=target_id, text="✅ Доступ одобрен\n\nОтправь /start.")
            except Exception:
                pass
        else:
            PENDING.pop(target_id, None)
            await query.edit_message_text("❌ Заявка отклонена.")
            try:
                await context.bot.send_message(chat_id=target_id, text="❌ Заявка отклонена.")
            except Exception:
                pass
        return

    if data == "admin_panel":
        if not is_adm:
            return
        await query.edit_message_text("👑 ADMIN PANEL\n\nВыбери раздел:", reply_markup=admin_menu())
        return

    if data == "adm_users":
        if not is_adm:
            return
        if not USERS:
            await query.edit_message_text("📋 Пользователей нет.", reply_markup=admin_menu())
            return
        text = "👥 Пользователи (" + str(len(USERS)) + "):\n\n"
        keyboard = []
        for uid, u in list(USERS.items())[:30]:
            status = "🚫" if is_blocked(uid) else ("✅" if u.get("approved") else "⏳")
            text += status + " @" + (u.get("username") or str(uid)) + " | lvl " + str(u.get("level", 1)) + "\n"
            keyboard.append([InlineKeyboardButton(status + " @" + (u.get("username") or str(uid)), callback_data="user_" + str(uid))])
        keyboard.append([InlineKeyboardButton("⬅️ В админ-панель", callback_data="admin_panel")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("user_"):
        if not is_adm:
            return
        uid = int(data.split("_", 1)[1])
        u = USERS.get(uid)
        if not u:
            await query.edit_message_text("❌ Не найден.", reply_markup=admin_menu())
            return
        xp, need = level_progress(uid)
        status = "🚫 Заблокирован" if is_blocked(uid) else ("✅ Активен" if u.get("approved") else "⏳ Ожидает")
        text = (
            "👤 Пользователь\n\n"
            "🆔 ID: " + str(uid) + "\n"
            "📛 Username: @" + (u.get("username") or "—") + "\n"
            "👋 Имя: " + (u.get("first_name") or "—") + "\n"
            "📅 Регистрация: " + u.get("registered", "—") + "\n"
            "📊 XP: " + str(xp) + " / " + str(need) + "\n"
            "🏆 Уровень: " + str(u.get("level", 1)) + "\n"
            "💰 Баланс: " + str(u.get("balance", 0)) + "\n"
            "🔍 Запросов: " + str(u.get("queries", 0)) + "\n"
            "👥 Рефералов: " + str(len(u.get("referrals", []))) + "\n"
            "🚦 Статус: " + status
        )
        await query.edit_message_text(text, reply_markup=user_manage_buttons(uid))
        return

    if data.startswith("block_"):
        if not is_adm:
            return
        uid = int(data.split("_", 1)[1])
        BLOCKED[uid] = True
        await query.edit_message_text("🚫 Заблокирован.", reply_markup=admin_menu())
        try:
            await context.bot.send_message(chat_id=uid, text=rnd_deny())
        except Exception:
            pass
        return

    if data.startswith("unblock_"):
        if not is_adm:
            return
        uid = int(data.split("_", 1)[1])
        BLOCKED.pop(uid, None)
        await query.edit_message_text("✅ Разблокирован.", reply_markup=admin_menu())
        try:
            await context.bot.send_message(chat_id=uid, text="✅ Доступ восстановлен. /start")
        except Exception:
            pass
        return

    if data.startswith("edit_balance_"):
        if not is_adm:
            return
        uid = int(data.split("_", 2)[2])
        context.user_data["edit_balance"] = uid
        await query.edit_message_text("💰 Отправь новое значение баланса числом:", reply_markup=back_admin())
        return

    if data.startswith("give_xp_"):
        if not is_adm:
            return
        uid = int(data.split("_", 2)[2])
        context.user_data["give_xp"] = uid
        await query.edit_message_text("⭐ Отправь количество XP для выдачи:", reply_markup=back_admin())
        return

    if data.startswith("give_lvl_"):
        if not is_adm:
            return
        uid = int(data.split("_", 2)[2])
        context.user_data["give_lvl"] = uid
        await query.edit_message_text("🏆 Отправь номер уровня:", reply_markup=back_admin())
        return

    if data.startswith("dm_"):
        if not is_adm:
            return
        uid = int(data.split("_", 1)[1])
        context.user_data["dm_target"] = uid
        await query.edit_message_text("📩 Отправь сообщение для пользователя:", reply_markup=back_admin())
        return

    if data == "adm_stats":
        if not is_adm:
            return
        text = (
            "📊 Статистика\n\n"
            "👥 Всего: " + str(len(USERS)) + "\n"
            "✅ Активных: " + str(sum(1 for u in USERS.values() if u.get("approved"))) + "\n"
            "🚫 Заблокированных: " + str(len(BLOCKED)) + "\n"
            "⏳ Заявок: " + str(len(PENDING)) + "\n"
            "🔍 Запросов: " + str(STATS["queries"]) + "\n"
            "🎟 Промокодов: " + str(len(PROMOCODES))
        )
        await query.edit_message_text(text, reply_markup=admin_menu())
        return

    if data == "adm_broadcast":
        if not is_adm:
            return
        await query.edit_message_text("📨 Рассылка:", reply_markup=broadcast_menu())
        return

    if data == "bc_all":
        if not is_adm:
            return
        BROADCAST_MODE[user_id] = True
        await query.edit_message_text("📢 Отправь текст для рассылки ВСЕМ:", reply_markup=back_admin())
        return

    if data == "bc_one":
        if not is_adm:
            return
        BROADCAST_TARGET[user_id] = True
        await query.edit_message_text("👤 Отправь ID или @username получателя:", reply_markup=back_admin())
        return

    if data == "adm_blocks":
        if not is_adm:
            return
        if not BLOCKED:
            await query.edit_message_text("🚫 Заблокированных нет.", reply_markup=admin_menu())
            return
        text = "🚫 Заблокированные:\n\n"
        keyboard = []
        for uid in BLOCKED.keys():
            u = USERS.get(uid, {})
            text += "• @" + (u.get("username") or str(uid)) + "\n"
            keyboard.append([InlineKeyboardButton("✅ @" + (u.get("username") or str(uid)), callback_data="unblock_" + str(uid))])
        keyboard.append([InlineKeyboardButton("⬅️ В админ-панель", callback_data="admin_panel")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "adm_promos":
        if not is_adm:
            return
        text = "🎟 Промокоды:\n\n"
        if PROMOCODES:
            for code, info in PROMOCODES.items():
                text += "• " + code + " — " + str(info["amount"]) + " (осталось " + str(info["uses"]) + ")\n"
        else:
            text += "Пусто."
        keyboard = [
            [InlineKeyboardButton("➕ Создать", callback_data="create_promo")],
            [InlineKeyboardButton("⬅️ В админ-панель", callback_data="admin_panel")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "create_promo":
        if not is_adm:
            return
        context.user_data["create_promo"] = True
        await query.edit_message_text("🎟 Формат: код сумма количество\nПример: SALE 100 10", reply_markup=back_admin())
        return

    if data == "adm_economy":
        if not is_adm:
            return
        total = sum(u.get("balance", 0) for u in USERS.values())
        text = "💰 Экономика\n\n💵 Общий баланс: " + str(total) + "\n👥 Кошельков: " + str(len(USERS))
        await query.edit_message_text(text, reply_markup=admin_menu())
        return

    if data == "adm_settings":
        if not is_adm:
            return
        await query.edit_message_text("⚙️ Настройки:", reply_markup=admin_settings_menu())
        return

    if data == "global_toggle":
        if not is_adm:
            return
        GLOBAL_BLOCK = not GLOBAL_BLOCK
        await query.edit_message_text("Настройки:", reply_markup=admin_settings_menu())
        return

    if data == "forward_toggle":
        if not is_adm:
            return
        FORWARD_MESSAGES = not FORWARD_MESSAGES
        await query.edit_message_text("Настройки:", reply_markup=admin_settings_menu())
        return

    if data == "adm_pending":
        if not is_adm:
            return
        if not PENDING:
            await query.edit_message_text("📋 Заявок нет.", reply_markup=admin_menu())
            return
        text = "📋 Заявки:\n\n"
        keyboard = []
        for uid, info in PENDING.items():
            text += "• @" + (info.get("username") or str(uid)) + "\n"
            keyboard.append([InlineKeyboardButton("✅ @" + (info.get("username") or str(uid)), callback_data="approve_" + str(uid))])
        keyboard.append([InlineKeyboardButton("⬅️ В админ-панель", callback_data="admin_panel")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "menu_phone":
        await query.edit_message_text("📞 Проверка номера\n\nОтправь: +380XXXXXXXXX", reply_markup=back_main())
    elif data == "menu_username":
        await query.edit_message_text("👤 Проверка юзернейма\n\nОтправь: @username", reply_markup=back_main())
    elif data == "menu_domain":
        await query.edit_message_text("🔍 Whois домена\n\nОтправь: google.com", reply_markup=back_main())
    elif data == "menu_tools":
        await query.edit_message_text("🎲 Инструменты:", reply_markup=tools_menu())
    elif data == "menu_profile":
        if not is_allowed(user_id) and not is_adm:
            await query.edit_message_text("⛔ Нет доступа.", reply_markup=back_main())
            return
        u = USERS.get(user_id, {})
        xp, need = level_progress(user_id)
        text = (
            "👤 Профиль\n\n"
            "🆔 ID: " + str(user_id) + "\n"
            "📛 @" + (u.get("username") or "—") + "\n"
            "📅 " + u.get("registered", "—") + "\n"
            "📊 XP: " + str(xp) + " / " + str(need) + "\n"
            "🏆 Уровень: " + str(u.get("level", 1)) + "\n"
            "💰 Баланс: " + str(u.get("balance", 0)) + "\n"
            "👥 Рефералов: " + str(len(u.get("referrals", [])))
        )
        await query.edit_message_text(text, reply_markup=profile_menu())
    elif data == "tool_password":
        await query.edit_message_text("🔑 Пароль:\n\n" + generate_password(20), reply_markup=tools_menu())
    elif data == "tool_nickname":
        await query.edit_message_text("🎭 Ник:\n\n" + generate_nickname(), reply_markup=tools_menu())
    elif data == "daily_bonus":
        u = USERS.get(user_id)
        if not u:
            return
        if u.get("daily_claimed") == today_str():
            await query.edit_message_text("🎁 Бонус уже получен.", reply_markup=profile_menu())
            return
        u["daily_claimed"] = today_str()
        u["balance"] += 50
        add_xp(user_id, 10)
        await query.edit_message_text("🎁 +50 монет, +10 XP", reply_markup=profile_menu())
    elif data == "my_referrals":
        u = USERS.get(user_id, {})
        link = "https://t.me/" + (context.bot.username or "bot") + "?start=ref" + str(user_id)
        await query.edit_message_text(
            "👥 Рефералы\n\n🔗 " + link + "\n\n👤 Приглашено: " + str(len(u.get("referrals", []))),
            reply_markup=profile_menu(),
        )
    elif data == "enter_promo":
        context.user_data["enter_promo"] = True
        await query.edit_message_text("🎟 Отправь промокод:", reply_markup=profile_menu())
    elif data == "back_to_menu":
        if is_adm:
            await query.edit_message_text("👑 ADMIN PANEL\n\nВыбери раздел:", reply_markup=admin_menu())
        else:
            await query.edit_message_text(rnd_greet(), reply_markup=main_menu())

# ═══ СООБЩЕНИЯ ═══
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global FORWARD_MESSAGES
    user = update.effective_user
    user_id = user.id
    username = user.username or ""
    text = update.message.text.strip()

    register_user(user_id, username, user.first_name or "")

    if not is_owner(user_id) and contains_protected(text):
        BLOCKED[user_id] = True
        u = USERS.get(user_id)
        if u:
            u["approved"] = False
        await update.message.reply_text("⛔ Доступ отозван.\n\nТы отправил защищённые данные владельца.")
        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text="🚨 ЗАЩИТА\n\n👤 @" + username + "\n🆔 " + str(user_id) + "\n💬 " + text + "\n\n🚫 Доступ отозван.",
            )
        except Exception:
            pass
        return

    if is_owner(user_id) and BROADCAST_MODE.get(user_id):
        BROADCAST_MODE.pop(user_id, None)
        sent = 0
        for uid in USERS.keys():
            if uid == user_id:
                continue
            try:
                await context.bot.send_message(chat_id=uid, text="📨 Сообщение от админа:\n\n" + text)
                sent += 1
            except Exception:
                pass
        await update.message.reply_text("✅ Рассылка: " + str(sent) + " пользователям.")
        return

    if is_owner(user_id) and BROADCAST_TARGET.get(user_id):
        target = text.lstrip("@")
        target_id = None
        if target.isdigit():
            target_id = int(target)
        else:
            target_id = USERNAMES.get(target.lower())
        if not target_id or target_id not in USERS:
            await update.message.reply_text("❌ Получатель не найден.")
            BROADCAST_TARGET.pop(user_id, None)
            return
        context.user_data["dm_target"] = target_id
        BROADCAST_TARGET.pop(user_id, None)
        await update.message.reply_text("📩 Теперь отправь текст сообщения:")
        return

    if is_owner(user_id) and context.user_data.get("edit_balance"):
        try:
            amount = int(text)
            uid = context.user_data.pop("edit_balance")
            if uid in USERS:
                USERS[uid]["balance"] = amount
                await update.message.reply_text("✅ Баланс: " + str(amount))
                try:
                    await context.bot.send_message(chat_id=uid, text="💰 Баланс изменён: " + str(amount))
                except Exception:
                    pass
            else:
                await update.message.reply_text("❌ Не найден.")
        except ValueError:
            await update.message.reply_text("❌ Введи число.")
        return

    if is_owner(user_id) and context.user_data.get("give_xp"):
        try:
            amount = int(text)
            uid = context.user_data.pop("give_xp")
            if uid in USERS:
                add_xp(uid, amount)
                await update.message.reply_text("✅ Выдано XP: " + str(amount))
                try:
                    await context.bot.send_message(chat_id=uid, text="⭐ Тебе выдано XP: " + str(amount))
                except Exception:
                    pass
            else:
                await update.message.reply_text("❌ Не найден.")
        except ValueError:
            await update.message.reply_text("❌ Введи число.")
        return

    if is_owner(user_id) and context.user_data.get("give_lvl"):
        try:
            level = int(text)
            uid = context.user_data.pop("give_lvl")
            if uid in USERS:
                set_level(uid, level)
                await update.message.reply_text("✅ Уровень: " + str(level))
                try:
                    await context.bot.send_message(chat_id=uid, text="🏆 Твой уровень: " + str(level))
                except Exception:
                    pass
            else:
                await update.message.reply_text("❌ Не найден.")
        except ValueError:
            await update.message.reply_text("❌ Введи число.")
        return

    if is_owner(user_id) and context.user_data.get("dm_target"):
        uid = context.user_data.pop("dm_target")
        try:
            await context.bot.send_message(chat_id=uid, text="📩 Сообщение от админа:\n\n" + text)
            await update.message.reply_text("✅ Отправлено.")
        except Exception as e:
            await update.message.reply_text("❌ " + str(e))
        return

    if is_owner(user_id) and context.user_data.get("create_promo"):
        context.user_data.pop("create_promo")
        parts = text.split()
        if len(parts) != 3:
            await update.message.reply_text("❌ Формат: код сумма количество")
            return
        try:
            code, amount, uses = parts[0].upper(), int(parts[1]), int(parts[2])
            PROMOCODES[code] = {"amount": amount, "uses": uses, "used_by": []}
            await update.message.reply_text("✅ Промокод " + code + " создан.")
        except ValueError:
            await update.message.reply_text("❌ Сумма и кол-во — числа.")
        return

    if context.user_data.get("enter_promo"):
        context.user_data.pop("enter_promo")
        code = text.upper()
        if code not in PROMOCODES:
            await update.message.reply_text("❌ Не найден.", reply_markup=profile_menu())
            return
        p = PROMOCODES[code]
        if p["uses"] <= 0:
            await update.message.reply_text("❌ Использован.", reply_markup=profile_menu())
            return
        if user_id in p["used_by"]:
            await update.message.reply_text("❌ Уже активировал.", reply_markup=profile_menu())
            return
        p["uses"] -= 1
        p["used_by"].append(user_id)
        u = USERS.get(user_id)
        if u:
            u["balance"] += p["amount"]
        await update.message.reply_text("✅ +" + str(p["amount"]) + " монет.", reply_markup=profile_menu())
        return

    if GLOBAL_BLOCK and not is_owner(user_id):
        await update.message.reply_text(rnd_gdeny())
        return
    if is_blocked(user_id) and not is_owner(user_id):
        await update.message.reply_text(rnd_deny())
        return
    if not is_owner(user_id) and not is_allowed(user_id):
        await update.message.reply_text("⛔ Доступ запрещён\n\nОтправь /start.")
        return

    try:
        STATS["queries"] += 1
        u = USERS.get(user_id)
        if u:
            u["queries"] = u.get("queries", 0) + 1
        add_xp(user_id, 5)

        if FORWARD_MESSAGES and not is_owner(user_id):
            try:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text="📬 @" + username + " (" + str(user_id) + ")\n\n💬 " + text,
                )
            except Exception:
                pass

        if re.match(r"^\+?\d{10,15}$", text):
            info = get_phone_info(text)
            if "error" in info:
                await update.message.reply_text("❌ " + info["error"], reply_markup=back_main())
                return
            reply = (
                "📞 Результат\n\n"
                "🔹 Номер: " + info["phone"] + "\n"
                "🌍 Страна: " + info["country"] + "\n"
                "📡 Оператор: " + info["operator"] + "\n"
                "⏳ Таймзона: " + info["timezone"]
            )
            await update.message.reply_text(reply, reply_markup=back_main())

        elif text.startswith("@"):
            info = get_telegram_info(text[1:])
            if "error" in info:
                await update.message.reply_text("❌ " + info["error"], reply_markup=back_main())
                return
            if info.get("exists"):
                reply = (
                    "👤 Результат\n\n"
                    "✅ Юзернейм: @" + info["username"] + "\n"
                    "🔗 Ссылка: " + info["url"] + "\n"
                    "📝 Название: " + info.get("title", "Неизвестно")
                )
                await update.message.reply_text(reply, reply_markup=back_main())
            else:
                await update.message.reply_text("❌ Юзернейм не существует.", reply_markup=back_main())

        elif "." in text and " " not in text:
            info = get_domain_info(text)
            if "error" in info:
                await update.message.reply_text("❌ " + info["error"], reply_markup=back_main())
                return
            reply = "🔍 Домен\n\n🔹 " + info["domain"] + "\n🌐 IP: " + info["ip"]
            await update.message.reply_text(reply, reply_markup=back_main())

        else:
            await update.message.reply_text("❌ Не распознано. Выбери из меню:", reply_markup=main_menu())

    except Exception as e:
        await update.message.reply_text("⚠️ Ошибка: " + str(e))
        logger.error("Краш: " + str(e))

# ═══ ЗАПУСК ═══
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("🤖 SquidHub Bot v8.0 запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()