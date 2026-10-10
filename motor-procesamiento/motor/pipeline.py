"""Motor de procesamiento: video del anaquel -> salida/observaciones.json.

    python -m motor.pipeline --video video/recorrido_realista.mp4 \
        --planograma datos/sistema/planograma.csv --salida salida/

Pasos: cuadros nítidos -> marcadores y homografía -> etiquetas -> YOLO (productos y
huecos) -> OCR y votación -> huecos y frentes -> recortes, video anotado y JSON.
Si una posición falla, sale con confianza_precio 0 y las demás siguen.

Regla de oro: el motor no lee escena/ ni video/verdad/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import heapq
import itertools
import shutil

import cv2
import numpy as np

from motor import anotar, contrato, cuadros, etiquetas, frentes, huecos, marcadores, ocr

log = logging.getLogger("motor")

MODELO_DEFECTO = "modelos/anaquel.pt"
_orden = itertools.count()  # desempate en los montículos de recortes


def _dispositivo(valor: str) -> str:
    if valor != "auto":
        return valor
    try:
        import torch
        return "cuda:0" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


class Tiempos:
    def __init__(self):
        self.t = defaultdict(float)

    def medir(self, etapa):
        tiempos = self

        class _M:
            def __enter__(self):
                self.t0 = time.perf_counter()

            def __exit__(self, *a):
                tiempos.t[etapa] += time.perf_counter() - self.t0
        return _M()


class Progreso:
    """Escribe {"paso", "porcentaje"} en un JSON para el GET /estado de la API de P4."""

    def __init__(self, ruta: str | None):
        self.ruta = Path(ruta) if ruta else None
        self.ultimo = 0.0

    def __call__(self, paso: str, porcentaje: float, forzar: bool = False):
        if self.ruta is None or (not forzar and time.perf_counter() - self.ultimo < 0.5):
            return
        self.ultimo = time.perf_counter()
        tmp = self.ruta.with_name(f".{self.ruta.name}.{os.getpid()}.tmp")
        try:
            tmp.write_text(json.dumps({"paso": paso, "porcentaje": round(porcentaje)},
                                      ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.ruta)  # atómico: quien lee nunca ve el archivo a medias
        except OSError as e:  # el progreso nunca debe tumbar el proceso
            log.warning("no se pudo escribir el progreso: %s", e)


def entrada_vacia(pos: str) -> dict:
    return {"posicion": pos, "etiqueta_visible": False, "sku_leido": None, "precio_leido": None,
            "confianza_precio": 0, "lecturas_coinciden": 0, "hueco": False,
            "frentes_vistos": 0, "cuadro": None, "recorte_etiqueta": None,
            "recorte_posicion": None}


def procesar(video: str, ruta_planograma: str, salida: str, modelo: str | None = MODELO_DEFECTO,
             cada: int = 12, dispositivo: str = "auto", imgsz: int = 960,
             confianza: float = 0.35, ocr_modelo: str = "mobile", ampliar: float = 1.0,
             geometria: bool = False, max_lecturas: int = 8, con_video: bool = True,
             catalogo: str | None = None, progreso: str | None = None) -> dict:
    t_inicio = time.perf_counter()
    avisar = Progreso(progreso)
    avisar("eligiendo cuadros", 0, forzar=True)
    tiempos = Tiempos()
    plan = contrato.leer_planograma(ruta_planograma)
    alturas = contrato.alturas_por_repisa(plan)
    info = cuadros.info_video(video)
    d_salida = Path(salida)
    d_recortes = d_salida / "recortes"
    if d_recortes.exists():  # que no queden recortes de otra corrida
        shutil.rmtree(d_recortes)
    d_recortes.mkdir(parents=True)
    dispositivo = _dispositivo(dispositivo)

    # Los modelos se cargan mientras empieza la decodificación.
    pool = ThreadPoolExecutor(3)
    f_ocr = pool.submit(ocr.LectorOCR, ocr_modelo, "cpu", ampliar)
    f_ident = None
    if catalogo:  # corte H14: qué producto hay en cada posición
        from motor import identificar
        f_ident = pool.submit(identificar.Identificador, catalogo, dispositivo)
    f_yolo = None
    if modelo and Path(modelo).exists():
        f_yolo = pool.submit(huecos.DetectorAnaquel, modelo, imgsz, confianza, dispositivo)
    else:
        log.warning("sin modelo YOLO (%s): no se pueden medir huecos ni frentes", modelo)

    homografias: dict[int, np.ndarray] = {}
    detectadas: list[etiquetas.EtiquetaDetectada] = []
    oportunidades = defaultdict(int)
    vistas = defaultdict(list)
    recorte_pos: dict[str, tuple[float, np.ndarray, int]] = {}
    recortes_prod: dict[str, list] = defaultdict(list)  # montículo (-distancia, n, recorte)
    sin_homografia = elegidos = 0
    detector = None

    flujo = cuadros.elegir_cuadros_en_hilo(video, cada)
    while True:
        with tiempos.medir("decodificar (espera)"):
            c = next(flujo, None)
        if c is None:
            break
        elegidos += 1
        avisar("eligiendo cuadros", 75 * c.indice / max(1, info.cuadros))
        try:
            with tiempos.medir("marcadores"):
                h = marcadores.calcular_homografia(c.imagen, alturas)
            c.homografia = h
            if h is None:
                sin_homografia += 1
                continue
            homografias[c.indice] = h.cm_a_px_m
            with tiempos.medir("etiquetas"):
                detectadas.extend(etiquetas.detectar_etiquetas(
                    c.imagen, h, plan, c.indice, c.nitidez, geometria))
                for p in plan:
                    if etiquetas.etiqueta_completa_en_cuadro(p, h, info.ancho, info.alto):
                        oportunidades[p.posicion] += 1
            if f_yolo is not None:
                if detector is None:
                    with tiempos.medir("cargar modelos (espera)"):
                        detector = f_yolo.result()
                with tiempos.medir("yolo"):
                    dets = detector.detectar([c.imagen])[0]
                    huecos.asignar(dets, h, plan)
                    vs = huecos.vistas_por_posicion(c.indice, dets, h, plan, info.ancho, info.alto)
                    for pos, v in vs.items():
                        vistas[pos].append(v)
                    if f_ident is not None:
                        _guardar_recortes_producto(c, dets, vs, recortes_prod, info)
            with tiempos.medir("recortes"):
                centro = np.array([info.ancho / 2, info.alto / 2])
                for p in plan:
                    if p.seccion != h.seccion:
                        continue
                    r = p.rect_recorte_cm()
                    if huecos.fraccion_visible(r, h, info.ancho, info.alto) < 0.98:
                        continue
                    d = float(np.linalg.norm(h.a_px([[(r[0] + r[2]) / 2, (r[1] + r[3]) / 2]])[0]
                                             - centro))
                    if p.posicion not in recorte_pos or d < recorte_pos[p.posicion][0]:
                        recorte_pos[p.posicion] = (d, anotar.recortar_cm(c.imagen, h.cm_a_px_m, r),
                                                   c.indice)
        except Exception:
            log.error("falló el cuadro %d:\n%s", c.indice, traceback.format_exc())

    # OCR: como mucho `max_lecturas` etiquetas por posición, las más centradas.
    por_posicion = defaultdict(list)
    for e in detectadas:
        por_posicion[e.posicion].append(e)
    a_leer = []
    for pos, lista in por_posicion.items():
        lista.sort(key=lambda e: e.distancia_centro)
        a_leer.extend(lista[:max_lecturas])
    avisar("leyendo etiquetas", 75, forzar=True)
    with tiempos.medir("cargar modelos (espera)"):
        lector = f_ocr.result()
    with tiempos.medir("ocr"):
        lecturas = lector.leer(a_leer)
    sku_visto = {}
    if f_ident is not None:
        with tiempos.medir("identificar productos"):
            try:
                ident = f_ident.result()
                from motor import identificar
                for pos, monton in recortes_prod.items():
                    sku_visto[pos] = identificar.votar_sku(
                        ident.identificar([r for _, _, r in monton]))
            except Exception:
                log.error("falló la identificación de productos:\n%s", traceback.format_exc())
    pool.shutdown(wait=False)
    lecturas_por_pos = defaultdict(list)
    for l in lecturas:
        lecturas_por_pos[l.posicion].append(l)
    etiqueta_de = {(e.posicion, e.cuadro): e for e in a_leer}

    # Resultado por posición. Solo se reportan las posiciones que el video cubrió (su
    # etiqueta cupo completa en algún cuadro, o se detectó): en un clip de una sola repisa,
    # las otras no son "etiqueta faltante", simplemente no se vieron.
    posiciones, anotaciones, diagnostico = [], [], {}
    for p in plan:
        if not oportunidades.get(p.posicion) and not por_posicion.get(p.posicion):
            diagnostico[p.posicion] = {"no_cubierta": True}
            continue
        try:
            ent, anot, diag = _posicion(p, por_posicion.get(p.posicion, []),
                                        lecturas_por_pos.get(p.posicion, []), etiqueta_de,
                                        vistas.get(p.posicion, []), detector, recorte_pos,
                                        oportunidades.get(p.posicion, 0), d_recortes)
        except Exception:
            log.error("falló la posición %s:\n%s", p.posicion, traceback.format_exc())
            ent, anot, diag = entrada_vacia(p.posicion), anotar.AnotacionPosicion(p), {
                "error": traceback.format_exc(limit=1)}
        if f_ident is not None:  # campos extra, solo con --catalogo
            sku, sim = sku_visto.get(p.posicion, (None, 0.0))
            ent["sku_producto"] = None if ent["hueco"] else sku
            ent["similitud_producto"] = None if ent["hueco"] else sim
        posiciones.append(ent)
        anotaciones.append(anot)
        diagnostico[p.posicion] = diag

    if con_video:
        avisar("generando video anotado", 90, forzar=True)
        with tiempos.medir("video anotado"):
            try:
                anotar.escribir_video(video, str(d_salida / "recorrido_anotado.mp4"), info.ancho,
                                      info.alto, info.fps, homografias, anotaciones)
            except Exception:
                log.error("falló el video anotado:\n%s", traceback.format_exc())

    resultado = {"video": Path(video).name,
                 "segundos_proceso": round(time.perf_counter() - t_inicio, 1),
                 "posiciones": posiciones}
    (d_salida / "observaciones.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    (d_salida / "diagnostico.json").write_text(json.dumps({
        "video": {"ruta": video, "cuadros": info.cuadros, "fps": info.fps,
                  "resolucion": [info.ancho, info.alto]},
        "cuadros_elegidos": elegidos, "cuadros_sin_homografia": sin_homografia,
        "etiquetas_detectadas": len(detectadas), "etiquetas_leidas": len(a_leer),
        "dispositivo_yolo": dispositivo if detector else None,
        "tiempos_s": {k: round(v, 2) for k, v in tiempos.t.items()},
        "posiciones": diagnostico}, ensure_ascii=False, indent=1), encoding="utf-8")
    avisar("listo", 100, forzar=True)
    return resultado


def _guardar_recortes_producto(c, dets, vistas, recortes_prod, info, maximo=9):
    """Guarda los recortes de producto más centrados de cada posición (máx. `maximo`)."""
    centro = np.array([info.ancho / 2, info.alto / 2])
    for d in dets:
        v = vistas.get(d.posicion) if d.clase == "producto" else None
        if v is None or v.visible < 0.98:
            continue
        x1, y1, x2, y2 = (int(round(t)) for t in d.caja)
        recorte = c.imagen[max(0, y1):y2, max(0, x1):x2]
        if recorte.size == 0:
            continue
        f = 224 / max(recorte.shape[:2])
        if f < 1:
            recorte = cv2.resize(recorte, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        dist = float(np.linalg.norm(np.array([(x1 + x2) / 2, (y1 + y2) / 2]) - centro))
        monton = recortes_prod[d.posicion]
        item = (-dist, next(_orden), recorte)
        if len(monton) < maximo:
            heapq.heappush(monton, item)
        elif item[0] > monton[0][0]:
            heapq.heapreplace(monton, item)


def _posicion(p, detecciones, lecturas, etiqueta_de, vistas, detector, recorte_pos,
              oportunidades, d_recortes):
    ent = entrada_vacia(p.posicion)
    anot = anotar.AnotacionPosicion(p)
    voto = ocr.votar(lecturas)
    color = [e for e in detecciones if e.metodo == "color"]
    # Visible: hubo lectura, o el borde naranja apareció en 2+ cuadros aunque no se leyera.
    ent["etiqueta_visible"] = bool(voto.lecturas > 0 or voto.sku is not None or len(color) >= 2)
    if ent["etiqueta_visible"]:
        ent["sku_leido"] = voto.sku
        ent["precio_leido"] = voto.precio
        ent["confianza_precio"] = round(voto.confianza, 3) if voto.precio is not None else 0
        ent["lecturas_coinciden"] = voto.coinciden
        mejor = etiqueta_de.get((p.posicion, voto.cuadro)) if voto.cuadro is not None else None
        mejor = mejor or min(detecciones, key=lambda e: e.distancia_centro)
        ruta = d_recortes / f"{p.posicion}_etiqueta.jpg"
        cv2.imwrite(str(ruta), mejor.imagen, [cv2.IMWRITE_JPEG_QUALITY, 92])
        ent["recorte_etiqueta"] = f"recortes/{ruta.name}"
        ent["cuadro"] = int(mejor.cuadro)
        anot.etiqueta_cm = np.mean([e.esquinas_cm for e in detecciones], axis=0)
        anot.texto_etiqueta = (f"${voto.precio:.2f}" if voto.precio is not None else "?") + (
            f" {voto.sku}" if voto.sku else "")

    if detector is not None and huecos.elegir_vistas(vistas):
        hueco, vacios, contados = huecos.es_hueco(vistas)
        n_frentes = 0 if hueco else frentes.contar_frentes(vistas)
        ent["hueco"] = bool(hueco)
        ent["frentes_vistos"] = int(n_frentes)
        rep = frentes.vista_representativa(vistas, n_frentes)
        anot.hueco, anot.frentes = hueco, n_frentes
        if rep is not None:
            anot.productos_cm = [] if hueco else rep.cajas_cm
            if ent["cuadro"] is None:
                ent["cuadro"] = int(rep.cuadro)
    else:  # sin modelo, o la zona de producto nunca se vio: no se sabe
        ent["frentes_vistos"] = None
        vacios = contados = 0

    if p.posicion in recorte_pos:
        _, img, indice = recorte_pos[p.posicion]
        ruta = d_recortes / f"{p.posicion}.jpg"
        cv2.imwrite(str(ruta), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        ent["recorte_posicion"] = f"recortes/{ruta.name}"
        if ent["cuadro"] is None:
            ent["cuadro"] = int(indice)

    diag = {"etiquetas_detectadas": len(detecciones), "por_color": len(color),
            "oportunidades": oportunidades,
            "lecturas": [{"cuadro": l.cuadro, "precio": l.precio,
                          "conf": round(l.conf_precio, 3), "sku": l.sku,
                          "textos": [t[0] for t in l.textos]} for l in lecturas],
            "votos_hueco": [vacios, contados],
            "conteos_frentes": [v.productos for v in huecos.elegir_vistas(vistas)]}
    return ent, anot, diag


def huella(video: str, args: argparse.Namespace) -> str:
    """Huella del video (tamaño + primeros 16 MB) y de los parámetros que cambian el resultado."""
    h = hashlib.sha1()
    with open(video, "rb") as f:
        h.update(f.read(16 << 20))
    h.update(str(os.path.getsize(video)).encode())
    for clave in ("planograma", "modelo", "cada", "imgsz", "confianza", "ocr_modelo", "ampliar",
                  "geometria", "max_lecturas", "sin_video", "catalogo"):
        h.update(f"{clave}={getattr(args, clave)}".encode())
    with open(args.planograma, "rb") as f:
        h.update(f.read())
    return h.hexdigest()[:16]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Video del anaquel -> observaciones.json")
    ap.add_argument("--video", required=True)
    ap.add_argument("--planograma", required=True)
    ap.add_argument("--salida", default="salida/")
    ap.add_argument("--modelo", default=MODELO_DEFECTO, help="YOLO etiqueta/producto/hueco")
    ap.add_argument("--cada", type=int, default=12, help="un cuadro nítido de cada N")
    ap.add_argument("--dispositivo", default="auto", help="auto, cpu o cuda:0 (para YOLO)")
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--confianza", type=float, default=0.35)
    ap.add_argument("--ocr-modelo", default="mobile", choices=["mobile", "server"])
    ap.add_argument("--ampliar", type=float, default=1.0, help="ampliar la etiqueta antes del OCR")
    ap.add_argument("--geometria", action="store_true",
                    help="si no se ve el borde naranja, recortar donde dice el contrato")
    ap.add_argument("--max-lecturas", type=int, default=8, help="etiquetas a leer por posición")
    ap.add_argument("--sin-video", action="store_true", help="no generar el video anotado")
    ap.add_argument("--cache", help="carpeta de caché (corte H16): si el mismo clip ya se "
                                    "procesó con los mismos parámetros, se copia el resultado")
    ap.add_argument("--progreso", help="JSON con el paso actual y el porcentaje (para la API)")
    ap.add_argument("--catalogo", help="carpeta con <sku>.png para identificar el producto "
                                       "(corte H14); agrega sku_producto y similitud_producto")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for ruidoso in ("ppocr", "paddlex", "paddle", "ultralytics"):
        logging.getLogger(ruidoso).setLevel(logging.ERROR)
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

    guardado = Path(args.cache) / huella(args.video, args) if args.cache else None
    if guardado is not None and (guardado / "observaciones.json").exists():
        shutil.copytree(guardado, args.salida, dirs_exist_ok=True)
        r = json.loads((guardado / "observaciones.json").read_text(encoding="utf-8"))
        print(f"resultado desde la caché {guardado} (proceso original: {r['segundos_proceso']} s)")
    else:
        r = procesar(args.video, args.planograma, args.salida, args.modelo, args.cada,
                     args.dispositivo, args.imgsz, args.confianza, args.ocr_modelo, args.ampliar,
                     args.geometria, args.max_lecturas, not args.sin_video, args.catalogo,
                     args.progreso)
        if guardado is not None:
            shutil.copytree(args.salida, guardado, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("metricas"))
    print(f"\n{r['video']}: {len(r['posiciones'])} posiciones en {r['segundos_proceso']} s "
          f"-> {Path(args.salida) / 'observaciones.json'}")
    for e in r["posiciones"]:
        precio = f"${e['precio_leido']:.2f}" if e["precio_leido"] is not None else "-"
        print(f"  {e['posicion']}: etiqueta={'sí' if e['etiqueta_visible'] else 'NO'} "
              f"{e['sku_leido'] or '-'} {precio} (conf {e['confianza_precio']}, "
              f"{e['lecturas_coinciden']} coinciden) hueco={'SÍ' if e['hueco'] else 'no'} "
              f"frentes={e['frentes_vistos']} cuadro={e['cuadro']}"
              + (f" producto={e['sku_producto']} ({e['similitud_producto']})"
                 if "sku_producto" in e else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
