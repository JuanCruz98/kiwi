# -*- coding: utf-8 -*-
from __future__ import division
import contextlib
import functools
import re
import signal
import sys
import datetime
import collections
import snowboydetect
import time
import wave
import psutil
from os import listdir
from os.path import isfile, join, dirname, abspath
import logging
import grpc
import pyaudio
import urllib
import time
import json
import random
import googleEvents
import google.auth
import google.auth.transport.grpc
import google.auth.transport.requests
from GoogleTranslate import traduci

from calcoli import Operazioni
from googleEvents import getEvents
from aws import VoiceSynthesizer
from google.cloud.proto.speech.v1beta1 import cloud_speech_pb2
#TODO from google.cloud import speech 
from google.rpc import code_pb2
from six.moves import queue
from pygame import mixer
from subprocess import Popen, PIPE, call
#from PROVA import ytplayer
from threading import Thread, currentThread
from mpd import MPDClient
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
reload(sys)  
sys.setdefaultencoding('utf8') 
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms
DEADLINE_SECS = 60 * 3 + 5
SPEECH_SCOPE = 'https://www.googleapis.com/auth/cloud-platform'

logging.basicConfig()
logger = logging.getLogger("snowboy")
logger.setLevel(logging.INFO)
TOP_DIR = dirname(abspath(__file__))

RESOURCE_FILE = join(TOP_DIR, "resources/common.res")
DETECT_DING = join(TOP_DIR, "resources/ding.wav")
DETECT_DONG = join(TOP_DIR, "resources/dong.wav")
ip="192.168.1.81" #IP Raspberry per server musicale
ipSonoff="192.168.1.69"
accesa=True
interrupted=False
musica=False
service=None
sensibilita=0.6
keyword="kiwi.pmdl"
op=Operazioni()
events=getEvents()
#tr=translator()
languageDict = {'italiano': 'it', 'inglese': 'en', 'spagnolo': 'es', 'francese': 'fr', 'tedesco': 'de'}
voiceDict = {'inglese': 'Joanna', 'francese': 'Celine', 'tedesco': 'Vicki', 'spagnolo': 'Conchita'}
#dirMusica="resources/musica"
#nomeCanzoni = [f for f in listdir(dirMusica) if isfile(join(dirMusica, f))]
client = MPDClient()
try:
    client.connect(ip,"6600")
except:
    pass
client.clear()
client.stop()
client.close()
client.disconnect()

class RingBuffer(object):
    """Ring buffer to hold audio from PortAudio"""
    def __init__(self, size = 4096):
        self.buff = collections.deque(maxlen=size)

    def extend(self, data):
        """Adds data to the end of buffer"""
        self.buff.extend(data)
    def get(self):
        """Retrieves data from the beginning of buffer and clears it"""
        tmp = ''.join(self.buff)
        self.buff.clear()
        return tmp


def play_audio_file(fname=DETECT_DING):
    """Simple callback function to play a wave file. By default it plays
    a Ding sound.

    :param str fname: wave file name
    :return: None
    """
    ding_wav = wave.open(fname, 'rb')
    ding_data = ding_wav.readframes(ding_wav.getnframes())
    audio = pyaudio.PyAudio()
    stream_out = audio.open(
        format=audio.get_format_from_width(ding_wav.getsampwidth()),
        channels=ding_wav.getnchannels(),
        rate=ding_wav.getframerate(), input=False, output=True)
    stream_out.start_stream()
    stream_out.write(ding_data)
    time.sleep(0.2)
    stream_out.stop_stream()
    stream_out.close()
    audio.terminate()


class HotwordDetector(object):
    """
    Snowboy decoder to detect whether a keyword specified by `decoder_model`
    exists in a microphone input stream.

    :param decoder_model: decoder model file path, a string or a list of strings
    :param resource: resource file path.
    :param sensitivity: decoder sensitivity, a float of a list of floats.
                              The bigger the value, the more senstive the
                              decoder. If an empty list is provided, then the
                              default sensitivity in the model will be used.
    :param audio_gain: multiply input volume by this factor.
    """
    def __init__(self, decoder_model,
                 resource=RESOURCE_FILE,
                 sensitivity=[],
                 audio_gain=1):

        def audio_callback(in_data, frame_count, time_info, status):
            self.ring_buffer.extend(in_data)
            play_data = chr(0) * len(in_data)
            return play_data, pyaudio.paContinue

        tm = type(decoder_model)
        ts = type(sensitivity)
        if tm is not list:
            decoder_model = [decoder_model]
        if ts is not list:
            sensitivity = [sensitivity]
        model_str = ",".join(decoder_model)

        self.detector = snowboydetect.SnowboyDetect(
            resource_filename=resource, model_str=model_str)
        self.detector.SetAudioGain(audio_gain)
        self.num_hotwords = self.detector.NumHotwords()

        if len(decoder_model) > 1 and len(sensitivity) == 1:
            sensitivity = sensitivity*self.num_hotwords
        if len(sensitivity) != 0:
            assert self.num_hotwords == len(sensitivity), \
                "number of hotwords in decoder_model (%d) and sensitivity " \
                "(%d) does not match" % (self.num_hotwords, len(sensitivity))
        sensitivity_str = ",".join([str(t) for t in sensitivity])
        if len(sensitivity) != 0:
            self.detector.SetSensitivity(sensitivity_str);

        self.ring_buffer = RingBuffer(
            self.detector.NumChannels() * self.detector.SampleRate() * 5)    
        self.audio = pyaudio.PyAudio()
        global stream_in
        stream_in = self.audio.open(
            input=True, 
            output=False,
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            frames_per_buffer=1600,
            stream_callback=audio_callback)

    def start(self, detected_callback=play_audio_file,
              interrupt_check=lambda: False,
              sleep_time=0.03):
        """
        Start the voice detector. For every `sleep_time` second it checks the
        audio buffer for triggering keywords. If detected, then call
        corresponding function in `detected_callback`, which can be a single
        function (single model) or a list of callback functions (multiple
        models). Every loop it also calls `interrupt_check` -- if it returns
        True, then breaks from the loop and return.

        :param detected_callback: a function or list of functions. The number of
                                  items must match the number of models in
                                  `decoder_model`.
        :param interrupt_check: a function that returns True if the main loop
                                needs to stop.
        :param float sleep_time: how much time in second every loop waits.
        :return: None
        """
        if interrupt_check():
            logger.debug("detect voice return")
            return

        tc = type(detected_callback)
        if tc is not list:
            detected_callback = [detected_callback]
        if len(detected_callback) == 1 and self.num_hotwords > 1:
            detected_callback *= self.num_hotwords

        assert self.num_hotwords == len(detected_callback), \
            "Error: hotwords in your models (%d) do not match the number of " \
            "callbacks (%d)" % (self.num_hotwords, len(detected_callback))

        logger.debug("detecting...")

        while True:
            if interrupt_check():
                logger.debug("detect voice break")
                break
            data = self.ring_buffer.get()
            if len(data) == 0:
                time.sleep(sleep_time)
                continue

            ans = self.detector.RunDetection(data)
            if ans == -1:
                logger.warning("Error initializing streams or reading audio data")
            elif ans > 0:
                message = "Keyword " + str(ans) + " detected at time: "
                message += time.strftime("%Y-%m-%d %H:%M:%S",
                                         time.localtime(time.time()))
                logger.info(message)
                self.audio.terminate()
                callback = detected_callback[ans-1]
                if callback is not None:
                    callback()

        logger.debug("finished.")

    def terminate(self):
        """
        Terminate audio stream. Users cannot call start() again to detect.
        :return: None
        """
        self.stream_in.stop_stream()
        self.stream_in.close()
        self.audio.terminate()

 
      
class GoogleSpeech:

    def signal_handler(self,signal, frame):
        global interrupted
        interrupted = True

    def interrupt_callback(self):
        global interrupted
        return interrupted
        
    def make_channel(self, host, port):
        print ("open channel")
        """Creates a secure channel with auth credentials from the environment."""
        # Grab application default credentials from the environment
        credentials, _ = google.auth.default(scopes=[SPEECH_SCOPE])

        # Create a secure channel using the credentials.
        http_request = google.auth.transport.requests.Request()
        target = '{}:{}'.format(host, port)

        return google.auth.transport.grpc.secure_authorized_channel(
            credentials, http_request, target)
        print ("close channel")

    def _audio_data_generator(self, buff):
        print ("start audio_data")
        play_audio_file()
        """A generator that yields all available data in the given buffer.

        Args:
            buff - a Queue object, where each element is a chunk of data.
        Yields:
            A chunk of data that is the aggregate of all chunks of data in `buff`.
            The function will block until at least one data chunk is available.
        """
        stop = False
        while not stop:
            # Use a blocking get() to ensure there's at least one chunk of data.
            data = [buff.get()]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    data.append(buff.get(block=False))
                except queue.Empty:
                    break

            # `None` in the buffer signals that the audio stream is closed. Yield
            # the final bit of the buffer and exit the loop.
            if None in data:
                stop = True
                data.remove(None)

            yield b''.join(data)
        print ("close audio_data")

    def _fill_buffer(self, buff, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        buff.put(in_data)
        return None, pyaudio.paContinue


    # [START audio_stream]
    @contextlib.contextmanager
    def record_audio(self, rate, chunk):
        print ("start record")
        """Opens a recording stream in a context manager."""
        # Create a thread-safe buffer of audio data
        buff = queue.Queue()

        self.audio_interface = pyaudio.PyAudio()
        global audio_stream
        audio_stream = self.audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1, rate=rate,
            input=True, frames_per_buffer=chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't overflow
            # while the calling thread makes network requests, etc.
            stream_callback=functools.partial(self._fill_buffer, buff),
        )
        yield self._audio_data_generator(buff)

        audio_stream.stop_stream()
        audio_stream.close()
        # Signal the _audio_data_generator to finish
        buff.put(None)
        self.audio_interface.terminate()

    def request_stream(self, data_stream, rate, interim_results=True):
        print ("start request_stream")
        """Yields `StreamingRecognizeRequest`s constructed from a recording audio
        stream.

        Args:
            data_stream: A generator that yields raw audio data to send.
            rate: The sampling rate in hertz.
            interim_results: Whether to return intermediate results, before the
                transcription is finalized.
        """
        # The initial request must contain metadata about the stream, so the
        # server knows how to interpret it.
        recognition_config = cloud_speech_pb2.RecognitionConfig(
            # There are a bunch of config options you can specify. See
            # https://goo.gl/KPZn97 for the full list.
            encoding='LINEAR16',  # raw 16-bit signed LE samples
            sample_rate=rate,  # the rate in hertz
            # See http://g.co/cloud/speech/docs/languages
            # for a list of supported languages.
            language_code='it-IT',  # a BCP-47 language tag
        )
        streaming_config = cloud_speech_pb2.StreamingRecognitionConfig(
            interim_results=interim_results,
            config=recognition_config,
        )

        yield cloud_speech_pb2.StreamingRecognizeRequest(
            streaming_config=streaming_config)

        for data in data_stream:
            # Subsequent requests can all just have the content
            yield cloud_speech_pb2.StreamingRecognizeRequest(audio_content=data)  


    def listen_print_loop(self, recognize_stream):
        print ("start listen_print")
        global musica
        global accesa
        global sensibilita
        global keyword
        
       
        """Iterates through server responses and prints them.

        The recognize_stream passed is a generator that will block until a response
        is provided by the server. When the transcription response comes, print it.

        In this case, responses are provided for interim results as well. If the
        response is an interim one, print a line feed at the end of it, to allow
        the next result to overwrite it, until the response is a final one. For the
        final one, print a newline to preserve the finalized transcription.
        """
        num_chars_printed = 0
        for resp in recognize_stream:
            if resp.error.code != code_pb2.OK:
                raise RuntimeError('Server error: ' + resp.error.message)

            if not resp.results:
                continue

            # Display the top transcription
            result = resp.results[0]
            transcript = result.alternatives[0].transcript

            # Display interim results, but with a carriage return at the end of the
            # line, so subsequent lines will overwrite them.
            #
            # If the previous result was longer than this one, we need to print
            # some extra spaces to overwrite the previous result
            overwrite_chars = ' ' * max(0, num_chars_printed - len(transcript))
            synthesizer = VoiceSynthesizer(1.0)
            if not result.is_final:
                sys.stdout.write(transcript + overwrite_chars + '\r')
                sys.stdout.flush()

                num_chars_printed = len(transcript)
                
                if re.search(r'\b(no|stop)\b', transcript, re.I):
                    self.audio_interface.terminate()
                    if musica:
                        mixer.music.stop()
                    play_audio_file(fname=DETECT_DONG)
                    self.main()
                 
                    
                if re.search(r'\b(ciao)\b', transcript, re.I):
                    audio_stream.stop_stream()
                    synthesizer.say("Ciao capo!")
                    self.audio_interface.terminate()
                    self.main()
                         
                ora=datetime.datetime.now().strftime("%H:%M")
                if re.search(r'\b(ore sono|ora &egrave)\b', transcript, re.I):
                    audio_stream.stop_stream()
                    synthesizer.say('Sono le '+ str(ora))
                    self.audio_interface.terminate()
                    self.main()
                    
                if re.search(r'\b(ok Google|hey Cortana)\b', transcript, re.I):
                    audio_stream.stop_stream()
                    synthesizer.say('Davvero molto spiritoso, franco.')
                    self.audio_interface.terminate()
                    self.main()
                                      
                
                if re.search(r'\b(ventilatore|lampada|luce)\b', transcript, re.I):
                    audio_stream.stop_stream()
                    try:
                        accesa=False
                        url = "http://"+ipSonoff+"/json"
                        response = urllib.urlopen(url)
                        data = json.loads(response.read())
                        if data['Sensors'][0]['Relay']>0:
                            accesa=True
                        elif data['Sensors'][0]['Relay']<1:
                            accesa=False
                    except: 
                        synthesizer.say('Non riesco a comunicare con il dispositivo')
            
                    if "spegni" in transcript or "spegnere" in transcript:
                        try:
                            if (accesa):
                                content = urllib.urlopen('http://'+ipSonoff+'/control?cmd=GPIO,12,0')
                                synthesizer.say('Fatto.')
                                accesa=False
                            else:
                                synthesizer.say('La luce è già spenta.')
                        except:
                            synthesizer.say('Non riesco a comunicare con la luce')
                    elif "accendi" or "accendere" in transcript:
                        try:
                            if(not accesa):
                                content = urllib.urlopen('http://'+ipSonoff+'/control?cmd=GPIO,12,1')
                                synthesizer.say('Fatto.')
                                accesa=True
                            else:
                                synthesizer.say('La luce è già accesa.')
                        except:
                            synthesizer.say('Non riesco a comunicare con la luce')
                    else:
                        synthesizer.say("Non ho capito.")

                    self.audio_interface.terminate()
                    self.main()
                    
                if re.search(r'\b(eventi|appuntamenti)\b', transcript, re.I):
                    audio_stream.stop_stream()
                    list_events= events.main()
                    if 'Nessun' in list_events:
                        synthesizer.say(list_events)
                        self.audio_interface.terminate()
                        self.main()
                    a=[]
                    for event in list_events:
                        a.append(str(event))
                        
                    for x in a:
                        vocal=x.split(":")
                        b=x.split(" ",1)
                        synthesizer.say("Alle "+ vocal[0]+ " e "+ vocal[1] + " hai "+ b[1])
                    self.audio_interface.terminate()
                    self.main() 
                    
                if re.search(r'\b(gradi|temperatura)\b', transcript, re.I):
                    audio_stream.stop_stream()
                    try:
                        url = "http://172.22.20.140/json"
                        response = urllib.urlopen(url)
                        data = json.loads(response.read())
                        print data
                        synthesizer.say("Ci sono " + str(data['Sensors'][0]['Temperature']) + " gradi centigradi " + "e l'umidità è al " + str(data['Sensors'][0]['Humidity'])+ " percento" )
                    except: 
                        synthesizer.say('Non riesco a leggere i dati.')
                    self.audio_interface.terminate()
                    self.main() 

            else:
                print(transcript + overwrite_chars)
                if re.search(r'\b(quanto fa)\b', transcript, re.I):
                    audio_stream.stop_stream()
                    if "meno" in transcript or "-" in transcript: 
                        synthesizer.say(op.sottrazione(transcript))
                    elif "più" in transcript or "+" in transcript: 
                        synthesizer.say(op.somma(transcript))
                    elif "diviso" in transcript or  "/" in transcript: 
                       synthesizer.say(op.divisione(transcript))
                    elif "per"  in transcript or "x" in transcript  or "*" in transcript:
                        print ("per")
                        synthesizer.say(op.moltiplicazione(transcript))
                    else: 
                        synthesizer.say("Non ho capito.")
                    self.audio_interface.terminate()
                    self.main()

                elif re.search(r'\b(riproduci)\b', transcript.lower(), re.I):
                    audio_stream.stop_stream()
                    try:
                        titolo=transcript.lower().split("riproduci ")
                        print titolo[1]
                        client.connect(ip, 6600)
                        client.clear()
                        print (client.searchadd("any",titolo[1]))
                        client.play()
                        client.close()
                        client.disconnect()
                        keyword="kiwi.pmdl"
                        musica=True
                        sensibilita=0.4
                    except:
                        synthesizer.say("Non ho capito")

                    self.audio_interface.terminate()
                    self.main()
                    
                elif re.search(r'\b(traduci)\b', transcript, re.I):
                    audio_stream.stop_stream()
                    try:
                        lang= transcript.rsplit("in ",1) #reverse split, prende ultimo in
                        testo=lang[0].split("traduci")
                        lingua=voiceDict[lang[1]]
			traduzione=traduci(testo[1],languageDict[lang[1]])
                        print traduzione
                        synthesizer.say(traduzione,lingua)
                    except Exception,e: 
                        print str(e)
                        synthesizer.say("Non ho capito bene")
                    self.audio_interface.terminate()
                    self.main()
                else:
                    audio_stream.stop_stream()
                    synthesizer.say("Non ho capito.")
                    self.audio_interface.terminate()
                    self.main()
                    
                num_chars_printed = 0


    def ascolto(self):
        global musica
        global service
        global keyword
        global sensibilita
        global service

        if musica:
            print "musica"
            try:
                client.connect(ip, 6600)
                client.stop()
                client.close()
                client.disconnect()
                keyword="kiwi.pmdl"
                musica=False
                sensibilita=0.5
            except:
                print "errore stop musica"
                pass
        # For streaming audio from the microphone, there are three threads.
        # First, a thread that collects audio data as it comes in
        with self.record_audio(RATE, CHUNK) as buffered_audio_data:
            # Second, a thread that sends requests with that data
            
            global requests
            requests = self.request_stream(buffered_audio_data, RATE)
            # Third, a thread that listens for transcription responses
            recognize_stream = service.StreamingRecognize(
                requests, DEADLINE_SECS)

            # Exit things cleanly on interrupt
            signal.signal(signal.SIGINT, lambda *_: recognize_stream.cancel())

            # Now, put the transcription responses to use.
            try:
                self.listen_print_loop(recognize_stream)
                recognize_stream.cancel()
            except grpc.RpcError as e:
                code = e.code()
                print "errore"
                service = cloud_speech_pb2.SpeechStub(
                self.make_channel('speech.googleapis.com', 443))
                audio_stream.stop_stream()
                self.audio_interface.terminate()
                self.ascolto()
                # CANCELLED is caused by the interrupt handler, which is expected.
                if code is not code.CANCELLED:
                    raise
       

    def main(self):
        global keyword
        global sensibilita
        detector = HotwordDetector(join(TOP_DIR, "resources/"+keyword), sensitivity=sensibilita)
        detector.start(detected_callback=self.ascolto,
                       interrupt_check=self.interrupt_callback,
                       sleep_time=0.03)
        detector.terminate()    
    
                    
assistant=GoogleSpeech()
service = cloud_speech_pb2.SpeechStub(
                assistant.make_channel('speech.googleapis.com', 443))

assistant.main()
