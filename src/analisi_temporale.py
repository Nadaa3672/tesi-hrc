"""Analisi temporale: la stessa persona "prima e dopo".

Parte da una tabella delle finestre (una riga ogni N secondi, con le misure),
prodotta da analisi_finestre.py (dati propri) o da yasar.py (dataset pubblico),
e risponde a due domande.

1. CLASSIFICAZIONE (si riconosce lo stato della persona?)
   Addestra modelli di machine learning (scikit-learn) a riconoscere 2 o 3 stati
   (es. poco / molto affaticata) e li valuta su persone MAI viste in addestramento
   ("leave-one-subject-out": a turno si tiene fuori una persona e la si usa come prova).
   Confronta più gruppi di caratteristiche:
     - solo tempo      : i secondi dall'inizio. È il confronto onesto: se il tempo
                         basta da solo, le misure non aggiungono nulla;
     - misure          : le nostre misure così come sono;
     - misure rel      : le stesse misure meno quelle di riferimento DELLA STESSA PERSONA
                         (la sua "linea di base"): è l'idea del "prima e dopo";
     - catch22 (rel)   : le 22 caratteristiche standard catch22, se ci sono nella tabella;
     - tutto rel + tempo.
   La linea di base può essere:
     --base sequenza  : la prima finestra (o le prime N) della stessa sequenza (default);
     --base persona   : le finestre della persona con l'etichetta di riferimento
                        (es. --riferimento riposata), utile per sessioni diverse della stessa persona.

2. CAMBIAMENTI (--cambiamenti: quando è cambiato qualcosa?)
   Per ogni sequenza cerca il momento in cui le misure cambiano di più rispetto
   all'inizio (rilevamento di un punto di cambiamento con la libreria ruptures).
   Ha senso su sessioni lunghe (decine di finestre).

Uso:
    python src/analisi_temporale.py data/yasar_finestre.csv --etichetta borg --soglie 12 17
    python src/analisi_temporale.py data/yasar_finestre.csv --etichetta borg --soglie 12 17 --tre-classi
    python src/analisi_temporale.py data/finestre.csv --etichetta etichetta --base persona --riferimento riposata --gruppi sessione
    python src/analisi_temporale.py data/finestre.csv --cambiamenti

Risultati: <tabella>_classificazione.csv e/o <tabella>_cambiamenti.csv accanto alla tabella.
"""

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# Colonne che descrivono la finestra, non la persona: non sono caratteristiche
DESCRITTIVE = {"persona", "sequenza", "calibrazione", "sessione", "esercizio", "tipo", "carico", "etichetta", "finestra",
               "inizio_s", "fine_s", "borg", "progresso", "copertura_%", "fps_medi", "pausa_max_s",
               "pause_oltre_0.5s", "battito_valido_%", "silenzio_digitale_%", "emozione_prevalente"}


# ---------------------------------------------------------------- preparazione

def aggiungi_sequenza(tabella):
    """Una colonna 'sequenza' = una registrazione continua di una persona
    (persona + sessione, oppure persona + esercizio nel dataset di Yasar)."""
    for nome in ("sessione", "esercizio"):
        if nome in tabella.columns:
            tabella = tabella.copy()
            tabella["sequenza"] = tabella["persona"].astype(str) + " | " + tabella[nome].astype(str)
            return tabella, "sequenza"
    raise SystemExit("Nella tabella manca una colonna 'sessione' o 'esercizio'.")


def caratteristiche(tabella):
    """Le colonne numeriche che descrivono la persona: misure "nostre" e catch22."""
    numeriche = [c for c in tabella.columns
                 if c not in DESCRITTIVE and pd.api.types.is_numeric_dtype(tabella[c])
                 and tabella[c].notna().mean() > 0.5]
    catch22 = [c for c in numeriche if c.startswith("c22_")]
    return [c for c in numeriche if c not in catch22], catch22


def aggiungi_relative(tabella, colonne, base, sequenza, finestre_base, riferimento, etichetta):
    """Aggiunge <colonna>_rel = valore meno la linea di base della stessa persona,
    e la colonna 'calibrazione' = True per le finestre usate come linea di base
    (non vengono usate per valutare i modelli).

    --base sequenza: le prime finestre_base finestre di ogni sequenza.
    --base persona : le prime finestre_base finestre della PRIMA sessione della persona
                     con l'etichetta di riferimento (es. la prima sessione "riposata"):
                     come una breve calibrazione fatta una volta sola."""
    ordine = [sequenza, "inizio_s"] if "inizio_s" in tabella.columns else [sequenza]
    tabella = tabella.sort_values(ordine).copy()
    if base == "sequenza":
        calibrazione = tabella.groupby(sequenza).cumcount() < finestre_base
        chiave = tabella[sequenza]
    else:
        if riferimento is None:
            raise SystemExit("Con --base persona serve --riferimento (es. --riferimento riposata).")
        rif = tabella[tabella[etichetta].astype(str) == str(riferimento)]
        if rif.empty:
            raise SystemExit(f"Nessuna finestra con {etichetta} = {riferimento}.")
        prima_sessione = rif.groupby("persona")[sequenza].min()  # i nomi iniziano con data e ora
        calibrazione = ((tabella[sequenza] == tabella["persona"].map(prima_sessione))
                        & (tabella.groupby(sequenza).cumcount() < finestre_base))
        chiave = tabella["persona"]
    riferimento_valori = tabella[calibrazione].groupby(chiave[calibrazione])[colonne].mean()
    base_righe = riferimento_valori.reindex(chiave.to_numpy()).to_numpy()
    relative = pd.DataFrame(tabella[colonne].to_numpy() - base_righe,
                            columns=[c + "_rel" for c in colonne], index=tabella.index)
    tabella["calibrazione"] = calibrazione
    return pd.concat([tabella, relative], axis=1)


def classi(tabella, etichetta, soglie, tre_classi):
    """Le classi da riconoscere. Etichetta numerica + soglie (es. Borg 12 e 17):
    2 classi = fino a 12 / da 17 in su (le finestre intermedie si tolgono);
    3 classi = fino a 12 / 13-16 / da 17 in su. Etichetta testuale: usata così com'è."""
    valori = tabella[etichetta]
    if soglie:
        basso, alto = soglie
        if tre_classi:
            y = np.where(valori <= basso, "bassa", np.where(valori < alto, "media", "alta"))
        else:
            y = np.where(valori <= basso, "bassa", np.where(valori >= alto, "alta", ""))
        return pd.Series(y, index=tabella.index)
    return valori.astype(str)


# ---------------------------------------------------------------- 1. classificazione

def modelli():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return {
        "regressione logistica": make_pipeline(SimpleImputer(), StandardScaler(),
                                               LogisticRegression(max_iter=2000, class_weight="balanced")),
        "random forest": make_pipeline(SimpleImputer(), RandomForestClassifier(
            n_estimators=300, class_weight="balanced", random_state=0, n_jobs=-1)),
    }


def classifica(tabella, y, gruppi, insiemi, nome_gruppo):
    from sklearn.metrics import balanced_accuracy_score
    from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
    risultati = []
    for nome_insieme, colonne in insiemi.items():
        for nome_modello, modello in modelli().items():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                previsti = cross_val_predict(modello, tabella[colonne].to_numpy(dtype=float), y,
                                             groups=gruppi, cv=LeaveOneGroupOut())
            per_gruppo = [balanced_accuracy_score(y[gruppi == g], previsti[gruppi == g])
                          for g in np.unique(gruppi) if len(np.unique(y[gruppi == g])) > 1]
            risultati.append({"caratteristiche": nome_insieme, "n_caratteristiche": len(colonne),
                              "modello": nome_modello,
                              "accuratezza_bilanciata": round(balanced_accuracy_score(y, previsti), 3),
                              "mediana_per_gruppo": round(float(np.median(per_gruppo)), 3) if per_gruppo else None})
            print(f"  {nome_insieme:22s} {nome_modello:22s} {risultati[-1]['accuratezza_bilanciata']:.3f}"
                  f"   (mediana per {nome_gruppo}: "
                  f"{risultati[-1]['mediana_per_gruppo'] if risultati[-1]['mediana_per_gruppo'] is not None else '-'})")
    return pd.DataFrame(risultati)


# ---------------------------------------------------------------- 2. cambiamenti

def cambiamenti(tabella, sequenza, colonne, finestre_base, minimo_finestre=6):
    """Per ogni sequenza: il momento in cui le misure cambiano di più (un solo punto
    di cambiamento, algoritmo Binseg di ruptures) e quanto è forte il cambiamento."""
    import ruptures as rpt
    righe = []
    for nome, seq in tabella.sort_values([sequenza, "inizio_s"]).groupby(sequenza):
        if len(seq) < minimo_finestre:
            continue
        X = seq[colonne].to_numpy(dtype=float)
        X = np.where(np.isnan(X), np.nanmean(X, axis=0), X)
        X = np.nan_to_num((X - X[:finestre_base].mean(axis=0)) / (X.std(axis=0) + 1e-9))
        punto = rpt.Binseg(model="l2", min_size=2).fit(X).predict(n_bkps=1)[0]
        prima, dopo = X[:punto].mean(axis=0), X[punto:].mean(axis=0)
        righe.append({sequenza: nome, "persona": seq["persona"].iloc[0], "finestre": len(seq),
                      "cambio_s": float(seq["inizio_s"].iloc[punto]) if punto < len(seq) else None,
                      "forza_cambio": round(float(np.linalg.norm(dopo - prima) / np.sqrt(len(colonne))), 3),
                      "misura_che_cambia_di_piu": colonne[int(np.argmax(np.abs(dopo - prima)))]})
    return pd.DataFrame(righe)


# ---------------------------------------------------------------- programma

def main():
    parser = argparse.ArgumentParser(description="Analisi temporale: la stessa persona prima e dopo.")
    parser.add_argument("tabella", help="Tabella delle finestre (CSV)")
    parser.add_argument("--etichetta", default="etichetta", help="Colonna dello stato da riconoscere")
    parser.add_argument("--soglie", type=float, nargs=2, metavar=("BASSA", "ALTA"),
                        help="Per un'etichetta numerica (es. Borg): soglie delle classi, es. 12 17")
    parser.add_argument("--tre-classi", action="store_true", help="Con --soglie: 3 classi invece di 2")
    parser.add_argument("--base", choices=["sequenza", "persona"], default="sequenza",
                        help="Linea di base: inizio della stessa sequenza, o finestre di riferimento della persona")
    parser.add_argument("--finestre-base", type=int, default=1, help="Con --base sequenza: quante finestre iniziali")
    parser.add_argument("--riferimento", help="Con --base persona: l'etichetta della linea di base (es. riposata)")
    parser.add_argument("--gruppi", choices=["persona", "sessione"], default="persona",
                        help="Cosa tenere fuori a turno nella valutazione (sessione: se c'è una sola persona)")
    parser.add_argument("--cambiamenti", action="store_true", help="Cerca i punti di cambiamento in ogni sequenza")
    args = parser.parse_args()

    percorso = Path(args.tabella)
    tabella = pd.read_csv(percorso)
    tabella, sequenza = aggiungi_sequenza(tabella)
    misure_nostre, catch22 = caratteristiche(tabella)
    print(f"Tabella: {len(tabella)} finestre, {tabella['persona'].nunique()} persone, "
          f"{tabella[sequenza].nunique()} sequenze; {len(misure_nostre)} misure, {len(catch22)} catch22")
    tabella = aggiungi_relative(tabella, misure_nostre + catch22, args.base, sequenza,
                                args.finestre_base, args.riferimento, args.etichetta)
    rel = lambda colonne: [c + "_rel" for c in colonne]

    if args.cambiamenti:
        risultato = cambiamenti(tabella, sequenza, misure_nostre, args.finestre_base)
        uscita = percorso.with_name(percorso.stem + "_cambiamenti.csv")
        risultato.to_csv(uscita, index=False)
        print(f"\nPunti di cambiamento in {len(risultato)} sequenze -> {uscita}")
        if len(risultato):
            print(risultato.head(10).to_string(index=False))

    if args.etichetta in tabella.columns:
        y = classi(tabella, args.etichetta, args.soglie, args.tre_classi)
        tieni = (y != "") & y.notna()
        if args.base == "persona":  # le finestre di calibrazione non si usano per valutare
            tieni &= ~tabella["calibrazione"]
        costante = tabella[tieni].groupby(sequenza)[args.etichetta].nunique().max() == 1
        if costante and args.base == "sequenza":
            print("\nAttenzione: l'etichetta è la stessa in tutta ogni sequenza (es. una sessione 'riposata' e "
                  "una 'stanca'). Con --base sequenza le misure 'rel' cancellano proprio la differenza tra "
                  "sessioni: usa --base persona --riferimento <etichetta di riposo>.")
        dati, y = tabella[tieni], y[tieni].to_numpy()
        colonna_gruppi = "persona" if args.gruppi == "persona" else sequenza
        gruppi = dati[colonna_gruppi].to_numpy()
        if len(np.unique(gruppi)) < 2 or len(np.unique(y)) < 2:
            print("\nPer la classificazione servono almeno 2 gruppi e 2 classi: la salto.")
            return
        insiemi = {}
        if "inizio_s" in dati.columns and args.base == "sequenza":
            insiemi["solo tempo"] = ["inizio_s"]
        insiemi["misure"] = misure_nostre
        insiemi["misure rel"] = rel(misure_nostre)
        if catch22:
            insiemi["catch22"] = catch22
            insiemi["catch22 rel"] = rel(catch22)
            insiemi["misure+catch22 rel"] = rel(misure_nostre + catch22)
        if "solo tempo" in insiemi:
            insiemi["tutto rel + tempo"] = rel(misure_nostre + catch22) + ["inizio_s"]
        conteggi = pd.Series(y).value_counts().to_dict()
        print(f"\nClassificazione ({len(y)} finestre: {conteggi}); valutazione tenendo fuori "
              f"un{'a persona' if colonna_gruppi == 'persona' else ' gruppo'} alla volta "
              f"({len(np.unique(gruppi))} volte). Caso = {1 / len(conteggi):.2f}\n")
        risultato = classifica(dati, y, gruppi, insiemi, "persona" if colonna_gruppi == "persona" else "sessione")
        uscita = percorso.with_name(percorso.stem + "_classificazione.csv")
        risultato.to_csv(uscita, index=False)
        print(f"\nRisultati -> {uscita}")
        print("Accuratezza bilanciata: media delle percentuali di finestre riconosciute in ogni classe "
              "(0,5 con 2 classi = tirare a indovinare).")


if __name__ == "__main__":
    main()
