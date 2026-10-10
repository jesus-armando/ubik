"""Convierte video/verdad/cuadro_*.json al formato YOLO (solo para entrenar).

Clases: 0 etiqueta, 1 producto, 2 hueco. Usa 1 de cada 5 cuadros y separa 80/20 por
pasada: dentro de cada pasada, el primer 80 % del recorrido va a entrenamiento y el resto
a validación (no al azar, para que no haya cuadros casi idénticos en ambos lados).

Este es el único módulo del motor que lee video/verdad/.

    python -m motor.preparar_yolo --fuente video/verdad video/recorrido_realista.mp4 \
        --salida datasets/anaquel
    # varias fuentes: repetir --fuente VERDAD VIDEO
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path

import cv2

CLASES = {"etiqueta": 0, "producto": 1, "hueco": 2}


def leer_verdad(d: Path) -> list[dict]:
    cuadros = []
    for ruta in sorted(d.glob("cuadro_*.json")):
        v = json.loads(ruta.read_text(encoding="utf-8"))
        n = v.get("cuadro") or int(ruta.stem.split("_")[-1])
        v["_indice"] = v.get("indice", n - 1)
        cuadros.append(v)
    return cuadros


def cajas_yolo(v: dict, ancho: int, alto: int) -> list[str]:
    filas = []
    for o in v.get("objetos") or v.get("objects") or []:
        clase = str(o.get("clase") or o.get("class") or "").lower()
        if clase not in CLASES:
            continue
        x1, y1, x2, y2 = (float(c) for c in (o.get("caja") or o.get("bbox") or o.get("box")))
        if max(x1, y1, x2, y2) <= 1.0:  # ya normalizada
            x1, x2, y1, y2 = x1 * ancho, x2 * ancho, y1 * alto, y2 * alto
        x1, x2 = max(0.0, x1), min(float(ancho), x2)
        y1, y2 = max(0.0, y1), min(float(alto), y2)
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        filas.append(f"{CLASES[clase]} {(x1 + x2) / 2 / ancho:.6f} {(y1 + y2) / 2 / alto:.6f} "
                     f"{(x2 - x1) / ancho:.6f} {(y2 - y1) / alto:.6f}")
    return filas


def dividir(cuadros: list[dict], cada: int, frac_val: float) -> dict[int, str]:
    """indice -> 'train' | 'val', para 1 de cada `cada` cuadros."""
    por_pasada = defaultdict(list)
    for v in cuadros:
        if v["_indice"] % cada == 0:
            por_pasada[v.get("pasada", "")].append(v["_indice"])
    destino = {}
    for idx in por_pasada.values():
        idx.sort()
        corte = int(round(len(idx) * (1 - frac_val)))
        for i, k in enumerate(idx):
            destino[k] = "train" if i < corte else "val"
    return destino


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verdad por cuadro -> dataset YOLO")
    ap.add_argument("--fuente", nargs=2, action="append", metavar=("VERDAD", "VIDEO"),
                    required=True)
    ap.add_argument("--salida", default="datasets/anaquel")
    ap.add_argument("--cada", type=int, default=5)
    ap.add_argument("--val", type=float, default=0.2)
    ap.add_argument("--ancho", type=int, default=1920, help="ancho de las imágenes guardadas")
    args = ap.parse_args(argv)

    salida = Path(args.salida)
    if salida.exists():
        shutil.rmtree(salida)
    for parte in ("train", "val"):
        (salida / "images" / parte).mkdir(parents=True)
        (salida / "labels" / parte).mkdir(parents=True)

    totales = defaultdict(int)
    cajas = defaultdict(int)
    for k, (d_verdad, video) in enumerate(args.fuente):
        cuadros = leer_verdad(Path(d_verdad))
        por_indice = {v["_indice"]: v for v in cuadros}
        destino = dividir(cuadros, args.cada, args.val)
        cap = cv2.VideoCapture(video)
        i = 0
        prefijo = f"f{k}_{Path(video).stem}"
        while destino:
            ok = cap.grab()
            if not ok:
                break
            if i in destino:
                _, img = cap.retrieve()
                alto, ancho = img.shape[:2]
                v = por_indice[i]
                filas = cajas_yolo(v, v.get("ancho", ancho), v.get("alto", alto))
                if args.ancho and ancho > args.ancho:
                    f = args.ancho / ancho
                    img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
                parte = destino.pop(i)
                nombre = f"{prefijo}_{i:06d}"
                cv2.imwrite(str(salida / "images" / parte / f"{nombre}.jpg"), img,
                            [cv2.IMWRITE_JPEG_QUALITY, 92])
                (salida / "labels" / parte / f"{nombre}.txt").write_text("\n".join(filas))
                totales[parte] += 1
                for fila in filas:
                    cajas[(parte, fila.split()[0])] += 1
            i += 1
        cap.release()
        print(f"{video}: listo")

    nombres = {v: k for k, v in CLASES.items()}
    (salida / "data.yaml").write_text(
        f"path: {salida.resolve()}\ntrain: images/train\nval: images/val\nnames:\n"
        + "".join(f"  {i}: {n}\n" for i, n in sorted(nombres.items())))
    print(f"imágenes: {dict(totales)}")
    for parte in ("train", "val"):
        print(f"  cajas {parte}: " + ", ".join(
            f"{nombres[int(c)]}={cajas[(parte, c)]}" for c in ("0", "1", "2")))
    print(f"dataset: {salida / 'data.yaml'}")


if __name__ == "__main__":
    main()
