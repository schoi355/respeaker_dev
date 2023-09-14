import json
import usb.core
import usb.util
import pyaudio
import wave
import numpy as np
from tuning import Tuning
import time
import os


RESPEAKER_RATE = 16000
RESPEAKER_CHANNELS = 1 # change base on firmwares, 1_channel_firmware.bin as 1 or 6_channels_firmware.bin as 6
RESPEAKER_WIDTH = 2
# run getDeviceInfo.py to get index
RESPEAKER_INDEX = 5  # refer to input device id
CHUNK = 1024
RECORD_SECONDS = 7 # enter seconds to run

def transcribe_file(audio_file, transcription_file):
	import whisper_timestamped as whisper

	# Transcribe audio file
	audio = whisper.load_audio(audio_file)
	model = whisper.load_model("base", device="cpu") # choose a model (tiny, base, small, medium, and large)
	result = whisper.transcribe(model, audio, language="En")
	with open(transcription_file, 'w') as t:
		json.dump(result, t)

def add_doa(doa_file, transcription_file):
	with open(transcription_file) as j:
		transcription = json.load(j)
	
	with open(doa_file) as d:
		doa = json.load(d)

	for seg in transcription['segments']:
		for word in seg["words"]:
			audio_time = float(word["start"])
			for dic in doa:
				doa_time = dic['record_time']
				
				if 0 <= audio_time - doa_time < 0.1:

					word.update({'DOA': dic['doa']})
					word.update({'speaker': dic['speaker']})
	
	with open(transcription_file, 'w') as j:
		json.dump(transcription, j)

	
def get_input():
	value = input("number of chunks: ")
	return value


def main():
	os.environ['KMP_DUPLICATE_LIB_OK']='True'

	iteration = 10
	input = get_input()
	input = int(input)
	# Start recording	
	while iteration <= input*10:
		
		audio_file         = 'chunks/chunk_%d.wav'%iteration
		transcription_file = 'chunks/transcription_chunk_%d.json'%iteration
		doa_file           = 'chunks/DOA_%d.json'%iteration
		# Transcribe the audio
		transcribe_file(audio_file, transcription_file)
		
		# Add DOA info on the transcription file
		add_doa(doa_file, transcription_file)
		
		
		print("Chunk " + str(iteration) + " is added")
		iteration += 10
	
	print("Transcription is done")
	


	
if __name__ == "__main__":
	main()