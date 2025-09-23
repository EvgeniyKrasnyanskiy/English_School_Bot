import os
import datetime
import shutil

LOGS_DIR = "logs"
ARCHIVE_DIR = os.path.join(LOGS_DIR, "archive")
MAX_ARCHIVE_MONTHS = 12
LOG_FILE_NAME = "bot_errors.log"

def rotate_logs_monthly():
    """
    Rotates log files:
    1. Moves the current month's log file to an archive with a timestamp.
    2. Deletes archived logs older than MAX_ARCHIVE_MONTHS.
    """
    
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    # 1. Archive current log file if it exists and is not empty
    current_log_path = os.path.join(LOGS_DIR, LOG_FILE_NAME)
    if os.path.exists(current_log_path) and os.path.getsize(current_log_path) > 0:
        # Get the modification time of the log file to determine its month
        mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(current_log_path))
        
        # Check if the log file is from a previous month
        if mod_time.month != datetime.datetime.now().month or mod_time.year != datetime.datetime.now().year:
            timestamp = mod_time.strftime("%Y-%m")
            archive_file_name = f"bot_errors_{timestamp}.log"
            archive_path = os.path.join(ARCHIVE_DIR, archive_file_name)
            
            # Ensure unique name in case of multiple runs in the same month
            counter = 1
            original_archive_path = archive_path
            while os.path.exists(archive_path):
                archive_file_name = f"bot_errors_{timestamp}_{counter}.log"
                archive_path = os.path.join(ARCHIVE_DIR, archive_file_name)
                counter += 1

            shutil.move(current_log_path, archive_path)
            # Create a new empty log file after moving the old one
            open(current_log_path, 'a').close() 
            print(f"Archived {current_log_path} to {archive_path}")
        else:
            print(f"Log file {LOG_FILE_NAME} is from the current month, no archiving needed yet.")
    elif os.path.exists(current_log_path):
        print(f"Log file {LOG_FILE_NAME} is empty, no archiving needed.")
    else:
        print(f"Log file {LOG_FILE_NAME} not found, no archiving needed.")

    # 2. Delete old archived logs
    now = datetime.datetime.now()
    for filename in os.listdir(ARCHIVE_DIR):
        if filename.startswith("bot_errors_") and filename.endswith(".log"):
            try:
                # Extract year and month from filenames like "bot_errors_2023-10.log"
                parts = filename.replace("bot_errors_", "").replace(".log", "").split("_")
                date_part = parts[0]
                
                archive_year, archive_month = map(int, date_part.split("-"))
                archive_date = datetime.datetime(archive_year, archive_month, 1)

                # Calculate the difference in months
                # This approximation is sufficient for retaining 12 months
                months_diff = (now.year - archive_date.year) * 12 + (now.month - archive_date.month)

                if months_diff >= MAX_ARCHIVE_MONTHS:
                    file_to_delete = os.path.join(ARCHIVE_DIR, filename)
                    os.remove(file_to_delete)
                    print(f"Deleted old archived log: {file_to_delete}")
            except (ValueError, IndexError) as e:
                print(f"Could not parse date from archived log filename {filename}: {e}")

if __name__ == "__main__":
    rotate_logs_monthly()
