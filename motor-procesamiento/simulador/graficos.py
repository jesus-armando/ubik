"""Etiquetas, empaques y marcadores dibujados con Pillow / OpenCV."""
from __future__ import annotations

import colorsys
import hashlib
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from motor import contrato

FUENTES = {
    "negrita": ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "angosta": ["/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "normal": ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}


@lru_cache(maxsize=None)
def fuente(tipo: str, tam: int) -> ImageFont.FreeTypeFont:
    for ruta in FUENTES[tipo]:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, tam)
    return ImageFont.load_default(size=tam)


def tam_para_alto(tipo: str, texto_muestra: str, alto_px: int) -> int:
    """Tamaño de fuente con el que `texto_muestra` mide `alto_px` de alto."""
    tam = alto_px
    for _ in range(4):
        x0, y0, x1, y1 = fuente(tipo, tam).getbbox(texto_muestra)
        tam = max(4, round(tam * alto_px / max(1, y1 - y0)))
    return tam


def texto_ajustado(draw_img: Image.Image, xy, texto, tipo, tam, ancho_max, color,
                   alto_fijo=False):
    """Dibuja texto; si no cabe en ancho_max, lo comprime horizontalmente."""
    f = fuente(tipo, tam)
    x0, y0, x1, y1 = f.getbbox(texto)
    w, h = x1 - x0, y1 - y0
    capa = Image.new("RGBA", (w + 4, h + 4), (0, 0, 0, 0))
    ImageDraw.Draw(capa).text((2 - x0, 2 - y0), texto, font=f, fill=color)
    if w > ancho_max:
        capa = capa.resize((ancho_max + 4, capa.height), Image.LANCZOS)
    draw_img.alpha_composite(capa, (int(xy[0]) - 2, int(xy[1]) - 2))
    return capa.width - 4, h


def upc_desde_sku(sku: str) -> str:
    """UPC-A ficticio y válido (dígito verificador correcto) derivado del SKU."""
    digitos = "".join(c for c in sku if c.isdigit())[-6:].rjust(6, "0")
    base = ("0710" + digitos + "0")[:11]
    impares = sum(int(d) for d in base[0::2])
    pares = sum(int(d) for d in base[1::2])
    return base + str((10 - (impares * 3 + pares) % 10) % 10)


def modulos_upc(upc: str) -> str:
    try:
        import barcode
        return barcode.get("upca", upc[:11]).build()[0]
    except Exception:
        # Codificación UPC-A directa, por si python-barcode no está.
        izq = ["0001101", "0011001", "0010011", "0111101", "0100011",
               "0110001", "0101111", "0111011", "0110111", "0001011"]
        der = ["".join("1" if b == "0" else "0" for b in p) for p in izq]
        return ("101" + "".join(izq[int(d)] for d in upc[:6]) + "01010"
                + "".join(der[int(d)] for d in upc[6:12]) + "101")


def dibujar_etiqueta(nombre: str, precio: float, sku: str, upc: str | None = None,
                     vigente_desde: str = "2026-03-01") -> np.ndarray:
    """Etiqueta de 600 x 350 px (100 px por cm) en BGR, según la especificación de P4."""
    W, H, B = contrato.ETIQUETA_ANCHO_PX, contrato.ETIQUETA_ALTO_PX, contrato.ETIQUETA_BORDE_PX
    img = Image.new("RGBA", (W, H), contrato.COLOR_BORDE_ETIQUETA + (255,))
    d = ImageDraw.Draw(img)
    d.rectangle([B, B, W - B - 1, H - B - 1], fill=(255, 255, 255, 255))
    oscuro = (25, 25, 25, 255)
    ancho_util = W - 2 * B - 20
    # Nombre
    texto_ajustado(img, (B + 10, B + 8), nombre, "negrita", 32, ancho_util, oscuro)
    # Precio con dígitos de 120 px de alto
    tam = tam_para_alto("negrita", "0123456789", 120)
    texto_ajustado(img, (B + 10, B + 52), f"${precio:.2f}", "negrita", tam, ancho_util, oscuro)
    # SKU de 60 px (tamaño de fuente) y UPC a la derecha
    w_sku, _ = texto_ajustado(img, (B + 10, B + 190), sku, "negrita", 60, 330, oscuro)
    upc = upc or upc_desde_sku(sku)
    mods = modulos_upc(upc)
    x_bar, ancho_bar = B + 10 + w_sku + 16, W - B - 10 - (B + 10 + w_sku + 16)
    paso = ancho_bar / len(mods)
    for i, m in enumerate(mods):
        if m == "1":
            d.rectangle([x_bar + i * paso, B + 186, x_bar + (i + 1) * paso - 0.01, B + 232],
                        fill=oscuro)
    d.text((x_bar, B + 236), upc, font=fuente("normal", 16), fill=oscuro)
    # Vigencia
    d.text((B + 10, H - B - 32), f"Vigente desde {vigente_desde}", font=fuente("normal", 24),
           fill=(70, 70, 70, 255))
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def _hash(texto: str) -> int:
    return int(hashlib.md5(texto.encode()).hexdigest()[:8], 16)


# Colores RGB lejos del naranja de las etiquetas (10°–45° de tono)
PALETA = [(21, 101, 192), (46, 125, 50), (106, 27, 154), (198, 40, 40), (0, 131, 143),
          (255, 241, 118), (173, 20, 87), (55, 71, 79), (124, 179, 66), (236, 236, 236),
          (40, 53, 147), (0, 172, 193), (94, 53, 177), (233, 30, 99), (144, 164, 174),
          (0, 105, 92), (2, 119, 189), (139, 195, 74)]


def color_de_sku(sku: str) -> tuple[int, int, int]:
    return PALETA[_hash(sku) % len(PALETA)]


def color_aleatorio(rng: np.random.Generator) -> tuple[int, int, int]:
    while True:
        h = rng.uniform(0, 1)
        if not (0.02 < h < 0.13):  # fuera del naranja
            break
    s, v = rng.uniform(0.35, 0.95), rng.uniform(0.35, 0.95)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def alto_caja_cm(sku: str) -> float:
    return 20.0 + _hash("alto" + sku) % 11


def dibujar_empaque(sku: str, nombre: str, color: tuple[int, int, int] | None = None,
                    forma: int | None = None) -> np.ndarray:
    """Frente de empaque de 800 x 1000 px en BGR."""
    W, H = 800, 1000
    color = color or color_de_sku(sku)
    claro = sum(color) / 3 > 150
    tinta = (20, 20, 20) if claro else (255, 255, 255)
    img = Image.new("RGBA", (W, H), color + (255,))
    d = ImageDraw.Draw(img)
    # Franja de marca arriba y abajo
    d.rectangle([0, 0, W, 90], fill=tuple(int(c * 0.7) for c in color))
    d.text((40, 18), "GLAZED CO.", font=fuente("negrita", 52), fill=tinta)
    # Logo: forma geométrica
    forma = _hash("forma" + sku) % 6 if forma is None else forma
    cx, cy, r = W // 2, 340, 170
    acento = tuple(255 - c for c in color)
    if forma == 0:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=acento)
    elif forma == 1:
        d.polygon([(cx, cy - r), (cx + r, cy + r), (cx - r, cy + r)], fill=acento)
    elif forma == 2:
        d.rectangle([cx - r, cy - r, cx + r, cy + r], fill=acento)
    elif forma == 3:
        d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=acento)
    elif forma == 4:
        pts = [(cx + r * np.cos(a), cy + r * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 7)[:-1]]
        d.polygon(pts, fill=acento)
    else:
        pts = []
        for i in range(10):
            rr = r if i % 2 == 0 else r * 0.45
            a = -np.pi / 2 + i * np.pi / 5
            pts.append((cx + rr * np.cos(a), cy + rr * np.sin(a)))
        d.polygon(pts, fill=acento)
    # Nombre en letra grande (hasta 3 renglones)
    palabras, renglones, actual = nombre.split(), [], ""
    for p in palabras:
        prueba = (actual + " " + p).strip()
        if fuente("negrita", 96).getlength(prueba) > W - 80 and actual:
            renglones.append(actual)
            actual = p
        else:
            actual = prueba
    renglones.append(actual)
    y = 560
    for r_ in renglones[:3]:
        texto_ajustado(img, (40, y), r_, "negrita", 96, W - 80, tinta + (255,))
        y += 110
    d.rectangle([0, H - 80, W, H], fill=tuple(int(c * 0.7) for c in color))
    d.text((40, H - 66), sku, font=fuente("negrita", 48), fill=tinta)
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def dibujar_marcador(id_: int, lado_px: int = 400, borde_px: int = 50) -> np.ndarray:
    """Marcador ArUco DICT_4X4_100 con borde blanco (500 x 500 px por defecto), BGR."""
    dic = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_100)
    m = cv2.aruco.generateImageMarker(dic, id_, lado_px)
    m = cv2.copyMakeBorder(m, borde_px, borde_px, borde_px, borde_px,
                           cv2.BORDER_CONSTANT, value=255)
    return cv2.cvtColor(m, cv2.COLOR_GRAY2BGR)
