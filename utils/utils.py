import random
import json
from .word_manager import word_manager
import os

def shuffle_word(word: str) -> str:
    """Shuffles the letters of a word."""
    word_list = list(word)
    random.shuffle(word_list)
    return "".join(word_list)

def get_random_word(words: list):
    """Returns a random word from the loaded words."""
    return random.choice(words)

def get_quiz_options(correct_word_ru: str, all_words: list, num_options: int = 4) -> list:
    """Generates a list of quiz options including the correct answer and incorrect ones."""
    options = [correct_word_ru]
    incorrect_words = [w["ru"] for w in all_words if w["ru"] != correct_word_ru]
    random.shuffle(incorrect_words)
    
    # Ensure we don't pick more incorrect words than available
    num_incorrect = min(num_options - 1, len(incorrect_words))
    options.extend(incorrect_words[:num_incorrect])
    random.shuffle(options)
    return options

async def add_word(new_word: dict, filename: str = "words.json") -> bool:
    """Adds a new word to the specified file."""
    return word_manager.add_word_to_file(filename, new_word)

async def get_words_alphabetical(filename: str = "words.json") -> list[dict]:
    """Loads words from the specified file and returns them sorted alphabetically by English word."""
    words = word_manager.load_words_from_file(os.path.join(word_manager.data_dir, filename))
    return sorted(words, key=lambda x: x['en'].lower())

async def delete_word(word_to_delete_en: str, filename: str = "words.json") -> bool:
    """Deletes a word from the specified file by its English representation."""
    return word_manager.delete_word_from_file(filename, word_to_delete_en)
