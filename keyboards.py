from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Main Menu
main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Учить слова"), KeyboardButton(text="🎮 Игры")],
        [KeyboardButton(text="📝 Тест знаний"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="❓ Справка"), KeyboardButton(text="🧹 Очистить чат")],
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

# Клавиатура для подтверждения создания пользовательского набора слов
confirm_create_set_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Да, создать мой набор!", callback_data="create_my_word_set")],
    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_create_word_set")]
])

# Клавиатура для управления пользовательским набором слов
my_set_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Добавить слово", callback_data="add_my_word")],
    [InlineKeyboardButton(text="➖ Удалить слово", callback_data="del_my_word")],
    [InlineKeyboardButton(text="📖 Показать список слов", callback_data="show_my_word_list")],
    [InlineKeyboardButton(text="🗑️ Удалить набор", callback_data="delete_my_word_set")],
    [InlineKeyboardButton(text="⬆️ В главное меню", callback_data="back_to_main_from_my_set")]
])

def create_file_selection_keyboard(available_files: list[str], current_file: str) -> InlineKeyboardMarkup:
    """Создает InlineKeyboardMarkup для выбора файлов со словами."""
    keyboard = []
    for file in available_files:
        text = f"{file} ✅ (текущий)" if file == current_file else file
        keyboard.append([InlineKeyboardButton(text=text, callback_data=f"select_file_{file}")])
    
    keyboard.append([InlineKeyboardButton(text="⬆️ В главное меню", callback_data="back_to_main_from_my_set_select_file")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Клавиатура для отмены ввода имени файла при добавлении нового аудио
cancel_keyboard_for_filename = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_audio_upload")]
])

# Клавиатура для подтверждения удаления пользовательского набора слов
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
