"""Registrazione dell'audio dal microfono, sullo stesso orologio del video.

Il microfono lavora in parallelo (su un thread separato gestito da sounddevice):
ogni 100 ms consegna un blocco di campioni, che mettiamo in una coda.
Il ciclo principale dello script di acquisizione svuota la coda e scrive
i campioni in un file WAV.

Per ogni blocco salviamo anche il tempo (in secondi dall'inizio della
registrazione) del suo primo campione, nel file *_audio_tempi.csv:
così audio, posa, viso e mani si possono allineare con precisione.

Per vedere quali microfoni ci sono:   python -m sounddevice
"""

import csv
import queue
import time
import wave

import numpy as np

FREQUENZA = 16000      # campioni al secondo: sufficiente per voce e rumore
DURATA_BLOCCO = 0.1    # secondi per blocco


def livello_dbfs(campioni_int16):
    """Livello del suono in dBFS: 0 = massimo registrabile, valori più negativi = più silenzio."""
    x = np.asarray(campioni_int16, dtype=np.float64).ravel() / 32768.0
    rms = np.sqrt(np.mean(x ** 2)) if x.size else 0.0
    return 20 * np.log10(rms + 1e-10)


class RegistratoreAudio:
    def __init__(self, base, inizio, dispositivo=None):
        self.percorso_wav = str(base) + ".wav"
        self.percorso_tempi = str(base) + "_audio_tempi.csv"
        self.inizio = inizio            # stesso time.perf_counter() del video
        self.dispositivo = dispositivo  # None = microfono predefinito
        self.coda = queue.Queue()
        self.campioni_scritti = 0
        self.problemi = 0               # blocchi con avvisi (es. dati persi)
        self.flusso = None
        self.ultimo_db = None           # livello dell'ultimo blocco, da mostrare a schermo

    def _ricevi(self, dati, n_campioni, info_tempo, stato):
        """Chiamata da sounddevice ogni volta che arriva un blocco di audio."""
        arrivo = time.perf_counter() - self.inizio
        if stato:
            self.problemi += 1
        # tempo stimato del primo campione del blocco
        self.coda.put((arrivo - n_campioni / FREQUENZA, dati.copy()))

    def avvia(self):
        import sounddevice as sd  # importato qui: serve solo se si registra l'audio
        self.file_wav = wave.open(self.percorso_wav, "wb")
        self.file_wav.setnchannels(1)
        self.file_wav.setsampwidth(2)  # 16 bit
        self.file_wav.setframerate(FREQUENZA)
        self.file_tempi = open(self.percorso_tempi, "w", newline="")
        self.scrittore_tempi = csv.writer(self.file_tempi)
        self.scrittore_tempi.writerow(["campione_iniziale", "t_s"])
        self.flusso = sd.InputStream(samplerate=FREQUENZA, channels=1, dtype="int16",
                                     blocksize=int(FREQUENZA * DURATA_BLOCCO),
                                     device=self.dispositivo, callback=self._ricevi)
        self.flusso.start()

    def svuota(self):
        """Scrive su file i blocchi arrivati. Va chiamata spesso (ogni fotogramma)."""
        while True:
            try:
                t_s, dati = self.coda.get_nowait()
            except queue.Empty:
                return
            self.scrittore_tempi.writerow([self.campioni_scritti, round(t_s, 4)])
            self.file_wav.writeframes(dati.astype(np.int16).tobytes())
            self.campioni_scritti += len(dati)
            self.ultimo_db = livello_dbfs(dati)

    def ferma(self):
        if self.flusso is not None:
            self.flusso.stop()
            self.flusso.close()
        self.svuota()
        self.file_wav.close()
        self.file_tempi.close()
        return {
            "audio_frequenza_hz": FREQUENZA,
            "audio_durata_s": round(self.campioni_scritti / FREQUENZA, 1),
            "audio_blocchi_con_problemi": self.problemi,
        }
