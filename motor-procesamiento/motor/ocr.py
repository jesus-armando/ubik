"""OCR de etiquetas enderezadas con PaddleOCR 3.x (PP-OCRv5, sin ajustar) y votación.

De cada etiqueta se extrae el precio con  \\$?\\s?(\\d{1,4})[.,](\\d{2})  (el renglón más alto
gana) y el SKU con  SKU-\\d{6} . Por posición se juntan las lecturas de todos los cuadros y
gana la que más se repite.

    python -m motor.ocr debug/etiqueta_R1-P1.png
"""
from __future__ import annotations

import argparse
import logging
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import cv2
import numpy as np

RE_PRECIO = re.compile(r"\$?\s?(\d{1,4})[.,](\d{2})")
RE_SKU = re.compile(r"SKU\s*[-–—_.:~]?\s*([0-9OQDIL|]{6})(?![0-9])")
_A_DIGITO = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "|": "1"})


@dataclass
class Lectura:
    cuadro: int
    posicion: str
    precio: float | None = None
    conf_precio: float = 0.0
    sku: str | None = None
    conf_sku: float = 0.0
    textos: list = field(default_factory=list)  # [(texto, confianza, caja)]


def unir_renglones(textos: list[tuple[str, float, tuple]]) -> list[tuple[str, float, float]]:
    """Une cajas del mismo renglón (el detector suele partir "$24" | "99" en el punto).

    Entrada [(texto, confianza, (x1, y1, x2, y2))]; salida [(texto, confianza, alto)].
    Si al unir dos pedazos ninguno trae el separador decimal, se pone un punto.
    """
    cajas = sorted(textos, key=lambda t: t[2][0])
    usados = [False] * len(cajas)
    salida = []
    for i, (t, c, (x1, y1, x2, y2)) in enumerate(cajas):
        if usados[i]:
            continue
        usados[i] = True
        alto = y2 - y1
        for j in range(i + 1, len(cajas)):
            tj, cj, (a1, b1, a2, b2) = cajas[j]
            hj = b2 - b1
            traslape = min(y2, b2) - max(y1, b1)
            if usados[j] or traslape < 0.6 * min(alto, hj) or max(alto, hj) > 1.6 * min(alto, hj):
                continue
            if a1 - x2 > 0.8 * alto:  # demasiado lejos para ser el mismo número
                continue
            sep = "" if re.search(r"[.,]$", t) or re.match(r"^[.,]", tj) else "."
            numerico = re.fullmatch(r"\$?\s?\d{1,4}[.,]?", t) and re.fullmatch(r"[.,]?\d{2}", tj)
            t = t + (sep if numerico else " ") + tj
            t = re.sub(r"[.,]{2,}", ".", t)
            c = min(c, cj)
            x2, y1, y2 = max(x2, a2), min(y1, b1), max(y2, b2)
            alto = y2 - y1
            usados[j] = True
        salida.append((t, c, alto))
    return salida


def interpretar(textos: list[tuple[str, float, tuple]]) -> tuple:
    """[(texto, confianza, caja)] -> (precio, conf_precio, sku, conf_sku)."""
    precio, conf_p, alto_p = None, 0.0, -1.0
    sku, conf_s = None, 0.0
    for texto, conf, alto in unir_renglones(textos):
        t = texto.strip()
        m = RE_PRECIO.search(t.replace(" ", "") if "$" in t else t)
        if m and alto > alto_p:
            precio, conf_p, alto_p = float(f"{int(m.group(1))}.{m.group(2)}"), conf, alto
        ms = RE_SKU.search(t.upper().replace(" ", ""))
        if ms and conf > conf_s:
            sku, conf_s = "SKU-" + ms.group(1).translate(_A_DIGITO), conf
    return precio, conf_p, sku, conf_s


class LectorOCR:
    """Carga PaddleOCR una sola vez; `leer` acepta varias etiquetas a la vez."""

    def __init__(self, modelo: str = "mobile", dispositivo: str = "cpu", ampliar: float = 1.0):
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        logging.getLogger("ppocr").setLevel(logging.ERROR)
        from paddleocr import PaddleOCR
        self.ampliar = ampliar

        def crear(mkldnn: bool):
            return PaddleOCR(
                text_detection_model_name=f"PP-OCRv5_{modelo}_det",
                text_recognition_model_name=f"PP-OCRv5_{modelo}_rec",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                # la etiqueta enderezada mide 600 x 350: basta detectar texto a 480 px
                text_det_limit_side_len=int(480 * ampliar),
                text_det_limit_type="max",
                device=dispositivo,
                enable_mkldnn=mkldnn,
            )

        # oneDNN acelera ~2.5x en CPU, pero paddle 3.3 falla con él
        # (ConvertPirAttribute2RuntimeAttribute): si falla, se recarga sin oneDNN.
        prueba = np.full((350, 600, 3), 255, np.uint8)
        cv2.putText(prueba, "$1.23", (40, 200), cv2.FONT_HERSHEY_SIMPLEX, 4, (0, 0, 0), 8)
        try:
            self.ocr = crear(dispositivo == "cpu")
            list(self.ocr.predict([prueba]))
        except (NotImplementedError, RuntimeError):
            self.ocr = crear(False)
            list(self.ocr.predict([prueba]))

    def textos(self, imagenes: list[np.ndarray],
               limite: int | None = None) -> list[list[tuple[str, float, tuple]]]:
        """`limite`: lado mayor para detectar texto (por omisión, 480 × ampliar)."""
        if not imagenes:
            return []
        if self.ampliar != 1.0:
            imagenes = [cv2.resize(i, None, fx=self.ampliar, fy=self.ampliar,
                                   interpolation=cv2.INTER_CUBIC) for i in imagenes]
        salida = []
        extra = {"text_det_limit_side_len": int(limite * self.ampliar)} if limite else {}
        for res in self.ocr.predict(imagenes, **extra):
            r = res.json.get("res", res) if hasattr(res, "json") else res
            textos = r.get("rec_texts", []) or []
            confs = r.get("rec_scores", []) or []
            polys = r.get("rec_polys", None)
            if polys is None:
                polys = r.get("dt_polys", [])
            lineas = []
            for i, (t, c) in enumerate(zip(textos, confs)):
                if not str(t).strip() or i >= len(polys):
                    continue
                p = np.asarray(polys[i], float).reshape(-1, 2) / self.ampliar
                caja = (float(p[:, 0].min()), float(p[:, 1].min()),
                        float(p[:, 0].max()), float(p[:, 1].max()))
                lineas.append((str(t), float(c), caja))
            salida.append(lineas)
        return salida

    def leer(self, etiquetas) -> list[Lectura]:
        """etiquetas: objetos con .imagen, .cuadro y .posicion (etiquetas.EtiquetaDetectada)."""
        lecturas = []
        for e, lineas in zip(etiquetas, self.textos([e.imagen for e in etiquetas])):
            precio, cp, sku, cs = interpretar(lineas)
            lecturas.append(Lectura(e.cuadro, e.posicion, precio, cp, sku, cs, lineas))
        return lecturas


@dataclass
class Voto:
    precio: float | None
    confianza: float
    coinciden: int
    sku: str | None
    cuadro: int | None          # cuadro de la mejor lectura del precio ganador
    lecturas: int               # lecturas con algún precio


def votar(lecturas: list[Lectura]) -> Voto:
    con_precio = [l for l in lecturas if l.precio is not None]
    precio, conf, coinciden, cuadro = None, 0.0, 0, None
    if con_precio:
        grupos: dict[float, list[Lectura]] = defaultdict(list)
        for l in con_precio:
            grupos[round(l.precio, 2)].append(l)
        precio, grupo = max(grupos.items(),
                            key=lambda kv: (len(kv[1]), sum(l.conf_precio for l in kv[1])))
        coinciden = len(grupo)
        conf = float(np.mean([l.conf_precio for l in grupo]))
        cuadro = max(grupo, key=lambda l: l.conf_precio).cuadro
    skus = Counter(l.sku for l in lecturas if l.sku)
    sku = None
    if skus:
        sku = max(skus, key=lambda s: (skus[s], sum(l.conf_sku for l in lecturas if l.sku == s)))
    return Voto(precio, conf, coinciden, sku, cuadro, len(con_precio))


def main(argv=None):
    ap = argparse.ArgumentParser(description="OCR de una o varias etiquetas enderezadas")
    ap.add_argument("imagenes", nargs="+")
    ap.add_argument("--modelo", default="mobile", choices=["server", "mobile"])
    ap.add_argument("--ampliar", type=float, default=1.0)
    args = ap.parse_args(argv)
    lector = LectorOCR(args.modelo, ampliar=args.ampliar)
    imgs = [cv2.imread(r) for r in args.imagenes]
    for ruta, lineas in zip(args.imagenes, lector.textos(imgs)):
        print(ruta, interpretar(lineas))
        for t in lineas:
            print("   ", t)


if __name__ == "__main__":
    main()
