from flask import Flask, request, jsonify
import json
import os
import pandas as pd
import nltk
from nltk.stem import PorterStemmer

# Initialize NLTK stemmer
stemmer = PorterStemmer()

app = Flask(__name__)

@app.route('/')
def analyze_transcripts():
    # Your code for analyzing transcripts here
    # Initialize an empty list to store the table data
    all_table_data = []
    x = 240 + 1 #last chunk ID + 1
    # Define the range of numbers (10 to 240) for the filenames
    for number in range(10, x, 10):
        #Provide path to transcript chunks here
        filename = f'transcript_chunk_{number}.json'
        if os.path.exists(filename):
            # Load the JSON data from the file
            with open(filename, 'r') as file:
                data = json.load(file)

            # Extract the speaker names from the JSON data
            speaker_names = set(word['speaker'] for segment in data['segments'] for word in segment.get('words', []) if 'speaker' in word)

            # Iterate through segments and extract relevant information
            for segment in data['segments']:
                segment_id = segment['id']
                start_time = segment['start']
                end_time = segment['end']

                # Extract words spoken by each person
                words = segment.get('words', [])

                # Initialize the speaker name for this segment
                segment_speaker = None

                for word in words:
                    text = word['text']
                    if 'speaker' in word:
                        segment_speaker = word['speaker']
                    if segment_speaker:
                        speaker_name = segment_speaker
                    else:
                        speaker_name = "unknown"

                    spoken_text = text if segment_speaker else f"{text} (unknown)"

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
        "health*",
        "obes*",
        "garden*",
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
    root_word_dict = {stemmer.stem(word): '*' in word for word in bag_of_words}

    # Print the root word dictionary
    print(root_word_dict)

    # Initialize a dictionary to store the first occurrence of words from the bag of words
    first_occurrence = {word: None for word in bag_of_words}

    # Iterate through the DataFrame to find the first occurrence of words
    prev = None
    for index, row in df.iterrows():
        words = row['Sentence'].split()
        for word in words:
            word = stemmer.stem(word)
            word = word.lower()
            if word in bag_of_words and first_occurrence[word] is None:
                first_occurrence[word] = row['Person']
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
    app.run(debug=True)
