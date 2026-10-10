"""Cruce del modo sin estructura: observaciones_libre.json -> hallazgos.json del tablero.

    python -m cruce.libre --salida-motor salida_libre/ --json salida_libre/hallazgos.json

Sin planograma ni sistema de la tienda solo se puede juzgar lo que se ve en el video; cada
etiqueta seguida por motor/libre.py es una posición y tiene a lo más un hallazgo:

- hueco: encima de la etiqueta no hay producto.
- precio_inconsistente: otra etiqueta del mismo producto (por el nombre leído) tiene otro
  precio. Se marca la del precio minoritario; si empatan, la del precio más alto.
Una etiqueta cuyo precio no se leyó con seguridad (las lecturas que coinciden pesan menos de
60 %, o la confianza es baja) queda en estado "revisar" y cuenta en lecturas_dudosas, pero no
es un hallazgo: sin estructura y con videos de baja resolución pasa seguido (los centavos en
superíndice casi no se leen) y llenaría la lista de problemas.

El dinero es una estimación con el precio leído en la etiqueta y una venta supuesta por
posición (no hay ventas del sistema); el tablero lo dice en el aviso y en los supuestos.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from motor.libre import parecido

DISCLAIMER = "Video sin estructura (p. ej. generado con IA) · Sin datos de sistema: montos estimados"
MONEDA = "$"
VENTA_SUPUESTA = 6           # piezas al día por posición (no hay ventas del sistema)
CONFIANZA_MINIMA = 0.6       # por debajo, el precio es "lectura dudosa"
CONFIANZA_COMPARAR = 0.75    # para decir que dos etiquetas tienen precios distintos
PARECIDO_MISMO = 0.8         # nombres leídos así de parecidos son el mismo producto
COINCIDEN_MINIMO = 0.6       # fracción (por confianza) de lecturas con el mismo precio
SUPUESTOS = (f"Sin ventas ni precios del sistema: se supone una venta de {VENTA_SUPUESTA} "
             "piezas al día por posición. Hueco: precio de la etiqueta × venta supuesta (si "
             "ese precio no se leyó con seguridad, la mediana de los precios del video que sí). "
             "Mismo producto con precios distintos: diferencia × venta supuesta. Lectura "
             "dudosa: sin estimar.")


def _p(x: float | None) -> str:
    return f"{MONEDA}{x:.2f}" if x is not None else "sin precio"


def precio_confiable(e: dict) -> bool:
    """El precio se leyó con confianza y la mayoría de las lecturas coinciden."""
    if e["precio_leido"] is None or (e["confianza_precio"] or 0) < CONFIANZA_MINIMA:
        return False
    return (e.get("acuerdo") or 0.0) >= COINCIDEN_MINIMO


def _nombre_para_comparar(nombre: str | None) -> str:
    """Sin unidades ni números: "ARROZ BLANCO 1KG" y "ARROZ BLANCO KG" son el mismo."""
    if not nombre:
        return ""
    palabras = [w for w in nombre.split() if not re.fullmatch(r"\d*(KG|K|G|L|ML|GR|OZ)?", w)]
    return " ".join(palabras)


def nombres_de_grupo(etiquetas: list[dict]) -> dict[str, str]:
    """id -> nombre para mostrar: el de la etiqueta mejor leída entre las del mismo producto
    (así "RROZBLANCO KG" se muestra como "ARROZ BLANCO")."""
    grupos: list[list[dict]] = []
    for e in etiquetas:
        n = _nombre_para_comparar(e["nombre_leido"])
        if len(n.replace(" ", "")) < 5:
            continue
        for g in grupos:
            if any(parecido(n, _nombre_para_comparar(x["nombre_leido"])) >= PARECIDO_MISMO
                   for x in g):
                g.append(e)
                break
        else:
            grupos.append([e])
    nombres = {}
    for g in grupos:
        mejor = max(g, key=lambda e: (e["lecturas_coinciden"], e["lecturas"]))
        for e in g:
            nombres[e["id"]] = mejor["nombre_leido"]
    return nombres


def precios_inconsistentes(etiquetas: list[dict]) -> dict[str, dict]:
    """id de etiqueta -> {"otra": etiqueta, ...} para las que contradicen a otra del mismo
    producto."""
    seguras = [e for e in etiquetas if precio_confiable(e)
               and e["confianza_precio"] >= CONFIANZA_COMPARAR
               and len(_nombre_para_comparar(e["nombre_leido"]).replace(" ", "")) >= 5]
    grupos: list[list[dict]] = []
    for e in seguras:
        n = _nombre_para_comparar(e["nombre_leido"])
        for g in grupos:
            if any(parecido(n, _nombre_para_comparar(x["nombre_leido"])) >= PARECIDO_MISMO
                   for x in g):
                g.append(e)
                break
        else:
            grupos.append([e])
    marcadas = {}
    for g in grupos:
        precios = Counter(e["precio_leido"] for e in g)
        if len(precios) < 2:
            continue
        # el precio "bueno" es el más repetido; si empatan, el más bajo
        bueno = max(precios, key=lambda p: (precios[p], -p))
        referencia = next(e for e in g if e["precio_leido"] == bueno)
        for e in g:
            if e["precio_leido"] != bueno:
                marcadas[e["id"]] = {"otra": referencia, "precio_otra": bueno}
    return marcadas


def construir(obs: dict, prefijo: str = "/salida", fecha_escaneo: str | None = None,
              video_url: str | None = None, disclaimer: str = DISCLAIMER) -> dict:
    """observaciones_libre.json (dict) -> hallazgos.json (dict) con el esquema del tablero."""
    fps = float(obs.get("fps") or 30.0)
    base = prefijo.rstrip("/")
    etiquetas = obs.get("etiquetas", [])
    inconsistentes = precios_inconsistentes(etiquetas)
    nombres = nombres_de_grupo(etiquetas)
    confiables = [e["precio_leido"] for e in etiquetas if precio_confiable(e)]
    precio_tipico = statistics.median(confiables) if confiables else None
    posiciones, hallazgos = [], []
    for n, e in enumerate(etiquetas, 1):
        precio, conf = e["precio_leido"], e["confianza_precio"] or 0.0
        leido = nombres.get(e["id"]) or e["nombre_leido"]
        nombre = leido or f"Etiqueta {e['id']} · sin nombre legible"
        de_quien = f"{e['id']} de {leido}" if leido else e["id"]
        dudosa = not precio_confiable(e)
        if e["hueco"]:
            tipo = "hueco"
        elif e["id"] in inconsistentes:
            tipo = "precio_inconsistente"
        elif dudosa:
            tipo = "revisar"
        else:
            tipo = None
        evid_etiqueta = f"{base}/{e['recorte_etiqueta']}" if e.get("recorte_etiqueta") else None
        evid_zona = f"{base}/{e['recorte_posicion']}" if e.get("recorte_posicion") else None
        cuadro = int(e.get("cuadro") or 0)
        fila = {
            "id": f"pos-{e['id'].lower()}", "repisa": 0, "posicion": n,
            "ubicacion": f"Etiqueta {e['id']}",
            "estado": "ok" if tipo is None else "revisar" if tipo == "revisar" else "error",
            "sku": "", "producto": nombre, "precio_etiqueta": precio, "precio_sistema": None,
            "frentes": None, "inventario_sistema": None, "hallazgo_id": None,
            "evidencia": (evid_zona if tipo == "hueco" else evid_etiqueta) or evid_zona,
        }
        if tipo == "revisar":  # posición en ámbar, sin hallazgo (ver el docstring)
            leido_txt = f"se leyó {_p(precio)} " if precio is not None else ""
            fila.update(tipo="revisar", impacto_diario=0.0,
                        accion=f"Verificar la etiqueta en piso: el precio no se leyó con "
                               f"seguridad ({leido_txt}con confianza de {round(100 * conf)} %).")
        elif tipo is not None:
            precio_txt = (_p(precio) if not dudosa else "precio ilegible" if precio is None
                          else f"precio dudoso, se leyó {_p(precio)}")
            if tipo == "hueco":
                base_precio = precio if not dudosa else precio_tipico
                impacto = base_precio * VENTA_SUPUESTA if base_precio is not None else 0.0
                descripcion = f"Encima de la etiqueta {de_quien} ({precio_txt}) no hay producto."
                accion = "Surtir el producto de esta etiqueta o confirmar si está agotado."
            elif tipo == "precio_inconsistente":
                otra = inconsistentes[e["id"]]
                impacto = abs(precio - otra["precio_otra"]) * VENTA_SUPUESTA
                descripcion = (f"La etiqueta {de_quien} dice {_p(precio)}, pero la etiqueta "
                               f"{otra['otra']['id']} del mismo producto dice "
                               f"{_p(otra['precio_otra'])}.")
                accion = ("Confirmar el precio vigente en el sistema y cambiar la etiqueta que "
                          "no coincida.")
            impacto = round(impacto, 2)
            h = {
                "id": f"hallazgo-{e['id'].lower()}", "tipo": tipo, "producto": nombre, "sku": "",
                "repisa": 0, "posicion": n, "ubicacion": fila["ubicacion"],
                "precio_etiqueta": precio, "precio_sistema": None, "impacto_diario": impacto,
                "cuadro": cuadro, "segundo": round(cuadro / fps, 2), "descripcion": descripcion,
                "accion_sugerida": accion,
                "evidencia_crop": (evid_zona if tipo == "hueco" else evid_etiqueta) or evid_zona,
                "corregido": False, "confianza_precio": conf,
            }
            hallazgos.append(h)
            fila.update(hallazgo_id=h["id"], tipo=tipo, impacto_diario=impacto, accion=accion)
        posiciones.append(fila)

    hallazgos.sort(key=lambda h: -h["impacto_diario"])
    total = round(sum(h["impacto_diario"] for h in hallazgos), 2)
    tipos = [h["tipo"] for h in hallazgos]
    ok = sum(1 for f in posiciones if f["estado"] == "ok")
    n = len(hallazgos)
    resumen = {
        "total_problemas": n,
        "dinero_en_riesgo_diario": total,
        "frase": f"{n} problema{'s' if n != 1 else ''} en este anaquel · {MONEDA}{total:.2f} al "
                 "día en juego (estimado)",
        "etiquetas_con_error": tipos.count("precio_inconsistente"),
        "huecos_inventario": tipos.count("hueco"),
        "lecturas_dudosas": sum(1 for f in posiciones if f["estado"] == "revisar"),
        "precision_anaquel_pct": round(100.0 * ok / len(posiciones), 1) if posiciones else 100.0,
        "fecha_escaneo": fecha_escaneo or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "disclaimer": disclaimer,
        "modo": "libre", "moneda": MONEDA,
        "video": obs.get("video"), "video_url": video_url,
        "segundos_proceso": obs.get("segundos_proceso"), "fps": fps,
        "supuestos_calculo": SUPUESTOS,
    }
    return {"resumen": resumen, "posiciones": posiciones, "hallazgos": hallazgos}


def desde_carpeta(dir_motor: str | Path, prefijo: str = "/salida", **opciones) -> dict:
    """Arma hallazgos.json a partir de la salida de motor/libre.py (opciones: `video_url`,
    `disclaimer`)."""
    ruta = Path(dir_motor) / "observaciones_libre.json"
    obs = json.loads(ruta.read_text(encoding="utf-8"))
    fecha = datetime.fromtimestamp(ruta.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    return construir(obs, prefijo, fecha, **opciones)


def main(argv=None):
    ap = argparse.ArgumentParser(description="observaciones_libre.json -> hallazgos.json")
    ap.add_argument("--salida-motor", default="salida_libre/")
    ap.add_argument("--json", default=None, help="por omisión, en la carpeta del motor")
    ap.add_argument("--prefijo", default="/salida", help="URL base de los recortes en el tablero")
    args = ap.parse_args(argv)

    datos = desde_carpeta(args.salida_motor, args.prefijo)
    destino = Path(args.json or Path(args.salida_motor) / "hallazgos.json")
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{datos['resumen']['frase']} -> {destino}")
    for h in datos["hallazgos"]:
        print(f"  {h['ubicacion']:<12} {h['tipo']:<22} {MONEDA}{h['impacto_diario']:>7.2f}  "
              f"{h['producto']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
