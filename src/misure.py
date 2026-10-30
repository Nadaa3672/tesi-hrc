"""Tutte le misure ("dimensioni") calcolate dai segnali.

Ogni funzione riceve i dati di un intervallo di tempo (una sessione intera
oppure una finestra di pochi secondi) e restituisce un dizionario di numeri.
La usano sia analisi_sessione.py sia analisi_finestre.py, così le due analisi
calcolano le misure esattamente nello stesso modo.

Le distanze del corpo sono divise per la larghezza delle spalle ("unità spalle"),
quelle delle mani per la grandezza della mano ("unità mano"): così non
dipendono dalla distanza dalla webcam.
"""

import wave
from pathlib import Path

import numpy as np
import pandas as pd

SOGLIA_VISIBILITA = 0.5
SOGLIA_FERMO = 0.15       # unità spalle al secondo: sotto, la mano è "ferma"
SOGLIA_CHIUSI = 0.5       # chiusura degli occhi oltre cui li consideriamo chiusi
SOGLIA_RIAPERTI = 0.35    # sotto questa gli occhi tornano "aperti" (isteresi)
SOGLIA_BOCCA = 0.5        # apertura della bocca per uno sbadiglio
DURATA_SBADIGLIO = 1.5    # secondi minimi di bocca aperta
SOGLIA_PAUSA = 0.5        # secondi tra due fotogrammi oltre cui c'è un "salto"


def arrotonda(valore, cifre=3):
    if valore is None or (isinstance(valore, float) and np.isnan(valore)):
        return None
    return round(float(valore), cifre)


# ---------------------------------------------------------------- file di una sessione

def base_sessione(percorso):
    """Dal nome di un qualunque file della sessione al prefisso comune.
    Es. data/20261018_175018_mattina_pose.csv -> data/20261018_175018_mattina"""
    percorso = Path(percorso)
    nome = percorso.stem
    for suffisso in ("_pose", "_viso", "_mani", "_emozioni", "_eventi", "_info",
                     "_audio_tempi", "_finestre"):
        if nome.endswith(suffisso):
            nome = nome[: -len(suffisso)]
            break
    return percorso.with_name(nome)


def leggi_se_esiste(base, suffisso):
    percorso = Path(str(base) + suffisso)
    if percorso.exists() and percorso.stat().st_size > 0:
        df = pd.read_csv(percorso)
        return df if len(df) else None
    return None


def carica_sessione(base):
    """Legge tutti i file disponibili di una sessione. Quelli mancanti restano None."""
    sessione = {
        "nome": Path(base).name,
        "posa": leggi_se_esiste(base, "_pose.csv"),
        "viso": leggi_se_esiste(base, "_viso.csv"),
        "mani": leggi_se_esiste(base, "_mani.csv"),
        "emozioni": leggi_se_esiste(base, "_emozioni.csv"),
        "eventi": leggi_se_esiste(base, "_eventi.csv"),
        "audio": livelli_audio(base),
    }
    posa = sessione["posa"]
    sessione["scala_spalle"] = larghezza_spalle(posa) if posa is not None else None
    sessione["scala_mani"] = grandezza_mani(sessione["mani"])
    return sessione


def taglia(df, inizio, fine):
    """Le righe con inizio <= t_s < fine."""
    if df is None:
        return None
    parte = df[(df["t_s"] >= inizio) & (df["t_s"] < fine)]
    return parte if len(parte) else None


# ---------------------------------------------------------------- qualità

def misure_qualita(posa):
    """Controlli sulla registrazione: velocità e 'salti' tra fotogrammi."""
    if posa is None or len(posa) < 2:
        return {}
    salti = posa["t_s"].diff().dropna()
    durata = posa["t_s"].iloc[-1] - posa["t_s"].iloc[0]
    return {
        "fps_medi": arrotonda(len(posa) / durata, 1) if durata > 0 else None,
        "pausa_max_s": arrotonda(salti.max(), 2),
        "pause_oltre_0.5s": int((salti > SOGLIA_PAUSA).sum()),
    }


# ---------------------------------------------------------------- corpo

def larghezza_spalle(posa):
    dx = posa["left_shoulder_x"] - posa["right_shoulder_x"]
    dy = posa["left_shoulder_y"] - posa["right_shoulder_y"]
    return float(np.median(np.hypot(dx, dy)))


def velocita_mani(posa, scala):
    """Velocità media dei due polsi, in unità spalle al secondo, leggermente smussata.
    Non calcola la velocità attraverso un 'salto' tra fotogrammi."""
    dt = posa["t_s"].diff()
    serie = []
    for lato in ("left", "right"):
        v = np.hypot(posa[f"{lato}_wrist_x"].diff(), posa[f"{lato}_wrist_y"].diff()) / scala / dt
        v[(posa[f"{lato}_wrist_vis"] <= SOGLIA_VISIBILITA) | (dt > SOGLIA_PAUSA)] = np.nan
        serie.append(v.rolling(5, center=True, min_periods=1).median())
    return pd.concat(serie, axis=1).mean(axis=1)


def altezza_testa(posa, scala):
    """Quanto il naso sta sopra la linea delle spalle (unità spalle).
    Valori più bassi = testa più bassa o schiena più curva."""
    spalle_y = (posa["left_shoulder_y"] + posa["right_shoulder_y"]) / 2
    return (spalle_y - posa["nose_y"]) / scala


def misure_corpo(posa, scala):
    if posa is None or not scala:
        return {}
    v = velocita_mani(posa, scala)
    validi = v.dropna()
    return {
        "velocita_mani_media": arrotonda(validi.mean()) if len(validi) else None,
        "mani_ferme_%": arrotonda((validi < SOGLIA_FERMO).mean() * 100, 1) if len(validi) else None,
        "altezza_testa_media": arrotonda(altezza_testa(posa, scala).mean()),
    }


# ---------------------------------------------------------------- viso

def conta_ammiccamenti(chiusura):
    """Un ammiccamento = gli occhi passano da aperti a chiusi. Due soglie diverse
    (isteresi) evitano di contare due volte lo stesso ammiccamento."""
    conteggio, aperti = 0, True
    for valore in chiusura:
        if aperti and valore > SOGLIA_CHIUSI:
            conteggio, aperti = conteggio + 1, False
        elif not aperti and valore < SOGLIA_RIAPERTI:
            aperti = True
    return conteggio


def conta_sbadigli(tempi, bocca):
    """Uno sbadiglio = bocca molto aperta per almeno DURATA_SBADIGLIO secondi."""
    conteggio, inizio = 0, None
    for t, valore in zip(tempi, bocca):
        if valore > SOGLIA_BOCCA and inizio is None:
            inizio = t
        elif valore <= SOGLIA_BOCCA and inizio is not None:
            conteggio += (t - inizio) >= DURATA_SBADIGLIO
            inizio = None
    if inizio is not None and len(tempi) and (list(tempi)[-1] - inizio) >= DURATA_SBADIGLIO:
        conteggio += 1  # sbadiglio ancora in corso alla fine dell'intervallo
    return conteggio


def misure_viso(viso):
    if viso is None or len(viso) < 2:
        return {}
    chiusura = (viso["eyeBlinkLeft"] + viso["eyeBlinkRight"]) / 2
    durata_min = (viso["t_s"].iloc[-1] - viso["t_s"].iloc[0]) / 60
    risultato = {
        "ammiccamenti_al_min": arrotonda(conta_ammiccamenti(chiusura) / durata_min, 1) if durata_min > 0 else None,
        "occhi_chiusi_%": arrotonda((chiusura > SOGLIA_CHIUSI).mean() * 100, 1),
        "chiusura_occhi_media": arrotonda(chiusura.mean()),
        "sguardo_in_basso": arrotonda(((viso["eyeLookDownLeft"] + viso["eyeLookDownRight"]) / 2).mean()),
        "sbadigli": int(conta_sbadigli(viso["t_s"], viso["jawOpen"])),
    }
    # Orientamento della testa (solo nei file estratti con la versione che lo calcola)
    if "testa_pitch" in viso.columns:
        risultato.update({
            "testa_pitch_media": arrotonda(viso["testa_pitch"].mean(), 1),
            "testa_pitch_variab": arrotonda(viso["testa_pitch"].std(), 2),
            "testa_yaw_variab": arrotonda(viso["testa_yaw"].std(), 2),
            "testa_roll_variab": arrotonda(viso["testa_roll"].std(), 2),
        })
    return risultato


# ---------------------------------------------------------------- mani

def grandezza_mani(mani):
    """Per ogni mano, la distanza mediana dal polso (p0) alla base del dito medio (p9)."""
    if mani is None:
        return {}
    return {lato: float(np.median(np.hypot(g["p9_x"] - g["p0_x"], g["p9_y"] - g["p0_y"])))
            for lato, g in mani.groupby("mano")}


def misure_mani(mani, fotogrammi, scale):
    if mani is None or not fotogrammi:
        return {}
    velocita = []
    for lato, una_mano in mani.groupby("mano"):
        scala = scale.get(lato)
        if not scala:
            continue
        una_mano = una_mano.drop_duplicates("frame").sort_values("frame")
        consecutivi = una_mano["frame"].diff() == 1
        v = np.hypot(una_mano["p8_x"].diff(), una_mano["p8_y"].diff()) / scala / una_mano["t_s"].diff()
        velocita.append(v[consecutivi])
    v_tutte = pd.concat(velocita).dropna() if velocita else pd.Series(dtype=float)
    return {
        "mani_visibili_%": arrotonda(min(100.0, mani["frame"].nunique() / fotogrammi * 100), 1),
        "velocita_dita": arrotonda(v_tutte.median()) if len(v_tutte) else None,
    }


# ---------------------------------------------------------------- emozioni

def misure_emozioni(emo):
    if emo is None:
        return {}
    return {
        "emozione_prevalente": emo["emozione"].mode().iloc[0],
        "neutro_%": arrotonda((emo["emozione"] == "neutro").mean() * 100, 1),
        "valenza_media": arrotonda(emo["valenza"].mean()),
        "attivazione_media": arrotonda(emo["attivazione"].mean()),
    }


# ---------------------------------------------------------------- audio

def livelli_audio(base):
    """Livello del suono ogni 100 ms, in dBFS, con il suo tempo t_s sullo stesso
    orologio del video (grazie a *_audio_tempi.csv). None se non c'è audio."""
    wav = Path(str(base) + ".wav")
    if not wav.exists():
        return None
    with wave.open(str(wav), "rb") as f:
        frequenza = f.getframerate()
        x = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
    blocco = int(0.1 * frequenza)
    n = len(x) // blocco
    if n == 0:
        return None
    rms = np.sqrt((x[:n * blocco].reshape(n, blocco) ** 2).mean(axis=1))
    db = 20 * np.log10(rms + 1e-10)
    inizio_campioni = np.arange(n) * blocco

    tempi_csv = Path(str(base) + "_audio_tempi.csv")
    if tempi_csv.exists():
        tempi = pd.read_csv(tempi_csv)
        t_s = np.interp(inizio_campioni, tempi["campione_iniziale"], tempi["t_s"])
    else:
        t_s = inizio_campioni / frequenza
    return pd.DataFrame({"t_s": t_s, "db": db})


def misure_audio(livelli):
    """dBFS: 0 = massimo registrabile, più negativo = più silenzio. Relativi al microfono."""
    if livelli is None or len(livelli) < 10:
        return {}
    db = livelli["db"].to_numpy()
    digitale = db < -90  # "silenzio digitale": campioni a zero, non suono vero
    validi = db[~digitale]
    risultato = {"silenzio_digitale_%": arrotonda(digitale.mean() * 100, 1)}
    if len(validi) >= 10:
        fondo = np.percentile(validi, 10)
        risultato.update({
            "rumore_fondo_dbfs": arrotonda(fondo, 1),
            "livello_medio_dbfs": arrotonda(np.median(validi), 1),
            "picco_dbfs": arrotonda(np.percentile(validi, 95), 1),
            "suoni_sopra_fondo_%": arrotonda((validi > fondo + 10).mean() * 100, 1),
        })
    return risultato


# ---------------------------------------------------------------- tutto insieme

def tutte_le_misure(sessione, inizio=None, fine=None):
    """Tutte le misure di una sessione, oppure solo dell'intervallo [inizio, fine)."""
    if inizio is None:
        parti = {k: sessione[k] for k in ("posa", "viso", "mani", "emozioni", "audio")}
    else:
        parti = {k: taglia(sessione[k], inizio, fine) for k in ("posa", "viso", "mani", "emozioni", "audio")}
    fotogrammi = len(parti["posa"]) if parti["posa"] is not None else None
    risultato = {}
    risultato.update(misure_qualita(parti["posa"]))
    risultato.update(misure_corpo(parti["posa"], sessione["scala_spalle"]))
    risultato.update(misure_viso(parti["viso"]))
    risultato.update(misure_mani(parti["mani"], fotogrammi, sessione["scala_mani"]))
    risultato.update(misure_emozioni(parti["emozioni"]))
    risultato.update(misure_audio(parti["audio"]))
    return risultato
