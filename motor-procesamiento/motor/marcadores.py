"""Marcadores ArUco y homografía imagen -> centímetros de la sección.

Cada marcador mide 5 cm; su id es seccion*20 + repisa*4 + k y su esquina superior
izquierda está en x = 0, 55 o 110 cm, a la altura de la superficie de su repisa. Como
todo el frente del anaquel es un plano, con un solo marcador ya hay homografía; con más
marcadores se ajusta por mínimos cuadrados y se descartan los que no cuadran.

    python -m motor.marcadores video/cuadros/000001.png
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from motor import contrato

ANCHO_DETECCION = 1920  # se detecta en una copia reducida y se refina en la original

_detector = None


def detector() -> cv2.aruco.ArucoDetector:
    global _detector
    if _detector is None:
        dic = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_100)
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        params.errorCorrectionRate = 0.3  # menos falsos positivos en empaques
        _detector = cv2.aruco.ArucoDetector(dic, params)
    return _detector


@dataclass
class Marcador:
    id: int
    esquinas: np.ndarray  # (4, 2) px: sup-izq, sup-der, inf-der, inf-izq

    @property
    def seccion_repisa_k(self):
        return contrato.decodificar_marcador(self.id)


@dataclass
class Homografia:
    px_a_cm_m: np.ndarray
    cm_a_px_m: np.ndarray
    seccion: int
    marcadores: list[Marcador]
    error_px: float

    def a_cm(self, pts) -> np.ndarray:
        pts = np.asarray(pts, np.float64).reshape(-1, 1, 2)
        return cv2.perspectiveTransform(pts, self.px_a_cm_m).reshape(-1, 2)

    def a_px(self, pts_cm) -> np.ndarray:
        pts = np.asarray(pts_cm, np.float64).reshape(-1, 1, 2)
        return cv2.perspectiveTransform(pts, self.cm_a_px_m).reshape(-1, 2)

    def rect_a_px(self, rect_cm) -> np.ndarray:
        """(x1, y1, x2, y2) en cm -> 4 esquinas en px (sup-izq, sup-der, inf-der, inf-izq)."""
        x1, y1, x2, y2 = rect_cm
        return self.a_px([[x1, y2], [x2, y2], [x2, y1], [x1, y1]])

    def px_por_cm(self, x_cm: float, y_cm: float) -> float:
        p = self.a_px([[x_cm, y_cm], [x_cm + 1, y_cm], [x_cm, y_cm + 1]])
        return float((np.linalg.norm(p[1] - p[0]) + np.linalg.norm(p[2] - p[0])) / 2)


def detectar_marcadores(imagen: np.ndarray) -> list[Marcador]:
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY) if imagen.ndim == 3 else imagen
    f = min(1.0, ANCHO_DETECCION / gris.shape[1])
    peq = cv2.resize(gris, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f < 1 else gris
    esquinas, ids, _ = detector().detectMarkers(peq)
    if ids is None:
        return []
    marcadores = []
    for c, i in zip(esquinas, ids.ravel()):
        c = c.reshape(4, 2) / f
        if f < 1:
            c = cv2.cornerSubPix(gris, c.astype(np.float32).reshape(-1, 1, 2),
                                 (max(2, int(2 / f)),) * 2, (-1, -1),
                                 (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.01)
                                 ).reshape(4, 2)
        marcadores.append(Marcador(int(i), c.astype(np.float64)))
    return marcadores


def esquinas_cm(id_: int, alturas: dict[tuple[int, int], float]) -> np.ndarray | None:
    """Esquinas del marcador en cm de la sección, en el mismo orden que ArUco."""
    seccion, repisa, k = contrato.decodificar_marcador(id_)
    if k >= len(contrato.MARCADOR_X_CM):
        return None
    h = alturas.get((seccion, repisa))
    if h is None:
        h = contrato.ALTURA_REPISA_CM.get(repisa)
        if h is None:
            return None
    x, l = contrato.MARCADOR_X_CM[k], contrato.MARCADOR_LADO_CM
    return np.array([[x, h], [x + l, h], [x + l, h - l], [x, h - l]], np.float64)


def calcular_homografia(imagen: np.ndarray,
                        alturas: dict[tuple[int, int], float] | None = None,
                        marcadores: list[Marcador] | None = None) -> Homografia | None:
    """Homografía de píxeles a cm de la sección con más marcadores en el cuadro."""
    alturas = alturas or {}
    if marcadores is None:
        marcadores = detectar_marcadores(imagen)
    validos = [(m, esquinas_cm(m.id, alturas)) for m in marcadores]
    validos = [(m, c) for m, c in validos if c is not None]
    if alturas:
        validos = [(m, c) for m, c in validos if m.seccion_repisa_k[:2] in alturas]
    if not validos:
        return None
    secciones = [m.seccion_repisa_k[0] for m, _ in validos]
    seccion = max(set(secciones), key=secciones.count)
    validos = [(m, c) for m, c in validos if m.seccion_repisa_k[0] == seccion]
    src = np.concatenate([m.esquinas for m, _ in validos])
    dst = np.concatenate([c for _, c in validos])
    if len(validos) == 1:
        H, _ = cv2.findHomography(src, dst, 0)
    else:
        H, inl = cv2.findHomography(src, dst, cv2.RANSAC, 0.6)
        if H is not None and inl is not None:
            # se descartan los marcadores con alguna esquina fuera del ajuste
            buenos = inl.ravel().reshape(-1, 4).all(axis=1)
            if buenos.any() and not buenos.all():
                validos = [v for v, b in zip(validos, buenos) if b]
                src = np.concatenate([m.esquinas for m, _ in validos])
                dst = np.concatenate([c for _, c in validos])
                H, _ = cv2.findHomography(src, dst, 0)
    if H is None:
        return None
    Hinv = np.linalg.inv(H)
    rep = cv2.perspectiveTransform(dst.reshape(-1, 1, 2), Hinv).reshape(-1, 2)
    error = float(np.sqrt(((rep - src) ** 2).sum(axis=1)).mean())
    return Homografia(H, Hinv, seccion, [m for m, _ in validos], error)


_cache: dict[int, Homografia | None] = {}


def pixel_a_cm(cuadro, x: float, y: float) -> tuple[float, float] | None:
    """Convierte un píxel del cuadro a cm de la sección.

    `cuadro` puede ser un cuadros.Cuadro (con su homografía ya calculada), una Homografia
    o la imagen; con la imagen se detectan los marcadores con las alturas del contrato.
    """
    if isinstance(cuadro, Homografia):
        h = cuadro
    elif getattr(cuadro, "homografia", None) is not None:
        h = cuadro.homografia
    else:
        img = getattr(cuadro, "imagen", cuadro)
        clave = id(img)
        if clave not in _cache:
            _cache[clave] = calcular_homografia(img)
        h = _cache[clave]
    if h is None:
        return None
    x_cm, y_cm = h.a_cm([[x, y]])[0]
    return float(x_cm), float(y_cm)


def dibujar_depuracion(imagen: np.ndarray, h: Homografia | None,
                       marcadores: list[Marcador], paso_cm: float = 10.0) -> np.ndarray:
    out = imagen.copy()
    grosor = max(2, imagen.shape[1] // 960)
    if h is not None:
        for x in np.arange(-40, 161, paso_cm):
            p = h.a_px([[x, 0], [x, 190]]).astype(int)
            cv2.line(out, tuple(p[0]), tuple(p[1]), (255, 200, 0), grosor // 2 + 1, cv2.LINE_AA)
        for y in np.arange(0, 191, paso_cm):
            p = h.a_px([[-40, y], [160, y]]).astype(int)
            cv2.line(out, tuple(p[0]), tuple(p[1]), (255, 200, 0), grosor // 2 + 1, cv2.LINE_AA)
        for x in range(0, 121, 30):
            for y in range(0, 181, 30):
                p = h.a_px([[x, y]])[0].astype(int)
                cv2.putText(out, f"{x},{y}", tuple(p + 4), cv2.FONT_HERSHEY_SIMPLEX,
                            grosor * 0.35, (255, 120, 0), grosor // 2 + 1, cv2.LINE_AA)
    for m in marcadores:
        cv2.polylines(out, [m.esquinas.astype(np.int32)], True, (0, 0, 255), grosor * 2, cv2.LINE_AA)
        s, r, k = m.seccion_repisa_k
        cv2.putText(out, f"id {m.id} S{s} R{r} k{k}", tuple(m.esquinas[0].astype(int) + [0, -10]),
                    cv2.FONT_HERSHEY_SIMPLEX, grosor * 0.5, (0, 0, 255), grosor, cv2.LINE_AA)
    if h is not None:
        cv2.putText(out, f"error de reproyeccion {h.error_px:.2f} px", (30, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, grosor * 0.7, (0, 0, 255), grosor, cv2.LINE_AA)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Detecta marcadores y dibuja la rejilla en cm")
    ap.add_argument("imagen", nargs="?", default="video/cuadros/000001.png")
    ap.add_argument("--planograma", default="datos/sistema/planograma.csv")
    ap.add_argument("--debug", default="debug")
    args = ap.parse_args(argv)
    img = cv2.imread(args.imagen)
    if img is None:
        raise SystemExit(f"no se pudo leer {args.imagen}")
    alturas = None
    if Path(args.planograma).exists():
        alturas = contrato.alturas_por_repisa(contrato.leer_planograma(args.planograma))
    marcadores = detectar_marcadores(img)
    h = calcular_homografia(img, alturas, marcadores)
    print(f"marcadores: {[m.id for m in marcadores]}")
    if h is None:
        print("sin homografía (no hay marcadores válidos)")
    else:
        print(f"sección {h.seccion}, error de reproyección {h.error_px:.2f} px, "
              f"{h.px_por_cm(60, 100):.1f} px por cm")
        cx, cy = img.shape[1] / 2, img.shape[0] / 2
        print(f"centro de la imagen -> {pixel_a_cm(h, cx, cy)} cm")
    Path(args.debug).mkdir(parents=True, exist_ok=True)
    salida = Path(args.debug) / f"marcadores_{Path(args.imagen).stem}.png"
    cv2.imwrite(str(salida), dibujar_depuracion(img, h, marcadores))
    print(f"depuración: {salida}")


if __name__ == "__main__":
    main()
