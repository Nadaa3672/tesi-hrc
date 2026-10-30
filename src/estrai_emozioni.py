"""Stima le emozioni dal viso nei video registrati con --video.

Usa due modelli, uno dopo l'altro:
  1. MediaPipe Face Landmarker trova il viso e lo ritaglia;
  2. EmotiEffLib, modello "enet_b0_8_va_mtl" (una rete EfficientNet-B0 addestrata
     sul dataset AffectNet), guarda il ritaglio e stima:
       - la probabilità di 8 emozioni: rabbia, disprezzo, disgusto, paura,
         felicità, neutro, tristezza, sorpresa (somma = 1);
       - due valori continui: valenza (quanto l'espressione è positiva o
         negativa) e attivazione, in inglese "arousal" (quanto è intensa/agitata).

Analizza un fotogramma ogni N (di default 5, cioè circa 6 al secondo):
le espressioni cambiano lentamente e così l'elaborazione è più veloce.

Il modello delle emozioni viene scaricato da GitHub al primo uso e salvato
in C:\\Users\\<nome>\\.emotiefflib (una volta sola, circa 15 MB).

Uso:
    python src/estrai_emozioni.py data/*.mp4
    python src/estrai_emozioni.py data/20261018_175018_mattina.mp4 --ogni 3
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
MODELLO_EMOZIONI = "enet_b0_8_va_mtl"

# Stesso ordine delle uscite del modello (Anger, Contempt, Disgust, Fear,
# Happiness, Neutral, Sadness, Surprise), tradotto in italiano
EMOZIONI = ["rabbia", "disprezzo", "disgusto", "paura", "felicita", "neutro", "tristezza", "sorpresa"]


def tempi_dalla_posa(video):
    posa = Path(str(Path(video).with_suffix("")) + "_pose.csv")
    if posa.exists():
        df = pd.read_csv(posa, usecols=["frame", "t_s"])
        return dict(zip(df["frame"], df["t_s"]))
    return {}


def ritaglia_viso(immagine_rgb, punti, margine=0.15):
    """Ritaglio quadrato attorno ai punti del viso, con un piccolo margine."""
    altezza, larghezza = immagine_rgb.shape[:2]
    xs = [p.x * larghezza for p in punti]
    ys = [p.y * altezza for p in punti]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    lato = max(max(xs) - min(xs), max(ys) - min(ys)) * (1 + 2 * margine)
    sinistra, destra = int(max(0, cx - lato / 2)), int(min(larghezza, cx + lato / 2))
    alto, basso = int(max(0, cy - lato / 2)), int(min(altezza, cy + lato / 2))
    if destra - sinistra < 32 or basso - alto < 32:
        return None  # viso troppo piccolo o fuori dall'immagine
    return immagine_rgb[alto:basso, sinistra:destra]


def crea_rilevatore_viso():
    # Uno nuovo per ogni video: in modalità VIDEO i tempi devono sempre crescere,
    # e ogni video ricomincia da zero.
    return vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODELLO_VISO)),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
    ))


def crea_modello_emozioni():
    from emotiefflib.facial_analysis import EmotiEffLibRecognizer
    return EmotiEffLibRecognizer(engine="onnx", model_name=MODELLO_EMOZIONI)


def riga_emozioni(frame, t_s, punteggi):
    """punteggi = 8 probabilità + valenza + attivazione (in quest'ordine)."""
    probabilita = [float(v) for v in punteggi[:8]]
    valenza, attivazione = float(punteggi[8]), float(punteggi[9])
    prevalente = EMOZIONI[max(range(8), key=lambda i: probabilita[i])]
    return ([frame, t_s, prevalente] + [round(p, 4) for p in probabilita]
            + [round(valenza, 4), round(attivazione, 4)])


def elabora(video, ogni, emozioni):
    video = Path(video)
    tempi = tempi_dalla_posa(video)
    filmato = cv2.VideoCapture(str(video))
    fps = filmato.get(cv2.CAP_PROP_FPS) or 30
    totale = int(filmato.get(cv2.CAP_PROP_FRAME_COUNT))
    uscita = str(video.with_suffix("")) + "_emozioni.csv"

    with crea_rilevatore_viso() as viso, open(uscita, "w", newline="") as f:
        scrittore = csv.writer(f)
        scrittore.writerow(["frame", "t_s", "emozione"] + EMOZIONI + ["valenza", "attivazione"])
        frame, analizzati, con_viso, ultimo_ms = 0, 0, 0, -1
        while True:
            ok, immagine = filmato.read()
            if not ok:
                break
            if frame % ogni == 0:
                t_s = round(float(tempi.get(frame, frame / fps)), 4)
                ms = max(int(t_s * 1000), ultimo_ms + 1)
                ultimo_ms = ms
                rgb = cv2.cvtColor(immagine, cv2.COLOR_BGR2RGB)
                risultato = viso.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ms)
                analizzati += 1
                if risultato.face_landmarks:
                    ritaglio = ritaglia_viso(rgb, risultato.face_landmarks[0])
                    if ritaglio is not None:
                        _, punteggi = emozioni.predict_emotions(ritaglio, logits=False)
                        scrittore.writerow(riga_emozioni(frame, t_s, punteggi[0]))
                        con_viso += 1
            frame += 1
            if frame % 600 == 0:
                print(f"  {video.name}: {frame}/{totale} fotogrammi")

    filmato.release()
    print(f"{video.name}: emozioni stimate in {con_viso}/{analizzati} fotogrammi analizzati -> {Path(uscita).name}")


def main():
    parser = argparse.ArgumentParser(description="Stima le emozioni dal viso nei video registrati.")
    parser.add_argument("video", nargs="+", help="Uno o più file video (.mp4, .mov, .avi...)")
    parser.add_argument("--ogni", type=int, default=5,
                        help="Analizza un fotogramma ogni N (default 5)")
    args = parser.parse_args()

    if not MODELLO_VISO.exists():
        raise SystemExit("Manca face_landmarker.task. Esegui prima:  python scarica_modelli.py")

    percorsi = []
    for schema in args.video:
        percorsi += sorted(glob.glob(schema)) or [schema]

    emozioni = crea_modello_emozioni()
    for percorso in percorsi:
        elabora(percorso, max(1, args.ogni), emozioni)


if __name__ == "__main__":
    main()
