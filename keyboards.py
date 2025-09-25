from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Main Menu
main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Учить слова"), KeyboardButton(text="🎮 Игры")],
        [KeyboardButton(text="📝 Тест знаний"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="❓ Справка"), KeyboardButton(text="🔁 Словари")],
        [KeyboardButton(text="⬆️ В главное меню")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_audio_upload")]
])

# Learn Words
learn_words_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➡️ Следующее слово"), KeyboardButton(text="🎲 Случайное слово")],
        [KeyboardButton(text="⬆️ В главное меню")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# Games Menu
games_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🤔 Выбери перевод"), KeyboardButton(text="🔍 Найди букву")],
        [KeyboardButton(text="🧩 Собери слово"), KeyboardButton(text="🎧 Угадай слово")],
        [KeyboardButton(text="📝 Ввод по памяти"), KeyboardButton(text="⬆️ В главное меню")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# Back to main menu - This keyboard is now redundant as 'В главное меню' is in main_menu_keyboard
# I will remove it and update its usages.

def quiz_options_keyboard(options: list[str], correct_option: str):
    """Generates an InlineKeyboardMarkup for quiz options in a 2-column layout with pictograms."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    row = []
    for i, option in enumerate(options):
        # Store options in state and use index for callback_data
        callback_data = f"quiz_answer_{i}_{'correct' if option == correct_option else 'incorrect'}"
        row.append(InlineKeyboardButton(text=f"▪️ {option}", callback_data=callback_data))
        if len(row) == 2 or i == len(options) - 1:
            keyboard.inline_keyboard.append(row)
            row = []
    return keyboard

start_recall_typing_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Начать", callback_data="start_recall_typing_countdown")]
])

# Клавиатура для подтверждения создания пользовательского словаря
confirm_create_set_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Да, создать мой словарь!", callback_data="create_my_word_set")],
    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_create_word_set")]
])

# Клавиатура для управления пользовательским словарём
def get_my_set_keyboard(is_personal_set: bool = False, show_list_button_text: str = "📖 Показать список слов") -> InlineKeyboardMarkup:
    keyboard_buttons = []

    if is_personal_set:
        keyboard_buttons.append([InlineKeyboardButton(text="➕ Добавить слово", callback_data="add_my_word")])
        keyboard_buttons.append([InlineKeyboardButton(text="➖ Удалить слово", callback_data="del_my_word")])
        keyboard_buttons.append([InlineKeyboardButton(text="🗑️ Удалить словарь", callback_data="delete_my_word_set")])
        keyboard_buttons.append([InlineKeyboardButton(text=show_list_button_text, callback_data="toggle_my_word_list")]) # Использование нового callback_data
    else:
        keyboard_buttons.append([InlineKeyboardButton(text=show_list_button_text, callback_data="toggle_my_word_list")]) # Использование нового callback_data

    # Добавляем кнопку "Словарь" здесь
    keyboard_buttons.append([InlineKeyboardButton(text="🔁 Словари", callback_data="switch_my_set_inline")])
    
    keyboard_buttons.append([InlineKeyboardButton(text="✅ Готово", callback_data="back_to_main_from_my_set")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

def create_file_selection_keyboard(available_files: list[str], current_file: str) -> InlineKeyboardMarkup:
    """Создает InlineKeyboardMarkup для выбора файлов со словами."""
    keyboard = []
    for file in available_files:
        display_name = file.replace(".json", "")
        text = f"{display_name} ✅" if file == current_file else display_name
        keyboard.append([InlineKeyboardButton(text=text, callback_data=f"select_file_{file}")])
    
    keyboard.append([InlineKeyboardButton(text="✅ Подтвердить и закрыть", callback_data="back_to_main_from_my_set_select_file")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Клавиатура для отмены ввода имени файла при добавлении нового аудио
cancel_keyboard_for_filename = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_audio_upload")]
])

# Клавиатура для подтверждения удаления пользовательского словаря
delete_my_set_confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Да, удалить", callback_data="confirm_delete_my_word_set")],
    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_my_word_set")]
])

# Клавиатура для отмены добавления/удаления слов
cancel_add_del_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_del_word")]
])

# Клавиатура для подтверждения рассылки
confirm_broadcast_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Да, отправить")],
        [KeyboardButton(text="Отмена")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

delete_audio_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Удалить из /ogg по имени", callback_data="delete_single_ogg")],
    [InlineKeyboardButton(text="Удалить из /mp3 по имени", callback_data="delete_single_mp3")],
    [InlineKeyboardButton(text="Удалить все из /ogg", callback_data="delete_all_ogg")],
    [InlineKeyboardButton(text="Удалить все из /mp3", callback_data="delete_all_mp3")],
    [InlineKeyboardButton(text="Удалить из /sounds по имени", callback_data="delete_single_sounds")],
    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_audio")]
])

confirm_delete_audio_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Да, удалить", callback_data="confirm_delete_audio_files")],
    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_audio")]
])

def create_file_list_keyboard(files: list[str], directory_type: str) -> InlineKeyboardMarkup:
    keyboard_buttons = []
    for file in files:
        keyboard_buttons.append([InlineKeyboardButton(text=file, callback_data=f"select_file_for_deletion_{directory_type}_{file}")])
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_delete_selection")])
    keyboard_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_audio")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
