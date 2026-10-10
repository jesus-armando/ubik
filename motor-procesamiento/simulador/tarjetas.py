"""Clips de las 4 tarjetas del juez (P1, paso 5): una sola pasada, rápida de renderizar.

Cada clip es la escena base con un error nuevo (escena/tarjetas/<tarjeta>.json), solo la
repisa de la tarjeta, ~10 s con 1.5 s quieto al inicio y al final. El mp4 que procesa el
motor (video/tarjetas/<tarjeta>.mp4) ya trae el paso de realismo.

    python -m simulador.tarjetas                    # 4K a 10 fps
    python -m simulador.tarjetas --res 1920x1080   # como el render rápido de P1

P1 propone 1920x1080 para renderizar rápido, pero a esa resolución el SKU de la etiqueta
mide ~9 px y no se lee (el precio sí). En 4K a 10 fps el clip sigue tardando segundos.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from simulador import realismo, render


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarjetas", default="escena/tarjetas")
    ap.add_argument("--planograma", default="datos/sistema/planograma.csv")
    ap.add_argument("--salida", default="video/tarjetas")
    ap.add_argument("--res", default="3840x2160",
                    help="en 1920x1080 el SKU de la etiqueta ya no se alcanza a leer")
    ap.add_argument("--fps", type=float, default=10)
    ap.add_argument("--pausa", type=float, default=1.5)
    args = ap.parse_args(argv)
    d = Path(args.salida)
    d.mkdir(parents=True, exist_ok=True)
    for ruta in sorted(Path(args.tarjetas).glob("*.json")):
        esc = json.loads(ruta.read_text(encoding="utf-8"))
        nombre, repisa = ruta.stem, esc["tarjeta"]["repisa"]
        limpio = d / f"{nombre}_limpio.mp4"
        render.main(["--escena", str(ruta), "--planograma", args.planograma,
                     "--empaques", "escena/empaques", "--video", str(limpio),
                     "--verdad", str(d / f"{nombre}_verdad"), "--solo-repisa", repisa,
                     "--fps", str(args.fps), "--res", args.res, "--pausa", str(args.pausa)])
        realismo.main([str(limpio), str(d / f"{nombre}.mp4")])
        limpio.unlink()


if __name__ == "__main__":
    main()
