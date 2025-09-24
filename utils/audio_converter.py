import os
import asyncio
import subprocess
from typing import List

async def check_for_similar_audio_file(filename_without_extension: str) -> bool:
    """Checks if a file with a similar name (case-insensitive) exists in data/sounds or its subdirectories."""
    sounds_dir = os.path.join("data", "sounds")
    if not os.path.exists(sounds_dir):
        return False

    target_name_lower = filename_without_extension.lower()

    for root, _, files in os.walk(sounds_dir):
        for file in files:
            file_basename, _ = os.path.splitext(file)
            if file_basename.lower() == target_name_lower:
                return True
    return False

async def convert_single_ogg_to_mp3(ogg_filepath: str, filename_without_extension: str) -> (List[str], bool):
    log_messages = []
    ffmpeg_exe_path = r"C:\ffmpeg\bin\ffmpeg.exe"
    
    # Define base sounds directory
    sounds_dir = os.path.join("data", "sounds")

    # Define output directories relative to sounds_dir
    ogg_archive_dir = os.path.join(sounds_dir, "ogg")
    mp3_output_dir = os.path.join(sounds_dir, "mp3")
    overall_success = True # Флаг общего успеха

    if not os.path.exists(ogg_archive_dir):
        os.makedirs(ogg_archive_dir, exist_ok=True)
    if not os.path.exists(mp3_output_dir): # Создаем папку для MP3 файлов, если ее нет
        os.makedirs(mp3_output_dir, exist_ok=True)
    if not os.path.exists(sounds_dir):
        log_messages.append(f"Директория {sounds_dir} не существует. Пропускаю конвертацию OGG в MP3.")
        return log_messages, True # Нет файлов - не ошибка

    # Check if ffmpeg.exe exists before proceeding
    if not os.path.exists(ffmpeg_exe_path):
        log_messages.append(f"Ошибка: ffmpeg.exe не найден по пути {ffmpeg_exe_path}. Невозможно конвертировать аудио.")
        return log_messages, False # Критическая ошибка

    log_messages.append(f"Проверяю {ogg_filepath} на наличие OGG файлов для конвертации в MP3...")
    converted_count = 0
    
    filename = os.path.basename(ogg_filepath)
    if filename.endswith(".ogg"):
        mp3_filename = f"{filename_without_extension}.mp3"
        mp3_filepath = os.path.join(mp3_output_dir, mp3_filename)

        if os.path.exists(mp3_filepath):
            log_messages.append(f"MP3 файл уже существует для {filename}. Пропускаю конвертацию.")
        else:
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
                log_messages.append(f"Выполняемая команда FFmpeg: {' '.join(command)}") # Debugging line
                # Run the command in a separate thread to avoid blocking asyncio event loop
                process_result = await asyncio.to_thread(lambda: subprocess.run(command, check=False, capture_output=True))
                
                if process_result.stdout:
                    log_messages.append(f"FFmpeg STDOUT: {process_result.stdout.decode(errors='ignore').strip()}") # Debugging line
                if process_result.stderr and process_result.returncode != 0:
                    log_messages.append(f"FFmpeg STDERR: {process_result.stderr.decode(errors='ignore').strip()}") # Debugging line
                
                if process_result.returncode == 0:
                    log_messages.append(f"Успешно конвертирован {filename} в {mp3_filename}")
                    # Move original .ogg file to the 'ogg' subfolder
                    final_ogg_destination = os.path.join(ogg_archive_dir, filename)
                    os.replace(ogg_filepath, final_ogg_destination)
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

async def convert_all_ogg_to_mp3() -> List[str]:
    log_messages = []
    ffmpeg_exe_path = r"C:\ffmpeg\bin\ffmpeg.exe"

    sounds_dir = os.path.join("data", "sounds")
    ogg_source_dir = os.path.join(sounds_dir, "ogg")
    mp3_output_dir = os.path.join(sounds_dir, "mp3")

    os.makedirs(ogg_source_dir, exist_ok=True)
    os.makedirs(mp3_output_dir, exist_ok=True)

    if not os.path.exists(ffmpeg_exe_path):
        log_messages.append(f"Ошибка: ffmpeg.exe не найден по пути {ffmpeg_exe_path}. Невозможно конвертировать аудио.")
        return log_messages

    ogg_files = [f for f in os.listdir(ogg_source_dir) if f.endswith(".ogg")]

    if not ogg_files:
        log_messages.append(f"В папке `{ogg_source_dir.replace(os.sep, '/')}` нет OGG файлов для конвертации.")
        return log_messages

    log_messages.append(f"Начинаю пакетную конвертацию OGG в MP3 из `{ogg_source_dir.replace(os.sep, '/')}`...")
    
    converted_count = 0
    for filename in ogg_files:
        ogg_filepath = os.path.join(ogg_source_dir, filename)
        filename_without_extension = os.path.splitext(filename)[0]
        
        mp3_filename = f"{filename_without_extension}.mp3"
        mp3_filepath = os.path.join(mp3_output_dir, mp3_filename)

        if os.path.exists(mp3_filepath):
            log_messages.append(f"MP3 файл '{mp3_filename}' уже существует. Пропускаю конвертацию.")
            continue

        log_messages.append(f"Конвертирую '{filename}' в '{mp3_filename}'...")
        try:
            command = [
                ffmpeg_exe_path,
                "-i", ogg_filepath,
                "-acodec", "libmp3lame",
                "-q:a", "2",
                mp3_filepath
            ]
            process_result = await asyncio.to_thread(lambda: subprocess.run(command, check=False, capture_output=True))
            
            if process_result.returncode == 0:
                log_messages.append(f"Успешно конвертирован '{filename}' в '{mp3_filename}'.")
                converted_count += 1
            else:
                error_msg = process_result.stderr.decode(errors='ignore').strip()
                log_messages.append(f"Ошибка конвертации '{filename}': {error_msg}")
        except Exception as e:
            log_messages.append(f"Произошла непредвиденная ошибка при конвертации '{filename}': {str(e)}")
        
        await asyncio.sleep(0.1) # Small delay to avoid API limits

    log_messages.append(f"Пакетная конвертация завершена. Конвертировано: {converted_count} файлов.")
    return log_messages

async def delete_audio_files_from_dir(target_dir: str, file_extension: str) -> List[str]:
    log_messages = []
    if not os.path.exists(target_dir):
        log_messages.append(f"Папка `{target_dir.replace(os.sep, '/')}` не существует.")
        return log_messages

    files_to_delete = [f for f in os.listdir(target_dir) if f.endswith(file_extension)]

    if not files_to_delete:
        log_messages.append(f"В папке `{target_dir.replace(os.sep, '/')}` нет файлов с расширением `{file_extension}` для удаления.")
        return log_messages

    log_messages.append(f"Начинаю удаление файлов `{file_extension}` из `{target_dir.replace(os.sep, '/')}`...")
    deleted_count = 0
    for filename in files_to_delete:
        filepath = os.path.join(target_dir, filename)
        try:
            os.remove(filepath)
            log_messages.append(f"✅ Удален файл: `{filename}`")
            deleted_count += 1
        except Exception as e:
            log_messages.append(f"❌ Ошибка при удалении файла `{filename}`: {e}")
    
    log_messages.append(f"Удаление завершено. Всего удалено: {deleted_count} файлов.")
    return log_messages
