import logging
import nest_asyncio
import asyncio
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import random
import os
import json
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = '7302385733:AAFduy80LAJRgFaGdrZr5ZRsYrASHdYY93Y'  # Ваш токен бота
CHANNEL_USERNAME = '@tarkotest'  # Имя пользователя вашего канала
ADMIN_IDS = [359406176, 195719447]  # Список user ID администраторов

bot = Bot(token=TOKEN)

# Применение nest_asyncio
nest_asyncio.apply()

# Папка для хранения баз данных участников
DATA_DIR = 'Data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

participants = set()
date_drawing = None

# Восстановление участников из файла
def load_participants(date):
    global participants
    file_path = os.path.join(DATA_DIR, f"participants_{date}.json")
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            participants = set(json.load(file))
        logging.info(f"Участники для розыгрыша {date} восстановлены.")
    else:
        participants = set()
        logging.info(f"Файл участников для розыгрыша {date} не найден. Начинаем с пустого списка.")

# Сохранение участников в файл
def save_participants(date):
    file_path = os.path.join(DATA_DIR, f"participants_{date}.json")
    with open(file_path, 'w') as file:
        json.dump(list(participants), file)
    logging.info(f"Участники для розыгрыша {date} сохранены.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if user.id in ADMIN_IDS:
        await update.message.reply_text('Привет, администратор! Используйте /publish для публикации ссылки на участие в розыгрыше.')
    else:
        args = context.args
        if len(args) > 0 and args[0] == 'priz':
            await priz(update, context)
        else:
            await update.message.reply_text(
                f'Привет. Для участия в розыгрыше вам нужно быть подписанным на наш канал {CHANNEL_USERNAME}.'
                f'\n\nЕсли вы уже подписаны на наш канал просто нажмите на эту команду /priz'
            )

async def publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global date_drawing
    user = update.message.from_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text('У вас нет прав для использования этой команды.')
        return

    await update.message.reply_text('Отправьте текст конкурса для публикации.')
    context.user_data['publish_stage'] = 'text'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global date_drawing
    user = update.message.from_user

    if 'publish_stage' not in context.user_data:
        return

    stage = context.user_data['publish_stage']

    if stage == 'text':
        context.user_data['publish_text'] = update.message.text
        context.user_data['publish_stage'] = 'image'
        await update.message.reply_text('Теперь отправьте изображение для публикации, если вы не хотите прикреплять изображение отправьте "пропустить".')
    elif stage == 'image':
        if update.message.photo:
            context.user_data['publish_image'] = update.message.photo[-1].file_id
            context.user_data['publish_stage'] = 'date'
            await update.message.reply_text('Напишите дату в формате дд.мм.гггг')
        elif update.message.text.lower() == 'пропустить':
            context.user_data['publish_image'] = None
            context.user_data['publish_stage'] = 'date'
            await update.message.reply_text('Напишите дату в формате дд.мм.гггг')
        else:
            await update.message.reply_text('Пожалуйста, отправьте изображение или отправьте "пропустить".')
    elif stage == 'date':
        date_text = update.message.text
        try:
            date_drawing = datetime.strptime(date_text, '%d.%m.%Y').strftime('%d.%м.%Y')
            context.user_data['publish_date'] = date_drawing
            text = context.user_data['publish_text']
            image = context.user_data.get('publish_image')
            deep_link = f"https://t.me/{context.bot.username}?start=priz"

            if image:
                await context.bot.send_photo(chat_id=CHANNEL_USERNAME, photo=image, caption=f"{text}\n\nЧтобы участвовать в конкурсе переходите по ссылке и следуйте инструкциям: [сюда]({deep_link}).", parse_mode='Markdown')
            else:
                await context.bot.send_message(chat_id=CHANNEL_USERNAME, text=f"{text}\n\nЧтобы участвовать в конкурсе переходите по ссылке и следуйте инструкциям: [сюда]({deep_link}).", parse_mode='Markdown')

            save_participants(date_drawing)  # Сохраняем текущих участников
            await update.message.reply_text(f"Конкурс опубликован. Дата розыгрыша: {date_drawing}")
            logging.info(f"Published participation link in channel {CHANNEL_USERNAME}")
            context.user_data['publish_stage'] = None  # Сброс этапа публикации
        except ValueError:
            await update.message.reply_text('Неверный формат даты. Попробуйте снова.')

async def priz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global date_drawing
    user = update.message.from_user
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user.id)
        if member.status not in ['member', 'administrator', 'creator']:
            await update.message.reply_text(f"Вы должны быть подписаны на канал {CHANNEL_USERNAME}, чтобы участвовать в розыгрыше.")
            logging.info(f"User {user.id} is not a member of the channel")
            return

        bot_member = await context.bot.get_chat_member(user.id, context.bot.id)
        if bot_member.status == 'left':
            await update.message.reply_text("Вы должны подписаться на бота, чтобы участвовать в розыгрыше.")
            logging.info(f"User {user.id} is not subscribed to the bot")
            return

        participants.add(user.id)
        save_participants(date_drawing)  # Сохраняем участников после каждого добавления
        await update.message.reply_text(f"Вы успешно присоединились к розыгрышу! Осталось последнее действие! Отправьте сообщение о розыгрыше из нашего канала 3 вашим друзьям! И уже {date_drawing} мы выберем победителей! Для удобства просто сделайте скриншоты ваших сообщений друзьям и отправьте их сюда.")
        logging.info(f"User {user.id} joined the lottery")

    except Exception as e:
        await update.message.reply_text("Произошла ошибка при проверке подписки.")
        logging.error(f"Error checking membership for user {user.id}: {e}")

async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text('У вас нет прав для использования этой команды.')
        return

    if not participants:
        await update.message.reply_text('Нет участников для розыгрыша.')
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text('Использование: /draw <количество победителей>')
        return

    num_winners = int(context.args[0])
    if num_winners > len(participants):
        await update.message.reply_text(f'Количество победителей ({num_winners}) больше количества участников ({len(participants)}).')
        return

    participants_list = list(participants)
    winners = random.sample(participants_list, num_winners)

    winner_links = [f"[user_{winner_id}](tg://user?id={winner_id})" for winner_id in winners]
    winner_message = "Розыгрыш завершен. Победители:\n" + "\n".join(winner_links) + f"\n\nВсего участников: {len(participants_list)}"

    for winner_id in winners:
        try:
            await context.bot.send_photo(chat_id=winner_id, photo='https://images.unsplash.com/photo-1513151233558-d860c5398176?w=600&auto=format&fit=crop&q=60&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Mjh8fHByZXNlbnR8ZW58MHx8MHx8fDA%3D', caption="Поздравляем! Вы выиграли в нашем розыгрыше! Теперь вам достаточно просто прийти к нам в магазин, и забрать приз. Покажите это сообщение продавцу и 3 скриншота, что вы делали репосты вашим друзьям поста с розыгрышем.")
            logging.info(f"User {winner_id} notified as a winner")
        except Exception as e:
            logging.error(f"Failed to send message to user {winner_id}: {e}")

    await update.message.reply_text(winner_message, parse_mode='Markdown')
    logging.info(f"Draw completed with winners: {', '.join(map(str, winners))}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text('У вас нет прав для использования этой команды.')
        return

    await update.message.reply_text(f'Всего участников: {len(participants)}')
    logging.info(f"Total participants: {len(participants)}")

async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    await update.message.reply_text(f"Ваш ID: {user.id}")

async def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("publish", publish))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    application.add_handler(CommandHandler("priz", priz))
    application.add_handler(CommandHandler("draw", draw))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("get_user_id", get_user_id))

    logging.info("Starting polling...")
    await application.run_polling()

if __name__ == '__main__':
    logging.info("Starting bot application...")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
