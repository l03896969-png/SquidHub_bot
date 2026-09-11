# -*- coding: utf-8 -*-
"""
🔍 SquidHub Bot — Telegram-бот для проверки открытых данных
Владелец: @zxcelite
Версия: 3.0
"""

import logging
import re
import requests
import phonenumbers
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

# ═══════════════════════════════════════════════
#  НАСТРОЙКИ
# ═══════════════════════════════════════════════

TELEGRAM_TOKEN = "8476291431:AAElHgmZT92_GIBIchbnQ3AxCxu98HEQjx4"
OWNER_ID = 1100862483

# Белый список (одобренные юзернеймы)
ALLOWED_USERNAMES = [
    "zxcelite",  # ← ТЫ
]

# Временно заблокированные {username: user_id}
BLOCKED_USERS = {}

# Заявки на одобрение {username: user_id}
PENDING_REQUESTS = {}

# Глобальная блокировка
GLOBAL_BLOCK = False

# ═══════════════════════════════════════════════
#  ЛОГИРОВАНИЕ
# ═══════════════════════════════════════════════

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

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

# ═══════════════════════════════════════════════
#  КЛАВИАТУРЫ
# ═══════════════════════════════════════════════

def main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📞 Проверить номер", callback_data="menu_phone")],
        [InlineKeyboardButton("👤 Проверить юзернейм", callback_data="menu_username")],
        [InlineKeyboardButton("🌐 Проверить IP", callback_data="menu_ip")],
    ]
    return InlineKeyboardMarkup(keyboard)


def owner_menu() -> InlineKeyboardMarkup:
    status = "🔴 ВЫКЛЮЧЕН" if GLOBAL_BLOCK else "🟢 ВКЛЮЧЕН"
    keyboard = [
        [InlineKeyboardButton("📞 Проверить номер", callback_data="menu_phone")],
        [InlineKeyboardButton("👤 Проверить юзернейм", callback_data="menu_username")],
        [InlineKeyboardButton("🌐 Проверить IP", callback_data="menu_ip")],
        [InlineKeyboardButton(f"🌐 Глобальный доступ: {status}", callback_data="global_toggle")],
        [InlineKeyboardButton("👥 Список пользователей", callback_data="list_users")],
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
            "❌ У вас не установлен юзернейм в Telegram.\n"
            "Установите его в настройках и попробуйте снова."
        )
        return

    if is_owner(user_id):
        await update.message.reply_text(
            "👑 *Панель владельца*\n\nВыберите действие:",
            parse_mode="Markdown",
            reply_markup=owner_menu(),
        )
        return

    if GLOBAL_BLOCK:
        await update.message.reply_text(
            "⛔ *Бот временно приостановлен администратором.*\n\nПопробуйте позже."
        )
        return

    if is_blocked(username):
        await update.message.reply_text(
            "🚫 *Ваш доступ временно приостановлен администратором.*\n\n"
            "Обратитесь к владельцу бота."
        )
        return

    if is_allowed(username):
        await update.message.reply_text(
            "🔍 *SquidHub Bot*\n\nВыберите действие:",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
        return

    if username.lower() in [u.lower() for u in PENDING_REQUESTS.keys()]:
        await update.message.reply_text("⏳ Ваш запрос уже отправлен на одобрение.\nОжидайте.")
        return

    PENDING_REQUESTS[username] = user_id
    await update.message.reply_text(
        "📨 *Запрос отправлен!*\n\nОжидайте одобрения владельца бота.",
        parse_mode="Markdown",
    )
    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=(
            f"🔔 *Новый запрос доступа*\n\n"
            f"👤 @{username}\n"
            f"🆔 ID: `{user_id}`"
        ),
        parse_mode="Markdown",
        reply_markup=approval_buttons(username),
    )

# ═══════════════════════════════════════════════
#  КНОПКИ
# ═══════════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GLOBAL_BLOCK
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id

    # ─── Одобрение / отклонение ───
    if data.startswith("approve_") or data.startswith("deny_"):
        if not is_owner(user_id):
            await query.edit_message_text("⛔ Только владелец.")
            return

        action, target = data.split("_", 1)
        found_key = None
        for k in PENDING_REQUESTS.keys():
            if k.lower() == target.lower():
                found_key = k
                break

        if not found_key:
            await query.edit_message_text(f"❌ Заявка от @{target} не найдена.")
            return

        target_id = PENDING_REQUESTS.pop(found_key)

        if action == "approve":
            ALLOWED_USERNAMES.append(found_key)
            await query.edit_message_text(f"✅ *@{found_key} одобрен.*", parse_mode="Markdown")
            await context.bot.send_message(
                chat_id=target_id,
                text="✅ *Ваш запрос одобрен!*\n\nОтправьте /start, чтобы начать.",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text(f"❌ *@{found_key} отклонён.*", parse_mode="Markdown")
            await context.bot.send_message(
                chat_id=target_id, text="❌ Ваш запрос отклонён владельцем бота."
            )
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
                                    text="⛔ *Администратор временно приостановил работу бота.*\n\nПопробуйте позже.",
                                    parse_mode="Markdown",
                                )
                            except:
                                pass
            await query.edit_message_text(
                "🔴 *Бот выключен для всех пользователей.*\n\nНажмите снова, чтобы включить.",
                parse_mode="Markdown",
                reply_markup=owner_menu(),
            )
        else:
            await query.edit_message_text(
                "🟢 *Бот снова включён для всех.*",
                parse_mode="Markdown",
                reply_markup=owner_menu(),
            )
        return

    # ─── Список пользователей ───
    if data == "list_users":
        if not is_owner(user_id):
            return

        if not ALLOWED_USERNAMES:
            await query.edit_message_text(
                "📋 *Список пуст.*",
                parse_mode="Markdown",
                reply_markup=owner_menu(),
            )
            return

        text = "📋 *Одобренные пользователи:*\n\n"
        for i, uname in enumerate(ALLOWED_USERNAMES, 1):
            status = "🚫" if is_blocked(uname) else "✅"
            text += f"{i}. {status} @{uname}\n"

        keyboard = []
        for uname in ALLOWED_USERNAMES:
            if uname.lower() == "zxcelite":
                continue
            status = "🚫" if is_blocked(uname) else "✅"
            keyboard.append([
                InlineKeyboardButton(f"{status} @{uname}", callback_data=f"manage_{uname}")
            ])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")])

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
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

    # ─── Заблокировать ───
    if data.startswith("block_"):
        if not is_owner(user_id):
            return

        target = data.split("_", 1)[1]

        if is_blocked(target):
            await query.edit_message_text(f"ℹ️ @{target} уже заблокирован.")
            return

        target_id = None
        for source in [PENDING_REQUESTS, BLOCKED_USERS]:
            for k, v in source.items():
                if k.lower() == target.lower():
                    target_id = v
                    break

        BLOCKED_USERS[target] = target_id
        ALLOWED_USERNAMES[:] = [u for u in ALLOWED_USERNAMES if u.lower() != target.lower()]

        await query.edit_message_text(
            f"🚫 *@{target} заблокирован.*",
            parse_mode="Markdown",
            reply_markup=owner_menu(),
        )

        if target_id:
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text="🚫 *Ваш доступ временно приостановлен администратором.*\n\n"
                         "Обратитесь к владельцу бота.",
                    parse_mode="Markdown",
                )
            except:
                pass
        return

    # ─── Разблокировать ───
    if data.startswith("unblock_"):
        if not is_owner(user_id):
            return

        target = data.split("_", 1)[1]

        if not is_blocked(target):
            await query.edit_message_text(f"ℹ️ @{target} не заблокирован.")
            return

        target_id = BLOCKED_USERS.pop(target, None)
        if target.lower() not in [u.lower() for u in ALLOWED_USERNAMES]:
            ALLOWED_USERNAMES.append(target)

        await query.edit_message_text(
            f"✅ *@{target} разблокирован.*",
            parse_mode="Markdown",
            reply_markup=owner_menu(),
        )

        if target_id:
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text="✅ *Ваш доступ восстановлен!*\n\nОтправьте /start.",
                    parse_mode="Markdown",
                )
            except:
                pass
        return

    # ─── Назад ───
    if data == "back_to_menu":
        if is_owner(user_id):
            await query.edit_message_text(
                "👑 *Панель владельца*\n\nВыберите действие:",
                parse_mode="Markdown",
                reply_markup=owner_menu(),
            )
        return

    # ─── Меню пробива ───
    if data == "menu_phone":
        await query.edit_message_text(
            "📞 *Проверка номера*\n\nОтправьте номер:\n`+380XXXXXXXXX`",
            parse_mode="Markdown",
        )
    elif data == "menu_username":
        await query.edit_message_text(
            "👤 *Проверка юзернейма*\n\nОтправьте:\n`@username`",
            parse_mode="Markdown",
        )
    elif data == "menu_ip":
        await query.edit_message_text(
            "🌐 *Проверка IP*\n\nОтправьте:\n`8.8.8.8`",
            parse_mode="Markdown",
        )

# ═══════════════════════════════════════════════
#  СООБЩЕНИЯ
# ═══════════════════════════════════════════════

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username

    if GLOBAL_BLOCK and not is_owner(user_id):
        await update.message.reply_text(
            "⛔ *Бот временно приостановлен администратором.*\n\nПопробуйте позже.",
            parse_mode="Markdown",
        )
        return

    if is_blocked(username) and not is_owner(user_id):
        await update.message.reply_text(
            "🚫 *Ваш доступ временно приостановлен администратором.*",
            parse_mode="Markdown",
        )
        return

    if not is_owner(user_id) and not is_allowed(username):
        await update.message.reply_text(
            "⛔ *Доступ запрещён.*\n\nОтправьте /start для запроса доступа.",
            parse_mode="Markdown",
        )
        return

    try:
        text = update.message.text.strip()
        logger.info(f"Запрос от @{username} ({user_id}): {text}")

        if re.match(r"^\+?\d{10,15}$", text):
            info = get_phone_info(text)
            if "error" in info:
                await update.message.reply_text(f"❌ {info['error']}")
                return
            reply = (
                f"📞 *Результат проверки номера*\n\n"
                f"🔹 *Номер:* `{info['phone']}`\n"
                f"🌍 *Страна:* {info['country']}\n"
                f"📡 *Оператор:* {info['operator']}\n"
                f"⏳ *Таймзона:* {info['timezone']}\n"
                f"✅ *Валидный:* {'Да' if info['valid'] else 'Нет'}"
            )
            await update.message.reply_text(reply, parse_mode="Markdown", reply_markup=main_menu())

        elif text.startswith("@"):
            info = get_telegram_info(text[1:])
            if "error" in info:
                await update.message.reply_text(f"❌ {info['error']}")
                return
            if info.get("exists"):
                reply = (
                    f"👤 *Результат проверки юзернейма*\n\n"
                    f"✅ *Юзернейм:* @{info['username']}\n"
                    f"🔗 *Ссылка:* {info['url']}\n"
                    f"📝 *Название:* {info.get('title', 'Неизвестно')}"
                )
                await update.message.reply_text(reply, parse_mode="Markdown", reply_markup=main_menu())
            else:
                await update.message.reply_text("❌ Такой юзернейм не существует.", reply_markup=main_menu())

        elif re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", text):
            info = get_ip_info(text)
            if "error" in info:
                await update.message.reply_text(f"❌ {info['error']}")
                return
            if info.get("status") == "fail":
                await update.message.reply_text(f"❌ {info.get('message', 'Ошибка')}")
                return
            reply = (
                f"🌐 *Результат проверки IP*\n\n"
                f"🔹 *IP:* `{text}`\n"
                f"📍 *Страна:* {info.get('country', 'Неизвестно')}\n"
                f"🏙️ *Город:* {info.get('city', 'Неизвестно')}\n"
                f"📌 *Регион:* {info.get('region', 'Неизвестно')}\n"
                f"📡 *Провайдер:* {info.get('isp', 'Неизвестно')}\n"
                f"🗺️ *Координаты:* {info.get('lat', '—')}, {info.get('lon', '—')}"
            )
            await update.message.reply_text(reply, parse_mode="Markdown", reply_markup=main_menu())

        else:
            await update.message.reply_text(
                "❌ *Не распознано.*\n\nВыберите действие:",
                parse_mode="Markdown",
                reply_markup=main_menu(),
            )

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

    logger.info("🤖 SquidHub Bot v3.0 запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()