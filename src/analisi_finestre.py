"""La "tabella delle finestre": le misure calcolate ogni N secondi.

Per la profilazione non basta un numero per tutta la sessione: serve vedere
come la persona cambia nel tempo. Questo script divide ogni sessione in
finestre (di default 30 secondi) e calcola tutte le misure per ognuna.
Il risultato è una sola tabella: una riga per finestra, con chi è la persona,
in che stato era (l'etichetta) e tutte le misure.

Due modi di indicare persona ed etichetta:

  1. Le stesse per tutte le sessioni indicate:
       python src/analisi_finestre.py data/*_mattina_pose.csv --persona P01 --etichetta riposata

  2. Un file CSV di elenco, utile per i dataset con molte persone, con le colonne
     file, persona, etichetta (file = un qualunque file della sessione):
       python src/analisi_finestre.py --elenco elenco_sessioni.csv

Opzioni: --finestra (secondi, default 30), --passo (secondi, default = finestra,
cioè finestre che non si sovrappongono), --uscita (default data/finestre.csv).
Le finestre in cui la persona si vede per meno di metà del tempo vengono scartate.
Funziona anche con sessioni di solo orologio (create da importa_orologio.py senza --sessione).
"""

import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd

import misure

COPERTURA_MINIMA = 50  # % minima di fotogrammi con la persona visibile


def finestre_di_una_sessione(base, persona, etichetta, durata, passo):
    sessione = misure.carica_sessione(base)
    # Il tempo di riferimento: la webcam se c'è, altrimenti solo l'orologio
    riferimento = next((sessione[k] for k in ("posa", "viso", "orologio") if sessione[k] is not None), None)
    if riferimento is None or len(riferimento) < 10:
        print(f"  {sessione['nome']}: nessun dato di posa, viso o orologio, salto la sessione.")
        return []
    if sessione["posa"] is None and sessione["viso"] is None:
        riferimento = riferimento[riferimento["gyr_x"].notna()]  # solo i campioni dell'orologio presenti

    tempi = riferimento["t_s"]
    inizio_sessione, fine_sessione = tempi.iloc[0], tempi.iloc[-1]
    fps = (len(tempi) - 1) / (fine_sessione - inizio_sessione) if fine_sessione > inizio_sessione else 0

    righe, scartate = [], 0
    for k, inizio in enumerate(np.arange(inizio_sessione, fine_sessione - durata + 1e-9, passo)):
        fine = inizio + durata
        presenti = int(((tempi >= inizio) & (tempi < fine)).sum())
        copertura = min(100.0, presenti / (fps * durata) * 100) if fps else 0
        if copertura < COPERTURA_MINIMA:
            scartate += 1
            continue
        riga = {
            "persona": persona,
            "sessione": sessione["nome"],
            "etichetta": etichetta,
            "finestra": k,
            "inizio_s": round(float(inizio - inizio_sessione), 2),
            "fine_s": round(float(fine - inizio_sessione), 2),
            "copertura_%": round(copertura, 1),
        }
        riga.update(misure.tutte_le_misure(sessione, inizio, fine))
        righe.append(riga)

    print(f"  {sessione['nome']}: {len(righe)} finestre"
          + (f" ({scartate} scartate perché la persona si vedeva poco)" if scartate else ""))
    return righe


def leggi_elenco(args):
    """Restituisce una lista di (base della sessione, persona, etichetta)."""
    if args.elenco:
        elenco = pd.read_csv(args.elenco)
        mancanti = {"file", "persona", "etichetta"} - set(elenco.columns)
        if mancanti:
            raise SystemExit(f"Nell'elenco mancano le colonne: {', '.join(sorted(mancanti))}")
        return [(misure.base_sessione(r.file), str(r.persona), str(r.etichetta))
                for r in elenco.itertuples()]
    if not args.file:
        raise SystemExit("Indica dei file di sessione oppure --elenco.")
    percorsi = []
    for schema in args.file:
        percorsi += sorted(glob.glob(schema)) or [schema]
    basi = list(dict.fromkeys(misure.base_sessione(p) for p in percorsi))  # senza doppioni
    return [(b, args.persona, args.etichetta) for b in basi]


def main():
    parser = argparse.ArgumentParser(description="Calcola le misure su finestre di tempo.")
    parser.add_argument("file", nargs="*", help="File delle sessioni (es. data/*_pose.csv)")
    parser.add_argument("--elenco", help="CSV con colonne file, persona, etichetta")
    parser.add_argument("--persona", default="", help="Codice della persona (es. P01)")
    parser.add_argument("--etichetta", default="", help="Stato della persona (es. riposata)")
    parser.add_argument("--finestra", type=float, default=30, help="Durata di una finestra in secondi")
    parser.add_argument("--passo", type=float, default=None, help="Distanza tra l'inizio di due finestre")
    parser.add_argument("--uscita", default="data/finestre.csv", help="File CSV di uscita")
    args = parser.parse_args()

    passo = args.passo or args.finestra
    righe = []
    for base, persona, etichetta in leggi_elenco(args):
        righe += finestre_di_una_sessione(base, persona, etichetta, args.finestra, passo)

    if not righe:
        raise SystemExit("Nessuna finestra calcolata.")
    tabella = pd.DataFrame(righe)
    Path(args.uscita).parent.mkdir(parents=True, exist_ok=True)
    tabella.to_csv(args.uscita, index=False)
    print(f"\nTabella delle finestre: {len(tabella)} righe, {tabella.shape[1]} colonne -> {args.uscita}")


if __name__ == "__main__":
    main()
