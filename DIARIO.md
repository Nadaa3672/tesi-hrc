# Diario di bordo

Le decisioni di progetto più importanti, con il motivo. Le voci più recenti sono in alto.

## 31 ottobre 2026 – v6.3: allineamento concentrato sulla scossa

- Terza prova webcam + orologio (30,6 s): orologio completo (copre il 100% della webcam, battito 71–85 bpm),
  misure degli arti plausibili (gomito ~102°, braccia a ~41°, polsi ~31 cm davanti alle spalle,
  busto non calcolabile perché le anche non si vedono). Ma l'allineamento fine falliva.
- Causa, vista sui dati veri: il polso si vedeva solo dal 2° al 20° secondo (meno dei 20 s richiesti), e
  confrontando tutta la registrazione la webcam vede spostamenti del polso che l'orologio (che misura
  rotazioni) non vede allo stesso modo: una ricerca su ±5 s dava anche un falso risultato al limite (−5,00 s).
- Correzione: l'orologio trova da solo la scossa (picco di rotazione nei primi 120 s) e il confronto si fa solo
  su quel tratto ±3 s; la velocità del polso nel video viene ripulita con una mediana mobile; uno sfasamento al
  limite dell'intervallo di ricerca viene scartato come inaffidabile.
- Risultato sulla prova vera: scossa trovata tra 13,05 e 14,23 s, polso destro, sfasamento +0,06 s
  (orologi di PC e telefono quasi coincidenti), correlazione 0,64. Sui dati sintetici: −0,40 / −1,20 / +2,30 s
  ritrovati esattamente (correlazione 0,96).

## 31 ottobre 2026 – v6.2: controlli sui dati dell'orologio

- Seconda prova webcam + orologio: la webcam ha registrato 57 s, ma l'orologio ha inviato dati solo
  dal secondo 40 al 46,6 (battito sempre 0). Le scosse (secondo 36) erano quindi fuori dai dati, eppure
  l'allineamento aveva restituito un risultato (−0,30 s, correlazione 0,67) calcolato su 6,6 s di dati: non affidabile.
- Ora `importa_orologio.py` controlla: (1) quanta parte della registrazione webcam è coperta dall'orologio
  (avviso sotto il 90%); (2) che nei dati dell'orologio ci sia davvero una scossa (rotazione > 3 rad/s);
  (3) almeno 20 s di dati in comune per l'allineamento fine. Altrimenti usa solo l'ora esatta e lo dice.
- Protocollo aggiornato: aprire Sensor Logger sull'orologio, aspettare che mostri il battito prima di avviare
  la webcam, alla fine aspettare qualche secondo prima di fermare e prima di esportare.
- Mattina e sera del 18/10 rielaborate con `--forza` (dopo l'interruzione): completate senza errori.
- Nota: muovere la webcam durante la registrazione cambia la "verticale" vista da MediaPipe e quindi
  gli angoli delle braccia e del busto: la webcam deve restare ferma per tutta la sessione.

## 31 ottobre 2026 – v6.1: file al sicuro dalle interruzioni

- Un'elaborazione interrotta (PC chiuso durante `elabora.py`) poteva lasciare file incompleti con il nome
  di quelli veri; alla ripresa venivano considerati "già presenti". Ora `estrai_da_video.py` ed
  `estrai_emozioni.py` scrivono in file `*.parziale` e li rinominano solo a lavoro finito.
  Provato simulando uno spegnimento a metà: restano solo i `.parziale`, e la ripresa rifà tutto.
- Le sessioni elaborate durante l'interruzione (mattina e sera del 18/10) vanno rifatte con `--forza`.
- Registrazione di prova webcam + orologio del 31/10: la profondità salvata in diretta funziona
  (`_pose3d.csv` presente, non ricalcolata). Lo zip di Sensor Logger conteneva solo i metadati, senza i dati
  dell'orologio (probabilmente esportato prima che l'orologio finisse di inviarli): messaggio d'errore più chiaro.

## 30 ottobre 2026 (sera) – v6: profondità, arti, smartwatch, dataset di Yasar

- **Dataset scelti** (dopo una ricerca: non esiste un dataset con corpo, fatica e stessa persona nel tempo):
  - dati propri da casa con fatica reale (webcam + smartwatch): dati principali;
  - **Yasar et al., Scientific Data 2024** (WSD4FEDSRM, Zenodo, CC BY 4.0): 34 persone, rotazioni della spalla
    fino allo sfinimento, sensori di movimento su mano/avambraccio/braccio, Borg ogni 10 s → per sviluppare
    l'analisi temporale sul sensore al polso;
  - OperatorEYEVP (Sensors 2023): link non più attivi, chiesti i dati agli autori.
- **Profondità**: si salvano i "world landmarks" di MediaPipe (`*_pose3d.csv`, metri, origine tra le anche).
  Motivo: angoli e velocità reali degli arti; nessuna libreria in più. Stima da una sola telecamera, quindi
  meno precisa di una camera RGB-D: va bene per confrontare la stessa persona nel tempo.
  Le sessioni vecchie la ottengono rielaborando il video (`elabora.py`).
- **Misure degli arti**: angolo dei gomiti e sua variabilità, elevazione delle braccia, % braccia alzate (> 45°),
  allungamento delle braccia, quanto i polsi stanno davanti alle spalle, inclinazione del busto (solo se le anche
  si vedono), velocità e variazione di velocità dei polsi in m/s.
- **Smartwatch**: Galaxy Watch4 + app **Sensor Logger** (Android/Wear OS). Prove del 30/10:
  - 1ª prova: buchi fino a 8 s e battito sempre 0 → risolti con batteria "senza restrizioni", permesso
    "sensori del corpo", cinturino aderente;
  - 2ª prova (93 s): dati presenti ~100%, battito valido dal 9° secondo (76–77 bpm a riposo, ~90 in attività).
  - I campioni arrivano ~80 al secondo e non regolari → ricampionati a **50 Hz**; battito 0 = dato mancante.
- **Allineamento orologio–video** (`importa_orologio.py`): (1) con l'ora esatta (nuovo `inizio_epoch_s` in
  `*_info.json`); (2) con le scosse del polso, confrontando la velocità del polso vista da MediaPipe con la
  rotazione misurata dall'orologio. Provato su dati sintetici costruiti dalla registrazione vera: sfasamenti
  di −0,40 s, −1,20 s e +2,30 s ritrovati esattamente (correlazione 0,94).
- **Stesse misure per orologio e Yasar** (`misure_orologio`): rotazione media e 95° percentile, % polso fermo,
  variabilità dell'accelerazione. Il "ritmo" (frequenza dominante) è stato tolto: su Yasar non cambiava con
  la fatica e nelle prove a scrivania non era stabile.
- **Risultato su Yasar** (avambraccio, finestre di 10 s, 34 persone, 203 prove, Borg mediano 9 → 19):
  rotazione media −13,5% (rho con Borg −0,52, concorde nel 76% delle prove); picchi −18,1% (rho −0,45).
  Limite: fatica e tempo crescono insieme, quindi questo non basta a separarli.

## 30 ottobre 2026 – Verifica dell'orientamento della testa

- Prova 1 (muovendo solo gli occhi): `testa_pitch` quasi fermo (tra 1° e 5°).
  Corretto: l'angolo misura la testa, non lo sguardo (lo sguardo è nei valori `eyeLook*` del viso).
- Prova 2 (muovendo la testa, medie ogni 5 s): dritto −7,2° → giù +23,4° → passaggio −8,0° → su −32,0° → dritto −1,4°;
  `testa_yaw` sempre entro ±1,2°.
  **Convenzione: pitch positivo = testa abbassata, negativo = testa alzata.** Escursione di circa 55° tra giù e su.
- Lo zero non è assoluto (con la testa dritta ≈ −7°, dipende da dove sta la webcam):
  nelle analisi conta il cambiamento rispetto alla stessa persona.

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
  Segno verificato il 30/10 (vedi sopra).
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
