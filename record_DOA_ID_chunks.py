import usb.core
import usb.util
import pyaudio
import wave
import numpy as np
from tuning import Tuning
import json
import time

RESPEAKER_RATE = 16000
RESPEAKER_CHANNELS = 1 # change base on firmwares, 1_channel_firmware.bin as 1 or 6_channels_firmware.bin as 6
RESPEAKER_WIDTH = 2
# run getDeviceInfo.py to get index
RESPEAKER_INDEX = 5  # refer to input device id
CHUNK = 1024
CHUNKSIZE = 10 # sec

def ang_shift(angle):
    shifted_angle = angle % 360
    if shifted_angle < 0:
        shifted_angle += 360
    return shifted_angle

def ang_shift_backward(angle):
    if 320 <= angle < 360:
        shifted_angle = angle - 360
    else:
        shifted_angle = angle
    return shifted_angle


# Assign a range of angles for each speaker 
def assign_angle(number, ID_file):
    angle = int(20) # 20 deg 
    ang_dic = {}
    with open(ID_file, 'r') as f:
        ID_data = json.load(f)
        if len(ID_data) == number:
            for key in ID_data:
                angle_range = [ang_shift(ID_data[key]['doa']-angle), ang_shift(ID_data[key]['doa']+angle)]
                ang_dic[ID_data[key]['ID'][0]] = angle_range

            print('The range of angles are assigned:')
            return ang_dic

        else:
            print('The number of people does not match with the number of IDs')

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

def record_audio(stream, p, dev, num, ID_file, audio_file, doa_file):
    data_list = []
    count = 0

    ang_dic = assign_angle(num, ID_file)
    print(ang_dic)

    wf = wave.open(audio_file, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(p.get_sample_size(p.get_format_from_width(RESPEAKER_WIDTH)))
    wf.setframerate(RESPEAKER_RATE)
    for i in range(0, int(RESPEAKER_RATE / CHUNK * CHUNKSIZE)):
        data = stream.read(CHUNK)
        wf.writeframes(data)
        
        Mic_tuning = Tuning(dev)
        if count < CHUNKSIZE*10:
            if RESPEAKER_RATE / CHUNK / 10 * (count) < i < RESPEAKER_RATE / CHUNK / 10 * (count + 1):
                # Get DOA
                doa = Mic_tuning.direction
                timestamp = time.time()

                # Assign a speaker according to DOA
                ID = 'unknown'
                for key in ang_dic:
                    if ang_shift_backward(ang_dic[key][0]) <= ang_shift_backward(doa) <= ang_shift_backward(ang_dic[key][1]):
                        ID = key

                data_list.append({'doa': doa, 'timestamp': timestamp, 'record_time': count/10, 'speaker': ID})
                print(str(count/10) + ', ' + str(doa))
                count += 1
             
            with open (doa_file, 'w') as fj:
                json.dump(data_list,fj)
    
    print("chunk saved")

def close_audio_stream(stream, p):
    stream.stop_stream()
    stream.close()
    p.terminate()

def get_ID_number():
    value = input("Type number of perople in the table: ")
    return value

def get_sec():
    value = input("Type duration of record in seconds: ")
    return value

def main():
    ID_file  = 'assign_speaker/ID.json'
    num = int(get_ID_number())
    sec = int(get_sec())
    iteration = 0
    # Start recording
    while True:
        if iteration >= sec:
            print("DONE RECORDING")
            break
        else:
            dev = find_device()
            p = pyaudio.PyAudio()
            stream = open_audio_stream(p)
            iteration += CHUNKSIZE
            audio_file = 'chunks/chunk_%d.wav'%iteration
            doa_file   = 'chunks/DOA_%d.json'%iteration

            print("RECORDING STARTED")
                
            record_audio(stream, p, dev, num, ID_file, audio_file, doa_file)
            close_audio_stream(stream, p)

            print(str(iteration) + ' of '+ str(sec) + ' seconds are recorded')

if __name__ == '__main__':
    main()

