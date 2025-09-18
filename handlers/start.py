from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import add_user, get_user, update_last_active
from keyboards import main_menu_keyboard
from utils.data_manager import update_user_profile_data
from config import ADMIN_ID

router = Router()

class Registration(StatesGroup):
    waiting_for_name = State()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await get_user(user_id)

    if user:
        await update_last_active(user_id)
        await message.answer(
            f"Привет, {user['name']}! С возвращением в главное меню.",
            reply_markup=main_menu_keyboard
        )
        await state.clear()
    else:
        await message.answer(
            "Привет! Я бот для изучения английского языка. "
            "Как тебя зовут? (Пожалуйста, введи только свое имя)"
        )
        await state.set_state(Registration.waiting_for_name)

@router.message(Registration.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    user_name = message.text.strip()
    user_id = message.from_user.id

    if user_name:
        await add_user(user_id, user_name)
        # Update user profile data in stats.json
        await update_user_profile_data(
            str(user_id),
            user_name,
            message.from_user.first_name,
            message.from_user.last_name,
            message.from_user.username
        )
        # Notify admin about a new user
        try:
            from aiogram import Bot
            bot = Bot.get_current()
            if bot and ADMIN_ID:
                full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
                username = f"@{message.from_user.username}" if message.from_user.username else "(no username)"
                await bot.send_message(
                    chat_id=ADMIN_ID,
                    text=(
                        "🆕 Новый пользователь\n"
                        f"ID: {user_id}\n"
                        f"Имя в боте: {user_name}\n"
                        f"Профиль TG: {full_name} {username}"
                    )
                )
        except Exception:
            pass
        await message.answer(
            f"Очень приятно, {user_name}! Добро пожаловать!"
            "Выбери действие в меню ниже:",
            reply_markup=main_menu_keyboard
        )
        await state.clear()
    else:
        await message.answer(
            "Пожалуйста, введи свое имя."
        )
