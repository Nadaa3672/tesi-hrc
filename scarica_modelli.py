"""Scarica i modelli di MediaPipe nella cartella models/.

Uso:  python scarica_modelli.py
"""
from pathlib import Path
from urllib.request import urlretrieve

MODELLI = {
    "pose_landmarker_full.task": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
    "hand_landmarker.task": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task",
}

cartella = Path(__file__).resolve().parent / "models"
cartella.mkdir(exist_ok=True)

for nome, url in MODELLI.items():
    destinazione = cartella / nome
    if destinazione.exists():
        print(f"Già presente: {destinazione}")
        continue
    print(f"Scarico {nome} ...")
    urlretrieve(url, destinazione)
    print(f"Salvato in {destinazione} ({destinazione.stat().st_size / 1e6:.1f} MB)")
