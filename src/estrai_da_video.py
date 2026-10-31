"""Estrae posa, viso, testa e mani da un video.

Per ogni video crea, accanto al video, i file della sessione:
  *_viso.csv  i 52 "blendshape" del viso, cioè quanto è attivo ogni movimento
              (es. eyeBlinkLeft = palpebra sinistra chiusa, jawOpen = bocca aperta),
              con valori da 0 a 1, più l'orientamento della testa in gradi:
              testa_pitch (su/giù: POSITIVO = testa verso il basso, NEGATIVO = verso l'alto),
              testa_yaw (destra/sinistra), testa_roll (inclinata).
              Lo zero dipende dall'altezza della webcam: conta il cambiamento
              rispetto alla stessa persona, non il valore assoluto.
  *_mani.csv  i 21 punti di ogni mano visibile (x, y, z)
  *_pose.csv  i 33 punti del corpo, SOLO se non esiste già. Serve per i video che
              non vengono dal nostro script di acquisizione (per esempio quelli
              di un dataset pubblico).
  *_pose3d.csv i 33 punti del corpo in METRI (profondità compresa), se non esiste già.
              Così anche le registrazioni fatte con le versioni precedenti
              ottengono la profondità.

Il tempo t_s di ogni fotogramma viene preso dal file *_pose.csv della stessa
sessione se esiste (così tutti i segnali stanno sullo stesso orologio),
altrimenti dal numero del fotogramma diviso per i fotogrammi al secondo del video.

Uso:
    python src/estrai_da_video.py data/20261018_175018_mattina.mp4
    python src/estrai_da_video.py data/*.mp4
"""

import argparse
import csv
import glob
import math
import os
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
from mediapipe.tasks.python import BaseOptions, vision

CARTELLA_PROGETTO = Path(__file__).resolve().parents[1]
MODELLO_POSA = CARTELLA_PROGETTO / "models" / "pose_landmarker_full.task"
MODELLO_VISO = CARTELLA_PROGETTO / "models" / "face_landmarker.task"
MODELLO_MANI = CARTELLA_PROGETTO / "models" / "hand_landmarker.task"
NOMI_PUNTI = [p.name.lower() for p in vision.PoseLandmark]


def base_video(video):
    """data/xxx.mp4 -> data/xxx (funziona con qualunque estensione: .mp4, .mov, .avi...)"""
    return Path(video).with_suffix("")


def tempi_dalla_posa(video):
    """Tempi dei fotogrammi registrati dallo script di acquisizione, se disponibili."""
    posa = Path(str(base_video(video)) + "_pose.csv")
    if posa.exists():
        df = pd.read_csv(posa, usecols=["frame", "t_s"])
        return dict(zip(df["frame"], df["t_s"]))
    return {}


def angoli_testa(matrice):
    """Dalla matrice di trasformazione del viso (4x4) all'orientamento della testa,
    in gradi: pitch (su/giù), yaw (destra/sinistra), roll (testa inclinata).
    Verificato il 30/10/2026: pitch positivo = testa abbassata, negativo = testa alzata."""
    r = np.asarray(matrice, dtype=float)[:3, :3]
    pitch = math.degrees(math.atan2(r[2, 1], r[2, 2]))
    yaw = math.degrees(math.atan2(-r[2, 0], math.hypot(r[2, 1], r[2, 2])))
    roll = math.degrees(math.atan2(r[1, 0], r[0, 0]))
    return round(pitch, 2), round(yaw, 2), round(roll, 2)


def crea_rilevatori(con_posa):
    viso = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODELLO_VISO)),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
    ))
    mani = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODELLO_MANI)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
    ))
    posa = None
    if con_posa:
        posa = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(MODELLO_POSA)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
        ))
    return viso, mani, posa


def riga_viso(frame, t_s, risultato):
    """Una riga con i 52 valori del viso e i 3 angoli della testa, oppure None."""
    if not risultato.face_blendshapes:
        return None
    categorie = risultato.face_blendshapes[0]
    nomi = [c.category_name for c in categorie] + ["testa_pitch", "testa_yaw", "testa_roll"]
    if risultato.facial_transformation_matrixes:
        angoli = list(angoli_testa(risultato.facial_transformation_matrixes[0]))
    else:
        angoli = ["", "", ""]
    return [frame, t_s] + [round(c.score, 4) for c in categorie] + angoli, nomi


def righe_mani(frame, t_s, risultato):
    """Una riga per ogni mano visibile nel fotogramma."""
    righe = []
    for lato, punti in zip(risultato.handedness, risultato.hand_landmarks):
        riga = [frame, t_s, lato[0].category_name, round(lato[0].score, 3)]
        for p in punti:
            riga += [round(p.x, 5), round(p.y, 5), round(p.z, 5)]
        righe.append(riga)
    return righe


def riga_posa(frame, t_s, risultato):
    if not risultato.pose_landmarks:
        return None
    riga = [frame, t_s]
    for p in risultato.pose_landmarks[0]:
        riga += [round(p.x, 5), round(p.y, 5), round(p.z, 5), round(p.visibility, 3)]
    return riga


def riga_posa_3d(frame, t_s, risultato):
    """I 33 punti in metri ("world landmarks"), oppure None."""
    if not getattr(risultato, "pose_world_landmarks", None):
        return None
    riga = [frame, t_s]
    for p in risultato.pose_world_landmarks[0]:
        riga += [round(p.x, 4), round(p.y, 4), round(p.z, 4)]
    return riga


def parziale(nome):
    """Nome temporaneo: si scrive qui e si rinomina solo alla fine. Così, se il PC
    si spegne a metà, non resta un file incompleto con il nome di quello vero."""
    return nome + ".parziale"


def elabora(video):
    video = Path(video)
    base = str(base_video(video))
    tempi = tempi_dalla_posa(video)
    scrivi_posa_2d = not tempi  # la posa la scriviamo solo se non c'è già
    scrivi_posa_3d = not Path(base + "_pose3d.csv").exists()
    con_posa = scrivi_posa_2d or scrivi_posa_3d
    filmato = cv2.VideoCapture(str(video))
    if not filmato.isOpened():
        print(f"{video.name}: non riesco ad aprire il video, lo salto.")
        return
    fps = filmato.get(cv2.CAP_PROP_FPS) or 30
    totale = int(filmato.get(cv2.CAP_PROP_FRAME_COUNT))

    rilevatore_viso, rilevatore_mani, rilevatore_posa = crea_rilevatori(con_posa)
    finali = [base + "_viso.csv", base + "_mani.csv"]
    if scrivi_posa_2d:
        finali.append(base + "_pose.csv")
    if scrivi_posa_3d:
        finali.append(base + "_pose3d.csv")
    f_posa = open(parziale(base + "_pose.csv"), "w", newline="") if scrivi_posa_2d else None
    f_posa_3d = open(parziale(base + "_pose3d.csv"), "w", newline="") if scrivi_posa_3d else None
    try:
        with rilevatore_viso, rilevatore_mani, \
                open(parziale(base + "_viso.csv"), "w", newline="") as f_viso, \
                open(parziale(base + "_mani.csv"), "w", newline="") as f_mani:
            scrivi_viso, scrivi_mani = csv.writer(f_viso), csv.writer(f_mani)
            intestazione_viso_scritta = False
            scrivi_mani.writerow(["frame", "t_s", "mano", "sicurezza"]
                                 + [f"p{i}_{a}" for i in range(21) for a in "xyz"])
            scrivi_posa = scrivi_posa_3d_csv = None
            if scrivi_posa_2d:
                scrivi_posa = csv.writer(f_posa)
                scrivi_posa.writerow(["frame", "t_s"] + [f"{n}_{a}" for n in NOMI_PUNTI
                                                         for a in ("x", "y", "z", "vis")])
            if scrivi_posa_3d:
                scrivi_posa_3d_csv = csv.writer(f_posa_3d)
                scrivi_posa_3d_csv.writerow(["frame", "t_s"] + [f"{n}_{a}" for n in NOMI_PUNTI
                                                                for a in ("x", "y", "z")])

            frame, ultimo_ms, con_viso, con_mani, con_corpo = 0, -1, 0, 0, 0
            while True:
                ok, immagine = filmato.read()
                if not ok:
                    break
                t_s = round(float(tempi.get(frame, frame / fps)), 4)
                ms = max(int(t_s * 1000), ultimo_ms + 1)
                ultimo_ms = ms
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB,
                                  data=cv2.cvtColor(immagine, cv2.COLOR_BGR2RGB))

                risultato_viso = riga_viso(frame, t_s, rilevatore_viso.detect_for_video(mp_img, ms))
                if risultato_viso is not None:
                    riga, nomi = risultato_viso
                    if not intestazione_viso_scritta:
                        scrivi_viso.writerow(["frame", "t_s"] + nomi)
                        intestazione_viso_scritta = True
                    scrivi_viso.writerow(riga)
                    con_viso += 1

                righe = righe_mani(frame, t_s, rilevatore_mani.detect_for_video(mp_img, ms))
                scrivi_mani.writerows(righe)
                con_mani += bool(righe)

                if con_posa:
                    risultato_posa = rilevatore_posa.detect_for_video(mp_img, ms)
                    riga = riga_posa(frame, t_s, risultato_posa)
                    if riga is not None:
                        con_corpo += 1
                        if scrivi_posa_2d:
                            scrivi_posa.writerow(riga)
                    riga3d = riga_posa_3d(frame, t_s, risultato_posa)
                    if riga3d is not None and scrivi_posa_3d:
                        scrivi_posa_3d_csv.writerow(riga3d)

                frame += 1
                if frame % 300 == 0:
                    print(f"  {video.name}: {frame}/{totale} fotogrammi")
    finally:
        for f in (f_posa, f_posa_3d):
            if f is not None:
                f.close()
        if rilevatore_posa is not None:
            rilevatore_posa.close()
        filmato.release()

    # Arrivati qui l'elaborazione è finita: i file temporanei diventano quelli veri
    for nome in finali:
        os.replace(parziale(nome), nome)

    messaggio = f"{video.name}: viso in {con_viso}/{frame} fotogrammi, mani in {con_mani}/{frame}"
    if con_posa:
        cosa = "posa e profondità" if scrivi_posa_2d else "profondità"
        messaggio += f", corpo in {con_corpo}/{frame} ({cosa} estratte dal video)"
    print(messaggio + ".")


def main():
    parser = argparse.ArgumentParser(description="Estrae posa, viso, testa e mani dai video.")
    parser.add_argument("video", nargs="+", help="Uno o più file video (.mp4, .mov, .avi...)")
    args = parser.parse_args()

    for modello in (MODELLO_POSA, MODELLO_VISO, MODELLO_MANI):
        if not modello.exists():
            raise SystemExit(f"Manca {modello.name}. Esegui prima:  python scarica_modelli.py")

    percorsi = []
    for schema in args.video:
        percorsi += sorted(glob.glob(schema)) or [schema]
    for percorso in percorsi:
        elabora(percorso)


if __name__ == "__main__":
    main()
