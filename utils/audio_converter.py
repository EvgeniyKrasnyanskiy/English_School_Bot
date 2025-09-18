import os
import asyncio
import subprocess

async def convert_ogg_to_mp3():
    ffmpeg_exe_path = r"C:\ffmpeg\bin\ffmpeg.exe"
    ogg_dir = "data/sounds"

    if not os.path.exists(ogg_dir):
        print(f"Directory {ogg_dir} does not exist. Skipping OGG to MP3 conversion.")
        return

    # Check if ffmpeg.exe exists before proceeding
    if not os.path.exists(ffmpeg_exe_path):
        print(f"Error: ffmpeg.exe not found at {ffmpeg_exe_path}. Cannot convert audio.")
        return

    print(f"Checking {ogg_dir} for OGG files to convert to MP3 using ffmpeg...")
    for filename in os.listdir(ogg_dir):
        if filename.endswith(".ogg"):
            ogg_filepath = os.path.join(ogg_dir, filename)
            mp3_filename = filename.replace(".ogg", ".mp3")
            mp3_filepath = os.path.join(ogg_dir, mp3_filename)

            if os.path.exists(mp3_filepath):
                print(f"MP3 already exists for {filename}. Skipping conversion.")
                continue

            print(f"Converting {filename} to {mp3_filename}...")
            try:
                # Use subprocess to run ffmpeg command
                command = [
                    ffmpeg_exe_path,
                    "-i", ogg_filepath,
                    "-acodec", "libmp3lame",
                    "-q:a", "2",
                    mp3_filepath
                ]
                # Run the command in a separate thread to avoid blocking asyncio event loop
                await asyncio.to_thread(lambda: subprocess.run(command, check=True, capture_output=True))
                print(f"Successfully converted {filename} to {mp3_filename}")
            except subprocess.CalledProcessError as e:
                print(f"Error converting {filename}: {e}\nStderr: {e.stderr.decode()}")
            except FileNotFoundError:
                print(f"Error: ffmpeg.exe not found at {ffmpeg_exe_path}. This should not happen.")
            except Exception as e:
                print(f"An unexpected error occurred while converting {filename}: {e}")
