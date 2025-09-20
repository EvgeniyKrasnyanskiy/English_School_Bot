import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from config import TOKEN, ADMIN_ID
from database import init_db
from keyboards import main_menu_keyboard
from utils.audio_converter import convert_ogg_to_mp3
from utils.audio_cleanup import cleanup_guess_audio

from handlers import start, learn, games, test, stats, help, admin
from handlers import user_words # Новый импорт для пользовательских команд

async def main():
    logging.basicConfig(level=logging.INFO)

    await init_db()

    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Include all feature routers first
    dp.include_router(start.router)
    dp.include_router(learn.router)
    dp.include_router(games.router)
    dp.include_router(test.router)
    dp.include_router(stats.router)
    dp.include_router(help.router)
    dp.include_router(admin.router)
    dp.include_router(user_words.router) # Регистрируем роутер для пользовательских слов

    @dp.message(F.text == "⬆️ В главное меню", F.fsm_state == None)
    async def already_in_main_menu(message: Message):
        await message.answer("Вы уже в главном меню.")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
