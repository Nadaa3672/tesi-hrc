"""Acquisizione della posa del corpo dalla webcam con MediaPipe.

Per ogni fotogramma trova i 33 punti del corpo (spalle, gomiti, polsi, ...)
e li salva in un file CSV, insieme al tempo trascorso dall'inizio.
Facoltativamente salva anche il video grezzo, per rielaborarlo in futuro
(per esempio per estrarre il viso).

Uso (dalla cartella del progetto):
    python src/acquisizione_pose.py --sessione mattina
    python src/acquisizione_pose.py --sessione sera --video

Durante la registrazione, nella finestra del video:
    SPAZIO = segna un evento (es. inizio barchetta, fine barchetta, fine aeroplano)
    Q      = ferma la registrazione
"""

import argparse
import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision

CARTELLA_PROGETTO = Path(__file__).resolve().parents[1]
MODELLO = CARTELLA_PROGETTO / "models" / "pose_landmarker_full.task"
CARTELLA_DATI = CARTELLA_PROGETTO / "data"

# Nomi dei 33 punti, nell'ordine di MediaPipe (0 = naso, 11 = spalla sinistra, ...)
NOMI_PUNTI = [p.name.lower() for p in vision.PoseLandmark]
CONNESSIONI = vision.PoseLandmarksConnections.POSE_LANDMARKS


def leggi_argomenti():
    parser = argparse.ArgumentParser(description="Registra la posa del corpo dalla webcam.")
    parser.add_argument("--sessione", required=True,
                        help="Nome della sessione, es. 'mattina' o 'sera'")
    parser.add_argument("--camera", type=int, default=0,
                        help="Indice della webcam (0 = quella predefinita)")
    parser.add_argument("--video", action="store_true",
                        help="Salva anche il video grezzo (.mp4)")
    parser.add_argument("--note", default="",
                        help="Note libere sulla sessione, es. 'dopo 8 ore di studio'")
    return parser.parse_args()


def intestazione_csv():
    colonne = ["frame", "t_s"]
    for nome in NOMI_PUNTI:
        colonne += [f"{nome}_x", f"{nome}_y", f"{nome}_z", f"{nome}_vis"]
    return colonne


def disegna_scheletro(immagine, punti):
    """Disegna linee e punti del corpo sull'immagine (in pixel)."""
    altezza, larghezza = immagine.shape[:2]
    pixel = [(int(p.x * larghezza), int(p.y * altezza)) for p in punti]
    for c in CONNESSIONI:
        if punti[c.start].visibility > 0.5 and punti[c.end].visibility > 0.5:
            cv2.line(immagine, pixel[c.start], pixel[c.end], (255, 255, 255), 2)
    for p, (x, y) in zip(punti, pixel):
        if p.visibility > 0.5:
            cv2.circle(immagine, (x, y), 4, (0, 200, 255), -1)


def main():
    args = leggi_argomenti()

    if not MODELLO.exists():
        raise SystemExit("Modello non trovato. Esegui prima:  python scarica_modelli.py")

    CARTELLA_DATI.mkdir(exist_ok=True)
    timbro = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = CARTELLA_DATI / f"{timbro}_{args.sessione}"

    # Su Windows CAP_DSHOW apre la webcam più velocemente
    backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
    webcam = cv2.VideoCapture(args.camera, backend)
    if not webcam.isOpened():
        raise SystemExit(f"Non riesco ad aprire la webcam {args.camera}. Prova con --camera 1")

    larghezza = int(webcam.get(cv2.CAP_PROP_FRAME_WIDTH))
    altezza = int(webcam.get(cv2.CAP_PROP_FRAME_HEIGHT))

    registratore = None
    if args.video:
        registratore = cv2.VideoWriter(str(base) + ".mp4",
                                       cv2.VideoWriter_fourcc(*"mp4v"), 30, (larghezza, altezza))

    opzioni = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODELLO)),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
    )

    frame = 0
    frame_con_persona = 0
    eventi = []  # tempi (in secondi) in cui hai premuto SPAZIO
    ultimo_ms = -1
    inizio = time.perf_counter()

    with vision.PoseLandmarker.create_from_options(opzioni) as rilevatore, \
            open(str(base) + "_pose.csv", "w", newline="") as file_csv:
        scrittore = csv.writer(file_csv)
        scrittore.writerow(intestazione_csv())

        print("Registrazione avviata. SPAZIO = segna un evento, Q = ferma.")
        while True:
            ok, immagine = webcam.read()
            if not ok:
                print("La webcam non restituisce immagini: interrompo.")
                break

            t_s = time.perf_counter() - inizio
            # MediaPipe vuole tempi in millisecondi sempre crescenti
            ms = max(int(t_s * 1000), ultimo_ms + 1)
            ultimo_ms = ms

            if registratore is not None:
                registratore.write(immagine)

            rgb = cv2.cvtColor(immagine, cv2.COLOR_BGR2RGB)
            risultato = rilevatore.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ms)

            if risultato.pose_landmarks:
                punti = risultato.pose_landmarks[0]
                riga = [frame, round(t_s, 4)]
                for p in punti:
                    riga += [round(p.x, 5), round(p.y, 5), round(p.z, 5), round(p.visibility, 3)]
                scrittore.writerow(riga)
                frame_con_persona += 1
                disegna_scheletro(immagine, punti)

            fps = frame / t_s if t_s > 0 else 0
            cv2.putText(immagine, f"REC {args.sessione}  {t_s:5.1f}s  {fps:4.1f} fps",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.putText(immagine, f"Eventi: {len(eventi)}   (SPAZIO = evento, Q = stop)",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.imshow("Acquisizione posa", immagine)
            frame += 1

            tasto = cv2.waitKey(1) & 0xFF
            if tasto == ord(" "):
                eventi.append(round(t_s, 3))
                print(f"Evento {len(eventi)} a {t_s:.1f} s")
            elif tasto in (ord("q"), ord("Q")):
                break

    durata = time.perf_counter() - inizio
    webcam.release()
    if registratore is not None:
        registratore.release()
    cv2.destroyAllWindows()

    with open(str(base) + "_eventi.csv", "w", newline="") as f:
        scrittore = csv.writer(f)
        scrittore.writerow(["evento", "t_s"])
        for numero, t in enumerate(eventi, start=1):
            scrittore.writerow([numero, t])

    # Informazioni sulla sessione, utili quando confronterai più registrazioni
    info = {
        "sessione": args.sessione,
        "note": args.note,
        "inizio": timbro,
        "durata_s": round(durata, 1),
        "frame_totali": frame,
        "frame_con_persona": frame_con_persona,
        "fps_medi": round(frame / durata, 1) if durata > 0 else 0,
        "risoluzione": [larghezza, altezza],
        "modello": MODELLO.name,
        "mediapipe": mp.__version__,
        "video_salvato": bool(args.video),
        "eventi": len(eventi),
    }
    with open(str(base) + "_info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)

    print(f"Fatto: {frame_con_persona}/{frame} fotogrammi con una persona, {durata:.1f} s.")
    print(f"File salvati in {CARTELLA_DATI} con prefisso {base.name}")


if __name__ == "__main__":
    main()
