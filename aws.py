
from boto3 import Session
from botocore.exceptions import BotoCoreError, ClientError
from contextlib import closing
import os
import sys
import subprocess
from tempfile import gettempdir

class VoiceSynthesizer(object):
    def __init__(self, volume=1.0):
       self._volume = volume
       session = Session(profile_name="default")
       self.__polly = session.client("polly")
 
    def _getVolume(self):
       return self._volume
 
    def say(self, text, voice="Carla"):
       self._synthesize(text, voice)

    def _synthesize(self, text, voice):
		try:
			# Request speech synthesis
			response = self.__polly.synthesize_speech(Text=text, 
			              OutputFormat="mp3", VoiceId=voice)
		except (BotoCoreError, ClientError) as error:
			# The service returned an error, exit gracefully
			print(error)
			sys.exit(-1)

		# Access the audio stream from the response
		if "AudioStream" in response:
			# Note: Closing the stream is important as the service throttles on the
			# number of parallel connections. Here we are using contextlib.closing to
			# ensure the close method of the stream object will be called automatically
			# at the end of the with statement's scope.
			with closing(response["AudioStream"]) as stream:
				output = os.path.join(gettempdir(), "speech.mp3")

				try:
					# Open a file for writing the output as a binary stream
					with open(output, "wb") as file:
						file.write(stream.read())
				except IOError as error:
					# Could not write to file, exit gracefully
					print(error)
					sys.exit(-1)

		else:
			# The response didn't contain audio data, exit gracefully
			print("Could not stream audio")
			sys.exit(-1)

		opener = "mplayer"
		subprocess.call([opener, output])
