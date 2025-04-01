import os
import json
import boto3
import pandas as pd
import time
from flask import Flask, jsonify
from datetime import datetime, timedelta

def read_cfg(file_path):
    dic = {}
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"): 
                continue            
            if '=' in line:
                key, value = line.split('=', 1)
                dic[key.strip()] = value.strip().strip("'\"") 
    return dic

POLLING_INTERVAL = 10
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HARDWARE_DIR = os.path.dirname(SCRIPT_DIR)
DATE_DIR = datetime.now().strftime('%Y-%m-%d')

cfg_path = os.path.join(HARDWARE_DIR, "application.cfg")
aws_key = read_cfg(cfg_path)
AWS_ACCESS_KEY_ID = aws_key.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = aws_key.get('AWS_SECRET_ACCESS_KEY')
AWS_REGION = aws_key.get('AWS_REGION')
S3_BUCKET_NAME = 'respeaker-recordings'

PROJECT_NO = 1
CLASS_NO = 1
PI_ID = 1

BASE_DIR = f"Project_{PROJECT_NO}/Class_{CLASS_NO}/{DATE_DIR}/Pi_{PI_ID}"
PROCESSED_FILES_KEY = f"{BASE_DIR}/processed_files.txt"

# Initialize S3 client
s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

app = Flask(__name__)

def fetch_existing_csv(base_dir):
    """Fetch existing CSV file from S3 or create a new one if not found."""
    try:
        obj = s3.get_object(Bucket=S3_BUCKET_NAME, Key=f"{base_dir}/batch_transcriptions.csv")
        df = pd.read_csv(obj["Body"])
    except s3.exceptions.NoSuchKey:
        df = pd.DataFrame(columns=["timestamp", "speaker", "transcription"])
    return df

def load_processed_files():
    """Load the list of processed JSON files from S3."""
    try:
        obj = s3.get_object(Bucket=S3_BUCKET_NAME, Key=PROCESSED_FILES_KEY)
        processed_files = set(obj["Body"].read().decode("utf-8").splitlines())
    except s3.exceptions.NoSuchKey:
        processed_files = set()
    return processed_files

def save_processed_files(processed_files):
    """Save the updated processed JSON file list back to S3."""
    temp_file = "/tmp/processed_files.txt"

    try:
        with open(temp_file, "w") as file:
            file.write("\n".join(processed_files))

        s3.upload_file(temp_file, S3_BUCKET_NAME, PROCESSED_FILES_KEY)
    
    finally:
        # Ensure file exists before deleting
        if os.path.exists(temp_file):
            os.remove(temp_file)

def find_insert_row(existing_df, new_timestamp, speaker):
    """Find the correct row to insert the text based on timestamp range."""
    for i in range(len(existing_df) - 1):
        start_time = existing_df.iloc[i]["timestamp"]
        end_time = existing_df.iloc[i + 1]["timestamp"]

        if start_time <= new_timestamp < end_time and existing_df.iloc[i]["speaker"] == speaker:
            return i  # Append text to the earlier row

    return None  # No match found, create a new row

import re  # Import regex module for extracting trial number

def append_json_to_csv(project_no, class_no, date_dir, pi_id):
    """Append new JSON transcription files from S3 subdirectories to CSV while preventing duplicates."""
    base_dir = BASE_DIR.format(PROJECT_NO=project_no, CLASS_NO=class_no, DATE_DIR=date_dir, PI_ID=pi_id)
    existing_df = fetch_existing_csv(base_dir)

    # Convert timestamps to datetime for processing
    if not existing_df.empty:
        existing_df["timestamp"] = pd.to_datetime(existing_df["timestamp"])

    # Load previously processed JSON files
    processed_files = load_processed_files()

    # Recursively list all objects in subdirectories
    response = s3.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=base_dir)
    
    if "Contents" not in response:
        return "No new files found."

    for obj in response["Contents"]:
        file_key = obj["Key"]

        # Extract trial number from directory name
        trial_match = re.search(r'Pi_\d+/(Trial_\d+)', file_key)
        trial_no = trial_match.group(1).replace("Trial_", "") if trial_match else "Unknown"

        # Skip non-JSON or non-wav.json files
        if not file_key.endswith(".wav.json"):
            continue
        
        # Skip already processed files
        if file_key in processed_files:
            continue

        json_obj = s3.get_object(Bucket=S3_BUCKET_NAME, Key=file_key)
        json_data = json.load(json_obj["Body"])

        # Dictionary to hold merged data for each speaker in the current file
        speaker_transcriptions = {}

        for entry in json_data["transcription"]:
            timestamp = datetime.fromtimestamp(float(entry["utc_time"]))
            speaker = entry.get("speaker", "NONE")
            text = entry["text"]

            if speaker in speaker_transcriptions:
                speaker_transcriptions[speaker]["text"] += " " + text
            else:
                speaker_transcriptions[speaker] = {"timestamp": timestamp, "text": text, "trial_no": trial_no}

        # Merge into existing DataFrame
        for speaker, data in speaker_transcriptions.items():
            new_timestamp = data["timestamp"]
            new_text = data["text"]
            trial_no = data["trial_no"]

            # Check if the speaker already has a row in the CSV
            appended = False
            if not existing_df.empty:
                for i in range(len(existing_df) - 1, -1, -1):  # Iterate in reverse
                    row_speaker = existing_df.iloc[i]["speaker"]
                    row_trial_no = str(existing_df.iloc[i].get("Trial No", ""))

                    if row_speaker == speaker and row_trial_no == trial_no:
                        existing_df.at[i, "transcription"] += " " + new_text
                        appended = True
                        break

            # If no matching row is found, create a new row
            if not appended:
                new_entry = pd.DataFrame([[new_timestamp, speaker, new_text, trial_no]], 
                                         columns=["timestamp", "speaker", "transcription", "Trial No"])
                existing_df = pd.concat([existing_df, new_entry], ignore_index=True)

        # Mark file as processed
        processed_files.add(file_key)

    # Save the processed file list to S3
    save_processed_files(processed_files)

    # Save the updated CSV file
    temp_csv_path = f"/tmp/temp_transcriptions_{project_no}_{class_no}_{date_dir}_{pi_id}.csv"
    
    if not existing_df.empty:
        existing_df.to_csv(temp_csv_path, index=False)
        s3.upload_file(temp_csv_path, S3_BUCKET_NAME, f"{base_dir}/batch_transcriptions.csv")

        # Remove temporary CSV file if it exists
        if os.path.exists(temp_csv_path):
            os.remove(temp_csv_path)

    return "CSV updated successfully."



def watch_s3(project_no, class_no, date_dir, pi_id):
    """Continuously monitor S3 and update CSV."""
    while True:
        append_json_to_csv(project_no, class_no, date_dir, pi_id)
        time.sleep(POLLING_INTERVAL)

@app.route("/update/<int:project_no>/<int:class_no>/<string:date_dir>/<int:pi_id>", methods=["GET"])
def update_csv(project_no, class_no, date_dir, pi_id):
    """Manually trigger CSV update."""
    result = append_json_to_csv(project_no, class_no, date_dir, pi_id)
    return jsonify({"message": result})

if __name__ == "__main__":
    import threading
    watcher_thread = threading.Thread(target=watch_s3, args=(PROJECT_NO, CLASS_NO, DATE_DIR, PI_ID), daemon=True)
    watcher_thread.start()
    app.run(host="127.0.0.1", port=7000, debug=True)
