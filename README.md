# respeaker_dev

Note: google speach-to-text API requires python 3.7


## How to use

Before running any python script, run `get_index.py`
```
$ python get_index.py 
``` 

This gives you what index the device is using.
The index is defined as `RESPEAKER_INDEX` in `record.py` and `record_DOA.py`

## How to use `record_DOA.py`
This code is to record wave file from Respeaker device and collect DOA with timestamp and record time in JSON file. It produces `.wav` and `.json`


## How to use `synchronous_transcribe_local_file.py`
This code is to use an audio file and corresponding json file which are collected by `record_DOA.py`. It sends the audio data to google speech-to-text API, receive transcription, and save the transcription and corresponding DOA in json file. The list in json file includes transcription, word, start time of the word, timestamp (UTC), and DOA. Refer `


## How to use `respeaker_loca.py` (in progress)

To record voice in `.wav` and DOA and timestamp in `.json`, run `respeaker_local.py` 

```
$ python respeaker_local.py [-h] [-i INDEX] [-d DURATION] [-t TIMESTEP] [-w WAVE] [-j JSON]
``` 
with options:
- `-h`, `--help`:                          show this help message and exit
- `-i INDEX`, `--index INDEX`:             input device id (default: 1)
- `-d DURATION`, `--duration DURATION`:    recording duration (s)
- `-t TIMESTEP`, `--timestep TIMESTEP`:    timestep for DOA (s)
- `-w WAVE`, `--wave WAVE`:                save voice data into wave format
- `-j JSON`, `--json JSON`:                save DOA and timestamp into json format
