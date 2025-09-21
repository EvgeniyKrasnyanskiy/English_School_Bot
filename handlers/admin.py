from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from config import ADMIN_ID
from utils.utils import add_word, get_words_alphabetical, delete_word
from utils.data_manager import calculate_overall_score_and_rank, delete_user_stats_entry
from utils.word_manager import word_manager
import datetime
from utils.audio_converter import convert_ogg_to_mp3 # Импорт для админской команды конвертации
from database import delete_user_from_db, get_all_users # Импорт get_all_users
import html # Import the html module for escaping
import re # Add this import

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram import Bot # Импорт Bot для загрузки файлов
import os # Импорт os для работы с файловой системой
import uuid # Импорт uuid для генерации уникальных имен файлов
from keyboards import cancel_keyboard_for_filename # Импорт клавиатуры для отмены
from keyboards import main_menu_keyboard # Импорт клавиатуры для отмены


class AdminStates(StatesGroup):
    waiting_for_voice = State()
    waiting_for_audio_filename = State()


router = Router()

@router.message(Command("add"))
async def add_new_word(message: Message):
    if message.from_user.id != ADMIN_ID:
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
    if message.from_user.id != ADMIN_ID:
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
    if message.from_user.id != ADMIN_ID:
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
    if message.from_user.id != ADMIN_ID:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    ranked_users = await calculate_overall_score_and_rank()

    if not ranked_users:
        await message.reply("Статистика по пользователям пока отсутствует.")
        return

    stats_text = "<b>Общая статистика пользователей (по рейтингу):</b>\n\n"
    for user_entry in ranked_users:
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
    if message.from_user.id != ADMIN_ID:
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
    if message.from_user.id != ADMIN_ID:
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
    if message.from_user.id != ADMIN_ID:
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
    if message.from_user.id != ADMIN_ID:
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
    if message.from_user.id != ADMIN_ID:
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
    if message.from_user.id != ADMIN_ID:
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
    if message.from_user.id != ADMIN_ID:
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
    if message.from_user.id != ADMIN_ID:
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
    if message.from_user.id != ADMIN_ID:
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

@router.message(Command("new_sound"))
async def add_new_audio_command(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    await message.reply("Пожалуйста, отправьте голосовое сообщение (аудиофайл), которое вы хотите добавить.")
    await state.set_state(AdminStates.waiting_for_voice)

@router.message(AdminStates.waiting_for_voice, F.voice)
async def process_voice_for_new_audio(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != ADMIN_ID:
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
    await message.reply("Голосовое сообщение получено. Как вы хотите назвать этот аудиофайл (без расширения)?")
    await state.set_state(AdminStates.waiting_for_audio_filename)

@router.message(AdminStates.waiting_for_audio_filename, F.text)
async def process_audio_filename(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != ADMIN_ID:
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
    finally:
        # Удаляем временную папку
        temp_audio_dir = os.path.join("data", "temp_audio")
        if os.path.exists(temp_audio_dir):
            for item in os.listdir(temp_audio_dir):
                os.remove(os.path.join(temp_audio_dir, item))
            os.rmdir(temp_audio_dir)
        await state.clear()


@router.message(AdminStates.waiting_for_audio_filename, ~F.text)
async def process_invalid_audio_filename(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.reply("У вас нет прав для выполнения этой команды.")
        await state.clear()
        return
    await message.reply("Пожалуйста, введите корректное имя файла (текст). Если вы хотите отменить, введите /cancel.")

@router.callback_query(F.data == "cancel_audio_filename_entry")
async def cancel_audio_filename_entry(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет прав для выполнения этой команды.", show_alert=True)
        await state.clear()
        return

    await callback.answer("Ввод имени файла отменен.", show_alert=True)
    await callback.message.edit_text("Ввод имени файла отменен.", reply_markup=None)
    await state.clear()
    await callback.message.answer("Возвращаемся в главное меню.", reply_markup=main_menu_keyboard)

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
