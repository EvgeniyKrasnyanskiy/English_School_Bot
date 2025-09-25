from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import logging
from database import update_last_active, get_user_stats, get_test_stats_by_word_set, get_game_stats_by_word_set
from keyboards import main_menu_keyboard
from utils.data_manager import calculate_overall_score_and_rank
from aiogram import Bot # Добавлено для явной передачи bot
from config import TEST_QUESTIONS_COUNT
import datetime

GAME_NAMES_RU = {
    "choose_translation": "*Выбери перевод*",
    "build_word": "*Собери слово*",
    "find_missing_letter": "*Найди букву*", # New game
    "recall_typing": "*Ввод по памяти*", # New game
    "guess_word": "*Угадай слово*", # New game (audio)
}

# Используем тот же словарь переводов, что и в admin.py для единообразия
GAME_NAME_TRANSLATIONS = {
    "guess_word": "Угадай слово (по аудио)",
    "choose_translation": "Выбери перевод",
    "build_word": "Собери слово",
    "find_missing_letter": "Найди букву",
    "recall_typing": "Ввод по памяти",
    "test": "Тест знаний",
}


router = Router()


@router.message(F.text == "📊 Статистика")
async def show_statistics_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = int(message.from_user.id)
    await update_last_active(user_id)

    user_name_display = message.from_user.username if message.from_user.username else message.from_user.full_name

    # Получаем общую статистику пользователя
    user_overall_stats = await get_user_stats(user_id)
    
    # Общая статистика по тестам
    total_correct_answers = user_overall_stats.get("total_correct_answers", 0)
    best_test_score = user_overall_stats.get("best_test_score", 0)
    best_test_time = user_overall_stats.get("best_test_time", float("inf"))

    # Форматируем отображение
    total_correct_answers_display = (
        str(total_correct_answers) if total_correct_answers > 0 else "тест не пройден"
    )
    best_test_score_display = (
        f"{best_test_score} из {TEST_QUESTIONS_COUNT}"
        if best_test_score > 0
        else "тест не пройден"
    )
    best_test_time_display = (
        f"{best_test_time:.2f} сек."
        if best_test_time != float("inf") and best_test_time != 999999.0 # Added check for 999999.0
        else "тест не пройден"
    )

    # Общая статистика по играм (для рейтинга)
    total_game_correct = 0
    if "games_stats" in user_overall_stats:
        for game_type, game_data in user_overall_stats["games_stats"].items():
            total_game_correct += game_data.get("correct", 0)

    # Общее количество правильных ответов (ОКПО)
    overall_correct_answers = total_correct_answers + total_game_correct

    # Calculate ranking
    user_ranks = await calculate_overall_score_and_rank()
    current_user_rank_info = next(
        (u for u in user_ranks if int(u['user_id']) == user_id), None
    )

    rank_text = ""
    if current_user_rank_info:
        rank_text = f"\n⭐ *Ваш рейтинг: {current_user_rank_info['rank']} место* (Очки: {current_user_rank_info['overall_score']:.2f})\n"

    stats_text = f"📊 *Ваша статистика, {user_name_display}:*\n"
    stats_text += rank_text
    stats_text += f"🏆 *Количество правильных ответов:* `{overall_correct_answers}`\n"

    # Последняя активность
    last_activity_date_display = "Неизвестно" # Значение по умолчанию
    if "last_activity_date" in user_overall_stats and user_overall_stats["last_activity_date"] != "N/A":
        try:
            # Преобразуем строку ISO в объект datetime
            dt_object = datetime.datetime.fromisoformat(user_overall_stats["last_activity_date"])
            # Форматируем в более читабельный вид (например, '23.09.2025 20:56')
            last_activity_date_display = dt_object.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            last_activity_date_display = user_overall_stats["last_activity_date"] # Если формат не ISO, оставляем как есть

    stats_text += f"🕒 *Последняя активность:* `{last_activity_date_display}`\n"

    stats_text += "\n📝 *Тест знаний:*\n"
    stats_text += (
        f"   Всего правильных ответов: `{total_correct_answers_display}`\n"
        f"   Лучший результат теста: `{best_test_score_display}`\n"
        f"   Лучшее время теста: `{best_test_time_display}`\n\n"
    )

    # === Статистика по тестам для каждого словаря ===
    test_stats_by_set = await get_test_stats_by_word_set(user_id)
    if test_stats_by_set:
        stats_text += "📝 Статистика тестов по словарям:\n"
        for word_set, stats in test_stats_by_set.items():
            # Убрана замена "default" на "Стандартный словарь", теперь всегда отображается точное имя файла
            display_word_set = word_set 
            
            total_tests = stats.get("total_tests", 0)
            total_score = stats.get("total_score", 0)
            total_possible_score = stats.get("total_possible_score", 0)
            best_score = stats.get("best_score", 0)

            accuracy = (
                (total_score / total_possible_score) * 100
                if total_possible_score > 0
                else 0
            )

            stats_text += f"  └ 📁 `{display_word_set}`:\n"
            stats_text += f"    • Тестов пройдено: {total_tests}\n"
            stats_text += f"    • Общий счет: {total_score} из {total_possible_score} ({accuracy:.2f}%)\n"
            stats_text += f"    • Лучший результат: {best_score}\n"
        stats_text += "\n" # Добавляем пустую строку после статистики тестов по словарям


    stats_text += "🎮 *Игры:*\n"
    # === Статистика по играм для каждого словаря (для пользователя) ===
    game_stats_by_set = await get_game_stats_by_word_set(user_id)
    if game_stats_by_set:
        for word_set, games in game_stats_by_set.items():
            # Убрана замена "default" на "Стандартный словарь", теперь всегда отображается точное имя файла
            display_word_set = word_set 
            
            stats_text += f"  └ 📁 `{display_word_set}`:\n"
            for game_type, stats in games.items():
                correct = stats.get("correct", 0)
                played = stats.get("played", 0)
                incorrect = stats.get("incorrect", 0)
                best_time_str = (
                    f" ({stats['best_time']:.2f}с)"
                    if stats["best_time"] and stats["best_time"] != float("inf")
                    else ""
                )
                translated_game_name = GAME_NAME_TRANSLATIONS.get(
                    game_type, game_type.replace("_", " ").title()
                )
                stats_text += f"    • {translated_game_name}: Всего: {played}, Верно: {correct}, Неверно: {incorrect}{best_time_str}\n"
        stats_text += "\n" # Добавляем пустую строку после статистики игр по словарям


    await message.answer(stats_text, reply_markup=main_menu_keyboard, parse_mode="Markdown")
