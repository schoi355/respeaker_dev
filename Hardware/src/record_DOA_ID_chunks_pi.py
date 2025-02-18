import usb.core
import usb.util
import pyaudio
import wave
import numpy as np
from tuning import Tuning
import json
import time
from datetime import datetime
import boto3
import os
import subprocess
from decimal import Decimal
from collections import defaultdict
import sys
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
# run get_index.py to get index
RESPEAKER_INDEX = 1  # refer to input device id
CHUNK = 1024
CHUNKSIZE = 15 # sec

def read_cfg(file_path):
    config = {}
    
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"): 
                continue            
            if '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip().strip("'\"") 
    return config

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HARDWARE_DIR = os.path.dirname(SCRIPT_DIR)

cfg_path = os.path.join(HARDWARE_DIR, "application.cfg")
config = read_cfg(cfg_path)
AWS_ACCESS_KEY_ID = config.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = config.get('AWS_SECRET_ACCESS_KEY')
AWS_REGION = config.get('AWS_REGION')
S3_BUCKET_NAME = 'respeaker-recordings'

s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

def upload_to_s3(local_file_path, s3_path):
    try:
        s3.upload_file(local_file_path, S3_BUCKET_NAME, s3_path)
        print(f'Successfully uploaded {local_file_path} to {s3_path}')
    except Exception as e:
        print(f'Error uploading {local_file_path} to {s3_path}: {e}')

def ang_shift(angle):
    shifted_angle = angle + 360
    return shifted_angle

# Assign a range of angles for each speaker 
def assign_angle(ID_file):
    angle = int(30) # 20 deg 
    ang_dic = {}
    with open(ID_file, 'r') as f:
        ID_data = json.load(f)
        
        for key in ID_data:
            angle_range = [ID_data[key]['doa']-angle, ID_data[key]['doa']+angle]
            ang_dic[ID_data[key]['ID']] = angle_range

        print('The range of angles are assigned:')
        return ang_dic

        # else:
        #     print('The number of people does not match with the number of IDs')

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


def record_audio(stream, p, dev, ID_file, audio_file, doa_file, unknown_speakers):
    data_list = []
    count = 0
    ang_dic = assign_angle(ID_file)

    wf = wave.open(audio_file, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(p.get_sample_size(p.get_format_from_width(RESPEAKER_WIDTH)))
    wf.setframerate(RESPEAKER_RATE)
    for i in range(0, int(RESPEAKER_RATE / CHUNK * CHUNKSIZE)):
        data = stream.read(CHUNK, exception_on_overflow = False)
        wf.writeframes(data)
        
        Mic_tuning = Tuning(dev)
        if count < CHUNKSIZE*10:
            if RESPEAKER_RATE / CHUNK / 10 * (count) < i < RESPEAKER_RATE / CHUNK / 10 * (count + 1):
                # Get DOA
                doa = Mic_tuning.direction
                timestamp = time.time()

                # Assign a speaker according to DOA
                ID = None
                for key in ang_dic:
                    if ang_shift(ang_dic[key][0]) <= ang_shift(doa) <= ang_shift(ang_dic[key][1]):
                        ID = key
                
                # If no known speaker matches, check unknown speakers
                if ID is None:
                     for us_id, details in unknown_speakers.items():
                        #print(doa, ang_shift(details['start']), ang_shift(details['end']))
                        if ang_shift(details['start']) <= ang_shift(doa) <= ang_shift(details['end']):  # Adjusting for ±5 degrees
                            ID = us_id
                            break

                # If no match found, assign a new temporary ID
                if ID is None:
                    ID = f'temp_{len(unknown_speakers) + 1}'
                    unknown_speakers[ID]['start'] = min(unknown_speakers[ID]['start'], doa - 20)
                    unknown_speakers[ID]['end'] = max(unknown_speakers[ID]['end'], doa + 20)
                    unknown_speakers[ID]['ids'].append(ID)

                data_list.append({'doa': doa, 'timestamp': timestamp, 'record_time': count/10, 'speaker': ID})
                print(str(count/10) + ', ' + str(doa), " ", ID)
                count += 1
             
            with open (doa_file, 'w') as fj:
                json.dump(data_list,fj)

    return unknown_speakers

def close_audio_stream(stream, p):
    stream.stop_stream()
    stream.close()
    p.terminate()

def word_to_num(word):
    mapping = {
        '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
        '6': 6, '7': 7, '8': 8, '9': 9, '10': 10
    }
    return mapping.get(word.lower(), 0)

def upload_json_to_dynamodb(id_file, table_name):
    # Initialize a DynamoDB resource
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION,
                              aws_access_key_id=AWS_ACCESS_KEY_ID,
                              aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
    table = dynamodb.Table(table_name)

    # Load ID.json file
    with open(id_file, 'r') as file:
        id_data = json.load(file)

    # Aggregate speaker information into a list or map
    speakers_list = []
    for speaker_id, info in id_data.items():
        
        # Each entry in the list is a map/dictionary of speaker information
        speaker_info = {
            'SpeakerID': speaker_id,
            'DOA': Decimal(str(info['doa'])),
            'ID': info['ID']
        }
        speakers_list.append(speaker_info)

    # Prepare the item for DynamoDB
    # Assuming 'SessionID' is the partition key, and 'Speakers' will store the list of speaker information
    item = {
        'SessionID': '3',
        'Speakers': speakers_list
    }

    # Upload the item to DynamoDB
    response = table.put_item(Item=item)
    print(f"Uploaded session 3 with all speakers to DynamoDB")

def update_id_json(id_file, dir_name, unknown_speakers):

    print(unknown_speakers)
    try:
        with open(dir_name + '/assign_speaker/' + id_file, 'r') as file:
            id_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error opening or reading {id_file}: {e}")
        id_data = {}

    for speaker_id, details in unknown_speakers.items():
        doa_avg = Decimal((details['start'] + details['end']) / 2)
        id_data[speaker_id] = {
            "doa": float(doa_avg),
            "ID": speaker_id
        }

    try:
        with open(dir_name + '/assign_speaker/ID.json', 'w') as file:
            json.dump(id_data, file, indent=4)
        print(f"{id_file} updated with unknown speakers.")
    except Exception as e:
        print(f"Failed to update {id_file}: {e}")

def upload_json_to_s3(local_file_path, file_key=None):
    # Validate the file exists locally
    if not os.path.isfile(local_file_path):
        raise FileNotFoundError(f"The file {local_file_path} does not exist.")
    # Use the local file's name as the key if not provided
    if file_key is None:
        file_key = os.path.basename(local_file_path)
    try:
        # Upload the file
        s3.upload_file(local_file_path, S3_BUCKET_NAME, file_key)
        print(f"File {local_file_path} successfully uploaded to {S3_BUCKET_NAME}/{file_key}.")
    except Exception as e:
        print(f"Failed to upload {local_file_path} to S3: {e}")
        raise
    print(f"File {file_key} updated successfully in bucket {S3_BUCKET_NAME}.")

def button_setup(chip, button_tuple):
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

def display_text(disp, text1, range1, text2='', range2=(0,0)):
    image = Image.new("1", (disp.width, disp.height))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text(range1, text1, font=font, fill=255,)
    draw.text(range2, text2, font=font, fill=255,)
    disp.image(image)
    disp.show()

def display_text2(disp, text0, text1, text2, text3):
    image = Image.new("1", (disp.width, disp.height))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((15, 0), text0, font=font, fill=255,)
    draw.text((120, 15), text1, font=font, fill=255,)
    draw.text((120, 40), text2, font=font, fill=255,)
    draw.text((0, 25), text3, font=font, fill=255,)
    disp.image(image)
    disp.show()

def save_config(disp, config_file, key, value):
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        config = {}
    
    config[key] = value
    
    with open(config_file, "w") as f:
        json.dump(config, f, indent=4)
    display_text(disp, f"{key} is set to {value}", (5, 15))
    time.sleep(2)

def select_id(disp, config_file, key, prompt, button_request, b1, b2, b3):
    value = 1
    # display_text2(f"{prompt}: {value}", "+", "--", "Select")
    while True:
        display_text2(disp, f"{prompt}: {value}", "+", "--", "Select")
        l1, l2, l3 = (button_request.get_value(b) for b in [b1, b2, b3])
        if l1 == Value.INACTIVE:
            value += 1
        elif l2 == Value.INACTIVE:
            value -= 1
        elif l3 == Value.INACTIVE:
            save_config(disp, config_file, key, value)
            break

def main():
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
    parser = argparse.ArgumentParser(description="directory")
    parser.add_argument("-d", "--directory", required=True, help="directory that will contain the dataset")
    parser.add_argument("-s", "--second", required=True, help="recording duration")
    args = parser.parse_args()
    dir_name = args.directory
    trial = str(dir_name)[-1]
    duration = args.second

    ID_file  = dir_name + '/assign_speaker/ID.json'
    config_file = dir_name + '/assign_speaker/config.json'

    pi_id = 2   # Change this according to the sd card number
    b1, b2, b3 = 6, 5, 4

    chip = gpiod.Chip("/dev/gpiochip4")
    i2c = busio.I2C(board.SCL, board.SDA)
    disp = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
    button_request = button_setup(chip, (b1, b2, b3)) 
    for key, prompt in [("project_id", "Set Project ID"), ("class_id", "Set Class ID")]:
        while button_request.get_value(b1) == Value.ACTIVE and button_request.get_value(b2) == Value.ACTIVE:
            display_text(disp, f"{prompt} -->", (40, 15), "Set as Default -->", (40, 40))
            pass
        if button_request.get_value(b2) == Value.INACTIVE:
            save_config(disp, config_file, key, 1) # default project/class id is 1
        elif button_request.get_value(b1) == Value.INACTIVE:
            select_id(disp, config_file, key, prompt, button_request, b1, b2, b3)
    save_config(disp, config_file, "pi_id", pi_id)
    button_request.release()
    chip.close()
    i2c.deinit()

    # Calibration
    dir_path = dir_name + '/recorded_data/'
    cal_path = SCRIPT_DIR + '/assign_speaker_pi.py'
    subprocess.run(['python3',cal_path, '-d', dir_name], check=True)

    # After assign_speaker.py completes, proceed with the rest of this script
    print("assign_speaker_pi.py has finished. Proceeding with the next part.")

    
    sec = int(duration)
    os.environ['LAST_ITERATION'] = str(sec)
    iteration = 0
    unknown_speakers = defaultdict(lambda: {'start': float('inf'), 'end': float('-inf'), 'ids': []})

    # Load IDs from the ID file
    with open(ID_file, 'r') as f:
        ID_data = json.load(f)
        # Convert word-based numeric IDs to integers and sort them
        numeric_ids = sorted([word_to_num(info['ID'][0]) for info in ID_data.values()])
        filtered_numeric_ids = list(filter(lambda x: x!= 0, numeric_ids))
        id_str = '_'.join(map(str, filtered_numeric_ids))

    # Set up the OLED
    chip = gpiod.Chip("/dev/gpiochip4")
    i2c = busio.I2C(board.SCL, board.SDA)
    disp = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

    prev_line1_state = Value.ACTIVE
    button_request = button_setup(chip, (b1, b2, b3)) 

    upload_json_to_s3(ID_file, 'ID.json')

    # Start recording
    while True:
        line1 = button_request.get_value(b2)
        prev_line1_state = line1
        if iteration >= sec:
            print("RECORDING FINISHED")
            display_text(disp, "RECORDING FINISHED", (10,15))
            upload_json_to_dynamodb(ID_file, 'Team_assignment')
            button_request.release()
            break
        elif line1 == Value.INACTIVE:
            print("RECORDING FINISHED")
            display_text(disp, "RECORDING FINISHED", (10,15))
            button_request.release()
            break
        else:
            dev = find_device()
            p = pyaudio.PyAudio()
            stream = open_audio_stream(p)
            iteration += CHUNKSIZE
            audio_file = dir_path + 'chunk_%d.wav'%iteration
            doa_file   = dir_path + 'DOA_%d.json'%iteration

            print("RECORDING STARTED")
            display_text(disp, "RECORDING STARTED", (10,15), "Hold to Finish recording -->", (0, 40))
                
            unknown_speakers = record_audio(stream, p, dev, ID_file, audio_file, doa_file, unknown_speakers)
            update_id_json('ID.json', dir_name, unknown_speakers)
            date_folder = datetime.now().strftime('%Y-%m-%d')

            # audio_s3_path = f'audio-files/{date_folder}/{id_str}/{os.path.basename(audio_file)}'
            # doa_s3_path = f'doa-files/{date_folder}/{id_str}/{os.path.basename(doa_file)}'
            audio_s3_path = f'trials/{date_folder}/{trial}/audio-files/{id_str}/{os.path.basename(audio_file)}'
            doa_s3_path = f'trials/{date_folder}/{trial}/doa-files/{id_str}/{os.path.basename(doa_file)}'
            
            # # Upload audio file to S3
            upload_to_s3(audio_file, audio_s3_path)

            # # Upload doa file to S3
            upload_to_s3(doa_file, doa_s3_path)

            close_audio_stream(stream, p)

            print(str(iteration) + ' of '+ str(sec) + ' seconds are recorded')

if __name__ == '__main__':
    main()
