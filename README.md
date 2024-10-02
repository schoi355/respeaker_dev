# respeaker_dev

This repository is under development for
 - Transcribe conversation using whisper
 - Identify speakers' Direction of Angle (DOA) usign Respeaker device

## 1. Setup

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

Install sounddevice for Pi
```
pip install sounddevice
```

### Set up Whisper (language model)

Install [whisper-timestamped](https://github.com/linto-ai/whisper-timestamped)
```
pip install git+https://github.com/linto-ai/whisper-timestamped
```

To setup insanely fast whisper:

Install insanely-fast-whisper using pipx:

```pipx install insanely-fast-whisper --force
```

Run transcribe_chunk_fast.py 

### Set up Flask
```
pip install flask nltk spacy
python -m spacy download en_core_web_sm
```

### Set up AWS
```
pip install boto3
```

### Set up remote control using Nomachine

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

In Nomachine on pi side, disable audio device.
```
Go to settings in Nomachine -> server -> devices -> Uncheck 'USB devices' and uncheck 'enable audio streaming and microphone forwarding'
```


## 2. How to use

Before running any python script, get the Respeaker device index by running `get_index.py`
```
$ python get_index.py 
``` 

This gives you what index the device is using. Put the number of Respeaker device to `RESPEAKER_INDEX` in `record_DOA_ID_chunks_pi.py`

First, edit the folder name in `setup.sh`. Then, run `setup.sh` to activate the virtual environment and create a data folder.
```
source setup.sh
```

Next, put the same folder name in `record.sh`, `transcribe.sh`, and `flask.sh`. Then, run `run_scripts.sh` to open three terminals and run `record_DOA_ID_chunks_pi.py`, `transcribe_chunk_pi.py`, and `flask_prep_pi_dynamoDB.py`.
```
source run_scripts.sh
```

The next step is to calibrate the DOA angles for each speaker. In one of the terminals, you will be prompted with 'add ID' or 'stop'. By typing add ID, the speaker will speak for 8 seconds to determine the angle from the voice. When all speakers are calibrated, type `stop`, then it starts recording.

----------------------------------------------------------------------------------------
## 3. Miscellaneous (in progress)

### Mac address for Pi
pi1 d8:3a:dd:f3:3d:dd
pi2 d8:3a:dd:f2:84:6f
pi3 d8:3a:dd:e8:4b:a2

----------------------------------------------------------------------------------------
### AWS URL

https://uiuc-education-tissenbaum.signin.aws.amazon.com/console

----------------------------------------------------------------------------------------
### Buttonshim
- Enable I2C communication.
```
sudo raspi-config
```
Select Interfacing options -> I2C, choose <Yes> and hit Enter, then go to Finish and reboot.

- Install Buttonshim.
Activate the virtual environment. Then, install buttonshim. Refer to [buttonshim](https://github.com/pimoroni/button-shim).

```
curl https://get.pimoroni.com/buttonshim | bash
```

On Raspberian,
```
sudo apt-get install python3-buttonshim
venv/bin/pip install buttonshim smbus
```
----------------------------------------------------------------------------------------
### LCD display
- Enable I2C communication.
```
sudo raspi-config
```
Select Interfacing options -> I2C, choose <Yes> and hit Enter, then go to Finish and reboot.

Type the command to scan the I2C bus for a connected device:
```
sudo i2cdetect -y 1
```
The output should display the address of the I2C backpack (usually 0x27 or 0x3F). Please make a note of this address, as you will need it later.

```
venv/bin/pip install RPLCD
```
----------------------------------------------------------------------------------------

### OLED display with buttons and joystick
- Enable I2C communication.
```
sudo raspi-config
```
Select Interfacing options -> I2C, choose <Yes> and hit Enter. Then, navigate to Interface Options -> P1 GPIO and ensure GPIO is enabled.
Then go to Finish and reboot.

Type the command to scan the I2C bus for a connected device:
```
sudo i2cdetect -y 1
```
The output should display the address of the I2C backpack (usually 0x27 or 0x3F). Please make a note of this address, as you will need it later.

```
venv/bin/pip install adafruit-circuitpython-ssd1306
sudo apt-get tinstall python3-pil
```
Note that Adafruit Blinka uses libgpiod for Pi 5 rather than RPi.GPIO on the Pi 4. Intall this
```
venv/bin/pip install gpiod
```

Pi 5 usually uses `gpiochip4` for the GPIO. You can see the list of pins by running
```
sudo gpioinfo gpiochip4
```

----------------------------------------------------------------------------------------
### Analysis

/check_speakers_not_spoken: not accumlate time, call this url every 60 sec..
check_speakers_not_spoken: first table: 0 - 60 sec, second: 60 - 120 sec, ...

/analysis: accumulate time, call this url every 300 sec.
word_counts
first_words_spoken: 
ex) First table: 0 - 300 sec, second table: 0 - 600 sec, ... 
