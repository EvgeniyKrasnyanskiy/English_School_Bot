# English 3 Bot

## Description
This is a Telegram bot designed to help users learn English words through various interactive features. It supports word learning, games, knowledge tests, and allows administrators to manage word sets and other bot settings.

## Features
- **Interactive Word Learning**: Learn new words through flashcards.
- **Engaging Games**: Play games like "Choose Translation", "Find Missing Letter", "Build Word", and "Guess Word" (audio).
- **Knowledge Tests**: Test your vocabulary with configurable quizzes.
- **Personalized Word Sets**: Users can create, add words to, and delete their own custom word sets.
- **Configurable Default Word Set**: Administrators can set a default word set for new users.
- **Admin Commands**:
    - Add/delete words from specific or default word sets.
    - View user statistics and active word sets.
    - Manage banned users.
    - Broadcast messages to users or specific classes.
    - Manage audio files (convert OGG to MP3, move, delete).
    - Configure bot settings via the `/settings` command (e.g., test question count, admin IDs).
- **Multi-part Message Handling**: Long word lists are paginated to avoid Telegram message length limits.
- **Robust Input Parsing**: Handles flexible spacing in commands and ensures consistent formatting.

## Setup

### Prerequisites
- Python 3.9+
- pip (Python package installer)
- FFmpeg (for audio conversion)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-repo/Eng3Bot.git
    cd Eng3Bot
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv .venv
    ```

3.  **Activate the virtual environment:**
    -   **Windows:**
        ```bash
        .venv\Scripts\activate
        ```
    -   **macOS/Linux:**
        ```bash
        source .venv/bin/activate
        ```

4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    (Note: A `requirements.txt` file is assumed to exist with all necessary packages.)

5.  **Configure `config.py`:**
    -   Create a `config.py` file in the project root.
    -   Add your Telegram Bot `TOKEN` (obtained from BotFather).
    -   Set `ADMIN_IDS` to a list of integer user IDs for administrators.
    -   Configure `DEFAULT_WORD_SET` (e.g., `"all_words.json"` or a custom one).
    -   Example `config.py`:
        ```python
        TOKEN = "YOUR_BOT_TOKEN"
        ADMIN_IDS = [123456789, 987654321] # Replace with actual admin user IDs (integers)
        DEFAULT_WORD_SET = "ant-zip.json"
        TEST_QUESTIONS_COUNT = 10
        MAX_USER_WORDS = 200
        CHECK_NEW_AUDIO = True
        TELEGRAM_MAX_MESSAGE_LENGTH = 4096
        RECALL_TYPING_COUNTDOWN_SECONDS = 5.0
        ```

6.  **Prepare data directories:**
    The bot expects certain directory structures for words, sounds, and images. These will be created automatically on first run if they don't exist:
    ```
    data/
    ├── config/
    ├── words/
    │   ├── all_words.json
    │   └── ... (other .json word files)
    ├── sounds/
    │   ├── mp3/
    │   ├── ogg/
    │   └── temp_audio/
    └── images/
    ```
    -   Place your `.json` word list files (e.g., `food.json`, `all_words.json`) in `data/words/`.
    -   Place audio files in `data/sounds/mp3/` or `data/sounds/ogg/`.

## Usage

1.  **Start the bot:**
    ```bash
    python main.py
    ```

2.  **Interact with the bot on Telegram:**

    **User Commands:**
    -   `/start`: Start interaction with the bot.
    -   `📚 Учить слова`: Enter the word learning mode.
    -   `🎮 Игры`: Access various word games.
    -   `📝 Тест знаний`: Start a knowledge test.
    -   `📊 Статистика`: View your learning statistics.
    -   `❓ Справка`: Get help information.
    -   `🔁 Словари`: Change your active word set.
    -   `⬆️ В главное меню`: Return to the main menu.
    -   (And various inline keyboard actions for specific features)

    **Admin Commands (only for `ADMIN_IDS`):**
    -   `/add [filename.json] english_word=russian_translation`: Add a word.
    -   `/del [filename.json] english_word`: Delete a word.
    -   `/files`: List available word set files.
    -   `/settings`: View and modify bot settings.
    -   `/users`: List all registered users.
    -   `/ban USER_ID`: Ban a user.
    -   `/unban USER_ID`: Unban a user.
    -   `/send_msg [class=CLASS_NAME] message_text`: Send a broadcast message.
    -   `/new_sound`: Add a new audio file (voice message).
    -   `/move_audio_files`: Move MP3 audio files from `mp3` to `sounds` directory.
    -   `/convert_all_audio`: Convert all OGG files to MP3.
    -   `/delete_audio_files`: Delete audio files.
    -   `/deduplicate_words [filename.json|all]`: Remove duplicate words.
