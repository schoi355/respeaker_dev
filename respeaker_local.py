"""
This code records voice from ReSpeaker USB Mic Array in wav file and save corresponding DOA and timestamp in json file.

Written by: Su Yeon Choi
Written on: 01/24/2023
"""

from tuning import Tuning
from pathlib import Path
from typing import NoReturn
import pyaudio
import usb.core
import usb.util
import wave
import time
import json
import numpy as np
from respeaker_args import voice_recorder_args



class voiceRecord:
    def __init__(self, index: int, duration: int, timestep: float) -> None:
        self.RESPEAKER_RATE = 16000
        self.RESPEAKER_CHANNELS = 6
        self.RESPEAKER_WIDTH = 2
        self.CHUNK = 1024
        self.dev = usb.core.find(idVendor=0x2886, idProduct=0x0018)
        self.index = index
        self.duration = duration
        self.timestep = timestep
        self.voiceframes = []
        self.doaframes = {}

        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            rate=self.RESPEAKER_RATE,
            format=self.p.get_format_from_width(self.RESPEAKER_WIDTH),
            channels=self.RESPEAKER_CHANNELS,
            input=True,
            input_device_index=self.index,)
    
    def get_voice(self) -> bytes:

        voice_data = self.stream.read(self.CHUNK)

        return voice_data


    def get_doa(self) -> str:

        if self.dev:
            Mic_tuning = Tuning(self.dev)
            timestamp = int(time.time()*1e6)
            doa_data = {"timestamp": str(timestamp), "DOA": str(Mic_tuning.direction)}

        return doa_data

    def write_to_file(self, wave_name: Path | str, json_name: Path | str) -> NoReturn:
        wave_name = Path(wave_name)
        json_name = Path(json_name)
        print(f"Writing files at {wave_name} and {json_name}")

        with wave.open(wave_name, 'wb') as w:
            while True:
                with open(json_name, 'w') as j:
                    while True:
                        try:
                            self.voiceframes.append(self.get_voice())
                            self.doaframes.update(self.get_doa())
                            
                            w.setnchannels(self.RESPEAKER_CHANNELS)
                            w.setsampwidth(self.p.get_sample_size(self.p.get_format_from_width(self.RESPEAKER_WIDTH)))
                            w.setframerate(self.RESPEAKER_RATE)
                            w.writeframes(b''.join(self.voiceframes))
                            json.dump(self.doaframes, j)

                        except KeyboardInterrupt:
                            print("\n ======= KEYBOARD INTERPUPT ======= ")
                            print(f"Wrote File at {wave_name} and {json_name}")
                            w.close()
                            exit()

    def print_to_console(self) -> NoReturn:
        while True:
            try:
                print(self.get_voice(), end="\n")
                print(self.get_doa, end="\n")
            except KeyboardInterrupt:
                print("\n ======= KEYBOARD INTERPUPT ======= ")
                exit()    

if __name__ == "__main__":
    args = voice_recorder_args().parse_args()

    voice_recorder = voiceRecord(index=args.index, duration=args.duration, timestep=args.timestep)

    if not args.wave or not args.json:
        voice_recorder.print_to_console()
    else:
        voice_recorder.write_to_file(args.wave, args.json)
        




# RESPEAKER_RATE = 16000
# RESPEAKER_CHANNELS = 1 # change base on firmwares, 1_channel_firmware.bin as 1 or 6_channels_firmware.bin as 6
# RESPEAKER_WIDTH = 2
# # run getDeviceInfo.py to get index
# RESPEAKER_INDEX = 0  # refer to input device id
# CHUNK = 1024
# RECORD_SECONDS = 10
# WAVE_OUTPUT_FILENAME = "Jul8.wav"
# f = open("experiment_data/Nov4/DOA_Nov4_1.txt", 'w') 

# dev = usb.core.find(idVendor=0x2886, idProduct=0x0018)

# p = pyaudio.PyAudio()
 
# stream = p.open(
#             rate=RESPEAKER_RATE,
#             format=p.get_format_from_width(RESPEAKER_WIDTH),
#             channels=RESPEAKER_CHANNELS,
#             input=True,
#             input_device_index=RESPEAKER_INDEX,)
 
# print("* recording")
 
# frames = []

# count = 1
# timestep = 0.1


# for i in range(0, int(RESPEAKER_RATE / CHUNK * RECORD_SECONDS)):
#     data = stream.read(CHUNK)
#     frames.append(data)

#     if dev:
#         Mic_tuning = Tuning(dev)
#         if count*timestep < RECORD_SECONDS:
#             if i < RESPEAKER_RATE / CHUNK * count*timestep and i > RESPEAKER_RATE / CHUNK *(count-1)*timestep:
#                 timestamp = int(time.time()*1e6)
#                 get_doa = str(timestamp) + ',' + str("{:.1f}".format(count*timestep)) + ',' + str(Mic_tuning.direction)
#                 print(get_doa)
#                 f.write(get_doa + '\n')
#                 count += 1

# f.close()
# print("* done recording")
 
# stream.stop_stream()
# stream.close()
# p.terminate()
 
# wf0 = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
# wf0.setnchannels(1)
# wf0.setsampwidth(p.get_sample_size(p.get_format_from_width(RESPEAKER_WIDTH)))
# wf0.setframerate(RESPEAKER_RATE)
# wf0.writeframes(b''.join(frames))
# wf0.close()