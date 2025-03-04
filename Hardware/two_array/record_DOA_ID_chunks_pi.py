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

from edit_speaker import start_monitoring  # Import the monitoring function


RESPEAKER_RATE = 16000
RESPEAKER_CHANNELS = 1 # change base on firmwares, 1_channel_firmware.bin as 1 or 6_channels_firmware.bin as 6
RESPEAKER_WIDTH = 2
# run getDeviceInfo.py to get index
#RESPEAKER_INDEX = 2  # refer to input device id
CHUNK = 1024
CHUNKSIZE = 15 # sec

"""
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
"""
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
            ang_dic[ID_data[key]['ID']] = angle_range

        print('The range of angles are assigned:')
        return ang_dic

        # else:
        #     print('The number of people does not match with the number of IDs')

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


def record_audio(stream, p, dev, audio_file, doa_file, unknown_speakers, start_time):
    data_list = []
    count = 0
    #ang_dic = assign_angle(ID_file)

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
                #for key in ang_dic:
                #    if ang_shift(ang_dic[key][0]) <= ang_shift(doa) <= ang_shift(ang_dic[key][1]):
                #        ID = key
                
                # If no known speaker matches, check unknown speakers
                #if ID is None:
                #     for us_id, details in unknown_speakers.items():
                #        #print(doa, ang_shift(details['start']), ang_shift(details['end']))
                #        if ang_shift(details['start']) <= ang_shift(doa) <= ang_shift(details['end']):  # Adjusting for ±5 degrees
                #            ID = us_id
                #            break

                # If no match found, assign a new temporary ID
                if ID is None:
                    ID = f'temp_{len(unknown_speakers) + 1}'
                    unknown_speakers[ID]['start'] = min(unknown_speakers[ID]['start'], doa - 20)
                    unknown_speakers[ID]['end'] = max(unknown_speakers[ID]['end'], doa + 20)
                    unknown_speakers[ID]['ids'].append(ID)

                data_list.append({'doa': doa, 'timestamp': timestamp, 'record_time': timestamp - start_time, 'speaker': ID})
                print(str(timestamp - start_time) + ', ' + str(doa), " ", ID)
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
"""
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
"""
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


def main():
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
    parser = argparse.ArgumentParser(description="directory")
    parser.add_argument("-d", "--directory", required=True, help="directory that will contain the dataset")
    parser.add_argument("-s", "--second", required=True, help="recording duration")
    parser.add_argument("-i", "--index", required=True, help="Index of the ReSpeaker device")  # New argument for index
    parser.add_argument("-o", "--other_index", required=True, help="Index of the other device") 
    parser.add_argument("-t", "--start_time", required=True, help="Shared start time for all recordings")  # Add start_time argument
    args = parser.parse_args()
    dir_name = args.directory
    duration = args.second
    RESPEAKER_INDEX = int(args.index)  # Set the microphone index from the argument
    start_time = float(args.start_time)  # Shared start time

    dir_path = dir_name + '/recorded_data/'
    #subprocess.run(['python', 'assign_speaker_pi.py', '-d', dir_name, '-i', args.index], check=True)
    process = subprocess.Popen(['python', 'assign_speaker_pi.py', '-d', dir_name, '-i', args.index])
    process.wait()  # Wait for it to finish


    # After assign_speaker.py completes, proceed with the rest of this script
    print("assign_speaker_pi.py has finished. Proceeding with the next part.")
    
    #ID_file  = dir_name + '/assign_speaker/ID.json'
    sec = int(duration)
    os.environ['LAST_ITERATION'] = str(sec)
    iteration = 0
    unknown_speakers = defaultdict(lambda: {'start': float('inf'), 'end': float('-inf'), 'ids': []})
    
    # Load IDs from the ID file
    #print(ID_file)
    #with open(ID_file, 'r') as f:
    #    ID_data = json.load(f)
    #    # Convert word-based numeric IDs to integers and sort them
    #    numeric_ids = sorted([word_to_num(info['ID'][0]) for info in ID_data.values()])
    #    filtered_numeric_ids = list(filter(lambda x: x!= 0, numeric_ids))
    #    id_str = '_'.join(map(str, filtered_numeric_ids))


    # Directory path for storing JSON files
    dir_path = 'data/recorded_data/'

    # Start monitoring the directory for JSON pairs
    start_monitoring(dir_path, args.index, args.other_index)

    # Start recording
    while True:
        if iteration >= sec:
            print("DONE RECORDING")

            #upload_json_to_dynamodb(ID_file, 'Team_assignment')
            break
        else:
            dev = find_device(int(args.index) - 2)
            p = pyaudio.PyAudio()
            stream = open_audio_stream(p, RESPEAKER_INDEX)
            iteration += CHUNKSIZE
            audio_file = dir_path + f'chunk_{RESPEAKER_INDEX}_{iteration}.wav'
            doa_file   = dir_path + f'DOA_{RESPEAKER_INDEX}_{iteration}.json'
            

            print("RECORDING STARTED")
                
            unknown_speakers = record_audio(stream, p, dev, audio_file, doa_file, unknown_speakers, start_time)
            #update_id_json('ID.json', dir_name, unknown_speakers)
            date_folder = datetime.now().strftime('%Y-%m-%d')
            audio_s3_path = f'audio-files/{date_folder}/{os.path.basename(audio_file)}'
            doa_s3_path = f'doa-files/{date_folder}/{os.path.basename(doa_file)}'
            """
            # # Upload audio file to S3
            upload_to_s3(audio_file, audio_s3_path)

            # # Upload doa file to S3
            upload_to_s3(doa_file, doa_s3_path)
            """
            close_audio_stream(stream, p)

            print(str(iteration) + ' of '+ str(sec) + ' seconds are recorded')

if __name__ == '__main__':
    main()
