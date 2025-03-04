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
#RESPEAKER_INDEX = 2  # refer to input device id
CHUNK = 1024
RECORD_SECONDS = 8 # enter seconds to run

def time_str_to_float(time_str):
    hours, minutes, seconds_ms = time_str.split(':')
    seconds, milliseconds = seconds_ms.split(',')
    time_float = float(hours) * 3600 + float(minutes) * 60 + float(seconds) + float(milliseconds) / 1000
    return time_float

def find_device(index):
    devices = [dev for dev in usb.core.find(find_all=True, idVendor=0x2886, idProduct=0x0018) 
           if any(usb.util.get_string(dev, intf.iInterface) == "SEEED Control" for cfg in dev for intf in cfg)]

    if not devices:
        raise Exception("No USB devices found.")
    if index >= len(devices):
        raise Exception(f"Device index {index} out of range. Only {len(devices)} devices found.")
    return devices[index]
    # previously was return devices[index], added below
    #device = devices[index]
    # Loop through the device configurations and pick the one that has 'SEEED Control' in its interface
    #for cfg in device:
    #    for intf in cfg:
    #        if 'SEEED Control' in usb.util.get_string(device, intf.iInterface):
    #            return device
    #raise Exception("Device with SEEED Control interface not found.")

def open_audio_stream(p, RESPEAKER_INDEX):
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
    parser.add_argument("-i", "--index", required=True, help="index of current speaker")
    args = parser.parse_args()
    dir_name = args.directory
    dir_path = dir_name+'/assign_speaker/'
    RESPEAKER_INDEX = int(args.index)

    ID_file = dir_path + f'mic{args.index}ID.json'
    ID_list = {}

    # Start recording
    """
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
    """
    #change range to 1, 5 for 4 people (ex)
    for i in range(1, 5):
        std_id = str(i)
        audio_file         = dir_path+'mic'+str(args.index)+'ID'+std_id+'.wav'
        doa_file           = dir_path+'mic'+str(args.index)+'doa'+std_id+'.json'
        # record audio
        dev = find_device(int(args.index) - 2)
        p = pyaudio.PyAudio()
        stream = open_audio_stream(p, RESPEAKER_INDEX)
        record_audio(stream, p, dev, audio_file, doa_file, std_id)
        close_audio_stream(stream, p)

        # Create ID file 
        ID_list, median_doa = add_ID(ID_list, doa_file, std_id)

    #Added
    with open(ID_file, 'w') as f:
        json.dump(ID_list, f, indent=4)


    
if __name__ == "__main__":
    main()