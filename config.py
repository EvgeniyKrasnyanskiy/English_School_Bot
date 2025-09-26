# config.py
TOKEN = "8334225591:AAHtS-y9fO8xs6qh0dKsAzprvhOXtHsPk-Y"  # Replace with your actual bot token
TEST_QUESTIONS_COUNT = 50
ADMIN_IDS = [94361431] # Allow multiple admin IDs separated by commas
RECALL_TYPING_COUNTDOWN_SECONDS = 4.0 # Default countdown for 'Recall Typing' game
MAX_USER_WORDS = 50 # Максимальное количество слов в пользовательском словаре
CHECK_NEW_AUDIO = True # Проверять наличие новых аудио в папке /sounds/mp3 и уведомлять админа
TELEGRAM_MAX_MESSAGE_LENGTH = 4096 # Maximum character length for Telegram messages
DEFAULT_WORD_SET = "base_min.json" # Default word set to use if a user has no active set configured
AUTO_RESET_STATS_MONTHLY = True # Automatically reset user statistics (rank, scores) on the 1st of every month at 00:01
