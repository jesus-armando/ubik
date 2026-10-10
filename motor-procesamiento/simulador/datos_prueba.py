"""Datos de prueba que sustituyen a los entregables de P4 (y los assets de P1).

Genera:
  datos/sistema/planograma.csv
  datos/sistema/precios.csv        (precio vigente y anterior por SKU)
  datos/sistema/inventario.csv     (existencia al cierre y venta diaria por SKU)
  escena/escena.json               (8 errores sembrados del Paso 7)
  escena/tarjetas/<tarjeta>.json   (4 variantes para el modo jurado)
  escena/etiquetas/<posicion>.png  (600 x 350, una por posición)
  escena/empaques/<sku>.png        (800 x 1000)
  escena/marcadores/aruco_<id>.png (500 x 500)

Los nombres y los precios de los errores 1 y 2 vienen del plan; el resto de los precios
son de prueba. Cuando P4 entregue sus archivos, se usan los de P4.

    python -m simulador.datos_prueba
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path

import cv2

from motor import contrato
from simulador import graficos

# sku: (nombre, precio vigente, precio anterior)
CATALOGO = {
    "SKU-100664": ("Original Coffee Cake Muffin", 7.69, 7.09),
    "SKU-100104": ("2 Lbs. Coffee", 24.99, 23.49),
    "SKU-101809": ("Caramel Iced Coffee", 4.99, 4.59),
    "SKU-100506": ("12 Bagels", 16.99, 15.99),
    "SKU-100292": ("Oatmeal", 4.29, 3.99),
    "SKU-100601": ("Pretzel Bites", 5.49, 5.19),
    "SKU-100131": ("Bagel W Butter", 2.89, 2.69),
    "SKU-101664": ("Chocolate Chunk Cookie", 3.29, 3.09),
    "SKU-100075": ("Tuna Salad Wrap", 8.99, 8.49),
    "SKU-100599": ("8 Donut Holes", 4.49, 4.19),
    "SKU-102560": ("Bacon Roll Up", 6.79, 6.39),
    "SKU-100936": ("French Toast Bagel", 2.39, 2.19),
    "SKU-102199": ("Chicken Croissant", 7.49, 6.99),
}

# sku: (existencia al cierre, venta diaria en piezas). R3-P1 tiene 6 piezas (hueco con
# inventario) y R3-P2 tiene 0 (agotado real), como dice la tabla de errores.
INVENTARIO = {
    "SKU-100664": (24, 18), "SKU-100104": (10, 6), "SKU-101809": (30, 25),
    "SKU-100506": (9, 8), "SKU-100292": (20, 15), "SKU-100601": (15, 12),
    "SKU-100131": (18, 20), "SKU-101664": (26, 22), "SKU-100075": (6, 9),
    "SKU-100599": (0, 14), "SKU-102560": (12, 10), "SKU-100936": (14, 16),
    "SKU-102199": (7, 8),
}

PLANOGRAMA = [  # posicion -> sku esperado
    ("R1-P1", "SKU-100664"), ("R1-P2", "SKU-100104"), ("R1-P3", "SKU-101809"),
    ("R1-P4", "SKU-100506"),
    ("R2-P1", "SKU-100292"), ("R2-P2", "SKU-100601"), ("R2-P3", "SKU-100131"),
    ("R2-P4", "SKU-101664"),
    ("R3-P1", "SKU-100075"), ("R3-P2", "SKU-100599"), ("R3-P3", "SKU-102560"),
    ("R3-P4", "SKU-100936"),
]

SECCION = 1
TIENDA, FECHA = "S012", "2026-03-03"


def filas_planograma():
    for pos, sku in PLANOGRAMA:
        repisa = contrato.repisa_a_numero(pos.split("-")[0])
        p = contrato.repisa_a_numero(pos.split("-")[1])
        x_ini = (p - 1) * 30
        yield {"posicion": pos, "seccion": SECCION, "repisa": f"R{repisa}", "sku": sku,
               "nombre": CATALOGO[sku][0], "x_ini_cm": x_ini, "x_fin_cm": x_ini + 30,
               "altura_cm": int(contrato.ALTURA_REPISA_CM[repisa]),
               "frentes_esperados": contrato.FRENTES_ESPERADOS}


def etiqueta_de(sku: str, precio: float | None = None, vigente_desde="2026-03-01"):
    nombre, vigente, _ = CATALOGO[sku]
    return {"visible": True, "sku": sku, "nombre": nombre,
            "precio": vigente if precio is None else precio,
            "upc": graficos.upc_desde_sku(sku), "vigente_desde": vigente_desde}


def escena_base() -> dict:
    posiciones = {}
    for pos, sku in PLANOGRAMA:
        posiciones[pos] = {"posicion": pos, "repisa": pos.split("-")[0],
                           "sku_planograma": sku, "sku_fisico": sku,
                           "frentes_fisicos": contrato.FRENTES_ESPERADOS,
                           "etiqueta": etiqueta_de(sku), "error": None}

    def error(pos, id_, tipo, descripcion):
        posiciones[pos]["error"] = {"id": id_, "tipo": tipo, "descripcion": descripcion}

    # Tabla de errores sembrados (Paso 7 del plan)
    posiciones["R1-P1"]["etiqueta"] = etiqueta_de("SKU-100664", 7.09, "2026-02-01")
    error("R1-P1", 1, "precio_anterior", "Etiqueta con precio anterior US$7.09 (vigente 7.69)")
    posiciones["R1-P3"]["etiqueta"] = etiqueta_de("SKU-101809", 4.59, "2026-02-01")
    error("R1-P3", 2, "precio_anterior", "Precio anterior US$4.59 (vigente 4.99)")
    posiciones["R2-P2"]["etiqueta"] = {"visible": False}
    error("R2-P2", 3, "etiqueta_faltante", "Sin etiqueta")
    posiciones["R2-P4"]["etiqueta"] = etiqueta_de("SKU-100506")
    error("R2-P4", 4, "etiqueta_otro_sku", "Etiqueta de 12 Bagels sobre Chocolate Chunk Cookie")
    posiciones["R3-P1"]["frentes_fisicos"] = 0
    error("R3-P1", 5, "hueco_con_inventario", "Hueco; el sistema dice 6 piezas al cierre")
    posiciones["R3-P2"]["frentes_fisicos"] = 0
    error("R3-P2", 6, "hueco_agotado", "Hueco; el sistema dice 0 (agotado real)")
    posiciones["R3-P3"]["sku_fisico"] = "SKU-102199"
    error("R3-P3", 7, "producto_equivocado",
          "Chicken Croissant sobre la etiqueta de Bacon Roll Up")
    posiciones["R1-P4"]["frentes_fisicos"] = 1
    error("R1-P4", 8, "frentes_bajos", "1 frente de 3 esperados")

    return {"tienda": TIENDA, "fecha": FECHA, "seccion": SECCION,
            "posiciones": list(posiciones.values())}


def tarjetas(base: dict) -> dict[str, dict]:
    """Las 4 variantes del modo jurado: la escena base más un error nuevo."""
    def variante(nombre, pos, cambio, tipo, descripcion):
        esc = copy.deepcopy(base)
        p = next(p for p in esc["posiciones"] if p["posicion"] == pos)
        cambio(p)
        p["error"] = {"id": 9, "tipo": tipo, "descripcion": descripcion}
        esc["tarjeta"] = {"nombre": nombre, "posicion": pos, "repisa": pos.split("-")[0]}
        return esc

    sku_r2p1 = "SKU-100292"
    return {
        "precio_viejo": variante(
            "precio_viejo", "R2-P1",
            lambda p: p.update(etiqueta=etiqueta_de(sku_r2p1, CATALOGO[sku_r2p1][2], "2026-02-01")),
            "precio_anterior", "Precio viejo en Oatmeal"),
        "etiqueta_otro_sku": variante(
            "etiqueta_otro_sku", "R2-P3",
            lambda p: p.update(etiqueta=etiqueta_de("SKU-100936")),
            "etiqueta_otro_sku", "Etiqueta de French Toast Bagel sobre Bagel W Butter"),
        "etiqueta_quitada": variante(
            "etiqueta_quitada", "R1-P2",
            lambda p: p.update(etiqueta={"visible": False}),
            "etiqueta_faltante", "Etiqueta quitada en 2 Lbs. Coffee"),
        "producto_retirado": variante(
            "producto_retirado", "R3-P4",
            lambda p: p.update(frentes_fisicos=0),
            "hueco_con_inventario", "Producto retirado: French Toast Bagel"),
    }


def escribir_json(ruta: Path, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def escribir_csv(ruta: Path, filas: list[dict]):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


def escribir_sistema(raiz: Path):
    """Los CSV del sistema de la tienda que usa el cruce (cruce/): precios e inventario."""
    escribir_csv(raiz / "datos/sistema/precios.csv", [
        {"sku": sku, "nombre": nombre, "precio_vigente": vigente, "precio_anterior": anterior,
         "vigente_desde": "2026-03-01"}
        for sku, (nombre, vigente, anterior) in CATALOGO.items()])
    escribir_csv(raiz / "datos/sistema/inventario.csv", [
        {"sku": sku, "existencia": existencia, "venta_diaria": venta}
        for sku, (existencia, venta) in INVENTARIO.items()])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raiz", default=".", help="raíz del proyecto")
    args = ap.parse_args()
    raiz = Path(args.raiz)

    plan = raiz / "datos/sistema/planograma.csv"
    filas = list(filas_planograma())
    escribir_csv(plan, filas)
    escribir_sistema(raiz)

    base = escena_base()
    escribir_json(raiz / "escena/escena.json", base)
    for nombre, esc in tarjetas(base).items():
        escribir_json(raiz / f"escena/tarjetas/{nombre}.json", esc)

    d_et = raiz / "escena/etiquetas"
    d_et.mkdir(parents=True, exist_ok=True)
    for p in base["posiciones"]:
        e = p["etiqueta"]
        if e.get("visible"):
            img = graficos.dibujar_etiqueta(e["nombre"], e["precio"], e["sku"], e["upc"],
                                            e["vigente_desde"])
            cv2.imwrite(str(d_et / f"{p['posicion']}.png"), img)

    d_emp = raiz / "escena/empaques"
    d_emp.mkdir(parents=True, exist_ok=True)
    for i, (sku, (nombre, _, _)) in enumerate(CATALOGO.items()):
        # color y forma por índice para que los 13 empaques se vean distintos
        img = graficos.dibujar_empaque(sku, nombre, graficos.PALETA[i], forma=i % 6)
        cv2.imwrite(str(d_emp / f"{sku}.png"), img)

    d_mk = raiz / "escena/marcadores"
    d_mk.mkdir(parents=True, exist_ok=True)
    for repisa in (1, 2, 3):
        for k in range(3):
            id_ = contrato.id_marcador(SECCION, repisa, k)
            cv2.imwrite(str(d_mk / f"aruco_{id_}.png"), graficos.dibujar_marcador(id_))

    print(f"planograma: {plan} ({len(filas)} posiciones)")
    print(f"escena: {raiz / 'escena/escena.json'} (8 errores) + 4 tarjetas")
    print(f"etiquetas: {d_et} · empaques: {d_emp} · marcadores: {d_mk}")


if __name__ == "__main__":
    main()
