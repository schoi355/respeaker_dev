import sys
import json

def transcribe_file(speech_file, doa_file):
	"""Transcribe the given audio file."""
	from google.cloud import speech
	import io

	client = speech.SpeechClient()

	with io.open(speech_file, "rb") as audio_file:
		content = audio_file.read()

	audio = speech.RecognitionAudio(content=content)
	config = speech.RecognitionConfig(
		encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
		sample_rate_hertz=16000,
		language_code="en-US",
		enable_word_time_offsets=True,
	)

	response = client.recognize(config=config, audio=audio)
	f = open(doa_file)
	doa_data = json.load(f)
	new_dic = []


	# Each result is for a consecutive portion of the audio. Iterate through
	# them to get the transcripts for the entire audio file.
	for result in response.results:
		# The first alternative is the most likely one for this portion.
		print("Transcript: {}".format(result.alternatives[0].transcript))
		new_dic.append({"Transcript" : result.alternatives[0].transcript})
		for word in result.alternatives[0].words:
			audio_time = int(word.start_time.seconds)
			print(audio_time)
			for dic in doa_data:
				doa_time = dic['record_time']
				if doa_time - audio_time < 1 & doa_time - audio_time >= 0:
					new_dic.append({'Start time': word.start_time.seconds,
					'timestamp': dic['timestamp'], 'word' : word.word, 'DOA': dic['doa']})
					print("Start time: {}".format(word.start_time.seconds))
					print("Word: {}".format(word.word))
					print("DOA: {}".format(dic['doa']))
				else:
					continue

	with open('Feb20_transcript.json', 'w') as j:
		json.dump(new_dic, j)


def main():
	transcribe_file('Feb20.wav', 'Feb20.json')
	print('Transcription is done')

	
if __name__ == "__main__":
	main()