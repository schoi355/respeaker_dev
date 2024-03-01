from flask import Flask, request, jsonify
import json
import os
import pandas as pd
import nltk
import spacy
from nltk.stem import PorterStemmer
from datetime import datetime, timedelta
DIR_NAME = 'dataset/Mar1/'

# Initialize NLTK stemmer
stemmer = PorterStemmer()

app = Flask(__name__)

# Load the spaCy language model
nlp = spacy.load("en_core_web_sm")

# Function to get the lemma (base form) of a word
def get_lemma(word):
    doc = nlp(word)
    return doc[0].lemma_

@app.route('/check_speakers_not_spoken', methods=['POST'])
def check_speakers_not_spoken():
    # Get the start and end times from the request
    data = request.json
    start_time = int(data['start_time'])  # Example format: '20'
    end_time = int(data['end_time']) #60

    # preset_speakers = set(['Litong', 'David', 'Faith', 'Hiroto'])
    preset_speakers = set(['Su', 'Preet', 'Ayush'])
    # Call a function to check speakers who have not spoken within the specified time frame
    speakers_not_spoken = check_speakers_within_timeframe(start_time, end_time, preset_speakers)

    if speakers_not_spoken:
        result = {
            'message': 'Speakers who did not speak within the specified time frame:',
            'speakers_not_spoken': speakers_not_spoken
        }
    else:
        result = {
            'message': 'All speakers spoke within the specified time frame.'
        }

    return jsonify(result)

def check_speakers_within_timeframe(start_time, end_time, preset_speakers):
    speakers_not_spoken = set(preset_speakers)

    # Define the range of numbers (15 to 240) for the filenames
    for number in range(start_time + 15, end_time + 1, 15):
        # Provide path to transcript chunks here
        filename = DIR_NAME+f'recorded_data/chunk_{number}.wav.json'
        if os.path.exists(filename):
            # Load the JSON data from the file
            with open(filename, 'r') as file:
                data = json.load(file)

                for segment in data['transcription']:
                    start_time = segment['timestamps']['from']
                    end_time = segment['timestamps']['to']

                    # Extract words spoken by each person
                    texts = segment['text']
                    words = texts.split()

                    segment_speaker = None

                    for word in words:
                        if segment['speaker']:
                            segment_speaker = segment['speaker']
                        if segment_speaker:
                            speaker_name = segment_speaker
                        else:
                            speaker_name = "unknown"

                        # Remove the speaker from the set as they speak
                        speakers_not_spoken.discard(speaker_name)

    print(list(speakers_not_spoken))
    return list(speakers_not_spoken)


@app.route('/analysis', methods=['POST'])
def analyze_transcripts():

    data = request.json
    
    total_files = data['total_files']  
    x = total_files + 10
    # x = total_files * 10 + 1 #last chunk ID + 1
    # Initialize an empty list to store the table data
    all_table_data = []
    
    # Define the range of numbers (10 to 240) for the filenames
    for number in range(10, x, 10):
        #Provide path to transcript chunks here
        filename = DIR_NAME + f'recorded_data/chunk_{number}.wav.json'
        if os.path.exists(filename):
            # Load the JSON data from the file
            with open(filename, 'r') as file:
                data = json.load(file)

            # Extract the speaker names from the JSON data
            speaker_names = set(word['speaker'] for segment in data['transcription'] for word in segment.get('words', []) if 'speaker' in word)

            # Iterate through segments and extract relevant information
            for segment in data['transcription']:
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

    # Print or use the DataFrame as needed
    # print(df)

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
    print(get_lemma("Sovereignty      "))
    # Print the root word dictionary
    print(root_word_dict)

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
    # Print the number of words spoken by each person and the first person to speak each word
    for person, group in df.groupby('Person'):
        word_count = group['Word Count'].sum()
        print(f"{person} spoke {word_count} words.")
        ans.append(f"{person} spoke {word_count} words.")

    
    for word, person in first_occurrence.items():
        if person:
            ans.append(f"{person} spoke the word '{word}' first.")
            print(f"{person} spoke the word '{word}' first.")
        else:
            ans.append(f"The word '{word}' was not spoken.")
            print(f"The word '{word}' was not spoken.")

    result = {
        'message': 'Analysis completed.',
        'data': ans  # Replace with your actual analysis result
    }
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=8080)