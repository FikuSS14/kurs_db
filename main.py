import psycopg2
import random
from telebot import types, TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup
from psycopg import (
    create_db,
    new_user,
    search_words,
    adding_word,
    del_word,
    true_answer,
)
from config import (
    db_name,
    login,
    password,
    token_bot,
)

try:
    conn = psycopg2.connect(database=db_name, user=login, password=password)
except psycopg2.OperationalError as e:
    print(f"Ошибка подключения к базе данных: {e}")
    exit(1)

try:
    with conn.cursor() as cur:
        create_db(cur)
        print("Start telegram bot...")

        state_storage = StateMemoryStorage()
        bot = TeleBot(token_bot, state_storage=state_storage)

        known_users = []
        buttons = []

        def show_hint(*lines):
            """Объединяет строки в одну и возвращает ее."""
            return "\n".join(lines)

        def show_target(data):
            """Форматирует строку с целевым и переводом слова."""
            return f"{data['target_word']} -> {data['translate_word']}"

        class Command:
            """Класс для хранения команд бота."""

            ADD_WORD = "Добавить слово ➕"
            DELETE_WORD = "Удалить слово🔙"
            NEXT = "Дальше ⏭"

        class MyStates(StatesGroup):
            """Класс для хранения состояний бота."""

            target_word = State()
            translate_word = State()
            another_words = State()

        @bot.message_handler(commands=["cards", "start"])
        def create_cards(message):
            """Создает карточки с английскими словами для пользователя."""
            cid = message.chat.id
            if cid not in known_users:
                known_users.append(cid)
                try:
                    new_user(cur, cid)
                except Exception as e:
                    bot.send_message(cid, f"Ошибка при добавлении пользователя: {e}")
                    return
                bot.send_message(
                    cid,
                    "\n".join(
                        ["Привет 🖖", "Давай попрактикуемся в английском языке.👇"]
                    ),
                )
            markup = types.ReplyKeyboardMarkup(row_width=2)
            buttons = []
            try:
                words = search_words(cur, cid)
            except Exception as e:
                bot.send_message(cid, f"Ошибка при поиске слов: {e}")
                return

            if not words:
                bot.send_message(cid, "Слова не найдены.")
                return

            random.shuffle(words)
            target_word = words[0][1]
            translate = words[0][0]
            target_word_btn = types.KeyboardButton(target_word)
            buttons.append(target_word_btn)

            others = [i[1] for i in words[1:4]]
            other_words_btns = [types.KeyboardButton(word) for word in others]
            buttons.extend(other_words_btns)
            random.shuffle(buttons)

            next_btn = types.KeyboardButton(Command.NEXT)
            add_word_btn = types.KeyboardButton(Command.ADD_WORD)
            delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
            buttons.extend([next_btn, add_word_btn, delete_word_btn])
            markup.add(*buttons)

            greeting = f"Выбери перевод слова:\n🇷🇺 {translate}"
            bot.send_message(message.chat.id, greeting, reply_markup=markup)
            bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)
            with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
                data["target_word"] = target_word
                data["translate_word"] = translate
                data["other_words"] = others

        @bot.message_handler(func=lambda message: message.text == Command.NEXT)
        def next_cards(message):
            """Переходит к следующей карточке."""
            create_cards(message)

        @bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
        def delete_word(message):
            """Удаляет слово из базы данных."""
            cid = message.chat.id
            with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
                try:
                    del_word(cur, cid, data["target_word"], data["translate_word"])
                    bot.send_message(
                        chat_id=message.chat.id,
                        text=f"Слово {data['translate_word']} удалено",
                    )
                except Exception as e:
                    bot.send_message(
                        chat_id=message.chat.id, text=f"Ошибка при удалении слова: {e}"
                    )

        @bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
        def enter_target_word(message: types.Message):
            """Запрашивает новое слово от пользователя."""
            bot.send_message(
                chat_id=message.chat.id, text="Введите новое английское слово"
            )
            bot.register_next_step_handler(message, enter_translate)

        def enter_translate(message: types.Message):
            """Запрашивает перевод слова от пользователя."""
            with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
                data["target_word"] = message.text
            bot.send_message(chat_id=message.chat.id, text="Введите перевод")
            bot.register_next_step_handler(message, add_word)

        def add_word(message: types.Message):
            """Добавляет новое слово и его перевод в базу данных."""
            cid = message.chat.id
            user_id = message.from_user.id
            with bot.retrieve_data(user_id, cid) as data:
                try:
                    existing_translations = search_words(cur, user_id)
                    if message.text in [word[0] for word in existing_translations]:
                        bot.send_message(chat_id=cid, text="Слово уже добавлено")
                    else:
                        data["translate_word"] = message.text
                        adding_word(
                            cur, user_id, data["target_word"], data["translate_word"]
                        )
                        bot.send_message(
                            chat_id=cid, text="Слово успешно добавлено /start"
                        )
                except Exception as e:
                    bot.send_message(
                        chat_id=cid, text=f"Ошибка при добавлении слова: {e}"
                    )

        @bot.message_handler(func=lambda message: True, content_types=["text"])
        def message_reply(message):
            """Обрабатывает сообщения от пользователей."""
            cid = message.chat.id
            buttons = []
            text = message.text
            markup = types.ReplyKeyboardMarkup(row_width=2)
            with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
                target_word = data["target_word"]
                try:
                    if text == target_word:
                        hint = show_target(data)
                        hint_text = ["Отлично!❤", hint]
                        next_btn = types.KeyboardButton(Command.NEXT)
                        add_word_btn = types.KeyboardButton(Command.ADD_WORD)
                        delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
                        buttons.extend([next_btn, add_word_btn, delete_word_btn])
                        hint = show_hint(*hint_text)
                        true_answer(
                            cur, cid, data["target_word"], data["translate_word"]
                        )
                    else:
                        hint = show_hint(
                            "Допущена ошибка!🤔",
                            f"Попробуй ещё раз вспомнить слово 🇷🇺{data['translate_word']}",
                        )
                except Exception as e:
                    hint = f"Ошибка: {e}"

            markup.add(*buttons)
            bot.send_message(message.chat.id, hint, reply_markup=markup)

        bot.add_custom_filter(custom_filters.StateFilter(bot))
        bot.infinity_polling(skip_pending=True)

        conn.commit()

except Exception as e:
    print(f"Произошла ошибка: {e}")

finally:
    conn.close()
