import aiosqlite
import datetime

DATABASE_NAME = 'bot_data.db'

async def init_db():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        with open('migrations/init.sql', 'r') as f:
            sql_script = f.read()
        await db.executescript(sql_script)
        await db.commit()

async def add_user(user_id: int, name: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        registered_at = datetime.datetime.now().isoformat()
        last_active = registered_at
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, name, registered_at, last_active) VALUES (?, ?, ?, ?)",
            (user_id, name, registered_at, last_active)
        )
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        return dict(user) if user else None

async def update_last_active(user_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        last_active = datetime.datetime.now().isoformat()
        await db.execute(
            "UPDATE users SET last_active = ? WHERE user_id = ?",
            (last_active, user_id)
        )
        await db.commit()

async def save_test_result(user_id: int, score: int, total: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        date = datetime.datetime.now().isoformat()
        await db.execute(
            "INSERT INTO results (user_id, score, total, date) VALUES (?, ?, ?, ?)",
            (user_id, score, total, date)
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
        
        return {
            "total_correct_answers": total_correct,
            "best_test_score": best_score,
            "last_activity_date": last_active
        }

async def delete_user_from_db(user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Delete from results table
        await db.execute("DELETE FROM results WHERE user_id = ?", (user_id,))
        # Delete from users table
        cursor = await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()
        return cursor.rowcount > 0 # Returns True if any row was deleted