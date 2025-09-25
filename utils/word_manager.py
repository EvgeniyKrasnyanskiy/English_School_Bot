import json
import os
from typing import List, Dict, Optional, Any
import random
import string
import logging
import datetime
import re # Added import
import asyncio # Added import
import database # Already present
import config # Import config

logger = logging.getLogger(__name__)

class WordManager:
    """Класс для управления файлами слов и переключения между ними."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.config_file_path = os.path.join(self.data_dir, "config", "config.json")
        # Словарь для хранения выбранных файлов и display_name для каждого пользователя
        self.user_current_files: Dict[int, Dict[str, str]] = {} 
        self._ensure_data_dir()
        self._load_config() # Загружаем конфигурацию при инициализации
    
    def _ensure_data_dir(self):
        """Создает директории данных, если они не существуют."""
        main_data_dir = self.data_dir # 'data'
        words_dir = os.path.join(main_data_dir, "words")
        config_dir = os.path.join(main_data_dir, "config")
        sounds_dir = os.path.join(main_data_dir, "sounds")
        images_dir = os.path.join(main_data_dir, "images")
        temp_audio_dir = os.path.join(sounds_dir, "temp_audio") # Moved temp_audio inside sounds_dir
        db_dir = os.path.join(main_data_dir, "db")
        
        for d in [main_data_dir, words_dir, config_dir, sounds_dir, images_dir, temp_audio_dir, db_dir]:
            if not os.path.exists(d):
                os.makedirs(d)
                logger.debug(f"[_ensure_data_dir] Created directory: {d}")
    
    def _get_sanitized_name(self, name: str) -> str:
        """Санитизирует имя пользователя для использования в именах файлов или ключах."""
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '', name.replace(' ', '_')).lower()
        return sanitized if sanitized else "unknown"

    def _get_descriptive_key_for_json(self, user_id: int, display_name: str) -> str:
        """Генерирует описательный ключ для JSON, включающий user_id и санитизированное имя."""
        sanitized_display_name = self._get_sanitized_name(display_name)
        return f"{user_id}_{sanitized_display_name}"

    def _load_config(self):
        """Загружает текущие активные файлы для пользователей из конфига."""
        try:
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if 'user_current_files' in config and isinstance(config['user_current_files'], dict):
                    temp_user_files: Dict[int, Dict[str, str]] = {} 
                    for key_str, filename in config['user_current_files'].items():
                        try:
                            user_id_int = int(key_str) # Attempt to parse as old format (int user ID)
                            # If old format, store with a placeholder display_name, it will be updated by set_user_current_file
                            temp_user_files[user_id_int] = {"filename": filename, "display_name": "Unknown User"}
                            logger.info(f"[_load_config] Loaded old config key for user {user_id_int} with filename {filename}.")
                        except ValueError: # New format key (user_id_display_name)
                            parts = key_str.split('_', 1) # Split only on first underscore
                            if parts and parts[0].isdigit():
                                user_id_int = int(parts[0])
                                # Extract display name from the key, removing user_id_ prefix
                                display_name_from_key = parts[1].replace('_', ' ') if len(parts) > 1 else "Unknown User"
                                temp_user_files[user_id_int] = {"filename": filename, "display_name": display_name_from_key}
                                logger.info(f"[_load_config] Loaded new config key for user {user_id_int} with filename {filename} and display name {display_name_from_key}.")
                            else:
                                logger.warning(f"[_load_config] Invalid key format in config file: {key_str}. Skipping.")

                    self.user_current_files = temp_user_files
                    logger.info(f"[_load_config] Final loaded user_current_files: {self.user_current_files}")
                else:
                    logger.warning(f"[_load_config] 'user_current_files' key not found or invalid in {self.config_file_path}. Initializing empty.")
        except FileNotFoundError:
            logger.info(f"[_load_config] Configuration file {self.config_file_path} not found. Initializing empty user_current_files.")
            self.user_current_files = {}
        except json.JSONDecodeError as e:
            logger.error(f"[_load_config] Error decoding JSON from {self.config_file_path}: {e}")
            self.user_current_files = {}

    def _save_config(self):
        """Сохраняет текущие активные файлы для пользователей в конфиг."""
        try:
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                saved_files: Dict[str, str] = {} # type: ignore
                for user_id, user_data in self.user_current_files.items():
                    # Generate descriptive key for JSON based on current user_id and stored display_name
                    descriptive_key = self._get_descriptive_key_for_json(user_id, user_data.get("display_name", "Unknown User"))
                    saved_files[descriptive_key] = user_data["filename"]

                json.dump({'user_current_files': saved_files}, f, ensure_ascii=False, indent=4)
            logger.info(f"[_save_config] Saved user_current_files: {saved_files}") # Log saved_files, not self.user_current_files
        except Exception as e:
            logger.error(f"[_save_config] Error saving configuration {self.config_file_path}: {e}")
    
    def get_available_files(self) -> List[str]:
        """Возвращает список доступных файлов со словами."""
        if not os.path.exists(self.data_dir):
            return []
        
        words_dir = os.path.join(self.data_dir, "words")
        if not os.path.exists(words_dir):
            return []
        
        word_files = [file for file in os.listdir(words_dir) if file.endswith('.json')]
        return sorted(word_files)
    
    def get_user_current_file(self, user_id: int) -> str:
        """Возвращает имя текущего файла для конкретного пользователя."""
        user_data = self.user_current_files.get(user_id)
        filename = user_data['filename'] if user_data else config.DEFAULT_WORD_SET
        logger.info(f"[get_user_current_file] For user {user_id}, returning filename: {filename}")
        return filename
    
    def set_user_current_file(self, user_id: int, filename: str, user_display_name: str) -> bool:
        """Устанавливает текущий файл слов для конкретного пользователя, обновляя его display_name."""
        if not filename.endswith('.json'):
            filename += '.json'
        
        file_path = os.path.join(self.data_dir, "words", filename)
        if os.path.exists(file_path):
            self.user_current_files[user_id] = {"filename": filename, "display_name": user_display_name}
            self._save_config() # Сохраняем изменение в конфиг
            logger.info(f"[set_user_current_file] User {user_id} ({user_display_name}) set current file to: {filename}")
            return True
        logger.warning(f"[set_user_current_file] File not found, cannot set current file for user {user_id} ({user_display_name}): {filename}")
        return False
    
    def get_current_file_path(self, user_id: int = None) -> str:
        """Возвращает полный путь к текущему файлу. Если user_id не указан, использует общий 'all_words.json'."""
        if user_id is not None:
            filename = self.get_user_current_file(user_id)
        else:
            filename = config.DEFAULT_WORD_SET # Дефолтный файл для обратной совместимости или общих операций
        file_path = os.path.join(self.data_dir, "words", filename)
        logger.debug(f"[get_current_file_path] For user {user_id if user_id else 'None'}, file path: {file_path}")
        return file_path
    
    def load_words(self, user_id: int = None) -> List[Dict[str, str]]:
        """Загружает слова из текущего файла для пользователя или общего файла."""
        file_path = self.get_current_file_path(user_id)
        logger.debug(f"[load_words] Attempting to load words from: {file_path} for user {user_id if user_id else 'None'}")
        return self.load_words_from_file(file_path)
    
    def load_words_from_file(self, file_path: str) -> List[Dict[str, str]]:
        """Загружает слова из указанного файла."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                words = json.load(f)
            logger.debug(f"[load_words_from_file] Successfully loaded {len(words)} words from: {file_path}")
            return words
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"[load_words_from_file] Error loading file {file_path}: {e}")
            return []
    
    def save_words(self, words: List[Dict[str, str]], user_id: int = None) -> bool:
        """Сохраняет слова в текущий файл для пользователя или общий файл."""
        file_path = self.get_current_file_path(user_id)
        logger.debug(f"[save_words] Attempting to save words to: {file_path} for user {user_id if user_id else 'None'}")
        return self.save_words_to_file(words, file_path)
    
    def save_words_to_file(self, words: List[Dict[str, str]], file_path: str) -> bool:
        """Сохраняет слова в указанный файл."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(words, f, ensure_ascii=False)
            logger.debug(f"[save_words_to_file] Successfully saved {len(words)} words from: {file_path}")
            return True
        except Exception as e:
            logger.error(f"[save_words_to_file] Error saving file {file_path}: {e}")
            return False
    
    def add_word_to_file(self, filename: str, word_pair: Dict[str, str]) -> bool:
        """Добавляет слово в указанный файл."""
        file_path = os.path.join(self.data_dir, "words", filename)
        words = self.load_words_from_file(file_path)
        words.append(word_pair)
        return self.save_words_to_file(words, file_path)
    
    def delete_word_from_file(self, filename: str, en_word: str) -> bool:
        """Удаляет слово из указанного файла."""
        file_path = os.path.join(self.data_dir, "words", filename)
        words = self.load_words_from_file(file_path)
        initial_len = len(words)
        words = [word for word in words if word['en'].lower() != en_word.lower()]
        if len(words) < initial_len:
            return self.save_words_to_file(words, file_path)
        return False
    
    def _generate_dynamic_filename_suffix(self) -> str:
        """Генерирует динамическую часть имени файла (случайные буквы + дата)."""
        # Генерируем случайные буквы в зависимости от текущей даты
        current_day = datetime.datetime.now().day
        num_random_letters = 1 if current_day % 2 == 0 else 2
        random_letters = ''.join(random.choice(string.ascii_lowercase) for _ in range(num_random_letters))

        # Добавляем день и месяц создания списка
        current_date = datetime.datetime.now()
        date_suffix = current_date.strftime("%d%m")

        return f"{random_letters}{date_suffix}"

    def get_user_custom_filename(self, user_id: int, user_display_name: str) -> str:
        """Генерирует стабильную базовую часть имени файла для пользовательского словаря."""
        # Извлекаем первые 3 буквы из имени пользователя, или 'lst' если нет букв
        alpha_chars = ''.join(filter(str.isalpha, user_display_name)).lower()
        prefix = (alpha_chars[:3] if len(alpha_chars) >= 3 else "lst").ljust(3, 'l') # Ensure prefix is 3 chars

        # Извлекаем последние 3 цифры ID пользователя
        user_id_str = str(user_id)
        suffix_id = user_id_str[-3:]

        # Формируем базовое имя файла
        base_filename = f"{prefix}{suffix_id}"
        return base_filename

    def create_new_file(self, user_id: int, user_display_name: str, words: List[Dict[str, str]] = None) -> Optional[str]:
        """Создает новый файл со словами с динамическим именем, устанавливает его как текущий для пользователя и возвращает полное имя файла."""
        base_filename = self.get_user_custom_filename(user_id, user_display_name)
        dynamic_suffix = self._generate_dynamic_filename_suffix()
        
        # Полное динамическое имя файла до .json
        full_dynamic_name_base = f"{base_filename}{dynamic_suffix}"
        
        # Обрезаем до 12 с символов, если необходимо
        final_filename_base = full_dynamic_name_base[:12].lower()
        final_filename = f"{final_filename_base}.json"

        file_path = os.path.join(self.data_dir, "words", final_filename)
        
        if os.path.exists(file_path):
            logger.warning(f"[create_new_file] File already exists, cannot create: {final_filename}")
            return None  # Файл уже существует

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(words or [], f, ensure_ascii=False)
            logger.info(f"[create_new_file] Successfully created new file: {final_filename}")
            self.set_user_current_file(user_id, final_filename, user_display_name) # Устанавливаем новый файл как текущий
            return final_filename
        except Exception as e:
            logger.error(f"[create_new_file] Error creating file {final_filename}: {e}")
            return None

    def delete_file(self, filename: str) -> bool:
        """Удаляет файл со словами."""
        if not filename.endswith('.json'):
            filename += '.json'
        
        file_path = os.path.join(self.data_dir, "words", filename)
        if not os.path.exists(file_path) or filename == "all_words.json":
            return False  # Нельзя удалить основной файл
        
        try:
            os.remove(file_path)
            # Удаляем файл из user_current_files, если он был выбран
            users_to_reset = [user_id for user_id, user_data in self.user_current_files.items() if user_data['filename'] == filename]
            for user_id in users_to_reset:
                del self.user_current_files[user_id]
            self._save_config() # Сохраняем изменения в конфиг
            return True
        except Exception as e:
            print(f"Ошибка удаления файла {file_path}: {e}")
            return False
    
    def get_file_info(self, filename: str) -> Optional[Dict[str, Any]]:
        """Возвращает информацию о файле (количество слов, размер и т.д.)."""
        if not filename.endswith('.json'):
            filename += '.json'
        
        file_path = os.path.join(self.data_dir, "words", filename)
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                words = json.load(f)
            
            file_size = os.path.getsize(file_path)
            return {
                'filename': filename,
                'word_count': len(words),
                'file_size': file_size,
                # 'is_current': filename == self.current_file # Удалено, т.к. теперь для каждого пользователя свой файл
            }
        except Exception as e:
            logger.error(f"[get_file_info] Error getting file info for {file_path}: {e}")
            return None

    def remove_duplicates_from_file(self, filename: str) -> int:
        """Удаляет дубликаты слов из указанного файла, основываясь на английском слове.
        Возвращает количество удаленных дубликатов."""
        file_path = os.path.join(self.data_dir, "words", filename)
        words = self.load_words_from_file(file_path)

        seen_en_words = set()
        unique_words = []
        duplicates_count = 0

        for word_pair in words:
            en_word_lower = word_pair['en'].lower()
            if en_word_lower not in seen_en_words:
                unique_words.append(word_pair)
                seen_en_words.add(en_word_lower)
            else:
                duplicates_count += 1
        
        if duplicates_count > 0:
            self.save_words_to_file(unique_words, file_path)
        
        return duplicates_count

# Глобальный экземпляр менеджера слов
word_manager = WordManager()
