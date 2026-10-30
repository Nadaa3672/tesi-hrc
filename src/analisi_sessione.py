"""Riepilogo di una o più sessioni intere, con un grafico di confronto.

Per ogni sessione calcola tutte le misure disponibili (vedi misure.py):
qualità della registrazione, corpo, viso e testa, mani, emozioni, audio,
più la durata dei compiti segnati con SPAZIO (*_eventi.csv).

Per l'analisi a finestre di pochi secondi, necessaria per la profilazione,
usa invece analisi_finestre.py.

Uso:
    python src/analisi_sessione.py data/20261018_093000_mattina_pose.csv
    python src/analisi_sessione.py data/*_mattina_pose.csv data/*_sera_pose.csv
"""

import argparse
import glob
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # salva i grafici su file senza aprire finestre
import matplotlib.pyplot as plt
import pandas as pd

import misure


def analizza(percorso):
    sessione = misure.carica_sessione(misure.base_sessione(percorso))
    posa = sessione["posa"]
    if posa is None or len(posa) < 10:
        raise SystemExit(f"{percorso}: dati della posa mancanti o troppo pochi.")

    riepilogo = {
        "sessione": sessione["nome"],
        "durata_s": round(posa["t_s"].iloc[-1] - posa["t_s"].iloc[0], 1),
        "fotogrammi": len(posa),
    }
    riepilogo.update(misure.tutte_le_misure(sessione))

    if sessione["eventi"] is not None:
        tempi = sessione["eventi"]["t_s"].tolist()
        for i in range(len(tempi) - 1):
            riepilogo[f"compito_{i + 1}_s"] = round(tempi[i + 1] - tempi[i], 1)

    scala = sessione["scala_spalle"]
    serie = pd.DataFrame({"t_s": posa["t_s"] - posa["t_s"].iloc[0],
                          "velocita_mani": misure.velocita_mani(posa, scala),
                          "altezza_testa": misure.altezza_testa(posa, scala)})
    return riepilogo, serie


def main():
    parser = argparse.ArgumentParser(description="Riepilogo di sessioni intere.")
    parser.add_argument("file", nargs="+", help="Uno o più file *_pose.csv")
    args = parser.parse_args()

    # Su Windows il terminale non espande gli asterischi: lo facciamo noi
    percorsi = []
    for schema in args.file:
        percorsi += sorted(glob.glob(schema)) or [schema]

    risultati = [analizza(p) for p in percorsi]

    tabella = pd.DataFrame([r for r, _ in risultati])
    print("\nRiepilogo delle sessioni (una riga per sessione):\n")
    # Le misure sono molte: le mostriamo in colonna, una sessione accanto all'altra
    print(tabella.set_index("sessione").T.to_string())

    avvisi = tabella[tabella.get("pausa_max_s", pd.Series(0, index=tabella.index)).fillna(0) > 1.0]
    for _, riga in avvisi.iterrows():
        print(f"\nAttenzione: in {riga['sessione']} c'è un salto di {riga['pausa_max_s']} s tra due "
              f"fotogrammi. Le misure di velocità e pausa vicino a quel punto sono meno affidabili.")

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
