# respeaker_dev

This repository is under development for
 - Transcribe conversation using whisper
 - Identify speakers' Direction of Angle (DOA) usign Respeaker device

## Setup
Install pyaudio and pyusb
```
pip install pyaudio pyusb
```
For raspberry Pi
```
sudo apt install python3-pyaudio
pip install pyusb --break-system-packages
```
Install [whisper-timestamped](https://github.com/linto-ai/whisper-timestamped)
```
pip3 install git+https://github.com/linto-ai/whisper-timestamped
```


## How to use

Before running any python script, run `get_index.py`
```
$ python get_index.py 
``` 

This gives you what index the device is using.
The index is defined as `RESPEAKER_INDEX` in `record.py` and `record_DOA.py`

## `record_DOA.py`
This code is to record wave file from Respeaker device and collect DOA with timestamp and record time in JSON file. It produces `.wav` and `.json`


## `record_DOA_chunks.py`
This code is to record 10 seceond chunk of audio and collect DOA with timestamp and record time in JSON file.


## `assign_speaker.py`
This code is to assign speakers with their name and match it with their DOA. Find the ID results in `assign_speaker/ID.json` 


## `record_DOA_ID_chunks.py`
This code is similar to `record_DOA_chunks.py`, but adds speaker's name to DOA json file. It needs `ID.json` file to match DOA to the speakers.

## `transcribe_chunks.py`
This code is to transcribe audio chunks and produces transcription with speaker's name and DOA.
