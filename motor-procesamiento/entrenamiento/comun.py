"""Entrenamiento YOLO reanudable, compartido por los dos scripts de entrenamiento."""
from __future__ import annotations

import shutil
from pathlib import Path


def entrenar(datos: str, nombre: str, epocas: int, imgsz: int, base: str, lote: int,
             destino: str, proyecto: str = "runs", **extra) -> Path:
    """Entrena (o reanuda) y copia best.pt a `destino`. Devuelve la ruta de best.pt."""
    from ultralytics import YOLO

    carpeta = Path(proyecto).resolve() / nombre
    ultimo = carpeta / "weights" / "last.pt"
    mejor = carpeta / "weights" / "best.pt"
    terminado = (carpeta / "results.csv").exists() and _epocas_hechas(carpeta) >= epocas
    if ultimo.exists() and not terminado:
        print(f"reanudando desde {ultimo}")
        try:
            YOLO(str(ultimo)).train(resume=True)
        except AssertionError as e:  # "nothing to resume": ya había terminado
            print(f"no hay nada que reanudar ({e})")
    elif not terminado:
        YOLO(base).train(data=datos, epochs=epocas, imgsz=imgsz, batch=lote,
                         project=str(carpeta.parent), name=nombre, exist_ok=True,
                         patience=0, **extra)
    else:
        print(f"{nombre} ya terminó {epocas} épocas")
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(mejor, destino)
    return mejor


def _epocas_hechas(carpeta: Path) -> int:
    lineas = (carpeta / "results.csv").read_text().strip().splitlines()
    return max(0, len(lineas) - 1)


def validar(modelo: str, datos: str, imgsz: int, lote: int = 8) -> dict:
    from ultralytics import YOLO
    m = YOLO(modelo).val(data=datos, imgsz=imgsz, batch=lote, split="val", plots=False,
                         verbose=False)
    por_clase = {m.names[i]: float(m.box.ap50[k]) for k, i in enumerate(m.box.ap_class_index)}
    return {"mAP50": float(m.box.map50), "mAP50-95": float(m.box.map), "por_clase": por_clase}
