"""hallazgos.json de un anaquel -> red.json del tablero (pantalla "Impacto en red").

    python -m cruce.red --hallazgos salida/hallazgos.json --json ../Road2Tech/Frontend/public/red.json

Un anaquel no dice qué pasa en las otras tiendas, así que no se multiplica todo lo encontrado
por el número de tiendas. Cada hallazgo se separa por su origen:

- Sistémico (`precio_anterior`): la etiqueta se quedó con el precio de la lista anterior. La
  lista la cambia el corporativo en toda la red a la vez, así que la misma etiqueta puede
  seguir vieja en otras tiendas que venden el SKU. Es lo único que se proyecta.
- Local (huecos, etiqueta faltante o de otro SKU, producto equivocado, frentes bajos, precio
  distinto y los del modo sin estructura): depende de esta tienda y de este momento. Se
  reporta como medido y no se proyecta. Las lecturas dudosas (`revisar`) no cuentan.

La proyección son escenarios, no una cifra: la etiqueta vieja sigue en el 10, 25 o 50 % de las
otras tiendas, o en todas (peor caso). Cada tienda se supone con las ventas de la auditada,
porque no hay ventas por tienda.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

TIENDAS_RED = 38  # red sintética de Glazed Co.
SISTEMICOS = {"precio_anterior"}
# precio_distinto no es ni el vigente ni el anterior: se toma como captura de la tienda hasta
# confirmar que viene del catálogo central.
ESCENARIOS = (("bajo", 10), ("central", 25), ("alto", 50))  # % de las otras tiendas
DIAS_MES = 30
SUPUESTOS = ("Solo se proyectan las etiquetas con el precio de la lista anterior: la lista la "
             "cambia el corporativo en toda la red a la vez, así que la misma etiqueta puede "
             "seguir vieja en otras tiendas. Se supone que cada una vende lo mismo que la "
             "auditada (no hay ventas por tienda) y se dan escenarios, no una cifra: la "
             "etiqueta sigue vieja en el " + ", ".join(str(p) for _, p in ESCENARIOS[:-1]) +
             f" o {ESCENARIOS[-1][1]} % de las otras tiendas, o en todas (peor caso). A "
             f"{DIAS_MES} días es el monto diario × {DIAS_MES}. Huecos, etiquetas faltantes o "
             "de otro producto, producto equivocado, frentes y precios distintos dependen de "
             "cada tienda: se reportan como medidos y no se proyectan.")


def _escenario(nombre: str, pct: int, otras: int, por_tienda: float) -> dict:
    tiendas = int(pct * otras / 100 + 0.5)
    diario = round(tiendas * por_tienda, 2)
    return {"nombre": nombre, "pct": pct, "tiendas": tiendas, "diario": diario,
            "mensual": round(diario * DIAS_MES, 2)}


def construir(hallazgos: dict, tiendas: int = TIENDAS_RED) -> dict:
    """hallazgos.json (dict) -> red.json (dict) con el esquema de Frontend/types/red.ts."""
    resumen = hallazgos["resumen"]
    otras = tiendas - 1
    sistemicos, locales = [], {}
    for h in hallazgos["hallazgos"]:
        if h["tipo"] in SISTEMICOS:
            sistemicos.append({
                "sku": h["sku"], "producto": h["producto"], "tipo": h["tipo"],
                "precio_etiqueta": h["precio_etiqueta"], "precio_sistema": h["precio_sistema"],
                "impacto_diario": h["impacto_diario"],
                "peor_caso_diario": round(h["impacto_diario"] * otras, 2)})
        elif h["tipo"] != "revisar":
            grupo = locales.setdefault(h["tipo"], {"tipo": h["tipo"], "cantidad": 0,
                                                   "impacto_diario": 0.0})
            grupo["cantidad"] += 1
            grupo["impacto_diario"] += h["impacto_diario"]
    for grupo in locales.values():
        grupo["impacto_diario"] = round(grupo["impacto_diario"], 2)

    por_tienda = round(sum(s["impacto_diario"] for s in sistemicos), 2)
    local = round(sum(g["impacto_diario"] for g in locales.values()), 2)
    escenarios = [_escenario(n, p, otras, por_tienda) for n, p in ESCENARIOS]
    escenarios.append(_escenario("peor_caso", 100, otras, por_tienda))
    return {
        "red": {
            "tiendas_total": tiendas,
            "otras_tiendas": otras,
            "moneda": resumen.get("moneda") or "US$",
            "medido_diario": round(por_tienda + local, 2),
            "sistemico_diario": por_tienda,
            "local_diario": local,
            "problemas_sistemicos": len(sistemicos),
            "problemas_locales": sum(g["cantidad"] for g in locales.values()),
            "dias_mes": DIAS_MES,
            "supuestos_calculo": SUPUESTOS,
            "dataset_label": f"Red sintética de Glazed Co. ({tiendas} tiendas)",
            "fecha_corte": (resumen.get("fecha_escaneo") or date.today().isoformat())[:10],
            "origen": resumen.get("video"),
        },
        "escenarios": escenarios,
        "sistemicos": sorted(sistemicos, key=lambda s: -s["impacto_diario"]),
        "locales": sorted(locales.values(), key=lambda g: -g["impacto_diario"]),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="hallazgos.json de un anaquel -> red.json")
    ap.add_argument("--hallazgos", default="salida/hallazgos.json")
    ap.add_argument("--json", default=None, help="ruta del red.json (por omisión, junto al "
                                                 "hallazgos.json)")
    ap.add_argument("--tiendas", type=int, default=TIENDAS_RED, help="tiendas en la red")
    args = ap.parse_args(argv)

    origen = Path(args.hallazgos)
    datos = construir(json.loads(origen.read_text(encoding="utf-8")), args.tiendas)
    destino = Path(args.json or origen.with_name("red.json"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    r, m = datos["red"], datos["red"]["moneda"]
    print(f"Medido: {m}{r['medido_diario']:.2f}/día · se proyecta {m}{r['sistemico_diario']:.2f}"
          f"/día por tienda ({r['problemas_sistemicos']} etiquetas con precio anterior) -> {destino}")
    for e in datos["escenarios"]:
        print(f"  {e['nombre']:<9} {e['tiendas']:>3} de {r['otras_tiendas']} tiendas: "
              f"{m}{e['diario']:>8.2f}/día · {m}{e['mensual']:>9.2f} a {DIAS_MES} días")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
