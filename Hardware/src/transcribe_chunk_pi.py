import subprocess
import os
import json
import time
from queue import Queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests
import sys
import argparse
import boto3
from datetime import datetime

RESPEAKER_RATE = 16000
RESPEAKER_CHANNELS = 1
RESPEAKER_WIDTH = 2
RESPEAKER_INDEX = 5
CHUNK = 1024
RECORD_SECONDS = 15
CHUNKSIZE = 15

def read_cfg(file_path):
    config = {}
    
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"): 
                continue            
            if '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip().strip("'\"") 
    return config

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HARDWARE_DIR = os.path.dirname(SCRIPT_DIR)

cfg_path = os.path.join(HARDWARE_DIR, "application.cfg")
config = read_cfg(cfg_path)
AWS_ACCESS_KEY_ID = config.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = config.get('AWS_SECRET_ACCESS_KEY')
AWS_REGION = config.get('AWS_REGION')
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

    model = HARDWARE_DIR + f"/whisper.cpp/models/ggml-{model_name}.bin"

    # Check if the file exists
    if not os.path.exists(model):
        raise FileNotFoundError(f"Model file not found: {model} \n\nDownload a model with this command:\n\n> bash ./models/download-ggml-model.sh {model_name}\n\n")

    if not os.path.exists(wav_file):
        raise FileNotFoundError(f"WAV file not found: {wav_file}")

    # full_command = f"./main -m {model} -f {wav_file} -np -nt -ml 16 -oj"
    full_command = HARDWARE_DIR + f"/whisper.cpp/main -m {model} -f {wav_file} -np -ml 16 -oj"

    # Execute the command
    process = subprocess.Popen(full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Get the output and error (if any)
    output, error = process.communicate()

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

    # url = "http://3.131.78.98:8080/check_speakers_not_spoken"
    # url2 = "http://3.131.78.98:8080/analysis"
    url = "http://127.0.0.1:8080/check_speakers_not_spoken"
    url2 = "http://127.0.0.1:8080/analysis"
    # url3 = "http://127.0.0.1:8080/word_concatenations"
    # url4 = "http://127.0.0.1:8080/emotion_check"
    print(f"Watching directory: {watched_directory}")
    observer.start()
    os.environ['LAST_ITERATION'] = ""

    try:
        while True:
            if not doa_queue.empty() and not audio_queue.empty():
                audio_file = audio_queue.get()
                doa_file = doa_queue.get()
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

                date_folder = datetime.now().strftime('%Y-%m-%d')
                trial = str(dir_name)[-1]   
                transcription_s3_path = f'trials/{date_folder}/{trial}/transcription-files/{id_str}/{transcription_name}'

                upload_to_s3(transcription_file, transcription_s3_path)

                # Call url once every 60 seconds
                if iteration % 60 == 0:
                    data = {"start_time": iteration - 30, "end_time": iteration}
                    response = requests.post(url, json=data)
                    
                #Call url2 once every 300 seconds
                if iteration % 300:
                    data2 = {"total_files": iteration}  # Use the last processed iteration
                    response2 = requests.post(url2, json=data2)
                    print("Response from url2", response2)

                # data3 = {"current_iteration": iteration}
                # response3 = requests.post(url3, json=data3)

                # # Call url4 after EVERY chunk once there are 4 existing chunks
                # if iteration >= (RECORD_SECONDS * 4):
                #     data4 = {"current_iteration": iteration}
                #     response4 = requests.post(url4, json=data4)
        
    except KeyboardInterrupt:
        observer.stop()

    observer.join()

if __name__ == "__main__":
    main()
