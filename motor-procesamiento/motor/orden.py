"""Acomodo de las etiquetas de un video sin marcadores en las posiciones de un planograma conocido,
por el orden en que la cámara pasa por ellas (lo usan motor/libre.py --planograma y cruce/orden.py).

Sin marcadores no hay centímetros, pero la cámara recorre el anaquel en serpentina (R1 de ida, R2
de regreso, R3 de ida) o repisa por repisa. Se alinean las dos secuencias, la de etiquetas
seguidas (en orden de aparición) y la del recorrido, como un diff: el SKU leído en la etiqueta
pesa mucho, el nombre algo y lo demás lo decide el orden. Se prueban los recorridos de `rutas` y
gana el que mejor alinea. Una etiqueta que no cabe en el orden (la misma vista otra vez, un número
suelto) queda sin posición; una posición entre dos etiquetas acomodadas que no recibió ninguna es
una por la que la cámara pasó sin ver etiqueta.
"""
from __future__ import annotations

from motor import contrato
from motor.libre import parecido

# Puntaje de poner una etiqueta en una posición (se maximiza la suma, respetando el orden)
SKU_IGUAL = 10.0  # el SKU leído es el de la posición
SKU_OTRO = 1.0    # se leyó otro SKU: solo el orden la pone aquí
NOMBRE = 5.0      # × parecido del nombre leído con el del planograma, si es al menos 0.6
SOLO_ORDEN = 0.5  # etiqueta bien leída, sin SKU ni nombre
RUIDO = -0.1      # una sola lectura sin SKU ni nombre: mejor descartarla


def rutas(plan: list[contrato.Posicion]) -> dict[str, list[contrato.Posicion]]:
    """Recorridos posibles de la cámara por el anaquel, del más común al menos común."""
    repisas = sorted({p.repisa for p in plan},
                     key=lambda r: -max(p.altura_cm for p in plan if p.repisa == r))
    filas = [sorted((p for p in plan if p.repisa == r), key=lambda p: p.x_ini_cm) for r in repisas]
    resultado = {}
    for desde, orden in (("arriba", filas), ("abajo", filas[::-1])):
        for lado, ida in (("izquierda", True), ("derecha", False)):
            resultado[f"serpentina desde {desde} a la {lado}"] = [
                p for k, f in enumerate(orden) for p in (f if (k % 2 == 0) == ida else f[::-1])]
            resultado[f"repisa por repisa desde {desde} a la {lado}"] = [
                p for f in orden for p in (f if ida else f[::-1])]
    return resultado


def puntaje(e: dict, p: contrato.Posicion) -> float:
    if e.get("sku_leido"):
        return SKU_IGUAL if e["sku_leido"] == p.sku else SKU_OTRO
    sim = parecido(e.get("nombre_leido") or "", (p.nombre or "").upper())
    if sim >= 0.6:
        return NOMBRE * sim
    return SOLO_ORDEN if (e.get("lecturas_coinciden") or 0) >= 2 else RUIDO


def alinear(etiquetas: list[dict], ruta: list[contrato.Posicion]) -> tuple[float, dict[int, int]]:
    """(puntaje, {índice en la ruta: índice de la etiqueta}): la mejor asignación que respeta el
    orden de las dos secuencias, con a lo más una etiqueta por posición."""
    n, m = len(etiquetas), len(ruta)
    s = [[puntaje(e, p) for p in ruta] for e in etiquetas]
    M = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            M[i][j] = max(M[i - 1][j], M[i][j - 1], M[i - 1][j - 1] + s[i - 1][j - 1])
    pares, i, j = {}, n, m
    while i and j:
        if s[i - 1][j - 1] > 0 and M[i][j] == M[i - 1][j - 1] + s[i - 1][j - 1]:
            pares[j - 1] = i - 1
            i, j = i - 1, j - 1
        elif M[i][j] == M[i - 1][j]:
            i -= 1
        else:
            j -= 1
    return M[n][m], pares


def acomodar(etiquetas: list[dict], plan: list[contrato.Posicion]) -> dict | None:
    """{"recorrido", "ruta": posiciones por las que pasó la cámara, en orden, "etiquetas":
    {id de etiqueta: posición}}, o None si ninguna etiqueta se pudo acomodar."""
    mejor = None
    for nombre, ruta in rutas(plan).items():
        total, pares = alinear(etiquetas, ruta)
        if pares and (mejor is None or total > mejor[0]):
            mejor = (total, nombre, ruta, pares)
    if mejor is None:
        return None
    _, nombre, ruta, pares = mejor
    return {"recorrido": nombre,
            "ruta": [p.posicion for p in ruta[min(pares):max(pares) + 1]],
            "etiquetas": {etiquetas[i]["id"]: ruta[j].posicion for j, i in sorted(pares.items())}}
