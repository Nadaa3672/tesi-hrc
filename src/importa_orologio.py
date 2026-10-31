"""Importa i dati dello smartwatch registrati con l'app Sensor Logger.

Prende lo zip esportato da Sensor Logger (formato CSV) e crea i file della
sessione, accanto a quelli della webcam:
  *_orologio.csv       movimento del polso, 50 campioni al secondo:
                       acc_x/y/z   accelerazione totale, gravità compresa (m/s²)
                       lin_x/y/z   accelerazione senza gravità (m/s²)
                       gyr_x/y/z   velocità di rotazione (rad/s)
                       grav_x/y/z  direzione della gravità (m/s²): dice come è inclinato il polso
  *_battito.csv        battito cardiaco (bpm), circa uno al secondo
  *_orologio_info.json come è stato fatto l'allineamento e la qualità dei dati

ALLINEAMENTO CON IL VIDEO (se indichi --sessione):
  1. grossolano: con l'ora esatta. Sensor Logger salva l'ora di ogni campione e lo
     script della webcam salva l'ora di inizio (inizio_epoch_s in *_info.json).
     Gli orologi di telefono e PC possono differire di qualche decimo di secondo.
  2. fine: con le scosse del polso. All'inizio della registrazione scuoti il polso
     3 volte davanti alla webcam: lo script confronta la velocità del polso vista
     da MediaPipe con la rotazione misurata dall'orologio e trova lo sfasamento
     che le fa coincidere meglio.

Uso:
    python src/importa_orologio.py orologio.zip --sessione data/20261031_101500_prova
    python src/importa_orologio.py orologio.zip            (solo orologio, senza video)
"""

import argparse
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

FREQUENZA = 50            # campioni al secondo dopo il ricampionamento
BUCO_MASSIMO = 0.1        # secondi: oltre, tra due campioni c'è un buco (dati mancanti)
RICERCA_SFASAMENTO = 5.0  # secondi: sfasamento massimo cercato con l'ora esatta
RICERCA_SENZA_ORA = 30.0  # secondi: se manca inizio_epoch_s (sessioni vecchie)
SECONDI_ALLINEAMENTO = 120  # si usano i primi N secondi, dove ci sono le scosse
CORRELAZIONE_MINIMA = 0.3   # sotto, l'allineamento fine è considerato incerto
MARGINE_SCOSSA = 3.0        # secondi considerati prima e dopo la scossa per l'allineamento fine
SOGLIA_SCOSSA = 3.0         # rad/s: una scossa del polso supera di molto questo valore
COPERTURA_MINIMA = 90       # % della registrazione webcam che l'orologio dovrebbe coprire

SENSORI = {  # file di Sensor Logger -> prefisso delle colonne
    "WatchTotalAcceleration": "acc",
    "WatchAccelerometer": "lin",
    "WatchGyroscope": "gyr",
    "WatchGravity": "grav",
}


# ---------------------------------------------------------------- lettura

def leggi_esportazione(percorso):
    """Legge i CSV di Sensor Logger da uno zip o da una cartella: {nome: DataFrame}."""
    percorso = Path(percorso)
    tabelle = {}
    if percorso.is_dir():
        for f in percorso.glob("*.csv"):
            if f.stat().st_size > 0:
                tabelle[f.stem] = pd.read_csv(f)
    else:
        with zipfile.ZipFile(percorso) as z:
            for nome in z.namelist():
                if nome.lower().endswith(".csv"):
                    dati = z.read(nome)
                    if dati.strip():
                        tabelle[Path(nome).stem] = pd.read_csv(io.BytesIO(dati))
    return tabelle


def ricampiona(df, griglia):
    """Porta un sensore su una griglia di tempi regolare (secondi, ora esatta).
    I punti della griglia che cadono in un buco dei dati restano vuoti (NaN)."""
    t = df["time"].to_numpy(dtype=np.int64) / 1e9
    ordine = np.argsort(t)
    t = t[ordine]
    risultato = {}
    for asse in ("x", "y", "z"):
        risultato[asse] = np.interp(griglia, t, df[asse].to_numpy(dtype=float)[ordine],
                                    left=np.nan, right=np.nan)
    # campione reale più vicino prima e dopo ogni punto della griglia
    dopo = np.clip(np.searchsorted(t, griglia), 1, len(t) - 1)
    buco = (t[dopo] - t[dopo - 1]) > BUCO_MASSIMO
    for asse in risultato:
        risultato[asse][buco] = np.nan
    return risultato


def tabella_orologio(tabelle):
    """Tutti i sensori del polso sulla stessa griglia a FREQUENZA Hz."""
    presenti = [n for n in SENSORI if n in tabelle and len(tabelle[n]) > 1]
    if "WatchGyroscope" not in presenti:
        raise SystemExit(
            "Nello zip non ci sono i dati dell'orologio (WatchGyroscope.csv).\n"
            "Di solito succede quando si esporta prima che l'orologio abbia finito di mandare i dati al telefono.\n"
            "Apri la registrazione in Sensor Logger, aspetta che compaiano i sensori dell'orologio e riesporta lo zip.\n"
            "Controlla anche che l'orologio fosse collegato al telefono e che i sensori 'Watch' fossero attivi.")
    inizio = max(tabelle[n]["time"].min() for n in presenti) / 1e9
    fine = min(tabelle[n]["time"].max() for n in presenti) / 1e9
    griglia = np.arange(inizio, fine, 1 / FREQUENZA)
    colonne = {"t_epoch": griglia}
    for nome in presenti:
        valori = ricampiona(tabelle[nome], griglia)
        for asse in ("x", "y", "z"):
            colonne[f"{SENSORI[nome]}_{asse}"] = valori[asse]
    return pd.DataFrame(colonne)


def tabella_battito(tabelle):
    if "HeartRate" not in tabelle:
        return None
    hr = tabelle["HeartRate"]
    battito = pd.DataFrame({"t_epoch": hr["time"].to_numpy(dtype=np.int64) / 1e9,
                            "bpm": hr["bpm"].astype(float)})
    # 0 = il sensore non ha letto il battito (all'inizio o se il cinturino si sposta)
    battito.loc[(battito["bpm"] < 30) | (battito["bpm"] > 220), "bpm"] = np.nan
    return battito


# ---------------------------------------------------------------- allineamento

def inizio_sessione_epoch(base):
    """Ora esatta (secondi dal 1970) in cui è iniziata la registrazione webcam."""
    percorso = Path(str(base) + "_info.json")
    if not percorso.exists():
        return None, "manca"
    info = json.loads(percorso.read_text(encoding="utf-8"))
    if "inizio_epoch_s" in info:
        return float(info["inizio_epoch_s"]), "esatta"
    # Sessioni registrate con versioni precedenti: solo l'ora al secondo (ora locale del PC)
    try:
        return datetime.strptime(info["inizio"], "%Y%m%d_%H%M%S").timestamp(), "al secondo"
    except (KeyError, ValueError):
        return None, "manca"


def inviluppo(segnale, campioni):
    """Media mobile del valore assoluto: tiene "quanto si muove", non il dettaglio."""
    s = pd.Series(np.abs(segnale)).interpolate(limit_direction="both").fillna(0)
    return s.rolling(campioni, center=True, min_periods=1).mean().to_numpy(copy=True)


def velocita_polsi_video(posa, griglia):
    """Velocità di ciascun polso nell'immagine, portata sulla griglia di tempi dell'orologio."""
    dt = posa["t_s"].diff()
    velocita = {}
    for lato in ("left", "right"):
        # la posa da webcam a volte "salta": una mediana mobile toglie i salti isolati
        x = posa[f"{lato}_wrist_x"].rolling(5, center=True, min_periods=3).median()
        y = posa[f"{lato}_wrist_y"].rolling(5, center=True, min_periods=3).median()
        v = np.hypot(x.diff(), y.diff()) / dt
        v[(posa[f"{lato}_wrist_vis"] <= 0.5) | (dt > 0.5)] = np.nan
        v = v.to_numpy()
        validi = ~np.isnan(v)
        if validi.sum() < 10:
            continue
        velocita[lato] = np.interp(griglia, posa["t_s"].to_numpy()[validi], v[validi],
                                   left=np.nan, right=np.nan)
    return velocita


def correlazione_a_sfasamento(a, b, massimo, minimo_campioni):
    """Per ogni sfasamento k (in campioni, |k| <= massimo) la correlazione tra
    a[i] e b[i + k], se ci sono almeno minimo_campioni validi in comune.
    Restituisce (sfasamenti, correlazioni)."""
    sfasamenti = np.arange(-massimo, massimo + 1)
    correlazioni = np.full(len(sfasamenti), np.nan)
    for j, k in enumerate(sfasamenti):
        if k >= 0:
            x, y = a[:len(a) - k], b[k:]
        else:
            x, y = a[-k:], b[:len(b) + k]
        n = min(len(x), len(y))
        x, y = x[:n], y[:n]
        validi = ~(np.isnan(x) | np.isnan(y))
        if validi.sum() < minimo_campioni or x[validi].std() == 0 or y[validi].std() == 0:
            continue
        correlazioni[j] = np.corrcoef(x[validi], y[validi])[0, 1]
    return sfasamenti, correlazioni


def copertura_sessione(posa, orologio):
    """% del tempo della registrazione webcam in cui ci sono dati dell'orologio."""
    inizio, fine = posa["t_s"].iloc[0], posa["t_s"].iloc[-1]
    validi = orologio[orologio["gyr_x"].notna() & (orologio["t_s"] >= inizio) & (orologio["t_s"] <= fine)]
    return 100 * len(validi) / (FREQUENZA * (fine - inizio)) if fine > inizio else 0.0


def scosse_presenti(orologio):
    """True se nei primi SECONDI_ALLINEAMENTO secondi l'orologio ha registrato una scossa."""
    inizio = orologio[orologio["t_s"] <= SECONDI_ALLINEAMENTO]
    rotazione = np.sqrt(inizio["gyr_x"] ** 2 + inizio["gyr_y"] ** 2 + inizio["gyr_z"] ** 2)
    return bool((rotazione > SOGLIA_SCOSSA).any())


def zona_scossa(b, griglia):
    """Inizio e fine (indici) della scossa: il tratto attorno al picco di rotazione
    dell'orologio in cui la rotazione resta sopra metà del picco."""
    candidati = np.where(griglia <= SECONDI_ALLINEAMENTO, b, np.nan)
    if np.all(np.isnan(candidati)):
        return None
    picco = int(np.nanargmax(candidati))
    soglia = 0.5 * b[picco]
    i0 = i1 = picco
    while i0 > 0 and b[i0 - 1] > soglia:
        i0 -= 1
    while i1 < len(b) - 1 and b[i1 + 1] > soglia:
        i1 += 1
    return i0, i1


def allineamento_fine(posa, orologio, ricerca):
    """Sfasamento (secondi) da AGGIUNGERE ai tempi dell'orologio perché il movimento
    del polso coincida con quello visto dalla webcam.

    Si confronta solo il tratto della scossa (più qualche secondo prima e dopo):
    nel resto della registrazione la webcam vede spostamenti del polso che
    l'orologio, che misura rotazioni, può non vedere allo stesso modo."""
    margine = ricerca + 2
    griglia = np.arange(max(0.0, posa["t_s"].iloc[0]) - margine,
                        min(posa["t_s"].iloc[-1], SECONDI_ALLINEAMENTO) + margine, 1 / FREQUENZA)
    rotazione = np.sqrt(orologio["gyr_x"] ** 2 + orologio["gyr_y"] ** 2 + orologio["gyr_z"] ** 2).to_numpy()
    polso_orologio = np.interp(griglia, orologio["t_s"].to_numpy(), rotazione, left=np.nan, right=np.nan)
    campioni = int(0.3 * FREQUENZA)
    b = inviluppo(polso_orologio, campioni)
    b[np.isnan(polso_orologio)] = np.nan
    zona = zona_scossa(b, griglia)
    if zona is None:
        return None
    margine_campioni = int(MARGINE_SCOSSA * FREQUENZA)
    i0, i1 = max(0, zona[0] - margine_campioni), min(len(b), zona[1] + margine_campioni + 1)
    b_scossa = np.full(len(b), np.nan)
    b_scossa[i0:i1] = b[i0:i1]
    minimo = int(0.6 * (i1 - i0))  # almeno il 60% del tratto della scossa visibile nel video

    migliore = None
    for lato, v in velocita_polsi_video(posa, griglia).items():
        a = inviluppo(v, campioni)
        a[np.isnan(v)] = np.nan
        # a[i] (video, tempo griglia[i]) confrontato con b[i + k] (orologio):
        # se coincidono con k > 0, l'orologio è "in ritardo" di k campioni
        sfasamenti, corr = correlazione_a_sfasamento(a, b_scossa, int(ricerca * FREQUENZA), minimo)
        if np.all(np.isnan(corr)):
            continue
        j = int(np.nanargmax(corr))
        if migliore is None or corr[j] > migliore["correlazione"]:
            migliore = {"polso": lato, "correlazione": float(corr[j]),
                        "sfasamento_s": float(-sfasamenti[j] / FREQUENZA),
                        "scossa_s": [round(float(griglia[zona[0]]), 2), round(float(griglia[zona[1]]), 2)],
                        "al_limite": bool(abs(sfasamenti[j]) >= int(ricerca * FREQUENZA) - 2)}
    return migliore


# ---------------------------------------------------------------- programma

def main():
    parser = argparse.ArgumentParser(description="Importa i dati dello smartwatch (Sensor Logger).")
    parser.add_argument("esportazione", help="Zip (o cartella) esportato da Sensor Logger in formato CSV")
    parser.add_argument("--sessione", help="Prefisso della sessione webcam, es. data/20261031_101500_prova")
    parser.add_argument("--sfasamento", type=float, default=None,
                        help="Sfasamento in secondi da usare invece di quello calcolato")
    args = parser.parse_args()

    tabelle = leggi_esportazione(args.esportazione)
    orologio = tabella_orologio(tabelle)
    battito = tabella_battito(tabelle)
    metadati = tabelle.get("Metadata")

    if args.sessione:
        base = Path(args.sessione)
        for suffisso in ("_pose.csv", "_info.json", ".mp4", "_pose", "_info"):
            if base.name.endswith(suffisso):
                base = base.with_name(base.name[: -len(suffisso)])
    else:
        nome = Path(args.esportazione).stem
        base = Path("data") / f"orologio_{nome}"
        base.parent.mkdir(exist_ok=True)

    info = {"esportazione": Path(args.esportazione).name, "frequenza_hz": FREQUENZA}
    if metadati is not None and len(metadati):
        riga = metadati.iloc[0]
        info.update({"telefono": str(riga.get("device name", "")),
                     "registrazione": str(riga.get("recording time", "")),
                     "app": str(riga.get("appVersion", ""))})

    # 1. allineamento grossolano con l'ora esatta
    inizio, precisione = (None, "manca")
    if args.sessione:
        inizio, precisione = inizio_sessione_epoch(base)
    if inizio is None:
        inizio = orologio["t_epoch"].iloc[0]
        if args.sessione:
            print("Attenzione: non trovo l'ora di inizio della sessione (_info.json).")
    info["ora_inizio_sessione"] = precisione
    orologio.insert(0, "t_s", orologio["t_epoch"] - inizio)
    if battito is not None:
        battito.insert(0, "t_s", battito["t_epoch"] - inizio)

    # 2. allineamento fine con le scosse del polso
    sfasamento = 0.0
    posa_file = Path(str(base) + "_pose.csv")
    if args.sfasamento is not None:
        sfasamento = args.sfasamento
        info["allineamento_fine"] = "indicato a mano"
    elif args.sessione and posa_file.exists():
        posa = pd.read_csv(posa_file)
        copertura = copertura_sessione(posa, orologio)
        info["copertura_sessione_%"] = round(copertura, 1)
        validi = orologio[orologio["gyr_x"].notna()]
        if copertura < COPERTURA_MINIMA:
            print(f"ATTENZIONE: l'orologio copre solo il {copertura:.0f}% della registrazione webcam "
                  f"(dati dal secondo {validi['t_s'].iloc[0]:.0f} al {validi['t_s'].iloc[-1]:.0f}, "
                  f"webcam da 0 a {posa['t_s'].iloc[-1]:.0f}). Probabilmente l'orologio ha iniziato a "
                  f"registrare in ritardo o si è fermato prima: conviene rifare la registrazione.")
        ricerca = RICERCA_SFASAMENTO if precisione == "esatta" else RICERCA_SENZA_ORA
        risultato = None
        if not scosse_presenti(orologio):
            print("Le scosse del polso non sono nei dati dell'orologio: allineamento fine impossibile, uso solo l'ora.")
            info["allineamento_fine"] = "scosse assenti nei dati dell'orologio"
        else:
            risultato = allineamento_fine(posa, orologio, ricerca)
            if risultato is None:
                print("Allineamento fine non riuscito (durante la scossa il polso non si vedeva abbastanza nel video): uso solo l'ora.")
                info["allineamento_fine"] = "non riuscito"
        if risultato is not None:
            info.update({"allineamento_fine": "scosse del polso", **{k: round(v, 3) if isinstance(v, float) else v
                                                                    for k, v in risultato.items()}})
            print(f"Allineamento con le scosse: sfasamento {risultato['sfasamento_s']:+.2f} s, "
                  f"polso {'sinistro' if risultato['polso'] == 'left' else 'destro'}, "
                  f"correlazione {risultato['correlazione']:.2f}")
            if risultato["al_limite"]:
                print("Attenzione: lo sfasamento trovato è al limite dell'intervallo di ricerca, quindi non è affidabile. "
                      "Uso solo l'ora. (Se sei sicura che gli orologi siano molto sfasati, usa --sfasamento.)")
                info["allineamento_incerto"] = True
            elif risultato["correlazione"] < CORRELAZIONE_MINIMA:
                print("Attenzione: correlazione bassa, l'allineamento è incerto. "
                      "Controlla di aver scosso il polso davanti alla webcam all'inizio.")
                info["allineamento_incerto"] = True
            else:
                sfasamento = risultato["sfasamento_s"]
    info["sfasamento_applicato_s"] = round(sfasamento, 3)
    orologio["t_s"] += sfasamento
    if battito is not None:
        battito["t_s"] += sfasamento

    # Qualità
    validi = orologio["gyr_x"].notna()
    info["durata_s"] = round(float(orologio["t_s"].iloc[-1] - orologio["t_s"].iloc[0]), 1)
    info["dati_presenti_%"] = round(float(validi.mean() * 100), 1)
    if battito is not None:
        info["battito_valido_%"] = round(float(battito["bpm"].notna().mean() * 100), 1)

    orologio.round(5).to_csv(str(base) + "_orologio.csv", index=False)
    if battito is not None:
        battito.round(3).to_csv(str(base) + "_battito.csv", index=False)
    with open(str(base) + "_orologio_info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)

    print(f"Orologio: {info['durata_s']} s, dati presenti {info['dati_presenti_%']}%"
          + (f", battito valido {info['battito_valido_%']}%" if battito is not None else ""))
    print(f"File salvati con prefisso {base}")


if __name__ == "__main__":
    main()
