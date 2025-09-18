from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from config import ADMIN_ID
from utils.utils import add_word, get_words_alphabetical, delete_word
from utils.data_manager import calculate_overall_score_and_rank, delete_user_stats_entry
import datetime
from database import delete_user_from_db

router = Router()

@router.message(Command("add"))
async def add_new_word(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Пожалуйста, используйте формат: /add английское_слово=русский_перевод")
        return

    word_pair_str = args[1]
    if "=" not in word_pair_str:
        await message.reply("Неверный формат. Используйте: /add английское_слово=русский_перевод")
        return

    en_word, ru_word = word_pair_str.split("=", maxsplit=1)
    en_word = en_word.strip().lower()
    ru_word = ru_word.strip().lower()

    if not en_word or not ru_word:
        await message.reply("Английское слово или русский перевод не могут быть пустыми.")
        return

    await add_word({"en": en_word, "ru": ru_word})
    await message.reply(f"Слово '{en_word}={ru_word}' успешно добавлено в словарь.")

@router.message(Command("list"))
async def list_words(message: Message):
    words = await get_words_alphabetical()
    if not words:
        await message.reply("Словарь пуст.")
        return

    word_list_text = "*Слова в словаре (по алфавиту):*\n"
    for word in words:
        word_list_text += f"  • {word['en']} = {word['ru']}\n"
    await message.reply(word_list_text, parse_mode="Markdown")

@router.message(Command("del"))
async def del_word(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Пожалуйста, используйте формат: /del английское_слово")
        return

    word_to_delete_en = args[1].strip().lower()

    if not word_to_delete_en:
        await message.reply("Пожалуйста, укажите английское слово для удаления.")
        return

    if await delete_word(word_to_delete_en):
        await message.reply(f"Слово '{word_to_delete_en}' успешно удалено из словаря.")
    else:
        await message.reply(f"Слово '{word_to_delete_en}' не найдено в словаре.")

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

        # Determine display name for the user
        display_name = str(user_id) # Default to user ID
        if user_entry.get('first_name') and user_entry.get('last_name'):
            display_name = f"{user_entry['first_name']} {user_entry['last_name']}"
        elif user_entry.get('first_name'):
            display_name = user_entry['first_name']
        elif user_entry.get('registered_name'):
            display_name = user_entry['registered_name']
        elif user_entry.get('username'):
            display_name = f"@{user_entry['username']}"

        # Create a user profile link (HTML format)
        user_link = f"<a href=\"tg://user?id={user_id}\">{display_name}</a>"
        
        stats_text += f"<b>Ранг: {rank}</b> - {user_link} (Балл: <b>{overall_score:.2f}</b>)\n"
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
