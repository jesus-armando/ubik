"""Versión "realista" del video (P1, paso 4).

Ruido gaussiano leve, desenfoque horizontal de 2–3 px, variación de brillo de ±5 % entre
cuadros, viñeteado suave y compresión H.264 con CRF 26. No cambia el número ni el orden
de los cuadros, así que la verdad por cuadro sigue valiendo.

    python -m simulador.realismo video/recorrido.mp4 video/recorrido_realista.mp4
"""
from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np


def vineta(ancho, alto, fuerza=0.18) -> np.ndarray:
    y, x = np.ogrid[:alto, :ancho]
    r = np.sqrt(((x - ancho / 2) / (ancho / 2)) ** 2 + ((y - alto / 2) / (alto / 2)) ** 2) / np.sqrt(2)
    return (1 - fuerza * r ** 2).astype(np.float32)[..., None]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("entrada")
    ap.add_argument("salida")
    ap.add_argument("--crf", type=int, default=26)
    ap.add_argument("--ruido", type=float, default=3.0, help="sigma del ruido gaussiano")
    ap.add_argument("--semilla", type=int, default=7)
    args = ap.parse_args(argv)

    cap = cv2.VideoCapture(args.entrada)
    fps = cap.get(cv2.CAP_PROP_FPS)
    ancho = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    rng = np.random.default_rng(args.semilla)
    vin = vineta(ancho, alto)
    escala = ancho / 3840  # el desenfoque de 2-3 px es para 4K
    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{ancho}x{alto}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset",
         "fast", "-crf", str(args.crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         args.salida], stdin=subprocess.PIPE)
    brillo = 1.0
    t0, n = time.time(), 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        largo = max(1.0, rng.uniform(2.0, 3.0) * escala)
        k = int(np.ceil(largo)) | 1
        nucleo = np.zeros((1, k), np.float32)
        nucleo[0, :] = 1.0 / k
        img = cv2.filter2D(img, -1, nucleo)
        brillo = float(np.clip(brillo + rng.normal(0, 0.02), 0.95, 1.05))
        f = img.astype(np.float32) * vin * brillo
        f += rng.normal(0, args.ruido, (alto, ancho, 1)).astype(np.float32)
        ff.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
        n += 1
    ff.stdin.close()
    ff.wait()
    print(f"{args.salida}: {n} cuadros en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
