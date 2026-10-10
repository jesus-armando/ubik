"""Escenas aleatorias para entrenar el detector YOLO (etiqueta, producto, hueco).

Cada escena cambia productos (incluye empaques inventados), frentes (0 a 3), huecos,
etiquetas faltantes o corridas, precios, alturas de caja, color del fondo, brillo y la
vibración de la cámara. Se renderizan con el mismo contrato que el video del demo, pero
el video del demo no se usa para entrenar: así las métricas sobre él son honestas.

    python -m simulador.escenas_entrenamiento --n 10 --salida datos_entrenamiento
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np

from motor import contrato
from simulador import graficos, realismo, render
from simulador.datos_prueba import CATALOGO

PALABRAS = ["Blueberry", "Glazed", "Vanilla", "Mocha", "Cinnamon", "Maple", "Turkey",
            "Cheddar", "Lemon", "Honey", "Almond", "Berry", "Classic", "Iced", "Hot",
            "Muffin", "Bagel", "Wrap", "Latte", "Cookie", "Donut", "Scone", "Brownie",
            "Tea", "Croissant", "Sandwich", "Granola", "Pretzel", "Chips", "Water"]


def catalogo_aleatorio(rng: random.Random, nrng: np.random.Generator, n_extra=18):
    productos = {sku: {"nombre": nombre} for sku, (nombre, _, _) in CATALOGO.items()}
    for _ in range(n_extra):
        sku = f"SKU-{rng.randint(200000, 299999)}"
        productos[sku] = {"nombre": " ".join(rng.sample(PALABRAS, rng.randint(1, 3))),
                          "color": list(graficos.color_aleatorio(nrng)),
                          "forma": rng.randint(0, 5)}
    return productos


def escena_aleatoria(semilla: int, planograma: list[contrato.Posicion]) -> dict:
    rng = random.Random(semilla)
    nrng = np.random.default_rng(semilla)
    productos = catalogo_aleatorio(rng, nrng)
    skus = list(productos)
    posiciones = []
    for p in planograma:
        sku = rng.choice(skus)
        fisico = sku if rng.random() < 0.85 else rng.choice(skus)
        frentes = rng.choices([0, 1, 2, 3], weights=[0.18, 0.12, 0.15, 0.55])[0]
        etiqueta = {"visible": rng.random() < 0.88}
        if etiqueta["visible"]:
            sku_et = sku if rng.random() < 0.85 else rng.choice(skus)
            etiqueta.update(sku=sku_et, nombre=productos[sku_et]["nombre"],
                            precio=round(rng.uniform(0.99, 39.99), 2),
                            desplazamiento_cm=round(rng.uniform(-3, 3), 1),
                            vigente_desde=rng.choice(["2026-02-01", "2026-03-01"]))
        prod = productos[fisico]
        posiciones.append({
            "posicion": p.posicion, "repisa": p.repisa_nombre, "sku_planograma": sku,
            "sku_fisico": fisico, "frentes_fisicos": frentes, "etiqueta": etiqueta,
            "producto_nombre": prod["nombre"], "producto_color": prod.get("color"),
            "producto_forma": prod.get("forma"),
            "alto_cm": round(rng.uniform(18, 32), 1), "paso_cm": round(rng.uniform(8.6, 10), 2),
            "error": None})
    gris = rng.randint(170, 225)
    return {"tienda": "ENTRENAMIENTO", "fecha": "2026-03-03", "seccion": 1,
            "posiciones": posiciones,
            "_color_fondo": [gris + rng.randint(-12, 12) for _ in range(3)],
            "_color_piso": [rng.randint(110, 170)] * 3}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--inicio", type=int, default=0)
    ap.add_argument("--planograma", default="datos/sistema/planograma.csv")
    ap.add_argument("--salida", default="datos_entrenamiento")
    ap.add_argument("--fps", type=float, default=10)
    ap.add_argument("--res", default="3840x2160")
    args = ap.parse_args(argv)
    plan = contrato.leer_planograma(args.planograma)
    for k in range(args.inicio, args.inicio + args.n):
        d = Path(args.salida) / f"escena_{k:02d}"
        if (d / "recorrido_realista.mp4").exists():
            print(f"{d}: ya existe")
            continue
        d.mkdir(parents=True, exist_ok=True)
        esc = escena_aleatoria(1000 + k, plan)
        (d / "escena.json").write_text(json.dumps(esc, ensure_ascii=False, indent=1))
        brillo = random.Random(k).uniform(0.85, 1.12)
        render.main(["--escena", str(d / "escena.json"), "--planograma", args.planograma,
                     "--empaques", "escena/empaques",
                     "--video", str(d / "recorrido.mp4"), "--verdad", str(d / "verdad"),
                     "--fps", str(args.fps), "--res", args.res, "--variacion", "1",
                     "--brillo", f"{brillo:.3f}", "--semilla", str(k)])
        realismo.main([str(d / "recorrido.mp4"), str(d / "recorrido_realista.mp4"),
                       "--semilla", str(k)])
        (d / "recorrido.mp4").unlink()


if __name__ == "__main__":
    main()
