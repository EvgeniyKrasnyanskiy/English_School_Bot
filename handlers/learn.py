import random
from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.utils import get_random_word
from keyboards import learn_words_keyboard, main_menu_keyboard
from utils.data_manager import get_image_filepath, get_audio_filepath
from utils.audio_cleanup import cleanup_guess_audio
from utils.word_manager import word_manager # Импортируем word_manager
from database import update_last_active
import asyncio

router = Router()

class LearnWords(StatesGroup):
    viewing_flashcard = State()

async def cleanup_old_audio_messages(message: Message, bot: Bot):
    """Try to delete recent audio messages from previous sessions"""
    try:
        if not bot:
            return
            
        # Try to delete the last 20 messages, checking if they are audio
        # This is a best-effort approach since we can't see full chat history
        current_message_id = message.message_id
        deleted_count = 0
        
        for i in range(1, 21):  # Try to delete messages 1-20 positions back
            try:
                msg_id_to_delete = current_message_id - i
                if msg_id_to_delete > 0:  # Make sure we don't try to delete negative IDs
                    # Try to get message info first
                    try:
                        msg_info = await bot.get_chat(chat_id=message.chat.id)
                        # If we can get chat info, try to delete the message
                        await bot.delete_message(chat_id=message.chat.id, message_id=msg_id_to_delete)
                        deleted_count += 1
                    except Exception:
                        # If we can't get message info or delete it, skip
                        pass
            except Exception:
                # If we can't delete a message, it might not exist or we don't have permission
                # This is expected, so we continue silently
                pass
                
    except Exception:
        pass

@router.message(F.text == "📚 Учить слова")
async def cmd_learn_words(message: Message, state: FSMContext, bot: Bot):
    # Удаляем аудиофайлы из игры "Угадай слово" при переходе к изучению слов
    await cleanup_guess_audio(message, state, bot)
    await state.set_state(LearnWords.viewing_flashcard)
    await send_flashcard(message, state, bot)

async def send_flashcard(message: Message, state: FSMContext, bot: Bot, random_word: bool = False):
    words = word_manager.load_words(int(message.from_user.id)) # Load words every time
    current_words = await state.get_data()
    word_index = current_words.get("word_index", -1)

    if random_word or word_index == -1 or word_index >= len(words):
        word = get_random_word(words)
        word_index = words.index(word) # Find index of the random word
    else:
        word = words[word_index]

    # Delete previously sent audio messages only
    previous_audio_ids = current_words.get("sent_audio_ids", [])
    if previous_audio_ids:
        for msg_id in previous_audio_ids:
            try:
                if bot:
                    await bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
            except Exception as e:
                pass
    sent_audio_ids = []

    # Check for image and send if exists
    image_path = await get_image_filepath(word['en'])
    if image_path:
        await message.answer_photo(photo=FSInputFile(image_path))
    
    await message.answer(
        f"*{word['en']}* ="
        f" _{word['ru']}_",
        parse_mode="Markdown",
        reply_markup=learn_words_keyboard
    )
    
    # Check for audio and send if exists
    audio_path = await get_audio_filepath(word['en'])
    if audio_path:
        sent_audio = await message.answer_audio(
            audio=FSInputFile(audio_path),
            title=f"{word['en']}",
            performer="EnglishBot"
        )
        sent_audio_ids.append(sent_audio.message_id)
    
    await state.update_data(current_word=word, word_index=word_index, sent_audio_ids=sent_audio_ids)

@router.message(F.text == "➡️ Следующее слово", LearnWords.viewing_flashcard)
async def next_word(message: Message, state: FSMContext, bot: Bot):
    words = word_manager.load_words(message.from_user.id) # Load words every time
    current_words_data = await state.get_data()
    current_index = current_words_data.get("word_index", -1)
    
    next_index = current_index + 1
    if next_index >= len(words):
        next_index = 0 # Loop back to the beginning

    await state.update_data(word_index=next_index)
    await send_flashcard(message, state, bot)


@router.message(F.text == "🎲 Случайное слово", LearnWords.viewing_flashcard)
async def random_word(message: Message, state: FSMContext, bot: Bot):
    await send_flashcard(message, state, bot, random_word=True)

@router.message(F.text == "⬆️ В главное меню", LearnWords.viewing_flashcard)
async def back_to_main_from_learn(message: Message, state: FSMContext, bot: Bot):
    current_words_data = await state.get_data()
    previous_audio_ids = current_words_data.get("sent_audio_ids", [])
    for msg_id in previous_audio_ids:
        try:
            if bot:
                await bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
        except Exception:
            pass
    await state.clear() # Перемещено в конец после очистки аудио
    await message.answer("Вы вернулись в главное меню.", reply_markup=main_menu_keyboard)

@router.message(F.text == "🧹 Очистить чат")
async def cleanup_chat(message: Message, bot: Bot):
    """Manual cleanup command for users"""
    status_message = await message.answer("Пытаюсь чистить чат, ждите...")
    await cleanup_old_audio_messages(message, bot)
    await status_message.edit_text("Чистка закончена! Но возможно не все сообщения были удалены.")
    await message.answer("Вы можете самостоятельно очистить всю историю чата в меню Telegram. \n\nИспользуйте команду /start если не отображаются кнопки или попробуйте перезапустить бота.")
