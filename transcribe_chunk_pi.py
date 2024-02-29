import subprocess
import sys
import os
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

def time_str_to_float(time_str):
    hours, minutes, seconds_ms = time_str.split(':')
    seconds, milliseconds = seconds_ms.split(',')
    time_float = float(hours) * 3600 + float(minutes) * 60 + float(seconds) + float(milliseconds) / 1000
    return time_float

def process_audio(wav_file, model_name):
    """
    Processes an audio file using a specified model and returns the processed string.

    :param wav_file: Path to the WAV file
    :param model_name: Name of the model to use
    :return: Processed string output from the audio processing
    :raises: Exception if an error occurs during processing
    """

    model = f"./whisper.cpp/models/ggml-{model_name}.bin"

    # Check if the file exists
    if not os.path.exists(model):
        raise FileNotFoundError(f"Model file not found: {model} \n\nDownload a model with this command:\n\n> bash ./models/download-ggml-model.sh {model_name}\n\n")

    if not os.path.exists(wav_file):
        raise FileNotFoundError(f"WAV file not found: {wav_file}")

    # full_command = f"./main -m {model} -f {wav_file} -np -nt -ml 16 -oj"
    full_command = f"./whisper.cpp/main -m {model} -f {wav_file} -np -ml 16 -oj"

    # Execute the command
    process = subprocess.Popen(full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Get the output and error (if any)
    output, error = process.communicate()

    # if error:
    #     raise Exception(f"Error processing audio: {error.decode('utf-8')}")

    # Process and return the output string
    decoded_str = output.decode('utf-8').strip()
    processed_str = decoded_str.replace('[BLANK_AUDIO]', '').strip()

    return processed_str

def transcribe_file(model, audio_file):
    result = process_audio(audio_file, model)

def add_doa(doa_file, transcription_file):
    with open(transcription_file) as j:
        transcription = json.load(j)

    with open(doa_file) as d:
        doa = json.load(d)

    for seg in transcription['transcription']:
        time_start = seg["timestamps"]["from"]
        audio_time = time_str_to_float(time_start)
        for dic in doa:
            doa_time = dic['record_time'] - 1
            if audio_time - doa_time < 1 and audio_time - doa_time >= 0:
                seg.update({'DOA': dic['doa']})
                seg.update({'speaker': dic['speaker']})

    with open(transcription_file, 'w') as j:
        json.dump(transcription, j)

def transcribe_and_add_doa(model, audio_file, doa_file, transcription_file):
    transcribe_file(model, audio_file)
    add_doa(doa_file, transcription_file)

# Define the function to execute when a new audio file is created
def on_created(event):
    global doa_file, audio_file 
    if not event.is_directory:
        file_path = event.src_path
        folder_path, file_name = os.path.split(file_path)
        if file_name.endswith(".wav"):
            print(f"New audio file created: {file_name}")
            audio_file = file_path
            audio_queue.put(audio_file)
        if file_name.endswith(".json") and file_name.startswith("DOA"):
            print(f"New DOA file created: {file_name}")
            doa_file = file_path
            doa_queue.put(doa_file)


def main():
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
    
    model = "tiny.en"
    watched_directory       = "dataset/Feb9/recorded_data"
    transcription_directory = "dataset/Feb9/recorded_data"

    # Create an event handler and observer    
    event_handler = FileSystemEventHandler()
    event_handler.on_created = on_created
    observer = Observer()
    observer.schedule(event_handler, path=watched_directory, recursive=True)

    # Start the directory observer
    print(f"Watching directory: {watched_directory}")
    observer.start()
    last_iteration = 60
    os.environ['LAST_ITERATION'] = ""
    url = "http://127.0.0.1:8080/check_speakers_not_spoken"
    url2 = "http://127.0.0.1:8080/analysis"

    try:
        while True:
            if not doa_queue.empty() and not audio_queue.empty():
                audio_file = audio_queue.get()
                doa_file = doa_queue.get()
                transcription_name = os.path.splitext(os.path.basename(audio_file))[0] + '.wav.json'
                transcription_file = os.path.join(transcription_directory, transcription_name)
                iteration = int(os.path.splitext(os.path.basename(audio_file))[0].split('_')[1])
                time.sleep(15) # Wait until the 10 sec chunk is finished

                transcribe_and_add_doa(model, audio_file, doa_file, transcription_file)
                print("Transcription: " + transcription_name + " is added")
                print(f"Removed from queue: {audio_file}")
                print(f"Removed from queue: {doa_file}")
                print("New flask has been called at", iteration)

                # Call url once every 15 seconds
                if iteration % 15 == 0:
                    data = {"start_time": iteration - 15, "end_time": iteration}
                    response = requests.post(url, json=data)
                    
                #Call url2 once every 300 seconds
                if iteration % 300 == 0:
                    data2 = {"total_files": last_iteration}  # Use the last processed iteration
                    response2 = requests.post(url2, json=data2)
                    print("Response from url2", response2)
                    break  # Exit the loop after processing all iterations

            

    except KeyboardInterrupt:
        observer.stop()

    observer.join()

if __name__ == "__main__":
    main()
