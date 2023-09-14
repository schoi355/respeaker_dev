import json
import usb.core
import usb.util
import pyaudio
import wave
import numpy as np
from tuning import Tuning
import time
import os


RESPEAKER_RATE = 16000
RESPEAKER_CHANNELS = 1 # change base on firmwares, 1_channel_firmware.bin as 1 or 6_channels_firmware.bin as 6
RESPEAKER_WIDTH = 2
# run getDeviceInfo.py to get index
RESPEAKER_INDEX = 5  # refer to input device id
CHUNK = 1024
RECORD_SECONDS = 8 # enter seconds to run

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


# Trnascribe audio file and save the transcription in json file
def transcribe_file(audio_file, transcription_file):
    import whisper_timestamped as whisper

    # Transcribe audio file
    audio = whisper.load_audio(audio_file)
    model = whisper.load_model("base", device="cpu") # choose a model (tiny, base, small, medium, and large)
    result = whisper.transcribe(model, audio, language="En")

    # Write transcription to json file
    with open(transcription_file, 'w') as t:
        json.dump(result, t)

# Add DOA in the transcription file
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
    
    with open(transcription_file, 'w') as j:
        json.dump(transcription, j)

# Add IDs in the dictionary
def add_ID(ID_list, transcription_file, count):
    with open(transcription_file) as j:
        transcription = json.load(j)

    # Words that are not saved as IDs
    words_to_remove = ['name', 'My', 'my', 'favorite', 'favourite', 'animal', 'is', 'number', 'animals', 'numbers', 'a', 'an', 'the', 'and']
    sentence = transcription["text"]
    sentence = sentence.replace(".","").replace(",","")
    words = sentence.split()
    word_not_removed = [word for word in words if word not in words_to_remove]

    doa_array = []
    for seg in transcription['segments']:
        for words in seg['words']:
            try: 
                doa_array.append(words['DOA'])
            except:
                pass
    doa_array.remove(max(doa_array))
    doa_array.remove(min(doa_array))
    median_doa = np.median(doa_array)

    # Add name, animal, number in the dictionary
    ID_list['person'+str(count)] = {'doa': median_doa, 'ID': word_not_removed}

    sentence_not_removed = ' '.join(word_not_removed)
    
    return sentence_not_removed, ID_list
    
def get_input():
    value = input("Type add ID or stop: ")
    return value


def main():
    os.environ['KMP_DUPLICATE_LIB_OK']='True'
    ID_file            = 'assign_speaker/ID.json'
    ID_list = {}

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
            audio_file         = 'assign_speaker/ID%d.wav'%iteration
            transcription_file = 'assign_speaker/transcript_ID%d.json'%iteration
            doa_file           = 'assign_speaker/doa%d.json'%iteration

            # record audio
            dev = find_device()
            p = pyaudio.PyAudio()
            stream = open_audio_stream(p)
            record_audio(stream, p, dev, audio_file, doa_file)
            close_audio_stream(stream, p)

            # Transcribe the audio
            transcribe_file(audio_file, transcription_file)
            
            # Add DOA info on the transcription file
            add_doa(doa_file, transcription_file)
            
            # Add ID 
            ID, ID_list = add_ID(ID_list, transcription_file, iteration)

            
            print("Speaker (" + ID + ") is added")
        else:
            print("Invalid input. Please try again.")
    


    
if __name__ == "__main__":
    main()