import json
import os
from typing import List

BAD_WORDS_FILE = os.path.join("data", "internal", "bad_words.json")
_bad_words_cache: List[str] = []

def _load_bad_words():
    global _bad_words_cache
    if not os.path.exists(BAD_WORDS_FILE):
        _bad_words_cache = []
        return
    try:
        with open(BAD_WORDS_FILE, 'r', encoding='utf-8') as f:
            _bad_words_cache = [word.lower() for word in json.load(f)]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Ошибка загрузки файла плохих слов {BAD_WORDS_FILE}: {e}")
        _bad_words_cache = []

def is_bad_word(word: str) -> bool:
    if not _bad_words_cache:
        _load_bad_words() # Загружаем слова, если кэш пуст
    return word.lower() in _bad_words_cache

# Загружаем слова при импорте модуля
_load_bad_words()
