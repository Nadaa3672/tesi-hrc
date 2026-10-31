# Tesi HRC – acquisizione e analisi di segnali sulla persona

Framework in Python che, con webcam, microfono e smartwatch, raccoglie segnali su una persona mentre
lavora (corpo e arti con la profondità, mani, viso, orientamento della testa, emozioni, audio, movimento
del polso e battito cardiaco), li sincronizza sullo stesso orologio e li trasforma in misure ("dimensioni")
per sessione e per finestre di tempo. Le misure a finestre sono la base per l'analisi nel tempo
della stessa persona (per esempio riposata e poi affaticata).

Funziona anche su video non registrati con questo progetto, per esempio quelli di un dataset pubblico:
in quel caso la posa del corpo viene estratta direttamente dal video. Contiene anche il lettore del
dataset pubblico di Yasar et al. (2024) sulla fatica del braccio, con le stesse misure dello smartwatch.

## Struttura

```
tesi-hrc/
├── scarica_modelli.py         scarica i modelli di MediaPipe in models/
├── requirements.txt           librerie Python necessarie
├── DIARIO.md                  diario di bordo: decisioni prese e perché
├── src/
│   ├── acquisizione_pose.py   webcam (+ microfono) -> corpo in tempo reale (anche in metri), video, audio, eventi
│   ├── registra_audio.py      registrazione del microfono sincronizzata con il video
│   ├── importa_orologio.py    smartwatch (zip di Sensor Logger) -> polso e battito, allineati al video
│   ├── estrai_da_video.py     video -> viso + orientamento della testa, mani (e corpo/profondità, se mancano)
│   ├── estrai_emozioni.py     video -> emozioni, valenza e attivazione
│   ├── misure.py              tutte le misure, usate da tutte le analisi
│   ├── analisi_sessione.py    riepilogo di sessioni intere + grafico di confronto
│   ├── analisi_finestre.py    misure ogni N secondi -> "tabella delle finestre"
│   ├── elabora.py             comando unico: esegue i passaggi che mancano su uno o più video
│   └── yasar.py               dataset di Yasar et al. -> tabella delle finestre con la fatica (Borg)
├── data/                      registrazioni (non vanno su Git)
└── models/                    modelli scaricati (non vanno su Git)
```

## Installazione (Windows, una volta sola)

1. Apri la cartella `tesi-hrc` in Visual Studio Code (**File → Apri cartella**).
2. Installa l'estensione **Python** di Microsoft, se non c'è già.
3. Apri il terminale di VS Code (**Terminale → Nuovo terminale**) e crea l'ambiente:

   ```
   conda create -n tesi python=3.12 -y
   conda activate tesi
   pip install -r requirements.txt
   python scarica_modelli.py
   ```

4. Di' a VS Code di usare questo ambiente: `Ctrl+Shift+P` → **Python: Select Interpreter** → scegli `tesi`.

Se il terminale dice che `conda` non è riconosciuto, apri invece **Anaconda Prompt** dal menu Start,
spostati nella cartella con `cd percorso\della\cartella\tesi-hrc` ed esegui gli stessi comandi.

## Uso

### 1. Registrare una sessione

Si apre una finestra con il video. Durante la registrazione premi **SPAZIO** per segnare un evento
(es. inizio e fine di un compito) e **Q** per fermare:

```
python src/acquisizione_pose.py --sessione mattina --video --audio --note "KSS 3, ore 9"
```

- `--video` salva il video grezzo: serve per estrarre viso, mani ed emozioni.
- `--audio` registra il microfono; a schermo compare il livello del suono.
  Per un microfono diverso da quello predefinito: `python -m sounddevice`, poi `--microfono <numero>`.

### 2. Registrare anche con lo smartwatch (facoltativo)

Serve l'app **Sensor Logger** sul telefono Android e sull'orologio Wear OS (es. Galaxy Watch4), con i
sensori dell'orologio attivi (Heart Rate, Wrist Motion). Una volta sola: sul telefono, batteria di Sensor
Logger "Senza restrizioni"; sull'orologio, permesso "Sensori del corpo" e cinturino ben aderente.

1. Sveglia l'orologio e apri Sensor Logger **sull'orologio**; avvia la registrazione (dal telefono o dall'orologio).
2. Aspetta che sull'orologio compaia il battito (non più 0): vuol dire che l'orologio sta registrando.
3. Avvia la webcam: `python src/acquisizione_pose.py --sessione prova --video`
4. Aspetta circa 10 secondi con le mani ferme.
5. **Scuoti il polso con l'orologio 3 volte davanti alla webcam** e premi SPAZIO: servirà ad allineare.
6. Svolgi il compito, con la webcam sempre ferma. Alla fine premi Q sulla webcam,
   aspetta 10 secondi e ferma Sensor Logger.
7. Prima di esportare, apri la registrazione nel telefono e controlla che i sensori "Watch" coprano
   tutta la durata (se mancano, aspetta un minuto: l'orologio può inviarli in ritardo).
8. Esporta in formato CSV (zip), copia lo zip sul PC e importalo nella sessione:

```
python src/importa_orologio.py percorso\dello\zip.zip --sessione data/20261031_101500_prova
```

Lo script porta i dati a 50 campioni al secondo, tratta il battito "0" come dato mancante e allinea
l'orologio al video: prima con l'ora esatta, poi con le scosse del polso. Stampa lo sfasamento trovato
e la correlazione (sopra 0,3 l'allineamento è affidabile). Avvisa se l'orologio copre meno del 90% della
registrazione webcam o se le scosse non sono nei suoi dati. Senza `--sessione` crea una sessione di solo orologio.

### 3. Elaborare i video (comando unico)

```
python src/elabora.py data/*.mp4 --persona P01 --etichetta riposata
```

Per ogni video esegue solo i passaggi che mancano: posa, profondità, viso, testa e mani; emozioni;
misure su finestre di 30 secondi (file `*_finestre.csv`), comprese quelle dell'orologio se è stato importato.
Le sessioni registrate con le versioni precedenti ottengono la profondità rielaborando il video. Stampa anche un controllo di qualità
(fotogrammi al secondo e "salti" tra fotogrammi). Con `--forza` rifà tutto.
Il modello delle emozioni si scarica da solo al primo uso (circa 15 MB).

### 4. Analizzare

Riepilogo di sessioni intere, con grafico:

```
python src/analisi_sessione.py data/*_mattina_pose.csv data/*_sera_pose.csv
```

Tabella delle finestre di più sessioni insieme (per la profilazione):

```
python src/analisi_finestre.py data/*_pose.csv --persona P01 --etichetta riposata
python src/analisi_finestre.py --elenco elenco_sessioni.csv --finestra 30
```

L'elenco è un CSV con le colonne `file, persona, etichetta`, una riga per sessione
(`file` = un qualunque file della sessione, anche il video). Le finestre in cui la persona
si vede per meno di metà del tempo vengono scartate.

### 5. Dataset di Yasar et al. (fatica del braccio)

Scarica `WSD4FEDSRM.zip` da https://zenodo.org/records/8415066 (licenza CC BY 4.0), estrailo
**fuori da OneDrive** e poi:

```
python src/yasar.py C:\percorso\WSD4FEDSRM
python src/yasar.py C:\percorso\WSD4FEDSRM --sensore Hand
```

Crea `data/yasar_finestre.csv` (finestre di 10 s con il valore Borg e le misure del polso) e stampa
quanto ogni misura segue la fatica nella stessa persona. Da citare: Yasar M.N. et al., "A dataset for
fatigue estimation during shoulder internal and external rotation movements using wearables",
Scientific Data (2024), doi:10.1038/s41597-024-03254-8.

## Le misure

| Gruppo | Misure |
| --- | --- |
| Qualità | fotogrammi al secondo, salto massimo tra due fotogrammi, numero di salti oltre 0,5 s |
| Corpo | velocità delle mani (polsi), % di tempo con le mani ferme, altezza della testa sopra le spalle |
| Arti (metri) | angolo medio dei gomiti e sua variabilità, elevazione delle braccia, % braccia alzate (> 45°), allungamento delle braccia, quanto i polsi stanno davanti alle spalle, inclinazione del busto (se le anche si vedono), velocità dei polsi in m/s (media e 95° percentile), variazione di velocità |
| Viso | ammiccamenti al minuto, % occhi chiusi, chiusura media degli occhi, sguardo in basso, sbadigli |
| Testa | inclinazione media su/giù (pitch) e variabilità di pitch, yaw e roll |
| Mani | % di tempo con le mani visibili, velocità della punta dell'indice |
| Emozioni | emozione prevalente, % neutro, valenza e attivazione medie |
| Audio | silenzio digitale %, rumore di fondo, livello medio, picco, % suoni sopra il fondo |
| Polso (orologio) | rotazione media e 95° percentile (rad/s), % polso fermo, variabilità dell'accelerazione, accelerazione senza gravità |
| Battito | battito medio e variabilità, % letture valide |

Le distanze del corpo nell'immagine sono divise per la larghezza delle spalle, quelle delle mani per la
grandezza della mano: così non dipendono dalla distanza dalla webcam. Le misure degli arti usano
la posa in metri stimata da MediaPipe: è una stima da una sola telecamera, adatta a confrontare
la stessa persona nel tempo più che a misure assolute.
Le velocità non vengono calcolate attraverso un "salto" tra fotogrammi.

## Cosa contengono i file di una sessione

- `*_pose.csv`: una riga per fotogramma con il tempo `t_s` e, per ognuno dei 33 punti del corpo,
  `x` e `y` (posizione nell'immagine, da 0 a 1), `z` (profondità relativa) e `vis` (visibilità, da 0 a 1).
- `*_pose3d.csv`: gli stessi 33 punti in **metri** ("world landmarks" di MediaPipe), con l'origine a metà
  tra le anche: `x` verso destra dell'immagine, `y` verso il basso, `z` più piccolo = più vicino alla webcam.
- `*_eventi.csv`: i momenti in cui hai premuto SPAZIO.
- `*_viso.csv`: per ogni fotogramma, i 52 valori del viso da 0 a 1 (es. `eyeBlinkLeft` = palpebra chiusa,
  `jawOpen` = bocca aperta) e l'orientamento della testa in gradi: `testa_pitch` (su/giù:
  positivo = testa abbassata, negativo = testa alzata; lo zero dipende dall'altezza della webcam),
  `testa_yaw` (destra/sinistra), `testa_roll` (testa inclinata).
- `*_mani.csv`: per ogni mano visibile, i 21 punti `p0` ... `p20` (p0 = polso, p4 = punta del pollice,
  p8 = punta dell'indice).
- `*_emozioni.csv`: un fotogramma ogni 5, con l'emozione prevalente, le probabilità di 8 emozioni,
  la valenza (espressione positiva o negativa) e l'attivazione (intensità).
  Modello: EmotiEffLib `enet_b0_8_va_mtl`, addestrato sul dataset AffectNet.
- `*_finestre.csv`: le misure ogni 30 secondi.
- `*_info.json`: durata, fotogrammi al secondo, note, versioni usate e ora esatta di inizio (`inizio_epoch_s`).
- `*_orologio.csv`: smartwatch a 50 campioni al secondo: `acc_*` accelerazione con la gravità (m/s²),
  `lin_*` senza gravità, `gyr_*` rotazione (rad/s), `grav_*` direzione della gravità; `t_s` sullo stesso
  orologio del video, `t_epoch` ora esatta. Vuoto (NaN) dove mancano dati.
- `*_battito.csv`: battito cardiaco (bpm) circa ogni secondo; vuoto dove l'orologio non l'ha letto.
- `*_orologio_info.json`: telefono, sfasamento trovato con le scosse, correlazione, % dati presenti.
- `*.mp4`: il video grezzo. `*.wav`: l'audio (16 kHz, mono).
- `*_audio_tempi.csv`: per ogni blocco di 100 ms di audio, il tempo del suo primo campione sullo stesso orologio del video.

## Consigli per registrare

- Webcam ferma, inquadratura dalla vita in su, con viso, spalle e mani sempre visibili.
- Luce frontale, non alle spalle.
- Stesso compito, stessa posizione e stessa inquadratura in tutte le sessioni.
- Windows: lasciare **disattivati i "Miglioramenti audio"** del microfono (Impostazioni → Sistema → Audio → Input).
  Altrimenti la soppressione del rumore azzera i silenzi. Il controllo `silenzio_digitale_%` deve restare vicino a 0.
- Evitare che altri programmi pesanti (o la sincronizzazione di OneDrive) lavorino durante la registrazione:
  causano "salti" tra fotogrammi.

## Problemi frequenti

- **"Non riesco ad aprire la webcam"**: chiudi le altre app che la usano (Teams, Zoom) o prova `--camera 1`.
- **"Modello non trovato"**: esegui `python scarica_modelli.py`.
- **L'orologio ha buchi nei dati o il battito è sempre 0**: batteria di Sensor Logger "Senza restrizioni"
  sul telefono, permesso "Sensori del corpo" sull'orologio, cinturino aderente, telefono vicino.
- **"Allineamento incerto"**: all'inizio scuoti il polso 3 volte ben visibile alla webcam; se serve,
  indica lo sfasamento a mano con `--sfasamento`.
- **Errore di installazione di mediapipe**: controlla di essere nell'ambiente `tesi` (`conda activate tesi`) con Python 3.12.
