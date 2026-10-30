"""Un comando unico che elabora uno o più video dall'inizio alla fine.

Per ogni video esegue solo i passaggi che mancano:
  1. posa, viso, testa e mani   (estrai_da_video.py)   -> *_pose.csv, *_viso.csv, *_mani.csv
  2. emozioni                    (estrai_emozioni.py)   -> *_emozioni.csv
  3. misure su finestre di tempo (analisi_finestre.py)  -> *_finestre.csv
e alla fine stampa un breve controllo di qualità.

Con --forza rifà tutti i passaggi anche se i file esistono già
(utile dopo un aggiornamento del codice, per esempio per avere l'orientamento della testa).

Uso:
    python src/elabora.py data/20261026_003537_test_emozioni.mp4
    python src/elabora.py data/*.mp4 --persona P01 --etichetta riposata
    python src/elabora.py data/*.mp4 --forza
"""

import argparse
import glob
from pathlib import Path

import pandas as pd

import analisi_finestre
import estrai_da_video
import estrai_emozioni
import misure


def esiste(base, suffisso):
    percorso = Path(str(base) + suffisso)
    return percorso.exists() and percorso.stat().st_size > 0


def manca_orientamento_testa(base):
    """True se il file del viso è stato creato da una versione senza gli angoli della testa."""
    if not esiste(base, "_viso.csv"):
        return True
    return "testa_pitch" not in pd.read_csv(str(base) + "_viso.csv", nrows=1).columns


def main():
    parser = argparse.ArgumentParser(description="Elabora uno o più video dall'inizio alla fine.")
    parser.add_argument("video", nargs="+", help="Uno o più file video")
    parser.add_argument("--persona", default="", help="Codice della persona (es. P01)")
    parser.add_argument("--etichetta", default="", help="Stato della persona (es. riposata)")
    parser.add_argument("--finestra", type=float, default=30, help="Durata delle finestre in secondi")
    parser.add_argument("--emozioni-ogni", type=int, default=5, help="Emozioni: un fotogramma ogni N")
    parser.add_argument("--forza", action="store_true", help="Rifà tutti i passaggi")
    args = parser.parse_args()

    percorsi = []
    for schema in args.video:
        percorsi += sorted(glob.glob(schema)) or [schema]

    modello_emozioni = None
    for percorso in percorsi:
        video = Path(percorso)
        base = estrai_da_video.base_video(video)
        print(f"\n=== {video.name} ===")

        if args.forza or manca_orientamento_testa(base) or not esiste(base, "_mani.csv"):
            print("1. Estraggo posa, viso, testa e mani...")
            estrai_da_video.elabora(video)
        else:
            print("1. Posa, viso, testa e mani: già presenti.")

        if args.forza or not esiste(base, "_emozioni.csv"):
            print("2. Stimo le emozioni...")
            if modello_emozioni is None:
                modello_emozioni = estrai_emozioni.crea_modello_emozioni()
            estrai_emozioni.elabora(video, max(1, args.emozioni_ogni), modello_emozioni)
        else:
            print("2. Emozioni: già presenti.")

        print(f"3. Calcolo le misure su finestre di {args.finestra:g} secondi...")
        righe = analisi_finestre.finestre_di_una_sessione(
            base, args.persona, args.etichetta, args.finestra, args.finestra)
        if righe:
            pd.DataFrame(righe).to_csv(str(base) + "_finestre.csv", index=False)

        qualita = misure.misure_qualita(misure.leggi_se_esiste(base, "_pose.csv"))
        if qualita:
            print(f"   Qualità: {qualita.get('fps_medi')} fotogrammi al secondo, "
                  f"salto massimo {qualita.get('pausa_max_s')} s, "
                  f"salti oltre 0,5 s: {qualita.get('pause_oltre_0.5s')}")
            if (qualita.get("pausa_max_s") or 0) > 1.0:
                print("   Attenzione: c'è almeno un salto di oltre 1 secondo tra due fotogrammi.")

    print("\nFatto.")


if __name__ == "__main__":
    main()
