import asyncio
import datetime
import os
from utils.log_archiver import rotate_logs_monthly
import config
from aiogram import Bot # Импортируем Bot для отправки сообщений
# import aioschedule as schedule # Удаляем aioschedule
from database import reset_all_user_statistics # Импортируем функцию сброса статистики

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
    ogg_dir = os.path.join("data", "sounds", "ogg")
    os.makedirs(mp3_dir, exist_ok=True) # Ensure directory exists
    os.makedirs(ogg_dir, exist_ok=True) # Ensure directory exists

    while True:
        now = datetime.datetime.now()
        # Calculate time until next 12 PM
        next_run = now.replace(hour=12, minute=0, second=0, microsecond=0)
        if now.hour >= 12:
            next_run += datetime.timedelta(days=1)
        
        wait_seconds = (next_run - now).total_seconds()
        print(f"Следующая проверка аудиофайлов (mp3 и ogg) запланирована на {next_run}. Ожидание {wait_seconds:.0f} секунд.")
        await asyncio.sleep(wait_seconds)

        # now = datetime.datetime.now() # Update `now` after sleep
        
        if not config.CHECK_NEW_AUDIO:
            print("Проверка новых аудиофайлов отключена в config.py.")
            # await asyncio.sleep(60) # Короткая задержка, чтобы не забивать логи, если проверка отключена
            continue

        mp3_audio_files = [f for f in os.listdir(mp3_dir) if os.path.isfile(os.path.join(mp3_dir, f))]
        ogg_audio_files = [f for f in os.listdir(ogg_dir) if os.path.isfile(os.path.join(ogg_dir, f))]
        
        all_new_audio_files = mp3_audio_files + ogg_audio_files

        if all_new_audio_files:
            count = len(all_new_audio_files)
            admin_message = f"Обнаружено {count} новых аудиофайлов, требующих внимания (в папках `data/sounds/mp3` и `data/sounds/ogg`)."\
                            f"\n\nMP3 файлы: {', '.join(mp3_audio_files) if mp3_audio_files else 'нет'}"\
                            f"\nOGG файлы: {', '.join(ogg_audio_files) if ogg_audio_files else 'нет'}"
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, admin_message, parse_mode="Markdown")
                    print(f"Администратору {admin_id} отправлено уведомление о новых аудиофайлах.")
                except Exception as e:
                    print(f"Не удалось отправить уведомление администратору {admin_id}: {e}")
        else:
            print("В папках data/sounds/mp3 и data/sounds/ogg новых аудиофайлов не найдено.")

async def reset_all_user_statistics_task(bot: Bot):
    # Проверяем, что сегодня 1-е число месяца
    if datetime.datetime.now().day != 1:
        print("Сегодня не 1-е число месяца. Пропускаю ежемесячный сброс статистики.")
        return
    
    print("Запускаю ежемесячный сброс статистики пользователей...")
    success = await reset_all_user_statistics()
    if success:
        message_to_send = "✅ Ежемесячный сброс статистики пользователей успешно выполнен! Ваши рейтинги и очки обнулены. Соревнуйтесь снова!"
        print("Ежемесячный сброс статистики успешно выполнен.")
    else:
        message_to_send = "❌ Произошла ошибка при ежемесячном сбросе статистики пользователей."
        print("Ошибка при ежемесячном сбросе статистики.")

    # Отправляем сообщение всем админам
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, message_to_send)
        except Exception as e:
            print(f"Не удалось отправить сообщение администратору {admin_id}: {e}")

async def monthly_reset_loop(bot: Bot):
    """
    Custom loop to schedule monthly reset of user statistics on the 1st of every month at 00:01.
    """
    while True:
        now = datetime.datetime.now()
        # Определяем целевое время (00:00 1-го числа следующего месяца)
        if now.day < 1:
            # Если сегодня до 1-го числа, то это 1-е число текущего месяца
            target_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            # Если сегодня 1-е число или после, то это 1-е число следующего месяца
            # Вычисляем первое число следующего месяца
            # Для этого сначала переходим к следующему месяцу, затем устанавливаем день в 1
            next_month = now.replace(day=28) + datetime.timedelta(days=4) # Уходим подальше в следующий месяц
            target_date = next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Если целевая дата уже прошла в текущем месяце (т.е. сейчас, например, 1 октября 00:02, а цель была 1 октября 00:00),
        # то переносим цель на 1 число следующего месяца.
        if now > target_date:
            next_month = now.replace(day=28) + datetime.timedelta(days=4)
            target_date = next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        wait_seconds = (target_date - now).total_seconds()

        if wait_seconds < 0:
            # Если по какой-то причине wait_seconds отрицательный (например, сразу после 00:00),
            # то ждем до 1-го числа следующего месяца.
            next_month = now.replace(day=28) + datetime.timedelta(days=4)
            target_date = next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            wait_seconds = (target_date - now).total_seconds()

        print(f"Следующий ежемесячный сброс статистики запланирован на {target_date}. Ожидание {wait_seconds:.0f} секунд.")
        await asyncio.sleep(wait_seconds)

        if config.AUTO_RESET_STATS_MONTHLY:
            await reset_all_user_statistics_task(bot)
        else:
            print("Ежемесячный автосброс статистики отключен. Пропускаю выполнение.")

        # После выполнения задачи (или пропуска), сразу пересчитываем дату для следующего месяца,
        # чтобы избежать повторного срабатывания в том же цикле для той же даты.
        # Ждем 1 секунду, чтобы избежать бесконечного цикла, если sleep был очень короткий
        await asyncio.sleep(1)


async def start_background_tasks(bot: Bot):
    asyncio.create_task(check_and_rotate_logs())
    asyncio.create_task(check_new_audio_for_admin_notification(bot))
    asyncio.create_task(monthly_reset_loop(bot)) # Запускаем пользовательский планировщик
