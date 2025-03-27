from flask import Flask, request, jsonify
import json
import os
import pandas as pd
import nltk
import spacy
from nltk.stem import PorterStemmer
from datetime import datetime, timedelta
from transformers import pipeline
import torch
import boto3
import os
import time
import botocore.exceptions
from boto3.dynamodb.conditions import Attr
import sys
import argparse
from collections import defaultdict


application = Flask(__name__)

application.config.from_object(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HARDWARE_DIR = os.path.dirname(SCRIPT_DIR)
cfg_path = os.path.join(HARDWARE_DIR, "application.cfg")
application.config.from_pyfile(cfg_path, silent=True)

AWS_ACCESS_KEY_ID = application.config['AWS_ACCESS_KEY_ID']
AWS_SECRET_ACCESS_KEY = application.config['AWS_SECRET_ACCESS_KEY']
AWS_REGION = application.config['AWS_REGION']

device = 0 if torch.cuda.is_available() else -1
topic_detection_classifier = pipeline(
    'zero-shot-classification',
    model='Recognai/zeroshot_selectra_small',
    device=device
)
emotion_detection_classifier = pipeline(
    'text-classification',
    model='j-hartmann/emotion-english-distilroberta-base',
    top_k=None,
    device=device
)

os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
parser = argparse.ArgumentParser(description="directory")
parser.add_argument("-d", "--directory", required=True, help="directory that will contain the dataset")
args = parser.parse_args()
dir_name = args.directory
# TODO: Set using cmd args
PROJECT_NO = None
CLASS_NO = None
PI_ID = None
TRIAL_NO = None
date_folder = datetime.now().strftime('%Y-%m-%d')
# date_folder = '2025-02-20'
CHUNKSIZE = 15 # sec

dynamodb = boto3.resource(
    'dynamodb',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

table = dynamodb.Table('respeaker-analysis')
transcript_table = dynamodb.Table('respeaker-transcripts')
S3_BUCKET_NAME = 'respeaker-recordings'

# Initialize NLTK stemmer
stemmer = PorterStemmer()

# Load the spaCy language model
nlp = spacy.load("en_core_web_sm")

# Load LLM
# classifier = pipeline(task="text-classification", model="SamLowe/roberta-base-go_emotions", top_k=None)


def word_to_num(word):
    mapping = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 
        'nine': 9, 'ten': 10, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9}
    return mapping.get(word.lower(), 0)


def get_dynamic_folder_name(prefix):
    response = s3.list_objects_v2(
        Bucket=S3_BUCKET_NAME,
        Prefix=prefix,
        Delimiter='/',
    )

    if 'CommonPrefixes' in response:
        dynamic = response['CommonPrefixes'][0]['Prefix'].split('/')[-2]
        return dynamic
    
    return '1_2_3_4'


def get_id_json_from_s3():
    file_key = f'Project_{PROJECT_NO}/Class_{CLASS_NO}/{date_folder}/Pi_{PI_ID}/Trial_{TRIAL_NO}/ID.json'
    response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=file_key)
    content = response['Body'].read().decode('utf-8')
    return json.loads(content)

def get_transcription_from_s3(file_key):
    response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=file_key)
    content = response['Body'].read().decode('utf-8')
    if not content:
        return None
    return json.loads(content)

def get_id_str():
    # ID_file  = DIR_NAME + '/assign_speaker/ID.json'
    # # Load IDs from the ID file
    # with open(ID_file, 'r') as f:
    #     ID_data = json.load(f)
    #     # Convert word-based numeric IDs to integers and sort them
    #     numeric_ids = sorted([word_to_num(info['ID'][0]) for info in ID_data.values()])
    #     id_str = '_'.join(map(str, numeric_ids))
    ID_data = get_id_json_from_s3()

    numeric_ids = sorted([word_to_num(info['ID'][0]) for info in ID_data.values()])
    id_str = '_'.join(map(str, numeric_ids))
    
    # id_str = "Apple"
    return id_str


# Function to get the lemma (base form) of a word
def get_lemma(word):
    doc = nlp(word)
    return doc[0].lemma_


@application.route('/check_speakers_not_spoken', methods=['POST'])
def check_speakers_not_spoken():
    """
    return speakerId of ppl silent -> dynamoDB
    """
    # parser = argparse.ArgumentParser(description="directory")
    # parser.add_argument("-d", "--directory", required=True, help="directory that will contain the dataset")
    # args = parser.parse_args()
    # DIR_NAME = args.directory
    # # Get the start and end times from the request

    # Load the JSON data from the ID.json file
    # with open(DIR_NAME + '/assign_speaker/ID.json', 'r') as file:
    #     data = json.load(file)

    id_json = get_id_json_from_s3()
    print(id_json)
    # Initialize an empty set for preset_speakers
    preset_speakers = set()

    # Iterate through the data and add the first value of the ID array for each person to the set
    for person in id_json.values():
        if person['ID']:  # Check if the ID list is not empty
            preset_speakers.add(person['ID']) 

    data = request.json
    start_time = int(data['start_time'])  # Example format: '20'
    end_time = int(data['end_time']) #60

    
    print("Current time to call", end_time)
    # Call a function to check speakers who have not spoken within the specified time frame
    speakers_not_spoken = check_speakers_within_timeframe(start_time, end_time, preset_speakers)

    speakers_not_spoken_result = json.dumps(speakers_not_spoken)
    
    # DynamoDB update logic
    id_str = get_id_str()
    cur_date_formatted = datetime.now().strftime('%Y-%m-%d')
    cur_time_formatted = datetime.now().strftime('%H:%M:%S')

    try:
        # # Fetch the current item based on group_id
        response = table.get_item(Key={'Date': date_folder, 'Pi_id': str(PI_ID)})
        item = response.get('Item')

        if item:
            try:
                if f'Trial_{TRIAL_NO}' not in item:
                    item[f'Trial_{TRIAL_NO}'] = defaultdict(dict)
                item[f'Trial_{TRIAL_NO}'][f'{start_time}-{end_time}'] = {
                    'Check_Speakers_Not_Spoken': speakers_not_spoken_result,
                    'Word_Count': {},
                    'Off_Topic': {},
                    'Emotion': {},
                }
                table.put_item(Item=item)
            except Exception as e:
                return jsonify({
                    'Message': 'An error occurred',
                    'Error': e
                })
        else:
            new_item = {
                'Date': date_folder,
                'Pi_id': str(PI_ID),
                f'Trial_{TRIAL_NO}': {
                    f'{start_time}-{end_time}': {
                        'Check_Speakers_Not_Spoken': speakers_not_spoken_result,
                        'Word_Count': {},
                        'Off_Topic': {},
                        'Emotion': {},
                    }
                },
            }
            table.put_item(Item=new_item)


    except botocore.exceptions.ClientError as error:
        # Handle the exception
        print(f"An error occurred: {error}")

    result = {
        'message': 'Check for speakers not spoken completed and stored in DynamoDB.',
        'speakers_not_spoken': speakers_not_spoken  # Assuming speakers_not_spoken is the list of speakers
    }

    print(speakers_not_spoken)
    return jsonify(result)


def check_speakers_within_timeframe(start_time, end_time, preset_speakers):
    speakers_not_spoken = set(preset_speakers)

    # Define the range of numbers (10 to 240) for the filenames
    for number in range(start_time + CHUNKSIZE, end_time + 1, CHUNKSIZE):
        prefix = f'Project_{PROJECT_NO}/Class_{CLASS_NO}/{date_folder}/Pi_{PI_ID}/Trial_{TRIAL_NO}/transcription-files/'
        mid_folder = get_dynamic_folder_name(prefix)
        file_key = f'{prefix}{mid_folder}/chunk_{number}.wav.json'
        data = get_transcription_from_s3(file_key)
        if data:
            for segment in data['transcription']:
                if 'speaker' not in segment:
                    continue    
                speaker_name = segment['speaker']
                speakers_not_spoken.discard(speaker_name)

    print("Speakers not speaking: ", list(speakers_not_spoken))
    return list(speakers_not_spoken)
  
# TODO: Need to Access the transcribed files from somewhere
@application.route('/analysis', methods=['POST'])
def analyze_transcripts():
    """
    Off-topic and emotion -> DynamoDB {JSON}
    """
    parser = argparse.ArgumentParser(description="directory")
    parser.add_argument("-d", "--directory", required=True, help="directory that will contain the dataset")
    args = parser.parse_args()
    DIR_NAME = args.directory

    # Load the JSON data from the ID.json file
    # with open(DIR_NAME + '/assign_speaker/ID.json', 'r') as file:
    #     data = json.load(file)
    data = get_id_json_from_s3()

    # Initialize an empty set for preset_speakers
    preset_speakers = set()

    # Iterate through the data and add the first value of the ID array for each person to the set
    for person in data.values():
        if person['ID']:  # Check if the ID list is not empty
            preset_speakers.add(person['ID'])

    data = request.json
    request_start_time = int(data['start_time'])  # Example format: '20'
    request_end_time = int(data['end_time']) #60
    # Initialize an empty list to store the table data
    all_table_data = []

    # Define the range of numbers (105 to 240) for the filenames
    for number in range(request_start_time + CHUNKSIZE, request_end_time, CHUNKSIZE):
        #Provide path to transcript chunks here
        prefix = f'Project_{PROJECT_NO}/Class_{CLASS_NO}/{date_folder}/Pi_{PI_ID}/Trial_{TRIAL_NO}/transcription-files/'
        mid_folder = get_dynamic_folder_name(prefix)
        file_key = f'{prefix}{mid_folder}/chunk_{number}.wav.json'
        data = get_transcription_from_s3(file_key)

            # Extract the speaker names from the JSON data
        speaker_names = set(word['speaker'] for segment in data['transcription'] for word in segment.get('words', []) if 'speaker' in word)

        # Iterate through segments and extract relevant information
        for segment in data['transcription']:
            # segment_id = segment['id']
            start_time = segment['timestamps']['from']
            end_time = segment['timestamps']['to']

            # Extract words spoken by each person
            texts = segment['text']
            words = texts.split()
            # Initialize the speaker name for this segment
            segment_speaker = None

            for word in words:
                if 'speaker' in segment:
                    segment_speaker = segment['speaker']
                if segment_speaker:
                    speaker_name = segment_speaker
                else:
                    speaker_name = "unknown"

                spoken_text = word if segment_speaker else f"{word} (unknown)"

                all_table_data.append({
                    'Person': speaker_name,
                    'Sentence': spoken_text.strip(),
                    'Start Time': start_time,
                    'End Time': end_time,
                })

    # Merge consecutive sentences spoken by the same person in the final result
    merged_table_data = []
    current_speaker = None
    current_sentence = ""

    for data in all_table_data:
        if current_speaker == data['Person']:
            current_sentence += " " + data['Sentence']
        else:
            if current_sentence:
                merged_table_data.append({
                    'Person': current_speaker,
                    'Sentence': current_sentence,
                    'Start Time': current_start_time,
                    'End Time': current_end_time,
                })
            current_speaker = data['Person']
            current_sentence = data['Sentence']
            current_start_time = data['Start Time']
            current_end_time = data['End Time']


    # Add the last merged sentence
    if current_sentence:
        merged_table_data.append({
            'Person': current_speaker,
            'Sentence': current_sentence,
            'Start Time': current_start_time,
            'End Time': current_end_time,
        })

    # Create a DataFrame
    df = pd.DataFrame(merged_table_data)

    # Calculate the number of words spoken by each person
    df['Word Count'] = df['Sentence'].apply(lambda x: len(x.split()))

    # Create a bag of words dictionary
    # List of words with possible wildcards
    bag_of_words = [
        "Community garden",
        "Food desert",
        "Food swamp",
        "food system",
        "insecurity",
        "health",
        "obese",
        "garden",
        "access",
        "urban",
        "poverty",
        "rural",
        "low income",
        "middle income",
        "prices",
        "minority",
        "Sovereignty",
        "Local",
        "affordable",
        "Vegetable",
        "Meat",
        "hung",
        "Nutrition",
        "Grow",
        "Gather",
        "Grocery",
        "Agriculture",
        "Climate change",
        "Usda",
        "Food",
        "Policy",
        "plant",
        "environment",
        "greenhouse gas",
        "organic"
    ]
    # Replace with your dictionary
    bag_of_words = [word.lower() for word in bag_of_words]

    # Create a dictionary with root words (without wildcards)
    root_word_dict = {get_lemma(word): '*' in word for word in bag_of_words}


    # Initialize a dictionary to store the first occurrence of words from the bag of words
    first_occurrence = {word: None for word in root_word_dict}

    # Iterate through the DataFrame to find the first occurrence of words
    prev = None
    for index, row in df.iterrows():
        words = row['Sentence'].split()
        for word in words:
            if word in root_word_dict and first_occurrence[word] is None:
                first_occurrence[word] = row['Person']

            if prev and prev + word in root_word_dict and first_occurrence[prev + word] is None:
                first_occurrence[prev + word] = row['Person']

            prev = word
    ans = []
    word_counts_result = {speaker: 0 for speaker in preset_speakers}

    # Update the word counts for speakers who have spoken
    for person, group in df.groupby('Person'):
        word_count = group['Word Count'].sum()
        # Update the count for this person
        word_counts_result[person] = int(word_count)

    for word, person in first_occurrence.items():
        if person:
            ans.append(f"{person} spoke the word '{word}' first.")
            #print(f"{person} spoke the word '{word}' first.")
        else:
            ans.append(f"The word '{word}' was not spoken.")
            #print(f"The word '{word}' was not spoken.")

    # Prepare the separate results for word counts and first words spoken
    word_counts_result = {person: int(group['Word Count'].sum().item()) for person, group in df.groupby('Person')}
    first_words_spoken_result = first_occurrence

    try:
        response = table.get_item(Key={'Date': date_folder, 'Pi_id': str(PI_ID)})
        item = response.get('Item')
        # print("ITEM: ", item)

        if item:
            item[f'Trial_{TRIAL_NO}'][f'{request_start_time}-{request_end_time}']['Word_Count'] = json.dumps(word_counts_result)
            item[f'Trial_{TRIAL_NO}'][f'{request_start_time}-{request_end_time}']['First_Words_Spoken'] = json.dumps(first_words_spoken_result)
            table.put_item(Item=item)

    except botocore.exceptions.ClientError as error:
        print(f"An error occurred: {error}")

    result = {
        'message': 'Analysis completed and stored in DynamoDB.',
        'word_counts': word_counts_result,
        'first_words_spoken': first_words_spoken_result
    }

    print(first_words_spoken_result)

    return jsonify(result)


@application.route('/topic_detection', methods=['POST'])
def topic_detection():
    data = request.json
    request_start_time = int(data['start_time'])
    request_end_time = int(data['end_time'])
    speaker_topic = dict()
    bag_of_words = [
        "Community garden",
        "Food desert",
        "Food swamp",
        "food system",
        "insecurity",
        "health",
        "obese",
        "garden",
        "access",
        "urban",
        "poverty",
        "rural",
        "low income",
        "middle income",
        "prices",
        "minority",
        "Sovereignty",
        "Local",
        "affordable",
        "Vegetable",
        "Meat",
        "hung",
        "Nutrition",
        "Grow",
        "Gather",
        "Grocery",
        "Agriculture",
        "Climate change",
        "Usda",
        "Food",
        "Policy",
        "plant",
        "environment",
        "greenhouse gas",
        "organic"
    ]

    def topic_detection(seq):
        CI = 2.5
        res = topic_detection_classifier(seq, bag_of_words, multi_label=True)
        score = sum(res['scores'][:5])
        if score > CI:
            return 'On-Topic'
        else:
            return 'Off-Topic'
    
    try:
        response = transcript_table.get_item(Key={'Date': date_folder, 'Pi_id': str(PI_ID)})
        item = response.get('Item')

        df = pd.DataFrame(item[f'Transcript_{TRIAL_NO}'])
        df['End_time'] = df['Timestamp'].str.split('-').str[1].astype(int)
        df_filtered = df[df['End_time'] <= request_end_time]
        speaker_texts = df_filtered.groupby('Speaker')['Text'].agg(" ".join).to_dict()
        
        for speaker, spoken in speaker_texts.items():
            if speaker != 'Unknown':
                speaker_topic[speaker] = topic_detection(spoken)
        
        try:
            response = table.get_item(Key={'Date': date_folder, 'Pi_id': str(PI_ID)})
            analysis_item = response.get('Item')

            analysis_item[f'Trial_{TRIAL_NO}'][f'{request_start_time}-{request_end_time}']['Off_Topic'] = json.dumps(speaker_topic)
            table.put_item(Item=analysis_item)
        except botocore.exceptions.ClientError as error:
            print(f"An error occurred: {error}")
        
    except botocore.exceptions.ClientError as error:
        print(f"An error occurred: {error}")
            
    return jsonify({
        'message': 'Topic Detection completed and stored in DynamoDB',
    })


@application.route('/emotion_check', methods=['POST'])
def emotion_check():
    data = request.json
    request_start_time = int(data['start_time'])
    request_end_time = int(data['end_time'])
    speaker_emotion = dict()

    try:
        response = transcript_table.get_item(Key={'Date': date_folder, 'Pi_id': str(PI_ID)})
        item = response.get('Item')

        df = pd.DataFrame(item[f'Transcript_{TRIAL_NO}'])
        df['End_time'] = df['Timestamp'].str.split('-').str[1].astype(int)
        df_filtered = df[df['End_time'] <= request_end_time]
        speaker_texts = df_filtered.groupby('Speaker')['Text'].agg(" ".join).to_dict()
        
        for speaker, spoken in speaker_texts.items():
            if speaker != 'Unknown':
                op = emotion_detection_classifier(spoken)
                op[0].sort(key=lambda x: x['score'], reverse=True)
                speaker_emotion[speaker] = op[0][0]['label']
        
        try:
            response = table.get_item(Key={'Date': date_folder, 'Pi_id': str(PI_ID)})
            analysis_item = response.get('Item')

            analysis_item[f'Trial_{TRIAL_NO}'][f'{request_start_time}-{request_end_time}']['Emotion'] = json.dumps(speaker_emotion)
            table.put_item(Item=analysis_item)
        except botocore.exceptions.ClientError as error:
            print(f"An error occurred: {error}")
        
    except botocore.exceptions.ClientError as error:
        print(f"An error occurred: {error}")
            
    return jsonify({
        'message': 'Emotion analysis completed and stored in DynamoDB',
    })


@application.route('/check_server_working_get', methods=['GET'])
def check_server_working():
    try:
        response_message = {
            "status": "Success",
            "message": "Server is working correctly.",
        }

        return jsonify(response_message), 200  # HTTP 200 OK

    except Exception as e:
        # Handle any errors
        error_message = {
            "status": "Error",
            "message": "An error occurred.",
            "error_details": str(e)
        }
        return jsonify(error_message), 500  # HTTP 500 Internal Server Error


@application.route('/check_server_working_post', methods=['POST'])
def check_server_working_post():
    try:
        data = request.json  # Dummy data

        response_message = {
            "status": "Success",
            "message": "Server is working correctly.",
            "received_data": data
        }

        return jsonify(response_message), 200  # HTTP 200 OK

    except Exception as e:
        # Handle any errors
        error_message = {
            "status": "Error",
            "message": "An error occurred.",
            "error_details": str(e)
        }
        return jsonify(error_message), 500  # HTTP 500 Internal Server Error


@application.route('/append_transcript', methods=['POST'])
def append_transcript():
    print("Starting Appending")
    print(PROJECT_NO, CLASS_NO, TRIAL_NO, PI_ID)
    data = get_id_json_from_s3()

    # Initialize an empty set for preset_speakers
    preset_speakers = set()

    # Iterate through the data and add the first value of the ID array for each person to the set
    for person in data.values():
        if person['ID']:  # Check if the ID list is not empty
            preset_speakers.add(person['ID'])

    data = request.json
    request_start_time = int(data['start_time'])  # Example format: '20'
    request_end_time = int(data['end_time']) #60
    # Initialize an empty list to store the table data
    speaker_words = defaultdict(str)

    # Define the range of numbers (105 to 240) for the filenames
    for number in range(request_start_time + CHUNKSIZE, request_end_time + 1, CHUNKSIZE):
        #Provide path to transcript chunks here
        prefix = f'Project_{PROJECT_NO}/Class_{CLASS_NO}/{date_folder}/Pi_{PI_ID}/Trial_{TRIAL_NO}/transcription-files/'
        mid_folder = get_dynamic_folder_name(prefix)
        file_key = f'{prefix}{mid_folder}/chunk_{number}.wav.json'
        data = get_transcription_from_s3(file_key)

        # Extract the speaker names from the JSON data
        # speaker_names = set(word['speaker'] for segment in data['transcription'] for word in segment.get('words', []) 
        #                    if 'speaker' in word)

        
        # Iterate through segments and extract relevant information
        for segment in data['transcription']:
            # Extract words spoken by each person
            transcript_texts = segment['text']
            # Initialize the speaker name for this segment
            if 'speaker' not in segment:
                continue
            segment_speaker = segment['speaker'] if segment['speaker'][0] != 't' else 'Unknown'
            speaker_words[segment_speaker] += transcript_texts

    try:
        response = transcript_table.get_item(Key={'Date': date_folder, 'Pi_id': str(PI_ID)})
        item = response.get('Item')

        timestamp = [f'{request_start_time}-{request_end_time}'] * len(speaker_words)
        speakers, texts = [], []
        for speaker, text in speaker_words.items():
            speakers.append(speaker)
            texts.append(text)

        if item:
            if f'Transcript_{TRIAL_NO}' not in item:
                item[f'Transcript_{TRIAL_NO}'] = {
                    'Timestamp': timestamp,
                    'Speaker': speakers,
                    'Text': texts,
                }
            else:
                item_timestamp = item[f'Transcript_{TRIAL_NO}']['Timestamp']
                item_speaker = item[f'Transcript_{TRIAL_NO}']['Speaker']
                item_text = item[f'Transcript_{TRIAL_NO}']['Text']

                for ts, s, t in zip(timestamp, speakers, texts):     
                    item_timestamp.append(ts)
                    item_speaker.append(s)
                    item_text.append(t)
                
                item[f'Transcript_{TRIAL_NO}']['Timestamp'] = item_timestamp
                item[f'Transcript_{TRIAL_NO}']['Speaker'] =item_speaker
                item[f'Transcript_{TRIAL_NO}']['Text'] = item_text

            transcript_table.put_item(Item=item)

        else:
            new_item = {
                'Date': date_folder,
                'Pi_id': str(PI_ID),
                f'Transcript_{TRIAL_NO}': {
                    'Timestamp': timestamp,
                    'Speaker': speakers,
                    'Text': texts
                },
            }
            transcript_table.put_item(Item=new_item)
    except botocore.exceptions.ClientError as error:
        print(f"An error occurred: {error}")
                
    print('Ending Appending')
    result = {
        'Message': 'Appending Transcription completed and stored in DynamoDB.',
    }

    return jsonify(result)


@application.route('/initial_setup', methods=['POST'])
def initial_setup():
    global PROJECT_NO, CLASS_NO, TRIAL_NO, PI_ID
    data = request.get_json()

    PROJECT_NO = str(data['PROJECT_NO'] if 'PROJECT_NO' in data else 1)
    CLASS_NO = str(data['CLASS_NO'] if 'CLASS_NO' in data else 1)
    TRIAL_NO = str(data['TRIAL_NO'] if 'TRIAL_NO' in data else 1)
    PI_ID = str(data['PI_ID'] if 'PI_ID' in data else 1)

    return jsonify({
        'Message': 'Global Variables Updated.',
        'PROJECT_NO': PROJECT_NO,
        'CLASS_NO': CLASS_NO,
        'TRIAL_NO': TRIAL_NO,
        'PI_ID': PI_ID,
    })

if __name__ == '__main__':
    application.run(debug=True, port=8000)


"""
{
    "0-120": {
        # CSNP: [],
        word_count: {},
        off-topic: {
            1: True
            2: False
            3: Silent
        }
        emotion_detection: {
            1: sad,
            2: happy,
            3: Silent
        }
    },

    "60-180": {
        CSNP: [],
        word_count: {},
        off-topic: {
            1: True
            2: False
        }
        emotion_detection: {
            1: sad,
            2: happy,
        }
    }
}

# Make one combined transcription file and store on S3
"""