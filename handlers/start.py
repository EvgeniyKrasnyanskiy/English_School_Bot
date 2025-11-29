from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import add_user, get_user, update_last_active
from keyboards import main_menu_keyboard
from utils.data_manager import update_user_profile_data
from config import ADMIN_IDS
from aiogram import Bot
from utils.word_manager import word_manager # Import word_manager
import config # Import config
from utils.data_manager import get_muted_users # Import get_muted_users

router = Router()

class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_admin_message = State() # New state for waiting for user message to admin

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await get_user(user_id)

    if user:
        await update_last_active(user_id)
        # Ensure display_name is updated in word_manager's config, in case it changed
        user_display_name = message.from_user.full_name or message.from_user.username or user['name'] or "Unknown User"
        word_manager.set_user_current_file(user_id, word_manager.get_user_current_file(user_id), user_display_name) # Update display_name
        await message.answer(
            f"С возвращением, {user['name']}!",
            reply_markup=main_menu_keyboard
        )
        await state.clear()
    else:
        await message.answer(
            "Привет! Я бот для изучения английского языка. "
            "Как тебя зовут? \nПожалуйста, введи только свое имя и класс (например, Саша 2В)"
        )
        await state.set_state(Registration.waiting_for_name)

@router.message(Registration.waiting_for_name)
async def process_name(message: Message, state: FSMContext, bot: Bot):
    user_name = message.text.strip()
    user_id = message.from_user.id

    if user_name:
        # Ensure first_name, last_name, username are always strings
        first_name = message.from_user.first_name or ''
        last_name = message.from_user.last_name or ''
        username = message.from_user.username or ''
        
        user_display_name = message.from_user.full_name or username or user_name or "Unknown User"

        await add_user(
            user_id,
            user_name,
            first_name,
            last_name,
            username
        )
        # Set default word set for new user
        word_manager.set_user_current_file(user_id, config.DEFAULT_WORD_SET, user_display_name)
        # Update user profile data in stats.json
        await update_user_profile_data(
            str(user_id),
            user_name,
            first_name,
            last_name,
            username
        )
        # Notify admin about a new user
        try:
            if bot and ADMIN_IDS:
                full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
                username = f"@{message.from_user.username}" if message.from_user.username else "(no username)"
                for admin_id in ADMIN_IDS:
                    await bot.send_message(
                        chat_id=admin_id,
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
            "\nВыбери действие в меню ниже:",
            reply_markup=main_menu_keyboard
        )
        await state.clear()
    else:
        await message.answer(
            "Пожалуйста, введи свое имя."
        )

# Удалена функция cleanup_old_audio_messages по запросу пользователя

@router.message(Command("msg_to_admin"))
async def msg_to_admin_command(message: Message, state: FSMContext):
    """Allows users to send a message to the admin."""
    user_id = message.from_user.id
    muted_users = await get_muted_users()
    if user_id in muted_users:
        await message.answer("Вы не можете отправлять сообщения администратору.")
        return

    await message.answer("Пожалуйста, напишите сообщение, которое вы хотите отправить администратору. Вы можете отправить текст, фото или видео.")
    await state.set_state(Registration.waiting_for_admin_message)

@router.message(Registration.waiting_for_admin_message)
async def process_admin_message(message: Message, state: FSMContext, bot: Bot):
    """Processes the message sent by the user to the admin."""
    if message.text and message.text.lower() == "/cancel":
        await state.clear()
        await message.answer("Отправка сообщения отменена.", reply_markup=main_menu_keyboard)
        return

    user_id = message.from_user.id
    full_name = message.from_user.full_name or "Unknown"
    username = f"@{message.from_user.username}" if message.from_user.username else "(no username)"
    
    # Get registered name from DB if available, otherwise use full name
    user_data = await get_user(user_id)
    registered_name = user_data['name'] if user_data else "Unregistered"

    admin_notification = (
        f"📩 <b>Новое сообщение от пользователя:</b>\n"
        f"Имя: {registered_name}\n"
        f"TG: {full_name} {username}\n"
        f"ID: <code>{user_id}</code>\n"
        f"Сообщение:"
    )

    sent_count = 0
    if ADMIN_IDS:
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(chat_id=admin_id, text=admin_notification, parse_mode="HTML")
                # Forward the user's message (using copy_message to keep it clean)
                await bot.copy_message(
                    chat_id=admin_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                sent_count += 1
            except Exception:
                pass # Ignore errors if admin blocked bot or something

    if sent_count > 0:
        await message.answer("✅ Ваше сообщение успешно отправлено администратору!", reply_markup=main_menu_keyboard)
    else:
        await message.answer("❌ Не удалось отправить сообщение. Попробуйте позже.", reply_markup=main_menu_keyboard)
    
    await state.clear()
