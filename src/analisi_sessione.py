"""Prime "dimensioni" da una o più registrazioni della posa.

Calcola, per ogni sessione:
  - velocità media delle mani (polsi)       -> quanto sei rapida
  - percentuale di tempo con le mani ferme  -> pause, esitazioni
  - posizione della testa rispetto alle spalle -> testa bassa / postura curva
  - se esiste il file *_eventi.csv: durata di ogni compito tra due eventi
    (es. evento 1 -> 2 = barchetta, evento 2 -> 3 = aeroplano)
  - se esiste *_viso.csv (da estrai_da_video.py): ammiccamenti al minuto,
    percentuale di tempo con gli occhi chiusi, sbadigli
  - se esiste *_mani.csv: quanto sono visibili le mani e velocità delle dita
  - se esiste *_emozioni.csv (da estrai_emozioni.py): emozione prevalente,
    percentuale di tempo neutra, valenza e attivazione medie
  - se esiste il file audio .wav: rumore di fondo, livello medio e
    percentuale di tempo con suoni sopra il fondo (voce, carta, oggetti)

Le distanze sono divise per la larghezza delle spalle, così non dipendono
da quanto sei lontana dalla webcam ("unità spalle").

Uso:
    python src/analisi_sessione.py data/20261018_093000_mattina_pose.csv
    python src/analisi_sessione.py data/*_mattina_pose.csv data/*_sera_pose.csv
"""

import argparse
import glob
import wave
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # salva i grafici su file senza aprire finestre
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SOGLIA_VISIBILITA = 0.5
SOGLIA_FERMO = 0.15  # sotto questa velocità (unità spalle al secondo) la mano è "ferma"


def carica(percorso):
    df = pd.read_csv(percorso)
    if len(df) < 10:
        raise SystemExit(f"{percorso}: troppo pochi fotogrammi ({len(df)}).")
    return df


def larghezza_spalle(df):
    dx = df["left_shoulder_x"] - df["right_shoulder_x"]
    dy = df["left_shoulder_y"] - df["right_shoulder_y"]
    return float(np.median(np.hypot(dx, dy)))


def velocita_polso(df, lato, scala):
    """Velocità del polso in unità spalle al secondo, leggermente smussata."""
    x, y = df[f"{lato}_wrist_x"], df[f"{lato}_wrist_y"]
    visibile = df[f"{lato}_wrist_vis"] > SOGLIA_VISIBILITA
    dt = df["t_s"].diff()
    v = np.hypot(x.diff(), y.diff()) / scala / dt
    v[~visibile] = np.nan
    return v.rolling(5, center=True, min_periods=1).median()


def altezza_testa(df, scala):
    """Quanto il naso sta sopra la linea delle spalle (in unità spalle).
    Valori più bassi = testa più bassa o schiena più curva."""
    spalle_y = (df["left_shoulder_y"] + df["right_shoulder_y"]) / 2
    return (spalle_y - df["nose_y"]) / scala


def ammiccamenti_e_sbadigli(viso):
    """Conta ammiccamenti e sbadigli dai valori del viso (da 0 a 1)."""
    chiusura = (viso["eyeBlinkLeft"] + viso["eyeBlinkRight"]) / 2
    durata_min = (viso["t_s"].iloc[-1] - viso["t_s"].iloc[0]) / 60

    # Un ammiccamento = gli occhi passano da aperti (< 0.35) a chiusi (> 0.5)
    ammiccamenti, aperti = 0, True
    for valore in chiusura:
        if aperti and valore > 0.5:
            ammiccamenti, aperti = ammiccamenti + 1, False
        elif not aperti and valore < 0.35:
            aperti = True

    # Uno sbadiglio = bocca molto aperta (jawOpen > 0.5) per almeno 1,5 secondi
    sbadigli, inizio = 0, None
    for t, bocca in zip(viso["t_s"], viso["jawOpen"]):
        if bocca > 0.5 and inizio is None:
            inizio = t
        elif bocca <= 0.5 and inizio is not None:
            sbadigli += (t - inizio) >= 1.5
            inizio = None

    return {
        "ammiccamenti_al_min": round(ammiccamenti / durata_min, 1) if durata_min > 0 else None,
        "occhi_chiusi_%": round(float((chiusura > 0.5).mean() * 100), 1),
        "sguardo_in_basso": round(float(((viso["eyeLookDownLeft"] + viso["eyeLookDownRight"]) / 2).mean()), 3),
        "sbadigli": int(sbadigli),
    }


def misure_mani(mani, fotogrammi_totali):
    """Visibilità delle mani e velocità della punta dell'indice (in "unità mano" al secondo)."""
    visibili = mani["frame"].nunique() / fotogrammi_totali * 100
    velocita = []
    for _, una_mano in mani.groupby("mano"):
        una_mano = una_mano.drop_duplicates("frame").sort_values("frame")
        # dimensione della mano: dal polso (p0) alla base del dito medio (p9)
        scala = float(np.median(np.hypot(una_mano["p9_x"] - una_mano["p0_x"],
                                         una_mano["p9_y"] - una_mano["p0_y"])))
        consecutivi = una_mano["frame"].diff() == 1
        v = (np.hypot(una_mano["p8_x"].diff(), una_mano["p8_y"].diff())
             / scala / una_mano["t_s"].diff())
        velocita.append(v[consecutivi])
    v_tutte = pd.concat(velocita) if velocita else pd.Series(dtype=float)
    return {
        "mani_visibili_%": round(float(visibili), 1),
        "velocita_dita": round(float(v_tutte.median()), 3) if len(v_tutte) else None,
    }


def misure_audio(percorso_wav):
    """Livello del suono ogni 100 ms, in dBFS (0 = massimo, più negativo = più silenzio).
    I dBFS sono relativi al microfono: confrontabili tra sessioni con lo stesso
    microfono e le stesse impostazioni, non tra microfoni diversi."""
    with wave.open(str(percorso_wav), "rb") as f:
        frequenza = f.getframerate()
        x = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
    finestra = int(0.1 * frequenza)
    n = len(x) // finestra
    if n < 10:
        return {}
    rms = np.sqrt((x[:n * finestra].reshape(n, finestra) ** 2).mean(axis=1))
    db = 20 * np.log10(rms + 1e-10)
    # Sotto -90 dBFS non c'è suono vero ma "silenzio digitale" (campioni a zero):
    # succede se il microfono è muto o se Windows sopprime il rumore. Lo escludiamo.
    digitale = db < -90
    validi = db[~digitale]
    if len(validi) < 10:
        return {"silenzio_digitale_%": round(float(digitale.mean() * 100), 1)}
    fondo = np.percentile(validi, 10)  # il 10% più silenzioso = rumore di fondo della stanza
    return {
        "rumore_fondo_dbfs": round(float(fondo), 1),
        "livello_medio_dbfs": round(float(np.median(validi)), 1),
        "picco_dbfs": round(float(np.percentile(validi, 95)), 1),
        "suoni_sopra_fondo_%": round(float((validi > fondo + 10).mean() * 100), 1),
        "silenzio_digitale_%": round(float(digitale.mean() * 100), 1),
    }


def analizza(percorso):
    df = carica(percorso)
    scala = larghezza_spalle(df)
    v_sx = velocita_polso(df, "left", scala)
    v_dx = velocita_polso(df, "right", scala)
    v_mani = pd.concat([v_sx, v_dx], axis=1).mean(axis=1)
    testa = altezza_testa(df, scala)

    riepilogo = {
        "sessione": Path(percorso).stem.replace("_pose", ""),
        "durata_s": round(df["t_s"].iloc[-1] - df["t_s"].iloc[0], 1),
        "fotogrammi": len(df),
        "velocita_mani_media": round(float(v_mani.mean()), 3),
        "mani_ferme_%": round(float((v_mani < SOGLIA_FERMO).mean() * 100), 1),
        "altezza_testa_media": round(float(testa.mean()), 3),
    }
    eventi_csv = Path(str(percorso).replace("_pose.csv", "_eventi.csv"))
    if eventi_csv.exists():
        tempi = pd.read_csv(eventi_csv)["t_s"].tolist()
        for i in range(len(tempi) - 1):
            riepilogo[f"compito_{i + 1}_s"] = round(tempi[i + 1] - tempi[i], 1)

    viso_csv = Path(str(percorso).replace("_pose.csv", "_viso.csv"))
    if viso_csv.exists() and viso_csv.stat().st_size > 0:
        riepilogo.update(ammiccamenti_e_sbadigli(pd.read_csv(viso_csv)))

    mani_csv = Path(str(percorso).replace("_pose.csv", "_mani.csv"))
    if mani_csv.exists():
        mani = pd.read_csv(mani_csv)
        if len(mani):
            riepilogo.update(misure_mani(mani, len(df)))

    emozioni_csv = Path(str(percorso).replace("_pose.csv", "_emozioni.csv"))
    if emozioni_csv.exists():
        emo = pd.read_csv(emozioni_csv)
        if len(emo):
            riepilogo["emozione_prevalente"] = emo["emozione"].mode().iloc[0]
            riepilogo["neutro_%"] = round(float((emo["emozione"] == "neutro").mean() * 100), 1)
            riepilogo["valenza_media"] = round(float(emo["valenza"].mean()), 3)
            riepilogo["attivazione_media"] = round(float(emo["attivazione"].mean()), 3)

    wav = Path(str(percorso).replace("_pose.csv", ".wav"))
    if wav.exists():
        riepilogo.update(misure_audio(wav))

    serie = pd.DataFrame({"t_s": df["t_s"] - df["t_s"].iloc[0],
                          "velocita_mani": v_mani, "altezza_testa": testa})
    return riepilogo, serie


def main():
    parser = argparse.ArgumentParser(description="Analizza le registrazioni della posa.")
    parser.add_argument("file", nargs="+", help="Uno o più file *_pose.csv")
    args = parser.parse_args()

    # Su Windows il terminale non espande gli asterischi: lo facciamo noi
    percorsi = []
    for schema in args.file:
        percorsi += sorted(glob.glob(schema)) or [schema]

    risultati = [analizza(p) for p in percorsi]

    tabella = pd.DataFrame([r for r, _ in risultati])
    print("\nRiepilogo delle sessioni:\n")
    print(tabella.to_string(index=False))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    for riepilogo, serie in risultati:
        ax1.plot(serie["t_s"], serie["velocita_mani"], label=riepilogo["sessione"], linewidth=1)
        ax2.plot(serie["t_s"], serie["altezza_testa"], label=riepilogo["sessione"], linewidth=1)
    ax1.set_ylabel("Velocità mani\n(unità spalle / s)")
    ax2.set_ylabel("Altezza testa\n(unità spalle)")
    ax2.set_xlabel("Tempo dall'inizio (s)")
    ax1.legend()
    ax1.grid(alpha=0.3)
    ax2.grid(alpha=0.3)
    fig.tight_layout()

    cartella = Path(percorsi[0]).parent
    tabella.to_csv(cartella / "riepilogo_sessioni.csv", index=False)
    fig.savefig(cartella / "confronto_sessioni.png", dpi=120)
    print(f"\nSalvati: {cartella / 'riepilogo_sessioni.csv'} e {cartella / 'confronto_sessioni.png'}")


if __name__ == "__main__":
    main()
