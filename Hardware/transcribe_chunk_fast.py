import json
import numpy as np
import time
import os
from queue import Queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests
import subprocess

RESPEAKER_RATE = 16000
RESPEAKER_CHANNELS = 1  
RESPEAKER_WIDTH = 2
RESPEAKER_INDEX = 5
CHUNK = 1024
RECORD_SECONDS = 7

# Create a queue to hold file paths
doa_queue = Queue()
audio_queue = Queue()

def transcribe_file(audio_file, transcription_file):
    # Use insanely-fast-whisper for transcription
    command = [
        "insanely-fast-whisper",
        "--file-name", audio_file,
        "--transcript-path", transcription_file,
        "--device-id", "0",  # Change to "mps" if using Mac with Apple Silicon
        "--flash", "True"
    ]
    subprocess.run(command, check=True)

def add_doa(doa_file, transcription_file):
    with open(transcription_file) as j:
        transcription = json.load(j)

    with open(doa_file) as d:
        doa = json.load(d)

    for seg in transcription['segments']:
        for word in seg["words"]:
            audio_time = int(word["start"])
            for dic in doa:
                doa_time = dic['record_time'] - 1
                if audio_time - doa_time < 1 and audio_time - doa_time >= 0:
                    word.update({'DOA': dic['doa']})
                    word.update({'speaker': dic['speaker']})

    with open(transcription_file, 'w') as j:
        json.dump(transcription, j)

def transcribe_and_add_doa(audio_file, doa_file, transcription_file):
    transcribe_file(audio_file, transcription_file)
    add_doa(doa_file, transcription_file)

# Define the function to execute when a new audio file is created
def on_created(event):
    global doa_file, audio_file 
    if not event.is_directory:
        file_path = event.src_path
        if file_path.endswith(".wav"):
            print(f"New audio file created: {file_path}")
            audio_file = file_path
            audio_queue.put(audio_file)
        if file_path.endswith(".json"):
            print(f"New DOA file created: {file_path}")
            doa_file = file_path
            doa_queue.put(doa_file)

def main():
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
    
    watched_directory = "chunks/"
    transcription_directory = "transcripts/"

    # Create an event handler and observer    
    event_handler = FileSystemEventHandler()
    event_handler.on_created = on_created
    observer = Observer()
    observer.schedule(event_handler, path=watched_directory, recursive=True)

    url = "http://127.0.0.1:8080/check_speakers_not_spoken"
    url2 = "http://127.0.0.1:8080/analysis"
    print(f"Watching directory: {watched_directory}")
    observer.start()
    os.environ['LAST_ITERATION'] = ""

    try:
        while True:
            if not doa_queue.empty() and not audio_queue.empty():
                audio_file = audio_queue.get()
                doa_file = doa_queue.get()
                transcription_name = os.path.splitext(os.path.basename(audio_file))[0] + '.json'
                transcription_file = os.path.join(transcription_directory, transcription_name)
                iteration = int(os.path.splitext(os.path.basename(audio_file))[0].split('_')[1])
                time.sleep(10)  # Wait until the 10 sec chunk is finished

                transcribe_and_add_doa(audio_file, doa_file, transcription_file)
                print("Transcription: " + transcription_name + " is added")
                print(f"Removed from queue: {audio_file}")
                print(f"Removed from queue: {doa_file}")
                print("New flask has been called at", iteration)

                # Call url once every 60 seconds
                if iteration % 60 == 0:
                    data = {"start_time": iteration - 15, "end_time": iteration}
                    response = requests.post(url, json=data)
                    
                # Call url2 once every 300 seconds
                if iteration % 300 == 0:
                    data2 = {"total_files": iteration}  # Use the last processed iteration
                    response2 = requests.post(url2, json=data2)
                    print("Response from url2", response2)
                    
    except KeyboardInterrupt:
        observer.stop()

    observer.join()

if __name__ == "__main__":
    main()
