"""Il dataset di Yasar et al. (Scientific Data, 2024) nello stesso formato del framework.

Dataset: WSD4FEDSRM, "Wearable sensor data for fatigue estimation during shoulder
rotation movements", https://zenodo.org/records/8415066 (licenza CC BY 4.0).
34 persone ripetono una rotazione della spalla con un cavo fino allo sfinimento,
con 6 esercizi (rotazione interna o esterna, carico 30-40%, 40-50% o 50-60% della
forza massima). Sensori di movimento (100 al secondo) su mano, avambraccio, braccio,
spalla, sterno e bacino; ogni 10 secondi la persona dice quanto è affaticata
sulla scala di Borg (6 = nessuno sforzo, 20 = sforzo massimo).

Questo script prende il sensore di una parte del corpo (di default l'avambraccio,
il più simile a uno smartwatch), lo porta a 50 campioni al secondo come quello
dell'orologio, lo divide in finestre di 10 secondi allineate alle risposte Borg
e calcola le stesse misure del polso usate per lo smartwatch (misure.misure_orologio).

Risultato: data/yasar_finestre.csv, una riga per finestra, con
persona, esercizio, tipo, carico, finestra, inizio_s, fine_s, borg, progresso
(0 = inizio, 1 = fine dell'esercizio) e le misure.
Alla fine stampa un riassunto: come cambiano le misure con la fatica nella stessa persona.

Uso:
    python src/yasar.py percorso/della/cartella/WSD4FEDSRM
    python src/yasar.py percorso/WSD4FEDSRM --sensore Hand
"""

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import misure

FREQUENZA_ORIGINALE = 100
FREQUENZA = 50
ESERCIZI = {  # colonna task_order di borg_data.csv -> cartella, tipo, carico
    "task1_35i": ("30-40_ internal rotation", "interna", "30-40%"),
    "task2_45i": ("40-50_ internal rotation", "interna", "40-50%"),
    "task3_55i": ("50-60_ internal rotation", "interna", "50-60%"),
    "task4_35e": ("30-40_ external rotation", "esterna", "30-40%"),
    "task5_45e": ("40-50_ external rotation", "esterna", "40-50%"),
    "task6_55e": ("50-60_ external rotation", "esterna", "50-60%"),
}
SENSORI = {"Forearm": "forearm", "Hand": "hand", "Upper arm": "upper_arm",
           "Shoulder": "shoulder", "Sternum": "sternum", "Pelvis": "pelvis"}
DIFFERENZA_MASSIMA_S = 10  # durata dei sensori vs durata Borg: oltre, la prova è incoerente


def leggi_borg(radice):
    borg = pd.read_csv(radice / "Borg data" / "borg_data.csv")
    borg.columns = [c.strip() for c in borg.columns]
    borg["subject"] = borg["subject"].ffill()
    return borg


def leggi_sensore(radice, cartella, soggetto, sensore):
    """Accelerometro e giroscopio di una prova, portati a 50 Hz (media di due campioni)."""
    base = radice / "EMG, IMU, and PPG data" / cartella / f"Subject {soggetto}" / "IMU data" / sensore
    nome = SENSORI[sensore]
    acc = pd.read_csv(base / f"acc_{nome}.csv").to_numpy(dtype=float)
    gyr = pd.read_csv(base / f"gyr_{nome}.csv").to_numpy(dtype=float)
    n = min(len(acc), len(gyr)) // 2 * 2
    passo = FREQUENZA_ORIGINALE // FREQUENZA
    acc = acc[:n].reshape(-1, passo, 3).mean(axis=1)
    gyr = gyr[:n].reshape(-1, passo, 3).mean(axis=1)
    dati = pd.DataFrame(np.hstack([acc, gyr]), columns=["acc_x", "acc_y", "acc_z", "gyr_x", "gyr_y", "gyr_z"])
    dati.insert(0, "t_s", np.arange(len(dati)) / FREQUENZA)  # i file non hanno il tempo: indice / frequenza
    return dati


def finestre(radice, sensore, durata):
    borg = leggi_borg(radice)
    righe, scartate = [], []
    for _, r in borg.iterrows():
        soggetto = int(str(r["subject"]).split("_")[1])
        cartella, tipo, carico = ESERCIZI[r["task_order"]]
        dati = leggi_sensore(radice, cartella, soggetto, sensore)
        durata_prova = float(r["length_of_trial_(sec)"])
        if abs(dati["t_s"].iloc[-1] - durata_prova) > DIFFERENZA_MASSIMA_S:
            scartate.append(f"S{soggetto:02d} {r['task_order']}")
            continue
        for k in range(1, int(durata_prova // durata) + 1):
            colonna = f"{int(k * durata)}_sec"
            if colonna not in borg.columns or pd.isna(r[colonna]):
                continue
            inizio, fine = (k - 1) * durata, k * durata
            riga = {"persona": f"S{soggetto:02d}", "esercizio": r["task_order"], "tipo": tipo,
                    "carico": carico, "finestra": k, "inizio_s": inizio, "fine_s": fine,
                    "borg": float(r[colonna]), "progresso": round(fine / durata_prova, 3)}
            riga.update(misure.misure_orologio(misure.taglia(dati, inizio, fine), FREQUENZA))
            righe.append(riga)
    if scartate:
        print(f"Prove scartate perché la durata dei dati non coincide con quella dichiarata: {', '.join(scartate)}")
    return pd.DataFrame(righe)


def riassunto(tabella):
    """Per ogni misura: quanto segue la fatica DENTRO ogni prova, e prima vs ultima finestra."""
    nomi = [c for c in tabella.columns if c.startswith("polso_")]
    prove = tabella.groupby(["persona", "esercizio"])
    print(f"\n{len(tabella)} finestre, {prove.ngroups} prove, {tabella['persona'].nunique()} persone. "
          f"Borg mediano: prima finestra {prove['borg'].first().median():g}, ultima {prove['borg'].last().median():g}")
    print(f"\n{'misura':26s} {'rho mediana':>11s} {'prove concordi':>15s} {'prima->ultima':>14s} {'p (Wilcoxon)':>13s}")
    primo, ultimo = prove.first(), prove.last()
    for nome in nomi:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rho = prove.apply(lambda g: stats.spearmanr(g[nome], g["borg"])[0] if len(g) >= 4 else np.nan,
                              include_groups=False).dropna()
        if not len(rho):
            continue
        concordi = np.mean(np.sign(rho) == np.sign(rho.median())) * 100
        coppie = pd.concat([primo[nome], ultimo[nome]], axis=1).dropna()
        variazione = (100 * (coppie.iloc[:, 1] - coppie.iloc[:, 0]) / coppie.iloc[:, 0].replace(0, np.nan)).median()
        p = stats.wilcoxon(coppie.iloc[:, 0], coppie.iloc[:, 1]).pvalue if len(coppie) > 10 else np.nan
        print(f"{nome:26s} {rho.median():+11.2f} {concordi:14.0f}% {variazione:+13.1f}% {p:13.1e}")
    print("\nrho = correlazione di Spearman tra la misura e il Borg nella stessa prova "
          "(negativa: la misura cala quando la fatica sale).")


def main():
    parser = argparse.ArgumentParser(description="Dataset di Yasar et al. nel formato del framework.")
    parser.add_argument("cartella", help="Cartella WSD4FEDSRM estratta dallo zip")
    parser.add_argument("--sensore", default="Forearm", choices=list(SENSORI), help="Parte del corpo")
    parser.add_argument("--finestra", type=int, default=10, choices=[10, 20, 30],
                        help="Durata delle finestre in secondi (multiplo di 10, come il Borg)")
    parser.add_argument("--uscita", default="data/yasar_finestre.csv", help="File CSV di uscita")
    args = parser.parse_args()

    radice = Path(args.cartella)
    if not (radice / "Borg data").exists():
        sotto = radice / "WSD4FEDSRM"
        if (sotto / "Borg data").exists():
            radice = sotto
        else:
            raise SystemExit("Non trovo la cartella 'Borg data': indica la cartella WSD4FEDSRM estratta dallo zip.")

    tabella = finestre(radice, args.sensore, args.finestra)
    Path(args.uscita).parent.mkdir(parents=True, exist_ok=True)
    tabella.to_csv(args.uscita, index=False)
    print(f"Sensore: {args.sensore}. Tabella -> {args.uscita}")
    riassunto(tabella)


if __name__ == "__main__":
    main()
