import asyncio
import datetime
from utils.log_archiver import rotate_logs_monthly

async def check_and_rotate_logs():
    """
    Checks daily if it's the 1st day of the month and rotates logs.
    Runs at 4 AM every day.
    """
    while True:
        now = datetime.datetime.now()
        # Calculate time until next 4 AM
        next_run = now.replace(hour=4, minute=0, second=0, microsecond=0)
        if now.hour >= 4:
            next_run += datetime.timedelta(days=1)
        
        wait_seconds = (next_run - now).total_seconds()
        print(f"Next log rotation check scheduled for {next_run}. Waiting {wait_seconds:.0f} seconds.")
        await asyncio.sleep(wait_seconds)

        now = datetime.datetime.now() # Update `now` after sleep
        if now.day == 1:
            print(f"It's the 1st of the month ({now.strftime('%Y-%m-%d')}). Running log rotation...")
            rotate_logs_monthly()
        else:
            print(f"Today is not the 1st of the month ({now.day}). Skipping log rotation.")

async def start_background_tasks():
    asyncio.create_task(check_and_rotate_logs())
