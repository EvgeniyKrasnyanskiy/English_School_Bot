import os
import asyncio
import subprocess
from typing import List

async def convert_ogg_to_mp3() -> (List[str], bool):
    log_messages = []
    ffmpeg_exe_path = r"C:\ffmpeg\bin\ffmpeg.exe"
    ogg_dir = "data/sounds"

    ogg_archive_dir = os.path.join(ogg_dir, "ogg")
    mp3_output_dir = os.path.join(ogg_dir, "mp3") # Добавляем путь для MP3 файлов
    overall_success = True # Флаг общего успеха

    if not os.path.exists(ogg_archive_dir):
        os.makedirs(ogg_archive_dir, exist_ok=True)
    if not os.path.exists(mp3_output_dir): # Создаем папку для MP3 файлов, если ее нет
        os.makedirs(mp3_output_dir, exist_ok=True)
    if not os.path.exists(ogg_dir):
        log_messages.append(f"Директория {ogg_dir} не существует. Пропускаю конвертацию OGG в MP3.")
        return log_messages, True # Нет файлов - не ошибка

    # Check if ffmpeg.exe exists before proceeding
    if not os.path.exists(ffmpeg_exe_path):
        log_messages.append(f"Ошибка: ffmpeg.exe не найден по пути {ffmpeg_exe_path}. Невозможно конвертировать аудио.")
        return log_messages, False # Критическая ошибка

    log_messages.append(f"Проверяю {ogg_dir} на наличие OGG файлов для конвертации в MP3...")
    converted_count = 0
    for filename in os.listdir(ogg_dir):
        if filename.endswith(".ogg"):
            ogg_filepath = os.path.join(ogg_dir, filename)
            mp3_filename = filename.replace(".ogg", ".mp3")
            mp3_filepath = os.path.join(mp3_output_dir, mp3_filename) # Сохраняем MP3 в отдельную папку

            if os.path.exists(mp3_filepath):
                log_messages.append(f"MP3 файл уже существует для {filename}. Пропускаю конвертацию.")
                continue

            log_messages.append(f"Конвертирую {filename} в {mp3_filename}...")
            try:
                # Use subprocess to run ffmpeg command
                command = [
                    ffmpeg_exe_path,
                    "-i", ogg_filepath,
                    "-acodec", "libmp3lame",
                    "-q:a", "2",
                    mp3_filepath
                ]
                # Run the command in a separate thread to avoid blocking asyncio event loop
                process_result = await asyncio.to_thread(lambda: subprocess.run(command, check=False, capture_output=True))
                
                if process_result.returncode == 0:
                    log_messages.append(f"Успешно конвертирован {filename} в {mp3_filename}")
                    # Move original .ogg file to the 'ogg' subfolder
                    os.replace(ogg_filepath, os.path.join(ogg_archive_dir, filename))
                    archived_path_formatted = ogg_archive_dir.replace(os.sep, '/')
                    log_messages.append(f"Перемещен {filename} в {archived_path_formatted}/")
                    converted_count += 1
                else:
                    overall_success = False
                    error_msg = process_result.stderr.decode(errors='ignore').strip()
                    log_messages.append(f"Ошибка конвертации {filename}: {error_msg}")
            except FileNotFoundError:
                overall_success = False
                log_messages.append(f"Ошибка: ffmpeg.exe не найден по пути {ffmpeg_exe_path}. Этого не должно было произойти.")
            except Exception as e:
                overall_success = False
                log_messages.append(f"Произошла непредвиденная ошибка при конвертации {filename}: {str(e)}")

    if converted_count == 0 and overall_success:
        log_messages.append("Все OGG файлы уже конвертированы или отсутствуют.")
    elif converted_count > 0 and overall_success:
        log_messages.append(f"Конвертация завершена. Конвертировано и перемещено {converted_count} файлов.")
    elif not overall_success:
        log_messages.append("Конвертация завершена с ошибками.")

    return log_messages, overall_success
