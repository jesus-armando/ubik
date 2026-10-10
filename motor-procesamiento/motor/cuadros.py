"""Selección de cuadros: el más nítido de cada ventana de N cuadros.

La nitidez es la varianza del Laplaciano, medida sobre una copia reducida en gris (es
mucho más barato y ordena los cuadros igual).

    python -m motor.cuadros video/recorrido_realista.mp4
"""
from __future__ import annotations

import argparse
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Iterator

import cv2
import numpy as np

ANCHO_NITIDEZ = 960


@dataclass
class Cuadro:
    indice: int                 # índice en el mp4, empieza en 0
    imagen: np.ndarray          # BGR a resolución completa
    nitidez: float
    homografia: object | None = field(default=None, repr=False)  # marcadores.Homografia


@dataclass
class InfoVideo:
    fps: float
    cuadros: int
    ancho: int
    alto: int


def info_video(ruta: str) -> InfoVideo:
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise FileNotFoundError(f"no se pudo abrir el video: {ruta}")
    info = InfoVideo(cap.get(cv2.CAP_PROP_FPS) or 30.0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                     int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    cap.release()
    return info


def nitidez(imagen: np.ndarray) -> float:
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY) if imagen.ndim == 3 else imagen
    if gris.shape[1] > ANCHO_NITIDEZ:
        f = ANCHO_NITIDEZ / gris.shape[1]
        gris = cv2.resize(gris, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(gris, cv2.CV_32F).var())


def elegir_cuadros(ruta: str, cada: int = 12) -> Iterator[Cuadro]:
    """Recorre el video y entrega el cuadro más nítido de cada ventana de `cada` cuadros."""
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise FileNotFoundError(f"no se pudo abrir el video: {ruta}")
    mejor: Cuadro | None = None
    indice = 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        n = nitidez(img)
        if mejor is None or n > mejor.nitidez:
            mejor = Cuadro(indice, img, n)
        indice += 1
        if indice % cada == 0:
            yield mejor
            mejor = None
    if mejor is not None:
        yield mejor
    cap.release()


def elegir_cuadros_en_hilo(ruta: str, cada: int = 12, maximo_en_cola: int = 4) -> Iterator[Cuadro]:
    """Igual que elegir_cuadros, pero decodifica en otro hilo mientras se procesa."""
    cola: queue.Queue = queue.Queue(maxsize=maximo_en_cola)
    fin = object()
    error: list[BaseException] = []

    def productor():
        try:
            for c in elegir_cuadros(ruta, cada):
                cola.put(c)
        except BaseException as e:  # se vuelve a lanzar en el hilo principal
            error.append(e)
        finally:
            cola.put(fin)

    hilo = threading.Thread(target=productor, daemon=True)
    hilo.start()
    while True:
        c = cola.get()
        if c is fin:
            break
        yield c
    hilo.join()
    if error:
        raise error[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Elige el cuadro más nítido de cada ventana")
    ap.add_argument("video")
    ap.add_argument("--cada", type=int, default=12)
    args = ap.parse_args(argv)
    info = info_video(args.video)
    t0 = time.time()
    elegidos = [(c.indice, round(c.nitidez, 1)) for c in elegir_cuadros(args.video, args.cada)]
    print(f"{info.cuadros} cuadros {info.ancho}x{info.alto} a {info.fps:g} fps -> "
          f"{len(elegidos)} elegidos en {time.time() - t0:.1f} s")
    print(elegidos[:20], "..." if len(elegidos) > 20 else "")


if __name__ == "__main__":
    main()
