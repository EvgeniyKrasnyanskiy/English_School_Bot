import random
import json

def shuffle_word(word: str) -> str:
    """Shuffles the letters of a word."""
    word_list = list(word)
    random.shuffle(word_list)
    return "".join(word_list)

def load_words(file_path: str = 'data/words.json'):
    """Loads words from a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        words = json.load(f)
    return words

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

async def add_word(new_word: dict, file_path: str = 'data/words.json'):
    """Adds a new word to the JSON file."""
    words = load_words(file_path) # Load current words
    words.append(new_word)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(words, f, ensure_ascii=False, indent=4)

async def get_words_alphabetical(file_path: str = 'data/words.json') -> list[dict]:
    """Loads words from a JSON file and returns them sorted alphabetically by English word."""
    words = load_words(file_path)
    return sorted(words, key=lambda x: x['en'].lower())

async def delete_word(word_to_delete_en: str, file_path: str = 'data/words.json') -> bool:
    """Deletes a word from the JSON file by its English representation."""
    words = load_words(file_path)
    initial_len = len(words)
    words = [word for word in words if word['en'].lower() != word_to_delete_en.lower()]
    if len(words) < initial_len:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(words, f, ensure_ascii=False, indent=4)
        return True
    return False
