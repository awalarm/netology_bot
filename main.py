import os
from dotenv import load_dotenv
from telebot import TeleBot, types, custom_filters
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage

import database

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
DB_URL = os.getenv('DATABASE_URL')

state_storage = StateMemoryStorage()
bot = TeleBot(TOKEN, state_storage=state_storage)
db = database.Database(DB_URL)


class MyStates(StatesGroup):
    target_word = State()
    waiting_for_english = State()
    waiting_for_russian = State()
    waiting_for_word_to_delete = State()


class Command:
    ADD_WORD = '➕ Добавить слово'
    DELETE_WORD = '🔙 Удалить слово'
    NEXT = '⏭ Дальше'
    MY_WORDS = '📚 Мои слова'
    HELP = '❓ Помощь'


WELCOME_MESSAGE = """Привет 👋

Давай попрактикуемся в английском языке. Тренировки можешь проходить в удобном для себя темпе. 

У тебя есть возможность использовать тренажёр, как конструктор, и собирать свою собственную базу для обучения. Для этого воспользуйся инструментами:
- добавить слово ➕,
- удалить слово 🔙,
- мои слова 📚.

Ну что, начнём ⬇️"""


@bot.message_handler(commands=['start', 'cards'])
def handle_start(message):
    """Начало работы с ботом"""
    cid = message.chat.id
    user = db.get_or_create_user(
        telegram_id=cid,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )

    if message.text == '/start':
        bot.send_message(cid, WELCOME_MESSAGE, parse_mode='HTML')

    create_cards(message, user.id)


@bot.message_handler(commands=['help'])
def handle_help(message):
    """Помощь по боту"""
    help_text = """🤖 *Команды бота:*

/start - Начать работу
/cards - Новая карточка  
/mywords - Мои слова
/help - Помощь

*Кнопки:*
⏭ Дальше - Следующее слово
➕ Добавить слово - Добавить новое слово
🔙 Удалить слово - Удалить ваше слово
📚 Мои слова - Показать все слова
❓ Помощь - Справка"""
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')


@bot.message_handler(commands=['mywords'])
def handle_mywords(message):
    """Показать слова пользователя"""
    cid = message.chat.id
    user = db.get_or_create_user(telegram_id=cid)

    # Все слова
    all_words = db.get_all_user_words(user.id)

    if not all_words:
        bot.send_message(cid, "У вас пока нет слов. Добавьте слова с помощью кнопки '➕ Добавить слово'.")
        return

    # Дефолтные слова
    default_words = db.get_user_default_words(user.id)
    # Пользовательские слова
    custom_words = db.get_user_words(user.id)

    text = f"📚 *Ваши слова ({len(all_words)}):*\n\n"

    if default_words:
        text += "*Слова по умолчанию:*\n"
        for w in default_words[:5]:
            text += f"• {w.english} - {w.russian}\n"
        if len(default_words) > 5:
            text += f"... и ещё {len(default_words) - 5}\n"
        text += "\n"

    if custom_words:
        text += "*Ваши слова:*\n"
        for w in custom_words[:10]:
            text += f"• {w.english} - {w.russian}\n"
        if len(custom_words) > 10:
            text += f"... и ещё {len(custom_words) - 10}"

    bot.send_message(cid, text, parse_mode='Markdown')


def create_cards(message, user_id=None):
    """Создать новую карточку с вопросом"""
    cid = message.chat.id

    if user_id is None:
        user = db.get_or_create_user(telegram_id=cid)
        user_id = user.id

    target_word, all_words = db.get_random_words_for_test(user_id)

    if not target_word:
        bot.send_message(cid, "Недостаточно слов для тренировки. Добавьте слова!")
        return

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)

    answer_buttons = [types.KeyboardButton(w.english) for w in all_words]

    service_buttons = [
        types.KeyboardButton(Command.NEXT),
        types.KeyboardButton(Command.ADD_WORD),
        types.KeyboardButton(Command.DELETE_WORD),
        types.KeyboardButton(Command.MY_WORDS),
        types.KeyboardButton(Command.HELP)
    ]

    # Добавление кнопок
    for i in range(0, len(answer_buttons), 2):
        markup.add(*answer_buttons[i:i + 2])

    for i in range(0, len(service_buttons), 2):
        markup.add(*service_buttons[i:i + 2])

    question = f"🇷🇺 *{target_word.russian}*\n\nВыбери перевод:"
    bot.send_message(cid, question, reply_markup=markup, parse_mode='Markdown')

    bot.set_state(message.from_user.id, MyStates.target_word, cid)
    with bot.retrieve_data(message.from_user.id, cid) as data:
        data['target_word'] = target_word
        data['all_words'] = all_words
        data['user_id'] = user_id


@bot.message_handler(func=lambda m: m.text == Command.NEXT)
def next_card(message):
    """Следующая карточка"""
    cid = message.chat.id
    user = db.get_or_create_user(telegram_id=cid)
    create_cards(message, user.id)


@bot.message_handler(func=lambda m: m.text == Command.ADD_WORD)
def add_word_start(message):
    """Начать добавление слова"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ Отмена"))
    bot.send_message(message.chat.id, "Введите английское слово:", reply_markup=markup)
    bot.set_state(message.from_user.id, MyStates.waiting_for_english, message.chat.id)


@bot.message_handler(func=lambda m: m.text == Command.DELETE_WORD)
def delete_word_start(message):
    """Начать удаление слова"""
    cid = message.chat.id
    user = db.get_or_create_user(telegram_id=cid)

    words = db.get_user_words(user.id)  # Только пользовательские слова

    if not words:
        bot.send_message(cid,
                         "У вас нет слов для удаления.\n\nВы можете удалять только слова, которые вы сами добавили.")
        return

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    word_buttons = [types.KeyboardButton(f"{w.english} - {w.russian}") for w in words[:12]]
    markup.add(*word_buttons)
    markup.add(types.KeyboardButton("❌ Отмена"))

    bot.send_message(cid, "Выберите слово для удаления:", reply_markup=markup)
    bot.set_state(message.from_user.id, MyStates.waiting_for_word_to_delete, cid)

    with bot.retrieve_data(message.from_user.id, cid) as data:
        data['words_to_delete'] = {f"{w.english} - {w.russian}": w.id for w in words[:12]}


@bot.message_handler(func=lambda m: m.text == Command.MY_WORDS)
def show_my_words(message):
    """Показать мои слова"""
    handle_mywords(message)


@bot.message_handler(func=lambda m: m.text == Command.HELP)
def show_help(message):
    """Показать помощь"""
    handle_help(message)


# Состояния ввода
@bot.message_handler(state=MyStates.waiting_for_english)
def get_english_word(message):
    """Получить английское слово"""
    if message.text == "❌ Отмена":
        bot.delete_state(message.from_user.id, message.chat.id)
        user = db.get_or_create_user(telegram_id=message.chat.id)
        create_cards(message, user.id)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ Отмена"))

    bot.send_message(message.chat.id,
                     f"Английское: *{message.text}*\n\nТеперь введите перевод:",
                     parse_mode='Markdown', reply_markup=markup)

    bot.set_state(message.from_user.id, MyStates.waiting_for_russian, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['new_english'] = message.text.strip()


@bot.message_handler(state=MyStates.waiting_for_russian)
def get_russian_translation(message):
    """Получить русский перевод"""
    if message.text == "❌ Отмена":
        bot.delete_state(message.from_user.id, message.chat.id)
        user = db.get_or_create_user(telegram_id=message.chat.id)
        create_cards(message, user.id)
        return

    cid = message.chat.id

    with bot.retrieve_data(message.from_user.id, cid) as data:
        english = data['new_english']
        russian = message.text.strip()
        user = db.get_or_create_user(telegram_id=cid)

        try:
            english_word, russian_word, result = db.add_word_to_user(user.id, english, russian)

            if result is True:
                response = f"✅ *Слово добавлено!*\n\n{english_word} - {russian_word}"
            elif result is False:
                response = f"✅ *Слово восстановлено!*\n\n{english_word} - {russian_word}"
            else:
                response = f"ℹ️ *Слово уже есть:*\n\n{english_word} - {russian_word}"

            bot.send_message(cid, response, parse_mode='Markdown')

        except Exception as e:
            bot.send_message(cid, f"❌ Ошибка: {str(e)}")

    bot.delete_state(message.from_user.id, cid)
    user = db.get_or_create_user(telegram_id=cid)
    create_cards(message, user.id)


@bot.message_handler(state=MyStates.waiting_for_word_to_delete)
def delete_selected_word(message):
    """Удалить выбранное слово"""
    if message.text == "❌ Отмена":
        bot.delete_state(message.from_user.id, message.chat.id)
        user = db.get_or_create_user(telegram_id=message.chat.id)
        create_cards(message, user.id)
        return

    cid = message.chat.id

    with bot.retrieve_data(message.from_user.id, cid) as data:
        words_map = data.get('words_to_delete', {})

        if message.text in words_map:
            word_id = words_map[message.text]
            user = db.get_or_create_user(telegram_id=cid)

            success, msg = db.delete_word_from_user(user.id, word_id)

            if success:
                bot.send_message(cid, f"✅ {msg}")
            else:
                bot.send_message(cid, f"❌ {msg}")
        else:
            bot.send_message(cid, "Выберите слово из списка!")
            return

    bot.delete_state(message.from_user.id, cid)
    user = db.get_or_create_user(telegram_id=cid)
    create_cards(message, user.id)


@bot.message_handler(func=lambda m: True)
def handle_test_answer(message):
    """Обработка ответов на тест"""
    cid = message.chat.id
    uid = message.from_user.id

    current_state = bot.get_state(uid, cid)
    if current_state in [MyStates.waiting_for_english,
                         MyStates.waiting_for_russian,
                         MyStates.waiting_for_word_to_delete]:
        return

    if message.text in [Command.NEXT, Command.ADD_WORD, Command.DELETE_WORD,
                        Command.MY_WORDS, Command.HELP]:
        return

    try:
        with bot.retrieve_data(uid, cid) as data:
            if not data or 'target_word' not in data:
                user = db.get_or_create_user(telegram_id=cid)
                create_cards(message, user.id)
                return

            target_word = data['target_word']
            all_words = data.get('all_words', [])

            # Проверяем ответ
            user_answer = message.text.strip()
            is_correct = user_answer == target_word.english

            # Создаем клавиатуру для ответа
            markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)

            if is_correct:
                response = f"✅ *Правильно!*\n\n{target_word.english} - {target_word.russian}"

                buttons = [
                    types.KeyboardButton(Command.NEXT),
                    types.KeyboardButton(Command.ADD_WORD),
                    types.KeyboardButton(Command.DELETE_WORD),
                    types.KeyboardButton(Command.MY_WORDS),
                    types.KeyboardButton(Command.HELP)
                ]
                markup.add(*buttons)

            else:
                response = f"❌ *Неправильно!*\n\nПравильный ответ: {target_word.english}\nСлово: {target_word.russian}"

                answer_buttons = []
                for word in all_words:
                    btn_text = word.english
                    if btn_text == user_answer:
                        btn_text = f"❌ {btn_text}"
                    answer_buttons.append(types.KeyboardButton(btn_text))

                service_buttons = [
                    types.KeyboardButton(Command.NEXT),
                    types.KeyboardButton(Command.ADD_WORD),
                    types.KeyboardButton(Command.DELETE_WORD),
                    types.KeyboardButton(Command.MY_WORDS),
                    types.KeyboardButton(Command.HELP)
                ]

                for i in range(0, len(answer_buttons), 2):
                    markup.add(*answer_buttons[i:i + 2])

                for i in range(0, len(service_buttons), 2):
                    markup.add(*service_buttons[i:i + 2])

            bot.send_message(cid, response, reply_markup=markup, parse_mode='Markdown')

            if is_correct:
                bot.delete_state(uid, cid)

    except Exception:
        user = db.get_or_create_user(telegram_id=cid)
        create_cards(message, user.id)


if __name__ == '__main__':
    db.create_tables()
    db.init_default_words()
    bot.add_custom_filter(custom_filters.StateFilter(bot))

    try:
        print("Бот запущен!")
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\nБот остановлен.")
