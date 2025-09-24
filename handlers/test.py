import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.utils import get_quiz_options
from database import save_test_result, update_last_active, get_user_stats, update_user_best_test_time
from keyboards import main_menu_keyboard, quiz_options_keyboard
from utils.word_manager import word_manager # Импортируем word_manager
from aiogram import Bot # Добавлено для явной передачи bot
from config import TEST_QUESTIONS_COUNT
from utils.audio_cleanup import cleanup_guess_audio
import datetime
import asyncio
import logging

router = Router()

class TestKnowledge(StatesGroup):
    in_test = State()
    question_num = State()
    correct_answers = State()

@router.message(F.text == "📝 Тест знаний")
async def start_test(message: Message, state: FSMContext, bot: Bot):
    # Удаляем аудиофайлы из игры "Угадай слово" при переходе к тесту
    await cleanup_guess_audio(message, state, bot)
    user_id = str(message.from_user.id)
    logging.info(f"[handlers/test.py] Starting test for user ID: {user_id}")
    await update_last_active(int(user_id))
    
    words = word_manager.load_words(int(user_id)) # Cast user_id to int
    
    logging.info(f"[handlers/test.py] Loaded {len(words)} words for user {user_id} from file: {word_manager.get_user_current_file(int(user_id))}") # Added logging
    
    # Определяем количество вопросов для теста
    num_questions = min(len(words), TEST_QUESTIONS_COUNT)

    if not words:
        await message.answer("В выбранном наборе слов нет слов для проведения теста. Пожалуйста, выберите другой набор или добавьте слова.", reply_markup=main_menu_keyboard)
        await state.clear()
        return

    if num_questions == 0:
        await message.answer("В выбранном наборе слов недостаточно слов для проведения теста. Пожалуйста, выберите другой набор или добавьте слова.", reply_markup=main_menu_keyboard)
        await state.clear()
        return

    await state.set_state(TestKnowledge.in_test)
    await state.update_data(
        user_id=user_id,
        question_num=0,
        correct_answers=0,
        num_questions=num_questions, # Сохраняем актуальное количество вопросов
        test_words=random.sample(words, num_questions),
        all_words=words,
        test_sent_message_ids=[],
        start_time=datetime.datetime.now() # Добавляем время начала теста
    )
    
    await message.answer("Результаты вашего теста будут отображаться в статистике только после его завершения!")
    current_word_set_name = word_manager.get_user_current_file(int(user_id))
    await message.answer(f"Начинаем тест! Ответьте на {num_questions} вопросов из набора '{current_word_set_name}' в котором {len(words)} слов.")
    await send_test_question(message, state)

async def send_test_question(message: Message, state: FSMContext):
    state_data = await state.get_data()
    question_num = state_data['question_num']
    test_words = state_data['test_words']
    words = state_data['all_words']
    actual_num_questions = state_data['num_questions'] # Получаем актуальное количество вопросов
    # Delete previously sent test messages (to keep chat clean)
    previous_ids = state_data.get('test_sent_message_ids', [])
    if previous_ids:
        try:
            # brief delay to ensure previous UI is visible before removal
            await asyncio.sleep(0.5)
            from aiogram import Bot
            bot = Bot.get_current()
            if bot:
                for mid in previous_ids:
                    try:
                        await bot.delete_message(chat_id=message.chat.id, message_id=mid)
                    except Exception:
                        pass
        except Exception:
            pass

    if question_num < actual_num_questions:
        current_word_data = test_words[question_num]
        english_word = current_word_data['en']
        russian_translation = current_word_data['ru']
        
        options = get_quiz_options(russian_translation, words)
        
        await state.update_data(
            current_test_word_ru=russian_translation, 
            current_test_word_en=english_word,
            quiz_options=options # Сохраняем опции в состоянии
        )

        word_msg = await message.answer(
            f"Вопрос {question_num + 1}/{actual_num_questions}: *{english_word}*",
            reply_markup=main_menu_keyboard, # Keep main menu visible
            parse_mode="Markdown"
        )
        options_msg = await message.answer(
            "Выберите перевод:",
            reply_markup=quiz_options_keyboard(options, russian_translation),
            parse_mode="Markdown"
        )
        await state.update_data(test_sent_message_ids=[word_msg.message_id, options_msg.message_id])
    else:
        await finish_test(message, state)

@router.callback_query(F.data.startswith("quiz_answer_"), TestKnowledge.in_test)
async def process_test_answer(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split('_')
    chosen_option_index = int(data[2]) # Индекс выбранной опции
    
    state_data = await state.get_data()
    question_num = state_data['question_num']
    correct_answers = state_data['correct_answers']
    correct_russian_word = state_data['current_test_word_ru']
    english_word = state_data['current_test_word_en']
    quiz_options = state_data['quiz_options'] # Получаем опции из состояния
    actual_num_questions = state_data['num_questions'] # Получаем актуальное количество вопросов

    chosen_answer = quiz_options[chosen_option_index]
    is_correct = (chosen_answer == correct_russian_word) # Определяем правильность ответа

    if is_correct:
        correct_answers += 1
        answer_feedback = "✅ Верно!"
    else:
        answer_feedback = f"❌ Неверно. Правильный ответ: *{correct_russian_word}*"
    
    await callback.message.edit_text(
        f"Вопрос {question_num + 1}/{actual_num_questions}: *{english_word}*"
        f"\nВаш ответ: *{chosen_answer}* - {answer_feedback}",
        parse_mode="Markdown"
    )

    question_num += 1
    await state.update_data(question_num=question_num, correct_answers=correct_answers)

    if question_num < actual_num_questions:
        await send_test_question(callback.message, state)
    else:
        await finish_test(callback.message, state)
    
    await callback.answer() # Close the processing of the callback query

@router.message(F.text == "⬆️ В главное меню", TestKnowledge.in_test)
async def back_to_main_from_test(message: Message, state: FSMContext):
    # Clean up any lingering test messages
    state_data = await state.get_data()
    previous_ids = state_data.get('test_sent_message_ids', [])
    if previous_ids:
        try:
            await asyncio.sleep(0.1) # Small delay to ensure UI updates
            bot = message.bot
            if bot:
                for mid in previous_ids:
                    try:
                        await bot.delete_message(chat_id=message.chat.id, message_id=mid)
                    except Exception:
                        pass
        except Exception:
            pass
    
    await state.clear()
    await message.answer("Вы вернулись в главное меню.", reply_markup=main_menu_keyboard)

async def finish_test(message: Message, state: FSMContext):
    state_data = await state.get_data()
    correct_answers = state_data['correct_answers']
    user_id = state_data['user_id']
    start_time = state_data['start_time'] # Получаем время начала
    actual_num_questions = state_data['num_questions'] # Получаем актуальное количество вопросов
    test_duration = (datetime.datetime.now() - start_time).total_seconds() # Рассчитываем продолжительность

    # Clean up last question messages if any
    try:
        previous_ids = state_data.get('test_sent_message_ids', [])
        if previous_ids:
            await asyncio.sleep(0.5)
            from aiogram import Bot
            bot = Bot.get_current()
            if bot:
                for mid in previous_ids:
                    try:
                        await bot.delete_message(chat_id=message.chat.id, message_id=mid)
                    except Exception:
                        pass
    except Exception:
        pass

    # Get the current word set name
    current_word_set = word_manager.get_user_current_file(int(user_id))
    await save_test_result(int(user_id), correct_answers, actual_num_questions, word_set_name=current_word_set)

    # Fetch updated stats to compare best_test_time
    current_user_stats = await get_user_stats(int(user_id))
    current_best_test_time = current_user_stats.get('best_test_time', float('inf'))
    
    if test_duration < current_best_test_time:
        await update_user_best_test_time(int(user_id), test_duration)
    
    # update_last_active is called at the start of the test, and save_test_result updates best_test_score.
    # So, no need to manually update these here again.

    await message.answer(
        f"Тест завершен! Вы ответили правильно на *{correct_answers}* из *{actual_num_questions}* вопросов.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard
    )
    await state.clear()
