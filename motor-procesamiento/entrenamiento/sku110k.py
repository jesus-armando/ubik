"""Módulo 0 (reemplaza el notebook de Colab): detector general de productos con SKU-110K.

YOLO nano de Ultralytics, subconjunto de 1,500 imágenes de entrenamiento, 30 épocas,
imagen de 640, una sola clase `producto`. Al final copia best.pt a modelos/sku110k.pt y
muestra el mAP50 en validación. Todo se puede reanudar: si se corta la descarga o el
entrenamiento, se vuelve a correr el mismo comando.

Fuentes:
  --fuente hf           (por defecto) espejo en parquet de Hugging Face
                        (benjamintli/sku110k): solo baja los fragmentos necesarios,
                        ~2 GB en lugar de 13.6 GB.
  --fuente ultralytics  el SKU-110K.yaml oficial de Ultralytics (baja los 13.6 GB) y
                        luego toma el subconjunto.

    python -m entrenamiento.sku110k
    python -m entrenamiento.sku110k --solo-datos      # solo descarga y convierte

SKU-110K es solo para uso académico y no comercial.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import time
from pathlib import Path

from entrenamiento.comun import entrenar, validar

REPO = "benjamintli/sku110k"
IMGS_POR_FRAGMENTO = 433  # 8,219 imágenes de entrenamiento en 19 fragmentos


def descargar(nombre: str, carpeta: Path, intentos: int = 30) -> Path:
    from huggingface_hub import hf_hub_download
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
    for i in range(1, intentos + 1):
        try:
            return Path(hf_hub_download(REPO, nombre, repo_type="dataset", local_dir=carpeta))
        except Exception as e:  # red inestable: se reintenta, la descarga se reanuda
            print(f"  {nombre}: intento {i} falló ({type(e).__name__}: {str(e)[:120]})")
            time.sleep(min(60, 5 * i))
    raise RuntimeError(f"no se pudo descargar {nombre}")


def convertir_parquet(ruta: Path, salida: Path, parte: str, limite: int, ya: int) -> int:
    """Escribe imágenes y etiquetas YOLO; devuelve cuántas lleva en total."""
    import pyarrow.parquet as pq
    from PIL import Image

    d_img, d_lab = salida / "images" / parte, salida / "labels" / parte
    d_img.mkdir(parents=True, exist_ok=True)
    d_lab.mkdir(parents=True, exist_ok=True)
    pf = pq.ParquetFile(ruta)
    for lote in pf.iter_batches(batch_size=16, columns=["image", "objects"]):
        for fila in lote.to_pylist():
            if ya >= limite:
                return ya
            nombre = Path((fila["image"] or {}).get("path") or f"{ruta.stem}_{ya:05d}.jpg").stem
            destino_img = d_img / f"{nombre}.jpg"
            datos = fila["image"]["bytes"]
            with Image.open(io.BytesIO(datos)) as im:
                ancho, alto = im.size
                if not destino_img.exists():
                    if im.format == "JPEG":
                        destino_img.write_bytes(datos)
                    else:
                        im.convert("RGB").save(destino_img, quality=92)
            cajas = fila["objects"]["bbox"]
            # El espejo usa formato COCO [x, y, ancho, alto]; si viniera en [x1, y1, x2, y2]
            # habría cajas con "ancho" mayor que lo que queda de imagen.
            xyxy = any(b[0] + b[2] > ancho * 1.02 or b[1] + b[3] > alto * 1.02 for b in cajas) \
                and all(b[2] > b[0] and b[3] > b[1] for b in cajas)
            filas = []
            for x, y, w, h in cajas:
                if xyxy:
                    w, h = w - x, h - y
                x, y = max(0.0, x), max(0.0, y)
                w, h = min(w, ancho - x), min(h, alto - y)
                if w > 1 and h > 1:
                    filas.append(f"0 {(x + w / 2) / ancho:.6f} {(y + h / 2) / alto:.6f} "
                                 f"{w / ancho:.6f} {h / alto:.6f}")
            (d_lab / f"{nombre}.txt").write_text("\n".join(filas))
            ya += 1
    return ya


def preparar_hf(carpeta: Path, n_train: int, n_val: int) -> Path:
    descargas = carpeta / "_parquet"
    marca = carpeta / "listo.json"
    if marca.exists() and json.loads(marca.read_text()) == {"train": n_train, "val": n_val}:
        print(f"datos ya preparados en {carpeta}")
        return carpeta / "data.yaml"
    n_frag = -(-n_train // IMGS_POR_FRAGMENTO)
    hechos = 0
    for k in range(n_frag):
        f = descargar(f"data/train-{k:05d}-of-00019.parquet", descargas)
        hechos = convertir_parquet(f, carpeta, "train", n_train, hechos)
        print(f"  train: {hechos}/{n_train}")
    hechos = 0
    for k in range(2):
        if hechos >= n_val:
            break
        f = descargar(f"data/validation-{k:05d}-of-00002.parquet", descargas)
        hechos = convertir_parquet(f, carpeta, "val", n_val, hechos)
        print(f"  val: {hechos}/{n_val}")
    yaml = carpeta / "data.yaml"
    yaml.write_text(f"path: {carpeta.resolve()}\ntrain: images/train\nval: images/val\n"
                    "names:\n  0: producto\n")
    marca.write_text(json.dumps({"train": n_train, "val": n_val}))
    return yaml


def preparar_ultralytics(carpeta: Path, n_train: int, n_val: int) -> Path:
    """Baja el SKU-110K.yaml oficial (13.6 GB) y arma un subconjunto con enlaces."""
    from ultralytics.data.utils import check_det_dataset
    info = check_det_dataset("SKU-110K.yaml")  # descarga y convierte si hace falta
    raiz = Path(info["path"])
    for parte, n, origen in (("train", n_train, "train"), ("val", n_val, "val")):
        d_img, d_lab = carpeta / "images" / parte, carpeta / "labels" / parte
        d_img.mkdir(parents=True, exist_ok=True)
        d_lab.mkdir(parents=True, exist_ok=True)
        for img in sorted((raiz / "images").glob(f"{origen}_*.jpg"))[:n]:
            lab = raiz / "labels" / f"{img.stem}.txt"
            for src, dst in ((img, d_img / img.name), (lab, d_lab / lab.name)):
                if src.exists() and not dst.exists():
                    dst.symlink_to(src)
    yaml = carpeta / "data.yaml"
    yaml.write_text(f"path: {carpeta.resolve()}\ntrain: images/train\nval: images/val\n"
                    "names:\n  0: producto\n")
    return yaml


def main(argv=None):
    ap = argparse.ArgumentParser(description="Detector general de productos con SKU-110K")
    ap.add_argument("--fuente", choices=["hf", "ultralytics"], default="hf")
    ap.add_argument("--datos", default="datasets/sku110k")
    ap.add_argument("--imagenes", type=int, default=1500)
    ap.add_argument("--val", type=int, default=300)
    ap.add_argument("--epocas", type=int, default=30)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--lote", type=int, default=8, help="8 cabe en una GPU de 4 GB")
    ap.add_argument("--base", default="yolo11n.pt")
    ap.add_argument("--modelo", default="modelos/sku110k.pt")
    ap.add_argument("--solo-datos", action="store_true")
    args = ap.parse_args(argv)

    carpeta = Path(args.datos)
    preparar = preparar_hf if args.fuente == "hf" else preparar_ultralytics
    yaml = preparar(carpeta, args.imagenes, args.val)
    if args.solo_datos:
        return
    entrenar(str(yaml), "sku110k", args.epocas, args.imgsz, args.base, args.lote,
             args.modelo, single_cls=True, max_det=1000, cache=False)
    m = validar(args.modelo, str(yaml), args.imgsz, args.lote)
    print(f"\nmAP50 en validación ({args.val} imágenes): {m['mAP50']:.3f} "
          f"· mAP50-95: {m['mAP50-95']:.3f}")
    print(f"modelo: {args.modelo}")
    Path(args.modelo).with_suffix(".json").write_text(json.dumps(m, indent=1))


if __name__ == "__main__":
    main()
