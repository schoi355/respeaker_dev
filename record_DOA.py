from tuning import Tuning
import usb.core
import usb.util
import pyaudio
import wave
import numpy as np
 
RESPEAKER_RATE = 16000
RESPEAKER_CHANNELS = 6 # change base on firmwares, 1_channel_firmware.bin as 1 or 6_channels_firmware.bin as 6
RESPEAKER_WIDTH = 2
# run getDeviceInfo.py to get index
RESPEAKER_INDEX = 1  # refer to input device id
CHUNK = 1024
RECORD_SECONDS = 30
WAVE_OUTPUT_FILENAME = "Aug18alone_1.wav"
 
dev = usb.core.find(idVendor=0x2886, idProduct=0x0018)

p = pyaudio.PyAudio()
 
stream = p.open(
            rate=RESPEAKER_RATE,
            format=p.get_format_from_width(RESPEAKER_WIDTH),
            channels=RESPEAKER_CHANNELS,
            input=True,
            input_device_index=RESPEAKER_INDEX,)
 
print("* recording")
 
frames = [] 
count = 1
 
for i in range(0, int(RESPEAKER_RATE / CHUNK * RECORD_SECONDS)):
    data = stream.read(CHUNK)
    frames.append(data)
    if dev:
        Mic_tuning = Tuning(dev)
        if count < RECORD_SECONDS:
            if i < RESPEAKER_RATE / CHUNK * count and i > RESPEAKER_RATE / CHUNK *(count - 1):
                print("{:02d}".format(0) + ':' + "{:02d}".format(count) + ' ' + str(Mic_tuning.direction))
                count += 1
            
 
print("* done recording")
 
stream.stop_stream()
stream.close()
p.terminate()
 
wf1 = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
wf1.setnchannels(1)
wf1.setsampwidth(p.get_sample_size(p.get_format_from_width(RESPEAKER_WIDTH)))
wf1.setframerate(RESPEAKER_RATE)
wf1.writeframes(b''.join(frames))
wf1.close()
