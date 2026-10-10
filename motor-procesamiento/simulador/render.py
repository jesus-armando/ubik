"""Render del recorrido y verdad por cuadro (sustituto del render de Blender de P1).

Cámara estenopeica con los parámetros del contrato (sensor de 36 mm, focal de 21.5 mm,
80 cm del frente, 3 pasadas en serpentina a 0.3 m/s). El anaquel se arma con caras
planas texturizadas y se pinta de atrás hacia adelante. Escribe el mp4, un JSON de
verdad por cuadro y el primer cuadro en PNG.

    python -m simulador.render --escena escena/escena.json \
        --planograma datos/sistema/planograma.csv --video video/recorrido.mp4 \
        --verdad video/verdad --primer-cuadro video/cuadros/000001.png
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from motor import contrato
from simulador import graficos

ALTURA_CAMARA_CM = {1: 140.0, 2: 95.0, 3: 50.0}
X_INICIO_CM, X_FIN_CM = -40.0, 160.0
VELOCIDAD_CM_S = 30.0
DISTANCIA_CM = 80.0
FONDO_CM = 40.0
LABIO_ALTO_CM = 6.0
GROSOR_REPISA_CM = 4.0
TECHO_GONDOLA_CM = 178.0


# ----------------------------------------------------------------------------- cámara
@dataclass
class Pose:
    x: float
    z: float
    distancia: float = DISTANCIA_CM
    guinada: float = 0.0   # grados
    cabeceo: float = 0.0
    alabeo: float = 0.0
    pasada: str = ""


def rotacion(p: Pose) -> np.ndarray:
    """Filas: derecha, abajo y adelante de la cámara en coordenadas del mundo."""
    g, c, a = (math.radians(v) for v in (p.guinada, p.cabeceo, p.alabeo))
    base = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=np.float64)
    Rg = np.array([[math.cos(g), 0, -math.sin(g)], [0, 1, 0], [math.sin(g), 0, math.cos(g)]])
    Rc = np.array([[1, 0, 0], [0, math.cos(c), -math.sin(c)], [0, math.sin(c), math.cos(c)]])
    Ra = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    return Ra @ Rc @ Rg @ base


class Camara:
    def __init__(self, ancho: int, alto: int, focal_mm=21.5, sensor_mm=36.0):
        self.ancho, self.alto = ancho, alto
        self.f = focal_mm / sensor_mm * ancho

    def proyectar(self, pts: np.ndarray, pose: Pose) -> tuple[np.ndarray, np.ndarray]:
        C = np.array([pose.x, -pose.distancia, pose.z])
        pc = (pts - C) @ rotacion(pose).T
        z = pc[:, 2]
        uv = np.stack([self.ancho / 2 + self.f * pc[:, 0] / z,
                       self.alto / 2 + self.f * pc[:, 1] / z], axis=1)
        return uv, z


# ----------------------------------------------------------------------------- escena
@dataclass
class Cara:
    esquinas: np.ndarray            # (4, 3): sup-izq, sup-der, inf-der, inf-izq vistas de frente
    textura: np.ndarray | None = None
    color: tuple | None = None      # BGR
    visible_si: tuple | None = None  # (eje, valor, signo): visible si signo*(cam[eje]-valor) > 0


@dataclass
class ObjetoVerdad:
    clase: str
    caja3d: np.ndarray              # (8, 3)
    datos: dict = field(default_factory=dict)


def caja3d(x1, x2, y1, y2, z1, z2) -> np.ndarray:
    return np.array([[x, y, z] for x in (x1, x2) for y in (y1, y2) for z in (z1, z2)], float)


def rect_frontal(x1, x2, z1, z2, y) -> np.ndarray:
    return np.array([[x1, y, z2], [x2, y, z2], [x2, y, z1], [x1, y, z1]], float)


def sombrear(color, f):
    return tuple(int(max(0, min(255, c * f))) for c in color)


def textura_perforada(ancho_cm, alto_cm, ppcm=10, color=(205, 207, 210), rng=None):
    rng = rng or np.random.default_rng(0)
    w, h = int(ancho_cm * ppcm), int(alto_cm * ppcm)
    img = np.empty((h, w, 3), np.uint8)
    img[:] = color
    grad = np.linspace(1.04, 0.92, h)[:, None, None]
    img = np.clip(img * grad, 0, 255).astype(np.uint8)
    paso = int(2.5 * ppcm)
    for y in range(paso // 2, h, paso):
        for x in range(paso // 2, w, paso):
            cv2.circle(img, (x, y), max(1, ppcm // 4), sombrear(color, 0.55), -1, cv2.LINE_AA)
    ruido = rng.normal(0, 2.0, img.shape)
    return np.clip(img + ruido, 0, 255).astype(np.uint8)


class Escena:
    """Caras a pintar (en orden) y objetos de verdad, construidos desde escena.json."""

    def __init__(self, escena: dict, planograma: list[contrato.Posicion],
                 dir_empaques: Path | None = None, dir_etiquetas: Path | None = None,
                 brillo: float = 1.0, semilla: int = 0):
        rng = np.random.default_rng(semilla)
        self.brillo = brillo
        por_pos = {p["posicion"]: p for p in escena["posiciones"]}
        seccion = escena.get("seccion", 1)
        self.caras: list[tuple[int, Cara]] = []   # (capa, cara)
        self.verdad: list[ObjetoVerdad] = []
        x_min = min(p.x_ini_cm for p in planograma)
        x_max = max(p.x_fin_cm for p in planograma)
        repisas = sorted({(p.repisa, p.altura_cm) for p in planograma})

        gris_poste, gris_repisa, gris_labio = (92, 96, 102), (160, 165, 170), (176, 181, 186)
        color_piso = escena.get("_color_piso", (150, 158, 165))
        color_fondo = tuple(int(c) for c in escena.get("_color_fondo", (205, 207, 210)))

        def agregar(capa, cara):
            self.caras.append((capa, cara))

        # Piso y panel trasero
        agregar(0, Cara(np.array([[-500, 600, 0], [600, 600, 0], [600, -70, 0], [-500, -70, 0]],
                                 float), color=color_piso))
        agregar(1, Cara(rect_frontal(x_min, x_max, 0, TECHO_GONDOLA_CM, FONDO_CM),
                        textura=textura_perforada(x_max - x_min, TECHO_GONDOLA_CM,
                                                  color=color_fondo, rng=rng)))
        # Postes laterales: la cara interna va detrás de todo lo de la sección; la externa,
        # vista desde fuera, tapa todo lo de adentro.
        for xp, xe in ((x_min, x_min - 4), (x_max, x_max + 4)):
            for xc, signo, capa in ((xp, 1 if xp == x_min else -1, 2),
                                    (xe, -1 if xp == x_min else 1, 8.5)):
                agregar(capa, Cara(np.array([[xc, 0, TECHO_GONDOLA_CM],
                                             [xc, FONDO_CM, TECHO_GONDOLA_CM],
                                             [xc, FONDO_CM, 0], [xc, 0, 0]], float),
                                   color=sombrear(gris_poste, 0.8), visible_si=(0, xc, signo)))
        # Repisas: superficie, cara inferior y labio frontal
        for repisa, h in repisas:
            agregar(3, Cara(np.array([[x_min, FONDO_CM, h], [x_max, FONDO_CM, h],
                                      [x_max, 0.05, h], [x_min, 0.05, h]], float),
                            color=sombrear(gris_repisa, 1.08), visible_si=(2, h, 1)))
            zb = h - GROSOR_REPISA_CM
            agregar(3, Cara(np.array([[x_min, 0.05, zb], [x_max, 0.05, zb],
                                      [x_max, FONDO_CM, zb], [x_min, FONDO_CM, zb]], float),
                            color=sombrear(gris_repisa, 0.55), visible_si=(2, zb, -1)))
            agregar(6, Cara(rect_frontal(x_min, x_max, h - LABIO_ALTO_CM, h, 0.05),
                            color=gris_labio))

        # Productos y huecos
        cache_emp: dict[str, np.ndarray] = {}
        for p in planograma:
            e = por_pos.get(p.posicion)
            if e is None:
                continue
            n = int(e.get("frentes_fisicos", 0))
            sku = e.get("sku_fisico") or p.sku
            if n == 0:
                self.verdad.append(ObjetoVerdad("hueco", caja3d(
                    p.x_ini_cm + 1, p.x_fin_cm - 1, 1, 9, p.altura_cm, p.altura_cm + 25),
                    {"posicion": p.posicion}))
                continue
            if sku not in cache_emp:
                ruta = dir_empaques / f"{sku}.png" if dir_empaques else None
                if ruta and ruta.exists():
                    cache_emp[sku] = cv2.imread(str(ruta))
                else:
                    color = tuple(e["producto_color"]) if e.get("producto_color") else None
                    nombre = e.get("producto_nombre") or _nombre(sku)
                    cache_emp[sku] = graficos.dibujar_empaque(sku, nombre, color,
                                                              e.get("producto_forma"))
            emp = cache_emp[sku]
            base_bgr = tuple(int(c) for c in emp[500, 40])
            alto = float(e.get("alto_cm") or graficos.alto_caja_cm(sku))
            paso = float(e.get("paso_cm", 9.0))
            for i in range(n):
                x1 = p.x_ini_cm + 2 + paso * i
                x2, z1, z2 = x1 + 8, p.altura_cm, p.altura_cm + alto
                agregar(4, Cara(np.array([[x1, 9, z2], [x2, 9, z2], [x2, 1, z2], [x1, 1, z2]], float),
                                color=sombrear(base_bgr, 1.15), visible_si=(2, z2, 1)))
                agregar(4, Cara(np.array([[x1, 9, z2], [x1, 1, z2], [x1, 1, z1], [x1, 9, z1]], float),
                                color=sombrear(base_bgr, 0.7), visible_si=(0, x1, -1)))
                agregar(4, Cara(np.array([[x2, 1, z2], [x2, 9, z2], [x2, 9, z1], [x2, 1, z1]], float),
                                color=sombrear(base_bgr, 0.7), visible_si=(0, x2, 1)))
                agregar(5, Cara(rect_frontal(x1, x2, z1, z2, 1.0), textura=emp))
                self.verdad.append(ObjetoVerdad("producto", caja3d(x1, x2, 1, 9, z1, z2),
                                                {"posicion": p.posicion, "sku": sku, "frente": i}))

        # Etiquetas
        for p in planograma:
            e = por_pos.get(p.posicion, {}).get("etiqueta") or {}
            if not e.get("visible"):
                continue
            ruta = dir_etiquetas / f"{p.posicion}.png" if dir_etiquetas else None
            if ruta and ruta.exists():
                tex = cv2.imread(str(ruta))
            else:
                tex = graficos.dibujar_etiqueta(e.get("nombre", ""), float(e["precio"]), e["sku"],
                                                e.get("upc"), e.get("vigente_desde", "2026-03-01"))
            dx = float(e.get("desplazamiento_cm", 0.0))
            x1, z1, x2, z2 = p.rect_etiqueta_cm()
            agregar(7, Cara(rect_frontal(x1 + dx, x2 + dx, z1, z2, 0.0), textura=tex))
            self.verdad.append(ObjetoVerdad("etiqueta", caja3d(x1 + dx, x2 + dx, 0, 0.01, z1, z2),
                                            {"posicion": p.posicion, "sku": e["sku"],
                                             "precio": float(e["precio"])}))

        # Marcadores ArUco: cuadro negro de 5 cm con esquina sup-izq en (x_k, altura)
        borde = contrato.MARCADOR_LADO_CM * 50 / 400
        for repisa, h in repisas:
            for k, xk in enumerate(contrato.MARCADOR_X_CM):
                id_ = contrato.id_marcador(seccion, repisa, k)
                agregar(8, Cara(rect_frontal(xk - borde, xk + contrato.MARCADOR_LADO_CM + borde,
                                             h - contrato.MARCADOR_LADO_CM - borde, h + borde, -0.01),
                                textura=graficos.dibujar_marcador(id_)))
                self.verdad.append(ObjetoVerdad("marcador", caja3d(
                    xk, xk + contrato.MARCADOR_LADO_CM, 0, 0.01, h - contrato.MARCADOR_LADO_CM, h),
                    {"id": id_}))

        # Frentes de postes, zoclo y copete
        for xa, xb in ((x_min - 4, x_min), (x_max, x_max + 4)):
            agregar(9, Cara(rect_frontal(xa, xb, 0, TECHO_GONDOLA_CM + 8, 0.0), color=gris_poste))
        h_min = min(h for _, h in repisas)
        agregar(9, Cara(rect_frontal(x_min, x_max, 0, h_min - LABIO_ALTO_CM, 0.05),
                        color=sombrear(gris_poste, 0.9)))
        agregar(9, Cara(rect_frontal(x_min - 4, x_max + 4, TECHO_GONDOLA_CM,
                                     TECHO_GONDOLA_CM + 8, 0.0), color=(60, 110, 40)))
        self.caras.sort(key=lambda c: c[0])


def _nombre(sku: str) -> str:
    from simulador.datos_prueba import CATALOGO
    return CATALOGO.get(sku, (sku,))[0]


# ----------------------------------------------------------------------------- pintado
def pintar_cara(img: np.ndarray, uv: np.ndarray, textura=None, color=None):
    H, W = img.shape[:2]
    x0 = max(int(math.floor(uv[:, 0].min())), 0)
    x1 = min(int(math.ceil(uv[:, 0].max())) + 1, W)
    y0 = max(int(math.floor(uv[:, 1].min())), 0)
    y1 = min(int(math.ceil(uv[:, 1].max())) + 1, H)
    if x1 <= x0 or y1 <= y0:
        return
    w, h = x1 - x0, y1 - y0
    dst = (uv - [x0 + 0.5, y0 + 0.5]).astype(np.float32)
    mascara = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(mascara, np.round(dst * 16).astype(np.int32), 255, cv2.LINE_AA, shift=4)
    roi = img[y0:y1, x0:x1]
    if textura is None:
        capa = np.empty_like(roi)
        capa[:] = color
    else:
        tw_px = max(np.linalg.norm(dst[1] - dst[0]), np.linalg.norm(dst[2] - dst[3]))
        th_px = max(np.linalg.norm(dst[3] - dst[0]), np.linalg.norm(dst[2] - dst[1]))
        th, tw = textura.shape[:2]
        if tw > 1.5 * tw_px or th > 1.5 * th_px:  # "mipmap": reducir antes de deformar
            nw = max(2, int(min(tw, tw_px * 1.25)))
            nh = max(2, int(min(th, th_px * 1.25)))
            textura = cv2.resize(textura, (nw, nh), interpolation=cv2.INTER_AREA)
            th, tw = nh, nw
        src = np.float32([[0, 0], [tw, 0], [tw, th], [0, th]]) - 0.5
        M = cv2.getPerspectiveTransform(src, dst)
        capa = cv2.warpPerspective(textura, M, (w, h), flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_REPLICATE)
    m = mascara[..., None].astype(np.uint16)
    roi[:] = ((roi.astype(np.uint16) * (255 - m) + capa.astype(np.uint16) * m + 127) // 255
              ).astype(np.uint8)


def fondo_base(ancho, alto) -> np.ndarray:
    grad = np.linspace(215, 185, alto, dtype=np.float32)[:, None]
    img = np.repeat(np.repeat(grad, ancho, axis=1)[..., None], 3, axis=2)
    img[..., 0] *= 0.97
    return img.astype(np.uint8)


def render_cuadro(escena: Escena, cam: Camara, pose: Pose, base: np.ndarray) -> np.ndarray:
    img = base.copy()
    cpos = (pose.x, -pose.distancia, pose.z)
    for _, cara in escena.caras:
        if cara.visible_si is not None:
            eje, valor, signo = cara.visible_si
            if signo * (cpos[eje] - valor) <= 0:
                continue
        uv, z = cam.proyectar(cara.esquinas, pose)
        if (z <= 1).any():
            continue
        pintar_cara(img, uv, cara.textura, cara.color)
    if escena.brillo != 1.0:
        img = cv2.convertScaleAbs(img, alpha=escena.brillo)
    return img


def caras_visibles(caja: np.ndarray, pose: Pose) -> np.ndarray:
    """Esquinas del frente de la caja, más la tapa si la cámara la ve desde arriba.

    Las caras laterales quedan fuera: las tapa la caja vecina y harían que las cajas de
    frentes contiguos se enciman.
    """
    y_frente, y_fondo = caja[:, 1].min(), caja[:, 1].max()
    z_tapa = caja[:, 2].max()
    pts = caja[caja[:, 1] == y_frente]
    if pose.z > z_tapa and y_fondo > y_frente:
        pts = np.concatenate([pts, caja[(caja[:, 1] == y_fondo) & (caja[:, 2] == z_tapa)]])
    return pts


def verdad_cuadro(escena: Escena, cam: Camara, pose: Pose) -> list[dict]:
    objetos = []
    for ob in escena.verdad:
        uv, z = cam.proyectar(caras_visibles(ob.caja3d, pose), pose)
        if (z <= 1).any():
            continue
        x1, y1 = uv.min(axis=0)
        x2, y2 = uv.max(axis=0)
        area = (x2 - x1) * (y2 - y1)
        cx1, cy1 = max(x1, 0), max(y1, 0)
        cx2, cy2 = min(x2, cam.ancho), min(y2, cam.alto)
        if cx2 <= cx1 or cy2 <= cy1 or area <= 0:
            continue
        visible = (cx2 - cx1) * (cy2 - cy1) / area
        if visible < 0.3:
            continue
        objetos.append({"clase": ob.clase, **ob.datos,
                        "caja": [round(float(v), 1) for v in (cx1, cy1, cx2, cy2)],
                        "visible": round(float(visible), 3)})
    return objetos


# ----------------------------------------------------------------------------- recorrido
def recorrido(fps: float, repisas: list[int], pausa_s: float = 0.0,
              variacion: float = 0.0, semilla: int = 0) -> list[Pose]:
    """Poses de la cámara: pasadas en serpentina con bajadas a la misma velocidad."""
    rng = np.random.default_rng(semilla)
    paso = VELOCIDAD_CM_S / fps
    poses: list[Pose] = []
    n_pasada = int(round((X_FIN_CM - X_INICIO_CM) / paso))
    serpentina = len(repisas) > 1
    for j, r in enumerate(repisas):
        z = ALTURA_CAMARA_CM[r]
        ida = (j % 2 == 0) or not serpentina
        xs = np.linspace(X_INICIO_CM, X_FIN_CM, n_pasada + 1)
        if not ida:
            xs = xs[::-1]
        if j > 0:  # bajada vertical desde la pasada anterior
            z_prev = ALTURA_CAMARA_CM[repisas[j - 1]]
            n_baj = int(round(abs(z_prev - z) / paso))
            for t in np.linspace(0, 1, n_baj + 2)[1:-1]:
                poses.append(Pose(xs[0], z_prev + (z - z_prev) * t, pasada="bajada"))
        n_pausa = int(round(pausa_s * fps))
        poses.extend(Pose(xs[0], z, pasada=f"R{r}") for _ in range(n_pausa))
        poses.extend(Pose(float(x), z, pasada=f"R{r}") for x in xs)
        poses.extend(Pose(xs[-1], z, pasada=f"R{r}") for _ in range(n_pausa))
    if variacion > 0:
        n = len(poses)
        t = np.arange(n) / fps
        fases = rng.uniform(0, 2 * np.pi, 5)
        frec = rng.uniform(0.15, 0.6, 5)
        dist = DISTANCIA_CM + rng.uniform(-5, 5) * variacion
        for i, p in enumerate(poses):
            p.distancia = dist
            p.z += 3.0 * variacion * math.sin(2 * np.pi * frec[0] * t[i] + fases[0])
            p.guinada = 2.0 * variacion * math.sin(2 * np.pi * frec[1] * t[i] + fases[1])
            p.cabeceo = 2.0 * variacion * math.sin(2 * np.pi * frec[2] * t[i] + fases[2])
            p.alabeo = 1.5 * variacion * math.sin(2 * np.pi * frec[3] * t[i] + fases[3])
    return poses


# ----------------------------------------------------------------------------- procesos
_G: dict = {}


def _iniciar(escena, planograma, dir_emp, dir_et, brillo, semilla, ancho, alto):
    _G["escena"] = Escena(escena, planograma, dir_emp, dir_et, brillo, semilla)
    _G["cam"] = Camara(ancho, alto)
    _G["base"] = fondo_base(ancho, alto)
    cv2.setNumThreads(1)


def _trabajo(pose: Pose):
    img = render_cuadro(_G["escena"], _G["cam"], pose, _G["base"])
    return img.tobytes(), verdad_cuadro(_G["escena"], _G["cam"], pose)


def abrir_ffmpeg(ruta: Path, ancho, alto, fps, crf=18):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", f"{ancho}x{alto}", "-r", str(fps), "-i", "-", "-c:v", "libx264",
           "-preset", "fast", "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(ruta)]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def escribir_verdad(d: Path, i: int, p: Pose, objetos: list, ancho, alto, fps):
    n = i + 1
    (d / f"cuadro_{n:06d}.json").write_text(json.dumps({
        "cuadro": n, "indice": i, "tiempo_s": round(i / fps, 4), "pasada": p.pasada,
        "ancho": ancho, "alto": alto, "fps": fps,
        "camara": {"x_cm": round(p.x, 3), "z_cm": round(p.z, 3),
                   "distancia_cm": round(p.distancia, 3)},
        "objetos": objetos}, ensure_ascii=False), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render del recorrido + verdad por cuadro")
    ap.add_argument("--escena", required=True)
    ap.add_argument("--planograma", required=True)
    ap.add_argument("--video", required=True, help="mp4 de salida")
    ap.add_argument("--verdad", help="carpeta para cuadro_NNNNNN.json")
    ap.add_argument("--primer-cuadro", help="PNG del primer cuadro")
    ap.add_argument("--png", help="carpeta para guardar todos los cuadros en PNG")
    ap.add_argument("--empaques", help="carpeta con <sku>.png (si no, se dibujan)")
    ap.add_argument("--etiquetas", help="carpeta con <posicion>.png (si no, se dibujan)")
    ap.add_argument("--res", default="3840x2160")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--solo-repisa", help="R1, R2 o R3: una sola pasada")
    ap.add_argument("--pausa", type=float, default=0.0, help="segundos quieto al inicio y fin")
    ap.add_argument("--cuadros", type=int, help="renderizar solo N cuadros (prueba)")
    ap.add_argument("--variacion", type=float, default=0.0,
                    help="0 = recorrido exacto; 1 = vibración/ángulos para entrenamiento")
    ap.add_argument("--brillo", type=float, default=1.0)
    ap.add_argument("--semilla", type=int, default=0)
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--procesos", type=int, default=max(1, mp.cpu_count() - 2))
    ap.add_argument("--solo-verdad", action="store_true",
                    help="no renderizar: solo reescribir la verdad (mismos argumentos)")
    args = ap.parse_args(argv)

    ancho, alto = (int(v) for v in args.res.lower().split("x"))
    escena = json.loads(Path(args.escena).read_text(encoding="utf-8"))
    planograma = contrato.leer_planograma(args.planograma)
    repisas = sorted({p.repisa for p in planograma})
    if args.solo_repisa:
        repisas = [contrato.repisa_a_numero(args.solo_repisa)]
    poses = recorrido(args.fps, repisas, args.pausa, args.variacion, args.semilla)
    if args.cuadros:
        poses = poses[:args.cuadros]

    d_verdad = Path(args.verdad) if args.verdad else None
    if d_verdad:
        d_verdad.mkdir(parents=True, exist_ok=True)
        for viejo in d_verdad.glob("cuadro_*.json"):
            viejo.unlink()
    d_png = Path(args.png) if args.png else None
    if d_png:
        d_png.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    if args.solo_verdad:
        esc = Escena(escena, planograma, Path(args.empaques) if args.empaques else None,
                     None, args.brillo, args.semilla)
        cam = Camara(ancho, alto)
        for i, p in enumerate(poses):
            escribir_verdad(d_verdad, i, p, verdad_cuadro(esc, cam, p), ancho, alto, args.fps)
        print(f"{d_verdad}: {len(poses)} cuadros de verdad en {time.time() - t0:.0f} s")
        return
    ff = abrir_ffmpeg(Path(args.video), ancho, alto, args.fps, args.crf)
    ini = (escena, planograma, Path(args.empaques) if args.empaques else None,
           Path(args.etiquetas) if args.etiquetas else None, args.brillo, args.semilla,
           ancho, alto)
    with mp.get_context("fork").Pool(args.procesos, _iniciar, ini) as pool:
        for i, (buf, objetos) in enumerate(pool.imap(_trabajo, poses, chunksize=2)):
            ff.stdin.write(buf)
            n = i + 1
            if i == 0 and args.primer_cuadro:
                Path(args.primer_cuadro).parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(args.primer_cuadro,
                            np.frombuffer(buf, np.uint8).reshape(alto, ancho, 3))
            if d_png:
                cv2.imwrite(str(d_png / f"{n:06d}.png"),
                            np.frombuffer(buf, np.uint8).reshape(alto, ancho, 3))
            if d_verdad:
                escribir_verdad(d_verdad, i, poses[i], objetos, ancho, alto, args.fps)
            if n % 100 == 0:
                print(f"  {n}/{len(poses)} cuadros ({time.time() - t0:.0f} s)", flush=True)
    ff.stdin.close()
    ff.wait()
    print(f"{args.video}: {len(poses)} cuadros {ancho}x{alto} a {args.fps:g} fps "
          f"({len(poses) / args.fps:.1f} s) en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
