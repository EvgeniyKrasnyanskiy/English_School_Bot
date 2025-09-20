from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import logging
from database import update_last_active
from keyboards import main_menu_keyboard
from utils.data_manager import load_stats, calculate_overall_score_and_rank
from aiogram import Bot # Добавлено для явной передачи bot
from config import TEST_QUESTIONS_COUNT
import datetime
from utils.audio_cleanup import cleanup_guess_audio

GAME_NAMES_RU = {
    "choose_translation": "*Выбери перевод*",
    "build_word": "*Собери слово*",
    "find_missing_letter": "*Найди букву*", # New game
    "recall_typing": "*Ввод по памяти*", # New game
    "guess_word": "*Угадай слово*", # New game (audio)
}

router = Router()

# async def get_formatted_statistics(user_id: str) -> str:
#     logging.info(f"[handlers/stats.py] Getting formatted stats for User ID: {user_id}")
#     all_stats = await load_stats()
#     stats = all_stats.get(user_id)
#
#     if stats:
#         last_activity_date = stats.get('last_activity_date')
#         formatted_last_activity_date = 'N/A'
#         if last_activity_date:
#             try:
#                 last_activity_datetime = datetime.datetime.fromisoformat(last_activity_date)
#                 formatted_last_activity_date = last_activity_datetime.strftime("%d.%m.%y в %H:%M")
#             except ValueError:
#                 formatted_last_activity_date = last_activity_date
#         else:
#             formatted_last_activity_date = last_activity_date
#
#         # Calculate ranking
#         user_ranks = await calculate_overall_score_and_rank()
#         current_user_rank_info = next((u for u in user_ranks if u['user_id'] == user_id), None)
#
#         stats_text = (
#             "📊 *Ваша статистика:*\n"
#             f"✅ Кол-во верных ответов в тестах: *{stats.get('total_correct_answers', 0)}*\n"
#             f"🏆 Лучший результат теста: *{stats.get('best_test_score', 0)}* из {TEST_QUESTIONS_COUNT}\n"
#             f"🗓️ Последняя активность: *{formatted_last_activity_date}*"
#         )
#
#         if current_user_rank_info:
#             stats_text += (
#                 f"\n\n⭐ *Ваш рейтинг: {current_user_rank_info['rank']} место* (Очки: {current_user_rank_info['overall_score']:.2f})\n"
#             )
#
#         if 'games_stats' in stats:
#             stats_text += "\n🎮 *Статистика по играм:*\n"
#             for game_type, game_data in stats['games_stats'].items():
#                 game_name = GAME_NAMES_RU.get(game_type, game_type.replace("_", " ").title())
#                 stats_text += (
#                     f"  • {game_name}:\n"
#                     f"    - Сыграно: *{game_data['played']}*\n"
#                     f"    - Правильных ответов: *{game_data['correct']}*\n"
#                     f"    - Неправильных ответов: *{game_data['incorrect']}*\n"
#                 )
#                 if game_type == "recall_typing" and 'best_time' in game_data and game_data['best_time'] is not None:
#                     stats_text += f"    - Лучшее время: *{game_data['best_time']:.2f}* сек.\n"
#                 stats_text += "\n"
#     else:
#         stats_text = "У вас пока нет статистики. Начните проходить тесты и играть в игры!"
#     return stats_text

@router.message(F.text == "📊 Статистика")
async def show_statistics_handler(message: Message, state: FSMContext, bot: Bot):
    await cleanup_guess_audio(message, state, bot)
    user_id = str(message.from_user.id)
    await update_last_active(int(user_id))
    user_stats = await load_stats() # Загружаем всю статистику
    user_stats = user_stats.get(user_id, {}) # Получаем статистику для текущего пользователя

    user_name_display = message.from_user.username if message.from_user.username else message.from_user.full_name

    total_correct_answers = user_stats.get('total_correct_answers', 0)
    best_test_score = user_stats.get('best_test_score', 0)
    last_activity_date = user_stats.get('last_activity_date', "N/A")
    best_test_time = user_stats.get('best_test_time', float('inf'))

    # Format total_correct_answers display
    total_correct_answers_display = str(total_correct_answers) if total_correct_answers > 0 else "не пройден"

    # Format best_test_score display
    best_test_score_display = f"{best_test_score} из {TEST_QUESTIONS_COUNT}" if best_test_score > 0 else "не пройден"

    # Format best_test_time display
    best_test_time_display = f"{best_test_time:.2f} сек." if best_test_time != float('inf') else "не пройден"

    # Calculate ranking
    user_ranks = await calculate_overall_score_and_rank()
    current_user_rank_info = next((u for u in user_ranks if u['user_id'] == user_id), None)
    
    rank_text = ""
    if current_user_rank_info:
        rank_text = f"\n⭐ *Ваш рейтинг: {current_user_rank_info['rank']} место* (Очки: {current_user_rank_info['overall_score']:.2f})\n"

    stats_text = (
        f"📊 *Ваша статистика, {user_name_display}:*\n"
    )

    stats_text += rank_text # Добавляем информацию о рейтинге сразу после "Ваша статистика"

    stats_text += (
        f"\n📝 *Тест знаний:*\n"
        f"   Всего правильных ответов: `{total_correct_answers_display}`\n"
        f"   Лучший результат теста: `{best_test_score_display}`\n"
        f"   Лучшее время теста: `{best_test_time_display}`\n\n"
        f"🎮 *Игры:*\n"
    )

    if 'games_stats' in user_stats:
        for game_type, game_data in user_stats['games_stats'].items():
            game_name = GAME_NAMES_RU.get(game_type, game_type.replace("_", " ").title())
            stats_text += (
                f"  • {game_name}:\n"
                f"    - Сыграно: *{game_data['played']}*\n"
                f"    - Правильных ответов: *{game_data['correct']}*\n"
                f"    - Неправильных ответов: *{game_data['incorrect']}*\n"
            )
            if game_type == "recall_typing" and 'best_time' in game_data and game_data['best_time'] is not None:
                stats_text += f"    - Лучшее время: *{game_data['best_time']:.2f}* сек.\n"
            stats_text += "\n"

    await message.answer(stats_text, reply_markup=main_menu_keyboard, parse_mode="Markdown")
