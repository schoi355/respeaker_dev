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
RESPEAKER_INDEX = 1  # refer to input device id
CHUNK = 1024
RECORD_SECONDS = 5 # enter seconds to run
WAVE_OUTPUT_FILENAME = "file_name.wav" # enter filename here

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

def record_audio(stream, p, dev):
    print("* recording")

    wf1 = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf1.setnchannels(1)
    wf1.setsampwidth(p.get_sample_size(p.get_format_from_width(RESPEAKER_WIDTH)))
    wf1.setframerate(RESPEAKER_RATE)

    data_list = []
    count = 1
    for i in range(0, int(RESPEAKER_RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        wf1.writeframes(data)

        Mic_tuning = Tuning(dev)
        if count < RECORD_SECONDS:
            if i < RESPEAKER_RATE / CHUNK * count and i > RESPEAKER_RATE / CHUNK * (count - 1):
                doa = Mic_tuning.direction
                timestamp = time.time()
                data_list.append({'doa': doa, 'timestamp': timestamp})
                print("{:02d}".format(0) + ':' + "{:02d}".format(count) + ' ' + str(doa))
                count += 1

    print("* done recording")
    wf1.close()

    # Write data to a JSON file
    with open('data.json', 'w') as f:
        json.dump(data_list, f)

def close_audio_stream(stream, p):
    stream.stop_stream()
    stream.close()
    p.terminate()

def main():
    dev = find_device()
    p = pyaudio.PyAudio()
    stream = open_audio_stream(p)
    record_audio(stream, p, dev)
    close_audio_stream(stream, p)

if __name__ == '__main__':
    main()
