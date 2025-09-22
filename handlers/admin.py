from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from config import ADMIN_IDS
from utils.utils import add_word, get_words_alphabetical, delete_word
from utils.data_manager import calculate_overall_score_and_rank, delete_user_stats_entry
from utils.word_manager import word_manager
import datetime
from utils.audio_converter import convert_ogg_to_mp3 # Импорт для админской команды конвертации
from database import delete_user_from_db, get_all_users # Импорт get_all_users
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
from keyboards import cancel_keyboard


class AdminStates(StatesGroup):
    waiting_for_voice = State()
    waiting_for_audio_filename = State()
    waiting_for_settings_selection = State() # New state for settings menu
    waiting_for_setting_value = State() # New state for setting new value
    waiting_for_ban_user_id = State()
    waiting_for_unban_user_id = State()
    waiting_for_broadcast_text = State()

router = Router()

# Dictionary to hold configurable settings and their types
CONFIGURABLE_SETTINGS = {
    "TEST_QUESTIONS_COUNT": {"type": int, "description": "Количество вопросов в тесте"},
    "ADMIN_IDS": {"type": list, "description": "Список ID администраторов"},
    "RECALL_TYPING_COUNTDOWN_SECONDS": {"type": float, "description": "Время на ввод в игре 'Ввод по памяти'"},
    "MAX_USER_WORDS": {"type": int, "description": "Максимальное количество слов в пользовательском наборе"},
}

@router.message(Command("add"))
async def add_new_word(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    # /add [файл_слов] английское_слово=русский_перевод
    parts = message.text.split(maxsplit=2)
    
    target_filename = "words.json"
    word_pair_str_index = 1

    if len(parts) > 1 and parts[1].endswith(".json"):
        target_filename = parts[1]
        word_pair_str_index = 2
    elif len(parts) > 1 and parts[1].startswith("-"):
        await message.reply("Неверный формат команды. Укажите имя файла перед парой слов или не указывайте его для использования файла по умолчанию.")
        return

    if len(parts) < word_pair_str_index + 1:
        await message.reply("Пожалуйста, используйте формат: /add [имя_файла.json] английское_слово=русский_перевод")
        return

    word_pair_str = parts[word_pair_str_index]
    if "=" not in word_pair_str:
        await message.reply("Неверный формат. Используйте: английское_слово=русский_перевод")
        return

    en_word, ru_word = word_pair_str.split("=", maxsplit=1)
    en_word = en_word.strip().lower()
    ru_word = ru_word.strip().lower()

    if not en_word or not ru_word:
        await message.reply("Английское слово или русский перевод не могут быть пустыми.")
        return

    if await add_word({"en": en_word, "ru": ru_word}, filename=target_filename):
        await message.reply(f"Слово '{en_word}={ru_word}' успешно добавлено в файл '{target_filename}'.")
    else:
        await message.reply(f"Не удалось добавить слово '{en_word}={ru_word}' в файл '{target_filename}'.")

@router.message(Command("admin_list"))
async def list_words(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    # /list [файл_слов.json]
    parts = message.text.split(maxsplit=1)
    
    target_filename = word_manager.get_user_current_file(message.from_user.id) # По умолчанию - текущий файл админа

    if len(parts) > 1:
        potential_filename = parts[1].strip()
        if potential_filename.endswith(".json"):
            target_filename = potential_filename
        else:
            await message.reply("Неверный формат команды. Используйте: `/list [имя_файла.json]` или `/list` для просмотра текущего файла.", parse_mode="Markdown")
            return
    
    words = await get_words_alphabetical(filename=target_filename)
    if not words:
        await message.reply(f"Словарь файла `{target_filename}` пуст или файл не найден.", parse_mode="Markdown")
        return

    word_list_text = f"*Слова в файле {target_filename} (по алфавиту):*\n"
    for word in words:
        word_list_text += f"  • {word['en']} = {word['ru']}\n"
    await message.reply(word_list_text, parse_mode="Markdown")

@router.message(Command("del"))
async def del_word(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    # /del [файл_слов.json] английское_слово
    parts = message.text.split(maxsplit=2)
    
    target_filename = "words.json"
    word_to_delete_index = 1

    if len(parts) > 1 and parts[1].endswith(".json"):
        target_filename = parts[1]
        word_to_delete_index = 2
    elif len(parts) > 1 and parts[1].startswith("-"):
        await message.reply("Неверный формат команды. Укажите имя файла перед словом или не указывайте его для использования файла по умолчанию.")
        return

    if len(parts) < word_to_delete_index + 1:
        await message.reply("Пожалуйста, используйте формат: /del [имя_файла.json] английское_слово")
        return

    word_to_delete_en = parts[word_to_delete_index].strip().lower()

    if not word_to_delete_en:
        await message.reply("Пожалуйста, укажите английское слово для удаления.")
        return

    if await delete_word(word_to_delete_en, filename=target_filename):
        await message.reply(f"Слово '{word_to_delete_en}' успешно удалено из файла '{target_filename}'.")
    else:
        await message.reply(f"Слово '{word_to_delete_en}' не найдено в файле '{target_filename}'.")

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
        current_user_stats = user_entry['stats'] # Get the full stats for the current user

        # Get detailed stats with default values
        total_correct_answers = current_user_stats.get('total_correct_answers', 0)
        best_test_score = current_user_stats.get('best_test_score', 0)
        last_activity_date_str = current_user_stats.get('last_activity_date', 'N/A')
        
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
        stats_text += f"  - ОКПО: <b>{total_correct_answers}</b> | Тест: <b>{best_test_score}</b> | ПА: <b>{formatted_last_activity}</b>\n"
        
        # Removed game stats as per user request
        # stats_text += f"\n"

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
    stats_deleted = await delete_user_stats_entry(str(user_id_to_delete))

    if db_deleted and stats_deleted:
        await message.reply(f"Пользователь с ID {user_id_to_delete} успешно удален из базы данных и статистики.")
    elif db_deleted:
        await message.reply(f"Пользователь с ID {user_id_to_delete} удален из базы данных, но не найден в статистике.")
    elif stats_deleted:
        await message.reply(f"Пользователь с ID {user_id_to_delete} удален из статистики, но не найден в базе данных.")
    else:
        await message.reply(f"Пользователь с ID {user_id_to_delete} не найден ни в базе данных, ни в статистике.")

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

@router.message(Command("switch"))
async def switch_word_file(message: Message):
    """Переключает активный файл со словами."""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Пожалуйста, используйте формат: /switch имя_файла")
        return

    filename = args[1].strip()
    if word_manager.set_user_current_file(message.from_user.id, filename):
        current_info = word_manager.get_file_info(filename)
        await message.reply(
            f"✅ Файл успешно переключен на *{filename}*\n"
            f"📊 Слов в файле: {current_info['word_count']}\n"
            f"📁 Размер файла: {current_info['file_size']} байт",
            parse_mode="Markdown"
        )
    else:
        await message.reply(f"❌ Файл '{filename}' не найден. Используйте /files для просмотра доступных файлов.")

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
    if filename == "words.json":
        await message.reply("❌ Нельзя удалить основной файл 'words.json'.")
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
    
    parts = message.text.split(maxsplit=1)
    target_filename = "words.json"

    if len(parts) > 1:
        potential_filename = parts[1].strip()
        if potential_filename.endswith(".json"):
            target_filename = potential_filename
        else:
            await message.reply("Неверный формат команды. Используйте: `/deduplicate_words [имя_файла.json]` или `/deduplicate_words` для обработки файла по умолчанию.", parse_mode="Markdown")
            return

    await message.reply(f"Начинаю удаление дубликатов из файла `{target_filename}`...")
    duplicates_removed = word_manager.remove_duplicates_from_file(target_filename)

    if duplicates_removed > 0:
        await message.reply(f"✅ Удалено {duplicates_removed} дубликатов из файла `{target_filename}`.", parse_mode="Markdown")
    else:
        await message.reply(f"ℹ️ В файле `{target_filename}` дубликатов не найдено.", parse_mode="Markdown")

@router.message(Command("current_file"))
async def show_current_file(message: Message):
    """Показывает информацию о текущем активном файле."""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    current_file_for_admin = word_manager.get_user_current_file(message.from_user.id)
    info = word_manager.get_file_info(current_file_for_admin)
    
    if info:
        await message.reply(
            f"📁 <b>Текущий активный файл (для вас):</b> {html.escape(current_file_for_admin)}\n"
            f"📊 Количество слов: {info['word_count']}\n"
            f"📁 Размер файла: {info['file_size']} байт",
            parse_mode="HTML"
        )
    else:
        await message.reply("❌ Ошибка получения информации о текущем файле. Возможно, файл не существует или поврежден.")

@router.message(Command("convert_audio"))
async def convert_audio_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    initial_message = (
        "⚙️ *Конвертер аудиофайлов OGG в MP3:*\n\n"
        "Бот будет искать файлы `.ogg` в папке `data/sounds`.\n"
        "После успешной конвертации, оригинальные `.ogg` файлы будут перемещены в подпапку `data/sounds/ogg`."
    )
    await message.reply(initial_message, parse_mode="Markdown")
    
    await message.reply("Начинаю конвертацию аудиофайлов OGG в MP3. Это может занять некоторое время...")
    log_messages, _ = await convert_ogg_to_mp3()
    for log_msg in log_messages:
        await message.reply(log_msg, parse_mode="Markdown")

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

@router.message(Command("send"))
async def send_message_command(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Пожалуйста, используйте формат: `/send [текст]` или `/send class=2в [текст]`", parse_mode="Markdown")
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
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    await message.reply("Пожалуйста, отправьте голосовое сообщение (аудиофайл), которое вы хотите добавить.", reply_markup=cancel_keyboard)
    await state.set_state(AdminStates.waiting_for_voice)

@router.message(AdminStates.waiting_for_voice, F.voice)
async def process_voice_for_new_audio(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        await state.clear()
        return

    # Создаем папку data/temp_audio если ее нет
    temp_audio_dir = os.path.join("data", "temp_audio")
    os.makedirs(temp_audio_dir, exist_ok=True)

    # Генерируем уникальное имя для временного OGG файла
    temp_ogg_filename = f"{uuid.uuid4().hex}.ogg"
    temp_ogg_filepath = os.path.join(temp_audio_dir, temp_ogg_filename)

    # Загружаем голосовое сообщение
    file_id = message.voice.file_id
    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, temp_ogg_filepath)

    await state.update_data(temp_ogg_filepath=temp_ogg_filepath)
    await message.reply("Голосовое сообщение получено. Как вы хотите назвать этот аудиофайл (без расширения)?", reply_markup=cancel_keyboard_for_filename)
    await state.set_state(AdminStates.waiting_for_audio_filename)

@router.message(AdminStates.waiting_for_audio_filename, F.text)
async def process_audio_filename(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        await state.clear()
        return

    filename = message.text.strip().lower()
    if not filename:
        await message.reply("Имя файла не может быть пустым. Пожалуйста, введите имя файла или /cancel для отмены.")
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

    # Перемещаем файл с временного пути в data/sounds с новым именем
    final_ogg_filename = f"{filename}.ogg"
    final_ogg_filepath = os.path.join(target_sounds_dir, final_ogg_filename)
    final_mp3_filepath = os.path.join(target_sounds_dir, "mp3", f"{filename}.mp3")

    # Проверяем, существует ли файл с таким именем (как OGG, так и MP3)
    old_mp3_filepath = os.path.join(target_sounds_dir, f"{filename}.mp3")
    if os.path.exists(final_ogg_filepath) or os.path.exists(final_mp3_filepath) or os.path.exists(old_mp3_filepath):
        await message.reply(
            f"Файл с именем '{filename}.ogg' или '{filename}.mp3' уже существует. "
            "Пожалуйста, введите другое имя для аудиофайла или нажмите Отмена.",
            reply_markup=cancel_keyboard_for_filename
        )
        return

    try:
        os.replace(temp_ogg_filepath, final_ogg_filepath)
        await message.reply(f"Файл '{final_ogg_filename}' успешно сохранен. Запускаю конвертацию... ")

        # Запускаем процесс конвертации
        log_messages, conversion_successful = await convert_ogg_to_mp3() # Используем существующую функцию
        for log_msg in log_messages:
            await message.reply(log_msg)

        if conversion_successful:
            await message.reply("Процесс добавления и конвертации аудиофайла завершен!")
        else:
            await message.reply("Добавлено успешно, но конвертация не удалась. Конвертируйте самостоятельно или настройте конвертер.")

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
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("У вас нет прав для выполнения этой команды.", show_alert=True)
        await state.clear()
        return

    state_data = await state.get_data()
    temp_ogg_filepath = state_data.get("temp_ogg_filepath")
    if temp_ogg_filepath and os.path.exists(temp_ogg_filepath):
        os.remove(temp_ogg_filepath)
    
    temp_audio_dir = os.path.join("data", "temp_audio")
    if os.path.exists(temp_audio_dir):
        for item in os.listdir(temp_audio_dir):
            os.remove(os.path.join(temp_audio_dir, item))
        os.rmdir(temp_audio_dir)
    
    await state.clear()
    await callback.answer("Операция отменена.", show_alert=True)
    await callback.message.edit_text("Операция отменена.", reply_markup=None)
    await callback.message.answer("Возвращаемся в главное меню.", reply_markup=main_menu_keyboard)

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
            # or quoted strings. We'll try to parse them.
            if new_value_str.startswith('"') and new_value_str.endswith('"'):
                new_value = [item.strip() for item in new_value_str[1:-1].split(',')]
            elif new_value_str.startswith('[') and new_value_str.endswith(']'):
                new_value = [item.strip() for item in new_value_str[1:-1].split(',')]
            else:
                new_value = [item.strip() for item in new_value_str.split(',')]
        else:
            new_value = new_value_str.strip('""') # Treat as string
        
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
                value_to_write = f"\"{new_value}\""
            elif isinstance(new_value, list):
                value_to_write = json.dumps(new_value, ensure_ascii=False)
            else:
                value_to_write = str(new_value)
            
            new_file_content_lines.append(f"{setting_name} = {value_to_write}{comment}\n")
            updated = True
        else: # Add non-empty, non-updated lines, ensuring single newline
            new_file_content_lines.append(stripped_line + '\n')
    
    if not updated: # Should not happen for predefined settings, but as a fallback for new settings
        value_to_write = ""
        if isinstance(new_value, str):
            value_to_write = f"\"{new_value}\""
        elif isinstance(new_value, list):
            value_to_write = json.dumps(new_value, ensure_ascii=False)
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
    await callback.message.answer("Возвращаемся в главное меню.", reply_markup=main_menu_keyboard)

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
