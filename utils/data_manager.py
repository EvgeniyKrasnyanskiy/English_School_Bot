import json
import os
import aiofiles
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

STATS_FILE = "data/stats.json"

async def load_stats() -> Dict[str, Any]:
    logger.debug(f"[load_stats] Attempting to load stats from {STATS_FILE}")
    if not os.path.exists(STATS_FILE):
        logger.info(f"[load_stats] {STATS_FILE} not found. Returning empty dict.")
        return {}
    async with aiofiles.open(STATS_FILE, 'r') as f:
        content = await f.read()
        if not content.strip(): # Check if content is empty or only whitespace
            logger.warning(f"[load_stats] {STATS_FILE} is empty or contains only whitespace. Returning empty dict.")
            return {} # Return empty dict if file is empty
        try:
            loaded_stats = json.loads(content)
            logger.debug(f"[load_stats] Successfully loaded stats: {loaded_stats}")
            return loaded_stats
        except json.JSONDecodeError as e:
            logger.error(f"[load_stats] Error decoding JSON from {STATS_FILE}: {e}. Content: {content[:200]}...")
            return {}

async def save_stats(stats: Dict[str, Any]):
    logger.debug(f"[save_stats] Attempting to save stats to {STATS_FILE}. Data: {stats}")
    os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
    async with aiofiles.open(STATS_FILE, 'w') as f:
        await f.write(json.dumps(stats, indent=4))
    logger.debug(f"[save_stats] Successfully saved stats to {STATS_FILE}")

async def update_user_profile_data(user_id: str,
                                   registered_name: str,
                                   first_name: str = None,
                                   last_name: str = None,
                                   username: str = None):
    user_id = str(user_id) # Ensure user_id is string
    all_stats = await load_stats()
    user_stats = all_stats.get(user_id, {})

    user_stats['registered_name'] = registered_name
    user_stats['first_name'] = first_name or '' # Ensure it's an empty string, not None
    user_stats['last_name'] = last_name or ''   # Ensure it's an empty string, not None
    user_stats['username'] = username or ''     # Ensure it's an empty string, not None
    
    all_stats[user_id] = user_stats
    await save_stats(all_stats)

async def calculate_overall_score_and_rank() -> list[Dict[str, Any]]:
    all_stats = await load_stats()
    user_scores = []

    for user_id, stats in all_stats.items():
        if not isinstance(stats, dict):
            logging.warning(f"[calculate_overall_score_and_rank] Skipping invalid stats entry for user {user_id}: Expected dict, got {type(stats)}")
            continue

        total_correct_answers = stats.get('total_correct_answers', 0)
        best_test_score = stats.get('best_test_score', 0)
        
        total_game_correct = 0
        if 'games_stats' in stats:
            for game_type, game_data in stats['games_stats'].items():
                total_game_correct += game_data.get('correct', 0)
        
        # Define the scoring mechanism
        # Example: total_correct_answers + (correct_game_answers * 0.5) + best_test_score
        overall_score = total_correct_answers + (total_game_correct * 0.5) + best_test_score

        # Add bonus for best time in 'recall_typing' game
        if 'games_stats' in stats and "recall_typing" in stats['games_stats']:
            recall_typing_stats = stats['games_stats']["recall_typing"]
            if 'best_time' in recall_typing_stats and recall_typing_stats['best_time'] is not None and recall_typing_stats['best_time'] > 0:
                time_bonus_multiplier = 100 # Adjust this value to change the impact of time
                overall_score += (1 / recall_typing_stats['best_time']) * time_bonus_multiplier
        
        user_scores.append({
            'user_id': user_id,
            'overall_score': overall_score,
            'stats': stats, # Include original stats for potential future use
            'registered_name': stats.get('registered_name'),
            'first_name': stats.get('first_name'),
            'last_name': stats.get('last_name'),
            'username': stats.get('username')
        })

    # Sort users by overall score in descending order
    user_scores.sort(key=lambda x: x['overall_score'], reverse=True)

    # Assign ranks
    for i, user_score_entry in enumerate(user_scores):
        user_score_entry['rank'] = i + 1
    
    return user_scores

async def update_user_stats(user_id: str, total_correct_answers: int, best_test_score: int, last_activity_date: str, best_test_time: float):
    user_id = str(user_id) # Ensure user_id is string
    all_stats = await load_stats()
    user_stats = all_stats.get(user_id, {})
    user_stats['total_correct_answers'] = total_correct_answers
    user_stats['best_test_score'] = best_test_score
    user_stats['last_activity_date'] = last_activity_date
    user_stats['best_test_time'] = best_test_time # Сохраняем лучшее время теста
    all_stats[user_id] = user_stats
    await save_stats(all_stats)

async def delete_user_stats_entry(user_id: str) -> bool:
    all_stats = await load_stats()
    if user_id in all_stats:
        del all_stats[user_id]
        await save_stats(all_stats)
        return True
    return False

async def update_game_stats(user_id: str, game_type: str, is_correct: bool, last_activity_date: str, time_taken: float = None):
    user_id = str(user_id) # Ensure user_id is string
    all_stats = await load_stats()
    user_stats = all_stats.get(user_id, {})

    if 'games_stats' not in user_stats:
        user_stats['games_stats'] = {}

    if game_type not in user_stats['games_stats']:
        user_stats['games_stats'][game_type] = {
            'played': 0,
            'correct': 0,
            'incorrect': 0
        }
        if game_type == "recall_typing":
            user_stats['games_stats'][game_type]['best_time'] = float('inf')

    if game_type == "recall_typing":
        # Ensure best_time is initialized before comparison, even if game_type existed previously
        if user_stats['games_stats'][game_type].get('best_time') is None:
            user_stats['games_stats'][game_type]['best_time'] = float('inf')

        if time_taken is not None and time_taken < user_stats['games_stats'][game_type]['best_time']:
            user_stats['games_stats'][game_type]['best_time'] = time_taken

    user_stats['games_stats'][game_type]['played'] += 1
    if is_correct:
        user_stats['games_stats'][game_type]['correct'] += 1
    else:
        user_stats['games_stats'][game_type]['incorrect'] += 1
    
    user_stats['last_activity_date'] = last_activity_date
    all_stats[user_id] = user_stats
    await save_stats(all_stats)

async def get_banned_users() -> list[int]:
    all_stats = await load_stats()
    return [int(user_id) for user_id in all_stats.get('banned_users', [])]

async def add_banned_user(user_id: int) -> bool:
    all_stats = await load_stats()
    banned_users = all_stats.get('banned_users', [])
    user_id_str = str(user_id)
    if user_id_str not in banned_users:
        banned_users.append(user_id_str)
        all_stats['banned_users'] = banned_users
        await save_stats(all_stats)
        return True
    return False

async def remove_banned_user(user_id: int) -> bool:
    all_stats = await load_stats()
    banned_users = all_stats.get('banned_users', [])
    user_id_str = str(user_id)
    if user_id_str in banned_users:
        banned_users.remove(user_id_str)
        all_stats['banned_users'] = banned_users
        await save_stats(all_stats)
        return True
    return False

IMAGE_DIR = "data/images"
SOUNDS_DIR = "data/sounds"

async def get_image_filepath(word: str):
    # Supported image extensions (add more if needed)
    for ext in ['.png', '.jpg', '.jpeg', '.gif']:
        filepath = os.path.join(IMAGE_DIR, f"{word.lower()}{ext}")
        if os.path.exists(filepath):
            return filepath
    return None

async def get_audio_filepath(word: str):
    # Supported audio extensions (add more if needed)
    for ext in ['.mp3', '.ogg', '.wav']:
        filepath = os.path.join(SOUNDS_DIR, f"{word.lower()}{ext}")
        if os.path.exists(filepath):
            return filepath
    return None