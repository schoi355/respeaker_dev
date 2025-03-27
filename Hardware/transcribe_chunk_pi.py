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
import glob
import threading
from queue import Queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests
import sys
import argparse
import boto3
import time
from datetime import datetime


RESPEAKER_RATE = 16000
RESPEAKER_CHANNELS = 1
RESPEAKER_WIDTH = 2
RESPEAKER_INDEX = 5
CHUNK = 1024
RECORD_SECONDS = 15

CHUNKSIZE = 15
AWS_ACCESS_KEY_ID = 'AKIA5ILC25FLKQPPTOEB'
AWS_SECRET_ACCESS_KEY = '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'
AWS_REGION = 'us-east-2'
S3_BUCKET_NAME = 'respeaker-recordings'

# Create a queue to hold file paths
doa_queue = Queue()
audio_queue = Queue()

s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

def upload_to_s3(local_file_path, s3_path):
    try:
        s3.upload_file(local_file_path, S3_BUCKET_NAME, s3_path)
        print(f'Successfully uploaded {local_file_path} to {s3_path}')
    except Exception as e:
        print(f'Error uploading {local_file_path} to {s3_path}: {e}')

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

    model = f"../whisper.cpp/models/ggml-{model_name}.bin"

    # Check if the file exists
    if not os.path.exists(model):
        raise FileNotFoundError(f"Model file not found: {model} \n\nDownload a model with this command:\n\n> bash ./models/download-ggml-model.sh {model_name}\n\n")

    if not os.path.exists(wav_file):
        raise FileNotFoundError(f"WAV file not found: {wav_file}")

    # full_command = f"./main -m {model} -f {wav_file} -np -nt -ml 16 -oj"
    full_command = f"../whisper.cpp/main -m {model} -f {wav_file} -np -ml 16 -oj"

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

def wait_until_written(file_path, timeout):
    last_size = -1
    while timeout > 0:
        current_size = os.path.getsize(file_path)
        if current_size == last_size:
            break
        time.sleep(1)
        timeout -= 1

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

def word_to_num(word):
    mapping = {
        '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
        '6': 6, '7': 7, '8': 8, '9': 9, '10': 10
    }
    return mapping.get(word.lower(), 0)


def main():
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
    parser = argparse.ArgumentParser(description="directory")
    parser.add_argument("-d", "--directory", required=True, help="directory that will contain the dataset")
    args = parser.parse_args()
    dir_name = args.directory

    dir_path = dir_name+'/recorded_data/'

    if os.path.exists(dir_path) and os.path.isdir(dir_path):
        print("The directory path is: " + dir_path)
    else:
        print("The directory does not exist. Create a directory and try again")
    
    model = "tiny.en"
    watched_directory = dir_path

    # Create an event handler and observer    
    event_handler = FileSystemEventHandler()
    event_handler.on_created = on_created
    observer = Observer()
    observer.schedule(event_handler, path=watched_directory, recursive=True)

    setup_url = "http://127.0.0.1:8000/initial_setup"
    csns_url = "http://127.0.0.1:8000/check_speakers_not_spoken"
    analysis_url = "http://127.0.0.1:8000/analysis"
    emotion_url = "http://127.0.0.1:8000/emotion_check"
    topic_url = "http://127.0.0.1:8000/topic_detection"
    transcript_url = "http://127.0.0.1:8000/append_transcript"

    print(f"Watching directory: {watched_directory}")
    observer.start()
    os.environ['LAST_ITERATION'] = ""

    # ******************************************************* SET BEFORE TRIAL ***********************************
    date_folder = datetime.now().strftime('%Y-%m-%d')
    PROJECT_NO = 1
    CLASS_NO = 1
    PI_ID = 1
    TRIAL_NO = str(dir_name)[-1]
    # ************************************************************************************************************
    time.sleep(10)
    response = requests.post(setup_url, json={
        "PROJECT_NO": PROJECT_NO,
        "CLASS_NO": CLASS_NO,
        "TRIAL_NO": TRIAL_NO,
        "PI_ID": PI_ID
    })
    print(response.text)


    try:
        while True:
            if not doa_queue.empty() and not audio_queue.empty():
                audio_file = audio_queue.get()
                doa_file = doa_queue.get()
                print("ERRRROR", os.path.splitext(os.path.basename(audio_file)))
                transcription_name = os.path.splitext(os.path.basename(audio_file))[0] + '.wav.json'
                transcription_file = os.path.join(watched_directory, transcription_name)
                iteration = int(os.path.splitext(os.path.basename(audio_file))[0].split('_')[1])
                
                if doa_queue.qsize() < 1:
                    time.sleep(15)
                    print("Waiting for the audio/doa coming")

                ID_file  = dir_name + '/assign_speaker/ID.json'
                with open(ID_file, 'r') as f:
                    ID_data = json.load(f)
                    # Convert word-based numeric IDs to integers and sort them
                    numeric_ids = sorted([word_to_num(info['ID'][0]) for info in ID_data.values()])
                    filtered_numeric_ids = list(filter(lambda x: x!= 0, numeric_ids))
                    id_str = '_'.join(map(str, filtered_numeric_ids))

                transcribe_and_add_doa(model, audio_file, doa_file, transcription_file)
                print("Transcription: " + transcription_name + " is added")
                print(f"Removed from queue: {audio_file}")
                print(f"Removed from queue: {doa_file}")
                print("New flask has been called at", iteration)

                transcription_s3_path = f'Project_{PROJECT_NO}/Class_{CLASS_NO}/{date_folder}/Pi_{PI_ID}/Trial_{TRIAL_NO}/transcription-files/{id_str}/{transcription_name}'
                upload_to_s3(transcription_file, transcription_s3_path)

                # Call url once every 60 seconds
                if iteration >= 120 and iteration % 60 == 0:
                    data = {"start_time": iteration - 120, "end_time": iteration}
                    response = requests.post(csns_url, json=data)
                    time.sleep(2)
                    response2 = requests.post(analysis_url, json=data)
                    print("Response from url2", response2)
                    time.sleep(5)
                    response3 = requests.post(emotion_url, json=data)
                    print("Response from url3", response3)
                    time.sleep(5)
                    response5 = requests.post(topic_url, json=data)
                    print("Response from url5", response5)

                if iteration >= 60 and iteration % 60 == 0:
                    data = {"start_time": iteration - 60, "end_time": iteration}
                    response = requests.post(transcript_url, json=data)
                    
    
        
    except KeyboardInterrupt:
        observer.stop()

    observer.join()

if __name__ == "__main__":
    main()
