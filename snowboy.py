import snowboydecoder
import sys
import signal
from transcribe import GoogleSpeech

interrupted = False

def signal_handler(signal, frame):
    global interrupted
    interrupted = True

def interrupt_callback():
    global interrupted
    return interrupted

detector = snowboydecoder.HotwordDetector("resources/kiwi.pmdl", sensitivity=0.5)

g=GoogleSpeech()
detector.start(detected_callback=g.main,              
               interrupt_check=interrupt_callback,
               sleep_time=0.03)

detector.terminate()
