"""Qué producto es (corte H14): recortes de producto contra una galería de referencia.

Cada recorte se convierte en un vector con DINOv2 (ViT-S/14) y se compara por similitud
coseno contra las fotos de referencia de cada SKU (`<sku>.png` en la carpeta del
catálogo). Gana el vecino más cercano; por debajo del umbral es "desconocido". Agregar un
SKU es agregar su foto, sin reentrenar.

Es opcional: solo corre con `--catalogo DIR` en el pipeline. En la demo, la galería son
los empaques de P1 (escena/empaques/), que hacen las veces del catálogo del retailer.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

MEDIA = np.array([0.485, 0.456, 0.406], np.float32)
DESV = np.array([0.229, 0.224, 0.225], np.float32)
LADO = 224
# El empaque de referencia es más ancho que el frente que se ve en el anaquel; se guardan
# varias proporciones de la referencia y se toma la más parecida.
PROPORCIONES = (0.3, 0.45, 0.8)


class Identificador:
    def __init__(self, dir_catalogo: str, dispositivo: str = "cpu", umbral: float = 0.45):
        import torch
        self.torch = torch
        self.dispositivo = dispositivo
        self.umbral = umbral
        self.modelo = torch.hub.load("facebookresearch/dinov2", "dinov2_vits14",
                                     trust_repo=True, verbose=False).eval().to(dispositivo)
        rutas = sorted(Path(dir_catalogo).glob("*.png")) + sorted(Path(dir_catalogo).glob("*.jpg"))
        if not rutas:
            raise FileNotFoundError(f"catálogo vacío: {dir_catalogo}")
        imgs, self.skus = [], []
        for r in rutas:
            img = cv2.imread(str(r))
            h, w = img.shape[:2]
            for prop in PROPORCIONES:  # ancho/alto con que aparece en el anaquel
                imgs.append(cv2.resize(img, (max(8, int(h * prop)), h), interpolation=cv2.INTER_AREA))
                self.skus.append(r.stem)
        self.galeria = self.vectores(imgs)

    def _tensor(self, imgs: list[np.ndarray]):
        lote = []
        for img in imgs:
            x = cv2.resize(img, (LADO, LADO), interpolation=cv2.INTER_AREA)
            x = (cv2.cvtColor(x, cv2.COLOR_BGR2RGB).astype(np.float32) / 255 - MEDIA) / DESV
            lote.append(x.transpose(2, 0, 1))
        return self.torch.from_numpy(np.stack(lote)).to(self.dispositivo)

    def vectores(self, imgs: list[np.ndarray]) -> np.ndarray:
        salida = []
        with self.torch.inference_mode():
            for i in range(0, len(imgs), 32):
                v = self.modelo(self._tensor(imgs[i:i + 32])).float()
                salida.append(self.torch.nn.functional.normalize(v, dim=1).cpu().numpy())
        return np.concatenate(salida) if salida else np.zeros((0, 384), np.float32)

    def identificar(self, recortes: list[np.ndarray]) -> list[tuple[str | None, float]]:
        if not recortes:
            return []
        sim = self.vectores(recortes) @ self.galeria.T
        resultado = []
        for fila in sim:
            mejor = defaultdict(float)
            for sku, s in zip(self.skus, fila):
                mejor[sku] = max(mejor[sku], float(s))
            sku, s = max(mejor.items(), key=lambda kv: kv[1])
            resultado.append((sku if s >= self.umbral else None, s))
        return resultado


def votar_sku(resultados: list[tuple[str | None, float]]) -> tuple[str | None, float]:
    """SKU más repetido entre los recortes de una posición y su similitud promedio."""
    validos = [(s, v) for s, v in resultados if s]
    if not validos:
        return None, round(max((v for _, v in resultados), default=0.0), 3)
    cuenta = Counter(s for s, _ in validos)
    sku = max(cuenta, key=lambda k: (cuenta[k], sum(v for s, v in validos if s == k)))
    return sku, round(float(np.mean([v for s, v in validos if s == sku])), 3)
