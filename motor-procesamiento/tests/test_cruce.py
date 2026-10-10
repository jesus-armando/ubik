"""Pruebas del cruce con el sistema (sin video, modelos ni GPU).

    python -m pytest -q tests/
"""
import pytest

from cruce import hallazgos as cruce
from motor import contrato

PLAN = [contrato.Posicion(f"R1-P{k + 1}", 1, 1, 30.0 * k, 30.0 * (k + 1), 120.0, 3,
                          sku=f"SKU-00000{k + 1}") for k in range(4)]
PRODUCTOS = {
    "SKU-000001": cruce.Producto("SKU-000001", "Muffin", 7.69, 7.09, 24, 18),
    "SKU-000002": cruce.Producto("SKU-000002", "Café", 24.99, 23.49, 10, 6),
    "SKU-000003": cruce.Producto("SKU-000003", "Wrap", 8.99, 8.49, 0, 9),
    "SKU-000004": cruce.Producto("SKU-000004", "Bagel", 2.39, 2.19, 14, 16),
}
SISTEMA = cruce.Sistema(PLAN, PRODUCTOS)


def obs(pos="R1-P1", **cambios):
    o = {"posicion": pos, "etiqueta_visible": True, "sku_leido": None, "precio_leido": None,
         "confianza_precio": 0.98, "lecturas_coinciden": 6, "hueco": False,
         "frentes_vistos": 3, "cuadro": 60, "recorte_etiqueta": f"recortes/{pos}_etiqueta.jpg",
         "recorte_posicion": f"recortes/{pos}.jpg"}
    o.update(cambios)
    return o


@pytest.mark.parametrize("pos, cambios, tipo", [
    ("R1-P1", dict(sku_leido="SKU-000001", precio_leido=7.69), None),
    ("R1-P1", dict(sku_leido="SKU-000001", precio_leido=7.09), "precio_anterior"),
    ("R1-P1", dict(precio_leido=6.50), "precio_distinto"),
    ("R1-P1", dict(precio_leido=6.50, confianza_precio=0.4), "revisar"),
    ("R1-P1", dict(precio_leido=6.50, lecturas_coinciden=1), "revisar"),
    # justo el precio anterior no sale de una mala lectura: con una basta
    ("R1-P1", dict(precio_leido=7.09, lecturas_coinciden=1), "precio_anterior"),
    ("R1-P1", dict(precio_leido=None), "revisar"),
    ("R1-P1", dict(etiqueta_visible=False), "etiqueta_faltante"),
    ("R1-P1", dict(sku_leido="SKU-000004", precio_leido=2.39), "etiqueta_otro_sku"),
    ("R1-P1", dict(precio_leido=7.69, sku_producto="SKU-000002"), "producto_equivocado"),
    ("R1-P1", dict(precio_leido=7.69, frentes_vistos=1), "frentes_bajos"),
    ("R1-P1", dict(precio_leido=7.69, frentes_vistos=None), None),  # zona no vista
    ("R1-P1", dict(hueco=True, frentes_vistos=0), "hueco_con_inventario"),
    ("R1-P3", dict(hueco=True, frentes_vistos=0), "hueco_agotado"),
])
def test_clasificar(pos, cambios, tipo):
    p = next(p for p in PLAN if p.posicion == pos)
    assert cruce.clasificar(obs(pos, **cambios), p, PRODUCTOS[p.sku]) == tipo


def test_impacto():
    p1, p3 = PLAN[0], PLAN[2]
    muffin, wrap = PRODUCTOS["SKU-000001"], PRODUCTOS["SKU-000003"]
    # precio menor: diferencia × piezas al día
    assert cruce.impacto_diario("precio_anterior", obs(precio_leido=7.09), p1, muffin) == \
        pytest.approx(0.60 * 18)
    # hueco: la venta diaria completa
    assert cruce.impacto_diario("hueco_agotado", obs("R1-P3", hueco=True), p3, wrap) == \
        pytest.approx(9 * 8.99)
    # 1 de 3 frentes: 20 % × 2/3 de la venta diaria
    assert cruce.impacto_diario("frentes_bajos", obs(frentes_vistos=1), p1, muffin) == \
        pytest.approx(18 * 7.69 * 0.2 * 2 / 3)
    assert cruce.impacto_diario("revisar", obs(), p1, muffin) == 0


def test_construir_y_nuevos():
    base = cruce.construir({"video": "r.mp4", "segundos_proceso": 30, "posiciones": [
        obs("R1-P1", sku_leido="SKU-000001", precio_leido=7.09),
        obs("R1-P2", precio_leido=24.99),
        obs("R1-P3", hueco=True, frentes_vistos=0)]}, SISTEMA, fps=30)
    assert [h["tipo"] for h in base["hallazgos"]] == ["hueco_agotado", "precio_anterior"]
    assert base["resumen"]["total_problemas"] == 2
    assert base["resumen"]["frase"].startswith("2 problemas en este anaquel · US$")
    assert len(base["posiciones"]) == 3  # R1-P4 no se vio: no se reporta
    h = base["hallazgos"][1]
    assert (h["repisa"], h["posicion"], h["segundo"]) == (1, 1, 2.0)
    assert h["evidencia_crop"] == "/salida/recortes/R1-P1_etiqueta.jpg"
    assert base["hallazgos"][0]["evidencia_crop"] == "/salida/recortes/R1-P3.jpg"

    tarjeta = cruce.construir({"posiciones": [
        obs("R1-P1", sku_leido="SKU-000001", precio_leido=7.09),
        obs("R1-P2", etiqueta_visible=False, recorte_etiqueta=None)]}, SISTEMA, fps=10,
        prefijo="/motor/x")
    nuevos = cruce.nuevos(base, tarjeta)
    assert [(h["posicion"], h["tipo"]) for h in nuevos] == [(2, "etiqueta_faltante")]
    assert nuevos[0]["evidencia_crop"] == "/motor/x/recortes/R1-P2.jpg"
    assert nuevos[0]["segundo"] == 6.0
