import json
import usb.core
import usb.util
import pyaudio
import wave
import numpy as np
from tuning import Tuning
import time
import os
import subprocess



RESPEAKER_RATE = 16000
RESPEAKER_CHANNELS = 1 # change base on firmwares, 1_channel_firmware.bin as 1 or 6_channels_firmware.bin as 6
RESPEAKER_WIDTH = 2
# run getDeviceInfo.py to get index
RESPEAKER_INDEX = 1  # refer to input device id
CHUNK = 1024
RECORD_SECONDS = 8 # enter seconds to run

def time_str_to_float(time_str):
    hours, minutes, seconds_ms = time_str.split(':')
    seconds, milliseconds = seconds_ms.split(',')
    time_float = float(hours) * 3600 + float(minutes) * 60 + float(seconds) + float(milliseconds) / 1000
    return time_float

def find_device():
    dev = usb.core.find(idVendor=0x2886, idProduct=0x0018)
    if dev is None:	
        raise Exception("USB device not found.")
    return dev

def open_audio_stream(p):
    stream = p.open(
        rate=RESPEAKER_RATE,
        format=p.get_format_from_width(RESPEAKER_WIDTH),
        channels=RESPEAKER_CHANNELS,
        input=True,
        input_device_index=RESPEAKER_INDEX,
    )
    return stream

# Record audio, save audio in wave file, save DOA in json file
def record_audio(stream, p, dev, record_file, doa_file):
    with wave.open(record_file, 'wb') as w:
        print("Say 'My name is 000, my favorite animal is 000, my favorite number is 000' in 6 seconds")
        w.setnchannels(1)
        w.setsampwidth(p.get_sample_size(p.get_format_from_width(RESPEAKER_WIDTH)))
        w.setframerate(RESPEAKER_RATE)

        data_list = []
        count = 1
        for i in range(0, int(RESPEAKER_RATE / CHUNK * RECORD_SECONDS)):
            data = stream.read(CHUNK)
            w.writeframes(data)
            Mic_tuning = Tuning(dev)
            if count < RECORD_SECONDS*10:
                if RESPEAKER_RATE / CHUNK / 10 * (count) < i < RESPEAKER_RATE / CHUNK / 10 * (count + 1):
                    doa = Mic_tuning.direction
                    timestamp = time.time()
                    data_list.append({'doa': doa, 'timestamp': timestamp, 'record_time': count/10})
                    print(str(count/10) + ', ' + str(doa))
                    count += 1

        print("* done recording")
        w.close()

    # Write DOA to json file
    with open(doa_file, 'w') as f:
        json.dump(data_list, f)

def close_audio_stream(stream, p):
    stream.stop_stream()
    stream.close()
    p.terminate()
    
def process_audio(wav_file, model_name):
    model = f"./whisper.cpp/models/ggml-{model_name}.bin"

    # Check if the file exists
    if not os.path.exists(model):
        raise FileNotFoundError(f"Model file not found: {model} \n\nDownload a model with this command:\n\n> bash ./models/download-ggml-model.sh {model_name}\n\n")

    if not os.path.exists(wav_file):
        raise FileNotFoundError(f"WAV file not found: {wav_file}")

    full_command = f"./whisper.cpp/main -m {model} -f {wav_file} -oj"

    # Execute the command
    process = subprocess.Popen(full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Get the output and error (if any)
    output, error = process.communicate()

    # Process and return the output string
    decoded_str = output.decode('utf-8').strip()
    processed_str = decoded_str.replace('[BLANK_AUDIO]', '').strip()

# Return DOA of speaker
def find_doa(doa_file, transcription_file):
    doa_list = []
    with open(transcription_file) as j:
        data = json.load(j)
    
    with open(doa_file) as d:
        doa_data = json.load(d)

    for transcription in data['transcription']:
        time_start = time_str_to_float(transcription['timestamps']['from'])
        time_end   = time_str_to_float(transcription['timestamps']['to'])
    for dic in doa_data:
        doa = dic['doa']
        doa_time = dic['record_time'] - 1
        if time_start < doa_time < time_end:
            doa_list.append(doa)
    median_doa = np.median(doa_list)
    
    return median_doa


# Add IDs in the dictionary
def add_ID(ID_list, doa_file, transcription_file, count):
    median_doa = find_doa(doa_file, transcription_file)
    words_not_removed = []

    with open(transcription_file) as j:
        data = json.load(j)

    # Words that are not saved as IDs
    words_to_remove = ['name', 'My', 'my', 'favorite', 'favourite', 'animal', 'is', 'number', 'animals', 'numbers', 'a', 'an', 'the', 'and', 'And', 'Hi']
    for transcription in data['transcription']:
        for item in transcription:
            if 'text' == item:
                sentence = transcription[item]
                sentence = sentence.replace(".","").replace(",","")
                words = sentence.split()
                word_not_removed = [word for word in words if word not in words_to_remove]
                words_not_removed.extend(word_not_removed)
                                                                                      
    print(words_not_removed)
    # Add name, animal, number in the dictionary
    ID_list['person'+str(count)] = {'doa': median_doa, 'ID': words_not_removed}

    sentence_not_removed = ' '.join(words_not_removed)
    
    return sentence_not_removed, ID_list, median_doa
    
def get_input():
    value = input("Type add ID or stop: ")
    return value


def main():
    os.environ['KMP_DUPLICATE_LIB_OK']='True'
    ID_file            = 'dataset/Feb23/assign_speaker/ID.json'
    ID_list = {}
    model = "base.en"

    iteration = 0
    # Start recording
    while True:
        input = get_input()
        if input == 'stop':
            with open(ID_file, 'a') as i:
                json.dump(ID_list, i)
            print("Assigning speakers is done")
            break
        if input == 'add ID':
            iteration += 1
            audio_file         = 'dataset/Feb23/assign_speaker/ID%d.wav'%iteration
            transcription_file = 'dataset/Feb23/assign_speaker/ID%d.wav.json'%iteration
            doa_file           = 'dataset/Feb23/assign_speaker/doa%d.json'%iteration

            # record audio
            dev = find_device()
            p = pyaudio.PyAudio()
            stream = open_audio_stream(p)
            record_audio(stream, p, dev, audio_file, doa_file)
            close_audio_stream(stream, p)

            # Transcribe the audio
            process_audio(audio_file, model)

            # Create ID file 
            ID, ID_list, median_doa = add_ID(ID_list, doa_file, transcription_file, iteration)

            
            print("Speaker (" + ID + ") is added from " + str(median_doa))
        else:
            print("Invalid input. Please try again.")
    


    
if __name__ == "__main__":
    main()