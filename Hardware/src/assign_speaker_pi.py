import json
import usb.core
import usb.util
import pyaudio
import wave
import numpy as np
from tuning import Tuning
import time
import os
import argparse
from gpiod.line_settings import LineSettings
from gpiod.line import Direction, Value
import gpiod  
import time
import board
import busio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306



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
            data = stream.read(CHUNK, exception_on_overflow = False)
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
    ID_list['person'+str(std_id)] = {'doa': median_doa, 'ID': str(std_id)}    
    print('DOA of student ' + str(std_id) + ' is ' + str(median_doa))

    return ID_list, median_doa

chip = gpiod.Chip("/dev/gpiochip4")
i2c = busio.I2C(board.SCL, board.SDA)
disp = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

def button_setup(button_tuple):
    line_settings = LineSettings()
    line_settings.direction = Direction.INPUT

    line_request = chip.request_lines(
        config={
            button_tuple: line_settings
        },
        consumer="button-reader",
        event_buffer_size=1
    )
    return line_request

def display_text(text1, range1, text2='', range2=(0,0)):
    image = Image.new("1", (disp.width, disp.height))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text(range1, text1, font=font, fill=255,)
    draw.text(range2, text2, font=font, fill=255,)
    disp.image(image)
    disp.show()

def display_text2(text0, text1, text2, text3):
    image = Image.new("1", (disp.width, disp.height))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((15, 0), text0, font=font, fill=255,)
    draw.text((120, 15), text1, font=font, fill=255,)
    draw.text((120, 40), text2, font=font, fill=255,)
    draw.text((0, 25), text3, font=font, fill=255,)
    disp.image(image)
    disp.show()

def calibration(dir_path, std_id, ID_list):
    audio_file         = dir_path+'ID'+str(std_id)+'.wav'
    doa_file           = dir_path+'doa'+str(std_id)+'.json'
    dev = find_device()
    p = pyaudio.PyAudio()
    stream = open_audio_stream(p)
    record_audio(stream, p, dev, audio_file, doa_file, std_id)
    close_audio_stream(stream, p)
    ID_list, median_doa = add_ID(ID_list, doa_file, std_id)
    return ID_list


def main():

    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

    parser = argparse.ArgumentParser(description="directory")
    parser.add_argument("-d", "--directory", required=True, help="directory that will contain the dataset")
    args = parser.parse_args()
    dir_name = args.directory
    dir_path = dir_name+'/assign_speaker/'

    ID_file            = dir_path+'ID.json'
    ID_list = {}

    b1 = 6
    b2 = 5
    b3 = 4

    prev_line1_state = Value.ACTIVE
    button_request = button_setup((b1, b2)) 
    
    while True:
        
        line1 = button_request.get_value(b1)
        line2 = button_request.get_value(b2)
        
        student_id = 0
        
        if line1 == Value.ACTIVE and line2 == Value.ACTIVE:
            display_text("Add student -->", (50, 15), "Finish calibration -->", (20, 40))
            
        elif line2 == Value.INACTIVE:
            with open(ID_file, 'a') as i:
                json.dump(ID_list, i)
            display_text("Calibration is finished", (5,15))
            time.sleep(2)
            button_request.release()
            chip.close()
            i2c.deinit()
            break
        
        while line1 == Value.INACTIVE or prev_line1_state == Value.INACTIVE:
            prev_line1_state = line1
            button_request.release()
            display_text2(f"Select student ID: {student_id}", "+", "--", "Start recording")
            button_request = button_setup((b1, b2, b3))
            l1 = button_request.get_value(b1)
            l2 = button_request.get_value(b2)
            l3 = button_request.get_value(b3)
            if l1 == Value.INACTIVE:
                student_id += 1
                display_text2(f"Select student ID: {student_id}", "+", "--", "Start  recording")
            if l2 == Value.INACTIVE:
                student_id -= 1
                display_text2(f"Select student ID: {student_id}", "+", "--", "Start  recording")
            if l3 == Value.INACTIVE:
                display_text("Start calibration", (15,15), f"for student {student_id}", (15,30))
                ID_list = calibration(dir_path, student_id, ID_list)
                display_text(f"Student {student_id} is done!", (15,15))
                time.sleep(2)
                prev_line1_state = Value.ACTIVE
                button_request.release()
                button_request = button_setup((b1, b2))
                break

    
if __name__ == "__main__":
    main()
