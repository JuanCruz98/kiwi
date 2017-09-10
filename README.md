# Kiwi

Il tuo assistente personale.
 
 ## Requisiti hardware:

* Raspberry (Pi 2 o superiore)
* Memoria (non testato su 4GB, consigliato 8GB+)
* Speaker
* Microfono (Necessariamente USB perchè aux in input non lo elabora)
* Cavo Jack (Possibile utilizzare Bluetooth ma non testato)

 ## Extra utilizzati:
 
* Sonoff con firmware ESP Easy
* Powerbank per alimentazione Raspberry
* Lampada o altro da utilizzare con Sonoff
* ESP8266
* Sensori di temperatura e umidità

 ## Requisiti software:

* Raspbian o altre distribuzioni unix (non testate)
* Python (dovrebbe essere già installato)
* Account gratuito Google Cloud Platform
* Account gratuito Amazon Web Services
* Spotify Premium (Anche prova gratuita di x giorni)

 ## Configurazioni:

```
$ git clone https://github.com/JuanCruz98/kiwi.git (in una qualsiasi directory su Rasberry)
$ sudo apt-get update
$ sudo apt-get install build-essential python-dev python-pip
```
 ### Google Cloud SDK:
```

$ export CLOUD_SDK_REPO="cloud-sdk-$(lsb_release -c -s)"
$ echo "deb http://packages.cloud.google.com/apt $CLOUD_SDK_REPO main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
$ curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
$ sudo apt-get update && sudo apt-get install google-cloud-sdk
$ sudo apt-get install google-cloud-sdk-app-engine-python
$ sudo pip install google-cloud
$ sudo pip install --upgrade protobuf
$ gcloud init
```
premi [6] Create a new project
chiamalo come vuoi
```
$ gcloud beta auth login
$ sudo pip install -r requirements.txt
```

 ### Mopidy (server musicale):
```

$ wget -q -O - https://apt.mopidy.com/mopidy.gpg | sudo apt-key add -
$ sudo wget -q -O /etc/apt/sources.list.d/mopidy.list https://apt.mopidy.com/jessie.list
$ sudo apt-get update
$ sudo apt-get install mopidy
$ sudo apt-get install mopidy-spotify
$ mopidy per far partire il server
```

file di configurazione: ~/.config/mopidy/mopidy.conf
```

$ sudo dpkg-reconfigure mopidy per far partire il server come servizio (x avvio automatico al boot)
```

[$ sudo service mopidy status per vedere lo stato]
[$ sudo service mopidy start per farlo partire]
[$ sudo service mopidy stop per fermarlo]
[$ sudo service mopidy restart per riavviarlo]

file configurazione del servizio /etc/mopidy/mopidy.conf
```

$ sudo cp ~/.config/mopidy/mopidy.conf /etc/mopidy/
```

decommentare la sezione [file] e aggiungere in media_dirs = /home/pi/kiwi/musica o qualsiasi dir contentente musica per poterla riprodurre dal server
decommentare hostname nella sezione [mpd] e metterci indirizzo raspberry per poter accedere dall' esterno (esiste un client android chiamato MPDroid molto utile per verificare il funzionamento)

andare su 
https://www.mopidy.com/authenticate/#spotify
e generare chiave da aggiungere al file di configurazione

 ### Amazon Web Services:
```

$ sudo pip install awscli
```

andare su https://console.aws.amazon.com/iam/home?#/home
premere nel menu a sinistra "Users"
premere il pulsante "Add user"
dare un nome (es. admin)
spuntare "Programmatic access" su "Access type"
premere Next
Crea un gruppo e seleziona AdministratorAccess dall'elenco delle policy
Fare Next fino all'ultimo step e memorizzare le keys (quella secret sarà possibile visualizzarla solo una volta, ma è possibile ricrearla)

Guida creazione utente: http://docs.aws.amazon.com/IAM/latest/UserGuide/id_users_create.html
```

$ aws configure 
```

-aggiungere le keys precedentemente salvate
-default region name: eu-west-1
-default output: text
```

sudo apt-get install libatlas-base-dev
sudo apt-get install swig3.0 python-pyaudio python3-pyaudio sox
sudo apt-get install mplayer
```

