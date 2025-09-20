import json
import os
from typing import List, Dict, Optional

class WordManager:
    """Класс для управления файлами слов и переключения между ними."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.config_file_path = os.path.join(self.data_dir, "config.json")
        self.user_current_files: Dict[int, str] = {} # Словарь для хранения выбранных файлов для каждого пользователя
        self._ensure_data_dir()
        self._load_config() # Загружаем конфигурацию при инициализации
    
    def _ensure_data_dir(self):
        """Создает директорию data, если она не существует."""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
    
    def _load_config(self):
        """Загружает текущие активные файлы для пользователей из конфига."""
        if os.path.exists(self.config_file_path):
            try:
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'user_current_files' in config and isinstance(config['user_current_files'], dict):
                        # Преобразуем ключи user_id в int при загрузке
                        self.user_current_files = {int(k): v for k, v in config['user_current_files'].items()}
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"Ошибка загрузки конфигурации {self.config_file_path}: {e}")
        
    def _save_config(self):
        """Сохраняет текущие активные файлы для пользователей в конфиг."""
        try:
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                # Преобразуем ключи user_id в str для сохранения в JSON
                json.dump({'user_current_files': {str(k): v for k, v in self.user_current_files.items()}}, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Ошибка сохранения конфигурации {self.config_file_path}: {e}")
    
    def get_available_files(self) -> List[str]:
        """Возвращает список доступных файлов со словами."""
        if not os.path.exists(self.data_dir):
            return []
        
        word_files = []
        for file in os.listdir(self.data_dir):
            if file.endswith('.json') and file not in ['stats.json', 'config.json']:
                word_files.append(file)
        return sorted(word_files)
    
    def get_user_current_file(self, user_id: int) -> str:
        """Возвращает имя текущего файла для конкретного пользователя."""
        return self.user_current_files.get(user_id, "words.json") # По умолчанию "words.json"
    
    def set_user_current_file(self, user_id: int, filename: str) -> bool:
        """Устанавливает текущий файл слов для конкретного пользователя."""
        if not filename.endswith('.json'):
            filename += '.json'
        
        file_path = os.path.join(self.data_dir, filename)
        if os.path.exists(file_path):
            self.user_current_files[user_id] = filename
            self._save_config() # Сохраняем изменение в конфиг
            return True
        return False
    
    def get_current_file_path(self, user_id: int = None) -> str:
        """Возвращает полный путь к текущему файлу. Если user_id не указан, использует общий 'words.json'."""
        if user_id is not None:
            filename = self.get_user_current_file(user_id)
        else:
            filename = "words.json" # Дефолтный файл для обратной совместимости или общих операций
        return os.path.join(self.data_dir, filename)
    
    def load_words(self, user_id: int = None) -> List[Dict[str, str]]:
        """Загружает слова из текущего файла для пользователя или общего файла."""
        file_path = self.get_current_file_path(user_id)
        return self.load_words_from_file(file_path)
    
    def load_words_from_file(self, file_path: str) -> List[Dict[str, str]]:
        """Загружает слова из указанного файла."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                words = json.load(f)
            return words
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Ошибка загрузки файла {file_path}: {e}")
            return []
    
    def save_words(self, words: List[Dict[str, str]], user_id: int = None) -> bool:
        """Сохраняет слова в текущий файл для пользователя или общий файл."""
        file_path = self.get_current_file_path(user_id)
        return self.save_words_to_file(words, file_path)
    
    def save_words_to_file(self, words: List[Dict[str, str]], file_path: str) -> bool:
        """Сохраняет слова в указанный файл."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(words, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"Ошибка сохранения файла {file_path}: {e}")
            return False
    
    def add_word_to_file(self, filename: str, word_pair: Dict[str, str]) -> bool:
        """Добавляет слово в указанный файл."""
        file_path = os.path.join(self.data_dir, filename)
        words = self.load_words_from_file(file_path)
        words.append(word_pair)
        return self.save_words_to_file(words, file_path)
    
    def delete_word_from_file(self, filename: str, en_word: str) -> bool:
        """Удаляет слово из указанного файла."""
        file_path = os.path.join(self.data_dir, filename)
        words = self.load_words_from_file(file_path)
        initial_len = len(words)
        words = [word for word in words if word['en'].lower() != en_word.lower()]
        if len(words) < initial_len:
            return self.save_words_to_file(words, file_path)
        return False
    
    def create_new_file(self, filename: str, words: List[Dict[str, str]] = None) -> bool:
        """Создает новый файл со словами."""
        if not filename.endswith('.json'):
            filename += '.json'
        
        file_path = os.path.join(self.data_dir, filename)
        if os.path.exists(file_path):
            return False  # Файл уже существует
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(words or [], f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"Ошибка создания файла {file_path}: {e}")
            return False
    
    def delete_file(self, filename: str) -> bool:
        """Удаляет файл со словами."""
        if not filename.endswith('.json'):
            filename += '.json'
        
        file_path = os.path.join(self.data_dir, filename)
        if not os.path.exists(file_path) or filename == "words.json":
            return False  # Нельзя удалить основной файл
        
        try:
            os.remove(file_path)
            # Удаляем файл из user_current_files, если он был выбран
            users_to_reset = [user_id for user_id, f in self.user_current_files.items() if f == filename]
            for user_id in users_to_reset:
                del self.user_current_files[user_id]
            self._save_config() # Сохраняем изменения в конфиг
            return True
        except Exception as e:
            print(f"Ошибка удаления файла {file_path}: {e}")
            return False
    
    def get_file_info(self, filename: str) -> Optional[Dict[str, any]]:
        """Возвращает информацию о файле (количество слов, размер и т.д.)."""
        if not filename.endswith('.json'):
            filename += '.json'
        
        file_path = os.path.join(self.data_dir, filename)
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
            print(f"Ошибка получения информации о файле {file_path}: {e}")
            return None
    
    def get_user_custom_filename(self, user_id: int, user_display_name: str) -> str:
        """Генерирует уникальное имя файла для пользовательского набора слов."""
        # Очищаем имя пользователя, оставляя только буквы, цифры и пробелы, затем заменяем пробелы на подчеркивания
        clean_name_parts = []
        for char in user_display_name:
            if char.isalnum():
                clean_name_parts.append(char)
            elif char.isspace():
                clean_name_parts.append('_')
        clean_name = "".join(clean_name_parts).lower().strip('_') # Удаляем лишние подчеркивания по краям
        
        # Убедимся, что user_id достаточно длинный, чтобы взять последние 4 цифры
        user_id_str = str(user_id)
        user_id_suffix = user_id_str[-4:] if len(user_id_str) >= 4 else user_id_str
        
        # Формируем базовое имя файла
        if clean_name:
            base_filename = f"{clean_name}_{user_id_suffix}"
        else:
            base_filename = f"user_{user_id_suffix}"
            
        # Добавляем расширение .json
        return f"{base_filename}.json"

    def remove_duplicates_from_file(self, filename: str) -> int:
        """Удаляет дубликаты слов из указанного файла, основываясь на английском слове.
        Возвращает количество удаленных дубликатов."""
        file_path = os.path.join(self.data_dir, filename)
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
