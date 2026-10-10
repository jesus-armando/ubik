"""Modo sin estructura con planograma por orden: un anaquel cuyo planograma sí se conoce, grabado
sin marcadores ArUco (p. ej., el anaquel de la demo armado en un pizarrón y grabado con el celular).

    python -m cruce.orden --salida-motor analisis/<id>/salida/ --json analisis/<id>/hallazgos.json

Cada etiqueta que siguió motor/libre.py se acomoda en su posición por el orden en que la cámara
pasó por ellas y por el SKU leído (motor/orden.py; lo hace el motor con --planograma, o aquí si
la salida no lo trae).

- Posición entre dos etiquetas acomodadas que no recibió ninguna: etiqueta faltante. Si son
  SIN_LEER o más seguidas, lo más probable es que la cámara pasó rápido y no las leyó: quedan
  como lectura dudosa ("revisar"), no como error.
- Etiqueta que no cabe en el orden (la misma vista otra vez, un número suelto): se descarta.
- Etiqueta con el SKU de otro producto del catálogo: queda donde la pone el orden (etiqueta de
  otro producto). Un SKU que no está en el catálogo se toma como no leído.
- Producto: si encima de la etiqueta se lee el nombre de otro producto del catálogo (impreso en
  el empaque) y no el de la posición, es producto equivocado. Sin texto legible no se juzga.
- Frentes: no se cuentan (SKU-110K no separa bien los frentes de un anaquel armado a mano).

Con eso se arma observaciones.json con el contrato del modo con marcadores y se aplican las
reglas de cruce/hallazgos.py contra el sistema de la demo en pesos (`leer_sistema`): las
etiquetas impresas del anaquel armado están en pesos. Los precios salen de PRECIOS_PESOS
(datos/sistema/precios_pesos.csv) y, para un SKU que no esté ahí, de precios.csv × TIPO_DE_CAMBIO.
Inventario y ventas son los de la demo.
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import replace
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from difflib import SequenceMatcher
from pathlib import Path

from cruce import hallazgos as cruce
from motor import contrato
from motor.libre import palabras
from motor.orden import acomodar

PRECIOS_PESOS = "precios_pesos.csv"  # mismas columnas que precios.csv
TIPO_DE_CAMBIO = 17.5                # pesos por dólar, para lo que no esté en PRECIOS_PESOS
MONEDA = "$"
DISCLAIMER = "Video sin marcadores · Planograma y sistema de la demo, precios en pesos"

SIN_LEER = 2          # posiciones seguidas sin etiqueta: la cámara no las leyó
PRODUCTO_ESTA = 0.6   # el nombre del producto de la posición se lee al menos así encima
PRODUCTO_OTRO = 0.8   # y el de otro producto así: producto equivocado


def nombre_en_empaque(nombre: str, vistas: dict[str, int]) -> float:
    """Qué tanto del nombre de un producto se leyó encima de la etiqueta (0 a 1)."""
    partes = palabras(nombre)
    if not partes or not vistas:
        return 0.0
    return sum(max(SequenceMatcher(None, w, t).ratio() for t in vistas)
               for w in partes) / len(partes)


def identificar(e: dict, p: contrato.Posicion, productos: dict[str, cruce.Producto]) -> str | None:
    """SKU del producto que se ve encima de la etiqueta, solo si es otro que el de la posición."""
    vistas = e.get("texto_producto") or {}
    esperado = productos.get(p.sku) if p.sku else None
    if not vistas or esperado is None or nombre_en_empaque(esperado.nombre, vistas) >= PRODUCTO_ESTA:
        return None
    # nombres de una palabra ("Oatmeal") se confunden con cualquier texto: no cuentan
    otros = [(nombre_en_empaque(x.nombre, vistas), sku) for sku, x in productos.items()
             if sku != p.sku and len(palabras(x.nombre)) >= 2]
    parecido_otro, sku = max(otros, default=(0.0, None))
    return sku if parecido_otro >= PRODUCTO_OTRO else None


def observaciones(obs_libre: dict, sistema: cruce.Sistema) -> tuple[dict, str | None]:
    """observaciones_libre.json -> (observaciones.json del modo con marcadores, recorrido)."""
    etiquetas = obs_libre.get("etiquetas", [])
    acomodo = obs_libre.get("planograma") or acomodar(etiquetas, sistema.plan)
    base = {"video": obs_libre.get("video"), "segundos_proceso": obs_libre.get("segundos_proceso")}
    if not acomodo:
        return {**base, "posiciones": []}, None
    por_id = {e["id"]: {**e, "sku_leido": e.get("sku_leido")
                        if e.get("sku_leido") in sistema.productos else None} for e in etiquetas}
    en = {pos: por_id[id_] for id_, pos in acomodo["etiquetas"].items()}
    plan = {p.posicion: p for p in sistema.plan}

    posiciones = []
    ruta = acomodo["ruta"]  # fuera de este tramo el video no pasó
    for j, codigo in enumerate(ruta):
        p = plan[codigo]
        if codigo in en:
            e = en[codigo]
            posiciones.append({
                "posicion": p.posicion, "etiqueta_visible": True, "sku_leido": e["sku_leido"],
                "precio_leido": e["precio_leido"], "confianza_precio": e["confianza_precio"] or 0.0,
                "lecturas_coinciden": e["lecturas_coinciden"], "hueco": e["hueco"],
                "frentes_vistos": None, "cuadro": e["cuadro"],
                "recorte_etiqueta": e.get("recorte_etiqueta"),
                "recorte_posicion": e.get("recorte_posicion"),
                "sku_producto": None if e["hueco"] else identificar(e, p, sistema.productos),
                "etiqueta": e["id"]})
        else:  # la cámara pasó por aquí (hay etiquetas antes y después) y no vio etiqueta
            a = max(k for k in range(j) if ruta[k] in en)
            b = min(k for k in range(j, len(ruta)) if ruta[k] in en)
            antes, despues = en[ruta[a]], en[ruta[b]]
            sin_leer = b - a - 1 >= SIN_LEER
            posiciones.append({
                "posicion": p.posicion, "sin_leer": sin_leer,
                # sin leer: como una etiqueta ilegible, para que quede en "revisar"
                "etiqueta_visible": sin_leer, "sku_leido": None,
                "precio_leido": None, "confianza_precio": 0.0, "lecturas_coinciden": 0,
                "hueco": False, "frentes_vistos": None,
                "cuadro": (antes["ultimo_cuadro"] + despues["primer_cuadro"]) // 2,
                "recorte_etiqueta": None, "recorte_posicion": None})
    return {**base, "recorrido": acomodo["recorrido"], "posiciones": posiciones}, acomodo["recorrido"]


def en_pesos(sistema: cruce.Sistema, tipo_de_cambio: float = TIPO_DE_CAMBIO) -> cruce.Sistema:
    """El sistema con los precios convertidos y redondeados al centavo (7.09 × 17.5 = 124.08)."""
    def convertir(x: float | None) -> float | None:
        if x is None:
            return None
        return float((Decimal(str(x)) * Decimal(str(tipo_de_cambio)))
                     .quantize(Decimal("0.01"), ROUND_HALF_UP))
    return cruce.Sistema(sistema.plan, {
        sku: replace(p, precio_vigente=convertir(p.precio_vigente),
                     precio_anterior=convertir(p.precio_anterior))
        for sku, p in sistema.productos.items()})


def leer_sistema(dir_sistema: str | Path) -> cruce.Sistema:
    """El sistema de la demo (planograma, inventario y ventas) con los precios en pesos."""
    d = Path(dir_sistema)
    sistema = en_pesos(cruce.leer_sistema(d))
    if not (d / PRECIOS_PESOS).exists():
        return sistema
    with open(d / PRECIOS_PESOS, newline="", encoding="utf-8-sig") as f:
        lista = {r["sku"].strip(): r for r in csv.DictReader(f)}
    return cruce.Sistema(sistema.plan, {
        sku: replace(p, precio_vigente=float(lista[sku]["precio_vigente"]),
                     precio_anterior=cruce._numero(lista[sku].get("precio_anterior")))
        if sku in lista else p for sku, p in sistema.productos.items()})


def construir(obs: dict, recorrido: str | None, sistema: cruce.Sistema, fps: float = 30.0,
              prefijo: str = "/salida", fecha_escaneo: str | None = None,
              video_url: str | None = None, disclaimer: str = DISCLAIMER) -> dict:
    """observaciones (de `observaciones`) + sistema en pesos (de `leer_sistema`) -> hallazgos.json
    con el esquema del tablero."""
    datos = cruce.construir(obs, sistema, fps, prefijo, fecha_escaneo, video_url, disclaimer,
                            moneda=MONEDA)
    sin_leer = {o["posicion"].lower() for o in obs["posiciones"] if o.get("sin_leer")}
    accion = "Verificar en piso si la etiqueta está y volver a grabar esta parte más despacio."
    for h in datos["hallazgos"]:
        if h["id"].removeprefix("hallazgo-") in sin_leer:
            h.update(descripcion="La cámara pasó por aquí sin leer ninguna etiqueta, igual que en "
                                 "la posición vecina: puede faltar la etiqueta o el video no la "
                                 "alcanzó a leer.", accion_sugerida=accion)
    for f in datos["posiciones"]:
        if f["id"].removeprefix("pos-") in sin_leer:
            f["accion"] = accion
    datos["resumen"].update(
        modo="orden", recorrido=recorrido,
        supuestos_calculo=f"{cruce.SUPUESTOS} Sin marcadores: cada etiqueta se ubicó por el orden "
                          f"del recorrido ({recorrido}) y su SKU. Precios del sistema en pesos "
                          "(los del anaquel armado) y ventas de la demo. Los frentes no se cuentan "
                          "en este modo.")
    return datos


def desde_carpeta(dir_motor: str | Path, sistema: cruce.Sistema, prefijo: str = "/salida",
                  **opciones) -> dict:
    """Arma hallazgos.json a partir de la salida de motor/libre.py y del sistema en pesos (de
    `leer_sistema`), y deja junto a ella el observaciones.json del modo con marcadores
    (opciones: `video_url`, `disclaimer`)."""
    d = Path(dir_motor)
    ruta = d / "observaciones_libre.json"
    obs_libre = json.loads(ruta.read_text(encoding="utf-8"))
    obs, recorrido = observaciones(obs_libre, sistema)
    (d / "observaciones.json").write_text(json.dumps(obs, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    fecha = datetime.fromtimestamp(ruta.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    return construir(obs, recorrido, sistema, float(obs_libre.get("fps") or 30.0), prefijo, fecha,
                     **opciones)


def main(argv=None):
    ap = argparse.ArgumentParser(description="observaciones_libre.json + planograma -> hallazgos.json")
    ap.add_argument("--salida-motor", default="salida_libre/")
    ap.add_argument("--sistema", default="datos/sistema/", help="planograma, precios, inventario")
    ap.add_argument("--json", default=None, help="por omisión, en la carpeta del motor")
    ap.add_argument("--prefijo", default="/salida", help="URL base de los recortes en el tablero")
    args = ap.parse_args(argv)

    datos = desde_carpeta(args.salida_motor, leer_sistema(args.sistema), args.prefijo)
    destino = Path(args.json or Path(args.salida_motor) / "hallazgos.json")
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{datos['resumen']['frase']} ({datos['resumen']['recorrido']}) -> {destino}")
    for h in datos["hallazgos"]:
        print(f"  R{h['repisa']}-P{h['posicion']} {h['tipo']:<22} {MONEDA}{h['impacto_diario']:>8.2f}"
              f"  {h['producto']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
