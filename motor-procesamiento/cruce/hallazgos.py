"""Observaciones del motor + sistema de la tienda -> hallazgos.json del tablero.

    python -m cruce.hallazgos --salida-motor salida/ --json salida/hallazgos.json

Lee `observaciones.json` (y `diagnostico.json` para los fps) de la carpeta del motor y
`datos/sistema/` (planograma.csv, precios.csv, inventario.csv). El esquema de salida es el
de `Road2Tech/Frontend/types/hallazgos.ts`: `resumen`, `posiciones[]` y `hallazgos[]`.
Cada posición tiene a lo más un hallazgo (el primero que aplique, en el orden de
`clasificar`).
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from motor import contrato

DISCLAIMER = "Video simulado · Datos sintéticos de Glazed Co."

TIPOS_ETIQUETA = {"precio_anterior", "precio_distinto", "etiqueta_faltante", "etiqueta_otro_sku"}
TIPOS_HUECO = {"hueco_con_inventario", "hueco_agotado"}

# Un precio que no cuadra con lectura floja es "revisar", no un error.
CONFIANZA_MINIMA = 0.6
LECTURAS_MINIMAS = 2
TOLERANCIA_PRECIO = 0.005

# Supuestos del dinero en juego (US$ al día). V = venta diaria en piezas × precio vigente.
FRACCION_SIN_PRECIO = 0.25  # sin etiqueta, o con un precio más alto: el cliente no compra
FRACCION_FRENTES = 0.2      # con todos los frentes faltantes se pierde el 20 % de V
SUPUESTOS = ("Precio de etiqueta menor al del sistema: diferencia × venta diaria (se cobra el "
             "de la etiqueta). Sin etiqueta o con precio mayor: 25 % de la venta diaria. "
             "Hueco o producto equivocado: la venta diaria completa. Pocos frentes: 20 % de la "
             "venta diaria × frentes faltantes ÷ esperados. Lectura dudosa: sin estimar.")


@dataclass(frozen=True)
class Producto:
    sku: str
    nombre: str
    precio_vigente: float
    precio_anterior: float | None
    existencia: int | None
    venta_diaria: float

    @property
    def venta_diaria_usd(self) -> float:
        return self.venta_diaria * self.precio_vigente


@dataclass
class Sistema:
    plan: list[contrato.Posicion]
    productos: dict[str, Producto]


def _numero(valor: str | None) -> float | None:
    return float(valor) if valor not in (None, "") else None


def leer_sistema(dir_sistema: str | Path) -> Sistema:
    d = Path(dir_sistema)
    plan = contrato.leer_planograma(d / "planograma.csv")
    inventario = {}
    if (d / "inventario.csv").exists():
        with open(d / "inventario.csv", newline="", encoding="utf-8-sig") as f:
            inventario = {r["sku"].strip(): r for r in csv.DictReader(f)}
    productos = {}
    with open(d / "precios.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            sku = r["sku"].strip()
            inv = inventario.get(sku, {})
            existencia = _numero(inv.get("existencia"))
            productos[sku] = Producto(
                sku=sku, nombre=(r.get("nombre") or sku).strip(),
                precio_vigente=float(r["precio_vigente"]),
                precio_anterior=_numero(r.get("precio_anterior")),
                existencia=None if existencia is None else int(existencia),
                venta_diaria=_numero(inv.get("venta_diaria")) or 0.0)
    # Un SKU del planograma sin precio sale con precio_sistema 0 e impacto 0.
    return Sistema(plan, productos)


def _iguales(a: float, b: float | None) -> bool:
    return b is not None and abs(a - b) <= TOLERANCIA_PRECIO


def clasificar(o: dict, p: contrato.Posicion, prod: Producto | None) -> str | None:
    """Tipo de hallazgo de una posición, o None si está bien."""
    if o["hueco"]:
        hay = prod is not None and (prod.existencia or 0) > 0
        return "hueco_con_inventario" if hay else "hueco_agotado"
    if not o["etiqueta_visible"]:
        return "etiqueta_faltante"
    if o["sku_leido"] and p.sku and o["sku_leido"] != p.sku:
        return "etiqueta_otro_sku"
    if o.get("sku_producto") and p.sku and o["sku_producto"] != p.sku:  # solo con --catalogo
        return "producto_equivocado"
    precio = o["precio_leido"]
    if precio is None:
        return "revisar"  # se vio la etiqueta pero no se pudo leer
    if prod is not None and not _iguales(precio, prod.precio_vigente):
        anterior = _iguales(precio, prod.precio_anterior)
        # justo el precio anterior no sale de una mala lectura: basta con leerlo una vez
        if o["confianza_precio"] < CONFIANZA_MINIMA or (
                o["lecturas_coinciden"] < LECTURAS_MINIMAS and not anterior):
            return "revisar"
        return "precio_anterior" if anterior else "precio_distinto"
    if o["frentes_vistos"] is not None and o["frentes_vistos"] < p.frentes_esperados:
        return "frentes_bajos"  # None = la zona de producto no se vio completa
    return None


def impacto_diario(tipo: str, o: dict, p: contrato.Posicion, prod: Producto | None) -> float:
    if prod is None:
        return 0.0
    v = prod.venta_diaria_usd
    precio = o["precio_leido"]
    if tipo in ("precio_anterior", "precio_distinto", "etiqueta_otro_sku") and precio is not None:
        if precio < prod.precio_vigente:
            return (prod.precio_vigente - precio) * prod.venta_diaria
        return v * FRACCION_SIN_PRECIO
    if tipo in ("etiqueta_faltante", "etiqueta_otro_sku"):
        return v * FRACCION_SIN_PRECIO
    if tipo in TIPOS_HUECO or tipo == "producto_equivocado":
        return v
    if tipo == "frentes_bajos":
        faltan = max(0, p.frentes_esperados - (o["frentes_vistos"] or 0))
        return v * FRACCION_FRENTES * faltan / p.frentes_esperados
    return 0.0  # revisar: no se sabe hasta verificar en piso


def _dinero(x: float | None, moneda: str = "US$") -> str:
    return f"{moneda}{x:.2f}" if x is not None else "sin precio"


def describir(tipo: str, o: dict, p: contrato.Posicion, prod: Producto | None,
              productos: dict[str, Producto], moneda: str = "US$") -> tuple[str, str]:
    """(descripción, acción sugerida) en palabras de la tienda."""
    _usd = lambda x: _dinero(x, moneda)  # noqa: E731
    nombre = prod.nombre if prod else (p.nombre or p.sku or p.posicion)
    vigente = prod.precio_vigente if prod else None
    precio = o["precio_leido"]
    if tipo == "precio_anterior":
        return (f"La etiqueta dice {_usd(precio)} · El sistema dice {_usd(vigente)}. Es el "
                "precio anterior: la etiqueta no se cambió con la lista nueva.",
                f"Cambiar la etiqueta por la del precio vigente, {_usd(vigente)}.")
    if tipo == "precio_distinto":
        return (f"La etiqueta dice {_usd(precio)} · El sistema dice {_usd(vigente)}. No coincide "
                "ni con el precio vigente ni con el anterior.",
                f"Confirmar el precio y reimprimir la etiqueta con {_usd(vigente)}.")
    if tipo == "etiqueta_faltante":
        return ("No hay etiqueta de precio en el riel de esta posición.",
                f"Imprimir y colocar la etiqueta de {nombre} ({_usd(vigente)}).")
    if tipo == "etiqueta_otro_sku":
        otro = productos.get(o["sku_leido"])
        otro_nombre = otro.nombre if otro else o["sku_leido"]
        return (f"La etiqueta es de {otro_nombre} ({o['sku_leido']}, {_usd(precio)}), pero en "
                f"esta posición va {nombre}.",
                f"Quitar la etiqueta de {otro_nombre} y colocar la de {nombre} ({_usd(vigente)}).")
    if tipo == "producto_equivocado":
        otro = productos.get(o["sku_producto"])
        otro_nombre = otro.nombre if otro else o["sku_producto"]
        return (f"En el lugar de {nombre} hay {otro_nombre} (identificado por imagen).",
                f"Regresar {otro_nombre} a su lugar y surtir {nombre}.")
    if tipo == "hueco_con_inventario":
        n = prod.existencia if prod else None
        return (f"La posición está vacía, pero el sistema dice que hay {n} piezas en tienda.",
                f"Surtir desde bodega: hay {n} piezas de {nombre} en sistema.")
    if tipo == "hueco_agotado":
        return ("La posición está vacía y el sistema confirma 0 piezas: agotado real.",
                f"Pedir resurtido de {nombre}.")
    if tipo == "frentes_bajos":
        n = o["frentes_vistos"]
        return (f"Se {'ve' if n == 1 else 'ven'} {n} frente{'' if n == 1 else 's'} de "
                f"{p.frentes_esperados} esperados.",
                f"Acomodar hasta completar {p.frentes_esperados} frentes.")
    conf = round(100 * (o["confianza_precio"] or 0))
    leido = f"se leyó {_usd(precio)} " if precio is not None else ""
    return (f"La etiqueta se vio, pero la lectura no es segura ({leido}con confianza de "
            f"{conf} %).", "Verificar la etiqueta en piso.")


def _evidencia(o: dict, tipo: str | None, prefijo: str) -> str | None:
    etiqueta, posicion = o.get("recorte_etiqueta"), o.get("recorte_posicion")
    de_etiqueta = tipo in TIPOS_ETIQUETA or tipo == "revisar"
    ruta = (etiqueta or posicion) if de_etiqueta else (posicion or etiqueta)
    return f"{prefijo.rstrip('/')}/{ruta}" if ruta else None


def fps_de(dir_motor: Path, defecto: float = 30.0) -> float:
    try:
        diag = json.loads((dir_motor / "diagnostico.json").read_text(encoding="utf-8"))
        return float(diag["video"]["fps"]) or defecto
    except (OSError, KeyError, TypeError, ValueError):
        return defecto


def construir(obs: dict, sistema: Sistema, fps: float = 30.0, prefijo: str = "/salida",
              fecha_escaneo: str | None = None, video_url: str | None = None,
              disclaimer: str = DISCLAIMER, moneda: str = "US$") -> dict:
    """observaciones.json (dict) -> hallazgos.json (dict) con el esquema del tablero.

    `prefijo` es la URL base de los recortes, `video_url` la del video anotado en el tablero y
    `moneda` la de los precios del sistema (y de las etiquetas).
    """
    por_pos = {o["posicion"]: o for o in obs["posiciones"]}
    posiciones, hallazgos = [], []
    for p in sistema.plan:
        o = por_pos.get(p.posicion)
        if o is None:  # el video no cubrió esta posición
            continue
        prod = sistema.productos.get(p.sku) if p.sku else None
        tipo = clasificar(o, p, prod)
        num_pos = contrato.repisa_a_numero(p.posicion.split("-")[-1])
        clave = p.posicion.lower()
        cuadro = int(o["cuadro"] or 0)
        fila = {
            "id": f"pos-{clave}", "repisa": p.repisa, "posicion": num_pos,
            "estado": "ok" if tipo is None else "revisar" if tipo == "revisar" else "error",
            "sku": p.sku or "", "producto": prod.nombre if prod else (p.nombre or ""),
            "precio_etiqueta": o["precio_leido"],
            "precio_sistema": prod.precio_vigente if prod else 0.0,
            "frentes": o["frentes_vistos"], "frentes_esperados": p.frentes_esperados,
            "inventario_sistema": prod.existencia if prod else None,
            "hallazgo_id": None, "evidencia": _evidencia(o, tipo, prefijo),
        }
        if tipo is not None:
            descripcion, accion = describir(tipo, o, p, prod, sistema.productos, moneda)
            impacto = round(impacto_diario(tipo, o, p, prod), 2)
            h = {
                "id": f"hallazgo-{clave}", "tipo": tipo,
                "producto": fila["producto"], "sku": fila["sku"],
                "repisa": p.repisa, "posicion": num_pos,
                "precio_etiqueta": o["precio_leido"], "precio_sistema": fila["precio_sistema"],
                "impacto_diario": impacto, "cuadro": cuadro, "segundo": round(cuadro / fps, 2),
                "descripcion": descripcion, "accion_sugerida": accion,
                "evidencia_crop": _evidencia(o, tipo, prefijo), "corregido": False,
                "confianza_precio": o["confianza_precio"],
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
        "frase": f"{n} problema{'s' if n != 1 else ''} en este anaquel · {moneda}{total:.2f} al "
                 "día en juego",
        "etiquetas_con_error": sum(t in TIPOS_ETIQUETA for t in tipos),
        "huecos_inventario": sum(t in TIPOS_HUECO for t in tipos),
        "lecturas_dudosas": tipos.count("revisar"),
        "precision_anaquel_pct": round(100.0 * ok / len(posiciones), 1) if posiciones else 100.0,
        "fecha_escaneo": fecha_escaneo or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "disclaimer": disclaimer, "moneda": moneda,
        "video": obs.get("video"), "video_url": video_url, "segundos_proceso": obs.get("segundos_proceso"), "fps": fps,
        "supuestos_calculo": SUPUESTOS,
    }
    return {"resumen": resumen, "posiciones": posiciones, "hallazgos": hallazgos}


def desde_carpeta(dir_motor: str | Path, sistema: Sistema, prefijo: str = "/salida",
                  **opciones) -> dict:
    """Arma hallazgos.json a partir de la carpeta de salida del motor (opciones: `video_url`,
    `disclaimer`)."""
    d = Path(dir_motor)
    ruta = d / "observaciones.json"
    obs = json.loads(ruta.read_text(encoding="utf-8"))
    fecha = datetime.fromtimestamp(ruta.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    return construir(obs, sistema, fps_de(d), prefijo, fecha, **opciones)


def nuevos(base: dict, otro: dict) -> list[dict]:
    """Hallazgos de `otro` que no estaban en `base` (misma posición y mismo tipo)."""
    vistos = {(h["repisa"], h["posicion"], h["tipo"]) for h in base["hallazgos"]}
    return [h for h in otro["hallazgos"] if (h["repisa"], h["posicion"], h["tipo"]) not in vistos]


def main(argv=None):
    ap = argparse.ArgumentParser(description="observaciones.json + sistema -> hallazgos.json")
    ap.add_argument("--salida-motor", default="salida/", help="carpeta con observaciones.json")
    ap.add_argument("--sistema", default="datos/sistema/", help="planograma, precios, inventario")
    ap.add_argument("--json", default=None, help="ruta del hallazgos.json (por omisión, en la "
                                                 "carpeta del motor)")
    ap.add_argument("--prefijo", default="/salida", help="URL base de los recortes en el tablero")
    args = ap.parse_args(argv)

    datos = desde_carpeta(args.salida_motor, leer_sistema(args.sistema), args.prefijo)
    destino = Path(args.json or Path(args.salida_motor) / "hallazgos.json")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{datos['resumen']['frase']} -> {destino}")
    for h in datos["hallazgos"]:
        print(f"  R{h['repisa']}-P{h['posicion']} {h['tipo']:<22} US${h['impacto_diario']:>7.2f}"
              f"  {h['producto']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
