import logging
from threading import Timer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes, ConversationHandler, JobQueue
from config import ADMIN_ID, BOT_API_TOKEN

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

counter = 0
GET_PHONE = range(1)
GET_NEWS_INTERVAL = range(1)
bot_running = True
bot_simulation_mode = False
processed_photos = set()
workers = {}
current_worker = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Бот запущен!')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_running:
        return
    if bot_simulation_mode:
        await update.message.reply_text("😔 На данный момент нет доступных WhatsApp для выдачи", reply_to_message_id=update.message.message_id)
        return
    if not bot_simulation_mode and update.message.photo[-1].file_id in processed_photos:
        return
    if current_worker is not None:
        forwarded_message = await context.bot.forward_message(chat_id=current_worker, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
        await send_action_buttons(context, context.bot, current_worker, forwarded_message.message_id, update.message.chat_id, update.message.message_id)
        await update.message.reply_text(f'⬆️ Сообщение было успешно взято в работу {workers[current_worker]}', reply_to_message_id=update.message.message_id)
    else:
        await update.message.reply_text("Нет доступных пользователей для обработки заявки.")

async def send_action_buttons(context, bot, chat_id, message_id, user_id, photo_message_id):
    keyboard = [[InlineKeyboardButton("Вотсап поставлен ✅", callback_data=f"set_{message_id}_{user_id}_{photo_message_id}")], [InlineKeyboardButton("Повтор", callback_data=f"repeat_{message_id}_{user_id}_{photo_message_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    action_message = await bot.send_message(chat_id=chat_id, text="Выберите действие:", reply_markup=reply_markup)
    context.user_data.setdefault("action_message_ids", {}).update({user_id: action_message.message_id})

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_running:
        return
    query = update.callback_query
    await query.answer()
    action, forwarded_message_id, user_id, photo_message_id = query.data.split('_')
    for current_user_id in workers.keys():
        try:
            await context.bot.delete_message(chat_id=current_user_id, message_id=int(forwarded_message_id))
        except:
            pass
        try:
            action_message_id = context.user_data.get("action_message_ids", {}).get(current_user_id)
            if action_message_id:
                await context.bot.delete_message(chat_id=current_user_id, message_id=action_message_id)
        except:
            pass
    if action == "set":
        context.user_data.update({"forwarded_message_id": forwarded_message_id, "user_id": user_id, "photo_message_id": photo_message_id})
        await context.bot.send_message(chat_id=query.message.chat_id, text="Пожалуйста, отправьте номер телефона:")
        return GET_PHONE
    elif action == "repeat":
        await context.bot.send_message(chat_id=user_id, text="❌ Повтор", reply_to_message_id=photo_message_id)
        await context.bot.send_message(chat_id=query.message.chat_id, text="Повтор запрошен.")
    return ConversationHandler.END

def delete_message(bot, message):
    try:
        bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except:
        pass

async def cancel_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global counter
    query = update.callback_query
    await query.answer()
    _, photo_message_id = query.data.split('_')
    counter -= 1
    await context.bot.send_message(chat_id=query.message.chat_id, text="Счетчик откатился")
    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)

async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_simulation_mode:
        return
    global counter
    phone_number = update.message.text
    user_data = context.user_data
    if user_data:
        counter += 1
        if current_worker:  
            await context.bot.send_message(chat_id=user_data["user_id"], text=f"+{counter}\nВыданный номер: {phone_number}", reply_to_message_id=user_data["photo_message_id"])
            await context.bot.send_message(chat_id=update.effective_user.id, text="Номер успешно поставлен!")
            cancel_message = await context.bot.send_message(chat_id=user_data["user_id"], text="Можно отменить в течение 10 минут:", reply_to_message_id=user_data["photo_message_id"], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌", callback_data=f"cancel_{user_data['photo_message_id']}")]]))
            Timer(600, delete_message, args=(context.bot, cancel_message)).start()
            try:
                action_message_id = context.user_data.get("action_message_ids", {}).get(current_worker)
                if action_message_id:
                    await context.bot.delete_message(chat_id=current_worker, message_id=action_message_id)
            except:
                pass
            try:
                await context.bot.delete_message(chat_id=current_worker, message_id=user_data["forwarded_message_id"])
            except:
                pass
        context.user_data.clear()
        return ConversationHandler.END
    else:
        await update.message.reply_text("Произошла ошибка. Попробуйте снова.")
        return GET_PHONE

# --- Административные команды ---
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        try:
            user_id = int(context.args[0])  # Преобразуем только ID в число
            name = ' '.join(context.args[1:])  # Имя собираем из всех оставшихся аргументов
            if name in workers.values():
                await update.message.reply_text("Имя уже занято. Выберите другое имя.")
                return
            workers[user_id] = name
            await update.message.reply_text(f"Пользователь {user_id} с именем {name} добавлен в список обработчиков.")
        except (IndexError, ValueError):
            await update.message.reply_text("Использование: /adduser <user_id> <name>")
    else:
        await update.message.reply_text("У вас нет прав для этой команды.")


async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        try:
            user_id = int(context.args[0])
            if user_id in workers:
                del workers[user_id]
                await update.message.reply_text(f"Пользователь {user_id} удален из списка обработчиков.")
            else:
                await update.message.reply_text("Пользователь не найден в списке.")
        except (IndexError, ValueError):
            await update.message.reply_text("Использование: /removeuser <user_id>")
    else:
        await update.message.reply_text("У вас нет прав для этой команды.")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        if workers:
            user_list = "\n".join([f"{user_id} - {name}" for user_id, name in workers.items()])
            await update.message.reply_text(f"Список пользователей-обработчиков:\n{user_list}")
        else:
            await update.message.reply_text("Список пользователей пуст.")
    else:
        await update.message.reply_text("У вас нет прав для этой команды.")

async def worker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_worker
    if update.effective_user.id == ADMIN_ID:
        try:
            name = context.args[0]
            for user_id, worker_name in workers.items():
                if worker_name == name:
                    current_worker = user_id
                    await update.message.reply_text(f"На смену назначен {name} (ID: {user_id})")
                    return
            await update.message.reply_text("Работник с таким именем не найден.")
        except IndexError:
            await update.message.reply_text("Использование: /worker <name>")
    else:
        await update.message.reply_text("У вас нет прав для этой команды.")

async def remove_worker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_worker
    if update.effective_user.id == ADMIN_ID:
        current_worker = None
        keyboard = [[InlineKeyboardButton("Включить", callback_data="enable_simulation")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Воркеры обнулены. Место свободно. Хотите включить симуляцию?", reply_markup=reply_markup)

async def enable_simulation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_simulation_mode
    query = update.callback_query
    await query.answer()
    bot_simulation_mode = True
    await query.edit_message_text(text="Симуляция включена.")

async def start_simulation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_simulation_mode
    if update.effective_user.id == ADMIN_ID:
        bot_simulation_mode = True
        await update.message.reply_text("Симуляция включена.")
    else:
        await update.message.reply_text("У вас нет прав для этой команды.")

async def stop_simulation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_simulation_mode
    if update.effective_user.id == ADMIN_ID:
        bot_simulation_mode = False
        await update.message.reply_text("Симуляция выключена.")
    else:
        await update.message.reply_text("У вас нет прав для этой команды.")

async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_running
    if update.effective_user.id == ADMIN_ID:
        bot_running = True
        await update.message.reply_text("Бот включён.")
    else:
        await update.message.reply_text("У вас нет прав для этой команды.")

async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_running
    if update.effective_user.id == ADMIN_ID:
        bot_running = False
        await update.message.reply_text("Бот выключен.")
    else:
        await update.message.reply_text("У вас нет прав для этой команды.")

async def clear_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global counter
    if update.effective_user.id == ADMIN_ID:
        counter = 0
        await update.message.reply_text("Счетчик обнулен.")
    else:
        await update.message.reply_text("У вас нет прав для этой команды.")

# --- Функции для рассылки ---
async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("У вас нет прав для этой команды.")
        return
    
    try:
        text = " ".join(context.args)  # Собираем текст рассылки из всех аргументов
        if not text:
            await update.message.reply_text("Использование: /news <текст>")
            return

        context.user_data["news_text"] = text
        await update.message.reply_text("Теперь укажите интервал рассылки (например, 1h, 30m, 10s):")
        return GET_NEWS_INTERVAL  # Переходим в состояние ожидания интервала

    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /news <текст>")

async def handle_news_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_str = update.message.text
    try:
        time_interval = int(time_str[:-1])
        time_unit = time_str[-1]

        if time_unit == 's':
            time_interval *= 1
        elif time_unit == 'm':
            time_interval *= 60
        elif time_unit == 'h':
            time_interval *= 3600
        else:
            await update.message.reply_text("Неверный формат времени. Используйте s, m или h.")
            return GET_NEWS_INTERVAL

        text = context.user_data["news_text"]
        context.job_queue.run_repeating(send_news, time_interval, chat_id=update.effective_chat.id, data=text, name="news")
        await update.message.reply_text(f"Рассылка '{text}' запланирована каждые {time_str}.")
        return ConversationHandler.END  # Завершаем диалог

    except ValueError:
        await update.message.reply_text("Неверный формат интервала. Используйте число с суффиксом s, m или h.")
        return GET_NEWS_INTERVAL

async def send_news(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=context.job.chat_id, text=context.job.data)

async def newsnow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("У вас нет прав для этой команды.")
        return

    try:
        text = " ".join(context.args)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    except IndexError:
        await update.message.reply_text("Использование: /newsnow <текст>")

async def stop_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("У вас нет прав для этой команды.")
        return

    current_jobs = context.job_queue.get_jobs_by_name("news")
    for job in current_jobs:
        job.schedule_removal()

    await update.message.reply_text("Рассылка остановлена.")

def main():
    application = Application.builder().token(BOT_API_TOKEN).job_queue(JobQueue()).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    button_handler = CallbackQueryHandler(button, pattern="set_|repeat_")
    phone_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_phone)

    conv_handler = ConversationHandler(
        entry_points=[button_handler],
        states={
            GET_PHONE: [phone_handler],
        },
        fallbacks=[],
    )

    news_handler = ConversationHandler(
        entry_points=[CommandHandler("news", news)],
        states={
            GET_NEWS_INTERVAL: [MessageHandler(filters.TEXT & (~filters.COMMAND), handle_news_interval)],
        },
        fallbacks=[],
    )
    application.add_handler(news_handler)

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(cancel_button, pattern="cancel_"))

    # Регистрация административных команд
    application.add_handler(CommandHandler("adduser", add_user))
    application.add_handler(CommandHandler("removeuser", remove_user))
    application.add_handler(CommandHandler("listusers", list_users))
    application.add_handler(CommandHandler("startbot", start_bot))
    application.add_handler(CommandHandler("stopbot", stop_bot))
    application.add_handler(CommandHandler("startsim", start_simulation))  
    application.add_handler(CommandHandler("stopsim", stop_simulation))  
    application.add_handler(CommandHandler("clearcount", clear_count))
    application.add_handler(CommandHandler("worker", worker))
    application.add_handler(CommandHandler("removeworker", remove_worker))

    # Регистрация команд для рассылки
    application.add_handler(CommandHandler("news", news))
    application.add_handler(CommandHandler("newsnow", newsnow))
    application.add_handler(CommandHandler("stopnews", stop_news))

    application.add_handler(CallbackQueryHandler(enable_simulation, pattern="enable_simulation"))

    application.run_polling()

if __name__ == '__main__':
    main()

# Made by Shvyaner :3

