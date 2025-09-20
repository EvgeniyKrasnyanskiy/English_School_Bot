"""
Утилиты для очистки аудиофайлов из игры "Угадай слово"
"""

from aiogram import Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

async def cleanup_guess_audio(message: Message, state: FSMContext, bot: Bot):
    """Удаляет аудиофайлы из игры 'Угадай слово' при переходе к другим командам"""
    try:
        current_data = await state.get_data()
        audio_ids = current_data.get("guess_sent_audio_ids", [])
        if audio_ids:
            if bot:
                for audio_id in audio_ids:
                    try:
                        await bot.delete_message(chat_id=message.chat.id, message_id=audio_id)
                    except Exception:
                        pass
                # Очищаем список после удаления
                await state.update_data(guess_sent_audio_ids=[])
    except Exception:
        pass
