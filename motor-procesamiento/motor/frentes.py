"""Frentes: mediana, entre cuadros, del número de cajas `producto` en cada posición.

Solo cuentan los cuadros donde la posición se ve completa (ver huecos.elegir_vistas);
un cuadro que la ve cortada contaría de menos.
"""
from __future__ import annotations

import statistics

from motor.huecos import VistaPosicion, elegir_vistas


def contar_frentes(vistas: list[VistaPosicion]) -> int:
    usadas = elegir_vistas(vistas)
    if not usadas:
        return 0
    return int(statistics.median_high(v.productos for v in usadas))


def vista_representativa(vistas: list[VistaPosicion], frentes: int) -> VistaPosicion | None:
    """Cuadro cuyo conteo coincide con el resultado; sirve para el recorte y el video."""
    usadas = elegir_vistas(vistas)
    if not usadas:
        return None
    iguales = [v for v in usadas if v.productos == frentes] or usadas
    return iguales[len(iguales) // 2]
