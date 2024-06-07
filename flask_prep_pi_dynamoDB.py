from flask import Flask, request, jsonify
import json
import os
import pandas as pd
import nltk
import spacy
from nltk.stem import PorterStemmer
from datetime import datetime, timedelta
import boto3
import os
import time
import botocore.exceptions
from boto3.dynamodb.conditions import Attr
import sys
import argparse

AWS_ACCESS_KEY_ID = 'AKIA5ILC25FLJDD4PYMI'
AWS_SECRET_ACCESS_KEY = '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'
AWS_REGION = 'us-east-2'

dynamodb = boto3.resource(
    'dynamodb',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

table = dynamodb.Table('respeaker_data')

# Initialize NLTK stemmer
stemmer = PorterStemmer()

app = Flask(__name__)

# Load the spaCy language model
nlp = spacy.load("en_core_web_sm")




def word_to_num(word):
    mapping = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 
        'nine': 9, 'ten': 10, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9}
    return mapping.get(word.lower(), 0)


def get_id_str(DIR_NAME):
    ID_file  = DIR_NAME + '/assign_speaker/ID.json'
    # Load IDs from the ID file
    with open(ID_file, 'r') as f:
        ID_data = json.load(f)
        # Convert word-based numeric IDs to integers and sort them
        numeric_ids = sorted([word_to_num(info['ID'][0]) for info in ID_data.values()])
        id_str = '_'.join(map(str, numeric_ids))
    
    id_str = "Apple"
    return id_str


# Function to get the lemma (base form) of a word
def get_lemma(word):
    doc = nlp(word)
    return doc[0].lemma_

@app.route('/check_speakers_not_spoken', methods=['POST'])
def check_speakers_not_spoken():
    parser = argparse.ArgumentParser(description="directory")
    parser.add_argument("-d", "--directory", required=True, help="directory that will contain the dataset")
    args = parser.parse_args()
    DIR_NAME = args.directory
    # Get the start and end times from the request

    # Load the JSON data from the ID.json file
    with open(DIR_NAME + '/assign_speaker/ID.json', 'r') as file:
        data = json.load(file)

    # Initialize an empty set for preset_speakers
    preset_speakers = set()

    # Iterate through the data and add the first value of the ID array for each person to the set
    for person in data.values():
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
    id_str = get_id_str(DIR_NAME)
    cur_date_formatted = datetime.now().strftime('%Y-%m-%d')
    cur_time_formatted = datetime.now().strftime('%H:%M:%S')

    try:
        # Fetch the current item based on group_id
        response = table.get_item(Key={'group_id': id_str})
        item = response.get('Item')

        if item:
            # Ensure current date's map exists directly within the item
            if cur_date_formatted not in item:
                item[cur_date_formatted] = {}

            # Add the new result to the 'check_speakers_not_spoken' section within the current date
            cur_date_data = item[cur_date_formatted]
            cur_date_data.setdefault('check_speakers_not_spoken', {})
            cur_date_data['check_speakers_not_spoken'][f"Results_{cur_time_formatted}"] = speakers_not_spoken_result

            # Update the item in the table
            table.put_item(Item=item)
        else:
            # If the item does not exist, create a new one with the date directly under group_id
            new_item = {
                'group_id': id_str,
                cur_date_formatted: {
                    'check_speakers_not_spoken': {
                        f"Results_{cur_time_formatted}": speakers_not_spoken_result
                    }
                }
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
    parser = argparse.ArgumentParser(description="directory")
    parser.add_argument("-d", "--directory", required=True, help="directory that will contain the dataset")
    args = parser.parse_args()
    DIR_NAME = args.directory

    speakers_not_spoken = set(preset_speakers)

    # Define the range of numbers (10 to 240) for the filenames
    for number in range(start_time, end_time + 1, 15):
        # Provide path to transcript chunks here
        filename = DIR_NAME + '/recorded_data/chunk_%d.wav.json'%number
        if os.path.exists(filename):
            # Load the JSON data from the file
            with open(filename, 'r') as file:
                data = json.load(file)

                for segment in data['transcription']:
                    speaker_name = segment['speaker']
                    speakers_not_spoken.discard(speaker_name)

    print(list(speakers_not_spoken))
    return list(speakers_not_spoken)
  

@app.route('/analysis', methods=['POST'])
def analyze_transcripts():
    parser = argparse.ArgumentParser(description="directory")
    parser.add_argument("-d", "--directory", required=True, help="directory that will contain the dataset")
    args = parser.parse_args()
    DIR_NAME = args.directory

    # Load the JSON data from the ID.json file
    with open(DIR_NAME + '/assign_speaker/ID.json', 'r') as file:
        data = json.load(file)

    # Initialize an empty set for preset_speakers
    preset_speakers = set()

    # Iterate through the data and add the first value of the ID array for each person to the set
    for person in data.values():
        if person['ID']:  # Check if the ID list is not empty
            preset_speakers.add(person['ID']) 

    data = request.json
    
    total_files = int(data['total_files'])  
    x = total_files #last chunk ID + 1
    print("last_chunk_id", x)
    x += 1
    # Initialize an empty list to store the table data
    all_table_data = []
    
    # Define the range of numbers (105 to 240) for the filenames
    for number in range(15, x, 15):
        #Provide path to transcript chunks here
        filename = DIR_NAME + '/recorded_data/chunk_%d.wav.json'%number
        if os.path.exists(filename):
            # Load the JSON data from the file
            with open(filename, 'r') as file:
                data = json.load(file)

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
                    if segment['speaker']:
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
                        'File Name': filename  # Store the file name
                    })

    # Merge consecutive sentences spoken by the same person in the final result
    merged_table_data = []
    current_speaker = None
    current_sentence = ""
    current_file_names = []

    for data in all_table_data:
        if current_speaker == data['Person']:
            current_sentence += " " + data['Sentence']
            current_file_names.append(data['File Name'])
        else:
            if current_sentence:
                merged_table_data.append({
                    'Person': current_speaker,
                    'Sentence': current_sentence,
                    'Start Time': current_start_time,
                    'End Time': current_end_time,
                    'File Names': ', '.join(current_file_names)  # Store multiple file names as a comma-separated string
                })
            current_speaker = data['Person']
            current_sentence = data['Sentence']
            current_start_time = data['Start Time']
            current_end_time = data['End Time']
            current_file_names = [data['File Name']]


    # Add the last merged sentence
    if current_sentence:
        merged_table_data.append({
            'Person': current_speaker,
            'Sentence': current_sentence,
            'Start Time': current_start_time,
            'End Time': current_end_time,
            'File Names': ', '.join(current_file_names)
        })

    # Create a DataFrame
    df = pd.DataFrame(merged_table_data)

    # Drop duplicate file names from the 'File Names' column
    df['File Names'] = df['File Names'].apply(lambda x: ', '.join(sorted(set(x.split(', ')))))

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
            word = get_lemma(word)
            word = word.lower()
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

    id_str = get_id_str(DIR_NAME)
    cur_date_formatted = datetime.now().strftime('%Y-%m-%d')
    cur_time_formatted = datetime.now().strftime('%H:%M:%S')

    try:
        response = table.get_item(Key={'group_id': id_str})
        item = response.get('Item')

        if item:
            # Ensure current date exists directly within the item
            cur_date_data = item.setdefault(cur_date_formatted, {})
        else:
            # If the item does not exist, create a new structure for it
            cur_date_data = {}
            item = {
                'group_id': "Apple",
                cur_date_formatted: cur_date_data
            }

        # Update word counts and first words spoken in separate layers within the current date
        cur_date_data.setdefault('word_counts', {})
        cur_date_data['word_counts'][f"Results_{cur_time_formatted}"] = json.dumps(word_counts_result)
        
        cur_date_data.setdefault('first_words_spoken', {})
        if first_words_spoken_result:  # Check if the result is not empty before updating
            cur_date_data['first_words_spoken'][f"Results_{cur_time_formatted}"] = json.dumps(first_words_spoken_result)
        else:
            cur_date_data['first_words_spoken'][f"Results_{cur_time_formatted}"] = "{}"

        # Update or create the item in the table
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

if __name__ == '__main__':
    app.run(debug=True, port=8080)