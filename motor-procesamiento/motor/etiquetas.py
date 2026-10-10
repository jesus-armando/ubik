"""Etiquetas: borde naranja #FF6A00 -> recorte enderezado de 600 x 350 px -> posición.

1. Umbral HSV del naranja en una copia reducida, contornos externos y approxPolyDP.
2. Filtros con la homografía: tamaño esperado de 6 x 3.5 cm, centro hueco (el borde es
   un marco) y centro a la altura de la orilla de una repisa.
3. Se refinan las esquinas en la imagen completa y se endereza a 600 x 350.
4. La posición sale de la x del centro en cm (rango x_ini–x_fin del planograma).

Respaldo (corte H5): con `geometria=True`, si en un cuadro no se encontró por color la
etiqueta de una posición que debería verse completa, se recorta el rectángulo donde el
contrato dice que está.

    python -m motor.etiquetas video/cuadros/000001.png
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from motor import contrato, marcadores

# Naranja #FF6A00: H ≈ 12 en la escala 0–180 de OpenCV
H_MIN, H_MAX, S_MIN, V_MIN = 4, 22, 100, 100
ANCHO_BUSQUEDA = 1920


@dataclass
class EtiquetaDetectada:
    cuadro: int
    posicion: str
    esquinas: np.ndarray          # (4, 2) px en el cuadro: sup-izq, sup-der, inf-der, inf-izq
    esquinas_cm: np.ndarray       # (4, 2) cm
    imagen: np.ndarray            # 600 x 350 BGR
    metodo: str                   # "color" o "geometria"
    nitidez: float
    distancia_centro: float       # 0 = al centro del cuadro, 1 = en la orilla


def mascara_naranja(imagen: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (H_MIN, S_MIN, V_MIN), (H_MAX, 255, 255))


def ordenar_esquinas(pts: np.ndarray) -> np.ndarray:
    pts = np.asarray(pts, np.float64).reshape(4, 2)
    s, d = pts.sum(axis=1), pts[:, 1] - pts[:, 0]
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]])


def cuadrilatero(contorno: np.ndarray) -> np.ndarray:
    peri = cv2.arcLength(contorno, True)
    for eps in (0.02, 0.03, 0.045):
        aprox = cv2.approxPolyDP(contorno, eps * peri, True)
        if len(aprox) == 4 and cv2.isContourConvex(aprox):
            return ordenar_esquinas(aprox.reshape(4, 2))
    return ordenar_esquinas(cv2.boxPoints(cv2.minAreaRect(contorno)))


def enderezar(imagen: np.ndarray, esquinas: np.ndarray) -> np.ndarray:
    W, H = contrato.ETIQUETA_ANCHO_PX, contrato.ETIQUETA_ALTO_PX
    dst = np.float32([[0, 0], [W, 0], [W, H], [0, H]]) - 0.5
    M = cv2.getPerspectiveTransform(np.float32(esquinas) - 0.5, dst)
    return cv2.warpPerspective(imagen, M, (W, H), flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE)


def refinar(imagen: np.ndarray, esquinas: np.ndarray) -> np.ndarray:
    """Recalcula las esquinas con la máscara a resolución completa alrededor del candidato."""
    Himg, Wimg = imagen.shape[:2]
    x1, y1 = np.floor(esquinas.min(axis=0)).astype(int) - 8
    x2, y2 = np.ceil(esquinas.max(axis=0)).astype(int) + 8
    x1, y1, x2, y2 = max(x1, 0), max(y1, 0), min(x2, Wimg), min(y2, Himg)
    roi = imagen[y1:y2, x1:x2]
    m = mascara_naranja(roi)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cs:
        return esquinas
    c = max(cs, key=cv2.contourArea)
    if cv2.contourArea(c) < 0.6 * cv2.contourArea(esquinas.astype(np.float32)):
        return esquinas
    return cuadrilatero(c) + [x1, y1]


def detectar_etiquetas(imagen: np.ndarray, homografia: marcadores.Homografia | None,
                       planograma: list[contrato.Posicion], indice: int = 0,
                       nitidez: float = 0.0, geometria: bool = False) -> list[EtiquetaDetectada]:
    if homografia is None:
        return []
    Himg, Wimg = imagen.shape[:2]
    f = min(1.0, ANCHO_BUSQUEDA / Wimg)
    peq = cv2.resize(imagen, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f < 1 else imagen
    m = mascara_naranja(peq)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contornos, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    en_seccion = [p for p in planograma if p.seccion == homografia.seccion]

    encontradas: dict[str, EtiquetaDetectada] = {}
    for c in contornos:
        area = cv2.contourArea(c) / (f * f)
        if area < 200:
            continue
        x, y, w, h = cv2.boundingRect(c)
        if x <= 1 or y <= 1 or x + w >= peq.shape[1] - 1 or y + h >= peq.shape[0] - 1:
            continue  # cortada por la orilla del cuadro
        esquinas = cuadrilatero(c) / f
        centro = esquinas.mean(axis=0)
        cx_cm, cy_cm = homografia.a_cm([centro])[0]
        esperado = homografia.px_por_cm(cx_cm, cy_cm) ** 2 * (
            contrato.ETIQUETA_ANCHO_CM * contrato.ETIQUETA_ALTO_CM)
        if not (0.45 * esperado < area < 1.7 * esperado):
            continue
        relleno = cv2.countNonZero(m[y:y + h, x:x + w]) / max(1.0, cv2.contourArea(c))
        if relleno > 0.75:
            continue  # mancha naranja sólida: no es el marco de una etiqueta
        esquinas_cm = homografia.a_cm(esquinas)
        ancho_cm = np.linalg.norm(esquinas_cm[1] - esquinas_cm[0])
        alto_cm = np.linalg.norm(esquinas_cm[3] - esquinas_cm[0])
        if not (0.7 < ancho_cm / contrato.ETIQUETA_ANCHO_CM < 1.4
                and 0.7 < alto_cm / contrato.ETIQUETA_ALTO_CM < 1.4):
            continue
        pos = contrato.posicion_de_etiqueta(en_seccion, cx_cm, cy_cm)
        if pos is None:
            continue
        if f < 1:
            esquinas = refinar(imagen, esquinas)
        dc = float(np.linalg.norm((centro - [Wimg / 2, Himg / 2]) / [Wimg / 2, Himg / 2]))
        det = EtiquetaDetectada(indice, pos.posicion, esquinas, homografia.a_cm(esquinas),
                                enderezar(imagen, esquinas), "color", nitidez, dc)
        previa = encontradas.get(pos.posicion)
        if previa is None or dc < previa.distancia_centro:
            encontradas[pos.posicion] = det

    if geometria:
        for pos in en_seccion:
            if pos.posicion in encontradas:
                continue
            esquinas = homografia.rect_a_px(pos.rect_etiqueta_cm())
            margen = 4
            if (esquinas.min(axis=0) < margen).any() or (esquinas[:, 0].max() > Wimg - margen) \
                    or (esquinas[:, 1].max() > Himg - margen):
                continue
            centro = esquinas.mean(axis=0)
            dc = float(np.linalg.norm((centro - [Wimg / 2, Himg / 2]) / [Wimg / 2, Himg / 2]))
            encontradas[pos.posicion] = EtiquetaDetectada(
                indice, pos.posicion, esquinas, homografia.a_cm(esquinas),
                enderezar(imagen, esquinas), "geometria", nitidez, dc)
    return list(encontradas.values())


def etiqueta_completa_en_cuadro(pos: contrato.Posicion, homografia: marcadores.Homografia,
                                ancho: int, alto: int, margen: int = 4) -> bool:
    """¿La etiqueta de esta posición cabe completa en el cuadro? (oportunidad de verla)."""
    if homografia is None or pos.seccion != homografia.seccion:
        return False
    e = homografia.rect_a_px(pos.rect_etiqueta_cm())
    return bool((e.min(axis=0) >= margen).all() and e[:, 0].max() <= ancho - margen
                and e[:, 1].max() <= alto - margen)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Encuentra y endereza las etiquetas de un cuadro")
    ap.add_argument("imagen", nargs="?", default="video/cuadros/000001.png")
    ap.add_argument("--planograma", default="datos/sistema/planograma.csv")
    ap.add_argument("--debug", default="debug")
    ap.add_argument("--geometria", action="store_true")
    args = ap.parse_args(argv)
    img = cv2.imread(args.imagen)
    plan = contrato.leer_planograma(args.planograma)
    h = marcadores.calcular_homografia(img, contrato.alturas_por_repisa(plan))
    dets = detectar_etiquetas(img, h, plan, geometria=args.geometria)
    out = Path(args.debug)
    out.mkdir(parents=True, exist_ok=True)
    vista = img.copy()
    for d in dets:
        cv2.polylines(vista, [d.esquinas.astype(np.int32)], True, (0, 255, 0), 3)
        cv2.putText(vista, d.posicion, tuple(d.esquinas[0].astype(int) + [0, -8]),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
        cv2.imwrite(str(out / f"etiqueta_{d.posicion}.png"), d.imagen)
    cv2.imwrite(str(out / f"etiquetas_{Path(args.imagen).stem}.png"), vista)
    print(f"{len(dets)} etiquetas: {sorted((d.posicion, d.metodo) for d in dets)} -> {out}/")


if __name__ == "__main__":
    main()
