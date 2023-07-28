# respeaker_dev

This repository is under development for
 - Transcribe conversation using whisper
 - Identify speakers' Direction of Angle (DOA) usign Respeaker device

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


## `assign_speaekr.py
This code is to assign speakers with their name and match it with their DOA. Find the ID results in `assign_speaker/ID.json` 
