# Tesi HRC – acquisizione dei segnali sulla persona

Primo pezzo del framework: la webcam registra la posa del corpo con MediaPipe e la salva su file.
Poi uno script calcola alcune prime "dimensioni" (velocità delle mani, pause, posizione della testa)
e confronta più sessioni, per esempio "mattina" e "sera".

## Struttura
 
```
tesi-hrc/
├── scarica_modelli.py        scarica i modelli di MediaPipe in models/
├── requirements.txt          librerie Python necessarie
├── src/
│   ├── acquisizione_pose.py  webcam (+ microfono) -> punti del corpo -> data/*_pose.csv
│   ├── registra_audio.py     registrazione del microfono sincronizzata con il video
│   ├── estrai_da_video.py    video -> viso (*_viso.csv) e mani (*_mani.csv)
│   └── analisi_sessione.py   CSV -> riepilogo e grafico di confronto
├── data/                     registrazioni (non vanno su Git)
└── models/                   modelli scaricati (non vanno su Git)
```

## Installazione (Windows, una volta sola)

1. Apri la cartella `tesi-hrc` in Visual Studio Code (**File → Apri cartella**).
2. Installa l'estensione **Python** di Microsoft, se non c'è già (icona dei quadratini a sinistra).
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

Registrare una sessione (si apre una finestra con il video). Durante la registrazione premi
**SPAZIO** per segnare un evento (es. inizio e fine di un compito) e **Q** per fermare:

```
python src/acquisizione_pose.py --sessione mattina --note "riposata, ore 9"
python src/acquisizione_pose.py --sessione sera --note "dopo una giornata di studio" --video --audio
```

Con `--video` salvi anche il video grezzo, utile per estrarre altri segnali più avanti (per esempio il viso).
Con `--audio` registri anche il microfono: a schermo compare il livello del suono, per controllare che funzioni.
Per usare un microfono diverso da quello predefinito: `python -m sounddevice` elenca i dispositivi,
poi aggiungi `--microfono <numero>`.

Estrarre viso e mani dai video registrati con `--video` (può richiedere qualche minuto):

```
python src/estrai_da_video.py data/*.mp4
```

Confrontare le sessioni:

```
python src/analisi_sessione.py data/*_mattina_pose.csv data/*_sera_pose.csv
```

Se esistono i file del viso e delle mani, la tabella include anche ammiccamenti al minuto, tempo con gli occhi chiusi,
sguardo verso il basso, sbadigli, visibilità delle mani e velocità delle dita.
Se esiste il file audio, anche rumore di fondo, livello medio e percentuale di tempo con suoni sopra il fondo.
Escono una tabella nel terminale, `data/riepilogo_sessioni.csv` e il grafico `data/confronto_sessioni.png`.

## Cosa contengono i file

- `*_pose.csv`: una riga per fotogramma con il tempo `t_s` (secondi dall'inizio) e, per ognuno dei 33 punti
  del corpo, `x` e `y` (posizione nell'immagine, da 0 a 1), `z` (profondità relativa) e `vis` (quanto il punto è visibile, da 0 a 1).
- `*_eventi.csv`: i momenti in cui hai premuto SPAZIO.
- `*_viso.csv`: per ogni fotogramma, i 52 valori del viso da 0 a 1 (es. `eyeBlinkLeft` = palpebra chiusa, `jawOpen` = bocca aperta).
- `*_mani.csv`: per ogni mano visibile, i 21 punti `p0` ... `p20` (p0 = polso, p4 = punta del pollice, p8 = punta dell'indice).
- `*_info.json`: durata, fotogrammi al secondo, note e versioni usate.
- `*.mp4`: il video grezzo, solo con `--video`.
- `*.wav`: l'audio del microfono (16 kHz, mono), solo con `--audio`.
- `*_audio_tempi.csv`: per ogni blocco di 100 ms di audio, il tempo del suo primo campione sullo stesso orologio del video.

## Consigli per registrare

- Webcam ferma, inquadratura dalla vita in su, con spalle e mani sempre visibili.
- Luce frontale, non alle spalle.
- Stesso compito, stessa posizione e stessa inquadratura in tutte le sessioni, così il confronto è corretto.

## Problemi frequenti

- **"Non riesco ad aprire la webcam"**: chiudi le altre app che la usano (Teams, Zoom) o prova `--camera 1`.
- **"Modello non trovato"**: esegui `python scarica_modelli.py`.
- **Errore di installazione di mediapipe**: controlla di essere nell'ambiente `tesi` (`conda activate tesi`) con Python 3.12.
