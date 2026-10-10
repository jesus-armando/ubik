"""Pruebas del modo sin marcadores con planograma por orden (motor/orden.py y cruce/orden.py),
sin video ni modelos: las etiquetas son las que leyó motor/libre.py en el anaquel de la demo
armado en un pizarrón y grabado con el celular.

    python -m pytest -q tests/test_orden.py
"""
import shutil
from pathlib import Path

import pytest

from cruce import hallazgos as cruce
from cruce import orden as cruce_orden
from motor import orden

DIR_SISTEMA = Path(__file__).resolve().parent.parent / "datos/sistema"
SISTEMA = cruce.leer_sistema(DIR_SISTEMA)        # el de la demo, en dólares
EN_PESOS = cruce_orden.leer_sistema(DIR_SISTEMA)  # con datos/sistema/precios_pesos.csv


def etiqueta(id_, sku, precio, hueco=False, lecturas=4, texto=None, cuadro=0, nombre=None):
    return {"id": id_, "sku_leido": sku, "nombre_leido": nombre, "precio_leido": precio,
            "confianza_precio": 0.97, "lecturas": lecturas, "lecturas_coinciden": lecturas,
            "hueco": hueco, "texto_producto": texto or {}, "cuadro": cuadro,
            "primer_cuadro": cuadro, "ultimo_cuadro": cuadro + 40,
            "recorte_etiqueta": f"recortes/{id_}_etiqueta.jpg", "recorte_posicion": f"recortes/{id_}.jpg"}


# El recorrido del celular: serpentina, R2-P2 sin etiqueta, R2-P4 con la de 12 Bagels, una
# lectura suelta (E5: la etiqueta de R1-P3 otra vez, en la orilla) y croissants en R3-P3.
VIDEO = [
    etiqueta("E1", "SKU-100664", 124.08, lecturas=1, cuadro=0),
    etiqueta("E2", "SKU-100104", 271.07, cuadro=40),
    etiqueta("E3", "SKU-101809", 80.33, cuadro=150),
    etiqueta("E4", "SKU-100506", 260.57, cuadro=250),
    etiqueta("E5", None, 20.26, hueco=True, lecturas=1, cuadro=264),
    etiqueta("E6", "SKU-100506", 260.57, cuadro=350),
    etiqueta("E7", "SKU-100131", 73.33, texto={"BIELT": 1}, cuadro=420),
    etiqueta("E8", "SKU-100292", 45.32, texto={"OATMEAL": 3, "INSTANT": 2}, cuadro=600),
    etiqueta("E9", "SKU-100075", 87.33, hueco=True, cuadro=680),
    etiqueta("E10", "SKU-100599", 94.32, hueco=True, cuadro=740),
    etiqueta("E11", "SKU-102560", 43.58, texto={"CHICKEN": 3, "CROSSAT": 1, "CHICIEN": 1}, cuadro=830),
    etiqueta("E12", "SKU-100936", 24.32, texto={"FRENCH": 4, "TOAST": 4, "BAGEL": 3}, cuadro=930),
]


def test_rutas_serpentina_y_por_repisa():
    r = orden.rutas(SISTEMA.plan)
    assert [p.posicion for p in r["serpentina desde arriba a la izquierda"]][:8] == [
        "R1-P1", "R1-P2", "R1-P3", "R1-P4", "R2-P4", "R2-P3", "R2-P2", "R2-P1"]
    assert [p.posicion for p in r["repisa por repisa desde abajo a la izquierda"]][:5] == [
        "R3-P1", "R3-P2", "R3-P3", "R3-P4", "R2-P1"]
    assert len(r) == 8 and all(len(ruta) == 12 for ruta in r.values())


def test_acomodar_por_orden_y_sku():
    a = orden.acomodar(VIDEO, SISTEMA.plan)
    assert a["recorrido"] == "serpentina desde arriba a la izquierda"
    assert len(a["ruta"]) == 12
    assert "E5" not in a["etiquetas"]  # no cabe en el orden: se descarta
    assert a["etiquetas"]["E6"] == "R2-P4"  # la etiqueta de otro SKU queda donde la pone el orden
    assert a["etiquetas"]["E7"] == "R2-P3" and a["etiquetas"]["E8"] == "R2-P1"
    assert "R2-P2" not in a["etiquetas"].values()


def test_acomodar_un_solo_tramo():
    # solo la repisa de abajo, recorrida de derecha a izquierda
    a = orden.acomodar([etiqueta("E1", "SKU-100936", 1), etiqueta("E2", "SKU-102560", 1),
                        etiqueta("E3", "SKU-100599", 1)], SISTEMA.plan)
    assert a["ruta"] == ["R3-P4", "R3-P3", "R3-P2"]
    assert orden.acomodar([etiqueta("E1", None, 1, lecturas=1)], SISTEMA.plan) is None


def test_varias_posiciones_seguidas_sin_etiqueta_son_lectura_dudosa():
    # la toma en la que el motor no leyó R2-P4 ni R2-P3 (la cámara bajó rápido de repisa)
    video = [e for e in VIDEO if e["id"] not in ("E5", "E6", "E7")]
    obs, recorrido = cruce_orden.observaciones({"etiquetas": video}, SISTEMA)
    d = cruce_orden.construir(obs, recorrido, EN_PESOS)
    tipos = {f"R{h['repisa']}-P{h['posicion']}": h["tipo"] for h in d["hallazgos"]}
    assert [tipos[c] for c in ("R2-P4", "R2-P3", "R2-P2")] == ["revisar"] * 3
    h = next(h for h in d["hallazgos"] if h["posicion"] == 4 and h["repisa"] == 2)
    assert "sin leer ninguna etiqueta" in h["descripcion"] and h["impacto_diario"] == 0


def test_en_pesos_redondea_al_centavo():
    s = cruce_orden.en_pesos(SISTEMA)
    muffin, cafe = s.productos["SKU-100664"], s.productos["SKU-101809"]
    assert (muffin.precio_anterior, muffin.precio_vigente) == (124.08, 134.58)  # 124.075 -> .08
    assert (cafe.precio_anterior, cafe.precio_vigente) == (80.33, 87.33)
    assert muffin.venta_diaria == SISTEMA.productos["SKU-100664"].venta_diaria


def test_precios_pesos_del_anaquel_armado(tmp_path):
    cafe, muffin = EN_PESOS.productos["SKU-100104"], EN_PESOS.productos["SKU-100664"]
    assert (cafe.precio_vigente, cafe.precio_anterior) == (271.07, 254.80)  # el de su etiqueta
    assert (muffin.precio_vigente, muffin.precio_anterior) == (134.58, 124.08)
    assert cafe.existencia == SISTEMA.productos["SKU-100104"].existencia  # inventario de la demo
    # sin precios_pesos.csv: precios.csv × 17.5
    for nombre in ("planograma.csv", "precios.csv", "inventario.csv"):
        shutil.copy(DIR_SISTEMA / nombre, tmp_path)
    assert cruce_orden.leer_sistema(tmp_path).productos["SKU-100104"].precio_vigente == 437.33


def test_identificar_producto_por_el_empaque():
    plan = {p.posicion: p for p in SISTEMA.plan}
    e11, e12, e8 = VIDEO[10], VIDEO[11], VIDEO[7]
    assert cruce_orden.identificar(e11, plan["R3-P3"], SISTEMA.productos) == "SKU-102199"
    assert cruce_orden.identificar(e12, plan["R3-P4"], SISTEMA.productos) is None  # es el suyo
    # el nombre del producto de la posición se lee en el empaque: no se juzga
    assert cruce_orden.identificar(e8, plan["R2-P1"], SISTEMA.productos) is None
    assert cruce_orden.identificar({"texto_producto": {}}, plan["R1-P1"], SISTEMA.productos) is None


@pytest.mark.parametrize("con_acomodo_del_motor", [False, True])
def test_cruce_por_orden(con_acomodo_del_motor):
    obs_libre = {"video": "celular.mp4", "fps": 60, "segundos_proceso": 48, "etiquetas": VIDEO}
    if con_acomodo_del_motor:
        obs_libre["planograma"] = orden.acomodar(VIDEO, SISTEMA.plan)
    obs, recorrido = cruce_orden.observaciones(obs_libre, SISTEMA)
    faltante = next(o for o in obs["posiciones"] if o["posicion"] == "R2-P2")
    assert not faltante["etiqueta_visible"] and faltante["cuadro"] == (420 + 40 + 600) // 2

    d = cruce_orden.construir(obs, recorrido, EN_PESOS, fps=60, prefijo="/motor/x")
    tipos = {f"R{h['repisa']}-P{h['posicion']}": h["tipo"] for h in d["hallazgos"]}
    # los errores sembrados del recorrido de demo (menos frentes, que aquí no se cuentan)
    assert tipos == {
        "R1-P1": "precio_anterior",  # leída una vez, pero es justo el precio anterior
        "R1-P3": "precio_anterior", "R2-P2": "etiqueta_faltante", "R2-P4": "etiqueta_otro_sku",
        "R3-P1": "hueco_con_inventario", "R3-P2": "hueco_agotado",
        "R3-P3": "producto_equivocado"}
    r = d["resumen"]
    assert (r["modo"], r["moneda"], r["recorrido"]) == ("orden", "$", recorrido)
    assert r["frase"].startswith("7 problemas en este anaquel · $")
    h = next(h for h in d["hallazgos"] if h["tipo"] == "precio_anterior" and h["posicion"] == 1)
    assert h["precio_sistema"] == 134.58 and "$134.58" in h["accion_sugerida"]
    assert h["evidencia_crop"] == "/motor/x/recortes/E1_etiqueta.jpg"
