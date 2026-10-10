"""Métricas del motor contra la escena (las mismas que mide P4).

Esta herramienta sí lee escena/ (es la verdad); el motor no.

    python -m herramientas.evaluar_motor --observaciones salida/observaciones.json \
        --escena escena/escena.json [--duracion-clip 23.1]

Métricas mínimas (PDF de P2):
  etiquetas encontradas ≥ 95 %, precio exacto por etiqueta tras votar ≥ 95 %,
  huecos encontrados ≥ 90 % y huecos falsos ≤ 1, frentes exactos ≥ 85 %,
  ≤ 60 s para un clip de 10 s.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


def evaluar(obs: dict, escena: dict, diagnostico: dict | None = None,
            solo_repisa: str | None = None) -> dict:
    verdad = {p["posicion"]: p for p in escena["posiciones"]}
    filas = []
    for o in obs["posiciones"]:
        v = verdad.get(o["posicion"])
        if v is None or (solo_repisa and not o["posicion"].startswith(solo_repisa)):
            continue
        e = v.get("etiqueta") or {}
        filas.append((o, v, e))

    con_etiqueta = [(o, v, e) for o, v, e in filas if e.get("visible")]
    sin_etiqueta = [(o, v, e) for o, v, e in filas if not e.get("visible")]
    encontradas = [f for f in con_etiqueta if f[0]["etiqueta_visible"]]
    falsas = [f for f in sin_etiqueta if f[0]["etiqueta_visible"]]
    precio_ok = [f for f in con_etiqueta
                 if f[0]["precio_leido"] is not None
                 and abs(f[0]["precio_leido"] - float(f[2]["precio"])) < 0.005]
    sku_ok = [f for f in con_etiqueta if f[0]["sku_leido"] == f[2].get("sku")]
    huecos = [f for f in filas if int(f[1].get("frentes_fisicos", 0)) == 0]
    huecos_ok = [f for f in huecos if f[0]["hueco"]]
    huecos_falsos = [f for f in filas if f[0]["hueco"] and int(f[1].get("frentes_fisicos", 0)) > 0]
    medidas = [f for f in filas if f[0]["frentes_vistos"] is not None]
    frentes_ok = [f for f in medidas
                  if int(f[0]["frentes_vistos"]) == int(f[1].get("frentes_fisicos", 0))]
    con_producto = [f for f in medidas if not f[0]["hueco"] and "sku_producto" in f[0]]
    producto_ok = [f for f in con_producto if f[0]["sku_producto"] == f[1].get("sku_fisico")]

    def pct(a, b):
        return round(100.0 * len(a) / len(b), 1) if b else None

    m = {
        "posiciones_reportadas": len(filas),
        "etiquetas_encontradas_pct": pct(encontradas, con_etiqueta),
        "etiquetas_falsas": len(falsas),
        "precio_exacto_pct": pct(precio_ok, con_etiqueta),
        "sku_exacto_pct": pct(sku_ok, con_etiqueta),
        "huecos_encontrados_pct": pct(huecos_ok, huecos),
        "huecos_falsos": len(huecos_falsos),
        "frentes_exactos_pct": pct(frentes_ok, medidas),
        "frentes_no_medidos": len(filas) - len(medidas),
        "producto_correcto_pct": pct(producto_ok, con_producto) if con_producto else None,
        "segundos_proceso": obs.get("segundos_proceso"),
        "fallas": {
            "etiqueta_no_encontrada": [f[0]["posicion"] for f in con_etiqueta if f not in encontradas],
            "etiqueta_falsa": [f[0]["posicion"] for f in falsas],
            "precio": [(f[0]["posicion"], f[0]["precio_leido"], f[2]["precio"])
                       for f in con_etiqueta if f not in precio_ok],
            "sku": [(f[0]["posicion"], f[0]["sku_leido"], f[2].get("sku"))
                    for f in con_etiqueta if f not in sku_ok],
            "hueco_no_encontrado": [f[0]["posicion"] for f in huecos if f not in huecos_ok],
            "hueco_falso": [f[0]["posicion"] for f in huecos_falsos],
            "frentes": [(f[0]["posicion"], f[0]["frentes_vistos"], f[1].get("frentes_fisicos"))
                        for f in medidas if f not in frentes_ok],
            "producto": [(f[0]["posicion"], f[0]["sku_producto"], f[1].get("sku_fisico"))
                         for f in con_producto if f not in producto_ok],
        },
    }
    if diagnostico:
        total = ok = 0
        for pos, d in diagnostico.get("posiciones", {}).items():
            e = (verdad.get(pos) or {}).get("etiqueta") or {}
            if not e.get("visible"):
                continue
            for l in d.get("lecturas", []):
                total += 1
                ok += l["precio"] is not None and abs(l["precio"] - float(e["precio"])) < 0.005
        m["precio_exacto_por_cuadro_pct"] = round(100.0 * ok / total, 1) if total else None
    return m


def imprimir(m: dict, duracion_clip: float | None):
    def fila(nombre, valor, minimo, ok):
        estado = "—" if valor is None else ("OK" if ok else "FALLA")
        print(f"  {nombre:<38} {str(valor):>8}   {minimo:<14} {estado}")

    print(f"  {'Métrica':<38} {'Valor':>8}   {'Mínimo':<14}")
    fila("Posiciones reportadas", m["posiciones_reportadas"], "", True)
    fila("Etiquetas encontradas (%)", m["etiquetas_encontradas_pct"], "≥ 95",
         (m["etiquetas_encontradas_pct"] or 0) >= 95)
    fila("Etiquetas falsas", m["etiquetas_falsas"], "0", m["etiquetas_falsas"] == 0)
    fila("Precio exacto por etiqueta (%)", m["precio_exacto_pct"], "≥ 95",
         (m["precio_exacto_pct"] or 0) >= 95)
    if "precio_exacto_por_cuadro_pct" in m:
        fila("Precio exacto por cuadro (%)", m["precio_exacto_por_cuadro_pct"], "≥ 85 (diag.)",
             (m["precio_exacto_por_cuadro_pct"] or 0) >= 85)
    fila("SKU exacto por etiqueta (%)", m["sku_exacto_pct"], "(extra)",
         (m["sku_exacto_pct"] or 0) >= 95)
    fila("Huecos encontrados (%)", m["huecos_encontrados_pct"], "≥ 90",
         m["huecos_encontrados_pct"] is None or m["huecos_encontrados_pct"] >= 90)
    fila("Huecos falsos", m["huecos_falsos"], "≤ 1", m["huecos_falsos"] <= 1)
    fila("Frentes exactos (%)", m["frentes_exactos_pct"], "≥ 85",
         (m["frentes_exactos_pct"] or 0) >= 85)
    if m["frentes_no_medidos"]:
        fila("Posiciones sin zona de producto vista", m["frentes_no_medidos"], "(no cuentan)", True)
    if m["producto_correcto_pct"] is not None:
        fila("Producto correcto por imagen (%)", m["producto_correcto_pct"], "≥ 90 (H14)",
             m["producto_correcto_pct"] >= 90)
    seg = m["segundos_proceso"]
    if seg is not None and duracion_clip:
        por10 = round(seg * 10 / duracion_clip, 1)
        fila(f"Segundos por 10 s de video ({seg} s / {duracion_clip:g} s)", por10, "≤ 60",
             por10 <= 60)
    fallas = {k: v for k, v in m["fallas"].items() if v}
    if fallas:
        print("  Fallas:", json.dumps(fallas, ensure_ascii=False))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Métricas del motor contra escena.json")
    ap.add_argument("--observaciones", default="salida/observaciones.json")
    ap.add_argument("--escena", default="escena/escena.json")
    ap.add_argument("--diagnostico", help="por defecto, diagnostico.json junto a observaciones")
    ap.add_argument("--duracion-clip", type=float, help="segundos de video procesados")
    ap.add_argument("--solo-repisa", help="medir solo esta repisa (clips de una pasada)")
    ap.add_argument("--guardar", default="salida/metricas")
    args = ap.parse_args(argv)
    obs = json.loads(Path(args.observaciones).read_text(encoding="utf-8"))
    esc = json.loads(Path(args.escena).read_text(encoding="utf-8"))
    ruta_diag = Path(args.diagnostico or Path(args.observaciones).with_name("diagnostico.json"))
    diag = json.loads(ruta_diag.read_text(encoding="utf-8")) if ruta_diag.exists() else None
    if args.duracion_clip is None and diag:
        v = diag.get("video", {})
        args.duracion_clip = v.get("cuadros", 0) / (v.get("fps") or 30)
    m = evaluar(obs, esc, diag, args.solo_repisa)
    print(f"\n{obs['video']} contra {args.escena}")
    imprimir(m, args.duracion_clip)
    d = Path(args.guardar)
    d.mkdir(parents=True, exist_ok=True)
    ruta = d / f"metricas_{Path(obs['video']).stem}_{datetime.now():%Y%m%d_%H%M%S}.json"
    ruta.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  guardado en {ruta}")


if __name__ == "__main__":
    main()
