from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Main Menu
main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Учить слова"), KeyboardButton(text="🎮 Игры")],
        [KeyboardButton(text="📝 Проверка знаний"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="❓ Справка"), KeyboardButton(text="🧹 Очистить чат")],
        [KeyboardButton(text="⬆️ В главное меню")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

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
        callback_data = f"quiz_answer_{'correct' if option == correct_option else 'incorrect'}_{option}"
        row.append(InlineKeyboardButton(text=f"▪️ {option}", callback_data=callback_data))
        if len(row) == 2 or i == len(options) - 1:
            keyboard.inline_keyboard.append(row)
            row = []
    return keyboard

start_recall_typing_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Начать", callback_data="start_recall_typing_countdown")]
])
