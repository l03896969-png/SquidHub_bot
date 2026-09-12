# -*- coding: utf-8 -*-
import logging
import re
import requests
import random
import string
import socket
import time
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
ANTISPAM_ENABLED = True          # ← ТУМБЛЕР АНТИСПАМА
STATS = {"queries": 0}
BROADCAST_MODE = {}
BROADCAST_TARGET = {}
SPAM_TRACKER = {}
WARNINGS = {}
LAST_MESSAGES = {}

SPAM_LIMIT = 5
SPAM_WINDOW = 5
MAX_WARNINGS = 3

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
#  ШАБЛОНЫ
# ═══════════════════════════════════════════════

GREETINGS = [
    "╔══════════════════╗\n   🛸 *SQUIDHUB*\n╚══════════════════╝\n\nВыбери раздел:",
    "┌──────────────────┐\n  ⚡ *СИСТЕМА АКТИВНА*\n└──────────────────┘\n\nЧто пробиваем?",
    "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n   🔮 *SQUIDHUB BOT*\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\nВыбирай инструмент:",
    "◤◢◤◢◤◢◤◢◤◢◤◢◤◢\n    🎯 *ГОТОВ К РАБОТЕ*\n◤◢◤◢◤◢◤◢◤◢◤◢◤◢\n\nКуда направим запрос?",
    "┏━━━━━━━━━━━━━━┓\n   🧠 *ВСЁ ПОД РУКОЙ*\n┗━━━━━━━━━━━━━━┛\n\nВыбирай:",
    "╭────────────────╮\n   🚀 *SQUIDHUB*\n╰────────────────╯\n\nСистема готова. Действие:",
]

DENY_MESSAGES = [
    "⛔ *Доступ заблокирован администратором*\n\nОбратись к владельцу.",
    "🚫 *Твой доступ приостановлен*\n\nСвяжись с админом.",
    "🔒 *Бот закрыт для тебя*\n\nПричина: решение администратора.",
    "❌ *Ты в чёрном списке*\n\nДоступ заблокирован.",
]

GLOBAL_DENY = [
    "⛔ *Бот временно выключен*\n\nЗаходи позже.",
    "🔒 *Технический перерыв*\n\nАдмин скоро вернёт доступ.",
    "⚠️ *SquidHub остановлен*\n\nОжидай включения.",
    "🛑 *Сервис недоступен*\n\nПопробуй позже.",
]

WAIT_MESSAGES = [
    "📨 *Заявка улетела админу*\n\nЖди вердикта.",
    "⏳ *Запрос отправлен*\n\nАдмин скоро ответит.",
    "✉️ *Заявка на рассмотрении*\n\nНе спамь, жди.",
    "📮 *Голубь с заявкой улетел*\n\nОжидай.",
    "🕐 *Заявка в очереди*\n\nАдмин рассмотрит в ближайшее время.",
]

BLOCK_MESSAGES = [
    "🚫 *Ты заблокирован.*",
    "⛔ *Доступ отозван.*",
    "🔒 *Ты в чёрном списке.*",
]

SPAM_WARN_MESSAGES = [
    "⚠️ *Предупреждение {n}/{max}*\n\nНе спамь.",
    "⚠️ *Варн {n}/{max}*\n\nПрекрати флуд.",
    "⚠️ *Осталось {left} варнов*\n\nСбавь темп.",
]

def rnd_greet():
    return random.choice(GREETINGS)

def rnd_deny():
    return random.choice(DENY_MESSAGES)

def rnd_gdeny():
    return random.choice(GLOBAL_DENY)

def rnd_wait():
    return random.choice(WAIT_MESSAGES)

def rnd_block():
    return random.choice(BLOCK_MESSAGES)

def rnd_spam_warn(n, max_w):
    tpl = random.choice(SPAM_WARN_MESSAGES)
    return tpl.format(n=n, max=max_w, left=max_w - n)

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

def check_spam(user_id):
    """Проверка на спам. Возвращает True если спамит."""
    if not ANTISPAM_ENABLED:
        return False
    now = time.time()
    if user_id not in SPAM_TRACKER:
        SPAM_TRACKER[user_id] = []
    SPAM_TRACKER[user_id] = [t for t in SPAM_TRACKER[user_id] if now - t < SPAM_WINDOW]
    SPAM_TRACKER[user_id].append(now)
    return len(SPAM_TRACKER[user_id]) > SPAM_LIMIT

def add_warning(user_id):
    WARNINGS[user_id] = WARNINGS.get(user_id, 0) + 1
    if WARNINGS[user_id] >= MAX_WARNINGS:
        BLOCKED[user_id] = True
        u = USERS.get(user_id)
        if u:
            u["approved"] = False
        return WARNINGS[user_id], True
    return WARNINGS[user_id], False

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
        [InlineKeyboardButton("⚠️ Варны", callback_data="adm_warns"),
         InlineKeyboardButton("🎟 Промо", callback_data="adm_promos")],
        [InlineKeyboardButton("💰 Экономика", callback_data="adm_economy"),
         InlineKeyboardButton("⚙️ Настройки", callback_data="adm_settings")],
        [InlineKeyboardButton("📋 Заявки", callback_data="adm_pending")],
        [InlineKeyboardButton("⬅️ В меню", callback_data="back_to_menu")],
    ])

def warns_menu():
    anti = "🟢 ВКЛ" if ANTISPAM_ENABLED else "🔴 ВЫКЛ"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛡 Антиспам: " + anti, callback_data="antispam_toggle")],
        [InlineKeyboardButton("📋 Список варнов", callback_data="adm_warns_list")],
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
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Доступ: " + gs, callback_data="global_toggle")],
        [InlineKeyboardButton("🔔 Уведомления: " + fs, callback_data="forward_toggle")],
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
        [InlineKeyboardButton("💰 Баланс", callback_data="edit_balance_" + str(user_id)),
         InlineKeyboardButton("⭐ XP", callback_data="give_xp_" + str(user_id))],
        [InlineKeyboardButton("🏆 Уровень", callback_data="give_lvl_" + str(user_id)),
         InlineKeyboardButton("⚠️ Сброс варнов", callback_data="reset_warn_" + str(user_id))],
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

    # /start-СПАМ
    if not is_owner(user_id) and check_spam(user_id):
        cnt, blocked = add_warning(user_id)
        SPAM_TRACKER[user_id] = []
        if blocked:
            await update.message.reply_text("🚫 *Заблокирован за /start-спам.*", parse_mode="Markdown")
            try:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text="🚫 *Автоблок за /start-спам*\n\n👤 @" + username + "\n🆔 `" + str(user_id) + "`",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        else:
            await update.message.reply_text(rnd_spam_warn(cnt, MAX_WARNINGS), parse_mode="Markdown")
            try:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text="⚠️ */start-спам*\n\n👤 @" + username + "\n🆔 `" + str(user_id) + "`\n📊 " + str(cnt) + "/" + str(MAX_WARNINGS),
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        return

    if context.args and context.args[0].startswith("ref"):
        try:
            ref_id = int(context.args[0][3:])
            if ref_id != user_id and ref_id in USERS:
                if user_id not in USERS[ref_id]["referrals"]:
                    USERS[ref_id]["referrals"].append(user_id)
        except Exception:
            pass

    if is_owner(user_id):
        msg = await update.message.reply_text(rnd_greet(), parse_mode="Markdown", reply_markup=main_menu(is_admin=True))
        LAST_MESSAGES.setdefault(user_id, []).append(msg.message_id)
        return

    if GLOBAL_BLOCK:
        await update.message.reply_text(rnd_gdeny(), parse_mode="Markdown")
        return
    if is_blocked(user_id):
        await update.message.reply_text(rnd_deny(), parse_mode="Markdown")
        return
    if is_allowed(user_id):
        msg = await update.message.reply_text(rnd_greet(), parse_mode="Markdown", reply_markup=main_menu(is_admin=False))
        LAST_MESSAGES.setdefault(user_id, []).append(msg.message_id)
        return
    if user_id in PENDING:
        await update.message.reply_text("⏳ Заявка уже на рассмотрении.", parse_mode="Markdown")
        return

    PENDING[user_id] = {"username": username, "time": now_str()}
    await update.message.reply_text(rnd_wait(), parse_mode="Markdown")
    await context.bot.send_message(
        chat_id=OWNER_ID,
        text="🔔 *Новая заявка*\n\n👤 @" + (username or "без_юзернейма") + "\n🆔 `" + str(user_id) + "`\n📅 " + now_str(),
        parse_mode="Markdown",
        reply_markup=approval_buttons(user_id),
    )

# ═══ КНОПКИ ═══
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GLOBAL_BLOCK, FORWARD_MESSAGES, ANTISPAM_ENABLED
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
                await context.bot.send_message(chat_id=target_id, text="✅ *Доступ одобрен*\n\n/start", parse_mode="Markdown")
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
        await query.edit_message_text("╔══════════════════╗\n   👑 *ADMIN PANEL*\n╚══════════════════╝", parse_mode="Markdown", reply_markup=admin_menu())
        return

    if data == "adm_users":
        if not is_adm:
            return
        if not USERS:
            await query.edit_message_text("📋 Пусто.", reply_markup=admin_menu())
            return
        text = "👥 *Пользователи* (" + str(len(USERS)) + "):\n\n"
        keyboard = []
        for uid, u in list(USERS.items())[:30]:
            status = "🚫" if is_blocked(uid) else ("✅" if u.get("approved") else "⏳")
            warn = WARNINGS.get(uid, 0)
            warn_str = " ⚠️" + str(warn) if warn else ""
            text += status + " @" + (u.get("username") or str(uid)) + " | lvl " + str(u.get("level", 1)) + warn_str + "\n"
            keyboard.append([InlineKeyboardButton(status + " @" + (u.get("username") or str(uid)), callback_data="user_" + str(uid))])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
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
        warns = WARNINGS.get(uid, 0)
        text = (
            "╭─ 👤 *Профиль*\n│\n"
            "│ 🆔 `" + str(uid) + "`\n"
            "│ 📛 @" + (u.get("username") or "—") + "\n"
            "│ 👋 " + (u.get("first_name") or "—") + "\n"
            "│ 📅 " + u.get("registered", "—") + "\n"
            "│\n"
            "│ 📊 XP: " + str(xp) + " / " + str(need) + "\n"
            "│ 🏆 Ур: " + str(u.get("level", 1)) + "\n"
            "│ 💰 " + str(u.get("balance", 0)) + "\n"
            "│ 🔍 " + str(u.get("queries", 0)) + "\n"
            "│ 👥 Реф: " + str(len(u.get("referrals", []))) + "\n"
            "│ ⚠️ Варны: " + str(warns) + "/" + str(MAX_WARNINGS) + "\n"
            "│ 🚦 " + status + "\n"
            "╰────────────"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=user_manage_buttons(uid))
        return

    if data.startswith("block_"):
        if not is_adm:
            return
        uid = int(data.split("_", 1)[1])
        BLOCKED[uid] = True
        await query.edit_message_text("🚫 Заблокирован.", reply_markup=admin_menu())
        try:
            await context.bot.send_message(chat_id=uid, text=rnd_block(), parse_mode="Markdown")
        except Exception:
            pass
        return

    if data.startswith("unblock_"):
        if not is_adm:
            return
        uid = int(data.split("_", 1)[1])
        BLOCKED.pop(uid, None)
        WARNINGS[uid] = 0
        await query.edit_message_text("✅ Разблокирован.", reply_markup=admin_menu())
        try:
            await context.bot.send_message(chat_id=uid, text="✅ Доступ восстановлен. /start")
        except Exception:
            pass
        return

    if data.startswith("reset_warn_"):
        if not is_adm:
            return
        uid = int(data.split("_", 2)[2])
        WARNINGS[uid] = 0
        await query.edit_message_text("⚠️ Варны сброшены.", reply_markup=admin_menu())
        return

    if data.startswith("edit_balance_"):
        if not is_adm:
            return
        uid = int(data.split("_", 2)[2])
        context.user_data["edit_balance"] = uid
        await query.edit_message_text("💰 Отправь новое значение баланса:", reply_markup=back_admin())
        return

    if data.startswith("give_xp_"):
        if not is_adm:
            return
        uid = int(data.split("_", 2)[2])
        context.user_data["give_xp"] = uid
        await query.edit_message_text("⭐ Отправь количество XP:", reply_markup=back_admin())
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
        await query.edit_message_text("📩 Отправь сообщение:", reply_markup=back_admin())
        return

    if data == "adm_stats":
        if not is_adm:
            return
        anti = "🟢 ВКЛ" if ANTISPAM_ENABLED else "🔴 ВЫКЛ"
        text = (
            "╭─ 📊 *Статистика*\n│\n"
            "│ 👥 Всего: " + str(len(USERS)) + "\n"
            "│ ✅ Активных: " + str(sum(1 for u in USERS.values() if u.get("approved"))) + "\n"
            "│ 🚫 Заблокировано: " + str(len(BLOCKED)) + "\n"
            "│ ⏳ Заявок: " + str(len(PENDING)) + "\n"
            "│ ⚠️ С варнами: " + str(len(WARNINGS)) + "\n"
            "│ 🛡 Антиспам: " + anti + "\n"
            "│ 🔍 Запросов: " + str(STATS["queries"]) + "\n"
            "│ 🎟 Промокодов: " + str(len(PROMOCODES)) + "\n"
            "╰────────────"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=admin_menu())
        return

    # ── РАЗДЕЛ ВАРНОВ ──
    if data == "adm_warns":
        if not is_adm:
            return
        anti = "🟢 ВКЛ" if ANTISPAM_ENABLED else "🔴 ВЫКЛ"
        text = (
            "╭─ ⚠️ *Антиспам*\n│\n"
            "│ 🛡 Статус: " + anti + "\n"
            "│ 📊 Лимит: " + str(SPAM_LIMIT) + " сообщений / " + str(SPAM_WINDOW) + " сек\n"
            "│ 🚫 Варнов до блока: " + str(MAX_WARNINGS) + "\n"
            "│\n"
            "│ Ловит: текст, стикеры, фото,\n"
            "│ видео, голосовые, файлы, /start\n"
            "╰────────────"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=warns_menu())
        return

    if data == "antispam_toggle":
        if not is_adm:
            return
        ANTISPAM_ENABLED = not ANTISPAM_ENABLED
        anti = "🟢 ВКЛ" if ANTISPAM_ENABLED else "🔴 ВЫКЛ"
        text = (
            "╭─ ⚠️ *Антиспам*\n│\n"
            "│ 🛡 Статус: " + anti + "\n"
            "│ 📊 Лимит: " + str(SPAM_LIMIT) + " сообщений / " + str(SPAM_WINDOW) + " сек\n"
            "│ 🚫 Варнов до блока: " + str(MAX_WARNINGS) + "\n"
            "│\n"
            "│ Ловит: текст, стикеры, фото,\n"
            "│ видео, голосовые, файлы, /start\n"
            "╰────────────"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=warns_menu())
        return

    if data == "adm_warns_list":
        if not is_adm:
            return
        if not WARNINGS:
            await query.edit_message_text("⚠️ Нет варнов.", reply_markup=warns_menu())
            return
        text = "⚠️ *Варны:*\n\n"
        keyboard = []
        for uid, cnt in WARNINGS.items():
            u = USERS.get(uid, {})
            text += "• @" + (u.get("username") or str(uid)) + " — " + str(cnt) + "/" + str(MAX_WARNINGS) + "\n"
            keyboard.append([InlineKeyboardButton("✅ @" + (u.get("username") or str(uid)), callback_data="reset_warn_" + str(uid))])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="adm_warns")])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "adm_broadcast":
        if not is_adm:
            return
        await query.edit_message_text("📨 *Рассылка:*", parse_mode="Markdown", reply_markup=broadcast_menu())
        return

    if data == "bc_all":
        if not is_adm:
            return
        BROADCAST_MODE[user_id] = True
        await query.edit_message_text("📢 Отправь текст для ВСЕХ:", reply_markup=back_admin())
        return

    if data == "bc_one":
        if not is_adm:
            return
        BROADCAST_TARGET[user_id] = True
        await query.edit_message_text("👤 Отправь ID или @username:", reply_markup=back_admin())
        return

    if data == "adm_blocks":
        if not is_adm:
            return
        if not BLOCKED:
            await query.edit_message_text("🚫 Пусто.", reply_markup=admin_menu())
            return
        text = "🚫 *Заблокированные:*\n\n"
        keyboard = []
        for uid in BLOCKED.keys():
            u = USERS.get(uid, {})
            text += "• @" + (u.get("username") or str(uid)) + "\n"
            keyboard.append([InlineKeyboardButton("✅ @" + (u.get("username") or str(uid)), callback_data="unblock_" + str(uid))])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "adm_promos":
        if not is_adm:
            return
        text = "🎟 *Промокоды:*\n\n"
        if PROMOCODES:
            for code, info in PROMOCODES.items():
                text += "• `" + code + "` — " + str(info["amount"]) + " (" + str(info["uses"]) + ")\n"
        else:
            text += "Пусто."
        keyboard = [
            [InlineKeyboardButton("➕ Создать", callback_data="create_promo")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "create_promo":
        if not is_adm:
            return
        context.user_data["create_promo"] = True