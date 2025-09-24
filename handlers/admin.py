from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile # Import BufferedInputFile
from aiogram.filters import Command
from config import ADMIN_IDS
from utils.utils import add_word, get_words_alphabetical, delete_word
from utils.data_manager import calculate_overall_score_and_rank
from utils.word_manager import word_manager
import datetime
from utils.audio_converter import convert_single_ogg_to_mp3, check_for_similar_audio_file, convert_all_ogg_to_mp3 # Импорт для админской команды конвертации
from database import delete_user_from_db, get_all_users, get_game_stats_by_word_set # Импорт get_all_users и get_game_stats_by_word_set
import html # Import the html module for escaping
import re # Add this import
import json # Add this import for json.loads
import logging # Add this import for logging
import asyncio # Add this import for asyncio.sleep

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram import Bot # Импорт Bot для загрузки файлов
import os # Импорт os для работы с файловой системой
import uuid # Импорт uuid для генерации уникальных имен файлов
from keyboards import cancel_keyboard_for_filename, confirm_broadcast_keyboard # Импорт клавиатуры для отмены
from keyboards import main_menu_keyboard # Импорт клавиатуры для отмены
from keyboards import cancel_keyboard, delete_audio_keyboard, confirm_delete_audio_keyboard, create_file_list_keyboard # Импорт клавиатуры для отмены
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton # Импорт InlineKeyboardMarkup и InlineKeyboardButton


class AdminStates(StatesGroup):
    waiting_for_voice = State()
    waiting_for_audio_filename = State()
    waiting_for_settings_selection = State() # New state for settings menu
    waiting_for_setting_value = State() # New state for setting new value
    waiting_for_ban_user_id = State()
    waiting_for_unban_user_id = State()
    waiting_for_broadcast_text = State()
    waiting_for_files_to_move = State() # New state for moving audio files
    waiting_for_convert_confirmation = State() # New state for confirming batch conversion
    waiting_for_delete_selection = State() # New state for selecting directory to delete from
    waiting_for_delete_confirmation = State() # New state for confirming deletion
    waiting_for_filename_to_delete = State() # New state for deleting a single audio file

GAME_NAME_TRANSLATIONS = {
    "guess_word": "Угадай слово (по аудио)",
    "choose_translation": "Выбери перевод",
    "build_word": "Собери слово",
    "find_missing_letter": "Найди букву",
    "recall_typing": "Ввод по памяти",
    "test": "Тест знаний", # Добавил тест знаний на случай, если вы решите добавить статистику тестов сюда же.
}

router = Router()

# Dictionary to hold configurable settings and their types
CONFIGURABLE_SETTINGS = {
    "TEST_QUESTIONS_COUNT": {"type": int, "description": "Количество вопросов в тесте"},
    "ADMIN_IDS": {"type": list, "description": "Список ID администраторов"},
    "RECALL_TYPING_COUNTDOWN_SECONDS": {"type": float, "description": "Время на ввод в игре 'Ввод по памяти'"},
    "MAX_USER_WORDS": {"type": int, "description": "Максимальное количество слов в пользовательском наборе"},
    "CHECK_NEW_AUDIO": {"type": bool, "description": "Проверять наличие новых аудио в папке /sounds/mp3 и уведомлять админа"},
    "DEFAULT_WORD_SET": {"type": str, "description": "Набор слов по умолчанию при первом запуске или отсутствии активного"},
}

@router.message(Command("add"))
async def add_new_word(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    command_and_args = message.text.split(maxsplit=1)
    if len(command_and_args) < 2:
        await message.reply(f"Пожалуйста, используйте формат: /add [имя_файла.json] английское_слово=русский_перевод")
        return

    args_string = command_and_args[1].strip()
    logging.info(f"add_new_word: args_string = '{args_string}'")

    target_filename = None
    word_pair_str = None

    # Pattern to capture an optional filename.json and the rest of the string as word_pair
    # This regex handles cases like "food.json black coffee = черный кофе" or "black coffee = черный кофе"
    match_with_file = re.match(r"^(?:(\S+\.json)\s+)?(.+)$", args_string)
    logging.info(f"add_new_word: match_with_file = {match_with_file}")

    if match_with_file:
        potential_filename = match_with_file.group(1)
        if potential_filename:
            target_filename = potential_filename
            word_pair_str = match_with_file.group(2)
        else:
            word_pair_str = match_with_file.group(2)
    else:
        await message.reply(f"Неверный формат команды. Используйте: /add [имя_файла.json] английское_слово=русский_перевод")
        return

    logging.info(f"add_new_word: potential_filename = '{potential_filename}', word_pair_str (after file parsing) = '{word_pair_str}'")

    # If no filename was explicitly provided, use the user's current active file
    if target_filename is None:
        target_filename = word_manager.get_user_current_file(message.from_user.id)
        if not target_filename: # Fallback if for some reason get_user_current_file returns nothing
            target_filename = "all_words.json" # Дефолтный файл, если у пользователя нет текущего
    
    logging.info(f"add_new_word: final target_filename = '{target_filename}'")

    if not word_pair_str or not word_pair_str.strip():
        await message.reply(f"Пожалуйста, используйте формат: /add [имя_файла.json] английское_слово=русский_перевод (текущий файл: {target_filename})")
        return

    if "=" not in word_pair_str:
        await message.reply("Неверный формат. Используйте: английское_слово=русский_перевод")
        return

    en_word, ru_word = re.split(r'\s*=\s*', word_pair_str, maxsplit=1)
    en_word = re.sub(r'\s+', ' ', en_word).strip().lower()
    ru_word = re.sub(r'\s+', ' ', ru_word).strip().lower()

    logging.info(f"add_new_word: en_word = '{en_word}', ru_word = '{ru_word}'")

    if not en_word or not ru_word:
        await message.reply("Английское слово или русский перевод не могут быть пустыми.")
        return

    if await add_word({"en": en_word, "ru": ru_word}, filename=target_filename):
        await message.reply(f"Слово \'{en_word}={ru_word}\' успешно добавлено в файл \'{target_filename}\' (ваш текущий набор слов).")
    else:
        await message.reply(f"Не удалось добавить слово \'{en_word}={ru_word}\' в файл \'{target_filename}\' (ваш текущий набор слов).")

@router.message(Command("del"))
async def del_word(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    command_and_args = message.text.split(maxsplit=1)
    if len(command_and_args) < 2:
        await message.reply(f"Пожалуйста, используйте формат: /del [имя_файла.json] английское_слово")
        return

    args_string = command_and_args[1].strip()
    logging.info(f"del_word: args_string = '{args_string}'")

    target_filename = None
    word_to_delete = ""

    # Pattern to capture an optional filename.json and the rest of the string as the word to delete
    match_with_file = re.match(r"^(?:(\S+\.json)\s+)?(.+)$", args_string)
    logging.info(f"del_word: match_with_file = {match_with_file}")

    if match_with_file:
        potential_filename = match_with_file.group(1)
        if potential_filename:
            target_filename = potential_filename
            word_to_delete = match_with_file.group(2)
        else:
            word_to_delete = match_with_file.group(2)
    else:
        await message.reply(f"Неверный формат команды. Используйте: /del [имя_файла.json] английское_слово")
        return

    logging.info(f"del_word: potential_filename = '{potential_filename}', word_to_delete (after file parsing) = '{word_to_delete}'")

    # If no filename was explicitly provided, use the user's current active file
    if target_filename is None:
        target_filename = word_manager.get_user_current_file(message.from_user.id)
        if not target_filename: # Fallback if for some reason get_user_current_file returns nothing
            target_filename = "all_words.json" # Дефолтный файл, если у пользователя нет текущего
    
    logging.info(f"del_word: final target_filename = '{target_filename}'")

    if not word_to_delete or not word_to_delete.strip():
        await message.reply(f"Пожалуйста, используйте формат: /del [имя_файла.json] английское_слово (текущий файл: {target_filename})")
        return
    
    word_to_delete_en = word_to_delete.strip().lower()

    logging.info(f"del_word: word_to_delete_en = '{word_to_delete_en}'")

    if not word_to_delete_en:
        await message.reply("Пожалуйста, укажите английское слово для удаления.")
        return

    if await delete_word(word_to_delete_en, filename=target_filename):
        await message.reply(f"Слово \'{word_to_delete_en}\' успешно удалено из файла \'{target_filename}\' (ваш текущий набор слов).")
    else:
        await message.reply(f"Слово \'{word_to_delete_en}\' не найдено в файле \'{target_filename}\' (ваш текущий набор слов).")

@router.message(Command("stats"))
async def show_all_user_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split(maxsplit=1)
    target_class = None

    if len(args) > 1:
        class_match = re.match(r"class=([\wА-Яа-яЁё\d]+)", args[1].strip(), re.IGNORECASE)
        if class_match:
            target_class = class_match.group(1).upper()
        else:
            await message.reply("Неверный формат команды. Используйте: `/stats` или `/stats class=2в`", parse_mode="Markdown")
            return

    ranked_users = await calculate_overall_score_and_rank()

    if not ranked_users:
        await message.reply("Статистика по пользователям пока отсутствует.")
        return

    filtered_users = []
    for user_entry in ranked_users:
        if target_class:
            # Check if user's registered_name contains the class name (e.g., "Иван 2В")
            if user_entry.get('registered_name') and f" {target_class}" in user_entry['registered_name'].upper():
                filtered_users.append(user_entry)
        else:
            filtered_users.append(user_entry)

    if not filtered_users and target_class:
        await message.reply(f"Статистика для класса `{target_class}` не найдена.", parse_mode="Markdown")
        return

    stats_text = "<b>Общая статистика пользователей (по рейтингу):</b>\n\n"
    if target_class:
        stats_text = f"<b>Статистика пользователей класса {target_class} (по рейтингу):</b>\n\n"

    for user_entry in filtered_users:
        user_id = user_entry['user_id']
        rank = user_entry['rank']
        overall_score = user_entry['overall_score']

        # Get detailed stats with default values
        total_correct_answers = user_entry.get('total_correct_answers', 0) or 0
        best_test_score = user_entry.get('best_test_score', 0) or 0
        last_activity_date_str = user_entry.get('last_activity_date', 'N/A') or 'N/A'

        # Calculate total game correct for OKPO
        total_game_correct = 0
        if 'games_stats' in user_entry:
            for game_type, game_data in user_entry['games_stats'].items():
                total_game_correct += game_data.get('correct', 0)
        
        # Calculate OKPO
        overall_correct_answers = total_correct_answers + total_game_correct

        # Format last activity date
        formatted_last_activity = last_activity_date_str
        if last_activity_date_str != 'N/A':
            try:
                dt_object = datetime.datetime.fromisoformat(last_activity_date_str)
                formatted_last_activity = dt_object.strftime("%d.%m.%y в %H:%M")
            except ValueError:
                pass # Keep as 'N/A' or original string if parsing fails

        # Determine display name for the user, prioritizing Telegram full name, then username, then bot-registered name, then "No name"
        # Use the helper function to get the display name
        display_name_for_link = _get_display_name(
            user_entry.get('first_name'),
            user_entry.get('last_name'),
            user_entry.get('username'),
            user_entry.get('registered_name') # Correctly use registered_name
        )
        escaped_username_for_display = html.escape(str(user_entry.get('username', '') or ''))
        username_display_text = f" (@{escaped_username_for_display})" if escaped_username_for_display else " (No username)"

        # Create a user profile link (HTML format)
        user_link = f"<a href=\"tg://user?id={user_id}\">{display_name_for_link}</a>"

        stats_text += f"<b>Ранг: {rank}</b> - {user_link}{username_display_text} (Балл: <b>{overall_score:.2f}</b>)\n"
        stats_text += f"  - ОКПО: <b>{overall_correct_answers}</b> | Тест: <b>{best_test_score}</b> | ПА: <b>{formatted_last_activity}</b>\n"

        # Get and display game stats by word set
        game_stats_by_set = await get_game_stats_by_word_set(user_id)
        if game_stats_by_set:
            stats_text += "  <b>Статистика по наборам слов:</b>\n"
            for word_set, games in game_stats_by_set.items():
                stats_text += f"    └ 📁 `{html.escape(word_set)}`:\n"
                for game_type, stats in games.items():
                    correct = stats.get('correct', 0)
                    played = stats.get('played', 0)
                    incorrect = stats.get('incorrect', 0)
                    best_time_str = f" ({stats['best_time']:.2f}с)" if stats['best_time'] and stats['best_time'] != float('inf') else ""
                    
                    # Применяем перевод названия игры
                    translated_game_name = GAME_NAME_TRANSLATIONS.get(game_type, game_type.replace('_', ' ').title())
                    
                    stats_text += f"      • {translated_game_name}: Всего: {played}, Верно: {correct}, Неверно: {incorrect}{best_time_str}\n"
        stats_text += "\n" # Add a newline for better spacing between users

    await message.reply(stats_text, parse_mode="HTML")

@router.message(Command("deluser"))
async def del_user(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Пожалуйста, используйте формат: /deluser USER_ID")
        return

    try:
        user_id_to_delete = int(args[1].strip())
    except ValueError:
        await message.reply("Неверный формат ID пользователя. ID должен быть числом.")
        return

    db_deleted = await delete_user_from_db(user_id_to_delete)
    
    if db_deleted:
        await message.reply(f"Пользователь с ID {user_id_to_delete} успешно удален из базы данных.")
    else:
        await message.reply(f"Пользователь с ID {user_id_to_delete} не найден в базе данных.")

@router.message(Command("files"))
async def list_word_files(message: Message):
    """Показывает список доступных файлов со словами."""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    files = word_manager.get_available_files()
    if not files:
        await message.reply("Файлы со словами не найдены.")
        return

    admin_current_file = word_manager.get_user_current_file(message.from_user.id) # Получаем текущий файл для админа
    files_text = "📁 *Доступные файлы со словами:*\n\n"
    
    for file in files:
        info = word_manager.get_file_info(file)
        if info:
            status = "✅ (текущий)" if file == admin_current_file else ""
            files_text += f"• *{file}* {status}\n"
            files_text += f"  └ Слов: {info['word_count']}, Размер: {info['file_size']} байт\n\n"
    
    await message.reply(files_text, parse_mode="Markdown")

@router.message(Command("switch_set_to_all"))
async def switch_word_file_for_all_users(message: Message):
    """Переключает активный файл со словами для ВСЕХ пользователей."""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Пожалуйста, используйте формат: /switch_set_to_all имя_файла")
        return

    filename = args[1].strip()
    
    # Проверяем, что файл существует, прежде чем пытаться переключить его для всех
    if not word_manager.get_file_info(filename):
        await message.reply(f"❌ Файл '{filename}' не найден. Используйте /files для просмотра доступных файлов.")
        return

    await message.reply(f"Начинаю переключение активного файла на *{filename}* для всех пользователей...", parse_mode="Markdown")

    all_users = await get_all_users() # Получаем всех пользователей из базы данных
    successful_switches = 0
    failed_switches = 0

    for user in all_users:
        user_id = user['user_id']
        # Получаем display_name для каждого пользователя
        user_display_name = _get_display_name(user.get('first_name'), user.get('last_name'), user.get('username'), user.get('name'))

        if word_manager.set_user_current_file(user_id, filename, user_display_name):
            successful_switches += 1
        else:
            failed_switches += 1
        await asyncio.sleep(0.05) # Небольшая задержка для предотвращения превышения лимитов API
    
    await message.reply(
        f"✅ Переключение завершено! Успешно изменено: {successful_switches} пользователей, Не удалось: {failed_switches} пользователей.",
        parse_mode="Markdown"
    )

@router.message(Command("create_file"))
async def create_word_file(message: Message):
    """Создает новый файл со словами."""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Пожалуйста, используйте формат: /create_file имя_файла")
        return

    filename = args[1].strip()
    if word_manager.create_new_file(filename):
        await message.reply(f"✅ Файл '{filename}' успешно создан.")
    else:
        await message.reply(f"❌ Не удалось создать файл '{filename}'. Возможно, файл уже существует.")

@router.message(Command("delete_file"))
async def delete_word_file(message: Message):
    """Удаляет файл со словами."""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Пожалуйста, используйте формат: /delete_file имя_файла")
        return

    filename = args[1].strip()
    if filename == "all_words.json":
        await message.reply("❌ Нельзя удалить основной файл 'all_words.json'.")
        return

    if word_manager.delete_file(filename):
        await message.reply(f"✅ Файл '{filename}' успешно удален.")
    else:
        await message.reply(f"❌ Не удалось удалить файл '{filename}'. Файл не найден или это основной файл.")

@router.message(Command("deduplicate_words"))
async def deduplicate_words_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return
    
    # /deduplicate_words [имя_файла.json] или /deduplicate_words all
    parts = message.text.split(maxsplit=1)
    target = "default"

    if len(parts) > 1:
        target = parts[1].strip().lower()

    total_duplicates_removed = 0
    if target == "all" or target == "default": # Изменено здесь
        await message.reply("Начинаю удаление дубликатов из ВСЕХ файлов со словами... Это может занять некоторое время.")
        files = word_manager.get_available_files()
        if not files:
            await message.reply("Файлы со словами не найдены.")
            return
        
        for filename in files:
            duplicates_removed = word_manager.remove_duplicates_from_file(filename)
            if duplicates_removed > 0:
                total_duplicates_removed += duplicates_removed
                await message.reply(f"✅ Удалено {duplicates_removed} дубликатов из файла `{filename}`.", parse_mode="Markdown")
            else:
                await message.reply(f"ℹ️ В файле `{filename}` дубликатов не найдено.", parse_mode="Markdown")
            await asyncio.sleep(0.1) # Небольшая задержка, чтобы не перегружать API Telegram
        
        if total_duplicates_removed > 0:
            await message.reply(f"✅ Завершено: Всего удалено {total_duplicates_removed} дубликатов из всех файлов.", parse_mode="Markdown")
        else:
            await message.reply(f"ℹ️ Завершено: Дубликатов не найдено ни в одном файле.", parse_mode="Markdown")

    elif target.endswith(".json"):
        filename_to_process = target # Теперь target уже является именем файла
        
        if not word_manager.get_file_info(filename_to_process):
            await message.reply(f"❌ Файл `{filename_to_process}` не найден. Используйте /files для просмотра доступных файлов.", parse_mode="Markdown")
            return

        await message.reply(f"Начинаю удаление дубликатов из файла `{filename_to_process}`...")
        duplicates_removed = word_manager.remove_duplicates_from_file(filename_to_process)

        if duplicates_removed > 0:
            await message.reply(f"✅ Удалено {duplicates_removed} дубликатов из файла `{filename_to_process}`.", parse_mode="Markdown")
        else:
            await message.reply(f"ℹ️ В файле `{filename_to_process}` дубликатов не найдено.", parse_mode="Markdown")
    else:
        await message.reply("Неверный формат команды. Используйте: `/deduplicate_words [имя_файла.json]` для обработки конкретного файла, `/deduplicate_words all` для обработки всех файлов или `/deduplicate_words` для обработки файла по умолчанию.", parse_mode="Markdown")


@router.message(Command("current_files"))
async def show_all_users_current_files(message: Message):
    """Показывает текущие активные файлы со словами для всех пользователей."""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    await message.reply("Собираю информацию о текущих файлах всех пользователей... Это может занять некоторое время.", parse_mode="Markdown")

    all_users = await get_all_users()
    if not all_users:
        await message.reply("В базе данных нет зарегистрированных пользователей.")
        return

    files_info_text = "📁 *Текущие файлы пользователей:*\n\n"

    for user in all_users:
        user_id = user['user_id']
        display_name = _get_display_name(
            user.get('first_name'),
            user.get('last_name'),
            user.get('username'),
            user.get('name')
        )
        
        current_file = word_manager.get_user_current_file(user_id)
        
        files_info_text += f"• Пользователь: <a href=\"tg://user?id={user_id}\">{display_name}</a>\n"
        files_info_text += f"  └ Текущий файл: `{html.escape(current_file)}`\n\n"
        await asyncio.sleep(0.02) # Небольшая задержка, чтобы избежать перегрузки API Telegram

    await message.reply(files_info_text, parse_mode="HTML")

@router.message(Command("move_audio_files"))
async def move_audio_files_command(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    mp3_dir = os.path.join("data", "sounds", "mp3")
    if not os.path.exists(mp3_dir) or not os.listdir(mp3_dir):
        await message.reply("Папка `data/sounds/mp3` пуста или не существует.", parse_mode="Markdown")
        await state.clear()
        return

    audio_files = [f for f in os.listdir(mp3_dir) if f.endswith(".mp3")]
    audio_files.sort() # Sort for consistent numbering

    if not audio_files:
        await message.reply("В папке `data/sounds/mp3` нет MP3 аудиофайлов.", parse_mode="Markdown")
        await state.clear()
        return

    files_list_text = "🎵 *Доступные MP3 аудиофайлы для перемещения:*\n"
    numbered_files = {i + 1: filename for i, filename in enumerate(audio_files)}
    
    for num, filename in numbered_files.items():
        files_list_text += f"{num}. `{html.escape(filename)}`\n"
        # Send each audio file individually
        try:
            filepath = os.path.join(mp3_dir, filename)
            with open(filepath, 'rb') as audio_file:
                await message.reply_audio(BufferedInputFile(audio_file.read(), filename=filename), caption=f"{num}. {html.escape(filename)}", parse_mode="HTML")
            # await asyncio.sleep(0.1) # Small delay to avoid API limits (temporarily commented out for debugging)
        except Exception as e:
            logging.error(f"Error sending audio file {filename}: {e}")
            await message.reply(f"❌ Не удалось отправить аудиофайл `{html.escape(filename)}`. Ошибка: `{html.escape(str(e))}`", parse_mode="Markdown")

    files_list_text += "\nОтправьте номера файлов (через пробел или запятую), которые хотите переместить в `data/sounds`, или нажмите 'Отмена'."

    await message.reply(files_list_text, parse_mode="Markdown", reply_markup=cancel_keyboard)
    await state.update_data(files_to_move_list=numbered_files)
    await state.set_state(AdminStates.waiting_for_files_to_move)

@router.message(AdminStates.waiting_for_files_to_move, F.text)
async def process_files_to_move(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        await state.clear()
        return

    input_text = message.text.strip().lower()
    if input_text == "отмена":
        await message.reply("Операция перемещения файлов отменена.", reply_markup=main_menu_keyboard)
        await state.clear()
        return

    state_data = await state.get_data()
    numbered_files = state_data.get("files_to_move_list")

    if not numbered_files:
        await message.reply("Ошибка: список файлов для перемещения не найден. Пожалуйста, начните с `/move_audio_files` снова.", parse_mode="Markdown", reply_markup=main_menu_keyboard)
        await state.clear()
        return

    selected_numbers_str = re.split(r'[\s,]+', input_text) # Split by space or comma
    selected_numbers = []
    for num_str in selected_numbers_str:
        try:
            num = int(num_str)
            if num in numbered_files:
                selected_numbers.append(num)
            else:
                await message.reply(f"❌ Неверный номер файла: `{num_str}`. Пожалуйста, введите корректные номера.", parse_mode="Markdown", reply_markup=cancel_keyboard)
                return
        except ValueError:
            await message.reply(f"❌ Неверный формат ввода: `{num_str}` не является числом. Пожалуйста, введите номера файлов через пробел или запятую, или 'Отмена'.", parse_mode="Markdown", reply_markup=cancel_keyboard)
            return

    if not selected_numbers:
        await message.reply("Вы не выбрали ни одного файла для перемещения. Пожалуйста, введите номера файлов или 'Отмена'.", reply_markup=cancel_keyboard)
        return

    mp3_source_dir = os.path.join("data", "sounds", "mp3")
    target_sounds_dir = os.path.join("data", "sounds")

    move_results = []
    for num in selected_numbers:
        filename = numbered_files[num]
        source_filepath = os.path.join(mp3_source_dir, filename)
        destination_filepath = os.path.join(target_sounds_dir, filename)

        if os.path.exists(destination_filepath):
            move_results.append(f"⚠️ Файл `{html.escape(filename)}` уже существует в `data/sounds`. Пропускаю перемещение.")
        else:
            try:
                os.replace(source_filepath, destination_filepath) # Atomically move file (cut/paste)
                move_results.append(f"✅ Файл `{html.escape(filename)}` успешно перемещен в `data/sounds`.")
            except Exception as e:
                logging.error(f"Ошибка при перемещении файла {filename}: {e}")
                move_results.append(f"❌ Ошибка при перемещении `{html.escape(filename)}`: {e}")

    final_message = "\n".join(move_results)
    await message.reply(final_message, parse_mode="Markdown", reply_markup=main_menu_keyboard)
    await state.clear()

@router.message(Command("convert_all_audio"))
async def convert_all_audio_command(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return
    
    await message.reply(
        "Вы собираетесь запустить пакетную конвертацию всех OGG аудиофайлов из `data/sounds/ogg` в MP3 в `data/sounds/mp3`. "
        "Существующие MP3 файлы будут пропущены. Вы уверены, что хотите продолжить?",
        parse_mode="Markdown",
        reply_markup=confirm_broadcast_keyboard # Re-using the broadcast confirmation keyboard
    )
    await state.set_state(AdminStates.waiting_for_convert_confirmation)

@router.message(AdminStates.waiting_for_convert_confirmation, F.text == "Да, отправить")
async def confirm_convert_all_audio(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        await state.clear()
        return
    
    await message.reply("Начинаю пакетную конвертацию... Это может занять некоторое время.")
    
    log_messages = await convert_all_ogg_to_mp3()
    
    for log_msg in log_messages:
        await message.reply(log_msg)
        await asyncio.sleep(0.1) # Small delay to avoid API limits
        
    await message.reply("Процесс пакетной конвертации завершен!", reply_markup=main_menu_keyboard)
    await state.clear()

@router.message(AdminStates.waiting_for_convert_confirmation, F.text == "Отмена")
async def cancel_convert_all_audio(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        await state.clear()
        return
    
    await state.clear()
    await message.reply("Пакетная конвертация отменена.", reply_markup=main_menu_keyboard)

@router.message(Command("users"))
async def list_all_users(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return
    
    users = await get_all_users()
    
    if not users:
        await message.reply("В базе данных нет зарегистрированных пользователей.")
        return
    
    users_text = """*Список зарегистрированных пользователей:*

"""
    for user in users:
        user_id = user['user_id']
        name = user['name'] # This is 'registered_name' from update_user_profile_data
        first_name = user.get('first_name', '')
        last_name = user.get('last_name', '')
        username = user.get('username', '')

        # Use the helper function to get the display name for the link
        display_name_for_link = _get_display_name(
            first_name,
            last_name,
            username,
            name # 'name' here is the registered_name
        )
        
        # Escape HTML special characters for safe display of username
        escaped_username_for_display = html.escape(str(username or ''))
        
        # Create a clickable link to the user's profile
        user_link = f"<a href=\"tg://user?id={user_id}\">{display_name_for_link}</a>"

        username_display = f" (@{escaped_username_for_display})" if escaped_username_for_display else " (No username)"

        users_text += (
            f"ID: `{user_id}` | Имя в боте: `{html.escape(str(name or 'No name'))}`\n" # Bot-registered name
            f"Профиль TG: {user_link}{username_display}\n\n" # Telegram profile details
        )
    
    await message.reply(users_text, parse_mode="HTML") # Use HTML parse mode for links

@router.message(Command("ban"))
async def ban_user_command(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    await message.reply("Пожалуйста, отправьте ID пользователя, которого вы хотите забанить.", reply_markup=cancel_keyboard)
    await state.set_state(AdminStates.waiting_for_ban_user_id)

@router.message(AdminStates.waiting_for_ban_user_id, F.text)
async def process_ban_user_id(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        await state.clear()
        return

    try:
        user_id_to_ban = int(message.text.strip())
    except ValueError:
        await message.reply("Неверный формат ID пользователя. ID должен быть числом.", reply_markup=cancel_keyboard)
        return

    from utils.data_manager import add_banned_user # Import here to avoid circular dependency

    if await add_banned_user(user_id_to_ban):
        await message.reply(f"✅ Пользователь с ID {user_id_to_ban} успешно забанен.")
    else:
        await message.reply(f"❌ Пользователь с ID {user_id_to_ban} уже находится в черном списке.")
    
    await state.clear()
    await message.answer("Возвращаемся в главное меню.", reply_markup=main_menu_keyboard)

@router.message(Command("send_msg"))
async def send_message_command(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Пожалуйста, используйте формат: `/send_msg [текст]` или `/send_msg class=2в [текст]`", parse_mode="Markdown")
        return

    target_class = None
    message_text_raw = args[1].strip()

    class_match = re.match(r"class=([\wА-Яа-яЁё\d]+)\s*(.*)", message_text_raw, re.IGNORECASE)
    if class_match:
        target_class = class_match.group(1).upper() # Store class in uppercase for consistent matching
        message_text = class_match.group(2).strip()
    else:
        message_text = message_text_raw

    if not message_text:
        await message.reply("Текст рассылки не может быть пустым.", reply_markup=cancel_keyboard)
        return

    # Store the target_class and message_text in FSM context
    await state.update_data(broadcast_target_class=target_class, broadcast_message_text=message_text)
    await state.set_state(AdminStates.waiting_for_broadcast_text)

    confirmation_message = f"Вы собираетесь отправить следующее сообщение: `{message_text}`\n\n"
    if target_class:
        confirmation_message += f"Будет отправлено пользователям класса: `{target_class}`. Вы уверены?"
    else:
        confirmation_message += "Будет отправлено ВСЕМ пользователям. Вы уверены?"
    
    await message.reply(confirmation_message, parse_mode="Markdown", reply_markup=confirm_broadcast_keyboard)


@router.message(AdminStates.waiting_for_broadcast_text, F.text == "Да, отправить")
async def confirm_send_message(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        await state.clear()
        return

    state_data = await state.get_data()
    target_class = state_data.get("broadcast_target_class")
    message_text = state_data.get("broadcast_message_text")

    if not message_text:
        await message.reply("Ошибка: текст сообщения для рассылки не найден.", reply_markup=main_menu_keyboard)
        await state.clear()
        return

    from database import get_all_users
    all_users = await get_all_users()
    target_users = []

    for user in all_users:
        if target_class:
            # Check if user's registered_name contains the class name (e.g., "Иван 2В")
            if user.get('name') and f" {target_class}" in user['name'].upper():
                target_users.append(user)
        else:
            target_users.append(user)
    
    sent_count = 0
    failed_count = 0
    for user in target_users:
        try:
            await bot.send_message(user['user_id'], message_text)
            sent_count += 1
            await asyncio.sleep(0.05) # Small delay to avoid hitting Telegram API limits
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение пользователю {user['user_id']}: {e}")
            failed_count += 1
    
    await message.reply(f"✅ Рассылка завершена! Отправлено: {sent_count}, Не удалось отправить: {failed_count}", reply_markup=main_menu_keyboard)
    await state.clear()

@router.message(AdminStates.waiting_for_broadcast_text, F.text == "Отмена")
async def cancel_send_message(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        await state.clear()
        return
    await state.clear()
    await message.reply("Рассылка отменена.", reply_markup=main_menu_keyboard)


@router.message(Command("new_sound"))
async def add_new_audio_command(message: Message, state: FSMContext):
    # Удаляем проверку на ADMIN_IDS, делая команду общедоступной
    # if message.from_user.id not in ADMIN_IDS:
    #     await message.reply("У вас нет прав для выполнения этой команды.")
    #     return

    await message.reply("Пожалуйста, отправьте сначала голосовое сообщение (озвученное слово или выражение), которое вы хотите добавить. Затем бот поросит вас ввести имя файла для этого аудиофайла которое должно быть на английском языке и точно совпадать с озвученным словом или выражением.", reply_markup=cancel_keyboard)
    await state.set_state(AdminStates.waiting_for_voice)

@router.message(AdminStates.waiting_for_voice, F.voice)
async def process_voice_for_new_audio(message: Message, state: FSMContext, bot: Bot):
    # Удаляем проверку на ADMIN_IDS
    # if message.from_user.id not in ADMIN_IDS:
    #     await message.reply("У вас нет прав для выполнения этой команды.")
    #     await state.clear()
    #     return

    # Создаем папку data/sounds/temp_audio если ее нет
    temp_audio_dir = os.path.join("data", "sounds", "temp_audio")
    os.makedirs(temp_audio_dir, exist_ok=True)

    # Генерируем уникальное имя для временного OGG файла
    temp_ogg_filename = f"{uuid.uuid4().hex}.ogg"
    temp_ogg_filepath = os.path.join(temp_audio_dir, temp_ogg_filename)

    # Загружаем голосовое сообщение
    file_id = message.voice.file_id
    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, temp_ogg_filepath)

    await state.update_data(temp_ogg_filepath=temp_ogg_filepath)
    await message.reply("Голосовое сообщение получено. Как вы хотите назвать этот аудиофайл (без расширения)?\n\n*Имя файла должно быть только на английском языке!*", parse_mode="Markdown", reply_markup=cancel_keyboard_for_filename)
    await state.set_state(AdminStates.waiting_for_audio_filename)

@router.message(AdminStates.waiting_for_audio_filename, F.text)
async def process_audio_filename(message: Message, state: FSMContext, bot: Bot):
    # Удаляем проверку на ADMIN_IDS
    # if message.from_user.id not in ADMIN_IDS:
    #     await message.reply("У вас нет прав для выполнения этой команды.")
    #     await state.clear()
    #     return

    filename = message.text.strip().lower()
    if not filename:
        await message.reply("Имя файла не может быть пустым. Пожалуйста, введите имя файла *на английском языке* или /cancel для отмены.", parse_mode="Markdown")
        return

    state_data = await state.get_data()
    temp_ogg_filepath = state_data.get("temp_ogg_filepath")

    if not temp_ogg_filepath or not os.path.exists(temp_ogg_filepath):
        await message.reply("Произошла ошибка: временный аудиофайл не найден. Начните сначала с команды /new_sound.")
        await state.clear()
        return

    # Убедимся, что папка data/sounds существует
    target_sounds_dir = os.path.join("data", "sounds")
    os.makedirs(target_sounds_dir, exist_ok=True)

    # Define paths for permanent OGG and MP3 files
    ogg_archive_dir = os.path.join(target_sounds_dir, "ogg")
    mp3_output_dir = os.path.join(target_sounds_dir, "mp3")
    os.makedirs(ogg_archive_dir, exist_ok=True)
    os.makedirs(mp3_output_dir, exist_ok=True)

    final_ogg_filename = f"{filename}.ogg"
    final_ogg_filepath_permanent = os.path.join(ogg_archive_dir, final_ogg_filename)
    final_mp3_filepath = os.path.join(mp3_output_dir, f"{filename}.mp3")

    # NEW: Check for similar filenames across all /sounds subdirectories
    if await check_for_similar_audio_file(filename):
        await message.reply(
            f"⚠️ Аудиофайл с похожим именем '{filename}' уже существует. "
            "Пожалуйста, введите другое имя для аудиофайла или нажмите Отмена.",
            reply_markup=cancel_keyboard_for_filename
        )
        return

    # Проверяем, существует ли файл с таким именем (как OGG, так и MP3)
    if os.path.exists(final_ogg_filepath_permanent) or os.path.exists(final_mp3_filepath):
        await message.reply(
            f"Файл с именем '{filename}.ogg' или '{filename}.mp3' уже существует. "
            "Пожалуйста, введите другое имя для аудиофайла или нажмите Отмена.",
            reply_markup=cancel_keyboard_for_filename
        )
        return

    try:
        # Move temporary OGG to its permanent OGG archive location
        os.replace(temp_ogg_filepath, final_ogg_filepath_permanent)
        
        # Запускаем процесс конвертации, используя новый путь к OGG файлу
        log_messages, conversion_successful = await convert_single_ogg_to_mp3(final_ogg_filepath_permanent, filename) # Используем существующую функцию
        
        if message.from_user.id in ADMIN_IDS: # Admin receives detailed messages
            await message.reply(f"Файл '{final_ogg_filename}' успешно сохранен в архив OGG. Запускаю конвертацию... ")
            for log_msg in log_messages:
                await message.reply(log_msg)

            if conversion_successful:
                await message.reply("Процесс добавления и конвертации аудиофайла завершен!")
            else:
                await message.reply("Добавлено успешно, но конвертация не удалась. Конвертируйте самостоятельно или настройте конвертер.")
        else: # Non-admin user receives simplified message
            await message.reply("✅ Спасибо! Ваш аудиофайл получен и ожидает одобрения администратора.")

        await state.clear()

    except Exception as e:
        await message.reply(f"Произошла ошибка при сохранении или конвертации файла: {e}")
        await state.clear()


@router.message(AdminStates.waiting_for_audio_filename, ~F.text)
async def process_invalid_audio_filename(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        await state.clear()
        return
    await message.reply("Пожалуйста, введите корректное имя файла (текст). Если вы хотите отменить, введите /cancel.", reply_markup=cancel_keyboard)

@router.callback_query(F.data == "cancel_audio_upload")
async def cancel_audio_upload_handler(callback: CallbackQuery, state: FSMContext):
    # if callback.from_user.id not in ADMIN_IDS:
    #     await callback.answer("У вас нет прав для выполнения этой команды.", show_alert=True)
    #     await state.clear()
    #     return

    state_data = await state.get_data()
    temp_ogg_filepath = state_data.get("temp_ogg_filepath")
    if temp_ogg_filepath and os.path.exists(temp_ogg_filepath):
        os.remove(temp_ogg_filepath)
    
    await state.clear()
    await callback.answer("Операция отменена.", show_alert=True)
    await callback.message.edit_text("Операция отменена.", reply_markup=None)

@router.message(Command("settings"))
async def show_settings(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    settings_output = "⚙️ Текущие настройки бота:\n\n"
    current_settings = {}
    
    # Read config.py content
    with open("config.py", "r", encoding="utf-8") as f:
        config_lines = f.readlines()

    for line in config_lines:
        for setting_name, setting_info in CONFIGURABLE_SETTINGS.items():
            if line.strip().startswith(f"{setting_name} ="):
                try:
                    # Extract value dynamically
                    value_str = line.split("=", 1)[1].strip()
                    # Remove comments if any
                    if "#" in value_str:
                        value_str = value_str.split("#", 1)[0].strip()
                    
                    # Convert to appropriate type
                    setting_type = setting_info["type"]
                    value = None
                    if setting_type is int:
                        value = int(value_str)
                    elif setting_type is float:
                        value = float(value_str)
                    elif setting_type is bool:
                        value = value_str.lower() == "true"
                    elif setting_type is str:
                        # Remove quotes for string values
                        value = value_str.strip('"')
                    elif setting_type is list:
                        try:
                            value = json.loads(value_str.replace("'", '"')) # Handle single quotes in list strings
                        except json.JSONDecodeError:
                            value = [item.strip() for item in value_str.strip('[]').split(',')] # Fallback for simple comma-separated lists
                    
                    current_settings[setting_name] = value
                    # Format each setting individually using HTML
                    settings_output += f"<code>{setting_name}</code>: <code>{html.escape(str(value))}</code> ({setting_info['description']})\n\n"

                except (ValueError, json.JSONDecodeError) as e:
                    logging.error(f"Ошибка при парсинге настройки {setting_name} из config.py: {e}")
                    settings_output += f"<code>{setting_name}</code>: <code>Ошибка парсинга</code> ({setting_info['description']})\n\n"

    settings_output += "Для изменения настройки, отправьте ее название или нажмите 'Отмена':"
    
    # Store current settings in state for later modification
    await state.update_data(current_configurable_settings=current_settings)
    await state.set_state(AdminStates.waiting_for_settings_selection)
    
    await message.reply(settings_output, parse_mode="HTML", reply_markup=cancel_keyboard)

@router.message(AdminStates.waiting_for_settings_selection, F.text)
async def process_settings_selection(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        await state.clear()
        return

    selected_setting = message.text.strip().upper()
    
    if selected_setting not in CONFIGURABLE_SETTINGS:
        await message.reply("Неизвестная настройка. Пожалуйста, выберите настройку из списка или нажмите Отмена.", reply_markup=cancel_keyboard)
        return

    state_data = await state.get_data()
    current_settings = state_data.get("current_configurable_settings", {})
    
    await state.update_data(selected_setting_to_modify=selected_setting)
    await state.set_state(AdminStates.waiting_for_setting_value)

    setting_info = CONFIGURABLE_SETTINGS[selected_setting]
    current_value = current_settings.get(selected_setting, "N/A")
    
    await message.reply(
        f"Вы выбрали настройку *{selected_setting}* ({setting_info['description']}). "
        f"Текущее значение: `{current_value}`. "
        f"Пожалуйста, введите новое значение:",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard
    )

@router.message(AdminStates.waiting_for_setting_value, F.text)
async def process_new_setting_value(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        await state.clear()
        return
    
    new_value_str = message.text.strip()
    state_data = await state.get_data()
    selected_setting = state_data.get("selected_setting_to_modify")

    if not selected_setting:
        await message.reply("Произошла ошибка при определении настройки. Пожалуйста, начните с /settings снова.", reply_markup=main_menu_keyboard)
        await state.clear()
        return

    setting_info = CONFIGURABLE_SETTINGS[selected_setting]
    expected_type = setting_info["type"]

    try:
        if expected_type == int:
            new_value = int(new_value_str)
        elif expected_type == float:
            new_value = float(new_value_str)
        elif expected_type == list: # Handle list type
            # This is a bit complex, as list values might be comma-separated strings
            # or quoted strings. We'll try to parse them, and convert to int for ADMIN_IDS.
            parsed_list_str = new_value_str.strip('[]').replace("'", '"') # Remove brackets, normalize quotes
            if parsed_list_str:
                raw_items = [item.strip() for item in parsed_list_str.split(',')]
                if selected_setting == "ADMIN_IDS":
                    new_value = [int(item) for item in raw_items if item.isdigit()]
                else:
                    new_value = raw_items
            else:
                new_value = [] # Empty list if input is empty
        elif expected_type == bool: # Handle boolean type
            new_value = new_value_str.lower() == "true"
        else:
            new_value = new_value_str.strip('"') # Treat as string
        
        # Now, update the config.py file
        await update_config_file(selected_setting, new_value)

        await message.reply(
            f"✅ Настройка *{selected_setting}* успешно обновлена до `{new_value}`. Изменения применены.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard
        )
        await state.clear()

    except ValueError:
        await message.reply(
            f"❌ Неверный формат значения для *{selected_setting}*. Ожидается тип `{expected_type.__name__}`. "
            f"Пожалуйста, введите корректное значение или нажмите Отмена.",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard
        )
    except Exception as e:
        await message.reply(
            f"❌ Произошла ошибка при сохранении настройки *{selected_setting}*: {e}. "
            f"Пожалуйста, попробуйте снова или нажмите Отмена.",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard
        )
        
# Helper function to update config.py
async def update_config_file(setting_name: str, new_value: any):
    filepath = "config.py"
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_file_content_lines = []
    updated = False
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line: # Skip empty lines during rebuild
            continue
        
        if stripped_line.startswith(f"{setting_name} ="):
            comment = ""
            if "#" in stripped_line:
                line_parts = stripped_line.split("#", 1)
                comment = " # " + line_parts[1].strip()
            
            value_to_write = ""
            if isinstance(new_value, str):
                value_to_write = f'"{new_value}"'
            elif isinstance(new_value, list):
                # Ensure list of integers is written correctly without quotes around numbers
                if setting_name == "ADMIN_IDS" and all(isinstance(x, int) for x in new_value):
                    value_to_write = f"[{', '.join(map(str, new_value))}]"
                else:
                    value_to_write = json.dumps(new_value, ensure_ascii=False)
            elif isinstance(new_value, bool):
                value_to_write = str(new_value) # Ensures True/False are written as Python bools
            else:
                value_to_write = str(new_value)
            
            new_file_content_lines.append(f"{setting_name} = {value_to_write}{comment}\n")
            updated = True
        else: # Add non-empty, non-updated lines, ensuring single newline
            new_file_content_lines.append(stripped_line + '\n')
    
    if not updated: # Should not happen for predefined settings, but as a fallback for new settings
        value_to_write = ""
        if isinstance(new_value, str):
            value_to_write = f'"{new_value}"'
        elif isinstance(new_value, list):
            value_to_write = json.dumps(new_value, ensure_ascii=False)
        elif isinstance(new_value, bool):
            value_to_write = str(new_value)
        else:
            value_to_write = str(new_value)
        new_file_content_lines.append(f"{setting_name} = {value_to_write}\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(new_file_content_lines)


# Handler for invalid text input during settings selection
@router.message(AdminStates.waiting_for_settings_selection, ~F.text)
async def process_invalid_settings_selection(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return
    await message.reply("Пожалуйста, введите название настройки из списка или нажмите Отмена.")

# Universal cancel handler for admin states
@router.callback_query(F.data == "cancel_audio_upload", AdminStates.waiting_for_settings_selection)
@router.callback_query(F.data == "cancel_audio_upload", AdminStates.waiting_for_setting_value)
async def cancel_settings_operation(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("У вас нет прав для выполнения этой команды.", show_alert=True)
        await state.clear()
        return
    
    await state.clear()
    await callback.answer("Операция отменена.", show_alert=True)
    await callback.message.edit_text("Операция отменена.", reply_markup=None)

@router.message(Command("unban"))
async def unban_user_command(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    await message.reply("Пожалуйста, отправьте ID пользователя, которого вы хотите разбанить.", reply_markup=cancel_keyboard)
    await state.set_state(AdminStates.waiting_for_unban_user_id)

@router.message(AdminStates.waiting_for_unban_user_id, F.text)
async def process_unban_user_id(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        await state.clear()
        return

    try:
        user_id_to_unban = int(message.text.strip())
    except ValueError:
        await message.reply("Неверный формат ID пользователя. ID должен быть числом.", reply_markup=cancel_keyboard)
        return

    from utils.data_manager import remove_banned_user # Import here to avoid circular dependency

    if await remove_banned_user(user_id_to_unban):
        await message.reply(f"✅ Пользователь с ID {user_id_to_unban} успешно разбанен.")
    else:
        await message.reply(f"❌ Пользователь с ID {user_id_to_unban} не найден в черном списке.")
    
    await state.clear()
    await message.answer("Возвращаемся в главное меню.", reply_markup=main_menu_keyboard)

@router.message(Command("delete_audio_files"))
async def delete_audio_files_command(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return
    
    await message.reply(
        "Выберите, из какой папки вы хотите удалить аудиофайлы:",
        reply_markup=delete_audio_keyboard
    )
    await state.set_state(AdminStates.waiting_for_delete_selection)

@router.callback_query(AdminStates.waiting_for_delete_selection, F.data.in_([
    "delete_all_ogg", "delete_all_mp3", 
    "delete_single_ogg", "delete_single_mp3",
    "delete_single_sounds"
]))
async def process_delete_selection(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("У вас нет прав для выполнения этой команды.", show_alert=True)
        await state.clear()
        return

    delete_action = callback.data
    sounds_dir = os.path.join("data", "sounds")
    ogg_dir = os.path.join(sounds_dir, "ogg")
    mp3_dir = os.path.join(sounds_dir, "mp3")

    if delete_action == "delete_all_ogg":
        confirmation_message = "Вы собираетесь удалить ВСЕ OGG аудиофайлы из папки `data/sounds/ogg`. Вы уверены?"
        await state.update_data(delete_target="ogg", delete_type="all")
        await callback.message.edit_text(
            confirmation_message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Да, удалить", callback_data="confirm_delete_audio_files")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_audio")]
            ])
        )
        await state.set_state(AdminStates.waiting_for_delete_confirmation)
    elif delete_action == "delete_all_mp3":
        confirmation_message = "Вы собираетесь удалить ВСЕ MP3 аудиофайлы из папки `data/sounds/mp3`. Вы уверены?"
        await state.update_data(delete_target="mp3", delete_type="all")
        await callback.message.edit_text(
            confirmation_message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Да, удалить", callback_data="confirm_delete_audio_files")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_audio")]
            ])
        )
        await state.set_state(AdminStates.waiting_for_delete_confirmation)
    elif delete_action == "delete_single_ogg":
        ogg_files = [f for f in os.listdir(ogg_dir) if f.endswith(".ogg")]
        if not ogg_files:
            await callback.message.edit_text("В папке `data/sounds/ogg` нет OGG файлов для удаления.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_delete_selection")]])) # Added back button
            await state.clear()
            await callback.answer()
            return
        ogg_files.sort()
        await state.update_data(delete_target="ogg", delete_type="single", files_to_list=ogg_files)
        from keyboards import create_file_list_keyboard
        await callback.message.edit_text(
            "Выберите файл OGG для удаления или введите имя файла вручную:",
            reply_markup=create_file_list_keyboard(ogg_files, "ogg"),
        )
        await state.set_state(AdminStates.waiting_for_filename_to_delete)
    elif delete_action == "delete_single_mp3":
        mp3_files = [f for f in os.listdir(mp3_dir) if f.endswith(".mp3")]
        if not mp3_files:
            await callback.message.edit_text("В папке `data/sounds/mp3` нет MP3 файлов для удаления.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_delete_selection")]])) # Added back button
            await state.clear()
            await callback.answer()
            return
        mp3_files.sort()
        await state.update_data(delete_target="mp3", delete_type="single", files_to_list=mp3_files)
        from keyboards import create_file_list_keyboard
        await callback.message.edit_text(
            "Выберите файл MP3 для удаления или введите имя файла вручную:",
            reply_markup=create_file_list_keyboard(mp3_files, "mp3"),
        )
        await state.set_state(AdminStates.waiting_for_filename_to_delete)
    elif delete_action == "delete_single_sounds":
        sounds_files = [f for f in os.listdir(sounds_dir) if os.path.isfile(os.path.join(sounds_dir, f)) and (f.endswith(".mp3") or f.endswith(".ogg"))]
        if not sounds_files:
            await callback.message.edit_text("В папке `data/sounds` нет аудиофайлов (MP3 или OGG) для удаления.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_delete_selection")]])) # Added back button
            await state.clear()
            await callback.answer()
            return
        sounds_files.sort()
        await state.update_data(delete_target="sounds", delete_type="single", files_to_list=sounds_files)
        from keyboards import create_file_list_keyboard
        await callback.message.edit_text(
            "Выберите аудиофайл из `data/sounds` для удаления или введите имя файла вручную:",
            reply_markup=create_file_list_keyboard(sounds_files, "sounds"),
        )
        await state.set_state(AdminStates.waiting_for_filename_to_delete)
    await callback.answer()

@router.callback_query(AdminStates.waiting_for_delete_confirmation, F.data == "confirm_delete_audio_files")
async def confirm_delete_audio_files(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("У вас нет прав для выполнения этой команды.", show_alert=True)
        await state.clear()
        return
    
    state_data = await state.get_data()
    delete_target = state_data.get("delete_target")
    delete_type = state_data.get("delete_type")

    if delete_type != "all": # This handler is only for "delete all" confirmation
        await callback.message.edit_text("Ошибка: неверный тип операции для подтверждения.", reply_markup=None, parse_mode="Markdown")
        await state.clear()
        return

    if not delete_target:
        await callback.message.edit_text("Ошибка: цель удаления не определена. Пожалуйста, начните с /delete_audio_files снова.", reply_markup=None, parse_mode="Markdown")
        await state.clear()
        return

    await callback.message.edit_text("Начинаю удаление аудиофайлов... Это может занять некоторое время.")
    await callback.answer()
    
    log_messages = []
    sounds_dir = os.path.join("data", "sounds")
    ogg_dir = os.path.join(sounds_dir, "ogg")
    mp3_dir = os.path.join(sounds_dir, "mp3")

    from utils.audio_converter import delete_audio_files_from_dir # Import here to avoid circular dependency

    if delete_target == "ogg":
        log_messages.extend(await delete_audio_files_from_dir(ogg_dir, ".ogg"))
    elif delete_target == "mp3":
        log_messages.extend(await delete_audio_files_from_dir(mp3_dir, ".mp3"))
    
    final_message_text = "\n".join(log_messages)
    await callback.message.reply(final_message_text, parse_mode="Markdown")
    await callback.message.answer("Процесс удаления аудиофайлов завершен! Для продолжения удаления, выполните команду /delete_audio_files снова.", reply_markup=main_menu_keyboard)
    await state.clear()

@router.message(AdminStates.waiting_for_filename_to_delete, F.text)
async def process_filename_to_delete(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        await state.clear()
        return
    
    filename_to_delete = message.text.strip()
    state_data = await state.get_data()
    delete_target_dir_type = state_data.get("delete_target") # 'ogg', 'mp3' or 'sounds'

    if not delete_target_dir_type:
        await message.reply("Ошибка: папка для удаления не определена. Пожалуйста, начните с /delete_audio_files снова.", reply_markup=main_menu_keyboard)
        await state.clear()
        return
    
    target_dir = os.path.join("data", "sounds") if delete_target_dir_type == "sounds" else os.path.join("data", "sounds", delete_target_dir_type)
    full_filepath_to_delete = os.path.join(target_dir, filename_to_delete)

    log_messages = []
    if os.path.exists(full_filepath_to_delete):
        try:
            os.remove(full_filepath_to_delete)
            log_messages.append(f"✅ Файл `{html.escape(filename_to_delete)}` успешно удален из `{target_dir.replace(os.sep, '/')}`. Для продолжения удаления, выполните команду /delete\_audio\_files снова.")
        except OSError as e:
            log_messages.append(f"❌ Ошибка файловой системы при удалении `{html.escape(filename_to_delete)}`: {e}")
        except Exception as e:
            log_messages.append(f"❌ Непредвиденная ошибка при удалении файла `{html.escape(filename_to_delete)}`: {e}")
    else:
        log_messages.append(f"⚠️ Файл `{html.escape(filename_to_delete)}` не найден в папке `{target_dir.replace(os.sep, '/')}`.")

    final_message_text = "\n".join(log_messages)
    await message.reply(final_message_text, parse_mode="Markdown", reply_markup=main_menu_keyboard)
    await state.clear()

@router.callback_query(F.data.startswith("select_file_for_deletion_"), AdminStates.waiting_for_filename_to_delete)
async def select_file_for_deletion_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("У вас нет прав для выполнения этой команды.", show_alert=True)
        await state.clear()
        return
    
    parts = callback.data.split("_")
    directory_type = parts[4] # Corrected index
    filename_to_delete = "_".join(parts[5:]) # Reconstruct filename if it contains underscores

    state_data = await state.get_data()
    # Verify that the directory type from callback matches the state's delete_target
    if directory_type != state_data.get("delete_target"):
        await callback.answer("Ошибка: неверное действие.", show_alert=True)
        await state.clear()
        return

    target_dir = os.path.join("data", "sounds") if directory_type == "sounds" else os.path.join("data", "sounds", directory_type)
    full_filepath_to_delete = os.path.join(target_dir, filename_to_delete)

    log_messages = []
    if os.path.exists(full_filepath_to_delete):
        try:
            os.remove(full_filepath_to_delete)
            log_messages.append(f"✅ Файл `{html.escape(filename_to_delete)}` успешно удален из `{target_dir.replace(os.sep, '/')}`. Для продолжения удаления, выполните команду /delete\_audio\_files снова.")
        except OSError as e:
            log_messages.append(f"❌ Ошибка файловой системы при удалении `{html.escape(filename_to_delete)}`: {e}")
        except Exception as e:
            log_messages.append(f"❌ Непредвиденная ошибка при удалении файла `{html.escape(filename_to_delete)}`: {e}")
    else:
        log_messages.append(f"⚠️ Файл `{html.escape(filename_to_delete)}` не найден в папке `{target_dir.replace(os.sep, '/')}`.")

    final_message_text = "\n".join(log_messages)
    await callback.message.reply(final_message_text, parse_mode="Markdown", reply_markup=main_menu_keyboard)
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "back_to_delete_selection", AdminStates.waiting_for_filename_to_delete)
async def back_to_delete_selection(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("У вас нет прав для выполнения этой команды.", show_alert=True)
        await state.clear()
        return
    
    await state.set_state(AdminStates.waiting_for_delete_selection)
    await callback.message.edit_text(
        "Выберите, из какой папки вы хотите удалить аудиофайлы:",
        reply_markup=delete_audio_keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "cancel_delete_audio", AdminStates.waiting_for_delete_selection)
@router.callback_query(F.data == "cancel_delete_audio", AdminStates.waiting_for_delete_confirmation)
@router.callback_query(F.data == "cancel_delete_audio", AdminStates.waiting_for_filename_to_delete)
async def cancel_delete_audio_files(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("У вас нет прав для выполнения этой команды.", show_alert=True)
        await state.clear()
        return
    
    await state.clear()
    await callback.answer("Операция удаления отменена.", show_alert=True)
    await callback.message.edit_text("Операция удаления отменена.", reply_markup=None)

# New message handler for "Отмена" text during delete confirmation
@router.message(AdminStates.waiting_for_delete_confirmation, F.text == "Отмена")
async def cancel_delete_audio_files_message_handler(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        await state.clear()
        return
    await state.clear()
    await message.reply("Операция удаления отменена.", reply_markup=main_menu_keyboard)


# Helper function to update config.py

# Helper functions for name formatting
def _is_garbage_name(name: str) -> bool:
    if not name or not name.strip():
        return True
    
    letter_digit_count = len(re.findall(r'[^\W_]', name, flags=re.UNICODE))
    
    # If the name is very short (e.g., 1-2 chars) and has no letters/digits, consider it garbage.
    if len(name.strip()) <= 2 and letter_digit_count == 0:
        return True

    # If the proportion of non-alphanumeric, non-space, non-Cyrillic characters is high.
    # (e.g., more than 50% are "weird" characters)
    # This pattern matches any character that is *not* a standard letter, number, space, or common punctuation.
    # If a high percentage of the name consists of such 'bad' characters, it's probably garbage.
    # This regex is standard 're' compatible.
    bad_chars_pattern = r'[^a-zA-Z0-9\s.,! ?\'"-\[\]{}()<>/\\+=*&^%$#@`~]'
    num_bad_chars = len(re.findall(bad_chars_pattern, name, flags=re.UNICODE))
    
    if len(name) > 0 and num_bad_chars / len(name) > 0.5: # If more than 50% are "bad" characters
        return True

    return False

def _get_display_name(first_name: str | None, last_name: str | None, username: str | None, registered_name: str | None) -> str:
    # Ensure all inputs are strings or empty strings for processing
    first_name_str = str(first_name or '')
    last_name_str = str(last_name or '')
    username_str = str(username or '')
    registered_name_str = str(registered_name or '')

    full_name_parts = []
    if first_name_str and not _is_garbage_name(first_name_str):
        full_name_parts.append(html.escape(first_name_str))
    if last_name_str and not _is_garbage_name(last_name_str):
        full_name_parts.append(html.escape(last_name_str))
    full_name = " ".join(full_name_parts).strip()

    if full_name:
        return full_name
    elif username_str and not _is_garbage_name(username_str):
        return html.escape(username_str)
    elif registered_name_str and not _is_garbage_name(registered_name_str):
        return html.escape(registered_name_str)
    return "No name"
