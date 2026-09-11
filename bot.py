# -*- coding: utf-8 -*-
"""
🔍 SquidHub Bot v5.0 — Telegram-бот с расширенным функционалом
Владелец: @zxcelite
"""

import logging
import re
import requests
import random
import string
import socket
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ═══════════════════════════════════════════════
#  НАСТРОЙКИ
# ═══════════════════════════════════════════════

TELEGRAM_TOKEN = "8476291431:AAElHgmZT92_GIBIchbnQ3AxCxu98HEQjx4"
OWNER_ID = 1100862483

ALLOWED_USERNAMES = ["zxcelite"]
BLOCKED_USERS = {}
PENDING_REQUESTS = {}
GLOBAL_BLOCK = False

# Новая настройка: пересылать ли тебе сообщения пользователей
FORWARD_MESSAGES = True

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
#  УНИКАЛЬНЫЕ ШАБЛОНЫ
# ═══════════════════════════════════════════════

GREETINGS = [
    "🛸 *SquidHub на связи*\n\nВыбери, что хочешь проверить:",
    "⚡ *Система активна*\n\nЧто будем пробивать сегодня?",
    "🔮 *Готов к работе*\n\nВыбери инструмент:",
    "🎯 *SquidHub Bot*\n\nКуда направим запрос?",
    "🧠 *Все инструменты под рукой*\n\nВыбирай:",
]

DENY_MESSAGES = [
    "⛔ *Доступ заблокирован администратором*",
    "🚫 *Админ приостановил твой доступ*",
    "🔒 *Бот закрыт для тебя. Обратись к владельцу*",
]

GLOBAL_DENY = [
    "⛔ *Бот временно выключен администратором*\n\nЗаходи позже",
    "🔒 *Технический перерыв*\n\nАдмин скоро вернёт доступ",
    "⚠️ *SquidHub остановлен*\n\nОжидай включения",
]

WAIT_MESSAGES = [
    "📨 *Заявка улетела админу*\n\nЖди вердикта",
    "⏳ *Запрос отправлен*\n\nАдмин скоро ответит",
    "✉️ *Заявка на рассмотрении*\n\nНе спамь, жди",
]

def random_greeting():
    return random.choice(GREETINGS)

def random_deny():
    return random.choice(DENY_MESSAGES)

def random_global_deny():
    return random.choice(GLOBAL_DENY)

def random_wait():
    return random.choice(WAIT_MESSAGES)

# ═══════════════════════════════════════════════
#  ПРОВЕРКИ
# ═══════════════════════════════════════════════

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def is_allowed(username: str) -> bool:
    if not username:
        return False
    return username.lower() in [u.lower() for u in ALLOWED_USERNAMES]

def is_blocked(username: str) -> bool:
    if not username:
        return False
    return username.lower() in [u.lower() for u in BLOCKED_USERS.keys()]

# ═══════════════════════════════════════════════
#  ФУНКЦИИ ПРОБИВА
# ═══════════════════════════════════════════════

def get_phone_info(phone: str) -> dict:
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
            "valid": phonenumbers.is_valid_number(parsed),
        }
    except Exception as e:
        return {"error": str(e)}


def get_telegram_info(username: str) -> dict:
    try:
        resp = requests.get(f"https://t.me/{username}", timeout=5)
        if resp.status_code == 200:
            title = re.search(r"<title>(.*?)</title>", resp.text)
            title_text = title.group(1) if title else "Неизвестно"
            return {
                "username": username,
                "exists": True,
                "title": title_text,
                "url": f"https://t.me/{username}",
            }
        return {"username": username, "exists": False}
    except Exception:
        return {"error": "Не удалось проверить"}


def get_ip_info(ip: str) -> dict:
    try:
        url = (
            f"http://ip-api.com/json/{ip}"
            f"?fields=status,message,country,city,region,isp,lat,lon,org,as"
        )
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json()
        return {"error": "IP не найден"}
    except Exception:
        return {"error": "Ошибка запроса"}


def check_email_leaks(email: str) -> dict:
    try:
        resp = requests.get(
            f"https://api.xposedornot.com/v1/check-email/{email}",
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            breaches = data.get("breaches", [])
            return {"email": email, "breaches": breaches, "count": len(breaches)}
        return {"email": email, "breaches": [], "count": 0}
    except Exception as e:
        return {"error": str(e)}


def get_domain_info(domain: str) -> dict:
    try:
        ip = socket.gethostbyname(domain)
        return {"domain": domain, "ip": ip, "resolved": True}
    except Exception as e:
        return {"error": f"Домен не резолвится: {e}"}


def generate_password(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}"
    return "".join(random.choice(chars) for _ in range(length))


def generate_nickname() -> str:
    adjectives = ["Dark", "Neo", "Cyber", "Ghost", "Iron", "Silver", "Crimson", "Shadow", "Frost", "Blaze"]
    nouns = ["Wolf", "Fox", "Raven", "Dragon", "Tiger", "Hawk", "Bear", "Lynx", "Cobra", "Phoenix"]
    return f"{random.choice(adjectives)}{random.choice(nouns)}{random.randint(10, 999)}"


def get_random_fact() -> str:
    facts = [
        "🐙 У осьминога три сердца и голубая кровь.",
        "🍯 Мёд никогда не портится — археологи нашли съедобный мёд в гробницах Египта.",
        "🌌 В космосе нельзя плакать — слёзы не текут, а собираются в шарик.",
        "🐌 У улитки около 25 000 зубов.",
        "⚡ Молния в 5 раз горячее поверхности Солнца.",
        "🧠 Мозг тратит 20% всей энергии тела.",
        "🦈 Акулы старше деревьев — они появились 400 млн лет назад.",
        "🌍 Земля — единственная планета, названная не в честь бога.",
    ]
    return random.choice(facts)

# ═══════════════════════════════════════════════
#  КЛАВИАТУРЫ
# ═══════════════════════════════════════════════

def back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")]
    ])


def main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📞 Проверить номер", callback_data="menu_phone")],
        [InlineKeyboardButton("👤 Проверить юзернейм", callback_data="menu_username")],
        [InlineKeyboardButton("🌐 Проверить IP", callback_data="menu_ip")],
        [InlineKeyboardButton("📧 Проверить email", callback_data="menu_email")],
        [InlineKeyboardButton("🔍 Whois домена", callback_data="menu_domain")],
        [InlineKeyboardButton("🎲 Инструменты", callback_data="menu_tools")],
    ]
    return InlineKeyboardMarkup(keyboard)


def owner_menu() -> InlineKeyboardMarkup:
    global_status = "🔴 ВЫКЛ" if GLOBAL_BLOCK else "🟢 ВКЛ"
    forward_status = "🔔 ВКЛ" if FORWARD_MESSAGES else "🔕 ВЫКЛ"
    keyboard = [
        [InlineKeyboardButton("📞 Проверить номер", callback_data="menu_phone")],
        [InlineKeyboardButton("👤 Проверить юзернейм", callback_data="menu_username")],
        [InlineKeyboardButton("🌐 Проверить IP", callback_data="menu_ip")],
        [InlineKeyboardButton("📧 Проверить email", callback_data="menu_email")],
        [InlineKeyboardButton("🔍 Whois домена", callback_data="menu_domain")],
        [InlineKeyboardButton("🎲 Инструменты", callback_data="menu_tools")],
        [InlineKeyboardButton(f"🌐 Глобальный доступ: {global_status}", callback_data="global_toggle")],
        [InlineKeyboardButton(f"🔔 Уведомления о юзерах: {forward_status}", callback_data="forward_toggle")],
        [InlineKeyboardButton("👥 Список пользователей", callback_data="list_users")],
    ]
    return InlineKeyboardMarkup(keyboard)


def tools_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔑 Генератор пароля", callback_data="tool_password")],
        [InlineKeyboardButton("🎭 Генератор ника", callback_data="tool_nickname")],
        [InlineKeyboardButton("💡 Случайный факт", callback_data="tool_fact")],
        [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def approval_buttons(username: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{username}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"deny_{username}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def user_manage_buttons(username: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(f"🚫 Заблокировать @{username}", callback_data=f"block_{username}")],
        [InlineKeyboardButton(f"✅ Разблокировать @{username}", callback_data=f"unblock_{username}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ═══════════════════════════════════════════════
#  /start
# ═══════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username

    if not username:
        await update.message.reply_text(
            "❌ *Нет юзернейма в Telegram*\n\n"
            "Установи его в настройках и напиши /start снова.",
            parse_mode="Markdown",
        )
        return

    if is_owner(user_id):
        await update.message.reply_text(
            "👑 *Панель владельца*\n\nВыбери действие:",
            parse_mode="Markdown",
            reply_markup=owner_menu(),
        )
        return

    if GLOBAL_BLOCK:
        await update.message.reply_text(random_global_deny(), parse_mode="Markdown")
        return

    if is_blocked(username):
        await update.message.reply_text(random_deny(), parse_mode="Markdown")
        return

    if is_allowed(username):
        await update.message.reply_text(random_greeting(), parse_mode="Markdown", reply_markup=main_menu())
        return

    if username.lower() in [u.lower() for u in PENDING_REQUESTS.keys()]:
        await update.message.reply_text("⏳ *Заявка уже на рассмотрении*\n\nНе спамь.", parse_mode="Markdown")
        return

    PENDING_REQUESTS[username] = user_id
    await update.message.reply_text(random_wait(), parse_mode="Markdown")
    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=(
            f"🔔 *Новая заявка*\n\n"
            f"👤 @{username}\n"
            f"🆔 `{user_id}`"
        ),
        parse_mode="Markdown",
        reply_markup=approval_buttons(username),
    )

# ═══════════════════════════════════════════════
#  КНОПКИ
# ═══════════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GLOBAL_BLOCK, FORWARD_MESSAGES
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username

    # ─── Одобрить / отклонить ───
    if data.startswith("approve_") or data.startswith("deny_"):
        if not is_owner(user_id):
            return
        action, target = data.split("_", 1)
        found_key = None
        for k in PENDING_REQUESTS.keys():
            if k.lower() == target.lower():
                found_key = k
                break
        if not found_key:
            await query.edit_message_text(f"❌ Заявка @{target} не найдена.")
            return
        target_id = PENDING_REQUESTS.pop(found_key)
        if action == "approve":
            ALLOWED_USERNAMES.append(found_key)
            await query.edit_message_text(f"✅ *@{found_key} одобрен*", parse_mode="Markdown")
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text="✅ *Доступ одобрен!*\n\nОтправь /start.",
                    parse_mode="Markdown",
                )
            except:
                pass
        else:
            await query.edit_message_text(f"❌ *@{found_key} отклонён*", parse_mode="Markdown")
            try:
                await context.bot.send_message(chat_id=target_id, text="❌ Заявка отклонена.")
            except:
                pass
        return

    # ─── Глобальная блокировка ───
    if data == "global_toggle":
        if not is_owner(user_id):
            return
        GLOBAL_BLOCK = not GLOBAL_BLOCK
        if GLOBAL_BLOCK:
            for uname in ALLOWED_USERNAMES:
                if uname.lower() == "zxcelite":
                    continue
                for source in [PENDING_REQUESTS, BLOCKED_USERS]:
                    for k, v in source.items():
                        if k.lower() == uname.lower():
                            try:
                                await context.bot.send_message(
                                    chat_id=v,
                                    text="⛔ *Админ приостановил бота*\n\nЖди включения.",
                                    parse_mode="Markdown",
                                )
                            except:
                                pass
            await query.edit_message_text(
                "🔴 *Бот выключен для всех*\n\nНажми кнопку снова, чтобы включить.",
                parse_mode="Markdown",
                reply_markup=owner_menu(),
            )
        else:
            await query.edit_message_text(
                "🟢 *Бот включён для всех*",
                parse_mode="Markdown",
                reply_markup=owner_menu(),
            )
        return

    # ─── НОВОЕ: Переключение уведомлений о сообщениях юзеров ───
    if data == "forward_toggle":
        if not is_owner(user_id):
            return
        FORWARD_MESSAGES = not FORWARD_MESSAGES
        status = "🔔 *ВКЛЮЧЕНЫ*" if FORWARD_MESSAGES else "🔕 *ВЫКЛЮЧЕНЫ*"
        await query.edit_message_text(
            f"📬 *Уведомления о сообщениях пользователей: {status}*\n\n"
            f"{'Теперь ты будешь получать все сообщения от юзеров.' if FORWARD_MESSAGES else 'Теперь сообщения юзеров НЕ будут тебе приходить.'}",
            parse_mode="Markdown",
            reply_markup=owner_menu(),
        )
        return

    # ─── Список пользователей ───
    if data == "list_users":
        if not is_owner(user_id):
            return
        if not ALLOWED_USERNAMES:
            await query.edit_message_text("📋 Список пуст.", reply_markup=owner_menu())
            return
        text = "📋 *Одобренные:*\n\n"
        for i, uname in enumerate(ALLOWED_USERNAMES, 1):
            status = "🚫" if is_blocked(uname) else "✅"
            text += f"{i}. {status} @{uname}\n"
        keyboard = []
        for uname in ALLOWED_USERNAMES:
            if uname.lower() == "zxcelite":
                continue
            status = "🚫" if is_blocked(uname) else "✅"
            keyboard.append([InlineKeyboardButton(f"{status} @{uname}", callback_data=f"manage_{uname}")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ─── Управление юзером ───
    if data.startswith("manage_"):
        if not is_owner(user_id):
            return
        target = data.split("_", 1)[1]
        await query.edit_message_text(
            f"⚙️ *Управление @{target}*\n\n"
            f"Статус: {'🚫 Заблокирован' if is_blocked(target) else '✅ Активен'}",
            parse_mode="Markdown",
            reply_markup=user_manage_buttons(target),
        )
        return

    if data.startswith("block_"):
        if not is_owner(user_id):
            return
        target = data.split("_", 1)[1]
        if is_blocked(target):
            await query.edit_message_text(f"ℹ️ @{target} уже заблокирован.", reply_markup=owner_menu())
            return
        target_id = None
        for source in [PENDING_REQUESTS, BLOCKED_USERS]:
            for k, v in source.items():
                if k.lower() == target.lower():
                    target_id = v
                    break
        BLOCKED_USERS[target] = target_id
        ALLOWED_USERNAMES[:] = [u for u in ALLOWED_USERNAMES if u.lower() != target.lower()]
        await query.edit_message_text(f"🚫 *@{target} заблокирован*", parse_mode="Markdown", reply_markup=owner_menu())
        if target_id:
            try:
                await context.bot.send_message(chat_id=target_id, text=random_deny(), parse_mode="Markdown")
            except:
                pass
        return

    if data.startswith("unblock_"):
        if not is_owner(user_id):
            return
        target = data.split("_", 1)[1]
        if not is_blocked(target):
            await query.edit_message_text(f"ℹ️ @{target} не заблокирован.", reply_markup=owner_menu())
            return
        target_id = BLOCKED_USERS.pop(target, None)
        if target.lower() not in [u.lower() for u in ALLOWED_USERNAMES]:
            ALLOWED_USERNAMES.append(target)
        await query.edit_message_text(f"✅ *@{target} разблокирован*", parse_mode="Markdown", reply_markup=owner_menu())
        if target_id:
            try:
                await context.bot.send_message(chat_id=target_id, text="✅ Доступ восстановлен. /start", parse_mode="Markdown")
            except:
                pass
        return

    # ─── Назад ───
    if data == "back_to_menu":
        if is_owner(user_id):
            await query.edit_message_text("👑 *Панель владельца*\n\nВыбери:", parse_mode="Markdown", reply_markup=owner_menu())
        else:
            await query.edit_message_text(random_greeting(), parse_mode="Markdown", reply_markup=main_menu())
        return

    # ─── Меню пробива ───
    if data == "menu_phone":
        await query.edit_message_text("📞 *Проверка номера*\n\nОтправь: `+380XXXXXXXXX`", parse_mode="Markdown", reply_markup=back_button())
    elif data == "menu_username":
        await query.edit_message_text("👤 *Проверка юзернейма*\n\nОтправь: `@username`", parse_mode="Markdown", reply_markup=back_button())
    elif data == "menu_ip":
        await query.edit_message_text("🌐 *Проверка IP*\n\nОтправь: `8.8.8.8`", parse_mode="Markdown", reply_markup=back_button())
    elif data == "menu_email":
        await query.edit_message_text("📧 *Проверка email*\n\nОтправь: `example@gmail.com`", parse_mode="Markdown", reply_markup=back_button())
    elif data == "menu_domain":
        await query.edit_message_text("🔍 *Whois домена*\n\nОтправь: `google.com`", parse_mode="Markdown", reply_markup=back_button())
    elif data == "menu_tools":
        await query.edit_message_text("🎲 *Инструменты*\n\nВыбери:", parse_mode="Markdown", reply_markup=tools_menu())

    # ─── Инструменты ───
    elif data == "tool_password":
        pwd = generate_password(20)
        await query.edit_message_text(f"🔑 *Твой пароль:*\n\n`{pwd}`\n\n_Скопируй и сохрани._", parse_mode="Markdown", reply_markup=tools_menu())
    elif data == "tool_nickname":
        nick = generate_nickname()
        await query.edit_message_text(f"🎭 *Твой ник:*\n\n`{nick}`", parse_mode="Markdown", reply_markup=tools_menu())
    elif data == "tool_fact":
        fact = get_random_fact()
        await query.edit_message_text(f"💡 *Факт:*\n\n{fact}", parse_mode="Markdown", reply_markup=tools_menu())

# ═══════════════════════════════════════════════
#  СООБЩЕНИЯ
# ═══════════════════════════════════════════════

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global FORWARD_MESSAGES
    user_id = update.effective_user.id
    username = update.effective_user.username

    if GLOBAL_BLOCK and not is_owner(user_id):
        await update.message.reply_text(random_global_deny(), parse_mode="Markdown")
        return
    if is_blocked(username) and not is_owner(user_id):
        await update.message.reply_text(random_deny(), parse_mode="Markdown")
        return
    if not is_owner(user_id) and not is_allowed(username):
        await update.message.reply_text("⛔ *Доступ запрещён*\n\nОтправь /start.", parse_mode="Markdown")
        return

    try:
        text = update.message.text.strip()
        logger.info(f"@{username}: {text}")

        # ─── НОВОЕ: Пересылка сообщений владельцу ───
        if FORWARD_MESSAGES and not is_owner(user_id):
            try:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=(
                        f"📬 *Сообщение от пользователя*\n\n"
                        f"👤 @{username}\n"
                        f"🆔 `{user_id}`\n\n"
                        f"💬 {text}"
                    ),
                    parse_mode="Markdown",
                )
            except:
                pass

        # ─── Номер ───
        if re.match(r"^\+?\d{10,15}$", text):
            info = get_phone_info(text)
            if "error" in info:
                await update.message.reply_text(f"❌ {info['error']}", reply_markup=back_button())
                return
            reply = (
                f"📞 *Результат*\n\n"
                f"🔹 *Номер:* `{info['phone']}`\n"
                f"🌍 *Страна:* {info['country']}\n"
                f"📡 *Оператор:* {info['operator']}\n"
                f"⏳ *Таймзона:* {info['timezone']}\n"
                f"✅ *Валидный:* {'Да' if info['valid'] else 'Нет'}"
            )
            await update.message.reply_text(reply, parse_mode="Markdown", reply_markup=back_button())

        # ─── Email ───
        elif re.match(r"^[^@]+@[^@]+\.[^@]+$", text):
            info = check_email_leaks(text)
            if "error" in info:
                await update.message.reply_text(f"❌ {info['error']}", reply_markup=back_button())
                return
            if info["count"] > 0:
                breaches_list = "\n".join([f"• `{b}`" for b in info["breaches"][:10]])
                reply = (
                    f"📧 *Email проверен*\n\n"
                    f"🔹 *Email:* `{info['email']}`\n"
                    f"⚠️ *Найден в утечках:* {info['count']}\n\n"
                    f"{breaches_list}"
                )
            else:
                reply = f"📧 *Email:* `{info['email']}`\n\n✅ Утечек не найдено."
            await update.message.reply_text(reply, parse_mode="Markdown", reply_markup=back_button())

        # ─── Юзернейм ───
        elif text.startswith("@"):
            info = get_telegram_info(text[1:])
            if "error" in info:
                await update.message.reply_text(f"❌ {info['error']}", reply_markup=back_button())
                return
            if info.get("exists"):
                reply = (
                    f"👤 *Результат*\n\n"
                    f"✅ *Юзернейм:* @{info['username']}\n"
                    f"🔗 *Ссылка:* {info['url']}\n"
                    f"📝 *Название:* {info.get('title', 'Неизвестно')}"
                )
                await update.message.reply_text(reply, parse_mode="Markdown", reply_markup=back_button())
            else:
                await update.message.reply_text("❌ Юзернейм не существует.", reply_markup=back_button())

        # ─── IP ───
        elif re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", text):
            info = get_ip_info(text)
            if "error" in info:
                await update.message.reply_text(f"❌ {info['error']}", reply_markup=back_button())
                return
            if info.get("status") == "fail":
                await update.message.reply_text(f"❌ {info.get('message', 'Ошибка')}", reply_markup=back_button())
                return
            reply = (
                f"🌐 *Результат*\n\n"
                f"🔹 *IP:* `{text}`\n"
                f"📍 *Страна:* {info.get('country', '—')}\n"
                f"🏙️ *Город:* {info.get('city', '—')}\n"
                f"📌 *Регион:* {info.get('region', '—')}\n"
                f"📡 *Провайдер:* {info.get('isp', '—')}\n"
                f"🗺️ *Координаты:* {info.get('lat', '—')}, {info.get('lon', '—')}"
            )
            await update.message.reply_text(reply, parse_mode="Markdown", reply_markup=back_button())

        # ─── Домен ───
        elif "." in text and not text.startswith("@") and " " not in text:
            info = get_domain_info(text)
            if "error" in info:
                await update.message.reply_text(f"❌ {info['error']}", reply_markup=back_button())
                return
            reply = (
                f"🔍 *Домен*\n\n"
                f"🔹 *Домен:* `{info['domain']}`\n"
                f"🌐 *IP:* `{info['ip']}`\n"
                f"✅ *Резолвится:* Да"
            )
            await update.message.reply_text(reply, parse_mode="Markdown", reply_markup=back_button())

        else:
            await update.message.reply_text("❌ *Не распознано*\n\nВыбери из меню:", parse_mode="Markdown", reply_markup=main_menu())

    except Exception as e:
        await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")
        logger.error(f"Краш: {e}")

# ═══════════════════════════════════════════════
#  ЗАПУСК
# ═══════════════════════════════════════════════

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("🤖 SquidHub Bot v5.0 запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()