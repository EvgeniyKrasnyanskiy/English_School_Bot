import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.utils import get_random_word, shuffle_word, get_quiz_options
import uuid
from database import update_last_active
from keyboards import games_menu_keyboard, main_menu_keyboard, quiz_options_keyboard, start_recall_typing_keyboard
from utils.data_manager import update_game_stats
import datetime
from handlers.stats import show_statistics_handler # Import the function for unified stats display
import asyncio
from config import RECALL_TYPING_COUNTDOWN_SECONDS # Import countdown seconds
from utils.audio_cleanup import cleanup_guess_audio
from aiogram import Bot # Добавлено для явной передачи bot
from utils.word_manager import word_manager # Импортируем word_manager
from config import TEST_QUESTIONS_COUNT

router = Router()

class Games(StatesGroup):
    in_games_menu = State()
    quiz_choose_translation = State()
    quiz_build_word = State()
    quiz_find_missing_letter = State() # New state for 'Find Missing Letter' game
    quiz_recall_typing = State() # New state for 'Recall Typing' game
    quiz_guess_word = State() # New state for 'Guess the Word' game

@router.message(F.text == "🎮 Игры")
async def cmd_games(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    await state.set_state(Games.in_games_menu)
    await state.update_data(user_id=user_id)
    await message.answer("Выберите игру:", reply_markup=games_menu_keyboard)
# --- Guess the Word (by Audio) ---
@router.message(F.text == "🎧 Угадай слово", Games.in_games_menu)
async def start_guess_word_game(message: Message, state: FSMContext):
    user_id = message.from_user.id
    words = word_manager.load_words(user_id)
    await state.set_state(Games.quiz_guess_word)
    await state.update_data(user_id=user_id, all_words=words)
    await message.answer("Прослушайте аудио и угадайте слово.")
    await send_guess_word_question(message, state)

async def send_guess_word_question(message: Message, state: FSMContext):
    state_data = await state.get_data()
    words = state_data['all_words']
    word = get_random_word(words)

    # Build 3 distractors in Russian, 1 correct in Russian
    options = get_quiz_options(word['ru'], words)

    # Save current word and options for later validation
    await state.update_data(
        current_guess_word_en=word['en'],
        current_guess_word_ru=word['ru'],
        quiz_options=options
    )

    # Try to send audio for the word if exists via data_manager like in learn
    from aiogram.types import FSInputFile
    from utils.data_manager import get_audio_filepath
    audio_path = await get_audio_filepath(word['en'])
    if audio_path:
        obfuscated_filename = f"{uuid.uuid4().hex}.mp3"
        sent_audio = await message.answer_audio(
            audio=FSInputFile(audio_path, filename=obfuscated_filename),
            title="Задание",
            performer="",
        )
        # Re-fetch state data to ensure we have the most up-to-date list of audio IDs
        current_audio_ids = (await state.get_data()).get("guess_sent_audio_ids", [])
        current_audio_ids.append(sent_audio.message_id)
        await state.update_data(guess_sent_audio_ids=current_audio_ids)
    else:
        await message.answer("Извините, для этого слова аудиофайл не найден. Пожалуйста, выберите другую игру. Вы также можете поучавствовать в наполнении базы озвученных слов, используя команду /new_sound. Слово будет добавлено сразу после проверки администратором (~24 часа).",
                             reply_markup=main_menu_keyboard)
        await state.clear()
        return # Прекращаем выполнение функции, так как аудиофайла нет

    await message.answer(
        "Выберите правильный перевод на русский:",
        reply_markup=quiz_options_keyboard(options, word['ru']),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("quiz_answer_"), Games.quiz_guess_word)
async def process_guess_word_answer(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split('_')
    # The index of the chosen option is at data[2], and is_correct flag is at data[3]
    chosen_option_index = int(data[2])
    is_correct_flag = data[3]

    state_data = await state.get_data()
    user_id = state_data['user_id']
    correct_english_word = state_data['current_guess_word_en']
    correct_russian_word = state_data['current_guess_word_ru']
    quiz_options = state_data['quiz_options']
    current_date = datetime.datetime.now().isoformat()

    chosen_answer = quiz_options[chosen_option_index] # Get the actual text of the chosen answer
    is_correct = (chosen_answer == correct_russian_word)

    if is_correct:
        await callback.answer("Верно!", show_alert=False)
        await callback.message.edit_text(
            f"Слово по аудио: *{correct_english_word}*\nВаш ответ: *{chosen_answer}* - ✅ Верно!",
            parse_mode="Markdown"
        )
        current_word_set = word_manager.get_user_current_file(int(user_id))
        await update_game_stats(int(user_id), "guess_word", True, current_date, word_set_name=current_word_set)
    else:
        await callback.answer("Неверно.", show_alert=False)
        await callback.message.edit_text(
            f"Слово по аудио: *{correct_english_word}*\nВаш ответ: *{chosen_answer}* - ❌ Неверно. Правильный ответ: *{correct_russian_word}*",
            parse_mode="Markdown"
        )
        current_word_set = word_manager.get_user_current_file(int(user_id))
        await update_game_stats(int(user_id), "guess_word", False, current_date, word_set_name=current_word_set)

    await callback.message.answer(
        "Хотите еще раз сыграть?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Нет, завершить", callback_data="finish_game_show_stats"),
             InlineKeyboardButton(text="Да, еще раз!", callback_data="play_guess_word_again")]
        ])
    )
    '''
    await callback.message.answer(
        "Или вернитесь в главное меню.",
        reply_markup=main_menu_keyboard
    )
    '''

@router.callback_query(F.data == "play_guess_word_again", Games.quiz_guess_word)
async def play_guess_word_again(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    state_data = await state.get_data()
    user_id = state_data['user_id']
    await update_last_active(int(user_id))
    await cleanup_guess_audio(callback.message, state, bot) # Удаляем предыдущий аудиофайл
    await state.set_state(Games.quiz_guess_word) # Добавлено: Явно устанавливаем состояние
    await send_guess_word_question(callback.message, state)

# --- Choose Translation Quiz ---
@router.message(F.text == "🤔 Выбери перевод", Games.in_games_menu)
async def start_choose_translation_quiz(message: Message, state: FSMContext):
    user_id = message.from_user.id
    words = word_manager.load_words(user_id)
    await state.set_state(Games.quiz_choose_translation)
    await state.update_data(user_id=user_id, all_words=words)
    await message.answer("Выберите правильный перевод слова.")
    await send_choose_translation_question(message, state)

async def send_choose_translation_question(message: Message, state: FSMContext):
    state_data = await state.get_data()
    words = state_data['all_words']
    word = get_random_word(words)
    options = get_quiz_options(word['ru'], words)
    
    await state.update_data(
        current_quiz_word_en=word['en'],
        current_quiz_word_ru=word['ru'],
        quiz_options=options # Store options for later validation
    )

    await message.answer(
        f"Слово: *{word['en']}*",
        reply_markup=main_menu_keyboard, # Keep main menu visible
        parse_mode="Markdown"
    )
    await message.answer(
        "Выберите перевод:",
        reply_markup=quiz_options_keyboard(options, word['ru']),
        parse_mode="Markdown"
    )

@router.message(F.text == "📊 Статистика", Games.quiz_choose_translation)
async def handle_stats_button_in_choose_translation(message: Message, state: FSMContext, bot: Bot):
    # Удаляем аудиофайлы из игры "Угадай слово" перед переходом к статистике
    await cleanup_guess_audio(message, state, bot)
    await state.clear()
    await message.answer("Вы вернулись в главное меню.", reply_markup=main_menu_keyboard)


@router.callback_query(F.data.startswith("quiz_answer_"), Games.quiz_choose_translation)
async def process_choose_translation_answer(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split('_')
    # The index of the chosen option is at data[2], and is_correct flag is at data[3]
    chosen_option_index = int(data[2])
    is_correct_flag = data[3]
    
    state_data = await state.get_data()
    user_id = state_data['user_id']
    correct_russian_word = state_data['current_quiz_word_ru']
    english_word = state_data['current_quiz_word_en']
    quiz_options = state_data['quiz_options'] # Get options from state
    current_date = datetime.datetime.now().isoformat()

    chosen_answer = quiz_options[chosen_option_index] # Get the actual text of the chosen answer
    is_correct = (chosen_answer == correct_russian_word)

    if is_correct:
        await callback.answer("Верно!", show_alert=False)
        await callback.message.edit_text(
            f"Слово: *{english_word}*"
            f"\nВаш ответ: *{chosen_answer}* - ✅ Верно!",
            parse_mode="Markdown"
        )
        current_word_set = word_manager.get_user_current_file(int(user_id))
        await update_game_stats(int(user_id), "choose_translation", True, current_date, word_set_name=current_word_set)
    else:
        await callback.answer("Неверно.", show_alert=False)
        await callback.message.edit_text(
            f"Слово: *{english_word}*"
            f"\nВаш ответ: *{chosen_answer}* - ❌ Неверно. Правильный ответ: *{correct_russian_word}*",
            parse_mode="Markdown"
        )
        current_word_set = word_manager.get_user_current_file(int(user_id))
        await update_game_stats(int(user_id), "choose_translation", False, current_date, word_set_name=current_word_set)
    
    await callback.message.answer(
        "Хотите еще раз сыграть?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Нет, завершить", callback_data="finish_game_show_stats"),
             InlineKeyboardButton(text="Да, еще раз!", callback_data="play_choose_translation_again")]
        ])
    )

@router.callback_query(F.data == "play_choose_translation_again", Games.quiz_choose_translation)
async def play_choose_translation_again(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    state_data = await state.get_data()
    user_id = state_data['user_id']
    await update_last_active(int(user_id))
    await send_choose_translation_question(callback.message, state)

# --- Build Word Quiz ---
@router.message(F.text == "🧩 Собери слово", Games.in_games_menu)
async def start_build_word_quiz(message: Message, state: FSMContext):
    user_id = message.from_user.id
    words = word_manager.load_words(user_id)
    await state.set_state(Games.quiz_build_word)
    await state.update_data(user_id=user_id, all_words=words)
    await message.answer(
        "Я покажу тебе перемешанные буквы. Собери из них английское слово. "
        "Введи слово полностью.",
        reply_markup=main_menu_keyboard # Keep main menu visible
    )
    await send_build_word_question(message, state)

@router.message(F.text == "🔍 Найди букву", Games.in_games_menu)
async def start_find_missing_letter_quiz(message: Message, state: FSMContext):
    user_id = message.from_user.id
    words = word_manager.load_words(user_id)
    await state.set_state(Games.quiz_find_missing_letter)
    await state.update_data(user_id=user_id, all_words=words)
    await message.answer(
        "Я покажу тебе слово с пропущенной буквой. Выбери правильную букву.",
        reply_markup=main_menu_keyboard # Keep main menu visible
    )
    await send_find_missing_letter_question(message, state)

async def send_find_missing_letter_question(message: Message, state: FSMContext):
    state_data = await state.get_data()
    words = state_data['all_words']
    word_data = get_random_word(words)
    english_word = word_data['en']
    russian_translation = word_data['ru']

    if len(english_word) < 2:
        # Skip words too short to hide a letter meaningfully
        await send_find_missing_letter_question(message, state) # Try again with a different word
        return

    missing_index = random.randint(0, len(english_word) - 1)
    missing_letter = english_word[missing_index]
    displayed_word = english_word[:missing_index] + "_" + english_word[missing_index+1:]

    # Generate options for the missing letter
    options = [missing_letter]
    alphabet = 'abcdefghijklmnopqrstuvwxyz'
    while len(options) < 4:
        random_letter = random.choice(alphabet)
        if random_letter not in options:
            options.append(random_letter)
    random.shuffle(options)

    await state.update_data(current_missing_word_en=english_word, 
                             current_missing_word_ru=russian_translation, 
                             correct_missing_letter=missing_letter,
                             quiz_options=options # Store options for later validation
    )

    await message.answer(
        f"Какая буква пропущена в слове: *{displayed_word.lower()}*" 
        f"\nПодсказка: это слово означает '{russian_translation}'",
        reply_markup=main_menu_keyboard, # Keep main menu visible
        parse_mode="Markdown"
    )
    await message.answer(
        "Выберите пропущенную букву:",
        reply_markup=quiz_options_keyboard(options, missing_letter), # Reusing quiz_options_keyboard
        parse_mode="Markdown"
    )

async def send_build_word_question(message: Message, state: FSMContext):
    state_data = await state.get_data()
    words = state_data['all_words']
    word = get_random_word(words)
    shuffled = shuffle_word(word['en'])
    
    await state.update_data(current_build_word_en=word['en'], current_build_word_ru=word['ru'])
    
    await message.answer(
        f"Перемешанные буквы: *{shuffled.lower()}*"
        f"\nПодсказка: это слово означает '{word['ru']}'",
        reply_markup=main_menu_keyboard, # Keep main menu visible
        parse_mode="Markdown"
    )
    await message.answer(
        "Введите слово полностью:",
        reply_markup=None, # No inline keyboard needed for text input
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("quiz_answer_"), Games.quiz_find_missing_letter)
async def process_find_missing_letter_answer(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split('_')
    # The index of the chosen option is at data[2], and is_correct flag is at data[3]
    chosen_option_index = int(data[2])
    is_correct_flag = data[3]

    state_data = await state.get_data()
    user_id = state_data['user_id']
    correct_english_word = state_data['current_missing_word_en']
    russian_translation = state_data['current_missing_word_ru']
    correct_missing_letter = state_data['correct_missing_letter']
    quiz_options = state_data['quiz_options'] # Get options from state
    current_date = datetime.datetime.now().isoformat()

    chosen_answer = quiz_options[chosen_option_index] # Get the actual text of the chosen answer
    is_correct = (chosen_answer == correct_missing_letter)

    if is_correct:
        await callback.answer("Верно!", show_alert=False)
        await callback.message.edit_text(
            f"Слово: *{correct_english_word}* (пропущена: '{correct_missing_letter}')"
            f"\nВаш ответ: *{chosen_answer}* - ✅ Верно!",
            parse_mode="Markdown"
        )
        current_word_set = word_manager.get_user_current_file(int(user_id))
        await update_game_stats(int(user_id), "find_missing_letter", True, current_date, word_set_name=current_word_set)
    else:
        await callback.answer("Неверно.", show_alert=False)
        await callback.message.edit_text(
            f"Слово: *{correct_english_word}* (пропущена: '{correct_missing_letter}')"
            f"\nВаш ответ: *{chosen_answer}* - ❌ Неверно. Правильная буква: *{correct_missing_letter}*",
            parse_mode="Markdown"
        )
        current_word_set = word_manager.get_user_current_file(int(user_id))
        await update_game_stats(int(user_id), "find_missing_letter", False, current_date, word_set_name=current_word_set)

    await callback.message.answer(
        "Хотите еще раз сыграть?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Нет, завершить", callback_data="finish_game_show_stats"),
             InlineKeyboardButton(text="Да, еще раз!", callback_data="play_find_missing_letter_again")]
        ])
    )

@router.message(Games.quiz_build_word)
async def process_build_word_answer(message: Message, state: FSMContext):
    user_answer = message.text.lower().strip()
    
    state_data = await state.get_data()
    user_id = state_data['user_id']
    correct_english_word = state_data['current_build_word_en']
    russian_translation = state_data['current_build_word_ru']
    current_date = datetime.datetime.now().isoformat()

    if user_answer == "в главное меню" or user_answer == "📊 Статистика":
        await state.clear()
        await message.answer("Вы вернулись в главное меню.", reply_markup=main_menu_keyboard)
        return
    
    if user_answer == correct_english_word:
        await message.answer(
            f"✅ Верно! Слово: *{correct_english_word.capitalize()}* (перевод: *{russian_translation}*)",
            parse_mode="Markdown"
        )
        current_word_set = word_manager.get_user_current_file(int(user_id))
        await update_game_stats(int(user_id), "build_word", True, current_date, word_set_name=current_word_set)
    else:
        await message.answer(
            f"❌ Неверно. Попробуй еще раз или введи другое слово."
            f"Правильный ответ: *{correct_english_word.capitalize()}* (перевод: *{russian_translation}*)",
            parse_mode="Markdown"
        )
        current_word_set = word_manager.get_user_current_file(int(user_id))
        await update_game_stats(int(user_id), "build_word", False, current_date, word_set_name=current_word_set)
    
    await message.answer(
        "Хотите сыграть еще раз?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Нет, завершить", callback_data="finish_game_show_stats"),
             InlineKeyboardButton(text="Да, еще раз!", callback_data="play_build_word_again")]
        ])
    )

@router.callback_query(F.data == "play_build_word_again", Games.quiz_build_word)
async def play_build_word_again(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    state_data = await state.get_data()
    user_id = state_data['user_id']
    await update_last_active(int(user_id))
    await send_build_word_question(callback.message, state)


# --- Common Game Menu Navigation ---
@router.callback_query(F.data == "back_to_games_menu", Games.quiz_choose_translation)
@router.callback_query(F.data == "back_to_games_menu", Games.quiz_build_word)
async def back_to_games_menu_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(Games.in_games_menu)
    await callback.message.answer("Вы вернулись в меню игр.", reply_markup=games_menu_keyboard)

@router.callback_query(F.data == "finish_game_show_stats")
async def finish_game_and_show_stats(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    state_data = await state.get_data()
    user_id = state_data['user_id']
    await cleanup_guess_audio(callback.message, state, bot) # Добавлено: Очищаем аудиофайлы игры "Угадай слово"
    await update_last_active(int(user_id))
    # Вместо get_formatted_statistics, вызываем show_statistics_handler для унификации
    await callback.message.answer("Игра завершена. Вы можете посмотреть свою статистику в главном меню.", reply_markup=main_menu_keyboard)
    await state.clear() # Очищаем состояние после отображения статистики

@router.callback_query(F.data == "play_find_missing_letter_again", Games.quiz_find_missing_letter)
async def play_find_missing_letter_again(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    state_data = await state.get_data()
    user_id = state_data['user_id']
    await update_last_active(int(user_id))
    await send_find_missing_letter_question(callback.message, state)

@router.callback_query(F.data == "play_recall_typing_again", Games.quiz_recall_typing)
async def play_recall_typing_again(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    state_data = await state.get_data()
    user_id = state_data['user_id']
    await update_last_active(int(user_id))
    await send_recall_typing_question(callback.message, state)

@router.callback_query(F.data == "start_recall_typing_countdown", Games.quiz_recall_typing)
async def start_recall_typing_countdown(callback: CallbackQuery, state: FSMContext):
    await callback.answer() # Acknowledge the callback query
    # Edit the message to show the countdown
    countdown_message = await callback.message.edit_text(
        f"Приготовьтесь! Игра начнется через {(RECALL_TYPING_COUNTDOWN_SECONDS + 3)} секунд...",
        reply_markup=None
    )

    for i in range(int(RECALL_TYPING_COUNTDOWN_SECONDS + 2) - 1, 0, -1):
        await countdown_message.edit_text(f"Приготовьтесь! Игра начнется через {i} секунд...")
        await asyncio.sleep(1)
    
    await countdown_message.delete() # Remove countdown message
    await send_recall_typing_question(callback.message, state) # Start the actual game question

@router.message(F.text == "📝 Ввод по памяти", Games.in_games_menu)
async def start_recall_typing_quiz(message: Message, state: FSMContext):
    user_id = message.from_user.id
    words = word_manager.load_words(user_id)
    await state.set_state(Games.quiz_recall_typing)
    await state.update_data(user_id=user_id, all_words=words)
    await message.answer(
        "Я покажу вам слово с переводом, затем вы должны будете ввести его по памяти.\n\nНажмите 'Начать', когда будете готовы.",
        reply_markup=start_recall_typing_keyboard
    )

async def send_recall_typing_question(message: Message, state: FSMContext):
    state_data = await state.get_data()
    words = state_data['all_words']
    word_data = get_random_word(words)
    english_word = word_data['en']
    russian_translation = word_data['ru']

    # Store the start time and the correct word for comparison BEFORE sending/deleting message
    await state.update_data(
        current_recall_word_en=english_word,
        current_recall_word_ru=russian_translation,
        question_start_time=datetime.datetime.now().isoformat()
    )

    # Send the word with translation, then delete it after a short delay
    prompt_message = await message.answer(
        f"Запомните: *{english_word}* ({russian_translation})",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard # Keep main menu visible
    )
    await asyncio.sleep(3) # Display for 3 seconds
    await prompt_message.delete()

    await message.answer(
        "Введите английское слово по памяти:",
        reply_markup=None, # No inline keyboard for text input
        parse_mode="Markdown"
    )

@router.message(Games.quiz_recall_typing)
async def process_recall_typing_answer(message: Message, state: FSMContext):
    user_answer = message.text.lower().strip()

    state_data = await state.get_data()
    user_id = state_data['user_id']
    correct_english_word = state_data['current_recall_word_en']
    russian_translation = state_data['current_recall_word_ru']
    question_start_time_str = state_data['question_start_time']
    current_date = datetime.datetime.now().isoformat()

    question_start_time = datetime.datetime.fromisoformat(question_start_time_str)
    time_taken = (datetime.datetime.now() - question_start_time).total_seconds()

    if user_answer == "в главное меню" or user_answer == "📊 статистика":
        await state.clear()
        await message.answer("Вы вернулись в главное меню.", reply_markup=main_menu_keyboard)
        return

    is_correct = (user_answer == correct_english_word.lower())
    
    feedback_text = ""
    if is_correct:
        feedback_text = (
            f"✅ Верно! Слово: *{correct_english_word.capitalize()}* (перевод: *{russian_translation}*)\n"
            f"Время ответа: *{time_taken:.2f}* секунд."
        )
        current_word_set = word_manager.get_user_current_file(int(user_id))
        await update_game_stats(int(user_id), "recall_typing", True, current_date, time_taken=time_taken, word_set_name=current_word_set)
    else:
        feedback_text = (
            f"❌ Неверно. Правильное слово: *{correct_english_word.capitalize()}* (перевод: *{russian_translation}*)\n"
            f"Ваш ответ: *{user_answer}*"
        )
        current_word_set = word_manager.get_user_current_file(int(user_id))
        await update_game_stats(int(user_id), "recall_typing", False, current_date, word_set_name=current_word_set)
    
    await message.answer(feedback_text, parse_mode="Markdown")

    await message.answer(
        "Хотите еще раз сыграть?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Нет, завершить", callback_data="finish_game_show_stats"),
             InlineKeyboardButton(text="Да, еще раз!", callback_data="play_recall_typing_again")]
        ])
    )

@router.message(F.text == "⬆️ В главное меню", Games.in_games_menu)
async def back_to_main_from_games(message: Message, state: FSMContext):
    # Удаляем аудиофайлы из игры "Угадай слово" перед возвратом в главное меню
    #await cleanup_guess_audio(message, state, message.bot)
    await state.clear()
    await message.answer("Вы вернулись в главное меню.", reply_markup=main_menu_keyboard)

@router.message(F.text == "⬆️ В главное меню", Games.quiz_guess_word)
async def back_to_main_from_guess_word_game_specific(message: Message, state: FSMContext, bot: Bot):
    # Удаляем аудиофайлы из игры "Угадай слово" перед возвратом в главное меню
    await cleanup_guess_audio(message, state, bot)
    await state.clear()
    await message.answer("Вы вернулись в главное меню.", reply_markup=main_menu_keyboard)
