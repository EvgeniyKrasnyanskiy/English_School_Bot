from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import main_menu_keyboard, confirm_create_set_keyboard, get_my_set_keyboard, create_file_selection_keyboard, delete_my_set_confirm_keyboard, cancel_add_del_keyboard
from utils.word_manager import word_manager
from utils.bad_words import is_bad_word
from database import get_user_display_name
from typing import Dict, List
import html
import os
import logging
from config import MAX_USER_WORDS # Импортируем MAX_USER_WORDS из config.py
from utils.data_manager import get_banned_users, get_image_filepath, get_audio_filepath
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


class UserWordStates(StatesGroup):
    waiting_for_create_confirm = State()
    waiting_for_add_word = State()
    waiting_for_del_word = State()
    waiting_for_delete_confirm = State()
    word_list_visible = State() # New state to track word list visibility


router = Router()

# Заглушка для получения user_display_name, будет заменена на реальную функцию
async def _get_user_display_name(user_id: int) -> str:
    user_name_from_db = await get_user_display_name(user_id)
    if user_name_from_db:
        return user_name_from_db
    return "Пользователь"

@router.message(Command("my_set"))
async def my_word_set_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in await get_banned_users():
        await message.reply("Вы заблокированы и не можете использовать функционал пользовательских наборов слов.")
        return
    user_display_name = await _get_user_display_name(user_id)
    
    # Определяем базовое имя файла для пользовательского набора (без динамического суффикса и расширения)
    expected_custom_filename_base = word_manager.get_user_custom_filename(user_id, user_display_name)
    
    # Ищем файлы, которые начинаются с этого базового имени
    available_personal_files = [f for f in word_manager.get_available_files() if f.startswith(expected_custom_filename_base)]
    
    has_personal_set = len(available_personal_files) > 0
    current_user_file = word_manager.get_user_current_file(user_id) # Получаем текущий активный файл пользователя

    await state.update_data(word_list_visible=False) # Initialize word list visibility

    if has_personal_set:
        # Если есть несколько личных наборов, выберем первый (можно добавить логику выбора новейшего)
        selected_personal_file = available_personal_files[0]
        
        # Если текущий файл пользователя не его личный набор, автоматически переключаем на него
        if current_user_file != selected_personal_file:
            word_manager.set_user_current_file(user_id, selected_personal_file, user_display_name)
            current_user_file = selected_personal_file # Обновляем для дальнейшего использования

        base_personal_filename = word_manager.get_user_custom_filename(user_id, user_display_name)
        is_personal_set = current_user_file.startswith(base_personal_filename) and current_user_file.endswith(".json")
        info = word_manager.get_file_info(current_user_file)
        if info:
            words = word_manager.load_words_from_file(os.path.join(word_manager.data_dir, "words", current_user_file))
            
            message_text = f"📁 <b>Ваш личный набор слов:</b> {html.escape(current_user_file)}\n"
            message_text += f"📊 Количество слов: {info['word_count']} / {MAX_USER_WORDS}\n"
            message_text += f"⚠️ Примечание: Для этих слов могут отсутствовать картинки и аудио.\n\n"
    
            if words:
                message_text += "\nВыберите действие:"
            else:
                message_text += "Ваш личный набор слов пуст. Добавьте слова с помощью кнопки '➕ Добавить слово'.\n\n"
                message_text += "\nВыберите действие:"
            
            await message.answer(
                message_text,
                parse_mode="HTML",
                reply_markup=get_my_set_keyboard(is_personal_set=is_personal_set, show_list_button_text="📖 Показать список слов")
            )
        else:
            # Если файл существует, но информация не получена (поврежден), предлагаем создать новый
            await message.answer(
                "Не удалось получить информацию о вашем личном наборе слов. Возможно, файл поврежден. "
                "Пожалуйста, попробуйте создать новый набор или свяжитесь с администратором.",
                reply_markup=main_menu_keyboard
            )
            await state.clear()
    else:
        # Предлагаем создать новый набор, так как личного набора нет
        await message.answer(
            f"У вас пока нет личного набора слов. Вы хотите создать его?\n"
            f"Ваш набор будет назван: <b>{html.escape(word_manager.get_user_custom_filename(user_id, user_display_name))}*****.json</b>\n"
            f"Где ***** - случайные символы.",
            parse_mode="HTML",
            reply_markup=confirm_create_set_keyboard
        )
        await state.set_state(UserWordStates.waiting_for_create_confirm)


@router.callback_query(F.data == "create_my_word_set", UserWordStates.waiting_for_create_confirm)
async def create_my_word_set(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id in await get_banned_users():
        await callback.answer("Вы заблокированы и не можете использовать функционал пользовательских наборов слов.", show_alert=True)
        await state.clear()
        return
    await callback.answer()
    user_id = callback.from_user.id
    user_display_name = await _get_user_display_name(user_id)
    logger.debug(f"[create_my_word_set] User ID: {user_id}, Display Name: {user_display_name}")

    created_filename = word_manager.create_new_file(user_id, user_display_name) # Passing user_display_name

    if created_filename:
        logger.debug(f"[create_my_word_set] Successfully created and set current file to: {created_filename}")
        
        # После создания сразу показываем пустой список слов и кнопки управления
        await state.update_data(word_list_visible=False) # Initialize word list visibility
        await callback.message.edit_text(
            f"✅ Ваш личный набор слов <b>{html.escape(created_filename)}</b> успешно создан!\n"
            f"Ваш набор слов пуст ({0} / {MAX_USER_WORDS}). Добавьте слова с помощью кнопки '➕ Добавить слово'.\n\n"
            f"⚠️ Примечание: Для этих слов могут отсутствовать картинки и аудио.\n\n"
            f"Выберите действие:",
            parse_mode="HTML",
            reply_markup=get_my_set_keyboard(is_personal_set=True, show_list_button_text="📖 Показать список слов")
        )
    else:
        await callback.message.edit_text(
            "❌ Не удалось создать ваш личный набор слов. Возможно, он уже существует или произошла ошибка.",
            reply_markup=None # Убираем reply_markup из edit_text
        )
        await callback.message.answer("Возвращаемся в главное меню.", reply_markup=main_menu_keyboard)
    await state.clear()


@router.callback_query(F.data == "back_to_main_from_my_set")
async def back_to_main_from_my_set_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("Возвращаемся в главное меню.", reply_markup=None)
    await callback.message.answer("Возвращаемся в главное меню.", reply_markup=main_menu_keyboard)


@router.callback_query(F.data == "cancel_create_word_set", UserWordStates.waiting_for_create_confirm)
async def cancel_create_word_set(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("Создание набора слов отменено.", reply_markup=None)


# Удаляем старый обработчик для команды /my_list, так как его функционал теперь в /my_set
# @router.message(Command("my_list"))
# async def my_list_command(message: Message, state: FSMContext):
#     user_id = message.from_user.id
#     user_display_name = await _get_user_display_name(user_id)
#     custom_filename = word_manager.get_user_custom_filename(user_id, user_display_name)

#     if not os.path.exists(os.path.join(word_manager.data_dir, custom_filename)):
#         await message.answer(
#             "У вас нет личного набора слов. Создайте его с помощью команды /my_set сначала.",
#             reply_markup=main_menu_keyboard
#         )
#         await state.clear()
#         return

#     words = word_manager.load_words_from_file(os.path.join(word_manager.data_dir, custom_filename))
#     if not words:
#         await message.answer(
#             "Ваш личный набор слов пуст. Добавьте слова с помощью команды /add_my_word.",
#             reply_markup=main_menu_keyboard
#         )
#         await state.clear()
#         return

#     word_list_text = f"📁 <b>Ваш личный набор слов ({len(words)}):</b>\n\n"
#     for word_pair in words:
#         word_list_text += f"  • <code>{html.escape(word_pair['en'])} = {html.escape(word_pair['ru'])}</code>\n"
    
#     await message.answer(
#         word_list_text,
#         parse_mode="HTML",
#         reply_markup=my_set_keyboard # Возвращаем клавиатуру управления личным набором
#     )
#     await state.clear()


@router.callback_query(F.data == "add_my_word")
async def add_my_word_command(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id in await get_banned_users():
        await callback.answer("Вы заблокированы и не можете использовать функционал пользовательских наборов слов.", show_alert=True)
        await state.clear()
        return
    await callback.answer()
    user_id = callback.from_user.id
    current_user_file = word_manager.get_user_current_file(user_id) # Получаем текущий активный файл пользователя
    current_file_path = os.path.join(word_manager.data_dir, "words", current_user_file)
    logger.debug(f"[add_my_word_command] User ID: {user_id}, Current User File: {current_user_file}")
    logger.debug(f"[add_my_word_command] Checking file existence for path: {current_file_path}, Exists: {os.path.exists(current_file_path)}")

    if not os.path.exists(current_file_path) or current_user_file == "all_words.json":
        await callback.message.edit_text(
            "У вас нет личного набора слов. Создайте его с помощью команды /my_set сначала."
        )
        await callback.message.answer(
            "Возвращаемся в главное меню.",
            reply_markup=main_menu_keyboard
        )
        await state.clear()
        return

    await callback.message.edit_text(
        f"Пожалуйста, отправьте английское слово и его русский перевод в формате: <code>английское_слово=русский_перевод</code>\n"
        f"(Максимум слов в наборе: {MAX_USER_WORDS})",
        parse_mode="HTML",
        reply_markup=cancel_add_del_keyboard
    )
    await state.set_state(UserWordStates.waiting_for_add_word)


@router.message(UserWordStates.waiting_for_add_word, F.text)
async def process_add_my_word(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in await get_banned_users():
        await message.reply("Вы заблокированы и не можете использовать функционал пользовательских наборов слов.")
        await state.clear()
        return
    current_user_file = word_manager.get_user_current_file(user_id) # Получаем текущий активный файл пользователя
    current_file_path = os.path.join(word_manager.data_dir, "words", current_user_file)
    logger.debug(f"[process_add_my_word] User ID: {user_id}, Current User File: {current_user_file}")
    logger.debug(f"[process_add_my_word] Checking file existence for path: {current_file_path}, Exists: {os.path.exists(current_file_path)}")

    if not os.path.exists(current_file_path) or current_user_file == "all_words.json":
        await message.answer(
            "У вас нет личного набора слов. Создайте его с помощью команды /my_set сначала.",
            reply_markup=main_menu_keyboard
        )
        await state.clear()
        return

    # Проверка на лимит слов
    current_words = word_manager.load_words_from_file(os.path.join(word_manager.data_dir, "words", current_user_file))
    if len(current_words) >= MAX_USER_WORDS:
        state_data = await state.get_data()
        word_list_visible = state_data.get("word_list_visible", False)
        show_list_button_text = "Скрыть список слов" if word_list_visible else "📖 Показать список слов"
        await message.answer(
            f"❌ Вы достигли максимального количества слов ({MAX_USER_WORDS}) в вашем личном наборе. "
            "Пожалуйста, удалите некоторые слова, прежде чем добавлять новые.",
            parse_mode="HTML",
            reply_markup=get_my_set_keyboard(is_personal_set=True, show_list_button_text=show_list_button_text)
        )
        await state.clear()
        return

    word_pair_str = message.text.strip()
    if "=" not in word_pair_str:
        await message.answer(
            "Неверный формат. Используйте: <code>английское_слово=русский_перевод</code>. "
            "Пожалуйста, попробуйте снова или нажмите '❌ Отмена'.",
            parse_mode="HTML",
            reply_markup=cancel_add_del_keyboard
        )
        return

    en_word, ru_word = word_pair_str.split("=", maxsplit=1)
    en_word = en_word.strip().lower()
    ru_word = ru_word.strip().lower()

    if not en_word or not ru_word:
        await message.answer(
            "Английское слово или русский перевод не могут быть пустыми. "
            "Пожалуйста, попробуйте снова или /cancel для отмены."
        )
        return

    if is_bad_word(en_word) or is_bad_word(ru_word):
        state_data = await state.get_data()
        word_list_visible = state_data.get("word_list_visible", False)
        show_list_button_text = "Скрыть список слов" if word_list_visible else "📖 Показать список слов"
        await message.answer(
            "Это слово нельзя добавить. Оно находится в списке запрещенных слов.",
            reply_markup=get_my_set_keyboard(is_personal_set=True, show_list_button_text=show_list_button_text)
        )
        await state.clear()
        return

    if word_manager.add_word_to_file(current_user_file, {"en": en_word, "ru": ru_word}):
        state_data = await state.get_data()
        word_list_visible = state_data.get("word_list_visible", False)
        show_list_button_text = "Скрыть список слов" if word_list_visible else "📖 Показать список слов"
        await message.answer(
            f"✅ Слово <code>{html.escape(en_word)}={html.escape(ru_word)}</code> успешно добавлено в ваш личный набор!\n"
            "⚠️ Примечание: Для этого слова могут отсутствовать картинки и аудио.",
            parse_mode="HTML",
            reply_markup=get_my_set_keyboard(is_personal_set=True, show_list_button_text=show_list_button_text)
        )
    else:
        state_data = await state.get_data()
        word_list_visible = state_data.get("word_list_visible", False)
        show_list_button_text = "Скрыть список слов" if word_list_visible else "📖 Показать список слов"
        await message.answer(
            "❌ Не удалось добавить слово. Возможно, произошла ошибка.",
            parse_mode="HTML",
            reply_markup=get_my_set_keyboard(is_personal_set=True, show_list_button_text=show_list_button_text)
        )
    await state.clear()


@router.callback_query(F.data == "del_my_word")
async def del_my_word_command(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id in await get_banned_users():
        await callback.answer("Вы заблокированы и не можете использовать функционал пользовательских наборов слов.", show_alert=True)
        await state.clear()
        return
    await callback.answer()
    user_id = callback.from_user.id
    current_user_file = word_manager.get_user_current_file(user_id) # Получаем текущий активный файл пользователя
    current_file_path = os.path.join(word_manager.data_dir, "words", current_user_file)
    logger.debug(f"[del_my_word_command] User ID: {user_id}, Current User File: {current_user_file}")
    logger.debug(f"[del_my_word_command] Checking file existence for path: {current_file_path}, Exists: {os.path.exists(current_file_path)}")

    if not os.path.exists(current_file_path) or current_user_file == "all_words.json":
        await callback.message.edit_text(
            "У вас нет личного набора слов. Создайте его с помощью команды /my_set сначала.",
            reply_markup=main_menu_keyboard
        )
        await state.clear()
        return

    await callback.message.edit_text(
        "Пожалуйста, отправьте английское слово, которое вы хотите удалить из вашего набора.",
        reply_markup=cancel_add_del_keyboard
    )
    await state.set_state(UserWordStates.waiting_for_del_word)


@router.message(UserWordStates.waiting_for_del_word, F.text)
async def process_del_my_word(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in await get_banned_users():
        await message.reply("Вы заблокированы и не можете использовать функционал пользовательских наборов слов.")
        await state.clear()
        return
    current_user_file = word_manager.get_user_current_file(user_id) # Получаем текущий активный файл пользователя
    current_file_path = os.path.join(word_manager.data_dir, "words", current_user_file)
    logger.debug(f"[process_del_my_word] User ID: {user_id}, Current User File: {current_user_file}")
    logger.debug(f"[process_del_my_word] Checking file existence for path: {current_file_path}, Exists: {os.path.exists(current_file_path)}")

    if not os.path.exists(current_file_path) or current_user_file == "all_words.json":
        await message.answer(
            "У вас нет личного набора слов. Создайте его с помощью команды /my_set сначала.",
            reply_markup=main_menu_keyboard
        )
        await state.clear()
        return

    en_word_to_delete = message.text.strip().lower()
    if not en_word_to_delete:
        await message.answer(
            "Слово для удаления не может быть пустым. Пожалуйста, попробуйте снова или нажмите '❌ Отмена'.",
            parse_mode="HTML",
            reply_markup=cancel_add_del_keyboard
        )
        return

    if word_manager.delete_word_from_file(current_user_file, en_word_to_delete):
        state_data = await state.get_data()
        word_list_visible = state_data.get("word_list_visible", False)
        show_list_button_text = "Скрыть список слов" if word_list_visible else "📖 Показать список слов"
        await message.answer(
            f"✅ Слово <code>{html.escape(en_word_to_delete)}</code> успешно удалено из вашего личного набора.",
            parse_mode="HTML",
            reply_markup=get_my_set_keyboard(is_personal_set=True, show_list_button_text=show_list_button_text)
        )
    else:
        state_data = await state.get_data()
        word_list_visible = state_data.get("word_list_visible", False)
        show_list_button_text = "Скрыть список слов" if word_list_visible else "📖 Показать список слов"
        await message.answer(
            f"❌ Слово <code>{html.escape(en_word_to_delete)}</code> не найдено в вашем наборе или произошла ошибка.",
            parse_mode="HTML",
            reply_markup=get_my_set_keyboard(is_personal_set=True, show_list_button_text=show_list_button_text)
        )
    await state.clear()


@router.callback_query(F.data.startswith("select_file_"))
async def process_select_file(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id in await get_banned_users():
        await callback.answer("Вы заблокированы и не можете использовать функционал пользовательских наборов слов.", show_alert=True)
        await state.clear()
        return
    await callback.answer()
    user_id = callback.from_user.id
    selected_filename = callback.data.replace("select_file_", "")
    user_display_name = await _get_user_display_name(user_id)
    is_personal_set = selected_filename == word_manager.get_user_custom_filename(user_id, user_display_name)

    if word_manager.set_user_current_file(user_id, selected_filename, user_display_name):
        # После выбора файла, устанавливаем word_list_visible в False и обновляем сообщение до начального вида /my_set
        await state.update_data(word_list_visible=False)
        info = word_manager.get_file_info(selected_filename)
        words_in_file = word_manager.load_words_from_file(os.path.join(word_manager.data_dir, "words", selected_filename))
        
        message_text = f"📁 <b>{'Ваш личный набор слов:' if is_personal_set else 'Набор слов:'}</b> {html.escape(selected_filename)}\n"
        message_text += f"📊 Количество слов: {len(words_in_file)}{f' / {MAX_USER_WORDS}' if is_personal_set else ''}\n"
        message_text += f"⚠️ Примечание: Для этих слов могут отсутствовать картинки и аудио.\n\n"
        message_text += "\nВыберите действие:"
        
        await callback.message.edit_text(
            message_text,
            parse_mode="HTML",
            reply_markup=get_my_set_keyboard(is_personal_set=is_personal_set, show_list_button_text="📖 Показать список слов")
        )
    else:
        state_data = await state.get_data()
        word_list_visible = state_data.get("word_list_visible", False)
        show_list_button_text = "Скрыть список слов" if word_list_visible else "📖 Показать список слов"
        await callback.message.edit_text(
            f"❌ Не удалось выбрать файл '{html.escape(selected_filename)}'. Возможно, он не существует.",
            parse_mode="HTML",
            reply_markup=get_my_set_keyboard(is_personal_set=is_personal_set, show_list_button_text=show_list_button_text)
        )
    await state.clear()


@router.callback_query(F.data == "back_to_main_from_my_set_select_file")
async def back_to_main_from_my_set_select_file_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    try:
        await callback.message.edit_text("Возвращаемся в главное меню.", reply_markup=main_menu_keyboard)
    except TelegramBadRequest as e:
        logger.warning(f"[back_to_main_from_my_set_select_file_callback] TelegramBadRequest when editing message: {e}")
        await callback.message.answer("Возвращаемся в главное меню.", reply_markup=main_menu_keyboard)


@router.callback_query(F.data == "switch_my_set_inline")
async def switch_my_set_inline_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    # Передаем callback.message в качестве объекта сообщения
    await _send_file_selection_menu_helper(callback.message, state)


# @router.message(Command("list")) # Обновленный обработчик команды /list
# async def list_user_words_command(message: Message, state: FSMContext):
#     user_id = message.from_user.id
#     if user_id in await get_banned_users():
#         await message.reply("Вы заблокированы и не можете использовать функционал пользовательских наборов слов.")
#         return
    
#     parts = message.text.split(maxsplit=1)
#     target_filename = word_manager.get_user_current_file(user_id) # По умолчанию - текущий файл пользователя

#     if len(parts) > 1:
#         potential_filename = parts[1].strip()
#         if potential_filename.endswith(".json"):
#             if potential_filename in word_manager.get_available_files() or \
#                potential_filename == word_manager.get_user_custom_filename(user_id, await _get_user_display_name(user_id)):
#                 target_filename = potential_filename
#             else:
#                 await message.answer("Вы не можете просматривать слова из этого файла.", reply_markup=main_menu_keyboard)
#                 await state.clear()
#                 return
#         else:
#             await message.answer("Неверный формат команды. Используйте: <code>/list [имя_файла.json]</code> или <code>/list</code> для просмотра вашего текущего файла.", parse_mode="HTML")
#             await state.clear()
#             return

#     words = word_manager.load_words_from_file(os.path.join(word_manager.data_dir, "words", target_filename))
#     words.sort(key=lambda x: x['en'].lower()) # Сортируем слова по английскому эквиваленту
#     if not words:
#         await message.answer(f"Словарь файла <code>{html.escape(target_filename)}</code> пуст или файл не найден.", parse_mode="HTML")
#         await state.clear()
#         return

#     word_list_text = f"📁 <b>Слова в файле {html.escape(target_filename)} (по алфавиту):</b>\n\n"
#     for word_pair in words:
#         word_list_text += f"  • <code>{html.escape(word_pair['en'])} = {html.escape(word_pair['ru'])}</code>\n"
    
#     await message.answer(
#         word_list_text,
#         parse_mode="HTML",
#         reply_markup=main_menu_keyboard
#     )
#     await state.clear()


@router.callback_query(F.data == "toggle_my_word_list") # Измененный callback_data
async def toggle_my_word_list_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id in await get_banned_users():
        await callback.answer("Вы заблокированы и не можете использовать функционал пользовательских наборов слов.", show_alert=True)
        await state.clear()
        return
    await callback.answer()
    user_id = callback.from_user.id
    current_file = word_manager.get_user_current_file(user_id)
    user_display_name = await _get_user_display_name(user_id)
    base_personal_filename = word_manager.get_user_custom_filename(user_id, user_display_name)
    is_personal_set = current_file.startswith(base_personal_filename) and current_file.endswith(".json")
    
    state_data = await state.get_data()
    word_list_visible = state_data.get("word_list_visible", False)
    word_list_visible = not word_list_visible # Инвертируем состояние видимости
    await state.update_data(word_list_visible=word_list_visible)

    logger.debug(f"[toggle_my_word_list_callback] User ID: {user_id}, Current File: {current_file}, User Display Name: {user_display_name}, Is Personal Set: {is_personal_set}, List Visible: {word_list_visible}")

    message_prefix = f"📁 <b>{'Ваш личный набор слов:' if is_personal_set else 'Набор слов:'}</b> {html.escape(current_file)}\n"
    word_count_str = str(len(word_manager.load_words_from_file(os.path.join(word_manager.data_dir, 'words', current_file))))
    if is_personal_set:
        word_count_str += f" / {MAX_USER_WORDS}"
    message_prefix += f"📊 Количество слов: {word_count_str}\n"
    message_prefix += f"⚠️ Примечание: Для этих слов могут отсутствовать картинки и аудио.\n\n"
    message_prefix += "\nВыберите действие:"

    words = word_manager.load_words_from_file(os.path.join(word_manager.data_dir, "words", current_file))
    words.sort(key=lambda x: x['en'].lower()) # Сортируем слова по английскому эквиваленту

    show_list_button_text = "Скрыть список слов" if word_list_visible else "📖 Показать список слов"

    message_text_content = ""
    if word_list_visible and words:
        message_text_content = f"<b>Список слов ({len(words)}):</b>\n"
        for word_pair in words:
            icons = []
            if await get_audio_filepath(word_pair['en']):
                icons.append(" 🔊")
            if await get_image_filepath(word_pair['en']):
                icons.append(" 🖼️")
            icon_str = "".join(icons)
            message_text_content += f"  •<code>{html.escape(word_pair['en'])} = {html.escape(word_pair['ru'])}</code>{icon_str}\n"
    elif not words:
        message_text_content = f"{'Ваш личный набор слов' if is_personal_set else 'Набор слов'} <code>{html.escape(current_file)}</code> пуст. "
        if is_personal_set:
            message_text_content += 'Добавьте слова с помощью кнопки "➕ Добавить слово".'
        message_text_content += "\n"

    final_message_text = message_prefix
    if message_text_content:
        final_message_text = final_message_text.replace("\n\nВыберите действие:", f"\n{message_text_content}\nВыберите действие:")
    
    try:
        markup_to_send = get_my_set_keyboard(is_personal_set=is_personal_set, show_list_button_text=show_list_button_text)
        logger.debug(f"[toggle_my_word_list_callback] Sending markup: is_personal_set={is_personal_set}, markup={markup_to_send.inline_keyboard}")

        await callback.message.edit_text(
            final_message_text,
            parse_mode="HTML",
            reply_markup=markup_to_send
        )
    except TelegramBadRequest as e:
        logger.warning(f"[toggle_my_word_list_callback] TelegramBadRequest when editing message: {e}")


async def _send_file_selection_menu_helper(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_display_name = await _get_user_display_name(user_id)
    available_files = word_manager.get_available_files()
    current_file = word_manager.get_user_current_file(user_id)

    if not available_files:
        await message.edit_text("Нет доступных файлов со словами для выбора.", reply_markup=main_menu_keyboard)
        await state.clear()
        return
    
    keyboard = create_file_selection_keyboard(available_files, current_file)
    try:
        await message.edit_text(
            "Выберите набор слов для изучения:",
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        logger.warning(f"[_send_file_selection_menu_helper] TelegramBadRequest when editing message: {e}")
        await message.answer(
            "Выберите набор слов для изучения:",
            reply_markup=keyboard
        )


@router.callback_query(F.data == "delete_my_word_set")
async def delete_my_word_set_command(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id in await get_banned_users():
        await callback.answer("Вы заблокированы и не можете использовать функционал пользовательских наборов слов.", show_alert=True)
        await state.clear()
        return
    await callback.answer()
    user_id = callback.from_user.id
    current_user_file = word_manager.get_user_current_file(user_id)

    if current_user_file == "all_words.json":
        await callback.message.edit_text(
            "Вы не можете удалить основной набор слов.",
            reply_markup=get_my_set_keyboard(is_personal_set=False)
        )
        await state.clear()
        return

    await callback.message.edit_text(
        f"Вы уверены, что хотите удалить свой личный набор слов <b>{html.escape(current_user_file)}</b>? Это действие нельзя отменить.",
        parse_mode="HTML",
        reply_markup=delete_my_set_confirm_keyboard
    )
    await state.set_state(UserWordStates.waiting_for_delete_confirm)


@router.callback_query(F.data == "confirm_delete_my_word_set", UserWordStates.waiting_for_delete_confirm)
async def confirm_delete_my_word_set(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id in await get_banned_users():
        await callback.answer("Вы заблокированы и не можете использовать функционал пользовательских наборов слов.", show_alert=True)
        await state.clear()
        return
    await callback.answer()
    user_id = callback.from_user.id
    current_user_file = word_manager.get_user_current_file(user_id)
    user_display_name = await _get_user_display_name(user_id) # Добавлено: Получаем user_display_name

    if current_user_file == "all_words.json":
        state_data = await state.get_data()
        word_list_visible = state_data.get("word_list_visible", False)
        show_list_button_text = "Скрыть список слов" if word_list_visible else "📖 Показать список слов"
        await callback.message.edit_text(
            "Невозможно удалить основной набор слов.",
            reply_markup=get_my_set_keyboard(is_personal_set=False, show_list_button_text=show_list_button_text)
        )
        await state.clear()
        return

    if word_manager.delete_file(current_user_file):
        # Сбрасываем текущий файл пользователя на дефолтный
        word_manager.set_user_current_file(user_id, "all_words.json", user_display_name) # Pass user_display_name
        await callback.message.edit_text(
            f"✅ Ваш личный набор слов <b>{html.escape(current_user_file)}</b> успешно удален.",
            parse_mode="HTML"
        )
    else:
        state_data = await state.get_data()
        word_list_visible = state_data.get("word_list_visible", False)
        show_list_button_text = "Скрыть список слов" if word_list_visible else "📖 Показать список слов"
        await callback.message.edit_text(
            f"❌ Не удалось удалить набор слов <b>{html.escape(current_user_file)}</b>. Возможно, файл не существует или произошла ошибка.",
            parse_mode="HTML",
            reply_markup=get_my_set_keyboard(is_personal_set=False, show_list_button_text=show_list_button_text)
        )
    await state.clear()


@router.callback_query(F.data == "cancel_delete_my_word_set", UserWordStates.waiting_for_delete_confirm)
async def cancel_delete_my_word_set(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("Удаление набора слов отменено.", reply_markup=None)


@router.callback_query(F.data == "cancel_add_del_word", StateFilter(UserWordStates.waiting_for_add_word, UserWordStates.waiting_for_del_word))
async def cancel_add_del_word_action(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id in await get_banned_users():
        await callback.answer("Вы заблокированы и не можете использовать функционал пользовательских наборов слов.", show_alert=True)
        await state.clear()
        return
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("Действие отменено.", reply_markup=None)
    state_data = await state.get_data()
    word_list_visible = state_data.get("word_list_visible", False)
    show_list_button_text = "Скрыть список слов" if word_list_visible else "📖 Показать список слов"
    await callback.message.answer("Возвращаемся в меню управления набором слов.", reply_markup=get_my_set_keyboard(is_personal_set=True, show_list_button_text=show_list_button_text))
