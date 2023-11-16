import json
import usb.core
import usb.util
import pyaudio
import wave
import numpy as np
from tuning import Tuning
import time
import os
import whisper_timestamped as whisper
import glob
import threading
from queue import Queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests


RESPEAKER_RATE = 16000
RESPEAKER_CHANNELS = 1
RESPEAKER_WIDTH = 2
RESPEAKER_INDEX = 5
CHUNK = 1024
RECORD_SECONDS = 7
# Create a queue to hold file paths
doa_queue = Queue()
audio_queue = Queue()

def transcribe_file(model, audio_file, transcription_file):
    # Transcribe audio file
    result = whisper.transcribe(model, audio_file, language="En")
    with open(transcription_file, 'w') as t:
        json.dump(result, t)

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

def transcribe_and_add_doa(model, audio_file, doa_file, transcription_file):
    transcribe_file(model, audio_file, transcription_file)
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
    
    # Load whisper model
    model = whisper.load_model("base", device="cpu")  # choose a model (tiny, base, small, medium, and large)

    watched_directory       = "dataset/Nov1/recorded_data"
    transcription_directory = "dataset/Nov1/transcription"

    # Create an event handler and observer    
    event_handler = FileSystemEventHandler()
    event_handler.on_created = on_created
    observer = Observer()
    observer.schedule(event_handler, path=watched_directory, recursive=True)

    # Start the directory observer
    print(f"Watching directory: {watched_directory}")
    observer.start()

    try:
        while True:
            if not doa_queue.empty() and not audio_queue.empty():
                audio_file = audio_queue.get()
                doa_file = doa_queue.get()
                transcription_name = os.path.splitext(os.path.basename(audio_file))[0] + '.json'
                transcription_file = os.path.join(transcription_directory, transcription_name)
                iteration = int(os.path.splitext(os.path.basename(audio_file))[0].split('_')[1])
                time.sleep(10) # Wait until the 10 sec chunk is finished

                transcribe_and_add_doa(model, audio_file, doa_file, transcription_file)
                print("Transcription: " + transcription_name + " is added")
                print(f"Removed from queue: {audio_file}")
                print(f"Removed from queue: {doa_file}")

                url = "http://127.0.0.1:8080/check_speakers_not_spoken"
                url2 = "http://127.0.0.1:8080/analysis"
                # Define the data you want to send in the POST request (as a dictionary)
                if iteration >= 60 and iteration % 30 == 0:
                    data = {
                        "start_time": iteration - 60, 
                        "end_time":  iteration
                            }
                    data2 = {
                    "total_files": iteration, #x here is the total number of chunks we have generated. So if we have our last file x_550.json then we have total 55 files
        }
                    # Make the POST request
                    response = requests.post(url, json=data)
                    response2 = requests.post(url2, json=data2)

            

    except KeyboardInterrupt:
        observer.stop()

    observer.join()

if __name__ == "__main__":
    main()
