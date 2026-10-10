"""Constantes del contrato y lectura del planograma.

Todo lo que el motor sabe del anaquel físico vive aquí (ver CONTRATO.md). El motor no
lee escena/ ni video/verdad/: solo el planograma y estas constantes.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

# Marcadores ArUco: DICT_4X4_100, 5 cm, id = seccion*20 + repisa*4 + k
MARCADOR_LADO_CM = 5.0
MARCADOR_X_CM = (0.0, 55.0, 110.0)  # esquina superior izquierda, por k

# Repisas: altura de la superficie en cm desde el piso
ALTURA_REPISA_CM = {1: 120.0, 2: 75.0, 3: 30.0}
ALTO_UTIL_REPISA_CM = 30.0  # alto de la zona de producto que se mira por posición

# Etiqueta: 6 x 3.5 cm, borde superior a la altura de la superficie de la repisa
ETIQUETA_ANCHO_CM = 6.0
ETIQUETA_ALTO_CM = 3.5
ETIQUETA_ANCHO_PX = 600
ETIQUETA_ALTO_PX = 350
ETIQUETA_BORDE_PX = 30
COLOR_BORDE_ETIQUETA = (0xFF, 0x6A, 0x00)  # RGB de #FF6A00

FRENTES_ESPERADOS = 3


def id_marcador(seccion: int, repisa: int, k: int) -> int:
    return seccion * 20 + repisa * 4 + k


def decodificar_marcador(id_: int) -> tuple[int, int, int]:
    """id -> (seccion, repisa, k)."""
    return id_ // 20, (id_ % 20) // 4, id_ % 4


def repisa_a_numero(valor) -> int:
    m = re.search(r"\d+", str(valor))
    if not m:
        raise ValueError(f"repisa inválida: {valor!r}")
    return int(m.group())


@dataclass(frozen=True)
class Posicion:
    posicion: str
    seccion: int
    repisa: int
    x_ini_cm: float
    x_fin_cm: float
    altura_cm: float
    frentes_esperados: int
    sku: str | None = None
    nombre: str | None = None

    @property
    def repisa_nombre(self) -> str:
        return f"R{self.repisa}"

    @property
    def ancho_cm(self) -> float:
        return self.x_fin_cm - self.x_ini_cm

    def rect_producto_cm(self) -> tuple[float, float, float, float]:
        """(x1, y_abajo, x2, y_arriba) de la zona donde van los productos."""
        return (self.x_ini_cm, self.altura_cm, self.x_fin_cm,
                self.altura_cm + ALTO_UTIL_REPISA_CM)

    def rect_etiqueta_cm(self) -> tuple[float, float, float, float]:
        """Dónde debe estar la etiqueta si se respeta el contrato (centrada)."""
        cx = (self.x_ini_cm + self.x_fin_cm) / 2
        return (cx - ETIQUETA_ANCHO_CM / 2, self.altura_cm - ETIQUETA_ALTO_CM,
                cx + ETIQUETA_ANCHO_CM / 2, self.altura_cm)

    def rect_recorte_cm(self) -> tuple[float, float, float, float]:
        """Zona del recorte de la posición: productos y etiqueta."""
        return (self.x_ini_cm, self.altura_cm - 6.0, self.x_fin_cm,
                self.altura_cm + ALTO_UTIL_REPISA_CM + 4.0)


def leer_planograma(ruta: str | Path) -> list[Posicion]:
    posiciones = []
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        for fila in csv.DictReader(f):
            fila = {k.strip(): (v or "").strip() for k, v in fila.items() if k}
            repisa = repisa_a_numero(fila["repisa"])
            altura = fila.get("altura_cm") or ALTURA_REPISA_CM.get(repisa)
            if altura in (None, ""):
                raise ValueError(f"sin altura para la repisa {repisa}; agrega altura_cm")
            posiciones.append(Posicion(
                posicion=fila["posicion"],
                seccion=int(fila.get("seccion") or 1),
                repisa=repisa,
                x_ini_cm=float(fila["x_ini_cm"]),
                x_fin_cm=float(fila["x_fin_cm"]),
                altura_cm=float(altura),
                frentes_esperados=int(fila.get("frentes_esperados") or FRENTES_ESPERADOS),
                sku=fila.get("sku") or None,
                nombre=fila.get("nombre") or None,
            ))
    if not posiciones:
        raise ValueError(f"planograma vacío: {ruta}")
    return posiciones


def alturas_por_repisa(posiciones: list[Posicion]) -> dict[tuple[int, int], float]:
    """(seccion, repisa) -> altura de la superficie, para ubicar los marcadores."""
    alturas = {}
    for p in posiciones:
        alturas[(p.seccion, p.repisa)] = p.altura_cm
    return alturas


def posicion_en(posiciones: list[Posicion], x_cm: float, y_cm: float,
                seccion: int | None = None) -> Posicion | None:
    """Posición cuya zona de producto contiene el punto (x, y) en cm."""
    for p in posiciones:
        if seccion is not None and p.seccion != seccion:
            continue
        x1, y1, x2, y2 = p.rect_producto_cm()
        if x1 <= x_cm < x2 and y1 <= y_cm < y2 + 6.0:
            return p
    return None


def posicion_de_etiqueta(posiciones: list[Posicion], x_cm: float, y_cm: float,
                         tolerancia_y_cm: float = 3.0) -> Posicion | None:
    """Posición a la que pertenece una etiqueta cuyo centro está en (x, y) cm.

    La x decide la posición (rango x_ini–x_fin) y la y decide la repisa: el centro de la
    etiqueta debe quedar a ~1.75 cm por debajo de la superficie.
    """
    mejor, mejor_dy = None, tolerancia_y_cm
    for p in posiciones:
        if not (p.x_ini_cm <= x_cm < p.x_fin_cm):
            continue
        dy = abs(y_cm - (p.altura_cm - ETIQUETA_ALTO_CM / 2))
        if dy <= mejor_dy:
            mejor, mejor_dy = p, dy
    return mejor
