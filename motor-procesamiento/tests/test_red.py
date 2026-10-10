"""Pruebas de la proyección a la red (cruce/red.py).

    python -m pytest -q tests/test_red.py
"""
import pytest

from cruce import red


def hallazgo(tipo, impacto, sku="SKU-000001", **extra):
    h = {"tipo": tipo, "impacto_diario": impacto, "sku": sku, "producto": f"Producto {sku}",
         "precio_etiqueta": 7.09, "precio_sistema": 7.69}
    h.update(extra)
    return h


def salida(*hallazgos, **resumen):
    return {"resumen": {"fecha_escaneo": "2026-10-10T10:58:46+00:00", "video": "r.mp4",
                        **resumen},
            "posiciones": [], "hallazgos": list(hallazgos)}


def test_solo_se_proyecta_el_precio_anterior():
    datos = red.construir(salida(
        hallazgo("hueco_con_inventario", 80.91, "SKU-000003"),
        hallazgo("precio_anterior", 10.80),
        hallazgo("precio_anterior", 10.00, "SKU-000002"),
        hallazgo("precio_distinto", 5.00, "SKU-000004"),
        hallazgo("hueco_agotado", 62.86, "SKU-000005"),
        hallazgo("hueco_con_inventario", 9.09, "SKU-000006"),
        hallazgo("revisar", 0.0, "SKU-000007"),
    ))
    r = datos["red"]
    assert r["sistemico_diario"] == pytest.approx(20.80)
    assert r["local_diario"] == pytest.approx(80.91 + 5.00 + 62.86 + 9.09)
    assert r["medido_diario"] == pytest.approx(r["sistemico_diario"] + r["local_diario"])
    assert (r["problemas_sistemicos"], r["problemas_locales"]) == (2, 4)  # revisar no cuenta
    assert [s["sku"] for s in datos["sistemicos"]] == ["SKU-000001", "SKU-000002"]
    assert datos["sistemicos"][0]["peor_caso_diario"] == pytest.approx(10.80 * 37)
    # locales agrupados por tipo, de mayor a menor dinero
    assert [(g["tipo"], g["cantidad"]) for g in datos["locales"]] == [
        ("hueco_con_inventario", 2), ("hueco_agotado", 1), ("precio_distinto", 1)]
    assert datos["locales"][0]["impacto_diario"] == pytest.approx(90.00)
    assert r["fecha_corte"] == "2026-10-10"


def test_escenarios_sobre_las_otras_tiendas():
    datos = red.construir(salida(hallazgo("precio_anterior", 20.80)), tiendas=38)
    assert datos["red"]["otras_tiendas"] == 37
    esperado = {"bajo": 4, "central": 9, "alto": 19, "peor_caso": 37}  # 10, 25, 50 y 100 %
    for e in datos["escenarios"]:
        assert e["tiendas"] == esperado[e["nombre"]]
        assert e["diario"] == pytest.approx(e["tiendas"] * 20.80)
        assert e["mensual"] == pytest.approx(e["diario"] * red.DIAS_MES)


def test_sin_errores_de_lista_no_hay_proyeccion():
    # modo sin estructura: no hay sistema, así que no hay precio anterior
    datos = red.construir(salida(hallazgo("hueco", 33.9), hallazgo("precio_inconsistente", 6.0),
                                 modo="libre", moneda="$"))
    assert datos["red"]["moneda"] == "$"
    assert datos["red"]["sistemico_diario"] == 0
    assert datos["sistemicos"] == []
    assert all(e["diario"] == 0 for e in datos["escenarios"])
    assert datos["red"]["local_diario"] == pytest.approx(39.9)
