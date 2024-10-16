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

RESPEAKER_RATE = 16000
RESPEAKER_CHANNELS = 1 # change base on firmwares, 1_channel_firmware.bin as 1 or 6_channels_firmware.bin as 6
RESPEAKER_WIDTH = 2
# run getDeviceInfo.py to get index
RESPEAKER_INDEX = 0  # refer to input device id
CHUNK = 1024
CHUNKSIZE = 15 # sec


AWS_ACCESS_KEY_ID = 'AKIA5ILC25FLJDD4PYMI'
AWS_SECRET_ACCESS_KEY = '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'
AWS_REGION = 'us-east-2'
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
    angle = int(20) # 20 deg 
    ang_dic = {}
    with open(ID_file, 'r') as f:
        ID_data = json.load(f)
        
        for key in ID_data:
            angle_range = [ID_data[key]['doa']-angle, ID_data[key]['doa']+angle]
            ang_dic[ID_data[key]['ID'][0]] = angle_range

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


def record_audio(stream, p, dev, num, ID_file, audio_file, doa_file, unknown_speakers):
    data_list = []
    count = 0
    ang_dic = assign_angle(ID_file)
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

def get_ID_number():
    value = input("Type number of people in the table: ")
    return value

def get_sec():
    value = input("Type duration of record in seconds: ")
    return value

def word_to_num(word):
    mapping = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
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

def update_id_json(id_file, unknown_speakers):

    print(unknown_speakers)
    try:
        with open('assign_speaker/' + id_file, 'r') as file:
            id_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error opening or reading {id_file}: {e}")
        id_data = {}

    for speaker_id, details in unknown_speakers.items():
        doa_avg = Decimal((details['start'] + details['end']) / 2)
        id_data[speaker_id] = {
            "doa": float(doa_avg),
            "ID": [str(speaker_id), "Random animal", str(speaker_id.split('_')[1])]
        }

    try:
        with open('assign_speaker/ID.json', 'w') as file:
            json.dump(id_data, file, indent=4)
        print(f"{id_file} updated with unknown speakers.")
    except Exception as e:
        print(f"Failed to update {id_file}: {e}")

def main():

    subprocess.run(["python", "assign_speaker.py"], check=True)
    
    # # After assign_speaker.py completes, proceed with the rest of this script
    print("assign_speaker.py has finished. Proceeding with the next part.")


    ID_file  = 'assign_speaker/ID.json'
    num = int(get_ID_number())
    sec = int(get_sec())
    os.environ['LAST_ITERATION'] = str(sec)
    iteration = 0
    unknown_speakers = defaultdict(lambda: {'start': float('inf'), 'end': float('-inf'), 'ids': []})

    # Load IDs from the ID file
    with open(ID_file, 'r') as f:
        ID_data = json.load(f)
        # Convert word-based numeric IDs to integers and sort them
        numeric_ids = sorted([word_to_num(info['ID'][2]) for info in ID_data.values()])
        id_str = '_'.join(map(str, numeric_ids))

    
    # Start recording
    while True:
        if iteration >= sec:
            print("DONE RECORDING")
            
            upload_json_to_dynamodb('assign_speaker/ID.json', 'Team_assignment')
            break
        else:
            dev = find_device()
            p = pyaudio.PyAudio()
            stream = open_audio_stream(p)
            iteration += CHUNKSIZE
            audio_file = 'chunks/chunk_%d.wav'%iteration
            doa_file   = 'chunks/DOA_%d.json'%iteration

            print("RECORDING STARTED")
                
            unknown_speakers = (record_audio(stream, p, dev, num, ID_file, audio_file, doa_file, unknown_speakers))
            update_id_json('ID.json', unknown_speakers)
            date_folder = datetime.now().strftime('%Y-%m-%d')
            audio_s3_path = f'audio-files/{date_folder}/{id_str}/{os.path.basename(audio_file)}'
            doa_s3_path = f'doa-files/{date_folder}/{id_str}/{os.path.basename(doa_file)}'
            
            # Upload audio file to S3
            upload_to_s3(audio_file, audio_s3_path)

            # # Upload doa file to S3
            upload_to_s3(doa_file, doa_s3_path)

            close_audio_stream(stream, p)

            print(str(iteration) + ' of '+ str(sec) + ' seconds are recorded')

if __name__ == '__main__':
    main()
