import asyncio
import datetime
import os
from utils.log_archiver import rotate_logs_monthly
import config
from aiogram import Bot # Импортируем Bot для отправки сообщений

async def check_and_rotate_logs():
    """
    Checks daily if it's the 1st day of the month and rotates logs.
    Runs at 4 AM every day.
    """
    while True:
        now = datetime.datetime.now()
        # Calculate time until next 4 AM
        next_run = now.replace(hour=4, minute=0, second=0, microsecond=0)
        if now.hour >= 4:
            next_run += datetime.timedelta(days=1)
        
        wait_seconds = (next_run - now).total_seconds()
        print(f"Следующая проверка ротации логов запланирована на {next_run}. Ожидание {wait_seconds:.0f} секунд.")
        await asyncio.sleep(wait_seconds)

        now = datetime.datetime.now() # Update `now` after sleep
        if now.day == 1:
            print(f"Сегодня 1-е число месяца ({now.strftime('%Y-%m-%d')}). Запускаю ротацию логов...")
            rotate_logs_monthly()
        else:
            print(f"Сегодня не 1-е число месяца ({now.day}). Пропускаю ротацию логов.")

async def check_new_audio_for_admin_notification(bot: Bot):
    """
    Checks daily at 12 PM for new audio files in data/sounds/mp3 and notifies admin if CHECK_NEW_AUDIO is True.
    """
    mp3_dir = os.path.join("data", "sounds", "mp3") # Изменено на data/sounds/mp3
    os.makedirs(mp3_dir, exist_ok=True) # Ensure directory exists

    while True:
        now = datetime.datetime.now()
        # Calculate time until next 12 PM
        next_run = now.replace(hour=12, minute=0, second=0, microsecond=0)
        if now.hour >= 12:
            next_run += datetime.timedelta(days=1)
        
        wait_seconds = (next_run - now).total_seconds()
        print(f"Следующая проверка папки mp3 запланирована на {next_run}. Ожидание {wait_seconds:.0f} секунд.")
        await asyncio.sleep(wait_seconds)

        now = datetime.datetime.now() # Update `now` after sleep
        
        if not config.CHECK_NEW_AUDIO:
            print("Проверка папки data/sounds/mp3 отключена в config.py.")
            continue

        audio_files = [f for f in os.listdir(mp3_dir) if os.path.isfile(os.path.join(mp3_dir, f))]
        
        if audio_files:
            count = len(audio_files)
            admin_message = f"В папке `data/sounds/mp3` обнаружено {count} новых аудиофайлов, требующих внимания."\
                            f"\n\nИмена файлов: {', '.join(audio_files)}"
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, admin_message, parse_mode="Markdown")
                    print(f"Администратору {admin_id} отправлено уведомление о новых аудиофайлах.")
                except Exception as e:
                    print(f"Не удалось отправить уведомление администратору {admin_id}: {e}")
        else:
            print("В папке data/sounds/mp3 новых аудиофайлов не найдено.")

async def start_background_tasks(bot: Bot):
    asyncio.create_task(check_and_rotate_logs())
    asyncio.create_task(check_new_audio_for_admin_notification(bot))
