info = get_phone_info(text)
        if "error" in info:
            await update.message.reply_text(f"❌ {info['error']}")
            return
        reply = (
            f"📞 *Номер:* `{info['phone']}`\n"
            f"🌍 *Страна:* {info['country'] or 'Неизвестно'}\n"
            f"📡 *Оператор:* {info['operator'] or 'Неизвестно'}\n"
            f"⏳ *Таймзона:* {', '.join(info['timezone']) if info['timezone'] else 'Неизвестно'}\n"
            f"✅ *Валидный:* {'Да' if info['valid'] else 'Нет'}\n"
        )
        if info.get('abstract'):
            abstract = info['abstract']
            if abstract.get('valid'):
                reply += f"🔹 *Провайдер:* {abstract.get('carrier', 'Неизвестно')}\n"
                reply += f"🔹 *Тип:* {abstract.get('line_type', 'Неизвестно')}\n"
        await update.message.reply_text(reply, parse_mode="Markdown")

    # Если юзернейм Telegram (начинается с @)
    elif text.startswith('@'):
        info = get_telegram_info(text[1:])
        if "error" in info:
            await update.message.reply_text(f"❌ {info['error']}")
            return
        if info.get('exists'):
            await update.message.reply_text(
                f"✅ *Юзернейм:* @{info['username']}\n"
                f"🔗 *Ссылка:* {info['url']}\n"
                f"📝 *Название профиля:* {info.get('title', 'Неизвестно')}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Такой юзернейм не существует или скрыт.")

    # Если email
    elif re.match(r'^[^@]+@[^@]+\.[^@]+$', text):
        breaches = get_email_breaches(text)
        if isinstance(breaches, list) and len(breaches) > 0:
            reply = f"📧 *Email:* {text}\n🔓 *Найден в утечках:*\n"
            for breach in breaches[:5]:  # максимум 5
                reply += f"• {breach.get('Name', 'Неизвестно')} — {breach.get('BreachDate', 'дата неизвестна')}\n"
            await update.message.reply_text(reply, parse_mode="Markdown")
        elif isinstance(breaches, list) and len(breaches) == 0:
            await update.message.reply_text(f"✅ *Email:* {text}\nУтечек не найдено.", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Не удалось проверить утечки.")

    # Если IP (содержит цифры и точки)
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
            f"🗺️ *Координаты:* {info.get('lat', '—')}, {info.get('lon', '—')}\n"
        )
        await update.message.reply_text(reply, parse_mode="Markdown")

    else:
        await update.message.reply_text("❌ Не удалось распознать запрос. Отправь номер, @юзернейм, email или IP.")

# ========== ЗАПУСК ==========

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("🤖 Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if name == "__main__":
    main()
