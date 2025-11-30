import sys
print(sys.version)

import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from logging.handlers import TimedRotatingFileHandler # Импортируем TimedRotatingFileHandler

from config import TOKEN, ADMIN_IDS, AUTO_RESET_STATS_MONTHLY
from database import init_db
from keyboards import main_menu_keyboard
from utils.audio_converter import convert_single_ogg_to_mp3
from utils.audio_cleanup import cleanup_guess_audio
from utils.data_manager import get_banned_users

from handlers import start, learn, games, test, stats, help, admin
from handlers import user_words # Новый импорт для пользовательских команд
from utils.asyncio_background_tasks import start_background_tasks # Импортируем функцию для запуска фоновых задач

async def main():
    # Создаем папку для логов, если ее нет
    logs_dir = "logs"
    os.makedirs(logs_dir, exist_ok=True)

    # Настраиваем логирование
    logging.basicConfig(
        level=logging.INFO, # Уровень логирования
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(logs_dir, "bot_errors.log"), mode='a', encoding='utf-8'),
            logging.StreamHandler() # Вывод в консоль
        ]
    )

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

    @dp.message.outer_middleware()
    async def anti_ban_outer_middleware(handler, event, data):
        user_id = event.from_user.id
        if user_id in await get_banned_users():
            await event.answer("Вы заблокированы и не можете использовать этого бота.")
            return # Stop propagation for banned users

        return await handler(event, data) # Continue processing for non-banned users

    @dp.message(F.text == "⬆️ В главное меню", F.fsm_state == None)
    async def already_in_main_menu(message: Message):
        await message.answer("Вы уже в главном меню.")

    # Запускаем фоновые задачи
    await start_background_tasks(bot)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
