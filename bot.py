# -*- coding: utf-8 -*-
import logging
import re
import requests
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ========== ТОКЕН ==========
TELEGRAM_TOKEN = "8476291431:AAElHgmZT92_GIBIchbnQ3AxCxu98HEQjx4"

# ========== ТВОЙ ID (ВСТАВЛЕН) ==========
OWNER_ID = 1100862483

# ========== БЕЛЫЙ СПИСОК (РАЗРЕШЁННЫЕ) ==========
ALLOWED_USERS = [
    OWNER_ID,  # ты всегда имеешь доступ
]

# ========== ЗАЯВКИ НА ОДОБРЕНИЕ ==========
PENDING_REQUESTS = {}  # {user_id: username}

logging.basicConfig(level=logging.INFO)

# ========== ПРОВЕРКА ДОСТУПА ==========
def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

# ========== ФУНКЦИИ ПРОБИВА ==========
def get_phone_info(phone: str) -> dict:
    try:
        parsed = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed):
            return {"error": "Неверный номер"}
        country = geocoder.description_for_number(parsed, "ru")
        operator = carrier.name_for_number(parsed, "ru")
        tz = timezone.time_zones_for_number(parsed)
        return {
            "phone": phone,
            "country": country or "Неизвестно",
            "operator": operator or "Неизвестно",
            "timezone": ", ".join(tz) if tz else "Неизвестно",
            "valid": phonenumbers.is_valid_number(parsed)
        }
    except Exception as e:
        return {"error": str(e)}

def get_telegram_info(username: str) -> dict:
    try:
        resp = requests.get(f"https://t.me/{username}", timeout=5)
        if resp.status_code == 200:
            title = re.search(r'<title>(.*?)</title>', resp.text)
            title_text = title.group(1) if title else "Неизвестно"
            return {"username": username, "exists": True, "title": title_text, "url": f"https://t.me/{username}"}
        else:
            return {"username": username, "exists": False}
    except:
        return {"error": "Не удалось проверить"}

def get_ip_info(ip: str) -> dict:
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}?fields=status,message,country,city,region,isp,lat,lon,org,as", timeout=5)
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"error": "IP не найден"}
    except:
        return {"error": "Ошибка запроса"}

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "без юзернейма"

    if is_allowed(user_id):
        await update.message.reply_text(
            "🔍 *Бот-пробиватор*\n"
            "Отправь мне:\n"
            "• Номер телефона (+380XXXXXXXXX)\n"
            "• Юзернейм Telegram (@username)\n"
            "• IP-адрес\n\n"
            "Я выдам всю информацию.",
            parse_mode="Markdown"
        )
        return

    # Если пользователь НЕ в белом списке
    if user_id in PENDING_REQUESTS:
        await update.message.reply_text("⏳ Ваш запрос уже отправлен на одобрение. Ожидайте.")
        return

    # Добавляем в очередь на одобрение
    PENDING_REQUESTS[user_id] = username
    await update.message.reply_text("📨 Запрос отправлен на одобрение владельцу. Ожидайте.")

    # Отправляем уведомление владельцу
    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=f"🔔 *Новый запрос доступа*\n"
             f"👤 @{username}\n"
             f"🆔 ID: `{user_id}`\n\n"
             f"✅ /approve {user_id} — одобрить\n"
             f"❌ /deny {user_id} — отклонить",
        parse_mode="Markdown"
    )

# ========== ОДОБРЕНИЕ ==========
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ Только владелец может одобрять.")
        return

    try:
        target_id = int(context.args[0])
        if target_id in ALLOWED_USERS:
            await update.message.reply_text(f"ℹ️ Пользователь {target_id} уже в белом списке.")
            return

        if target_id not in PENDING_REQUESTS:
            await update.message.reply_text(f"❌ Заявка от {target_id} не найдена.")
            return

        # Добавляем в белый список
        ALLOWED_USERS.append(target_id)
        username = PENDING_REQUESTS.pop(target_id)
        await update.message.reply_text(f"✅ Пользователь @{username} (ID: {target_id}) одобрен.")

        # Уведомляем пользователя
        await context.bot.send_message(
            chat_id=target_id,
            text="✅ Ваш запрос одобрен! Теперь вы можете пользоваться ботом.\n"
                 "Отправьте /start, чтобы начать."
        )
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Используй: /approve ID_пользователя")

# ========== ОТКЛОНЕНИЕ ==========
async def deny(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ Только владелец может отклонять.")
        return

    try:
        target_id = int(context.args[0])
        if target_id not in PENDING_REQUESTS:
            await update.message.reply_text(f"❌ Заявка от {target_id} не найдена.")
            return

        username = PENDING_REQUESTS.pop(target_id)
        await update.message.reply_text(f"❌ Пользователь @{username} (ID: {target_id}) отклонён.")

        # Уведомляем пользователя
        await context.bot.send_message(
            chat_id=target_id,
            text="❌ Ваш запрос отклонён владельцем бота."
        )
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Используй: /deny ID_пользователя")

# ========== ОБРАБОТКА СООБЩЕНИЙ ==========
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("⛔ Доступ запрещён. Отправьте /start для запроса доступа.")
        return

    try:
        text = update.message.text.strip()
        user = update.effective_user
        logging.info(f"Запрос от {user.id}: {text}")

        if re.match(r'^\+?\d{10,15}$', text):
            info = get_phone_info(text)
            if "error" in info:
                await update.message.reply_text(f"❌ {info['error']}")
                return
            reply = (
                f"📞 *Номер:* `{info['phone']}`\n"
                f"🌍 *Страна:* {info['country']}\n"
                f"📡 *Оператор:* {info['operator']}\n"
                f"⏳ *Таймзона:* {info['timezone']}\n"
                f"✅ *Валидный:* {'Да' if info['valid'] else 'Нет'}"
            )
            await update.message.reply_text(reply, parse_mode="Markdown")

        elif text.startswith('@'):
            info = get_telegram_info(text[1:])
            if "error" in info:
                await update.message.reply_text(f"❌ {info['error']}")
                return
            if info.get('exists'):
                await update.message.reply_text(
                    f"✅ *Юзернейм:* @{info['username']}\n"
                    f"🔗 *Ссылка:* {info['url']}\n"
                    f"📝 *Название:* {info.get('title', 'Неизвестно')}",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ Такой юзернейм не существует или скрыт.")

        elif re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', text):
            info = get_ip_info(text)
            if "error" in info:
                await update.message.reply_text(f"❌ {info['error']}")
                return
            if info.get('status') == 'fail':
                await update.message.reply_text(f"❌ {info.get('message', 'Неизвестная ошибка')}")
                return
            reply = (
                f"🌐 *IP:* {text}\n"
                f"📍 *Страна:* {info.get('country', 'Неизвестно')}\n"
                f"🏙️ *Город:* {info.get('city', 'Неизвестно')}\n"
                f"📌 *Регион:* {info.get('region', 'Неизвестно')}\n"
                f"📡 *Провайдер:* {info.get('isp', 'Неизвестно')}\n"
                f"🗺️ *Координаты:* {info.get('lat', '—')}, {info.get('lon', '—')}"
            )
            await update.message.reply_text(reply, parse_mode="Markdown")

        else:
            await update.message.reply_text("❌ Не распознано. Отправь номер, @юзернейм или IP.")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")
        logging.error(f"Краш: {e}")

# ========== ЗАПУСК ==========
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("deny", deny))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("🤖 Бот запущен и работает!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
