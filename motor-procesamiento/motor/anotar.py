"""Video anotado y recortes.

El video anotado conserva todos los cuadros y los fps de la entrada (el tablero salta a
segundo = cuadro ÷ fps). Solo los cuadros elegidos tienen homografía; para los demás se
interpola entre los dos elegidos vecinos (la cámara se mueve a velocidad constante), y
con ella se proyectan las cajas de cada posición, guardadas en cm.

Colores: verde = producto, rojo = hueco, naranja = etiqueta.
"""
from __future__ import annotations

import bisect
import subprocess
from dataclasses import dataclass, field

import cv2
import numpy as np

from motor import contrato

VERDE, ROJO, NARANJA, BLANCO = (60, 200, 60), (40, 40, 230), (0, 106, 255), (255, 255, 255)


@dataclass
class AnotacionPosicion:
    posicion: contrato.Posicion
    etiqueta_cm: np.ndarray | None = None      # (4, 2) esquinas de la etiqueta en cm
    texto_etiqueta: str = ""
    productos_cm: list = field(default_factory=list)  # [(x1, y1, x2, y2)] en cm
    hueco: bool = False
    frentes: int | None = None


def recortar_cm(imagen: np.ndarray, cm_a_px: np.ndarray, rect_cm, px_por_cm: float = 15.0
                ) -> np.ndarray:
    """Recorte enderezado de un rectángulo del plano del anaquel (x1, y1, x2, y2 en cm)."""
    x1, y1, x2, y2 = rect_cm
    W, H = int(round((x2 - x1) * px_por_cm)), int(round((y2 - y1) * px_por_cm))
    # píxel de salida (u, v) -> cm (x1 + u/s, y2 - v/s) -> píxel de entrada
    T = np.array([[1 / px_por_cm, 0, x1], [0, -1 / px_por_cm, y2], [0, 0, 1]])
    M = cm_a_px @ T
    return cv2.warpPerspective(imagen, M, (W, H), flags=cv2.INTER_AREA | cv2.WARP_INVERSE_MAP,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=(40, 40, 40))


class Interpolador:
    """Homografía cm -> px para cualquier cuadro, a partir de los cuadros elegidos."""

    def __init__(self, homografias: dict[int, np.ndarray], max_hueco: int = 40):
        self.indices = sorted(homografias)
        self.H = {i: homografias[i] / homografias[i][2, 2] for i in self.indices}
        self.max_hueco = max_hueco

    def __call__(self, i: int) -> np.ndarray | None:
        if not self.indices:
            return None
        k = bisect.bisect_left(self.indices, i)
        if k < len(self.indices) and self.indices[k] == i:
            return self.H[i]
        antes = self.indices[k - 1] if k > 0 else None
        despues = self.indices[k] if k < len(self.indices) else None
        if antes is not None and despues is not None and despues - antes <= self.max_hueco:
            t = (i - antes) / (despues - antes)
            return (1 - t) * self.H[antes] + t * self.H[despues]
        cercano = min((j for j in (antes, despues) if j is not None), key=lambda j: abs(j - i))
        return self.H[cercano] if abs(cercano - i) <= self.max_hueco // 2 else None


def _poly(img, H, pts_cm, color, grosor):
    p = cv2.perspectiveTransform(np.asarray(pts_cm, np.float64).reshape(-1, 1, 2), H)
    p = p.reshape(-1, 2)
    if not np.isfinite(p).all() or np.abs(p).max() > 1e5:
        return None
    cv2.polylines(img, [np.round(p).astype(np.int32)], True, color, grosor, cv2.LINE_AA)
    return p


def _texto(img, texto, org, color, escala):
    x, y = int(org[0]), int(org[1])
    (w, h), base = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, escala, 2)
    if not (0 <= x < img.shape[1] and h + 4 <= y < img.shape[0]):
        return  # el ancla quedó fuera del cuadro
    cv2.rectangle(img, (x - 2, y - h - 6), (x + w + 4, y + base), (25, 25, 25), -1)
    cv2.putText(img, texto, (x + 1, y - 2), cv2.FONT_HERSHEY_SIMPLEX, escala, color, 2,
                cv2.LINE_AA)


def rect_cm(x1, y1, x2, y2):
    return [[x1, y2], [x2, y2], [x2, y1], [x1, y1]]


def fraccion_en_cuadro(H: np.ndarray, rect, ancho: int, alto: int) -> float:
    p = cv2.perspectiveTransform(np.asarray(rect_cm(*rect), np.float64).reshape(-1, 1, 2), H)
    x1, y1 = p.reshape(-1, 2).min(axis=0)
    x2, y2 = p.reshape(-1, 2).max(axis=0)
    area = max(1e-6, (x2 - x1) * (y2 - y1))
    return max(0.0, min(x2, ancho) - max(x1, 0)) * max(0.0, min(y2, alto) - max(y1, 0)) / area


def dibujar(img: np.ndarray, H: np.ndarray, anotaciones: list[AnotacionPosicion]):
    # 6 px a 1920 de ancho: el tablero muestra el video a ~760 px y más delgadas casi no se ven
    g = max(3, img.shape[1] // 320)
    escala = img.shape[1] / 2400
    for a in anotaciones:
        p = a.posicion
        if fraccion_en_cuadro(H, p.rect_recorte_cm(), img.shape[1], img.shape[0]) < 0.35:
            continue  # posición casi fuera del cuadro: no se anota
        if a.hueco:
            x1, y1, x2, y2 = p.rect_producto_cm()
            q = _poly(img, H, rect_cm(x1 + 0.5, y1 + 0.5, x2 - 0.5, y1 + 25), ROJO, g + 1)
            if q is not None:
                _texto(img, f"{p.posicion} HUECO", q[0] + [4, 28 * escala * 1.4], ROJO, escala)
        else:
            for c in a.productos_cm:
                _poly(img, H, rect_cm(*c), VERDE, g)
            if a.frentes is not None:
                q = H @ np.array([p.x_ini_cm + 1, p.altura_cm + 33, 1.0])
                if abs(q[2]) > 1e-9:
                    color = VERDE if a.frentes >= p.frentes_esperados else ROJO
                    _texto(img, f"{p.posicion} {a.frentes}/{p.frentes_esperados} frentes",
                           q[:2] / q[2], color, escala)
        if a.etiqueta_cm is not None:
            q = _poly(img, H, a.etiqueta_cm, NARANJA, g + 1)
            if q is not None and a.texto_etiqueta:
                _texto(img, a.texto_etiqueta, q[3] + [0, 34 * escala * 1.4], NARANJA, escala)
        else:
            q = _poly(img, H, rect_cm(*p.rect_etiqueta_cm()), ROJO, g)
            if q is not None:
                _texto(img, "sin etiqueta", q[3] + [0, 34 * escala * 1.4], ROJO, escala)


def escribir_video(entrada: str, salida: str, ancho_entrada: int, alto_entrada: int,
                   fps: float, homografias: dict[int, np.ndarray],
                   anotaciones: list[AnotacionPosicion], ancho: int = 1920) -> int:
    """Lee el video con ffmpeg (ya reducido), dibuja y escribe H.264. Devuelve cuadros."""
    ancho = min(ancho, ancho_entrada)
    alto = int(round(alto_entrada * ancho / ancho_entrada / 2)) * 2
    s = np.diag([ancho / ancho_entrada, alto / alto_entrada, 1.0])
    interp = Interpolador({i: s @ H for i, H in homografias.items()})
    lector = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-i", entrada, "-vf", f"scale={ancho}:{alto}",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    escritor = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{ancho}x{alto}", "-r", f"{fps}", "-i", "-", "-c:v", "libx264",
         "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags",
         "+faststart", salida], stdin=subprocess.PIPE)
    n = 0
    tam = ancho * alto * 3
    try:
        while True:
            buf = lector.stdout.read(tam)
            if len(buf) < tam:
                break
            img = np.frombuffer(buf, np.uint8).reshape(alto, ancho, 3).copy()
            H = interp(n)
            if H is not None:
                dibujar(img, H, anotaciones)
            escritor.stdin.write(img.tobytes())
            n += 1
    finally:
        lector.stdout.close()
        lector.wait()
        escritor.stdin.close()
        escritor.wait()
    return n
