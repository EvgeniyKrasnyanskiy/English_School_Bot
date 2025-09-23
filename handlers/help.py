from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from keyboards import main_menu_keyboard
from config import ADMIN_IDS, MAX_USER_WORDS
from aiogram import Bot # Добавлено для явной передачи bot
from utils.audio_cleanup import cleanup_guess_audio
import html # Добавлен импорт html для экранирования

router = Router()

@router.message(F.text == "❓ Справка")
async def show_help(message: Message, state: FSMContext, bot: Bot):
    # Удаляем аудиофайлы из игры "Угадай слово" при переходе к справке
    await cleanup_guess_audio(message, state, bot)
    
    help_text = (
        "Это бот создан для помощи школьникам в изучении английского языка.\n\n" +
        "<b>Основные разделы:</b>\n" +
        "📖 Учить слова: Просматривайте карточки с английскими словами и их русским переводом.\n" +
        "🎮 Игры: Играйте в викторины для закрепления знаний.\n" +
        "📝 Тест знаний: Пройдите небольшой тест из нескольких вопросов.\n" +
        "📊 Статистика: Посмотрите свои успехи и статистику.\n" +
        "ℹ️ Справка: Краткая информация о боте и его функциях.\n\n" +
        "Для возвращения в главное меню, нажмите кнопку '⬆️ В главное меню'.\n\n" +
        "/start - если не отображаются кнопки (перезапуск бота)\n\n" +
        "<b>📚 Управление словами:</b>\n" +
        f"/my_set - управлять своим личным набором слов (создать, добавить, удалить, просмотреть). <b>Максимум {MAX_USER_WORDS} слов.</b>\n" +
        f"/switch_set - выбрать другой набор слов для изучения\n\n" +
        f"/list <code>{html.escape('[имя_файла.json]')}</code> - список слов из указанного файла (по умолчанию ваш текущий активный набор)\n\n" +
        f"  • Обратите внимание! Добавлять или удалять слова вы можете только в своём собственном наборе слов после его создания!" 
    )
    
    # Добавляем админские команды, если пользователь - админ
    if message.from_user.id in ADMIN_IDS:
        admin_commands = (
            "\n\n<b>🔧 Админские команды:</b>\n" +
            "<b>📁 Управление файлами наборов слов:</b>\n" +
            f"/files - показать все доступные файлы\n" +
            f"/switch_set_to_all <code>{html.escape('[имя файла]')}</code> - изменить активный файл всем юзерам\n" +
            f"/current_files - показать активные файлы всех юзеров\n" +
            f"/create_file <code>{html.escape('[имя файла]')}</code> - создать файл\n" +
            f"/delete_file <code>{html.escape('[имя файла]')}</code> - удалить файл\n\n" +
            "<b>📝 Управление словами:</b>\n" +
            f"/add <code>{html.escape('[имя файла.json]')}</code> слово=перевод - добавить слово в указанный файл (по умолчанию ваш текущий)\n" +
            f"/del <code>{html.escape('[имя файла.json]')}</code> слово - удалить слово из указанного файла (по умолчанию ваш текущий)\n" +
            f"/deduplicate_words <code>{html.escape('[имя файла.json]')}</code> - удалить дубликаты слов из указанного файла (по умолчанию words.json)\n" +
            f"/admin_list <code>{html.escape('[имя файла.json]')}</code> - список слов из указанного файла (по умолчанию ваш текущий)\n\n" +
            "<b>👥 Управление пользователями:</b>\n" +
            f"/users - показать список всех юзеров\n" +
            f"/stats <code>[class=ID_класса]</code> - показать статистику всех юзеров или только юзеров указанного класса\n" +
            f"/deluser <code>ID</code> - удалить пользователя\n" +
            f"/ban <code>ID</code> - заблокировать пользователя\n" +
            f"/unban <code>ID</code> - разблокировать пользователя\n\n" +
            "<b>⚙️ Утилиты:</b>\n" +
            f"/settings - динамическое изменение настроек бота\n" +
            f"/convert_audio - конвертировать аудиофайлы OGG в MP3\n" +
            f"/new_sound - добавить новый аудиофайл\n" +
            f"/send <code>[текст]</code> или <code>class=ID_класса [текст]</code> - отправить сообщение пользователям\n\n" +
            "<b>💡 Примечание:</b> Все команды работают с текущим активным файлом слов."
        )
        help_text += admin_commands
    
    await message.answer(help_text, reply_markup=main_menu_keyboard, parse_mode="HTML")

@router.message(Command("help"))
async def show_help_command(message: Message, state: FSMContext, bot: Bot):
    """Обработчик команды /help"""
    await show_help(message, state, bot)
