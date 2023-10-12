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

RESPEAKER_RATE = 16000
RESPEAKER_CHANNELS = 1
RESPEAKER_WIDTH = 2
RESPEAKER_INDEX = 5
CHUNK = 1024
RECORD_SECONDS = 7

def transcribe_file(audio_file, transcription_file):
    # Transcribe audio file
    model = whisper.load_model("base", device="cpu")  # choose a model (tiny, base, small, medium, and large)
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

# Define a lock for thread-safe writing to the output file
output_lock = threading.Lock()

def transcribe_and_add_doa(queue):
    while not queue.empty():
        chunk_index = queue.get()
        audio_file = 'dataset/chunk_%d.wav' % (chunk_index * 10)
        transcription_file = 'transcript_chunk_%d.json' % (chunk_index * 10)
        doa_file = 'dataset/DOA_%d.json' % (chunk_index * 10)

        # Transcribe the audio
        transcribe_file(audio_file, transcription_file)

        # Add DOA info on the transcription file
        add_doa(doa_file, transcription_file)

        with output_lock:
            print("Chunk %d is added" % (chunk_index * 10))

def get_input():
    value = input("number of chunks: ")
    return int(value)

def main():
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

    current_directory = os.getcwd()
    print("Current Directory:", current_directory)

    num_chunks = get_input()
    num_threads = 5  # Limit the number of threads to 5

    folder_path = 'dataset'
    file_list = glob.glob(os.path.join(folder_path, '*'))

    print(file_list)

    queue = Queue()

    # Populate the queue with chunk indices
    for i in range(num_chunks):
        queue.put(i)

    threads = []

    start_time = time.time()  # Record the start time

    # Create 5 threads
    for i in range(num_threads):
        thread = threading.Thread(target=transcribe_and_add_doa, args=(queue,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

    end_time = time.time()  # Record the end time
    elapsed_time = end_time - start_time

    print("Transcription is done")
    print("Total time taken:", elapsed_time, "seconds")

if __name__ == "__main__":
    main()
