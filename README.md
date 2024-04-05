# respeaker_dev

This repository is under development for
 - Transcribe conversation using whisper
 - Identify speakers' Direction of Angle (DOA) usign Respeaker device

## Setup

### Clone the repository

Make sure you have an access to this private repository.

### Create a virtual environment for Raspberry Pi

For raspberry Pi, using a virtual environment is recommended to isolate dependencies.
```
# Create a virtual environment
python3 -m venv venv
# Activate the virtual environment
source venv/bin/activate
```

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

Raspberry Pi might need portaudio and usb.
```
sudo apt-get install python3-usb python3-pyaudio
pip install pyaudio pyusb
```

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

### Set up AWS
```
pip install boto3
```



## How to use

Before running any python script, run `get_index.py`
```
$ python get_index.py 
``` 

This gives you what index the device is using.
The index is defined as `RESPEAKER_INDEX` in `record.py` and `record_DOA.py`

### `record_DOA.py`
This code is to record wave file from Respeaker device and collect DOA with timestamp and record time in JSON file. It produces `.wav` and `.json`


### `record_DOA_chunks.py`
This code is to record 10 seceond chunk of audio and collect DOA with timestamp and record time in JSON file.


### `assign_speaker.py`
This code is to assign speakers with their name and match it with their DOA. Find the ID results in `assign_speaker/ID.json` 


### `record_DOA_ID_chunks.py`
This code is similar to `record_DOA_chunks.py`, but adds speaker's name to DOA json file. It needs `ID.json` file to match DOA to the speakers.

### `transcribe_chunks.py`
This code is to transcribe audio chunks and produces transcription with speaker's name and DOA.

## Set up Raspberry pi ssh
To enable SSH via the Desktop, go to the `start menu` > `Preferences` > `Raspberry Pi Configuration`. Now click on `Interfaces` and click `enable` next to `SSH` and click `OK`.

Now to connect, on the host computer open a terminal window and type in
```
ssh username@raspberrypi.local
```
When it asks for the password, type the password of the pi, for example, `0000`. Change `username` to username of the pi, for example, `respeaker`.
If you want to terminate ssh, type `exit` on the terminal

----------------------------------------------------------------------------------------
### Mac address for Pi
pi1 d8:3a:dd:f3:3d:dd
pi2 d8:3a:dd:f2:84:6f
pi3 d8:3a:dd:e8:4b:a2

### Setup Nomachine for Pi

Download [Nomachine](https://downloads.nomachine.com/download/?id=109&distro=Raspberry&hw=Pi4)

Install the package by running

```
sudo dpkg -i nomachine_8.11.3_3_arm64.deb
```

Additionally, there is a reported issue with Wayland compositor, so disable Wayland and use X.org by

```
sudo raspi-config
Advanced Options -> Wayland -> X11 -> OK -> Finish -> Yes (to reboot)
```

----------------------------------------------------------------------------------------
## AWS

https://uiuc-education-tissenbaum.signin.aws.amazon.com/console
