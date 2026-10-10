"""Publica la salida del motor en el tablero (Road2Tech/Frontend/public/).

    python -m cruce.publicar --web ../Road2Tech/Frontend/public

- salida/ (recorrido completo) -> public/salida/hallazgos.json, recortes/ y
  recorrido_anotado.mp4 (pantallas 1 a 4), y public/red.json (impacto en red, cruce/red.py).
- salida_tarjetas/<tarjeta>/ -> public/ensayos/<tarjeta>/hallazgos.json y recortes/: el
  resultado de ensayo del modo jurado si la API no responde o pasan 60 s.

Hay que correrlo antes de `npm run build`: Next solo sirve lo que había en public/ al
compilar.
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from cruce import hallazgos as cruce
from cruce import red
from cruce.api import PASOS


def _escribir(ruta: Path, datos: dict):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def _copiar_recortes(origen: Path, destino: Path):
    if destino.exists():
        shutil.rmtree(destino)
    if origen.is_dir():
        shutil.copytree(origen, destino)


def publicar(web: Path, salida: Path, tarjetas: Path, sistema: cruce.Sistema) -> dict:
    base = cruce.desde_carpeta(salida, sistema, "/salida",
                               video_url="/salida/recorrido_anotado.mp4")
    _escribir(web / "salida/hallazgos.json", base)
    _copiar_recortes(salida / "recortes", web / "salida/recortes")
    video = salida / "recorrido_anotado.mp4"
    if video.exists():
        shutil.copy2(video, web / "salida/recorrido_anotado.mp4")
    else:
        print(f"aviso: no está {video}; la pantalla de recorrido quedará sin video")
    print(f"{base['resumen']['frase']} -> {web / 'salida'}")
    _escribir(web / "red.json", red.construir(base))

    ensayos = {}
    for obs in sorted(tarjetas.glob("*/observaciones.json")):
        tarjeta = obs.parent.name
        resultado = cruce.desde_carpeta(obs.parent, sistema, f"/ensayos/{tarjeta}")
        nuevos = cruce.nuevos(base, resultado)
        _escribir(web / f"ensayos/{tarjeta}/hallazgos.json", {
            "origen": "ensayo", "tarjeta": tarjeta,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pasos_completados": list(PASOS),
            "segundos_proceso": resultado["resumen"]["segundos_proceso"],
            "hallazgo_nuevo": nuevos[0] if nuevos else None,
            "hallazgos_nuevos": nuevos})
        _copiar_recortes(obs.parent / "recortes", web / f"ensayos/{tarjeta}/recortes")
        ensayos[tarjeta] = nuevos
        print(f"  ensayo {tarjeta}: " + (", ".join(
            f"R{h['repisa']}-P{h['posicion']} {h['tipo']}" for h in nuevos) or "sin hallazgo nuevo"))
    return {"base": base, "ensayos": ensayos}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Copia la salida del motor al tablero")
    ap.add_argument("--web", default="../Road2Tech/Frontend/public", help="public/ del tablero")
    ap.add_argument("--salida", default="salida", help="salida del motor del recorrido")
    ap.add_argument("--tarjetas", default="salida_tarjetas",
                    help="una carpeta de salida del motor por tarjeta del modo jurado")
    ap.add_argument("--sistema", default="datos/sistema")
    args = ap.parse_args(argv)

    web = Path(args.web)
    if not web.is_dir():
        ap.error(f"no existe {web}")
    publicar(web, Path(args.salida), Path(args.tarjetas), cruce.leer_sistema(args.sistema))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
