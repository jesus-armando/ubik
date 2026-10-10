"""Entrena YOLO nano (etiqueta, producto, hueco) con el dataset de preparar_yolo.py.

Reemplaza el notebook de Colab: 40 épocas, reanudable (si se corta, se vuelve a correr el
mismo comando), copia best.pt a modelos/anaquel.pt y muestra el mAP50 en validación.

    python -m motor.preparar_yolo --fuente video/verdad video/recorrido_realista.mp4
    python -m entrenamiento.entrenar_yolo
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from entrenamiento.comun import entrenar, validar


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--datos", default="datasets/anaquel/data.yaml")
    ap.add_argument("--nombre", default="anaquel")
    ap.add_argument("--epocas", type=int, default=40)
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--lote", type=int, default=8, help="8 cabe en una GPU de 4 GB a 960")
    ap.add_argument("--base", default="yolo11n.pt")
    ap.add_argument("--modelo", default="modelos/anaquel.pt")
    args = ap.parse_args(argv)

    # Sin volteos verticales ni mosaicos raros: el anaquel siempre se ve de frente y derecho.
    entrenar(args.datos, args.nombre, args.epocas, args.imgsz, args.base, args.lote,
             args.modelo, fliplr=0.5, flipud=0.0, degrees=2.0, mosaic=0.5, close_mosaic=10,
             hsv_h=0.01)
    m = validar(args.modelo, args.datos, args.imgsz, args.lote)
    print(f"\nmAP50 en validación: {m['mAP50']:.3f} · mAP50-95: {m['mAP50-95']:.3f}")
    for clase, ap50 in m["por_clase"].items():
        print(f"  {clase}: {ap50:.3f}")
    print(f"modelo: {args.modelo}")
    Path(args.modelo).with_suffix(".json").write_text(json.dumps(m, indent=1))


if __name__ == "__main__":
    main()
