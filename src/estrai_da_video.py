"""Estrae viso e mani dai video già registrati con --video.

Per ogni video crea due file accanto agli altri della sessione:
  *_viso.csv  i 52 "blendshape" del viso, cioè quanto è attivo ogni movimento
              (es. eyeBlinkLeft = palpebra sinistra chiusa, jawOpen = bocca aperta),
              con valori da 0 a 1
  *_mani.csv  i 21 punti di ogni mano visibile (x, y, z)

Il tempo t_s di ogni fotogramma viene preso dal file *_pose.csv della stessa
sessione, così tutti i segnali stanno sullo stesso orologio.

Uso:
    python src/estrai_da_video.py data/20261018_175018_mattina.mp4
    python src/estrai_da_video.py data/*.mp4
"""

import argparse
import csv
import glob
from pathlib import Path

import cv2
import mediapipe as mp
import pandas as pd
from mediapipe.tasks.python import BaseOptions, vision

CARTELLA_PROGETTO = Path(__file__).resolve().parents[1]
MODELLO_VISO = CARTELLA_PROGETTO / "models" / "face_landmarker.task"
MODELLO_MANI = CARTELLA_PROGETTO / "models" / "hand_landmarker.task"


def tempi_dalla_posa(video):
    """Tempi dei fotogrammi registrati dallo script di acquisizione, se disponibili."""
    posa = Path(str(video).replace(".mp4", "_pose.csv"))
    if posa.exists():
        df = pd.read_csv(posa, usecols=["frame", "t_s"])
        return dict(zip(df["frame"], df["t_s"]))
    return {}


def crea_rilevatori():
    viso = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODELLO_VISO)),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        output_face_blendshapes=True,
    ))
    mani = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODELLO_MANI)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
    ))
    return viso, mani


def riga_viso(frame, t_s, risultato):
    """Una riga con i 52 valori del viso, oppure None se il viso non è visibile."""
    if not risultato.face_blendshapes:
        return None
    categorie = risultato.face_blendshapes[0]
    return [frame, t_s] + [round(c.score, 4) for c in categorie], [c.category_name for c in categorie]


def righe_mani(frame, t_s, risultato):
    """Una riga per ogni mano visibile nel fotogramma."""
    righe = []
    for lato, punti in zip(risultato.handedness, risultato.hand_landmarks):
        riga = [frame, t_s, lato[0].category_name, round(lato[0].score, 3)]
        for p in punti:
            riga += [round(p.x, 5), round(p.y, 5), round(p.z, 5)]
        righe.append(riga)
    return righe


def elabora(video):
    video = Path(video)
    tempi = tempi_dalla_posa(video)
    filmato = cv2.VideoCapture(str(video))
    fps = filmato.get(cv2.CAP_PROP_FPS) or 30
    totale = int(filmato.get(cv2.CAP_PROP_FRAME_COUNT))
    base = str(video).replace(".mp4", "")

    rilevatore_viso, rilevatore_mani = crea_rilevatori()
    with rilevatore_viso, rilevatore_mani, \
            open(base + "_viso.csv", "w", newline="") as f_viso, \
            open(base + "_mani.csv", "w", newline="") as f_mani:
        scrivi_viso, scrivi_mani = csv.writer(f_viso), csv.writer(f_mani)
        intestazione_viso_scritta = False
        scrivi_mani.writerow(["frame", "t_s", "mano", "sicurezza"]
                             + [f"p{i}_{a}" for i in range(21) for a in "xyz"])

        frame, ultimo_ms, con_viso, con_mani = 0, -1, 0, 0
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

            frame += 1
            if frame % 300 == 0:
                print(f"  {video.name}: {frame}/{totale} fotogrammi")

    filmato.release()
    print(f"{video.name}: viso in {con_viso}/{frame} fotogrammi, mani in {con_mani}/{frame}.")


def main():
    parser = argparse.ArgumentParser(description="Estrae viso e mani dai video registrati.")
    parser.add_argument("video", nargs="+", help="Uno o più file .mp4")
    args = parser.parse_args()

    for modello in (MODELLO_VISO, MODELLO_MANI):
        if not modello.exists():
            raise SystemExit(f"Manca {modello.name}. Esegui prima:  python scarica_modelli.py")

    percorsi = []
    for schema in args.video:
        percorsi += sorted(glob.glob(schema)) or [schema]
    for percorso in percorsi:
        elabora(percorso)


if __name__ == "__main__":
    main()
