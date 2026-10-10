"""Huecos: YOLO (etiqueta, producto, hueco) en los cuadros elegidos -> posiciones.

El centro de cada caja se convierte a cm con la homografía y se asigna a la posición cuyo
rango x_ini_cm–x_fin_cm y repisa lo contienen. Una posición es hueco si en la mayoría de
los cuadros donde se ve completa hay una caja `hueco` que la cubre (≥ 80 % del ancho) o
no hay ninguna caja `producto`.

Con un modelo de una sola clase (p. ej. el de SKU-110K para el clip real) todas las cajas
cuentan como `producto` y el hueco sale solo de "no hay producto".
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from motor import contrato
from motor.marcadores import Homografia

CLASES = ("etiqueta", "producto", "hueco")
COBERTURA_HUECO = 0.8


@dataclass
class Deteccion:
    clase: str
    confianza: float
    caja: tuple[float, float, float, float]          # px: x1, y1, x2, y2
    caja_cm: tuple[float, float, float, float] | None = None  # cm: x1, y_abajo, x2, y_arriba
    posicion: str | None = None


class DetectorAnaquel:
    def __init__(self, ruta_modelo: str, imgsz: int = 960, confianza: float = 0.35,
                 dispositivo: str | None = None):
        from ultralytics import YOLO
        self.modelo = YOLO(ruta_modelo)
        self.imgsz, self.confianza = imgsz, confianza
        self.dispositivo = dispositivo
        nombres = self.modelo.names
        self.mapa = {}
        for i, n in nombres.items():
            n = str(n).lower()
            self.mapa[i] = n if n in CLASES else ("producto" if len(nombres) == 1 else n)
        self.tiene_huecos = "hueco" in self.mapa.values()

    def detectar(self, imagenes: list[np.ndarray]) -> list[list[Deteccion]]:
        if not imagenes:
            return []
        res = self.modelo.predict(imagenes, imgsz=self.imgsz, conf=self.confianza,
                                  device=self.dispositivo, verbose=False, max_det=300)
        salida = []
        for r in res:
            cajas = r.boxes
            dets = []
            for xyxy, c, k in zip(cajas.xyxy.cpu().numpy(), cajas.conf.cpu().numpy(),
                                  cajas.cls.cpu().numpy().astype(int)):
                clase = self.mapa.get(int(k))
                if clase in CLASES:
                    dets.append(Deteccion(clase, float(c), tuple(float(v) for v in xyxy)))
            salida.append(dets)
        return salida


def fraccion_visible(rect_cm, h: Homografia, ancho: int, alto: int) -> float:
    """Fracción del rectángulo (cm) que cae dentro del cuadro."""
    esq = h.rect_a_px(rect_cm)
    x1, y1 = esq.min(axis=0)
    x2, y2 = esq.max(axis=0)
    area = max(1e-6, (x2 - x1) * (y2 - y1))
    ix = max(0.0, min(x2, ancho) - max(x1, 0))
    iy = max(0.0, min(y2, alto) - max(y1, 0))
    return float(ix * iy / area)


def caja_a_cm(caja, h: Homografia):
    x1, y1, x2, y2 = caja
    esq = h.a_cm([[x1, y1], [x2, y1], [x2, y2], [x1, y2]])
    return (float(esq[:, 0].min()), float(esq[:, 1].min()),
            float(esq[:, 0].max()), float(esq[:, 1].max()))


def asignar(detecciones: list[Deteccion], h: Homografia,
            planograma: list[contrato.Posicion]) -> list[Deteccion]:
    """Pone caja_cm y posición a cada detección de producto o hueco."""
    en_seccion = [p for p in planograma if p.seccion == h.seccion]
    for d in detecciones:
        d.caja_cm = caja_a_cm(d.caja, h)
        if d.clase == "etiqueta":
            continue
        cx = (d.caja_cm[0] + d.caja_cm[2]) / 2
        cy = (d.caja_cm[1] + d.caja_cm[3]) / 2
        p = contrato.posicion_en(en_seccion, cx, cy)
        if p is None:  # cajas altas: probar con la base de la caja
            p = contrato.posicion_en(en_seccion, cx, d.caja_cm[1] + 2.0)
        d.posicion = p.posicion if p else None
    return detecciones


@dataclass
class VistaPosicion:
    """Lo que un cuadro dice de una posición."""
    cuadro: int
    visible: float
    productos: int
    hueco_cubre: float           # fracción del ancho cubierta por la mayor caja hueco
    vacio: bool
    cajas_cm: list = field(default_factory=list)


def vistas_por_posicion(indice: int, detecciones: list[Deteccion], h: Homografia,
                        planograma: list[contrato.Posicion], ancho: int, alto: int
                        ) -> dict[str, VistaPosicion]:
    prod = defaultdict(list)
    cajas_hueco = defaultdict(list)
    for d in detecciones:
        if d.posicion is None:
            continue
        if d.clase == "producto":
            prod[d.posicion].append(d)
        elif d.clase == "hueco":
            cajas_hueco[d.posicion].append(d)
    vistas = {}
    for p in planograma:
        if p.seccion != h.seccion:
            continue
        vis = fraccion_visible(p.rect_producto_cm(), h, ancho, alto)
        if vis <= 0:
            continue
        cubre = 0.0
        for d in cajas_hueco.get(p.posicion, []):
            x1 = max(d.caja_cm[0], p.x_ini_cm)
            x2 = min(d.caja_cm[2], p.x_fin_cm)
            cubre = max(cubre, max(0.0, x2 - x1) / p.ancho_cm)
        n = len(prod.get(p.posicion, []))
        vistas[p.posicion] = VistaPosicion(indice, vis, n, cubre,
                                           n == 0 or cubre >= COBERTURA_HUECO,
                                           [d.caja_cm for d in prod.get(p.posicion, [])])
    return vistas


def elegir_vistas(vistas: list[VistaPosicion]) -> list[VistaPosicion]:
    """Cuadros donde la posición se ve completa; si no hay, los que la ven a medias."""
    completas = [v for v in vistas if v.visible >= 0.98]
    if completas:
        return completas
    return [v for v in vistas if v.visible >= 0.5]


def es_hueco(vistas: list[VistaPosicion]) -> tuple[bool, int, int]:
    """(hueco, cuadros que votan vacío, cuadros que cuentan)."""
    usadas = elegir_vistas(vistas)
    if not usadas:
        return False, 0, 0
    vacios = sum(v.vacio for v in usadas)
    return vacios * 2 > len(usadas), vacios, len(usadas)
