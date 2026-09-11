# -*- coding: utf-8 -*-
import logging
import re
import requests
import random
import string
import socket
import os
import phonenumbers
import yt_dlp
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

ALLOWED_USERNAMES = ["zxcelite"]
BLOCKED_USERS = {}
PENDING_REQUESTS = {}
GLOBAL_BLOCK = False
FORWARD_MESSAGES = True

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

def random_greeting():
    return random.choice(GREETINGS)

def random_deny():
    return random.choice(DENY_MESSAGES)

def random_global_deny():
    return random.choice(GLOBAL_DENY)

def random_wait():
    return random.choice(WAIT_MESSAGES)

def is_owner(user_id):
    return user_id == OWNER_ID

def is_allowed(username):
    if not username:
        return False
    return username.lower() in [u.lower() for u in ALLOWED_USERNAMES]

def is_blocked(username):
    if not username:
        return False
    return username.lower() in [u.lower() for u in BLOCKED_USERS.keys()]

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
            "valid": phonenumbers.is_valid_number(parsed),
        }
    except Exception as e:
        return {"error": str(e)}

def get_telegram_info(username):
    try:
        resp = requests.get("https://t.me/" + username, timeout=5)
        if resp.status_code == 200:
            title = re.search(r"<title>(.*?)</title>", resp.text)
            title_text = title.group(1) if title else "Неизвестно"
            return {
                "username": username,
                "exists": True,
                "title": title_text,
                "url": "https://t.me/" + username,
            }
        return {"username": username, "exists": False}
    except Exception:
        return {"error": "Не удалось проверить"}

def get_ip_info(ip):
    try:
        url = "http://ip-api.com/json/" + ip + "?fields=status,message,country,city,region,isp,lat,lon,org,as"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json()
        return {"error": "IP не найден"}
    except Exception:
        return {"error": "Ошибка запроса"}

def check_email_leaks(email):
    try:
        resp = requests.get("https://api.xposedornot.com/v1/check-email/" + email, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            breaches = data.get("breaches", [])
            return {"email": email, "breaches": breaches, "count": len(breaches)}
        return {"email": email, "breaches": [], "count": 0}
    except Exception as e:
        return {"error": str(e)}

def get_domain_info(domain):
    try:
        ip = socket.gethostbyname(domain)
        return {"domain": domain, "ip": ip, "resolved": True}
    except Exception as e:
        return {"error": "Домен не резолвится: " + str(e)}

def generate_password(length=16):
    chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}"
    return "".join(random.choice(chars) for _ in range(length))

NICK_ADJECTIVES = [
    "Silent", "Dark", "Frost", "Crimson", "Shadow", "Iron", "Neon", "Wild",
    "Swift", "Bitter", "Golden", "Hollow", "Lucid", "Vivid", "Ancient", "Broken",
    "Calm", "Distant", "Electric", "Fading", "Gentle", "Hidden", "Lonely", "Mystic",
]

NICK_NOUNS = [
    "River", "Storm", "Wolf", "Hawk", "Ember", "Frost", "Vale", "Ridge",
    "Echo", "Drift", "Flame", "Glade", "Haven", "Knight", "Light", "Moon",
    "Night", "Ocean", "Pine", "Quest", "Rain", "Sage", "Thorn", "Wave",
]

NICK_SUFFIXES = ["", "x", "z", "ex", "ix", "on", "ar", "er", "is", "us"]

def generate_nickname():
    adj = random.choice(NICK_ADJECTIVES)
    noun = random.choice(NICK_NOUNS)
    suffix = random.choice(NICK_SUFFIXES)
    return adj + noun + suffix

def get_random_fact():
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

def search_song(query):
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "default_search": "ytsearch1",
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info("ytsearch1:" + query, download=False)
            if "entries" in info and info["entries"]:
                entry = info["entries"][0]
                return {
                    "title": entry.get("title", "Неизвестно"),
                    "url": entry.get("webpage_url", ""),
                    "duration": entry.get("duration", 0),
                    "uploader": entry.get("uploader", "Неизвестно"),
                }
            return {"error": "Песня не найдена"}
    except Exception as e:
        return {"error": "Ошибка поиска: " + str(e)}

def download_song(query, output_path="/tmp/song"):
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "default_search": "ytsearch1",
            "noplaylist": True,
            "format": "bestaudio/best",
            "outtmpl": output_path + ".%(ext)s",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info("ytsearch1:" + query, download=True)
            if "entries" in info and info["entries"]:
                entry = info["entries"][0]
                return {
                    "title": entry.get("title", "song"),
                    "filepath": output_path + ".mp3",
                    "duration": entry.get("duration", 0),
                    "uploader": entry.get("uploader", "Неизвестно"),
                }
            return {"error": "Песня не найдена"}
    except Exception as e:
        return {"error": "Ошибка скачивания: " + str(e)}

def back_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")]
    ])

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📞 Проверить номер", callback_data="menu_phone")],
        [InlineKeyboardButton("👤 Проверить юзернейм", callback_data="menu_username")],
        [InlineKeyboardButton("🌐 Проверить IP", callback_data="menu_ip")],
        [InlineKeyboardButton("📧 Проверить email", callback_data="menu_email")],
        [InlineKeyboardButton("🔍 Whois домена", callback_data="menu_domain")],
        [InlineKeyboardButton("🎲 Инструменты", callback_data="menu_tools")],
    ]
    return InlineKeyboardMarkup(keyboard)

def owner_menu():
    global_status = "🔴 ВЫКЛ" if GLOBAL_BLOCK else "🟢 ВКЛ"
    forward_status = "🔔 ВКЛ" if FORWARD_MESSAGES else "🔕 ВЫКЛ"
    keyboard = [
        [InlineKeyboardButton("📞 Проверить номер", callback_data="menu_phone")],
        [InlineKeyboardButton("👤 Проверить юзернейм", callback_data="menu_username")],
        [InlineKeyboardButton("🌐 Проверить IP", callback_data="menu_ip")],
        [InlineKeyboardButton("📧 Проверить email", callback_data="menu_email")],
        [InlineKeyboardButton("🔍 Whois домена", callback_data="menu_domain")],
        [InlineKeyboardButton("🎲 Инструменты", callback_data="menu_tools")],
        [InlineKeyboardButton("🌐 Глобальный доступ: " + global_status, callback_data="global_toggle")],
        [InlineKeyboardButton("🔔 Уведомления: " + forward_status, callback_data="forward_toggle")],
        [InlineKeyboardButton("👥 Список пользователей", callback_data="list_users")],
    ]
    return InlineKeyboardMarkup(keyboard)

def tools_menu():
    keyboard = [
        [InlineKeyboardButton("🔑 Генератор пароля", callback_data="tool_password")],
        [InlineKeyboardButton("🎭 Генератор ника", callback_data="tool_nickname")],
        [InlineKeyboardButton("💡 Случайный факт", callback_data="tool_fact")],
        [InlineKeyboardButton("🎵 Найти песню", callback_data="tool_music_search")],
        [InlineKeyboardButton("📥 Скачать и отправить", callback_data="tool_music_download")],
        [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

def approval_buttons(username):
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data="approve_" + username),
            InlineKeyboardButton("❌ Отклонить", callback_data="deny_" + username),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def user_manage_buttons(username):
    keyboard = [
        [InlineKeyboardButton("🚫 Заблокировать @" + username, callback_data="block_" + username)],
        [InlineKeyboardButton("✅ Разблокировать @" + username, callback_data="unblock_" + username)],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username

    if not username:
        await update.message.reply_text("❌ Нет юзернейма в Telegram\n\nУстанови его в настройках и напиши /start снова.")
        return

    if is_owner(user_id):
        await update.message.reply_text("👑 Панель владельца\n\nВыбери действие:", reply_markup=owner_menu())
        return

    if GLOBAL_BLOCK:
        await update.message.reply_text(random_global_deny())
        return

    if is_blocked(username):
        await update.message.reply_text(random_deny())
        return

    if is_allowed(username):
        await update.message.reply_text(random_greeting(), reply_markup=main_menu())
        return

    if username.lower() in [u.lower() for u in PENDING_REQUESTS.keys()]:
        await update.message.reply_text("⏳ Заявка уже на рассмотрении\n\nНе спамь.")
        return

    PENDING_REQUESTS[username] = user_id
    await update.message.reply_text(random_wait())
    await context.bot.send_message(
        chat_id=OWNER_ID,
        text="🔔 Новая заявка\n\n👤 @" + username + "\n🆔 " + str(user_id),
        reply_markup=approval_buttons(username),
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GLOBAL_BLOCK, FORWARD_MESSAGES
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username

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
            await query.edit_message_text("❌ Заявка @" + target + " не найдена.")
            return
        target_id = PENDING_REQUESTS.pop(found_key)
        if action == "approve":
            ALLOWED_USERNAMES.append(found_key)
            await query.edit_message_text("✅ @" + found_key + " одобрен")
            try:
                await context.bot.send_message(chat_id=target_id, text="✅ Доступ одобрен\n\nОтправь /start.")
            except Exception:
                pass
        else:
            await query.edit_message_text("❌ @" + found_key + " отклонён")
            try:
                await context.bot.send_message(chat_id=target_id, text="❌ Заявка отклонена.")
            except Exception:
                pass
        return

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
                                await context.bot.send_message(chat_id=v, text="⛔ Админ приостановил бота\n\nЖди включения.")
                            except Exception:
                                pass
            await query.edit_message_text("🔴 Бот выключен для всех\n\nНажми кнопку снова, чтобы включить.", reply_markup=owner_menu())
        else:
            await query.edit_message_text("🟢 Бот включён для всех", reply_markup=owner_menu())
        return

    if data == "forward_toggle":
        if not is_owner(user_id):
            return
        FORWARD_MESSAGES = not FORWARD_MESSAGES
        status = "ВКЛЮЧЕНЫ" if FORWARD_MESSAGES else "ВЫКЛЮЧЕНЫ"
        await query.edit_message_text("📬 Уведомления о сообщениях: " + status, reply_markup=owner_menu())
        return

    if data == "list_users":
        if not is_owner(user_id):
            return
        if not ALLOWED_USERNAMES:
            await query.edit_message_text("📋 Список пуст.", reply_markup=owner_menu())
            return
        text = "📋 Одобренные:\n\n"
        for i, uname in enumerate(ALLOWED_USERNAMES, 1):
            status = "🚫" if is_blocked(uname) else "✅"
            text += str(i) + ". " + status + " @" + uname + "\n"
        keyboard = []
        for uname in ALLOWED_USERNAMES:
            if uname.lower() == "zxcelite":
                continue
            status = "🚫" if is_blocked(uname) else "✅"
            keyboard.append([InlineKeyboardButton(status + " @" + uname, callback_data="manage_" + uname)])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("manage_"):
        if not is_owner(user_id):
            return
        target = data.split("_", 1)[1]
        status = "🚫 Заблокирован" if is_blocked(target) else "✅ Активен"
        await query.edit_message_text("⚙️ Управление @" + target + "\n\nСтатус: " + status, reply_markup=user_manage_buttons(target))
        return

    if data.startswith("block_"):
        if not is_owner(user_id):
            return
        target = data.split("_", 1)[1]
        if is_blocked(target):
            await query.edit_message_text("ℹ️ @" + target + " уже заблокирован.", reply_markup=owner_menu())
            return
        target_id = None
        for source in [PENDING_REQUESTS, BLOCKED_USERS]:
            for k, v in source.items():
                if k.lower() == target.lower():
                    target_id = v
                    break
        BLOCKED_USERS[target] = target_id
        ALLOWED_USERNAMES[:] = [u for u in ALLOWED_USERNAMES if u.lower() != target.lower()]
        await query.edit_message_text("🚫 @" + target + " заблокирован", reply_markup=owner_menu())
        if target_id:
            try:
                await context.bot.send_message(chat_id=target_id, text=random_deny())
            except Exception:
                pass
        return

    if data.startswith("unblock_"):
        if not is_owner(user_id):
            return
        target = data.split("_", 1)[1]
        if not is_blocked(target):
            await query.edit_message_text("ℹ️ @" + target + " не заблокирован.", reply_markup=owner_menu())
            return
        target_id = BLOCKED_USERS.pop(target, None)
        if target.lower() not in [u.lower() for u in ALLOWED_USERNAMES]:
            ALLOWED_USERNAMES.append(target)
        await query.edit_message_text("✅ @" + target + " разблокирован", reply_markup=owner_menu())
        if target_id:
            try:
                await context.bot.send_message(chat_id=target_id, text="✅ Доступ восстановлен. /start")
            except Exception:
                pass
        return

    if data == "back_to_menu":
        if is_owner(user_id):
            await query.edit_message_text("👑 Панель владельца\n\nВыбери:", reply_markup=owner_menu())
        else:
            await query.edit_message_text(random_greeting(), reply_markup=main_menu())
        return

    if data == "menu_phone":
        await query.edit_message_text("📞 Проверка номера\n\nОтправь: +380XXXXXXXXX", reply_markup=back_button())
    elif data == "menu_username":
        await query.edit_message_text("👤 Проверка юзернейма\n\nОтправь: @username", reply_markup=back_button())
    elif data == "menu_ip":
        await query.edit_message_text("🌐 Проверка IP\n\nОтправь: 8.8.8.8", reply_markup=back_button())
    elif data == "menu_email":
        await query.edit_message_text("📧 Проверка email\n\nОтправь: example@gmail.com", reply_markup=back_button())
    elif data == "menu_domain":
        await query.edit_message_text("🔍 Whois домена\n\nОтправь: google.com", reply_markup=back_button())
    elif data == "menu_tools":
        await query.edit_message_text("🎲 Инструменты\n\nВыбери:", reply_markup=tools_menu())

    elif data == "tool_password":
        pwd = generate_password(20)
        await query.edit_message_text("🔑 Твой пароль:\n\n" + pwd + "\n\nСкопируй и сохрани.", reply_markup=tools_menu())
    elif data == "tool_nickname":
        nick = generate_nickname()
        await query.edit_message_text("🎭 Твой ник:\n\n" + nick, reply_markup=tools_menu())
    elif data == "tool_fact":
        fact = get_random_fact()
        await query.edit_message_text("💡 Факт:\n\n" + fact, reply_markup=tools_menu())
    elif data == "tool_music_search":
        await query.edit_message_text("🎵 Найти песню\n\nОтправь название песни или исполнителя:", reply_markup=back_button())
    elif data == "tool_music_download":
        await query.edit_message_text("📥 Скачать и отправить\n\nОтправь название песни — я скачаю и отправлю mp3:", reply_markup=back_button())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global FORWARD_MESSAGES
    user_id = update.effective_user.id
    username = update.effective_user.username

    if GLOBAL_BLOCK and not is_owner(user_id):
        await update.message.reply_text(random_global_deny())
        return
    if is_blocked(username) and not is_owner(user_id):
        await update.message.reply_text(random_deny())
        return
    if not is_owner(user_id) and not is_allowed(username):
        await update.message.reply_text("⛔ Доступ запрещён\n\nОтправь /start.")
        return

    try:
        text = update.message.text.strip()
        logger.info("@" + str(username) + ": " + text)

        if FORWARD_MESSAGES and not is_owner(user_id):
            try:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text="📬 Сообщение от пользователя\n\n👤 @" + username + "\n🆔 " + str(user_id) + "\n\n💬 " + text,
                )
            except Exception:
                pass

        if re.match(r"^\+?\d{10,15}$", text):
            info = get_phone_info(text)
            if "error" in info:
                await update.message.reply_text("❌ " + info["error"], reply_markup=back_button())
                return
            reply = (
                "📞 Результат\n\n"
                "🔹 Номер: " + info["phone"] + "\n"
                "🌍 Страна: " + info["country"] + "\n"
                "📡 Оператор: " + info["operator"] + "\n"
                "⏳ Таймзона: " + info["timezone"] + "\n"
                "✅ Валидный: " + ("Да" if info["valid"] else "Нет")
            )
            await update.message.reply_text(reply, reply_markup=back_button())

        elif re.match(r"^[^@]+@[^@]+\.[^@]+$", text):
            info = check_email_leaks(text)
            if "error" in info:
                await update.message.reply_text("❌ " + info["error"], reply_markup=back_button())
                return
            if info["count"] > 0:
                breaches_list = "\n".join(["• " + b for b in info["breaches"][:10]])
                reply = (
                    "📧 Email проверен\n\n"
                    "🔹 Email: " + info["email"] + "\n"
                    "⚠️ Найден в утечках: " + str(info["count"]) + "\n\n"
                    + breaches_list
                )
            else:
                reply = "📧 Email: " + info["email"] + "\n\n✅ Утечек не найдено."
            await update.message.reply_text(reply, reply_markup=back_button())

        elif text.startswith("@"):
            info = get_telegram_info(text[1:])
            if "error" in info:
                await update.message.reply_text("❌ " + info["error"], reply_markup=back_button())
                return
            if info.get("exists"):
                reply = (
                    "👤 Результат\n\n"
                    "✅ Юзернейм: @" + info["username"] + "\n"
                    "🔗 Ссылка: " + info["url"] + "\n"
                    "📝 Название: " + info.get("title", "Неизвестно")
                )
                await update.message.reply_text(reply, reply_markup=back_button())
            else:
                await update.message.reply_text("❌ Юзернейм не существует.", reply_markup=back_button())

        elif re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", text):
            info = get_ip_info(text)
            if "error" in info:
                await update.message.reply_text("❌ " + info["error"], reply_markup=back_button())
                return
            if info.get("status") == "fail":
                await update.message.reply_text("❌ " + info.get("message", "Ошибка"), reply_markup=back_button())
                return
            reply = (
                "🌐 Результат\n\n"
                "🔹 IP: " + text + "\n"
                "📍 Страна: " + info.get("country", "—") + "\n"
                "🏙️ Город: " + info.get("city", "—") + "\n"
                "📌 Регион: " + info.get("region", "—") + "\n"
                "📡 Провайдер: " + info.get("isp", "—") + "\n"
                "🗺️ Координаты: " + str(info.get("lat", "—")) + ", " + str(info.get("lon", "—"))
            )
            await update.message.reply_text(reply, reply_markup=back_button())

        elif "." in text and not text.startswith("@") and " " not in text:
            info = get_domain_info(text)
            if "error" in info:
                await update.message.reply_text("❌ " + info["error"], reply_markup=back_button())
                return
            reply = (
                "🔍 Домен\n\n"
                "🔹 Домен: " + info["domain"] + "\n"
                "🌐 IP: " + info["ip"] + "\n"
                "✅ Резолвится: Да"
            )
            await update.message.reply_text(reply, reply_markup=back_button())

        else:
            await update.message.reply_text("🎵 Ищу: " + text + "\n\nПодожди...", reply_markup=back_button())

            song_info = search_song(text)
            if "error" in song_info:
                await update.message.reply_text("❌ " + song_info["error"], reply_markup=back_button())
                return

            duration = song_info.get("duration", 0)
            dur_str = str(duration // 60) + ":" + str(duration % 60).zfill(2) if duration else "?"
            reply = (
                "🎵 Найдено:\n\n"
                "📌 " + song_info["title"] + "\n"
                "👤 " + song_info["uploader"] + "\n"
                "⏱️ " + dur_str + "\n\n"
                "Отправляю mp3..."
            )
            await update.message.reply_text(reply)

            try:
                result = download_song(text)
                if "error" in result:
                    await update.message.reply_text("❌ " + result["error"], reply_markup=back_button())
                    return

                filepath = result["filepath"]
                if os.path.exists(filepath):
                    with open(filepath, "rb") as audio:
                        await update.message.reply_audio(
                            audio=audio,
                            title=result["title"],
                            performer=result.get("uploader", "Unknown"),
                            reply_markup=back_button(),
                        )
                    os.remove(filepath)
                else:
                    await update.message.reply_text("❌ Файл не найден после скачивания.", reply_markup=back_button())
            except Exception as e:
                await update.message.reply_text("❌ Ошибка: " + str(e), reply_markup=back_button())

    except Exception as e:
        await update.message.reply_text("⚠️ Ошибка: " + str(e))
        logger.error("Краш: " + str(e))

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("🤖 SquidHub Bot v6.0 запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()