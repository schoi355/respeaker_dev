import usb.core
import usb.util
import pyaudio
import wave
import numpy as np
from tuning import Tuning
import json
import time

RESPEAKER_RATE = 16000
RESPEAKER_CHANNELS = 1 # change base on firmwares, 1_channel_firmware.bin as 1 or 6_channels_firmware.bin as 6
RESPEAKER_WIDTH = 2
# run getDeviceInfo.py to get index
RESPEAKER_INDEX = 5  # refer to input device id
CHUNK = 1024
RECORD_SECONDS = 1200 # enter seconds to run
WAVE_OUTPUT_FILENAME = "chunks/Jul28.wav" # enter filename here

# Assign a range of angles for each speaker 
def assign_angle(number):
	angle = int(20) # 20 deg 
	ang_dic = {}
	with open('assign_speaker/ID.json', 'r') as f:
		ID_data = json.load(f)
		if len(ID_data) == number:
			for key in ID_data:
				angle_range = [ID_data[key]['doa']-angle, ID_data[key]['doa']+angle]
				ang_dic[ID_data[key]['ID'][0]] = angle_range

			print('The range of angles are assigned:')
			print(ang_dic)
			return ang_dic

		else:
			print('The number of people does not match with the number of IDs')

def find_device():
	dev = usb.core.find(idVendor=0x2886, idProduct=0x0018)
	if dev is None:
		raise Exception("USB device not found.")
	return dev

def open_audio_stream(p):
	stream = p.open(
		rate=RESPEAKER_RATE,
		format=p.get_format_from_width(RESPEAKER_WIDTH),
		channels=RESPEAKER_CHANNELS,
		input=True,
		input_device_index=RESPEAKER_INDEX,
	)
	return stream

def record_audio(stream, p, dev, num):
	print("* recording")
	cur = 0
	wf1 = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
	wf1.setnchannels(1)
	wf1.setsampwidth(p.get_sample_size(p.get_format_from_width(RESPEAKER_WIDTH)))
	wf1.setframerate(RESPEAKER_RATE)

	data_list = []
	count = 1
	wf2 = wave.open("chunks/new_file_chunk_0.wav", 'wb')
	wf2.setnchannels(1)
	wf2.setsampwidth(p.get_sample_size(p.get_format_from_width(RESPEAKER_WIDTH)))
	wf2.setframerate(RESPEAKER_RATE)


	for i in range(0, int(RESPEAKER_RATE / CHUNK * RECORD_SECONDS)):
		data = stream.read(CHUNK)
		wf1.writeframes(data)
		wf2.writeframes(data)
		
		Mic_tuning = Tuning(dev)
		if count < RECORD_SECONDS:
			if i < RESPEAKER_RATE / CHUNK * count and i > RESPEAKER_RATE / CHUNK * (count - 1):
				# Get DOA
				doa = Mic_tuning.direction
				timestamp = time.time()

				# Assign a speaker with respect to DOA
				ang_dic = assign_angle(num)
				ID = 'unknown'
				for key in ang_dic:
					if ang_dic[key][0] <= doa <= ang_dic[key][1]:
						ID = key

				data_list.append({'doa': doa, 'timestamp': timestamp, 'record_time': count, 'speaker': ID})
				print("{:02d}".format(0) + ':' + "{:02d}".format(count) + ' ' + str(doa))
				count += 1

			#saving 10 second chunks
			if count != 0 and count % 10 == 0:
				wf2 = wave.open("chunks/new_file_chunk_" + str(count) + ".wav", 'wb')
				wf2.setnchannels(1)
				wf2.setsampwidth(p.get_sample_size(p.get_format_from_width(RESPEAKER_WIDTH)))
				wf2.setframerate(RESPEAKER_RATE)
				print("chunk saved")
				with open ('chunks/new_file_chunk_' + str(count) + '.json', 'w') as fj:
					json.dump(data_list,fj)

				
				

	print("* done recording")
	wf1.close()

	# Write data to a JSON file
	with open('chunks/full_json_for_chunks.json', 'w') as f:
		json.dump(data_list, f)

def close_audio_stream(stream, p):
	stream.stop_stream()
	stream.close()
	p.terminate()

def get_input():
	value = input("Type number of perople in the table:")
	return value


def main():
	num = get_input()
	num = int(num)
	dev = find_device()
	p = pyaudio.PyAudio()
	stream = open_audio_stream(p)
	record_audio(stream, p, dev, num)
	close_audio_stream(stream, p)

if __name__ == '__main__':
	main()

