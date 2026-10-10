"""Modo sin estructura: videos sin marcadores, sin etiquetas del contrato y sin planograma
(p. ej., generados con IA o grabados con el celular en cualquier tienda).

    python -m motor.libre --video ../videos_ia/clip.mp4 --salida salida_libre/

Sin marcadores no hay centímetros ni posiciones del planograma, así que la unidad es la
etiqueta de precio que se ve en el video:

1. Movimiento y productos (unos 8 cuadros por segundo): YOLO con SKU-110K (detector general
   de productos) y el movimiento de la cámara contra el cuadro anterior (ORB + homografía).
2. Etiquetas (unas 2 veces por segundo, el cuadro más nítido de cada ventana): OCR del
   cuadro completo a 1920 px. Un texto con forma de precio sobre papel claro es una
   etiqueta; se recorta, se amplía y se vuelve a leer para sacar el precio (con los
   centavos en superíndice) y el nombre del producto.
3. Seguimiento: cada etiqueta se arrastra de un cuadro a otro con el movimiento de la cámara;
   cada pista es una etiqueta física, la "posición" de este modo. Precio, nombre y hueco se
   votan entre los cuadros donde se leyó.
4. Hueco: encima de la etiqueta no hay productos (YOLO) y la zona se ve lisa.

Si la etiqueta trae el SKU impreso ("SKU-100664") también se lee, y se guardan las palabras
impresas encima de ella (el nombre en el empaque). Con --planograma (un anaquel conocido grabado
sin marcadores) cada etiqueta se acomoda en su posición por el orden del recorrido y su SKU
(motor/orden.py): el video rotula las etiquetas con su posición y no dibuja las que no caben;
cruce/orden.py hace el cruce. Las cajas de SKU-110K que caen sobre una etiqueta se descartan:
ese detector a veces toma una etiqueta de papel por producto.

Salida en --salida: observaciones_libre.json, recortes/, recorrido_anotado.mp4 y
diagnostico.json. El cruce (cruce/libre.py) lo convierte en hallazgos para el tablero.
"""
from __future__ import annotations

import argparse
import bisect
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

import cv2
import numpy as np

from motor import cuadros
from motor.anotar import BLANCO, NARANJA, ROJO, VERDE, _texto
from motor.pipeline import Progreso, Tiempos, _dispositivo

log = logging.getLogger("motor.libre")

MODELO_DEFECTO = "modelos/sku110k.pt"
ANCHO_OCR = 1920        # el cuadro se lleva a este ancho para buscar etiquetas
ANCHO_RECORTE = 480     # la etiqueta recortada se lee a este ancho
PRECIO_MIN, PRECIO_MAX = 0.5, 9999.0

# ------------------------------------------------------------------ lectura de etiquetas
# Precio completo: "$32.90", "s33-90", "S14.90", "32,90"
RE_PRECIO_COMPLETO = re.compile(r"^[$sS]?\s*(\d{1,4})\s*[.,\-:·]\s*(\d{2})$")
# Parte entera grande (los centavos van aparte, en superíndice): "$33", "s32", "33"
RE_ENTERO = re.compile(r"^[$sS]?\s*(\d{1,4})[.,]?$")
RE_CENTAVOS = re.compile(r"^[.,]?(\d{2})$")
# Todo junto sin separador: "$3290", "3390"
RE_PEGADO = re.compile(r"^[$sS]?(\d{3,4})$")
PALABRAS_RUIDO = {"PRECIO", "POR", "SKU", "PRICE", "READ", "UNIDAD", "UNIT", "IVA", "OFERTA"}
# SKU impreso en la etiqueta: "SKU-100664"; el OCR a veces lee "SKL-100131", "U-100599" o solo
# "-100131". Un código de barras (muchos dígitos, sin guion) no cuenta.
RE_SKU = re.compile(r"(?:SK[UL]-?|-)([0-9O]{6})(?![0-9])")


def _limpiar(t: str) -> str:
    """Quita espacios y cambia O por 0 en textos que son puros números."""
    t = t.strip()
    if re.fullmatch(r"[$sS]?[\dOo\s.,\-:·]+", t):
        return t.replace(" ", "").replace("O", "0").replace("o", "0")
    return t


def leer_precio(lineas: list[tuple[str, float, tuple]]) -> tuple[float | None, float]:
    """Precio de una etiqueta a partir de sus renglones [(texto, confianza, caja)].

    El precio es el número más grande de la etiqueta; los centavos pueden venir en su propia
    caja, más chica y arriba a la derecha.
    """
    candidatos = []  # (alto, precio, confianza)
    for i, (t, c, (x1, y1, x2, y2)) in enumerate(lineas):
        t = _limpiar(t)
        h = y2 - y1
        m = RE_PRECIO_COMPLETO.match(t)
        if m:
            candidatos.append((h, int(m.group(1)) + int(m.group(2)) / 100, c))
            continue
        m = RE_ENTERO.match(t)
        if not m:
            continue
        # centavos en superíndice: a la derecha, pegados y en la mitad de arriba
        for j, (tj, cj, (a1, b1, a2, b2)) in enumerate(lineas):
            mj = RE_CENTAVOS.match(_limpiar(tj))
            if j == i or not mj or b2 - b1 > 0.9 * h:
                continue
            if -0.4 * h <= a1 - x2 <= 0.8 * h and b1 < y1 + 0.5 * h:
                candidatos.append((h, int(m.group(1)) + int(mj.group(1)) / 100, min(c, cj)))
                break
        else:
            m2 = RE_PEGADO.match(t)
            if m2:  # "3390": se perdió el punto; con 3 dígitos ("183") es aún más dudoso
                d = m2.group(1)
                candidatos.append((h, int(d[:-2]) + int(d[-2:]) / 100,
                                   (0.85 if len(d) == 4 else 0.6) * c))
    candidatos = [k for k in candidatos if PRECIO_MIN <= k[1] <= PRECIO_MAX]
    if not candidatos:
        return None, 0.0
    _, precio, c = max(candidatos, key=lambda k: k[0])
    return round(precio, 2), float(c)


def leer_nombre(lineas: list[tuple[str, float, tuple]], alto_imagen: float) -> str:
    """Nombre del producto: los renglones con letras de la parte de arriba de la etiqueta."""
    partes = []
    for t, c, (x1, y1, x2, y2) in sorted(lineas, key=lambda k: (k[2][1], k[2][0])):
        if (y1 + y2) / 2 > 0.45 * alto_imagen or c < 0.5:
            continue
        palabras = [p for p in re.sub(r"[^A-ZÁÉÍÓÚÑ0-9 ]", " ", t.upper()).split()
                    if p not in PALABRAS_RUIDO]
        if sum(ch.isalpha() for ch in "".join(palabras)) >= 3:
            partes.extend(palabras)
    return " ".join(partes)[:60]


def leer_sku(lineas: list[tuple[str, float, tuple]]) -> str | None:
    """SKU impreso en la etiqueta ("SKU-100664"), o None si no se leyó."""
    for t, _, _ in lineas:
        m = RE_SKU.search(t.upper().replace(" ", ""))
        if m:
            return "SKU-" + m.group(1).replace("O", "0")
    return None


def palabras(texto: str) -> set[str]:
    """Palabras de 3 letras o más, en mayúsculas (para comparar con nombres de productos)."""
    return set(re.findall(r"[A-ZÁÉÍÓÚÑ]{3,}", texto.upper()))


def parece_precio(texto: str) -> bool:
    """¿Este texto del cuadro completo puede ser (parte de) el precio de una etiqueta?"""
    t = _limpiar(texto)
    return bool(RE_PRECIO_COMPLETO.match(t) or RE_PEGADO.match(t)
                or re.fullmatch(r"[$sS]\s*\d{1,4}[.,]?", t) or re.fullmatch(r"\d{1,3}", t))


def parecido(a: str, b: str) -> float:
    """Parecido entre dos nombres leídos (tolera letras mal leídas y palabras en otro orden)."""
    if not a or not b:
        return 0.0
    ordenar = lambda s: " ".join(sorted(s.split()))
    return max(SequenceMatcher(None, a, b).ratio(),
               SequenceMatcher(None, ordenar(a), ordenar(b)).ratio())


def mascara_clara(img: np.ndarray) -> np.ndarray:
    """Píxeles de papel de etiqueta: claros y poco saturados (blanco o amarillo pálido)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return ((hsv[..., 1] < 80) & (hsv[..., 2] > 140)).astype(np.uint8)


# Proporciones de una etiqueta de anaquel respecto al alto de los dígitos del precio,
# medidas en los videos: ~4.2 × 2.3, con el precio un poco a la derecha del centro.
ETIQUETA_ANCHO_H, ETIQUETA_ALTO_H = 4.2, 2.3


def rect_etiqueta(img: np.ndarray, caja_precio, clara: np.ndarray | None = None):
    """Rectángulo de la etiqueta a partir de la caja del precio, o None si alrededor del
    precio no hay papel claro (un número impreso en un empaque no es etiqueta)."""
    alto, ancho = img.shape[:2]
    x1, y1, x2, y2 = caja_precio
    w, h = x2 - x1, y2 - y1
    clara = mascara_clara(img) if clara is None else clara
    anillo = clara[int(max(0, y1 - 0.3 * h)):int(min(alto, y2 + 0.3 * h)),
                   int(max(0, x1 - 0.3 * w)):int(min(ancho, x2 + 0.3 * w))]
    if anillo.size == 0 or anillo.mean() < 0.35:
        return None
    W, H = ETIQUETA_ANCHO_H * h, ETIQUETA_ALTO_H * h
    cx = (x1 + x2) / 2 - 0.15 * W
    top = y1 - 0.5 * h
    return (max(0.0, cx - W / 2), max(0.0, top), min(float(ancho), cx + W / 2),
            min(float(alto), top + H))


def _area(r) -> float:
    return max(0.0, r[2] - r[0]) * max(0.0, r[3] - r[1])


def _interseccion(a, b) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def traslape(a, b) -> float:
    """Intersección sobre el área del más chico."""
    return _interseccion(a, b) / max(1e-6, min(_area(a), _area(b)))


def iou(a, b) -> float:
    i = _interseccion(a, b)
    return i / max(1e-6, _area(a) + _area(b) - i)


def _centro_en(caja, rect) -> bool:
    cx, cy = (caja[0] + caja[2]) / 2, (caja[1] + caja[3]) / 2
    return rect[0] <= cx <= rect[2] and rect[1] <= cy <= rect[3]


def sin_etiquetas(cajas, etiquetas):
    """Las cajas de producto que no son una etiqueta: SKU-110K a veces marca una etiqueta de
    papel como producto (más con etiquetas grandes, como las de un anaquel armado a mano)."""
    def es_etiqueta(c, e):
        mx, my = 0.1 * (e[2] - e[0]), 0.1 * (e[3] - e[1])
        return (_centro_en(c, (e[0] - mx, e[1] - my, e[2] + mx, e[3] + my))
                or _interseccion(c, e) >= 0.4 * _area(c))
    return [c for c in cajas if not any(es_etiqueta(c, e) for e in etiquetas)]


def _cerca(a, b, d: float) -> bool:
    return not (a[2] < b[0] - d or b[2] < a[0] - d or a[3] < b[1] - d or b[3] < a[1] - d)


def candidatos(lineas, img: np.ndarray, clara: np.ndarray):
    """Etiquetas de un cuadro: [(alto_digitos, rect, precio, confianza)], una por lugar."""
    cands = []
    for t, c, caja in lineas:
        if not parece_precio(t):
            continue
        h = caja[3] - caja[1]
        precio, conf = leer_precio([l for l in lineas if _cerca(l[2], caja, 0.5 * h)])
        if precio is None and not re.match(r"^[$sS]\s*\d", _limpiar(t)):
            continue  # un número suelto sin centavos ni signo de pesos no es precio
        rect = rect_etiqueta(img, caja, clara)
        if rect is not None:
            cands.append((h, rect, precio, conf))
    # gana el precio de dígitos más grandes: el precio por kilo de la misma etiqueta es chico
    elegidas = []
    for k in sorted(cands, key=lambda k: -k[0]):
        if all(traslape(k[1], e[1]) <= 0.3 for e in elegidas):
            elegidas.append(k)
    return elegidas


def recortar(img: np.ndarray, rect, margen: float = 0.06, ancho_salida: int | None = None):
    alto, ancho = img.shape[:2]
    x1, y1, x2, y2 = rect
    mx, my = margen * (x2 - x1), margen * (y2 - y1)
    a = img[int(max(0, y1 - my)):int(min(alto, y2 + my)),
            int(max(0, x1 - mx)):int(min(ancho, x2 + mx))]
    if a.size and ancho_salida:
        f = ancho_salida / a.shape[1]
        a = cv2.resize(a, None, fx=f, fy=f,
                       interpolation=cv2.INTER_CUBIC if f > 1 else cv2.INTER_AREA)
    return a


# ------------------------------------------------------------------ huecos
COBERTURA_HUECO = 0.25  # menos de esto tapado por productos
TEXTURA_HUECO = 0.045   # y menos de esto de bordes: fondo de anaquel liso
DENTRO_HUECO = 0.6      # la zona debe verse al menos así de completa
ANCHO_HUECO = 0.05      # etiquetas más angostas (× ancho del cuadro) están lejos para juzgar


def zona_producto(rect, ancho: int, alto: int):
    """Zona donde debería estar el producto de la etiqueta: encima de ella, de su ancho."""
    x1, y1, x2, y2 = rect
    w = x2 - x1
    cx = (x1 + x2) / 2
    z = (cx - 0.6 * w, y1 - 1.3 * w, cx + 0.6 * w, y1 - 0.08 * (y2 - y1))
    recortada = (max(0.0, z[0]), max(0.0, z[1]), min(float(ancho), z[2]), min(float(alto), z[3]))
    return recortada, _area(recortada) / max(1.0, _area(z))


def recorte_evidencia(img: np.ndarray, rect, hueco: bool | None, ancho_salida: int = 640):
    """Recorte apaisado alrededor de la etiqueta con su caja (naranja) y, si es hueco, la
    zona vacía de encima (roja): la foto que ve el gerente en la tarjeta del hallazgo."""
    alto, ancho = img.shape[:2]
    x1, y1, x2, y2 = rect
    w = x2 - x1
    zona, _ = zona_producto(rect, ancho, alto)
    vista = img.copy()
    grosor = max(2, round(ancho / 640))
    if hueco:
        cv2.rectangle(vista, (int(zona[0]), int(zona[1])), (int(zona[2]), int(zona[3])),
                      (40, 40, 230), grosor)
    cv2.rectangle(vista, (int(x1), int(y1)), (int(x2), int(y2)), (0, 106, 255), grosor)
    cx = (x1 + x2) / 2
    return recortar(vista, (cx - 1.6 * w, zona[1] - 0.1 * w, cx + 1.6 * w,
                            y2 + 0.3 * (y2 - y1)), 0.0, ancho_salida)


def cobertura(zona, cajas) -> float:
    """Fracción de la zona tapada por cajas de producto."""
    x1, y1, x2, y2 = (int(round(v)) for v in zona)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    m = np.zeros((y2 - y1, x2 - x1), np.uint8)
    for a1, b1, a2, b2 in cajas:
        a1, b1 = int(max(a1, x1)) - x1, int(max(b1, y1)) - y1
        a2, b2 = int(min(a2, x2)) - x1, int(min(b2, y2)) - y1
        if a2 > a1 and b2 > b1:
            m[b1:b2, a1:a2] = 1
    return float(m.mean())


def textura(img: np.ndarray, zona) -> float:
    """Densidad de bordes de la zona (un fondo de anaquel vacío es liso)."""
    x1, y1, x2, y2 = (int(round(v)) for v in zona)
    a = img[y1:y2, x1:x2]
    if a.size == 0:
        return 0.0
    f = 128 / max(a.shape[:2])
    gris = cv2.cvtColor(cv2.resize(a, None, fx=f, fy=f, interpolation=cv2.INTER_AREA),
                        cv2.COLOR_BGR2GRAY)
    return float((cv2.Canny(cv2.GaussianBlur(gris, (3, 3), 0), 60, 160) > 0).mean())


def evaluar_hueco(img: np.ndarray, rect, cajas):
    """(hueco, cobertura, textura); hueco es None si la zona no se ve bien en este cuadro."""
    alto, ancho = img.shape[:2]
    zona, dentro = zona_producto(rect, ancho, alto)
    if dentro < DENTRO_HUECO or rect[2] - rect[0] < ANCHO_HUECO * ancho:
        return None, None, None
    cob, tex = cobertura(zona, cajas), textura(img, zona)
    return bool(cob < COBERTURA_HUECO and tex < TEXTURA_HUECO), round(cob, 3), round(tex, 4)


# ------------------------------------------------------------------ movimiento de la cámara
class Movimiento:
    """Homografía entre cuadros consecutivos con ORB (sobre una copia de 640 px)."""

    def __init__(self, ancho: int, lado: int = 640):
        self.s = min(1.0, lado / ancho)
        self.S = np.diag([self.s, self.s, 1.0])
        self.Si = np.linalg.inv(self.S)
        self.orb = cv2.ORB_create(1500)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        self.anterior = None

    def __call__(self, img: np.ndarray) -> np.ndarray | None:
        """Homografía del cuadro anterior a este (píxeles completos), o None si se perdió."""
        gris = cv2.cvtColor(cv2.resize(img, None, fx=self.s, fy=self.s,
                                       interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        kp, des = self.orb.detectAndCompute(gris, None)
        anterior, self.anterior = self.anterior, (kp, des, gris.shape)
        if anterior is None or des is None or anterior[1] is None or len(kp) < 20:
            return None
        pares = self.bf.knnMatch(anterior[1], des, k=2)
        buenos = [p[0] for p in pares if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
        if len(buenos) < 15:
            return None
        src = np.float32([anterior[0][m.queryIdx].pt for m in buenos])
        dst = np.float32([kp[m.trainIdx].pt for m in buenos])
        H, inl = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
        if H is None or inl is None or inl.sum() < 12:
            return None
        h, w = gris.shape
        esquinas = cv2.perspectiveTransform(
            np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2), H).reshape(-1, 2)
        area = cv2.contourArea(esquinas.astype(np.float32))
        if not np.isfinite(esquinas).all() or not 0.5 < area / (w * h) < 2.0:
            return None  # deformación absurda: mejor tratarlo como corte
        return self.Si @ H @ self.S


def mover_rect(rect, H: np.ndarray):
    x1, y1, x2, y2 = rect
    p = cv2.perspectiveTransform(
        np.float64([[x1, y1], [x2, y1], [x2, y2], [x1, y2]]).reshape(-1, 1, 2), H).reshape(-1, 2)
    return (float(p[:, 0].min()), float(p[:, 1].min()), float(p[:, 0].max()), float(p[:, 1].max()))


# ------------------------------------------------------------------ seguimiento
@dataclass
class Observacion:
    cuadro: int
    rect: tuple
    alto_digitos: float
    precio: float | None
    confianza: float
    nombre: str
    hueco: bool | None
    cobertura: float | None
    textura: float | None
    recorte: np.ndarray = field(repr=False)
    recorte_zona: np.ndarray | None = field(repr=False)
    sku: str | None = None
    textos_zona: list = field(default_factory=list)  # lo impreso encima: nombre del empaque


@dataclass
class Pista:
    n: int
    rect: tuple
    ultimo: int
    obs: list = field(default_factory=list)
    rects: dict = field(default_factory=dict)  # cuadro procesado -> rect, para el video
    id_: str = ""                               # E1, E2... si sobrevive a la votación
    r: dict = field(default_factory=dict)       # resultado de resumir()


def seguir(indices: list[int], homografias: dict, observaciones: dict, ancho: int, alto: int,
           paciencia: int) -> list[Pista]:
    """Une las observaciones de etiquetas en pistas, arrastrándolas con el movimiento."""
    activas: list[Pista] = []
    todas: list[Pista] = []
    for i, idx in enumerate(indices):
        H = homografias.get(idx)
        if H is None and i > 0:
            activas = []  # corte de escena o movimiento perdido: se empieza de nuevo
        elif H is not None:
            for p in activas:
                p.rect = mover_rect(p.rect, H)
        cuadro = (0, 0, ancho, alto)
        activas = [p for p in activas
                   if _interseccion(p.rect, cuadro) >= 0.3 * _area(p.rect)
                   and idx - p.ultimo <= paciencia]
        nuevas = observaciones.get(idx, [])
        pares = []
        for a, p in enumerate(activas):
            for b, o in enumerate(nuevas):
                w = max(p.rect[2] - p.rect[0], o.rect[2] - o.rect[0])
                d = np.hypot((p.rect[0] + p.rect[2] - o.rect[0] - o.rect[2]) / 2,
                             (p.rect[1] + p.rect[3] - o.rect[1] - o.rect[3]) / 2)
                puntaje = max(iou(p.rect, o.rect), 0.01 if d < 0.5 * w else 0.0)
                if puntaje >= 0.2 or d < 0.5 * w:
                    pares.append((puntaje, a, b))
        usadas_p, usadas_o = set(), set()
        for _, a, b in sorted(pares, reverse=True):
            if a in usadas_p or b in usadas_o:
                continue
            usadas_p.add(a)
            usadas_o.add(b)
            p, o = activas[a], nuevas[b]
            p.obs.append(o)
            p.rect, p.ultimo = o.rect, idx
        for b, o in enumerate(nuevas):
            if b not in usadas_o:
                p = Pista(len(todas) + 1, o.rect, idx, [o])
                activas.append(p)
                todas.append(p)
        for p in activas:
            p.rects[idx] = p.rect
    return todas


def _medoide(nombres: list[str]) -> str:
    nombres = [n for n in nombres if n]
    if not nombres:
        return ""
    return max(nombres, key=lambda n: (sum(parecido(n, m) for m in nombres), len(n)))


def resumir(p: Pista, ancho: int) -> dict | None:
    """Votación de una pista; None si no parece una etiqueta de verdad."""
    leidas = [o for o in p.obs if o.precio is not None]
    if not leidas and len(p.obs) < 2:
        return None  # un número visto una vez y que no se pudo leer
    if len(p.obs) == 1 and leidas and leidas[0].confianza < 0.7:
        return None
    votos = Counter()
    for o in leidas:
        votos[o.precio] += o.confianza
    precio = max(votos, key=votos.get) if votos else None
    ganadoras = [o for o in leidas if o.precio == precio]
    confianza = float(np.mean([o.confianza for o in ganadoras])) if ganadoras else 0.0
    if leidas and len(ganadoras) < 0.5 * len(leidas):
        confianza *= len(ganadoras) / len(leidas)  # se leyeron precios distintos: dudosa
    evaluables = [o for o in p.obs if o.hueco is not None]
    vacios = sum(o.hueco for o in evaluables)
    hueco = bool(evaluables) and vacios >= max(1, 0.6 * len(evaluables))
    mejor = max(ganadoras or p.obs, key=lambda o: o.rect[2] - o.rect[0])
    ancho_rel = max(o.rect[2] - o.rect[0] for o in p.obs) / ancho
    if confianza < 0.5 and ancho_rel < 0.06:
        return None  # etiqueta lejana que no se alcanza a leer: no aporta nada
    zonas = [o for o in evaluables if o.hueco == hueco] or [mejor]
    evidencia_zona = max(zonas, key=lambda o: o.rect[2] - o.rect[0])
    skus = Counter(o.sku for o in p.obs if o.sku)
    # cada palabra cuenta una vez por cuadro: las que se repiten son el empaque, no ruido
    en_zona = Counter(w for o in p.obs for w in set().union(*map(palabras, o.textos_zona)))
    return {
        "nombre_leido": _medoide([o.nombre for o in p.obs]) or None,
        "sku_leido": skus.most_common(1)[0][0] if skus else None,
        "lecturas_sku": skus.most_common(1)[0][1] if skus else 0,
        "texto_producto": dict(en_zona.most_common(12)),  # palabra -> cuadros en que se leyó
        "precio_leido": precio, "confianza_precio": round(confianza, 3),
        "lecturas": len(p.obs), "lecturas_coinciden": len(ganadoras),
        # fracción del peso (confianza) de las lecturas que se llevó el precio ganador
        "acuerdo": round(votos[precio] / sum(votos.values()), 3) if votos else 0.0,
        "precios_vistos": {f"{k:.2f}": v for k, v in
                           Counter(o.precio for o in leidas).most_common()},
        "hueco": hueco, "votos_hueco": [vacios, len(evaluables)],
        "ancho_relativo": round(ancho_rel, 3),
        "cuadro": mejor.cuadro, "primer_cuadro": p.obs[0].cuadro,
        "ultimo_cuadro": p.obs[-1].cuadro,
        "_mejor": mejor, "_zona": evidencia_zona,
    }


# ------------------------------------------------------------------ proceso
def _leer_cuadros(video: str, indices: set[int] | None = None, cada: int = 1):
    """(índice, imagen) de los cuadros pedidos (o uno de cada `cada`)."""
    cap = cv2.VideoCapture(video)
    i = 0
    try:
        while True:
            quiero = (i in indices) if indices is not None else (i % cada == 0)
            if quiero:
                ok, img = cap.read()
                if not ok:
                    break
                yield i, img
            elif not cap.grab():
                break
            i += 1
    finally:
        cap.release()


def procesar(video: str, salida: str, modelo: str = MODELO_DEFECTO, por_segundo: float = 8.0,
             ocr_por_segundo: float = 2.0, dispositivo: str = "auto", imgsz: int = 640,
             confianza: float = 0.2, con_video: bool = True,
             progreso: str | None = None, planograma: str | None = None) -> dict:
    t_inicio = time.perf_counter()
    avisar = Progreso(progreso)
    avisar("eligiendo cuadros", 0, forzar=True)
    tiempos = Tiempos()
    info = cuadros.info_video(video)
    fps = info.fps or 30.0
    cada = max(1, round(fps / por_segundo))
    ventana_ocr = max(cada, round(fps / ocr_por_segundo))
    d_salida = Path(salida)
    d_recortes = d_salida / "recortes"
    if d_recortes.exists():
        shutil.rmtree(d_recortes)
    d_recortes.mkdir(parents=True)

    from motor.huecos import DetectorAnaquel
    from motor.ocr import LectorOCR
    with tiempos.medir("cargar modelos"):
        detector = DetectorAnaquel(modelo, imgsz, confianza, _dispositivo(dispositivo))

    # 1. Movimiento, productos y nitidez
    mov = Movimiento(info.ancho)
    indices, homografias, productos, nitidez = [], {}, {}, {}
    lote = []

    def vaciar():
        with tiempos.medir("yolo"):
            for (k, _), dets in zip(lote, detector.detectar([im for _, im in lote])):
                productos[k] = [d.caja for d in dets if d.clase == "producto"]
        lote.clear()

    for idx, img in _leer_cuadros(video, cada=cada):
        indices.append(idx)
        with tiempos.medir("movimiento"):
            homografias[idx] = mov(img)
            nitidez[idx] = cuadros.nitidez(img)
        lote.append((idx, img))
        if len(lote) == 8:
            vaciar()
        avisar("eligiendo cuadros", 40 * idx / max(1, info.cuadros))
    if lote:
        vaciar()

    # 2. Etiquetas en el cuadro más nítido de cada ventana
    avisar("leyendo etiquetas", 45, forzar=True)
    with tiempos.medir("cargar modelos"):
        lector = LectorOCR("mobile", "cpu")
    elegidos = set()
    for inicio in range(0, info.cuadros or (indices[-1] + 1 if indices else 0), ventana_ocr):
        en_ventana = [i for i in indices if inicio <= i < inicio + ventana_ocr]
        if en_ventana:
            elegidos.add(max(en_ventana, key=lambda i: nitidez[i]))
    observaciones: dict[int, list[Observacion]] = defaultdict(list)
    diag_ocr = {}
    esc = ANCHO_OCR / info.ancho
    hechos = 0
    for idx, img in _leer_cuadros(video, indices=elegidos):
        with tiempos.medir("ocr cuadro completo"):
            grande = cv2.resize(img, None, fx=esc, fy=esc,
                                interpolation=cv2.INTER_CUBIC if esc > 1 else cv2.INTER_AREA)
            lineas = lector.textos([grande], limite=ANCHO_OCR)[0]
            cands = candidatos(lineas, grande, mascara_clara(grande))
        with tiempos.medir("ocr etiquetas"):
            recortes = [recortar(grande, r, 0.08, ANCHO_RECORTE) for _, r, _, _ in cands]
            lecturas = lector.textos(recortes) if recortes else []
        with tiempos.medir("huecos"):
            productos[idx] = sin_etiquetas(productos.get(idx, []),
                                           [tuple(v / esc for v in r) for _, r, _, _ in cands])
            for (h, r, p0, c0), recorte, li in zip(cands, recortes, lecturas):
                precio, conf = leer_precio(li)
                if precio is None and p0 is not None:  # el recorte no se leyó: el del cuadro
                    precio, conf = p0, 0.8 * c0
                rect = tuple(v / esc for v in r)
                hueco, cob, tex = evaluar_hueco(img, rect, productos[idx])
                zona, _ = zona_producto(r, grande.shape[1], grande.shape[0])
                observaciones[idx].append(Observacion(
                    idx, rect, h / esc, precio, conf, leer_nombre(li, recorte.shape[0]),
                    hueco, cob, tex, recorte, recorte_evidencia(img, rect, hueco),
                    leer_sku(li) or leer_sku([l for l in lineas if _centro_en(l[2], r)]),
                    [t for t, c, caja in lineas if c >= 0.5 and _centro_en(caja, zona)]))
        diag_ocr[idx] = {"textos": [t for t, _, _ in lineas],
                         "etiquetas": [{"precio": o.precio, "conf": round(o.confianza, 3),
                                        "nombre": o.nombre, "hueco": o.hueco,
                                        "cobertura": o.cobertura, "textura": o.textura}
                                       for o in observaciones[idx]]}
        hechos += 1
        avisar("leyendo etiquetas", 45 + 40 * hechos / max(1, len(elegidos)))

    # 3. Seguimiento y votación
    with tiempos.medir("seguimiento"):
        pistas = seguir(indices, homografias, observaciones, info.ancho, info.alto,
                        paciencia=int(2 * fps))
        for idx in indices:  # también en los cuadros sin OCR, donde la etiqueta se arrastró
            productos[idx] = sin_etiquetas(productos.get(idx, []),
                                           [p.rects[idx] for p in pistas if idx in p.rects])
        etiquetas = []
        for p in pistas:
            r = resumir(p, info.ancho)
            if r is not None:
                etiquetas.append((p, r))
        etiquetas.sort(key=lambda pr: pr[1]["primer_cuadro"])
    salida_etiquetas = []
    for n, (p, r) in enumerate(etiquetas, 1):
        id_ = f"E{n}"
        cv2.imwrite(str(d_recortes / f"{id_}_etiqueta.jpg"), r["_mejor"].recorte,
                    [cv2.IMWRITE_JPEG_QUALITY, 92])
        if r["_zona"].recorte_zona is not None and r["_zona"].recorte_zona.size:
            cv2.imwrite(str(d_recortes / f"{id_}.jpg"), r["_zona"].recorte_zona,
                        [cv2.IMWRITE_JPEG_QUALITY, 90])
        r["id"] = id_
        r["recorte_etiqueta"] = f"recortes/{id_}_etiqueta.jpg"
        r["recorte_posicion"] = f"recortes/{id_}.jpg" if (d_recortes / f"{id_}.jpg").exists() \
            else None
        if r["hueco"]:
            r["cuadro"] = r["_zona"].cuadro
        p.id_, p.r = id_, r
        salida_etiquetas.append({k: v for k, v in r.items() if not k.startswith("_")})
    acomodo = None
    if planograma:
        from motor import contrato
        from motor.orden import acomodar
        acomodo = acomodar(salida_etiquetas, contrato.leer_planograma(planograma))
        for (p, _), e in zip(etiquetas, salida_etiquetas):
            e["posicion"] = p.r["posicion"] = (acomodo or {}).get("etiquetas", {}).get(e["id"])

    # 4. Video anotado
    if con_video:
        avisar("generando video anotado", 90, forzar=True)
        with tiempos.medir("video anotado"):
            try:
                escribir_video(video, str(d_salida / "recorrido_anotado.mp4"), info, indices,
                               productos, [p for p, r in etiquetas
                                           if acomodo is None or r.get("posicion")])
            except Exception:
                log.exception("falló el video anotado")

    resultado = {"video": Path(video).name, "modo": "libre",
                 "segundos_proceso": round(time.perf_counter() - t_inicio, 1),
                 "fps": round(fps, 3), "cuadros": info.cuadros,
                 "resolucion": [info.ancho, info.alto], "etiquetas": salida_etiquetas}
    if acomodo:
        resultado["planograma"] = acomodo
    (d_salida / "observaciones_libre.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    (d_salida / "diagnostico.json").write_text(json.dumps({
        "video": {"ruta": video, "cuadros": info.cuadros, "fps": fps,
                  "resolucion": [info.ancho, info.alto]},
        "modo": "libre", "cuadros_procesados": len(indices), "cuadros_ocr": sorted(elegidos),
        "movimiento_perdido": sum(1 for i in indices[1:] if homografias.get(i) is None),
        "pistas": len(pistas), "etiquetas": len(salida_etiquetas),
        "tiempos_s": {k: round(v, 2) for k, v in tiempos.t.items()},
        "ocr": {str(k): v for k, v in sorted(diag_ocr.items())},
        "pistas_detalle": [{"pista": p.n, "obs": [
            {"cuadro": o.cuadro, "precio": o.precio, "conf": round(o.confianza, 3),
             "nombre": o.nombre, "hueco": o.hueco, "cobertura": o.cobertura,
             "textura": o.textura, "rect": [round(v) for v in o.rect]} for o in p.obs]}
            for p in pistas]}, ensure_ascii=False, indent=1), encoding="utf-8")
    avisar("listo", 100, forzar=True)
    return resultado


def escribir_video(entrada: str, salida: str, info, indices: list[int], productos: dict,
                   pistas: list[Pista], ancho: int = 1920) -> int:
    """Video H.264 con productos (verde), etiquetas con su precio (naranja) y huecos (rojo)."""
    ancho = min(ancho, info.ancho)
    alto = int(round(info.alto * ancho / info.ancho / 2)) * 2
    sx, sy = ancho / info.ancho, alto / info.alto
    escala = max(0.5, ancho / 1920)
    grosor = max(3, round(6 * ancho / 1920))  # mismo grosor que motor/anotar.py
    margen = int(0.5 * (info.fps or 30))
    lector = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-i", entrada, "-vf", f"scale={ancho}:{alto}",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    escritor = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{ancho}x{alto}", "-r", f"{info.fps}", "-i", "-", "-c:v", "libx264",
         "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags",
         "+faststart", salida], stdin=subprocess.PIPE)

    def px(r):
        return (int(r[0] * sx), int(r[1] * sy)), (int(r[2] * sx), int(r[3] * sy))

    n = 0
    tam = ancho * alto * 3
    try:
        while True:
            buf = lector.stdout.read(tam)
            if len(buf) < tam:
                break
            img = np.frombuffer(buf, np.uint8).reshape(alto, ancho, 3).copy()
            k = bisect.bisect_right(indices, n) - 1
            if k >= 0:
                idx = indices[k]
                for c in productos.get(idx, []):
                    cv2.rectangle(img, *px(c), VERDE, grosor)
                for p in pistas:
                    r = p.rects.get(idx)
                    if r is None or not p.r["primer_cuadro"] - margen <= n <= \
                            p.r["ultimo_cuadro"] + margen:
                        continue
                    nombre = p.r.get("posicion") or p.id_
                    if p.r["hueco"]:
                        zona, _ = zona_producto(r, info.ancho, info.alto)
                        cv2.rectangle(img, *px(zona), ROJO, grosor + 1)
                        _texto(img, f"{nombre} HUECO", (zona[0] * sx + 4, zona[1] * sy + 24 * escala),
                               ROJO, 0.6 * escala)
                    cv2.rectangle(img, *px(r), NARANJA, grosor + 1)
                    precio = p.r["precio_leido"]
                    _texto(img, f"{nombre} " + (f"${precio:.2f}" if precio is not None else "?"),
                           (r[0] * sx, r[1] * sy - 4), BLANCO if precio else NARANJA,
                           0.6 * escala)
            escritor.stdin.write(img.tobytes())
            n += 1
    finally:
        lector.stdout.close()
        lector.wait()
        escritor.stdin.close()
        escritor.wait()
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description="Video sin estructura -> observaciones_libre.json")
    ap.add_argument("--video", required=True)
    ap.add_argument("--salida", default="salida_libre/")
    ap.add_argument("--modelo", default=MODELO_DEFECTO, help="YOLO de productos (SKU-110K)")
    ap.add_argument("--por-segundo", type=float, default=8.0,
                    help="cuadros por segundo para movimiento y productos")
    ap.add_argument("--ocr-por-segundo", type=float, default=2.0,
                    help="cuadros por segundo en los que se buscan etiquetas")
    ap.add_argument("--dispositivo", default="auto", help="auto, cpu o cuda:0 (para YOLO)")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--confianza", type=float, default=0.2)
    ap.add_argument("--sin-video", action="store_true", help="no generar el video anotado")
    ap.add_argument("--progreso", help="JSON con el paso actual y el porcentaje (para la API)")
    ap.add_argument("--planograma", help="planograma.csv del anaquel, si se conoce: acomoda cada "
                                         "etiqueta en su posición por el orden del recorrido")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for ruidoso in ("ppocr", "paddlex", "paddle", "ultralytics"):
        logging.getLogger(ruidoso).setLevel(logging.ERROR)
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

    r = procesar(args.video, args.salida, args.modelo, args.por_segundo, args.ocr_por_segundo,
                 args.dispositivo, args.imgsz, args.confianza, not args.sin_video, args.progreso,
                 args.planograma)
    print(f"\n{r['video']}: {len(r['etiquetas'])} etiquetas en {r['segundos_proceso']} s "
          f"-> {Path(args.salida) / 'observaciones_libre.json'}")
    for e in r["etiquetas"]:
        precio = f"${e['precio_leido']:.2f}" if e["precio_leido"] is not None else "-"
        print(f"  {e['id']}: {precio} {e['sku_leido'] or ''} (conf {e['confianza_precio']}, "
              f"{e['lecturas_coinciden']}/{e['lecturas']}) '{e['nombre_leido'] or ''}' "
              f"hueco={'SÍ' if e['hueco'] else 'no'} {e['votos_hueco']} cuadro={e['cuadro']}"
              + (f" -> {e['posicion'] or 'descartada'}" if "posicion" in e else ""))
    if r.get("planograma"):
        print(f"  recorrido: {r['planograma']['recorrido']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
