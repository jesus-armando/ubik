"""API local del motor para el tablero (sustituye a la de P4).

Corre con el Python de .venv (el mismo con el que lanza el motor):

    .venv/bin/python -m cruce.api                      # http://localhost:8000
    .venv/bin/python -m cruce.api --cache cache/       # corte H16: tarjetas ya ensayadas salen al instante

Modo jurado (frontend.pdf):
  POST /procesar {"tarjeta": "precio_viejo"}  corre el motor sobre video/tarjetas/<tarjeta>.mp4
  GET  /estado                                paso, progreso y, al final, el hallazgo nuevo: el
                                              que no estaba en el recorrido base (salida/)
  GET  /tarjetas

Videos subidos desde el tablero (pantalla "Subir video"):
  POST   /analisis?nombre=<archivo>&detector=anaquel|sku110k|libre&identificar=1&planograma=1
         El cuerpo es el video. Se guarda en analisis/<id>/, se corre el motor completo (con
         video anotado) y el cruce, y al terminar queda como el análisis activo. "libre" es el
         modo sin estructura (motor/libre.py + cruce/libre.py): sin marcadores ni planograma.
         Con planograma=1 (solo con libre) las etiquetas se acomodan en el planograma de la demo
         por el orden del recorrido y se cruzan con su sistema en pesos (cruce/orden.py).
  GET    /analisis                lista (la más nueva primero), cuál está activa y si el motor
                                  está ocupado
  GET    /analisis/<id>           estado, paso y progreso
  GET    /analisis/activo         hallazgos.json del análisis activo (404: el tablero usa el demo)
  GET    /analisis/activo/red     red.json del análisis activo (cruce/red.py; 404 igual)
  POST   /analisis/<id>/activar   lo muestra en el tablero ("demo" regresa al recorrido de demo)
  DELETE /analisis/<id>

Asistente (cruce/chat.py, RAG con Gemini; clave APIGEMINI en el .env de la raíz):
  POST   /analisis/<id>/chat      {"pregunta", "historial": [{"rol": "usuario|asistente",
                                  "texto"}]} -> {"respuesta", "fuentes", "modelo"}; <id> = demo
                                  para el recorrido de demo
  GET    /chat                    si hay clave y qué modelos usa

Archivos (el tablero los pide por /motor/..., rewrite de next.config.ts):
  GET /archivos/tarjetas/<tarjeta>/recortes/<archivo>.jpg
  GET /archivos/analisis/<id>/recortes/<archivo>.jpg
  GET /archivos/analisis/<id>/recorrido_anotado.mp4    (con Range, para adelantar el video)

El motor corre un trabajo a la vez (jurado o análisis): el segundo recibe 409.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from cruce import chat as asistente
from cruce import hallazgos as cruce
from cruce import libre as cruce_libre
from cruce import orden as cruce_orden
from cruce import red

log = logging.getLogger("cruce.api")

# Modo jurado: paso que escribe motor.pipeline en --progreso -> número de paso del tablero
PASOS = ("Eligiendo cuadros", "Leyendo etiquetas", "Comparando con el sistema")
PASO_MOTOR = {"eligiendo cuadros": 1, "leyendo etiquetas": 2, "generando video anotado": 2,
              "listo": 3}
LIMITE_S = 120  # el tablero cae al ensayo a los 60 s; aquí se corta el proceso al doble

# Videos subidos: aquí sí se genera el video anotado
PASOS_ANALISIS = ("Eligiendo cuadros", "Leyendo etiquetas", "Generando video anotado",
                  "Comparando con el sistema")
PASO_MOTOR_ANALISIS = {"eligiendo cuadros": 1, "leyendo etiquetas": 2,
                       "generando video anotado": 3, "listo": 4}
LIMITE_ANALISIS_S = 30 * 60
DETECTORES = {  # del README: SKU-110K para clips reales, con la imagen achicada
    "anaquel": ["--modelo", "modelos/anaquel.pt"],
    "sku110k": ["--modelo", "modelos/sku110k.pt", "--imgsz", "480", "--confianza", "0.2"],
    "libre": [],  # modo sin estructura: motor/libre.py con sus valores por omisión
}
EXTENSIONES = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
MAX_BYTES = 4 << 30
MAX_BYTES_CHAT = 256 << 10
DISCLAIMER_SUBIDO = "Video subido · Datos de sistema sintéticos de Glazed Co."

RECORTE = re.compile(r"^/archivos/(tarjetas|analisis)/([\w-]+)/recortes/([\w.-]+\.jpg)$")
VIDEO = re.compile(r"^/archivos/analisis/([\w-]+)/recorrido_anotado\.mp4$")
ID = re.compile(r"^[\w-]+$")


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _escribir_json(ruta: Path, datos: dict):
    tmp = ruta.with_name(f".{ruta.name}.tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ruta)  # atómico: quien lee nunca ve el archivo a medias


def _leer_json(ruta: Path) -> dict | None:
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class Motor:
    """Corre motor.pipeline en otro proceso, un trabajo a la vez."""

    def __init__(self, raiz: Path):
        self.raiz = raiz
        self._ocupado = threading.Lock()

    def tomar(self) -> bool:
        return self._ocupado.acquire(blocking=False)

    def soltar(self):
        self._ocupado.release()

    @property
    def ocupado(self) -> bool:
        return self._ocupado.locked()

    def correr(self, args: list[str], bitacora: Path, limite: float,
               modulo: str = "motor.pipeline"):
        cmd = [sys.executable, "-m", modulo, *args]
        log.info("%s", " ".join(cmd))
        with open(bitacora, "w", encoding="utf-8") as f:
            r = subprocess.run(cmd, cwd=self.raiz, stdout=f, stderr=subprocess.STDOUT,
                               timeout=limite)
        if r.returncode != 0:
            raise RuntimeError(f"el motor terminó con código {r.returncode} (ver {bitacora})")


def _avance(ruta: Path | None, pasos: tuple[str, ...], mapa: dict[str, int]) -> dict | None:
    """Paso y porcentaje que escribió el motor en --progreso, en términos del tablero."""
    p = _leer_json(ruta) if ruta else None
    if not p:
        return None
    n = mapa.get(p.get("paso"), 1)
    return {"paso": pasos[n - 1], "pasoNumero": n,
            "progreso": max(2, min(95, round(0.9 * p.get("porcentaje", 0))))}


class Trabajos:
    """Modo jurado: estado de la única tarjeta en curso (o de la última que terminó)."""

    def __init__(self, cfg: argparse.Namespace, motor: Motor):
        self.cfg = cfg
        self.motor = motor
        self.raiz = motor.raiz
        self.lock = threading.Lock()
        self.estado: dict = {"status": "inactivo"}
        self.progreso: Path | None = None

    def tarjetas(self) -> list[str]:
        return sorted(p.stem for p in (self.raiz / self.cfg.tarjetas).glob("*.mp4"))

    def carpeta(self, tarjeta: str) -> Path:
        return self.raiz / self.cfg.salida / tarjeta

    def iniciar(self, tarjeta: str) -> tuple[HTTPStatus, dict]:
        if tarjeta not in self.tarjetas():
            return HTTPStatus.NOT_FOUND, {"error": f"no hay video para la tarjeta {tarjeta!r}",
                                          "tarjetas": self.tarjetas()}
        if not self.motor.tomar():
            return HTTPStatus.CONFLICT, {"error": "el motor está ocupado con otro video"}
        with self.lock:
            # fuera de la carpeta de salida para que no entre en la caché del motor
            self.progreso = self.raiz / self.cfg.salida / f"{tarjeta}.progreso.json"
            self.carpeta(tarjeta).mkdir(parents=True, exist_ok=True)
            self.progreso.unlink(missing_ok=True)
            self.estado = {"status": "procesando", "completado": False, "tarjeta": tarjeta,
                           "paso": PASOS[0], "pasoNumero": 1, "progreso": 2,
                           "inicio": time.time()}
        threading.Thread(target=self._correr, args=(tarjeta,), daemon=True).start()
        return HTTPStatus.ACCEPTED, self.consultar()

    def consultar(self) -> dict:
        with self.lock:
            e = dict(self.estado)
            progreso = self.progreso
        if e.get("status") == "procesando" and e.get("pasoNumero", 1) < 3:
            e.update(_avance(progreso, PASOS, PASO_MOTOR) or {})
        inicio = e.pop("inicio", None)
        if inicio and e.get("status") == "procesando":
            e["segundos"] = round(time.time() - inicio, 1)
        return e

    def _terminar(self, **cambios):
        with self.lock:
            self.estado.update(cambios)

    def _correr(self, tarjeta: str):
        cfg, salida = self.cfg, self.carpeta(tarjeta)
        args = ["--video", str(self.raiz / cfg.tarjetas / f"{tarjeta}.mp4"),
                "--planograma", str(self.raiz / cfg.sistema / "planograma.csv"),
                "--salida", str(salida), "--progreso", str(self.progreso), "--sin-video"]
        if cfg.cache:
            args += ["--cache", str(self.raiz / cfg.cache)]
        try:
            self.motor.correr(args, self.raiz / cfg.salida / f"{tarjeta}.log", LIMITE_S)
            self._terminar(paso=PASOS[2], pasoNumero=3, progreso=95)
            sistema = cruce.leer_sistema(self.raiz / cfg.sistema)
            base = cruce.desde_carpeta(self.raiz / cfg.base, sistema)
            prefijo = f"{cfg.prefijo_web.rstrip('/')}/archivos/tarjetas/{tarjeta}"
            resultado = cruce.desde_carpeta(salida, sistema, prefijo)
            nuevos = cruce.nuevos(base, resultado)
            with self.lock:
                segundos = round(time.time() - self.estado.get("inicio", time.time()), 1)
            self._terminar(
                status="completado", completado=True, paso="Completado", pasoNumero=4,
                segundos=segundos, progreso=100,
                hallazgo_nuevo=nuevos[0] if nuevos else None, hallazgos_nuevos=nuevos,
                segundos_proceso=resultado["resumen"]["segundos_proceso"],
                mensaje=("Hallazgo nuevo detectado por el motor" if nuevos else
                         "El motor no encontró hallazgos nuevos en este clip"))
            log.info("%s: %d hallazgo(s) nuevo(s)", tarjeta, len(nuevos))
        except Exception as e:  # el tablero cae al resultado de ensayo
            log.exception("%s: falló", tarjeta)
            self._terminar(status="error", completado=False, mensaje=str(e))
        finally:
            self.motor.soltar()


class Analisis:
    """Videos subidos desde el tablero: analisis/<id>/{video.*, salida/, hallazgos.json, meta.json}."""

    def __init__(self, cfg: argparse.Namespace, motor: Motor):
        self.cfg = cfg
        self.motor = motor
        self.raiz = motor.raiz
        self.dir = self.raiz / cfg.analisis
        self.dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        for meta in self.listar():  # corridas que cortó un reinicio de la API
            if meta.get("status") == "procesando":
                self._actualizar(meta["id"], status="error",
                                 mensaje="Se interrumpió: la API se reinició a media corrida")

    # -------------------------------------------------------------- consulta
    def carpeta(self, id_: str) -> Path | None:
        d = self.dir / id_
        return d if ID.match(id_) and (d / "meta.json").exists() else None

    def meta(self, id_: str) -> dict | None:
        d = self.carpeta(id_)
        return _leer_json(d / "meta.json") if d else None

    def listar(self) -> list[dict]:
        metas = [m for m in (_leer_json(p) for p in self.dir.glob("*/meta.json")) if m]
        return sorted(metas, key=lambda m: m.get("creado", ""), reverse=True)

    def activo(self) -> str | None:
        id_ = (_leer_json(self.dir / "activo.json") or {}).get("id")
        m = self.meta(id_) if id_ else None
        return id_ if m and m.get("status") == "completado" else None

    def activar(self, id_: str | None) -> tuple[HTTPStatus, dict]:
        if id_ is not None:
            m = self.meta(id_)
            if m is None:
                return HTTPStatus.NOT_FOUND, {"error": f"no existe el análisis {id_!r}"}
            if m.get("status") != "completado":
                return HTTPStatus.CONFLICT, {"error": "el análisis no ha terminado bien"}
        _escribir_json(self.dir / "activo.json", {"id": id_})
        return HTTPStatus.OK, {"activo": id_}

    def hallazgos(self, id_: str) -> dict | None:
        d = self.carpeta(id_)
        return _leer_json(d / "hallazgos.json") if d else None

    def consultar(self, id_: str) -> dict | None:
        m = self.meta(id_)
        if m is None:
            return None
        if m.get("status") == "procesando":
            if m.get("pasoNumero", 1) < 4:
                m.update(_avance(self.dir / id_ / "progreso.json", PASOS_ANALISIS,
                                 PASO_MOTOR_ANALISIS) or {})
            m["segundos"] = round(time.time() - m.get("inicio", time.time()), 1)
        m["activo"] = self.activo() == id_
        return m

    def _actualizar(self, id_: str, **cambios) -> dict:
        with self.lock:
            ruta = self.dir / id_ / "meta.json"
            m = _leer_json(ruta) or {"id": id_}
            m.update(cambios)
            _escribir_json(ruta, m)
            return m

    # -------------------------------------------------------------- alta
    def crear(self, nombre: str, detector: str, identificar: bool, cuerpo,
              largo: int | None, planograma: bool = False) -> tuple[HTTPStatus, dict]:
        """Guarda el video que viene en `cuerpo` (iterable de bytes) y arranca el motor."""
        ext = Path(nombre).suffix.lower()
        if detector not in DETECTORES:
            return HTTPStatus.BAD_REQUEST, {"error": f"detector desconocido: {detector!r}"}
        if ext not in EXTENSIONES:
            return HTTPStatus.BAD_REQUEST, {
                "error": f"formato no soportado ({ext or 'sin extensión'}); usa "
                         + ", ".join(sorted(EXTENSIONES))}
        if largo is not None and not 0 < largo <= MAX_BYTES:
            return HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "el video pesa más de 4 GB"}

        id_ = f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
        d = self.dir / id_
        d.mkdir(parents=True)
        video = d / f"video{ext}"
        try:
            escritos = 0
            with open(video, "wb") as f:
                for trozo in cuerpo:
                    escritos += len(trozo)
                    if escritos > MAX_BYTES:
                        raise ValueError("el video pesa más de 4 GB")
                    f.write(trozo)
            if largo is not None and escritos != largo:
                raise ValueError("la subida se cortó antes de terminar")
            from motor.cuadros import info_video  # importa OpenCV solo al subir
            info = info_video(str(video))
            if info.cuadros <= 0 or info.ancho <= 0:
                raise ValueError("OpenCV no pudo leer cuadros de este archivo")
        except (ValueError, OSError) as e:
            shutil.rmtree(d, ignore_errors=True)
            return HTTPStatus.BAD_REQUEST, {"error": f"no es un video válido: {e}"}

        if not self.motor.tomar():
            shutil.rmtree(d, ignore_errors=True)
            return HTTPStatus.CONFLICT, {"error": "el motor está ocupado con otro video; espera "
                                                  "a que termine"}
        try:
            meta = self._actualizar(
                id_, id=id_, nombre=Path(nombre).name, creado=_ahora(), detector=detector,
                identificar=identificar, planograma=planograma and detector == "libre",
                status="procesando", paso=PASOS_ANALISIS[0],
                pasoNumero=1, progreso=2, inicio=time.time(), bytes=escritos,
                video={"fps": round(info.fps, 2), "cuadros": info.cuadros, "ancho": info.ancho,
                       "alto": info.alto, "segundos": round(info.cuadros / (info.fps or 30), 1)})
            threading.Thread(target=self._correr, args=(id_, video), daemon=True).start()
        except Exception:
            self.motor.soltar()
            raise
        log.info("análisis %s: %s (%d bytes)", id_, nombre, escritos)
        return HTTPStatus.ACCEPTED, meta

    def _correr(self, id_: str, video: Path):
        cfg, d = self.cfg, self.dir / id_
        m = self.meta(id_) or {}
        libre = m.get("detector") == "libre"
        args = ["--video", str(video), "--salida", str(d / "salida"),
                "--progreso", str(d / "progreso.json"), *DETECTORES[m.get("detector", "anaquel")]]
        if not libre or m.get("planograma"):
            args += ["--planograma", str(self.raiz / cfg.sistema / "planograma.csv")]
        if not libre:
            if m.get("identificar") and cfg.catalogo:
                args += ["--catalogo", str(self.raiz / cfg.catalogo)]
        try:
            self.motor.correr(args, d / "motor.log", LIMITE_ANALISIS_S,
                              "motor.libre" if libre else "motor.pipeline")
            self._actualizar(id_, paso=PASOS_ANALISIS[3], pasoNumero=4, progreso=96)
            prefijo = f"{cfg.prefijo_web.rstrip('/')}/archivos/analisis/{id_}"
            anotado = d / "salida/recorrido_anotado.mp4"
            video_url = f"{prefijo}/recorrido_anotado.mp4" if anotado.exists() else None
            if libre:
                obs = _leer_json(d / "salida/observaciones_libre.json") or {}
                if not obs.get("etiquetas"):
                    raise ValueError("no se encontró ninguna etiqueta de precio legible en el "
                                     "video. Acerca la cámara a las etiquetas del anaquel.")
                if m.get("planograma"):
                    datos = cruce_orden.desde_carpeta(
                        d / "salida", cruce_orden.leer_sistema(self.raiz / cfg.sistema), prefijo,
                        video_url=video_url)
                    if not datos["posiciones"]:
                        raise ValueError("ninguna etiqueta del video se pudo acomodar en el "
                                         "planograma: ¿se lee el SKU de las etiquetas?")
                else:
                    datos = cruce_libre.desde_carpeta(d / "salida", prefijo, video_url=video_url)
            else:
                obs = _leer_json(d / "salida/observaciones.json") or {}
                if not obs.get("posiciones"):
                    diag = _leer_json(d / "salida/diagnostico.json") or {}
                    raise ValueError(
                        "no se ubicó ninguna posición del anaquel "
                        f"({diag.get('cuadros_sin_homografia', '?')} de "
                        f"{diag.get('cuadros_elegidos', '?')} cuadros sin marcadores ArUco). El "
                        "video necesita los marcadores DICT_4X4_100 y las etiquetas de borde "
                        "naranja del contrato; si no los tiene, usa el modo sin estructura.")
                datos = cruce.desde_carpeta(
                    d / "salida", cruce.leer_sistema(self.raiz / cfg.sistema), prefijo,
                    video_url=video_url, disclaimer=DISCLAIMER_SUBIDO)
            datos["resumen"].update(analisis_id=id_, video=m.get("nombre"))
            _escribir_json(d / "hallazgos.json", datos)
            r = datos["resumen"]
            self._actualizar(
                id_, status="completado", paso="Completado", pasoNumero=5, progreso=100,
                terminado=_ahora(), segundos=round(time.time() - m.get("inicio", time.time()), 1),
                resumen={k: r[k] for k in ("frase", "total_problemas", "dinero_en_riesgo_diario",
                                           "precision_anaquel_pct", "segundos_proceso")},
                posiciones=len(datos["posiciones"]))
            self.activar(id_)
            log.info("análisis %s: %s", id_, r["frase"])
        except Exception as e:
            log.exception("análisis %s: falló", id_)
            self._actualizar(id_, status="error", mensaje=str(e))
        finally:
            self.motor.soltar()

    # -------------------------------------------------------------- asistente
    def preguntar(self, id_: str, datos: dict) -> tuple[HTTPStatus, dict]:
        """Pregunta sobre una corrida (cruce/chat.py); `demo` es el recorrido de demo."""
        pregunta = str(datos.get("pregunta") or "").strip()
        if not pregunta:
            return HTTPStatus.BAD_REQUEST, {"error": 'se espera {"pregunta": "...", "historial": [...]}'}
        try:
            corrida = asistente.cargar_corrida(self.raiz, id_, self.cfg.analisis, self.cfg.base,
                                               self.cfg.sistema)
            return HTTPStatus.OK, asistente.responder(
                corrida, pregunta, datos.get("historial"), asistente.configuracion(self.raiz))
        except asistente.CorridaNoDisponible as e:
            return HTTPStatus(e.status), {"error": str(e)}
        except asistente.SinClave as e:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(e)}
        except asistente.ErrorGemini as e:
            log.warning("asistente %s: %s", id_, e)
            return HTTPStatus.BAD_GATEWAY, {"error": f"Gemini no pudo responder: {e}"}

    def borrar(self, id_: str) -> tuple[HTTPStatus, dict]:
        m = self.meta(id_)
        if m is None:
            return HTTPStatus.NOT_FOUND, {"error": f"no existe el análisis {id_!r}"}
        if m.get("status") == "procesando":
            return HTTPStatus.CONFLICT, {"error": "no se puede borrar mientras se procesa"}
        if self.activo() == id_:
            self.activar(None)
        shutil.rmtree(self.dir / id_, ignore_errors=True)
        return HTTPStatus.OK, {"borrado": id_}


class Manejador(BaseHTTPRequestHandler):
    trabajos: Trabajos
    analisis: Analisis

    def _json(self, status: HTTPStatus, datos: dict | list):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _archivo(self, ruta: Path, tipo: str):
        """Sirve un archivo; con Range responde 206 (el <video> lo pide así para adelantar)."""
        tam = ruta.stat().st_size
        ini, fin, status = 0, tam - 1, HTTPStatus.OK
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", (self.headers.get("Range") or "").strip())
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                ini = int(m.group(1))
                fin = min(int(m.group(2)), tam - 1) if m.group(2) else tam - 1
            else:  # bytes=-N: los últimos N
                ini = max(0, tam - int(m.group(2)))
            if ini > fin:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{tam}")
                self.end_headers()
                return
            status = HTTPStatus.PARTIAL_CONTENT
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(fin - ini + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {ini}-{fin}/{tam}")
        self.end_headers()
        try:
            with open(ruta, "rb") as f:
                f.seek(ini)
                faltan = fin - ini + 1
                while faltan > 0:
                    trozo = f.read(min(1 << 20, faltan))
                    if not trozo:
                        break
                    self.wfile.write(trozo)
                    faltan -= len(trozo)
        except (BrokenPipeError, ConnectionResetError):
            pass  # el navegador cancela pedazos del video al adelantar

    def _cuerpo(self):
        """Trozos del cuerpo de la petición (con Content-Length o chunked)."""
        if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
            while True:
                tam = int(self.rfile.readline().split(b";")[0].strip() or b"0", 16)
                if tam == 0:
                    self.rfile.readline()
                    return
                faltan = tam
                while faltan > 0:
                    trozo = self.rfile.read(min(1 << 20, faltan))
                    if not trozo:
                        return
                    faltan -= len(trozo)
                    yield trozo
                self.rfile.readline()
        else:
            faltan = int(self.headers.get("Content-Length") or 0)
            while faltan > 0:
                trozo = self.rfile.read(min(1 << 20, faltan))
                if not trozo:
                    return
                faltan -= len(trozo)
                yield trozo

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        ruta = urlsplit(self.path).path
        a = self.analisis
        if ruta == "/estado":
            return self._json(HTTPStatus.OK, self.trabajos.consultar())
        if ruta == "/tarjetas":
            return self._json(HTTPStatus.OK, {"tarjetas": self.trabajos.tarjetas()})
        if ruta == "/salud":
            return self._json(HTTPStatus.OK, {"ok": True})
        if ruta == "/chat":
            c = asistente.configuracion(a.raiz)
            return self._json(HTTPStatus.OK, {"configurado": c.lista, "modelos": list(c.modelos),
                                              "embeddings": c.embeddings})
        if ruta == "/analisis":
            return self._json(HTTPStatus.OK, {"analisis": [a.consultar(m["id"]) for m in a.listar()],
                                              "activo": a.activo(), "ocupado": a.motor.ocupado})
        if ruta in ("/analisis/activo", "/analisis/activo/red"):
            id_ = a.activo()
            datos = a.hallazgos(id_) if id_ else None
            if datos is None:
                return self._json(HTTPStatus.NOT_FOUND, {"error": "sin análisis activo"})
            return self._json(HTTPStatus.OK, red.construir(datos) if ruta.endswith("/red") else datos)
        m = re.fullmatch(r"/analisis/([\w-]+)", ruta)
        if m:
            meta = a.consultar(m.group(1))
            if meta is None:
                return self._json(HTTPStatus.NOT_FOUND, {"error": f"no existe {m.group(1)}"})
            return self._json(HTTPStatus.OK, meta)
        m = RECORTE.match(ruta)
        if m:
            tipo, id_, nombre = m.groups()
            if tipo == "tarjetas":
                d = self.trabajos.carpeta(id_) if id_ in self.trabajos.tarjetas() else None
            else:
                d = a.carpeta(id_)
                d = d / "salida" if d else None
            if d is not None and (d / "recortes" / nombre).is_file():
                return self._archivo(d / "recortes" / nombre, "image/jpeg")
        m = VIDEO.match(ruta)
        if m and a.carpeta(m.group(1)):
            video = a.carpeta(m.group(1)) / "salida/recorrido_anotado.mp4"
            if video.is_file():
                return self._archivo(video, "video/mp4")
        self._json(HTTPStatus.NOT_FOUND, {"error": f"no existe {ruta}"})

    def do_POST(self):
        partes = urlsplit(self.path)
        if partes.path == "/procesar":
            try:
                largo = int(self.headers.get("Content-Length") or 0)
                tarjeta = str(json.loads(self.rfile.read(largo) or b"{}")["tarjeta"])
            except (ValueError, KeyError, TypeError):
                return self._json(HTTPStatus.BAD_REQUEST, {"error": 'se espera {"tarjeta": "..."}'})
            return self._json(*self.trabajos.iniciar(tarjeta))
        if partes.path == "/analisis":
            q = {k: v[0] for k, v in parse_qs(partes.query).items()}
            largo = self.headers.get("Content-Length")
            cuerpo = self._cuerpo()
            respuesta = self.analisis.crear(
                q.get("nombre", "video.mp4"), q.get("detector", "anaquel"),
                q.get("identificar", "0") in ("1", "true", "si", "sí"), cuerpo,
                int(largo) if largo else None,
                q.get("planograma", "0") in ("1", "true", "si", "sí"))
            for _ in cuerpo:  # si se rechazó antes de leerlo, que el navegador vea el error
                pass
            return self._json(*respuesta)
        m = re.fullmatch(r"/analisis/([\w-]+)/activar", partes.path)
        if m:
            id_ = None if m.group(1) == "demo" else m.group(1)
            return self._json(*self.analisis.activar(id_))
        m = re.fullmatch(r"/analisis/([\w-]+)/chat", partes.path)
        if m:
            largo = int(self.headers.get("Content-Length") or 0)
            if largo > MAX_BYTES_CHAT:
                return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                                  {"error": "la conversación es demasiado larga"})
            try:
                datos = json.loads(self.rfile.read(largo) or b"{}")
            except ValueError:
                datos = None
            if not isinstance(datos, dict):
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "se espera un objeto JSON"})
            return self._json(*self.analisis.preguntar(m.group(1), datos))
        self._json(HTTPStatus.NOT_FOUND, {"error": f"no existe {partes.path}"})

    def do_DELETE(self):
        m = re.fullmatch(r"/analisis/([\w-]+)", urlsplit(self.path).path)
        if not m:
            return self._json(HTTPStatus.NOT_FOUND, {"error": f"no existe {self.path}"})
        self._json(*self.analisis.borrar(m.group(1)))

    def log_message(self, formato, *args):
        # el tablero consulta el estado cada segundo y el <video> pide muchos pedazos
        if not re.search(r"/estado|/analisis/[\w-]+$|/archivos/", self.path):
            log.info("%s %s", self.address_string(), formato % args)


def main(argv=None):
    ap = argparse.ArgumentParser(description="API local del motor para el tablero")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--puerto", type=int, default=8000)
    ap.add_argument("--raiz", default=".", help="raíz de motor-procesamiento")
    ap.add_argument("--tarjetas", default="video/tarjetas", help="<tarjeta>.mp4 del jurado")
    ap.add_argument("--sistema", default="datos/sistema")
    ap.add_argument("--base", default="salida", help="salida del motor del recorrido de demo")
    ap.add_argument("--salida", default="salida_api", help="una carpeta por tarjeta")
    ap.add_argument("--analisis", default="analisis", help="una carpeta por video subido")
    ap.add_argument("--cache", help="carpeta de caché del motor para las tarjetas (corte H16)")
    ap.add_argument("--catalogo", default="escena/empaques",
                    help="galería <sku>.png para identificar productos en los videos subidos "
                         "(corte H14), si se pide al subir")
    ap.add_argument("--prefijo-web", default="/motor",
                    help="ruta del tablero que reenvía a esta API (rewrite de Next)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    motor = Motor(Path(args.raiz).resolve())
    Manejador.trabajos = Trabajos(args, motor)
    Manejador.analisis = Analisis(args, motor)
    servidor = ThreadingHTTPServer((args.host, args.puerto), Manejador)
    log.info("API en http://%s:%d · tarjetas: %s · análisis guardados: %d", args.host,
             args.puerto, ", ".join(Manejador.trabajos.tarjetas()) or "ninguna",
             len(Manejador.analisis.listar()))
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
