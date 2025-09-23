import os
import aiofiles
from typing import Dict, Any
import logging

import database

logger = logging.getLogger(__name__)

async def update_user_profile_data(user_id: str,
                                   registered_name: str,
                                   first_name: str = None,
                                   last_name: str = None,
                                   username: str = None):
    user_id_int = int(user_id) # Ensure user_id is integer for database operations
    await database.update_user_profile_data(user_id_int, registered_name, first_name, last_name, username)

async def calculate_overall_score_and_rank() -> list[Dict[str, Any]]:
    all_users_data = await database.get_all_users_for_ranking()
    user_scores = []

    for user_data in all_users_data:
        user_id = user_data['user_id']
        total_correct_answers = user_data.get('total_correct_answers', 0) or 0
        best_test_score = user_data.get('best_test_score', 0) or 0
        
        total_game_correct = 0
        if 'games_stats' in user_data:
            for game_type, game_data in user_data['games_stats'].items():
                total_game_correct += game_data.get('correct', 0)
        
        # Define the scoring mechanism
        # Example: total_correct_answers + (correct_game_answers * 0.5) + best_test_score
        overall_score = total_correct_answers + (total_game_correct * 0.5) + best_test_score

        # Add bonus for best time in 'recall_typing' game
        if 'games_stats' in user_data and "recall_typing" in user_data['games_stats']:
            recall_typing_stats = user_data['games_stats']["recall_typing"]
            if 'best_time' in recall_typing_stats and recall_typing_stats['best_time'] is not None and recall_typing_stats['best_time'] > 0:
                time_bonus_multiplier = 100 # Adjust this value to change the impact of time
                overall_score += (1 / recall_typing_stats['best_time']) * time_bonus_multiplier
        
        user_scores.append({
            'user_id': user_id,
            'overall_score': overall_score,
            'registered_name': user_data.get('registered_name'),
            'first_name': user_data.get('first_name'),
            'last_name': user_data.get('last_name'),
            'username': user_data.get('username'),
            'total_correct_answers': total_correct_answers,
            'best_test_score': best_test_score,
            'best_test_time': user_data.get('best_test_time', float('inf')),
            'last_activity_date': user_data.get('last_active', 'N/A')
        })

    # Sort users by overall score in descending order
    user_scores.sort(key=lambda x: x['overall_score'], reverse=True)

    # Assign ranks
    for i, user_score_entry in enumerate(user_scores):
        user_score_entry['rank'] = i + 1
    
    return user_scores

async def delete_user_stats_entry(user_id: str) -> bool:
    return await database.delete_user_from_db(int(user_id))

async def update_game_stats(user_id: str, game_type: str, is_correct: bool, last_activity_date: str, time_taken: float = None, word_set_name: str = "default"):
    user_id_int = int(user_id)
    await database.update_game_stats(user_id_int, game_type, is_correct, last_activity_date, time_taken, word_set_name)

async def get_banned_users() -> list[int]:
    return await database.get_banned_users()

async def add_banned_user(user_id: int) -> bool:
    return await database.add_banned_user(user_id)

async def remove_banned_user(user_id: int) -> bool:
    return await database.remove_banned_user(user_id)

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