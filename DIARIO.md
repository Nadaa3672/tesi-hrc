# Diario di bordo

Le decisioni di progetto più importanti, con il motivo. Le voci più recenti sono in alto.

## 29 ottobre 2026 – Incontro 3: nuova direzione

- Il prof chiede di: (1) aggiungere la **profondità** (MediaPipe o modelli monoculari, anche se meno precisi);
  (2) aggiungere **sensori indossabili** (telefono, braccialetto); (3) poi passare all'**analisi di serie temporali**
  per confrontare la stessa persona prima e dopo e riconoscere che qualcosa è cambiato (es. stanchezza).
- Dimensione principale per ora: **gli arti**. Si lavora da casa; il laboratorio (camere RGB-D) eventualmente dopo.
- Il camminare non interessa in sé: conta lo stato della persona (stanca, affaticata), non l'attività.
- Dispositivi disponibili: telefono Android e **Samsung Galaxy Watch4** (Wear OS).
- Scenario di registrazione: seduta alla scrivania, parte alta del corpo (braccia, busto, testa) visibile.

## 29 ottobre 2026 – Fase 1: framework pronto per la profilazione

- **Misure su finestre di tempo** (`analisi_finestre.py`, default 30 s, senza sovrapposizione).
  Motivo: per profilare una persona serve vedere come cambia nel tempo, non un solo valore per sessione.
  Le finestre in cui la persona è visibile meno di metà del tempo vengono scartate.
- **Un solo modulo per le misure** (`misure.py`), usato sia dall'analisi per sessione sia da quella a finestre.
  Motivo: garantire che le due analisi calcolino le misure esattamente nello stesso modo.
- **Orientamento della testa** (pitch, yaw, roll) dalla matrice di trasformazione del Face Landmarker.
  Motivo: la testa che cade o ciondola è un segnale classico di sonnolenza.
  Da verificare il segno degli angoli con una prova (guardare in basso e poi in alto).
- **Controllo di qualità sui "salti" tra fotogrammi**: in un test c'era una pausa di circa 2 s.
  Le velocità non vengono più calcolate attraverso un salto (> 0,5 s), e l'analisi segnala i salti oltre 1 s.
  Effetto collaterale: "mani ferme %" ora è calcolata solo sui fotogrammi validi, quindi i valori possono
  differire leggermente da quelli delle versioni precedenti.
- **Estrazione da video qualunque**: se manca `*_pose.csv` la posa viene estratta dal video; funziona con
  qualunque estensione video. Motivo: poter usare dataset pubblici.
- **Comando unico** `elabora.py` che esegue solo i passaggi mancanti.

## 26–28 ottobre 2026 – Scelta dei dati per la profilazione

- Non esistono dataset pubblici su operatori che lavorano con robot con etichette sullo stato della persona.
  Si useranno dataset di domini affini come banco di prova, dichiarandolo nella tesi:
  - **UTA-RLDD** (Ghoddoosian et al., CVPR Workshops 2019): 60 persone, video da webcam o telefono,
    sveglio / poco vigile / assonnato (autovalutazione KSS). Copre viso, occhi, testa, emozioni.
  - **SWELL-KW** (Koldijk et al., ICMI 2014): stress nel lavoro d'ufficio. Non distribuisce i video, solo misure
    già estratte: serve per provare il metodo di profilazione su una seconda dimensione, non il framework.
- Scartati come principali i dataset di guida (DMD, UL-DD): le mani sono sul volante e il contesto è lontano dal lavoro manuale.
- Mani, corpo e audio durante un compito manuale: solo con dati propri o di volontari.

## 26 ottobre 2026 – Emozioni

- Modello **EmotiEffLib `enet_b0_8_va_mtl`** (EfficientNet-B0 addestrata su AffectNet), versione ONNX, in locale.
  Motivo: leggero, senza PyTorch, dà anche valenza e attivazione continue.
- Verificato con un test (sorriso, poi viso accigliato): felicità con valenza ≈ +0,8; rabbia con valenza ≈ −0,5
  e attivazione alta. Confermato l'ordine delle ultime due uscite (valenza, attivazione).
- Limite: il modello legge l'espressione, non lo stato d'animo (un viso serio può diventare "rabbia").

## 25 ottobre 2026 – Audio

- Registrazione con **sounddevice**, 16 kHz mono, blocchi da 100 ms con il tempo di ogni blocco.
- Problema trovato: i "Miglioramenti audio" di Windows azzeravano i silenzi (44% della registrazione).
  Disattivati; aggiunto il controllo `silenzio_digitale_%`.

## 18 ottobre 2026 – Pilota con stanchezza simulata

- Compito di origami (barchetta e aeroplano), una sessione da riposata e una con **stanchezza simulata**.
  Tutte le misure si muovono nella direzione attesa. Nessun valore statistico: serve a validare la pipeline.

## 17 ottobre 2026 – Prima versione

- **MediaPipe** (interfaccia Tasks; la vecchia `mp.solutions` non esiste più nelle versioni recenti)
  per corpo, viso e mani, in locale. Motivo: leggero, tempo reale su CPU, open source.
- Pipeline in tre fasi (acquisizione, estrazione dai video, analisi) e video grezzo sempre salvato,
  per poter estrarre nuovi segnali dalle registrazioni esistenti.
- Misure normalizzate per la larghezza delle spalle e la grandezza della mano.
