# respeaker_dev

This repository is under development for
 - Transcribe conversation using whisper
 - Identify speakers' Direction of Angle (DOA) usign Respeaker device

## Setup

### Install portaudio
```
sudo apt install portaudio19-dev
```

### Install python packages
```
pip install pandas numpy watchdog
```
### Set up Respeaker
Refer to [respeaker wiki](https://wiki.seeedstudio.com/ReSpeaker-USB-Mic-Array/).
Install pyaudio and pyusb
```
pip install pyaudio pyusb
```
For raspberry Pi, using a virtual environment is recommended to isolate dependencies.
```
# Create a virtual environment
python3 -m venv venv
# Activate the virtual environment
source venv/bin/activate
```
Then, pip install pyaudio and pyusb. It might need portaudio and usb.

You might need to create a udev rule to ensure that the USB device is accessible by non-root users. Create a new file, for example, /etc/udev/rules.d/99-usb-permissions.rules, and add the following line:
```
SUBSYSTEM=="usb", MODE="0666"
```

### Set up Whisper (language model)

Install [whisper-timestamped](https://github.com/linto-ai/whisper-timestamped)
```
pip install git+https://github.com/linto-ai/whisper-timestamped
```

### Set up Flask
```
pip install flask nltk spacy
python -m spacy download en_core_web_sm
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
