# Tesi HRC – acquisizione e analisi di segnali sulla persona

Framework in Python che, con webcam e microfono, raccoglie segnali su una persona mentre lavora
(corpo, mani, viso, orientamento della testa, emozioni, audio), li sincronizza sullo stesso orologio
e li trasforma in misure ("dimensioni") per sessione e per finestre di tempo.
Le misure a finestre sono la base per la profilazione della persona (per esempio stanchezza o vigilanza).

Funziona anche su video non registrati con questo progetto, per esempio quelli di un dataset pubblico:
in quel caso la posa del corpo viene estratta direttamente dal video.

## Struttura

```
tesi-hrc/
├── scarica_modelli.py         scarica i modelli di MediaPipe in models/
├── requirements.txt           librerie Python necessarie
├── DIARIO.md                  diario di bordo: decisioni prese e perché
├── src/
│   ├── acquisizione_pose.py   webcam (+ microfono) -> corpo in tempo reale, video, audio, eventi
│   ├── registra_audio.py      registrazione del microfono sincronizzata con il video
│   ├── estrai_da_video.py     video -> viso + orientamento della testa, mani (e corpo, se manca)
│   ├── estrai_emozioni.py     video -> emozioni, valenza e attivazione
│   ├── misure.py              tutte le misure, usate da entrambe le analisi
│   ├── analisi_sessione.py    riepilogo di sessioni intere + grafico di confronto
│   ├── analisi_finestre.py    misure ogni N secondi -> "tabella delle finestre"
│   └── elabora.py             comando unico: esegue i passaggi che mancano su uno o più video
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

### 2. Elaborare i video (comando unico)

```
python src/elabora.py data/*.mp4 --persona P01 --etichetta riposata
```

Per ogni video esegue solo i passaggi che mancano: posa, viso, testa e mani; emozioni; misure su
finestre di 30 secondi (file `*_finestre.csv`). Stampa anche un controllo di qualità
(fotogrammi al secondo e "salti" tra fotogrammi). Con `--forza` rifà tutto.
Il modello delle emozioni si scarica da solo al primo uso (circa 15 MB).

### 3. Analizzare

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

## Le misure

| Gruppo | Misure |
| --- | --- |
| Qualità | fotogrammi al secondo, salto massimo tra due fotogrammi, numero di salti oltre 0,5 s |
| Corpo | velocità delle mani (polsi), % di tempo con le mani ferme, altezza della testa sopra le spalle |
| Viso | ammiccamenti al minuto, % occhi chiusi, chiusura media degli occhi, sguardo in basso, sbadigli |
| Testa | inclinazione media su/giù (pitch) e variabilità di pitch, yaw e roll |
| Mani | % di tempo con le mani visibili, velocità della punta dell'indice |
| Emozioni | emozione prevalente, % neutro, valenza e attivazione medie |
| Audio | silenzio digitale %, rumore di fondo, livello medio, picco, % suoni sopra il fondo |

Le distanze del corpo sono divise per la larghezza delle spalle, quelle delle mani per la
grandezza della mano: così non dipendono dalla distanza dalla webcam.
Le velocità non vengono calcolate attraverso un "salto" tra fotogrammi.

## Cosa contengono i file di una sessione

- `*_pose.csv`: una riga per fotogramma con il tempo `t_s` e, per ognuno dei 33 punti del corpo,
  `x` e `y` (posizione nell'immagine, da 0 a 1), `z` (profondità relativa) e `vis` (visibilità, da 0 a 1).
- `*_eventi.csv`: i momenti in cui hai premuto SPAZIO.
- `*_viso.csv`: per ogni fotogramma, i 52 valori del viso da 0 a 1 (es. `eyeBlinkLeft` = palpebra chiusa,
  `jawOpen` = bocca aperta) e l'orientamento della testa in gradi: `testa_pitch` (su/giù),
  `testa_yaw` (destra/sinistra), `testa_roll` (testa inclinata).
- `*_mani.csv`: per ogni mano visibile, i 21 punti `p0` ... `p20` (p0 = polso, p4 = punta del pollice,
  p8 = punta dell'indice).
- `*_emozioni.csv`: un fotogramma ogni 5, con l'emozione prevalente, le probabilità di 8 emozioni,
  la valenza (espressione positiva o negativa) e l'attivazione (intensità).
  Modello: EmotiEffLib `enet_b0_8_va_mtl`, addestrato sul dataset AffectNet.
- `*_finestre.csv`: le misure ogni 30 secondi.
- `*_info.json`: durata, fotogrammi al secondo, note e versioni usate.
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
- **Errore di installazione di mediapipe**: controlla di essere nell'ambiente `tesi` (`conda activate tesi`) con Python 3.12.
