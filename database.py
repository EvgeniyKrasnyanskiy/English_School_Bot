import aiosqlite
import datetime
from typing import Dict, Any

DATABASE_NAME = 'data/db/bot_data.db'

async def init_db():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        with open('migrations/init.sql', 'r') as f:
            sql_script = f.read()
        await db.executescript(sql_script)
        await db.commit()

        # Dynamically add new columns if they don't exist
        await _add_column_if_not_exists(db, "users", "first_name", "TEXT")
        await _add_column_if_not_exists(db, "users", "last_name", "TEXT")
        await _add_column_if_not_exists(db, "users", "username", "TEXT")
        await _add_column_if_not_exists(db, "users", "mute_until", "TEXT")
        await _add_column_if_not_exists(db, "games_stats", "word_set_name", "TEXT NOT NULL DEFAULT 'default'")
        await _add_column_if_not_exists(db, "results", "word_set_name", "TEXT NOT NULL DEFAULT 'default'")

async def _add_column_if_not_exists(db, table_name, column_name, column_type):
    cursor = await db.execute(f"PRAGMA table_info({table_name})")
    columns = await cursor.fetchall()
    column_exists = False
    for col in columns:
        if col[1] == column_name:
            column_exists = True
            break
    
    if not column_exists:
        await db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
        await db.commit()

async def add_user(user_id: int, name: str, first_name: str = None, last_name: str = None, username: str = None):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        registered_at = datetime.datetime.now().isoformat()
        last_active = registered_at
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, name, registered_at, last_active, first_name, last_name, username) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, name, registered_at, last_active, first_name, last_name, username)
        )
        await db.execute("INSERT OR IGNORE INTO user_data (user_id) VALUES (?) ", (user_id,))
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        return dict(user) if user else None

async def update_user_profile_data(user_id: int, name: str, first_name: str = None, last_name: str = None, username: str = None):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE users SET name = ?, first_name = ?, last_name = ?, username = ? WHERE user_id = ?",
            (name, first_name, last_name, username, user_id)
        )
        await db.commit()

async def update_last_active(user_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        last_active = datetime.datetime.now().isoformat()
        await db.execute(
            "UPDATE users SET last_active = ? WHERE user_id = ?",
            (last_active, user_id)
        )
        await db.commit()

async def save_test_result(user_id: int, score: int, total: int, word_set_name: str = "default"):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        date = datetime.datetime.now().isoformat()
        await db.execute(
            "INSERT INTO results (user_id, score, total, date, word_set_name) VALUES (?, ?, ?, ?, ?)",
            (user_id, score, total, date, word_set_name)
        )
        # Update best_test_score in user_data if current score is better
        await db.execute(
            "INSERT INTO user_data (user_id, best_test_score) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET best_test_score = MAX(excluded.best_test_score, user_data.best_test_score)",
            (user_id, score)
        )
        await db.commit()

async def get_user_stats(user_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        
        # Total correct answers
        cursor_total_correct = await db.execute(
            "SELECT SUM(score) FROM results WHERE user_id = ?", (user_id,)
        )
        total_correct = (await cursor_total_correct.fetchone())[0] or 0

        # Best test score
        cursor_best_score = await db.execute(
            "SELECT MAX(score) FROM results WHERE user_id = ?", (user_id,)
        )
        best_score = (await cursor_best_score.fetchone())[0] or 0

        # Last activity date (from users table)
        cursor_last_active = await db.execute(
            "SELECT last_active FROM users WHERE user_id = ?", (user_id,)
        )
        last_active_raw = (await cursor_last_active.fetchone())
        last_active = last_active_raw[0] if last_active_raw else "N/A"

        # Get best_test_time from user_data table
        cursor_best_test_time = await db.execute("SELECT best_test_time FROM user_data WHERE user_id = ?", (user_id,))
        best_test_time_raw = (await cursor_best_test_time.fetchone())
        best_test_time = best_test_time_raw[0] if best_test_time_raw else float('inf')

        # Get games_stats
        cursor_games_stats = await db.execute("SELECT game_type, played, correct, incorrect, best_time FROM games_stats WHERE user_id = ?", (user_id,))
        games_stats_rows = await cursor_games_stats.fetchall()
        games_stats = {
            row['game_type']: {
                'played': row['played'],
                'correct': row['correct'],
                'incorrect': row['incorrect'],
                'best_time': row['best_time']
            } for row in games_stats_rows
        }
        
        return {
            "total_correct_answers": total_correct,
            "best_test_score": best_score,
            "last_activity_date": last_active,
            "best_test_time": best_test_time,
            "games_stats": games_stats
        }

async def delete_user_from_db(user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Delete from results table
        await db.execute("DELETE FROM results WHERE user_id = ?", (user_id,))
        # Delete from games_stats table
        await db.execute("DELETE FROM games_stats WHERE user_id = ?", (user_id,))
        # Delete from user_data table
        await db.execute("DELETE FROM user_data WHERE user_id = ?", (user_id,))
        # Delete from banned_users table
        await db.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
        # Delete from users table
        cursor = await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()
        return cursor.rowcount > 0 # Returns True if any row was deleted

async def reset_all_user_statistics() -> bool:
    """Сбрасывает всю статистику пользователей, связанную с рейтингом и тестами."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        try:
            # Обнуляем best_test_score и best_test_time в user_data для всех пользователей
            await db.execute("UPDATE user_data SET best_test_score = 0, best_test_time = ?", (float('inf'),))
            # Удаляем все записи из таблицы результатов тестов
            await db.execute("DELETE FROM results")
            # Удаляем все записи из таблицы статистики игр
            await db.execute("DELETE FROM games_stats")
            await db.commit()
            return True
        except Exception as e:
            print(f"Error resetting all user statistics: {e}")
            return False


async def update_user_best_test_time(user_id: int, best_test_time: float):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE user_data SET best_test_time = ? WHERE user_id = ?",
            (best_test_time, user_id)
        )
        await db.commit()

async def get_all_users_for_ranking() -> list[Dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT
                u.user_id,
                u.name AS registered_name,
                u.first_name,
                u.last_name,
                u.username,
                ud.best_test_time,
                ud.best_test_score,
                SUM(r.score) AS total_correct_answers,
                u.last_active
            FROM users u
            LEFT JOIN user_data ud ON u.user_id = ud.user_id
            LEFT JOIN results r ON u.user_id = r.user_id
            GROUP BY u.user_id
        """)
        users_data = await cursor.fetchall()

        result = []
        for user_row in users_data:
            user_dict = dict(user_row)
            # Get games stats for each user
            games_cursor = await db.execute("SELECT game_type, played, correct, incorrect, best_time FROM games_stats WHERE user_id = ?", (user_dict['user_id'],))
            games_stats_rows = await games_cursor.fetchall()
            user_dict['games_stats'] = {
                row['game_type']: {
                    'played': row['played'],
                    'correct': row['correct'],
                    'incorrect': row['incorrect'],
                    'best_time': row['best_time']
                } for row in games_stats_rows
            }
            result.append(user_dict)
        return result

async def update_game_stats(user_id: int, game_type: str, is_correct: bool, last_activity_date: str, time_taken: float = None, word_set_name: str = "default"):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Update last activity in users table
        await db.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (last_activity_date, user_id))

        # Get current game stats
        cursor = await db.execute("SELECT played, correct, incorrect, best_time FROM games_stats WHERE user_id = ? AND game_type = ? AND word_set_name = ?", (user_id, game_type, word_set_name))
        game_data = await cursor.fetchone()

        played = game_data[0] if game_data else 0
        correct = game_data[1] if game_data else 0
        incorrect = game_data[2] if game_data else 0
        current_best_time = game_data[3] if game_data and game_data[3] is not None else float('inf')

        played += 1
        if is_correct:
            correct += 1
        else:
            incorrect += 1

        if game_type == "recall_typing" and time_taken is not None and time_taken < current_best_time:
            current_best_time = time_taken
        elif game_type != "recall_typing":
            current_best_time = None # Ensure best_time is None for other game types

        if game_data:
            await db.execute(
                "UPDATE games_stats SET played = ?, correct = ?, incorrect = ?, best_time = ? WHERE user_id = ? AND game_type = ? AND word_set_name = ?",
                (played, correct, incorrect, current_best_time, user_id, game_type, word_set_name)
            )
        else:
            await db.execute(
                "INSERT INTO games_stats (user_id, game_type, word_set_name, played, correct, incorrect, best_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, game_type, word_set_name, played, correct, incorrect, current_best_time)
            )
        await db.commit()

async def get_game_stats_by_word_set(user_id: int) -> dict[str, dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT game_type, word_set_name, played, correct, incorrect, best_time FROM games_stats WHERE user_id = ?", (user_id,))
        rows = await cursor.fetchall()
        
        stats_by_set = {}
        for row in rows:
            word_set = row['word_set_name']
            game_type = row['game_type']
            if word_set not in stats_by_set:
                stats_by_set[word_set] = {}
            stats_by_set[word_set][game_type] = {
                'played': row['played'],
                'correct': row['correct'],
                'incorrect': row['incorrect'],
                'best_time': row['best_time']
            }
        return stats_by_set

async def get_test_stats_by_word_set(user_id: int) -> dict[str, dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT 
                word_set_name, 
                COUNT(id) AS total_tests,
                SUM(score) AS total_score,
                SUM(total) AS total_possible_score,
                MAX(score) AS best_score
            FROM results 
            WHERE user_id = ?
            GROUP BY word_set_name
            """,
            (user_id,)
        )
        rows = await cursor.fetchall()
        
        stats_by_set = {}
        for row in rows:
            word_set = row['word_set_name']
            stats_by_set[word_set] = {
                'total_tests': row['total_tests'],
                'total_score': row['total_score'],
                'total_possible_score': row['total_possible_score'],
                'best_score': row['best_score']
            }
        return stats_by_set

async def get_banned_users() -> list[int]:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM banned_users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def add_banned_user(user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        try:
            await db.execute("INSERT INTO banned_users (user_id) VALUES (?) ", (user_id,))
            await db.commit()
            return True
        except aiosqlite.IntegrityError: # User might already be banned
            return False

async def remove_banned_user(user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
        await db.commit()
        return cursor.rowcount > 0

async def get_all_users():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        # Retrieve all relevant user information including first_name, last_name, username
        cursor = await db.execute("SELECT user_id, name, first_name, last_name, username FROM users")
        users = await cursor.fetchall()
        return [dict(user) for user in users]

async def get_user_display_name(user_id: int) -> str:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT name, first_name, last_name, username FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()

        if not user:
            return "Пользователь"

        first_name = user['first_name'] or ''
        last_name = user['last_name'] or ''
        username = user['username'] or ''
        bot_name = user['name'] or ''

        full_name = f"{first_name} {last_name}".strip()

        if full_name:
            return full_name
        elif username:
            return username
        elif bot_name:
            return bot_name
        else:
            return "Пользователь"

async def mute_user(user_id: int, hours: float | None) -> bool:
    """Mutes a user for a specified number of hours, or permanently if hours is None."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if hours is None:
            mute_until = "9999-12-31T23:59:59"
        else:
            mute_until = (datetime.datetime.now() + datetime.timedelta(hours=hours)).isoformat()
        
        try:
            await db.execute("UPDATE users SET mute_until = ? WHERE user_id = ?", (mute_until, user_id))
            await db.commit()
            return True
        except Exception as e:
            print(f"Error muting user {user_id}: {e}")
            return False

async def unmute_user(user_id: int) -> bool:
    """Unmutes a user."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        try:
            await db.execute("UPDATE users SET mute_until = NULL WHERE user_id = ?", (user_id,))
            await db.commit()
            return True
        except Exception as e:
            print(f"Error unmuting user {user_id}: {e}")
            return False

async def get_user_mute_status(user_id: int) -> datetime.datetime | None:
    """Returns the datetime until which the user is muted, or None if not muted."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT mute_until FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        
        if row and row['mute_until']:
            try:
                mute_until = datetime.datetime.fromisoformat(row['mute_until'])
                if mute_until > datetime.datetime.now():
                    return mute_until
            except ValueError:
                pass
        
        return None