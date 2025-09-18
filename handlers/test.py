import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.utils import load_words, get_quiz_options
from database import save_test_result, update_last_active
from keyboards import main_menu_keyboard, quiz_options_keyboard
from utils.data_manager import load_stats, update_user_stats
from config import TEST_QUESTIONS_COUNT
import datetime
import asyncio
import logging

router = Router()

class TestKnowledge(StatesGroup):
    in_test = State()
    question_num = State()
    correct_answers = State()

@router.message(F.text == "📝 Проверка знаний")
async def start_knowledge_test(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    logging.info(f"[handlers/test.py] Starting test for user ID: {user_id}")
    await update_last_active(int(user_id))
    
    words = load_words()
    await state.set_state(TestKnowledge.in_test)
    await state.update_data(
        user_id=user_id,
        question_num=0,
        correct_answers=0,
        test_words=random.sample(words, TEST_QUESTIONS_COUNT),
        all_words=words,
        test_sent_message_ids=[]
    )
    
    await message.answer(f"Начинаем тест! Ответьте на {TEST_QUESTIONS_COUNT} вопросов.")
    await send_test_question(message, state)

async def send_test_question(message: Message, state: FSMContext):
    state_data = await state.get_data()
    question_num = state_data['question_num']
    test_words = state_data['test_words']
    words = state_data['all_words']
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

    if question_num < TEST_QUESTIONS_COUNT:
        current_word_data = test_words[question_num]
        english_word = current_word_data['en']
        russian_translation = current_word_data['ru']
        
        options = get_quiz_options(russian_translation, words)
        
        await state.update_data(current_test_word_ru=russian_translation, current_test_word_en=english_word)

        word_msg = await message.answer(
            f"Вопрос {question_num + 1}/{TEST_QUESTIONS_COUNT}: *{english_word}*",
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
    is_correct = data[2] == 'correct'
    chosen_answer = data[3]
    
    state_data = await state.get_data()
    question_num = state_data['question_num']
    correct_answers = state_data['correct_answers']
    correct_russian_word = state_data['current_test_word_ru']
    english_word = state_data['current_test_word_en']

    if is_correct:
        correct_answers += 1
        answer_feedback = "✅ Верно!"
    else:
        answer_feedback = f"❌ Неверно. Правильный ответ: *{correct_russian_word}*"
    
    await callback.message.edit_text(
        f"Вопрос {question_num + 1}/{TEST_QUESTIONS_COUNT}: *{english_word}*"
        f"\nВаш ответ: *{chosen_answer}* - {answer_feedback}",
        parse_mode="Markdown"
    )

    question_num += 1
    await state.update_data(question_num=question_num, correct_answers=correct_answers)

    if question_num < TEST_QUESTIONS_COUNT:
        await send_test_question(callback.message, state)
    else:
        await finish_test(callback.message, state)
    
    await callback.answer() # Close the processing of the callback query

async def finish_test(message: Message, state: FSMContext):
    state_data = await state.get_data()
    correct_answers = state_data['correct_answers']
    user_id = state_data['user_id']
    logging.info(f"[handlers/test.py] Finishing test for user ID from state: {user_id}")

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

    await save_test_result(int(user_id), correct_answers, TEST_QUESTIONS_COUNT)

    all_stats = await load_stats()
    logging.info(f"[handlers/test.py] Loaded all stats before update: {all_stats}")
    user_stats = all_stats.get(user_id, {})
    # Ensure all relevant fields exist with default values if not present
    user_stats.setdefault('total_correct_answers', 0)
    user_stats.setdefault('best_test_score', 0)
    user_stats.setdefault('last_activity_date', "N/A")
    logging.info(f"[handlers/test.py] Existing user stats for {user_id}: {user_stats}")

    user_stats['total_correct_answers'] += correct_answers
    if correct_answers > user_stats['best_test_score']:
        user_stats['best_test_score'] = correct_answers
    user_stats['last_activity_date'] = datetime.datetime.now().isoformat()

    logging.info(f"[handlers/test.py] Updated user stats for {user_id}: {user_stats}")
    await update_user_stats(
        user_id,
        user_stats['total_correct_answers'],
        user_stats['best_test_score'],
        user_stats['last_activity_date']
    )

    await message.answer(
        f"Тест завершен! Вы ответили правильно на *{correct_answers}* из *{TEST_QUESTIONS_COUNT}* вопросов.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard
    )
    await state.clear()
