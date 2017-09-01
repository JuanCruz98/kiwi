#!/usr/bin/env python
# -*- coding: utf-8 -*-

from apiclient.discovery import build
from google.cloud import translate
import pprint
import getopt
import argparse
import json

def traduci(text, target):
 #   testo=raw_input("Testo: ")
	testo=text
        testo=testo.decode('utf-8') 
        service = build('translate', 'v2',
      
        developerKey='AIzaSyApHDP-O5n5iYhU8bsWfFrufdx4Xm2TjXM')
        
    #   fro=raw_input('Lingua di input (se vuoto rilevata automaticamente): ')
    #   to=raw_input('Lingua di output: ')
        fro="it"
        to=target
        traduzione = " "    
        try:
            if len(fro) == 0:
                jsonres = service.translations().list(target=to, q=[testo]).execute() 
            else:
                jsonres = service.translations().list(source=fro, target=to, q=[testo]).execute()
        
            traduzione =  jsonres['translations'][0]['translatedText']
        except:
            print "Errore", fro, to
    #   print jsonres
        return traduzione
