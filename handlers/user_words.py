from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import main_menu_keyboard, confirm_create_set_keyboard, my_set_keyboard, create_file_selection_keyboard
from utils.word_manager import word_manager
from utils.bad_words import is_bad_word
from database import get_user_display_name
from typing import Dict, List
import html
import os
from config import MAX_USER_WORDS # Импортируем MAX_USER_WORDS из config.py


class UserWordStates(StatesGroup):
    waiting_for_create_confirm = State()
    waiting_for_add_word = State()
    waiting_for_del_word = State()


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
    user_display_name = await _get_user_display_name(user_id) # Используем функцию для получения имени
    custom_filename = word_manager.get_user_custom_filename(user_id, user_display_name)

    # Проверяем, существует ли уже пользовательский файл
    if os.path.exists(os.path.join(word_manager.data_dir, custom_filename)):
        info = word_manager.get_file_info(custom_filename)
        if info:
            words = word_manager.load_words_from_file(os.path.join(word_manager.data_dir, custom_filename))
            
            message_text = (
                f"📁 <b>Ваш личный набор слов:</b> {html.escape(custom_filename)}\n"
                f"📊 Количество слов: {info['word_count']} / {MAX_USER_WORDS}\n"
                f"⚠️ Примечание: Для этих слов могут отсутствовать картинки и аудио.\n\n"
            )

            if words:
                message_text += f"<b>Список слов ({len(words)}):</b>\n"
                for word_pair in words:
                    message_text += f"  • <code>{html.escape(word_pair['en'])} = {html.escape(word_pair['ru'])}</code>\n"
            else:
                message_text += "Ваш личный набор слов пуст. Добавьте слова с помощью кнопки '➕ Добавить слово'.\n"
            
            message_text += "\nВыберите действие:"

            await message.answer(
                message_text,
                parse_mode="HTML",
                reply_markup=my_set_keyboard
            )
        else:
            await message.answer(
                "Не удалось получить информацию о вашем личном наборе слов. Возможно, файл поврежден. "
                "Пожалуйста, попробуйте создать новый набор или свяжитесь с администратором.",
                reply_markup=main_menu_keyboard
            )
            await state.clear()
    else:
        # Предлагаем создать новый набор
        await message.answer(
            f"У вас пока нет личного набора слов. Вы хотите создать его?\n"
            f"Ваш набор будет называться: <b>{html.escape(custom_filename.replace('.json', ''))}</b>",
            parse_mode="HTML",
            reply_markup=confirm_create_set_keyboard
        )
        await state.set_state(UserWordStates.waiting_for_create_confirm)


@router.callback_query(F.data == "create_my_word_set", UserWordStates.waiting_for_create_confirm)
async def create_my_word_set(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    user_display_name = await _get_user_display_name(user_id)
    custom_filename = word_manager.get_user_custom_filename(user_id, user_display_name)

    if word_manager.create_new_file(custom_filename):
        word_manager.set_user_current_file(user_id, custom_filename)
        
        # После создания сразу показываем пустой список слов и кнопки управления
        await callback.message.edit_text(
            f"✅ Ваш личный набор слов <b>{html.escape(custom_filename)}</b> успешно создан!\n"
            f"Ваш набор слов пуст ({0} / {MAX_USER_WORDS}). Добавьте слова с помощью кнопки '➕ Добавить слово'.\n\n"
            f"  • Для добавления используйте: /add_my_word <code>английское_слово=русский_перевод</code>\n"
            f"  • Для удаления используйте: /del_my_word <code>английское_слово</code>\n"
            f"⚠️ Примечание: Для этих слов могут отсутствовать картинки и аудио.\n\n"
            f"Выберите действие:",
            parse_mode="HTML",
            reply_markup=my_set_keyboard
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
    await callback.message.answer("Возвращаемся в главное меню.", reply_markup=main_menu_keyboard)


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
    await callback.answer()
    user_id = callback.from_user.id
    user_display_name = await _get_user_display_name(user_id)
    custom_filename = word_manager.get_user_custom_filename(user_id, user_display_name)

    if not os.path.exists(os.path.join(word_manager.data_dir, custom_filename)):
        await callback.message.edit_text(
            "У вас нет личного набора слов. Создайте его с помощью команды /my_set сначала.",
            reply_markup=main_menu_keyboard
        )
        await state.clear()
        return

    await callback.message.edit_text(
        f"Пожалуйста, отправьте английское слово и его русский перевод в формате: <code>английское_слово=русский_перевод</code>\n"
        f"(Максимум слов в наборе: {MAX_USER_WORDS})",
        parse_mode="HTML"
    )
    await state.set_state(UserWordStates.waiting_for_add_word)


@router.message(UserWordStates.waiting_for_add_word, F.text)
async def process_add_my_word(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_display_name = await _get_user_display_name(user_id)
    custom_filename = word_manager.get_user_custom_filename(user_id, user_display_name)

    if not os.path.exists(os.path.join(word_manager.data_dir, custom_filename)):
        await message.answer(
            "У вас нет личного набора слов. Создайте его с помощью команды /my_set сначала.",
            reply_markup=main_menu_keyboard
        )
        await state.clear()
        return

    # Проверка на лимит слов
    current_words = word_manager.load_words_from_file(os.path.join(word_manager.data_dir, custom_filename))
    if len(current_words) >= MAX_USER_WORDS:
        await message.answer(
            f"❌ Вы достигли максимального количества слов ({MAX_USER_WORDS}) в вашем личном наборе. "
            "Пожалуйста, удалите некоторые слова, прежде чем добавлять новые.",
            parse_mode="HTML",
            reply_markup=my_set_keyboard
        )
        await state.clear()
        return

    word_pair_str = message.text.strip()
    if "=" not in word_pair_str:
        await message.answer(
            "Неверный формат. Используйте: <code>английское_слово=русский_перевод</code>. "
            "Пожалуйста, попробуйте снова или /cancel для отмены.",
            parse_mode="HTML"
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
        await message.answer(
            "Это слово нельзя добавить. Оно находится в списке запрещенных слов.",
            reply_markup=my_set_keyboard
        )
        await state.clear()
        return

    if word_manager.add_word_to_file(custom_filename, {"en": en_word, "ru": ru_word}):
        await message.answer(
            f"✅ Слово <code>{html.escape(en_word)}={html.escape(ru_word)}</code> успешно добавлено в ваш личный набор!\n"
            "⚠️ Примечание: Для этого слова могут отсутствовать картинки и аудио.",
            parse_mode="HTML",
            reply_markup=my_set_keyboard
        )
    else:
        await message.answer(
            "❌ Не удалось добавить слово. Возможно, произошла ошибка.",
            reply_markup=my_set_keyboard
        )
    await state.clear()


@router.callback_query(F.data == "del_my_word")
async def del_my_word_command(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    user_display_name = await _get_user_display_name(user_id)
    custom_filename = word_manager.get_user_custom_filename(user_id, user_display_name)

    if not os.path.exists(os.path.join(word_manager.data_dir, custom_filename)):
        await callback.message.edit_text(
            "У вас нет личного набора слов. Создайте его с помощью команды /my_set сначала.",
            reply_markup=main_menu_keyboard
        )
        await state.clear()
        return

    await callback.message.edit_text(
        "Пожалуйста, отправьте английское слово, которое вы хотите удалить из вашего набора.",
        reply_markup=None
    )
    await state.set_state(UserWordStates.waiting_for_del_word)


@router.message(UserWordStates.waiting_for_del_word, F.text)
async def process_del_my_word(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_display_name = await _get_user_display_name(user_id)
    custom_filename = word_manager.get_user_custom_filename(user_id, user_display_name)

    if not os.path.exists(os.path.join(word_manager.data_dir, custom_filename)):
        await message.answer(
            "У вас нет личного набора слов. Создайте его с помощью команды /my_set сначала.",
            reply_markup=main_menu_keyboard
        )
        await state.clear()
        return

    en_word_to_delete = message.text.strip().lower()
    if not en_word_to_delete:
        await message.answer(
            "Слово для удаления не может быть пустым. Пожалуйста, попробуйте снова или /cancel для отмены."
        )
        return

    if word_manager.delete_word_from_file(custom_filename, en_word_to_delete):
        await message.answer(
            f"✅ Слово <code>{html.escape(en_word_to_delete)}</code> успешно удалено из вашего личного набора.",
            parse_mode="HTML",
            reply_markup=my_set_keyboard
        )
    else:
        await message.answer(
            f"❌ Слово <code>{html.escape(en_word_to_delete)}</code> не найдено в вашем наборе или произошла ошибка.",
            parse_mode="HTML",
            reply_markup=my_set_keyboard
        )
    await state.clear()


@router.message(Command("switch_my_set"))
async def switch_my_set_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    available_files = word_manager.get_available_files()
    current_file = word_manager.get_user_current_file(user_id)

    if not available_files:
        await message.answer("Нет доступных файлов со словами для выбора.", reply_markup=main_menu_keyboard)
        await state.clear()
        return
    
    keyboard = create_file_selection_keyboard(available_files, current_file)
    await message.answer(
        "Выберите набор слов для изучения:",
        reply_markup=keyboard
    )
    # Состояние не меняем, ожидаем callback_query


@router.callback_query(F.data.startswith("select_file_"))
async def process_select_file(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    selected_filename = callback.data.replace("select_file_", "")

    if word_manager.set_user_current_file(user_id, selected_filename):
        await callback.message.edit_text(
            f"✅ Выбран набор слов: <b>{html.escape(selected_filename)}</b>",
            parse_mode="HTML",
            reply_markup=my_set_keyboard # Устанавливаем my_set_keyboard вместо None
        )
    else:
        await callback.message.edit_text(
            f"❌ Не удалось выбрать файл '{html.escape(selected_filename)}'. Возможно, он не существует.",
            parse_mode="HTML",
            reply_markup=my_set_keyboard # Устанавливаем my_set_keyboard вместо None
        )
    await state.clear()


@router.callback_query(F.data == "back_to_main_from_my_set_select_file")
async def back_to_main_from_my_set_select_file_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("Возвращаемся в главное меню.", reply_markup=None)
    await callback.message.answer("Возвращаемся в главное меню.", reply_markup=main_menu_keyboard)


@router.message(Command("list"))
async def list_user_words(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    parts = message.text.split(maxsplit=1)
    target_filename = word_manager.get_user_current_file(user_id) # По умолчанию - текущий файл пользователя

    if len(parts) > 1:
        potential_filename = parts[1].strip()
        if potential_filename.endswith(".json"):
            # Проверяем, что пользователь может получить доступ к этому файлу (т.е., не admin-only или internal)
            if potential_filename in word_manager.get_available_files() or \
               potential_filename == word_manager.get_user_custom_filename(user_id, await _get_user_display_name(user_id)):
                target_filename = potential_filename
            else:
                await message.answer("Вы не можете просматривать слова из этого файла.", reply_markup=main_menu_keyboard)
                await state.clear()
                return
        else:
            await message.answer("Неверный формат команды. Используйте: <code>/list [имя_файла.json]</code> или <code>/list</code> для просмотра вашего текущего файла.", parse_mode="HTML")
            await state.clear()
            return

    words = word_manager.load_words_from_file(os.path.join(word_manager.data_dir, target_filename))
    words.sort(key=lambda x: x['en'].lower()) # Сортируем слова по английскому эквиваленту
    if not words:
        await message.answer(f"Словарь файла <code>{html.escape(target_filename)}</code> пуст или файл не найден.", parse_mode="HTML")
        await state.clear()
        return

    word_list_text = f"📁 <b>Слова в файле {html.escape(target_filename)} (по алфавиту):</b>\n\n"
    for word_pair in words:
        word_list_text += f"  • <code>{html.escape(word_pair['en'])} = {html.escape(word_pair['ru'])}</code>\n"
    
    await message.answer(
        word_list_text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard
    )
    await state.clear()


@router.callback_query(F.data == "show_my_word_list")
async def show_my_word_list_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    current_file = word_manager.get_user_current_file(user_id)
    
    words = word_manager.load_words_from_file(os.path.join(word_manager.data_dir, current_file))
    words.sort(key=lambda x: x['en'].lower()) # Сортируем слова по английскому эквиваленту

    if not words:
        await callback.message.edit_text(
            f"Ваш личный набор слов <code>{html.escape(current_file)}</code> пуст. "
            "Добавьте слова с помощью кнопки '➕ Добавить слово'.",
            parse_mode="HTML",
            reply_markup=my_set_keyboard
        )
        return

    message_text = f"📁 <b>Ваш личный набор слов:</b> {html.escape(current_file)}\n"
    message_text += f"📊 Количество слов: {len(words)} / {MAX_USER_WORDS}\n"
    message_text += f"⚠️ Примечание: Для этих слов могут отсутствовать картинки и аудио.\n\n"
    message_text += f"<b>Список слов ({len(words)}):</b>\n"
    for word_pair in words:
        message_text += f"  • <code>{html.escape(word_pair['en'])} = {html.escape(word_pair['ru'])}</code>\n"
    
    await callback.message.edit_text(
        message_text,
        parse_mode="HTML",
        reply_markup=my_set_keyboard
    )
