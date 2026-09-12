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

# Защищённые данные (если кто-то кинет их — сразу блок)
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

def set_xp(user_id, amount):
    u = USERS.get(user_id)
    if not u:
        return
    u["xp"] = amount
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
    """Проверяет, есть ли в тексте защищённые данные владельца."""
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

# ═══ КЛАВИАТУРЫ ═══

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