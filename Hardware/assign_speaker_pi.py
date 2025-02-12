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
import sys
import argparse



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
def record_audio(stream, p, dev, record_file, doa_file, std_id):
    with wave.open(record_file, 'wb') as w:
        print("Say 'My name is 000. My favorite animal is 000. My student ID is 000")
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

# Return DOA of speaker
def find_doa(doa_file):
    doa_list = []
    with open(doa_file) as d:
        doa_data = json.load(d)

    for dic in doa_data:
        doa = dic['doa']
        doa_list.append(doa)
    median_doa = np.median(doa_list)
    
    return median_doa


# Add IDs in the dictionary
def add_ID(ID_list, doa_file, std_id):
    median_doa = find_doa(doa_file)
    ID_list['person'+std_id] = {'doa': median_doa, 'ID': std_id}    
    print('DOA of student ' + std_id + ' is ' + str(median_doa))

    return ID_list, median_doa


def main():

    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

    parser = argparse.ArgumentParser(description="directory")
    parser.add_argument("-d", "--directory", required=True, help="directory that will contain the dataset")
    args = parser.parse_args()
    dir_name = args.directory
    dir_path = dir_name+'/assign_speaker/'

    ID_file = dir_path+'ID.json'
    ID_list = {}

    # Start recording
    while True:
        value = input("Type add ID or stop: ")
        if value == 'stop':
            with open(ID_file, 'a') as i:
                json.dump(ID_list, i)
            print("Assigning speakers is done")
            break
        if value == 'add ID':
            std_id = input('Type the student ID: ')
            audio_file         = dir_path+'ID'+std_id+'.wav'
            doa_file           = dir_path+'doa'+std_id+'.json'
            # record audio
            dev = find_device()
            p = pyaudio.PyAudio()
            stream = open_audio_stream(p)
            record_audio(stream, p, dev, audio_file, doa_file, std_id)
            close_audio_stream(stream, p)

            # Create ID file 
            ID_list, median_doa = add_ID(ID_list, doa_file, std_id)

        else:
            print("Invalid input. Please try again.")
    


    
if __name__ == "__main__":
    main()
