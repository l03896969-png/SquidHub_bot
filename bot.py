# -*- coding: utf-8 -*-
import logging
import re
import requests
import random
import string
import socket
import time
import html
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
MUTED = {}
PENDING = {}
PROMOCODES = {}
GLOBAL_BLOCK = False
FORWARD_MESSAGES = True
ANTISPAM_ENABLED = True
ANTIFLOOD_ENABLED = True
STATS = {"queries": 0, "mutes": 0}
BROADCAST_MODE = {}
BROADCAST_TARGET = {}
SPAM_TRACKER = {}
WARNINGS = {}
LAST_MESSAGES = {}

SPAM_LIMIT = 5
SPAM_WINDOW = 5
MAX_WARNINGS = 3
MUTE_LEVELS = [300, 3600, 86400]
MUTE_COUNTS = {}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

GREETINGS = [
    "🛸 SQUIDHUB\n\nВыбери раздел:",
    "⚡ СИСТЕМА АКТИВНА\n\nЧто пробиваем?",
    "🔮 SQUIDHUB BOT\n\nВыбирай инструмент:",
    "🎯 ГОТОВ К РАБОТЕ\n\nКуда направим запрос?",
]

DENY_MESSAGES = [
    "⛔ Доступ заблокирован администратором",
    "🚫 Твой доступ приостановлен",
    "🔒 Бот закрыт для тебя",
]

GLOBAL_DENY = [
    "⛔ Бот временно выключен",
    "🔒 Технический перерыв",
    "🛑 Сервис недоступен",
]

WAIT_MESSAGES = [
    "📨 Заявка улетела админу",
    "⏳ Запрос отправлен",
    "✉️ Заявка на рассмотрении",
]

MUTE_MESSAGES = [
    "🔇 Ты в муте. Осталось: {time}",
    "⏱ Подожди. Мут снимется через: {time}",
    "🚫 Флуд запрещён. Мут: {time}",
]

def rnd_greet():
    return random.choice(GREETINGS)

def rnd_deny():
    return random.choice(DENY_MESSAGES)

def rnd_gdeny():
    return random.choice(GLOBAL_DENY)

def rnd_wait():
    return random.choice(WAIT_MESSAGES)

def rnd_mute(time_left):
    return random.choice(MUTE_MESSAGES).format(time=time_left)

def now_str():
    return datetime.now().strftime("%d.%m.%Y %H:%M")

def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def fmt_time(seconds):
    if seconds < 60:
        return str(seconds) + " сек"
    if seconds < 3600:
        return str(seconds // 60) + " мин"
    if seconds < 86400:
        return str(seconds // 3600) + " ч"
    return str(seconds // 86400) + " дн"

def esc(text):
    """Экранирование для HTML."""
    return html.escape(str(text), quote=False)

def safe_username(username):
    """Убирает проблемные символы."""
    if not username:
        return "без_юзернейма"
    return re.sub(r"[*_`\[\]()]", "", username)

def is_owner(user_id):
    return user_id == OWNER_ID

def is_blocked(user_id):
    return user_id in BLOCKED

def is_muted(user_id):
    if user_id not in MUTED:
        return False, 0
    left = int(MUTED[user_id] - time.time())
    if left <= 0:
        MUTED.pop(user_id, None)
        return False, 0
    return True, left

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

def check_spam(user_id):
    if not ANTISPAM_ENABLED:
        return False
    now = time.time()
    if user_id not in SPAM_TRACKER:
        SPAM_TRACKER[user_id] = []
    SPAM_TRACKER[user_id] = [t for t in SPAM_TRACKER[user_id] if now - t < SPAM_WINDOW]
    SPAM_TRACKER[user_id].append(now)
    return len(SPAM_TRACKER[user_id]) > SPAM_LIMIT

def apply_mute(user_id):
    level = MUTE_COUNTS.get(user_id, 0)
    if level >= len(MUTE_LEVELS):
        BLOCKED[user_id] = True
        u = USERS.get(user_id)
        if u:
            u["approved"] = False
        return -1, 0
    duration = MUTE_LEVELS[level]
    MUTED[user_id] = time.time() + duration
    MUTE_COUNTS[user_id] = level + 1
    STATS["mutes"] += 1
    return level + 1, duration

async def cleanup_messages(context, user_id, keep_last=0):
    msgs = LAST_MESSAGES.get(user_id, [])
    while len(msgs) > keep_last:
        mid = msgs.pop(0)
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=mid)
        except Exception:
            pass
    LAST_MESSAGES[user_id] = msgs

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
        return {"domain": domain, "ip": ip}
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
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")]])

def back_admin():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ В админ-панель", callback_data="admin_panel")]])

def main_menu(is_admin=False):
    keyboard = [
        [InlineKeyboardButton("📞 Номер", callback_data="menu_phone"),
         InlineKeyboardButton("👤 Юзер", callback_data="menu_username")],
        [InlineKeyboardButton("🔍 Домен", callback_data="menu_domain"),
         InlineKeyboardButton("🎲 Инструменты", callback_data="menu_tools")],
        [InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")],
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def tools_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Пароль", callback_data="tool_password"),
         InlineKeyboardButton("🎭 Ник", callback_data="tool_nickname")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")],
    ])

def profile_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Бонус", callback_data="daily_bonus"),
         InlineKeyboardButton("👥 Рефералы", callback_data="my_referrals")],
        [InlineKeyboardButton("🎟 Промокод", callback_data="enter_promo")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")],
    ])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Юзеры", callback_data="adm_users"),
         InlineKeyboardButton("📊 Стата", callback_data="adm_stats")],
        [InlineKeyboardButton("📨 Рассылка", callback_data="adm_broadcast"),
         InlineKeyboardButton("🚫 Блоки", callback_data="adm_blocks")],
        [InlineKeyboardButton("🛡 Модерация", callback_data="adm_moderation"),
         InlineKeyboardButton("🎟 Промо", callback_data="adm_promos")],
        [InlineKeyboardButton("💰 Экономика", callback_data="adm_economy"),
         InlineKeyboardButton("⚙️ Настройки", callback_data="adm_settings")],
        [InlineKeyboardButton("📋 Заявки", callback_data="adm_pending")],
        [InlineKeyboardButton("⬅️ В меню", callback_data="back_to_menu")],
    ])

def moderation_menu():
    anti = "🟢 ВКЛ" if ANTIFLOOD_ENABLED else "🔴 ВЫКЛ"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛡 Антифлуд: " + anti, callback_data="antiflood_toggle")],
        [InlineKeyboardButton("📋 Активные муты", callback_data="adm_mutes")],
        [InlineKeyboardButton("📋 Варны", callback_data="adm_warns_list")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")],
    ])

def broadcast_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Всем", callback_data="bc_all"),
         InlineKeyboardButton("👤 Одному", callback_data="bc_one")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")],
    ])

def admin_settings_menu():
    gs = "🔴 ВЫКЛ" if GLOBAL_BLOCK else "🟢 ВКЛ"
    fs = "🔔 ВКЛ" if FORWARD_MESSAGES else "🔕 ВЫКЛ"
    anti = "🟢 ВКЛ" if ANTISPAM_ENABLED else "🔴 ВЫКЛ"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Доступ: " + gs, callback_data="global_toggle")],
        [InlineKeyboardButton("🔔 Уведомления: " + fs, callback_data="forward_toggle")],
        [InlineKeyboardButton("⚠️ Антиспам: " + anti, callback_data="antispam_toggle")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")],
    ])

def approval_buttons(user_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Одобрить", callback_data="approve_" + str(user_id)),
        InlineKeyboardButton("❌ Отклонить", callback_data="deny_" + str(user_id)),
    ]])

def user_manage_buttons(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Блок", callback_data="block_" + str(user_id)),
         InlineKeyboardButton("✅ Разблок", callback_data="unblock_" + str(user_id))],
        [InlineKeyboardButton("🔇 Мут", callback_data="mute_" + str(user_id)),
         InlineKeyboardButton("🔊 Размут", callback_data="unmute_" + str(user_id))],
        [InlineKeyboardButton("💰 Баланс", callback_data="edit_balance_" + str(user_id)),
         InlineKeyboardButton("⭐ XP", callback_data="give_xp_" + str(user_id))],
        [InlineKeyboardButton("🏆 Уровень", callback_data="give_lvl_" + str(user_id)),
         InlineKeyboardButton("⚠️ Сброс варнов", callback_data="reset_warn_" + str(user_id))],
        [InlineKeyboardButton("📩 Написать", callback_data="dm_" + str(user_id))],
        [InlineKeyboardButton("⬅️ К списку", callback_data="adm_users")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or ""
    first_name = user.first_name or ""
    register_user(user_id, username, first_name)

    if is_owner(user_id):
        msg = await update.message.reply_text(rnd_greet(), reply_markup=main_menu(is_admin=True))
        LAST_MESSAGES.setdefault(user_id, []).append(msg.message_id)
        return

    if GLOBAL_BLOCK:
        await update.message.reply_text(rnd_gdeny())
        return

    if is_blocked(user_id):
        await update.message.reply_text(rnd_deny())
        return

    if is_allowed(user_id):
        msg = await update.message.reply_text(rnd_greet(), reply_markup=main_menu(is_admin=False))
        LAST_MESSAGES.setdefault(user_id, []).append(msg.message_id)
        return

    muted, left = is_muted(user_id)
    if muted:
        await update.message.reply_text(rnd_mute(fmt_time(left)))
        return

    if check_spam(user_id):
        level, dur = apply_mute(user_id)
        if level == -1:
            await update.message.reply_text("🚫 Заблокирован за флуд")
        else:
            await update.message.reply_text(rnd_mute(fmt_time(dur)))
        return

    if context.args and context.args[0].startswith("ref"):
        try:
            ref_id = int(context.args[0][3:])
            if ref_id != user_id and ref_id in USERS:
                if user_id not in USERS[ref_id]["referrals"]:
                    USERS[ref_id]["referrals"].append(user_id)
        except Exception:
            pass

    if user_id in PENDING:
        await update.message.reply_text("⏳ Заявка уже на рассмотрении.")
        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text="🔔 Повторная заявка\n\n👤 @" + safe_username(username) + "\n🆔 " + str(user_id) + "\n📅 " + now_str(),
                reply_markup=approval_buttons(user_id),
            )
        except Exception as e:
            logger.error("Ошибка повторной заявки: " + str(e))
        return

    PENDING[user_id] = {"username": username, "time": now_str()}
    await update.message.reply_text(rnd_wait())

    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text="🔔 Новая заявка\n\n👤 @" + safe_username(username) + "\n🆔 " + str(user_id) + "\n📅 " + now_str(),
            reply_markup=approval_buttons(user_id),
        )
        logger.info("Заявка отправлена владельцу от " + str(user_id))
    except Exception as e:
        logger.error("Ошибка отправки заявки: " + str(e))
        await update.message.reply_text("⚠️ Не смог отправить заявку. Попробуй позже.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GLOBAL_BLOCK, FORWARD_MESSAGES, ANTISPAM_ENABLED, ANTIFLOOD_ENABLED
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    is_adm = is_owner(user_id)

    try:
        if data == "adm_moderation":
            if not is_adm:
                return
            anti = "🟢 ВКЛ" if ANTIFLOOD_ENABLED else "🔴 ВЫКЛ"
            text = "🛡 Модерация\n\nАнтифлуд: " + anti + "\nМуты: 5м → 1ч → 24ч → бан"
            await query.edit_message_text(text, reply_markup=moderation_menu())
            return

        if data == "antiflood_toggle":
            if not is_adm:
                return
            ANTIFLOOD_ENABLED = not ANTIFLOOD_ENABLED
            await query.edit_message_text("Модерация:", reply_markup=moderation_menu())
            return

        if data == "adm_mutes":
            if not is_adm:
                return
            if not MUTED:
                await query.edit_message_text("🔇 Нет мутов.", reply_markup=moderation_menu())
                return
            text = "🔇 Муты:\n\n"
            keyboard = []
            for uid in list(MUTED.keys()):
                u = USERS.get(uid, {})
                left = int(MUTED[uid] - time.time())
                if left <= 0:
                    MUTED.pop(uid, None)
                    continue
                uname = safe_username(u.get("username") or str(uid))
                text += "• @" + uname + " — " + fmt_time(left) + "\n"
                keyboard.append([InlineKeyboardButton("🔊 @" + uname, callback_data="unmute_" + str(uid))])
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="adm_moderation")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if data.startswith("mute_"):
            if not is_adm:
                return
            uid = int(data.split("_", 1)[1])
            MUTED[uid] = time.time() + 300
            await query.edit_message_text("🔇 Мут 5 мин.", reply_markup=admin_menu())
            return

        if data.startswith("unmute_"):
            if not is_adm:
                return
            uid = int(data.split("_", 1)[1])
            MUTED.pop(uid, None)
            MUTE_COUNTS.pop(uid, None)
            await query.edit_message_text("🔊 Размучен.", reply_markup=admin_menu())
            return

        if data == "adm_warns_list":
            if not is_adm:
                return
            if not WARNINGS:
                await query.edit_message_text("⚠️ Нет варнов.", reply_markup=moderation_menu())
                return
            text = "⚠️ Варны:\n\n"
            keyboard = []
            for uid, cnt in WARNINGS.items():
                u = USERS.get(uid, {})
                uname = safe_username(u.get("username") or str(uid))
                text += "• @" + uname + " — " + str(cnt) + "\n"
                keyboard.append([InlineKeyboardButton("✅ @" + uname, callback_data="reset_warn_" + str(uid))])
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="adm_moderation")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

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
                await query.edit_message_text("✅ Одобрена.")
                try:
                    await context.bot.send_message(chat_id=target_id, text="✅ Доступ одобрен\n\nНапиши /start")
                except Exception:
                    pass
            else:
                PENDING.pop(target_id, None)
                await query.edit_message_text("❌ Отклонена.")
                try:
                    await context.bot.send_message(chat_id=target_id, text="❌ Заявка отклонена.")
                except Exception:
                    pass
            return

        if data == "admin_panel":
            if not is_adm:
                return
            await query.edit_message_text("👑 ADMIN PANEL", reply_markup=admin_menu())
            return

        if data == "adm_users":
            if not is_adm:
                return
            if not USERS:
                await query.edit_message_text("📋 Пусто.", reply_markup=admin_menu())
                return
            text = "👥 Юзеры (" + str(len(USERS)) + "):\n\n"
            keyboard = []
            for uid, u in list(USERS.items())[:30]:
                status = "🚫" if is_blocked(uid) else ("🔇" if is_muted(uid)[0] else ("✅" if u.get("approved") else "⏳"))
                uname = safe_username(u.get("username") or str(uid))
                text += status + " @" + uname + "\n"
                keyboard.append([InlineKeyboardButton(status + " @" + uname, callback_data="user_" + str(uid))])
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")])
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
            muted, left = is_muted(uid)
            status = "🚫 Бан" if is_blocked(uid) else ("🔇 Мут " + fmt_time(left) if muted else ("✅ Активен" if u.get("approved") else "⏳ Ожидает"))
            uname = safe_username(u.get("username") or "—")
            text = (
                "👤 Профиль\n\n"
                "🆔 " + str(uid) + "\n"
                "📛 @" + uname + "\n"
                "📅 " + u.get("registered", "—") + "\n"
                "📊 XP: " + str(xp) + "/" + str(need) + "\n"
                "🏆 Ур: " + str(u.get("level", 1)) + "\n"
                "💰 " + str(u.get("balance", 0)) + "\n"
                "⚠️ " + str(WARNINGS.get(uid, 0)) + "/" + str(MAX_WARNINGS) + "\n"
                "🚦 " + status
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
            WARNINGS[uid] = 0
            MUTE_COUNTS.pop(uid, None)
            await query.edit_message_text("✅ Разблокирован.", reply_markup=admin_menu())
            return

        if data.startswith("reset_warn_"):
            if not is_adm:
                return
            uid = int(data.split("_", 2)[2])
            WARNINGS[uid] = 0
            await query.edit_message_text("⚠️ Сброшено.", reply_markup=admin_menu())
            return

        if data.startswith("edit_balance_"):
            if not is_adm:
                return
            uid = int(data.split("_", 2)[2])
            context.user_data["edit_balance"] = uid
            await query.edit_message_text("💰 Баланс:", reply_markup=back_admin())
            return

        if data.startswith("give_xp_"):
            if not is_adm:
                return
            uid = int(data.split("_", 2)[2])
            context.user_data["give_xp"] = uid
            await query.edit_message_text("⭐ XP:", reply_markup=back_admin())
            return

        if data.startswith("give_lvl_"):
            if not is_adm:
                return
            uid = int(data.split("_", 2)[2])
            context.user_data["give_lvl"] = uid
            await query.edit_message_text("🏆 Уровень:", reply_markup=back_admin())
            return

        if data.startswith("dm_"):
            if not is_adm:
                return
            uid = int(data.split("_", 1)[1])
            context.user_data["dm_target"] = uid
            await query.edit_message_text("📩 Сообщение:", reply_markup=back_admin())
            return

        if data == "adm_stats":
            if not is_adm:
                return
            text = (
                "📊 Статистика\n\n"
                "👥 Всего: " + str(len(USERS)) + "\n"
                "✅ Активных: " + str(sum(1 for u in USERS.values() if u.get("approved"))) + "\n"
                "🚫 Бан: " + str(len(BLOCKED)) + "\n"
                "🔇 Мут: " + str(len(MUTED)) + "\n"
                "⏳ Заявок: " + str(len(PENDING)) + "\n"
                "🔇 Мутов: " + str(STATS["mutes"])
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
            await query.edit_message_text("📢 Текст для ВСЕХ:", reply_markup=back_admin())
            return

        if data == "bc_one":
            if not is_adm:
                return
            BROADCAST_TARGET[user_id] = True
            await query.edit_message_text("👤 ID или @username:", reply_markup=back_admin())
            return

        if data == "adm_blocks":
            if not is_adm:
                return
            if not BLOCKED:
                await query.edit_message_text("🚫 Пусто.", reply_markup=admin_menu())
                return
            text = "🚫 Заблокированные:\n\n"
            keyboard = []
            for uid in BLOCKED.keys():
                u = USERS.get(uid, {})
                uname = safe_username(u.get("username") or str(uid))
                text += "• @" + uname + "\n"
                keyboard.append([InlineKeyboardButton("✅ @" + uname, callback_data="unblock_" + str(uid))])
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if data == "adm_promos":
            if not is_adm:
                return
            text = "🎟 Промокоды:\n\n"
            if PROMOCODES:
                for code, info in PROMOCODES.items():
                    text += "• " + code + " — " + str(info["amount"]) + "\n"
            else:
                text += "Пусто."
            keyboard = [
                [InlineKeyboardButton("➕ Создать", callback_data="create_promo")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")],
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if data == "create_promo":
            if not is_adm:
                return
            context.user_data["create_promo"] = True
            await query.edit_message_text("🎟 Формат: код сумма количество", reply_markup=back_admin())
            return

        if data == "adm_economy":
            if not is_adm:
                return
            total = sum(u.get("balance", 0) for u in USERS.values())
            text = "💰 Экономика\n\n💵 Общий: " + str(total) + "\n👥 Кошельков: " + str(len(USERS))
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
            await query.edit_message_text("⚙️ Настройки:", reply_markup=admin_settings_menu())
            return

        if data == "forward_toggle":
            if not is_adm:
                return
            FORWARD_MESSAGES = not FORWARD_MESSAGES
            await query.edit_message_text("⚙️ Настройки:", reply_markup=admin_settings_menu())
            return

        if data == "antispam_toggle":
            if not is_adm:
                return
            ANTISPAM_ENABLED = not ANTISPAM_ENABLED
            await query.edit_message_text("⚙️ Настройки:", reply_markup=admin_settings_menu())
            return

        if data == "adm_pending":
            if not is_adm:
                return
            if not PENDING:
                await query.edit_message_text("📋 Пусто.", reply_markup=admin_menu())
                return
            text = "📋 Заявки:\n\n"
            keyboard = []
            for uid, info in PENDING.items():
                uname = safe_username(info.get("username") or str(uid))
                text += "• @" + uname + "\n"
                keyboard.append([InlineKeyboardButton("✅ @" + uname, callback_data="approve_" + str(uid))])
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if data == "menu_phone":
            await query.edit_message_text("📞 Номер\n\nОтправь: +380XXXXXXXXX", reply_markup=back_main())
        elif data == "menu_username":
            await query.edit_message_text("👤 Юзер\n\nОтправь: @username", reply_markup=back_main())
        elif data == "menu_domain":
            await query.edit_message_text("🔍 Домен\n\nОтправь: google.com", reply_markup=back_main())
        elif data == "menu_tools":
            await query.edit_message_text("🎲 Инструменты:", reply_markup=tools_menu())
        elif data == "menu_profile":
            if not is_allowed(user_id) and not is_adm:
                await query.edit_message_text("⛔ Нет доступа.", reply_markup=back_main())
                return
            u = USERS.get(user_id, {})
            xp, need = level_progress(user_id)
            uname = safe_username(u.get("username") or "—")
            text = (
                "👤 Профиль\n\n"
                "🆔 " + str(user_id) + "\n"
                "📛 @" + uname + "\n"
                "📊 XP: " + str(xp) + "/" + str(need) + "\n"
                "🏆 Ур: " + str(u.get("level", 1)) + "\n"
                "💰 " + str(u.get("balance", 0)) + "\n"
                "👥 Реф: " + str(len(u.get("referrals", [])))
            )
            await query.edit_message_text(text, reply_markup=profile_menu())
        elif data == "tool_password":
            await query.edit_message_text("🔑 " + generate_password(20), reply_markup=tools_menu())
        elif data == "tool_nickname":
            await query.edit_message_text("🎭 " + generate_nickname(), reply_markup=tools_menu())
        elif data == "daily_bonus":
            u = USERS.get(user_id)
            if not u:
                return
            if u.get("daily_claimed") == today_str():
                await query.edit_message_text("🎁 Уже получен.", reply_markup=profile_menu())
                return
            u["daily_claimed"] = today_str()
            u["balance"] += 50
            add_xp(user_id, 10)
            await query.edit_message_text("🎁 +50 монет", reply_markup=profile_menu())
        elif data == "my_referrals":
            u = USERS.get(user_id, {})
            link = "https://t.me/" + (context.bot.username or "bot") + "?start=ref" + str(user_id)
            await query.edit_message_text(
                "👥 Рефералы\n\n🔗 " + link + "\n\n👤 " + str(len(u.get("referrals", []))),
                reply_markup=profile_menu(),
            )
        elif data == "enter_promo":
            context.user_data["enter_promo"] = True
            await query.edit_message_text("🎟 Промокод:", reply_markup=profile_menu())
        elif data == "back_to_menu":
            if is_adm:
                await query.edit_message_text(rnd_greet(), reply_markup=main_menu(is_admin=True))
            else:
                await query.edit_message_text(rnd_greet(), reply_markup=main_menu(is_admin=False))

    except Exception as e:
        logger.error("Ошибка в button_handler: " + str(e))
        try:
            await query.answer("Ошибка: " + str(e)[:50], show_alert=True)
        except Exception:
            pass

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global FORWARD_MESSAGES
    user = update.effective_user
    user_id = user.id
    username = user.username or ""
    text = update.message.text.strip()

    register_user(user_id, username, user.first_name or "")

    if not is_owner(user_id):
        muted, left = is_muted(user_id)
        if muted:
            await update.message.reply_text(rnd_mute(fmt_time(left)))
            return

    if not is_owner(user_id) and contains_protected(text):
        BLOCKED[user_id] = True
        u = USERS.get(user_id)
        if u:
            u["approved"] = False
        await update.message.reply_text("🚫 Заблокирован.")
        return

    if not is_owner(user_id) and ANTIFLOOD_ENABLED and check_spam(user_id):
        SPAM_TRACKER[user_id] = []
        level, dur = apply_mute(user_id)
        if level == -1:
            await update.message.reply_text("🚫 Заблокирован за флуд")
        else:
            await update.message.reply_text(rnd_mute(fmt_time(dur)))
        return

    if is_owner(user_id) and BROADCAST_MODE.get(user_id):
        BROADCAST_MODE.pop(user_id, None)
        sent = 0
        for uid in USERS.keys():
            if uid == user_id:
                continue
            try:
                await context.bot.send_message(chat_id=uid, text="📨 От админа:\n\n" + text)
                sent += 1
            except Exception:
                pass
        await update.message.reply_text("✅ Отправлено: " + str(sent))
        return

    if is_owner(user_id) and BROADCAST_TARGET.get(user_id):
        target = text.lstrip("@")
        target_id = None
        if target.isdigit():
            target_id = int(target)
        else:
            target_id = USERNAMES.get(target.lower())
        if not target_id or target_id not in USERS:
            await update.message.reply_text("❌ Не найден.")
            BROADCAST_TARGET.pop(user_id, None)
            return
        context.user_data["dm_target"] = target_id
        BROADCAST_TARGET.pop(user_id, None)
        await update.message.reply_text("📩 Текст:")
        return

    if is_owner(user_id) and context.user_data.get("edit_balance"):
        try:
            amount = int(text)
            uid = context.user_data.pop("edit_balance")
            if uid in USERS:
                USERS[uid]["balance"] = amount
                await update.message.reply_text("✅ " + str(amount))
            else:
                await update.message.reply_text("❌ Не найден.")
        except ValueError:
            await update.message.reply_text("❌ Число.")
        return

    if is_owner(user_id) and context.user_data.get("give_xp"):
        try:
            amount = int(text)
            uid = context.user_data.pop("give_xp")
            if uid in USERS:
                add_xp(uid, amount)
                await update.message.reply_text("✅ XP: " + str(amount))
        except ValueError:
            await update.message.reply_text("❌ Число.")
        return

    if is_owner(user_id) and context.user_data.get("give_lvl"):
        try:
            level = int(text)
            uid = context.user_data.pop("give_lvl")
            if uid in USERS:
                set_level(uid, level)
                await update.message.reply_text("✅ Уровень: " + str(level))
        except ValueError:
            await update.message.reply_text("❌ Число.")
        return

    if is_owner(user_id) and context.user_data.get("dm_target"):
        uid = context.user_data.pop("dm_target")
        try:
            await context.bot.send_message(chat_id=uid, text="📩 От админа:\n\n" + text)
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
            await update.message.reply_text("✅ " + code)
        except ValueError:
            await update.message.reply_text("❌ Числа.")
        return

    if context.user_data.get("enter_promo"):
        context.user_data.pop("enter_promo")
        code = text.upper()
        if code not in PROMOCODES:
            await update.message.reply_text("❌ Не найден.", reply_markup=profile_menu())
            return
        p = PROMOCODES[code]
        if p["uses"] <= 0 or user_id in p["used_by"]:
            await update.message.reply_text("❌ Недоступен.", reply_markup=profile_menu())
            return
        p["uses"] -= 1
        p["used_by"].append(user_id)
        u = USERS.get(user_id)
        if u:
            u["balance"] += p["amount"]
        await update.message.reply_text("✅ +" + str(p["amount"]), reply_markup=profile_menu())
        return

    if GLOBAL_BLOCK and not is_owner(user_id):
        await update.message.reply_text(rnd_gdeny())
        return
    if is_blocked(user_id) and not is_owner(user_id):
        await update.message.reply_text(rnd_deny())
        return
    if not is_owner(user_id) and not is_allowed(user_id):
        await update.message.reply_text("⛔ Доступ запрещён. /start")
        return

    try:
        await update.message.delete()
    except Exception:
        pass
    await cleanup_messages(context, user_id, keep_last=0)

    if re.match(r"^\+?\d{10,15}$", text):
        info = get_phone_info(text)
        if "error" in info:
            msg = await update.message.reply_text("❌ " + info["error"], reply_markup=back_main())
            LAST_MESSAGES.setdefault(user_id, []).append(msg.message_id)
            return
        reply = (
            "📞 Номер: " + info["phone"] + "\n"
            "🌍 Страна: " + info["country"] + "\n"
            "📡 Оператор: " + info["operator"]
        )
        msg = await update.message.reply_text(reply, reply_markup=back_main())
        LAST_MESSAGES.setdefault(user_id, []).append(msg.message_id)
        STATS["queries"] += 1
        return

    if text.startswith("@"):
        info = get_telegram_info(text[1:])
        if info.get("exists"):
            reply = "👤 @" + info["username"] + "\n🔗 " + info["url"] + "\n📝 " + info.get("title", "—")
            msg = await update.message.reply_text(reply, reply_markup=back_main())
        else:
            msg = await update.message.reply_text("❌ Не существует.", reply_markup=back_main())
        LAST_MESSAGES.setdefault(user_id, []).append(msg.message_id)
        STATS["queries"] += 1
        return

    if "." in text and " " not in text and not text.startswith("@"):
        info = get_domain_info(text)
        if "error" in info:
            msg = await update.message.reply_text("❌ " + info["error"], reply_markup=back_main())
            LAST_MESSAGES.setdefault(user_id, []).append(msg.message_id)
            return
        msg = await update.message.reply_text("🔍 " + info["domain"] + "\n🌐 " + info["ip"], reply_markup=back_main())
        LAST_MESSAGES.setdefault(user_id, []).append(msg.message_id)
        STATS["queries"] += 1
        return

    msg = await update.message.reply_text("❌ Не распознано.", reply_markup=main_menu(is_admin=is_owner(user_id)))
    LAST_MESSAGES.setdefault(user_id, []).append(msg.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_text))
    logger.info("🤖 SquidHub Bot v13.2 запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()