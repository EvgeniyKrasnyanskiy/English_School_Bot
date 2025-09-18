import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from config import TOKEN
from database import init_db
from keyboards import main_menu_keyboard
from utils.audio_converter import convert_ogg_to_mp3

from handlers import start, learn, games, test, stats, help, admin

async def main():
    logging.basicConfig(level=logging.INFO)

    await init_db()
    await convert_ogg_to_mp3() # Call the conversion function here

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

    # Handler for 'В главное меню' button from anywhere
    @dp.message(F.text == "⬆️ В главное меню")
    async def back_to_main_menu_global(message: Message, state: FSMContext):
        # Try to delete any audio messages tracked in FSM state
        try:
            current_data = await state.get_data()
            previous_audio_ids = current_data.get("sent_audio_ids", [])
            if previous_audio_ids:
                from aiogram import Bot
                bot = Bot.get_current()
                if bot:
                    for msg_id in previous_audio_ids:
                        try:
                            await bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
                        except Exception:
                            pass
        except Exception:
            pass
        await state.clear()
        await message.answer("Вы вернулись в главное меню.", reply_markup=main_menu_keyboard)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
