"""Pruebas del modo sin estructura (sin video, modelos ni GPU).

    python -m pytest -q tests/
"""
import numpy as np
import pytest

from cruce import libre as cruce_libre
from motor import libre


def caja(x1, y1, x2, y2):
    return (x1, y1, x2, y2)


# ------------------------------------------------------------------ precios
@pytest.mark.parametrize("lineas, precio", [
    ([("$32.90", 0.97, caja(100, 60, 300, 140))], 32.90),
    ([("s33-90", 0.83, caja(100, 60, 300, 140))], 33.90),
    ([("S14.90", 0.91, caja(100, 60, 300, 140))], 14.90),
    # centavos en superíndice: caja aparte, más chica y arriba a la derecha
    ([("$33", 0.99, caja(100, 60, 220, 140)), ("90", 0.95, caja(225, 62, 270, 95))], 33.90),
    # se perdió el punto
    ([("3290", 0.9, caja(100, 60, 300, 140))], 32.90),
    # gana el número más alto (el precio por kilo es chico) y no cuentan los gramos
    ([("$1.20", 0.9, caja(10, 150, 80, 170)), ("$17.90", 0.9, caja(100, 60, 300, 140)),
      ("500g", 0.9, caja(10, 10, 80, 30))], 17.90),
    ([("ARROZ BLANCO 1KG", 0.9, caja(10, 10, 300, 40))], None),
])
def test_leer_precio(lineas, precio):
    p, _ = libre.leer_precio(lineas)
    assert p == precio


def test_tres_digitos_pegados_son_dudosos():
    _, c4 = libre.leer_precio([("3290", 0.9, caja(0, 0, 100, 50))])
    _, c3 = libre.leer_precio([("183", 0.9, caja(0, 0, 100, 50))])
    assert c3 < c4


def test_leer_nombre():
    lineas = [("ARROZ BLANCO 1KG", 0.95, caja(10, 10, 300, 40)),
              ("$32.90", 0.97, caja(100, 60, 300, 140)),
              ("PRECIO POR KG", 0.9, caja(10, 160, 120, 175))]
    assert libre.leer_nombre(lineas, 200) == "ARROZ BLANCO 1KG"


def test_parecido_tolera_ocr_y_orden():
    assert libre.parecido("ARROZ BLANCO", "BLANCO ARROZ") == 1.0
    assert libre.parecido("RROZBLANCO", "ARROZ BLANCO") >= 0.8
    assert libre.parecido("ARROZ BLANCO", "FRIJOL NEGRO") < 0.5


# ------------------------------------------------------------------ huecos
def test_hueco_zona_lisa_sin_productos():
    img = np.full((720, 1280, 3), 128, np.uint8)  # fondo de anaquel liso
    etiqueta = (500, 400, 640, 480)
    hueco, cob, tex = libre.evaluar_hueco(img, etiqueta, [])
    assert hueco is True and cob == 0
    # con un producto encima ya no es hueco
    hueco, cob, _ = libre.evaluar_hueco(img, etiqueta, [(480, 200, 660, 395)])
    assert hueco is False and cob > 0.5


def test_hueco_no_se_juzga_si_la_zona_no_se_ve():
    img = np.full((720, 1280, 3), 128, np.uint8)
    assert libre.evaluar_hueco(img, (500, 10, 640, 90), [])[0] is None   # pegada arriba
    assert libre.evaluar_hueco(img, (500, 400, 530, 420), [])[0] is None  # lejana


@pytest.mark.parametrize("texto, sku", [
    ("SKU-100664", "SKU-100664"), ("SKL-100131", "SKU-100131"), ("0L-100075", "SKU-100075"),
    ("-100131", "SKU-100131"), ("SKU 1OO664", "SKU-100664"),
    ("SKU-1005", None), ("980205978963", None), ("03/03/2026", None),
])
def test_leer_sku(texto, sku):
    assert libre.leer_sku([(texto, 0.9, (0, 0, 1, 1))]) == sku


def test_sin_etiquetas_quita_las_cajas_que_son_etiquetas():
    etiqueta = (500, 400, 700, 500)
    producto = (500, 150, 700, 395)           # encima de la etiqueta: se queda
    sobre_etiqueta = (520, 410, 720, 560)     # SKU-110K tomó la etiqueta por producto
    assert libre.sin_etiquetas([producto, sobre_etiqueta], [etiqueta]) == [producto]


def test_seguimiento_une_la_misma_etiqueta():
    def obs(cuadro, x):
        return libre.Observacion(cuadro, (x, 400, x + 140, 480), 30, 32.9, 0.9, "ARROZ", False,
                                 0.9, 0.1, np.zeros((1, 1, 3)), None)
    desplazamiento = np.array([[1, 0, -50], [0, 1, 0], [0, 0, 1]], float)  # cámara a la derecha
    indices = [0, 3, 6]
    homografias = {0: None, 3: desplazamiento, 6: desplazamiento}
    pistas = libre.seguir(indices, homografias, {0: [obs(0, 600)], 6: [obs(6, 500)]},
                          1280, 720, paciencia=48)
    assert len(pistas) == 1 and len(pistas[0].obs) == 2


# ------------------------------------------------------------------ cruce
def etiqueta(id_, precio, nombre=None, hueco=False, conf=0.9, acuerdo=1.0, lecturas=3):
    return {"id": id_, "nombre_leido": nombre, "precio_leido": precio, "confianza_precio": conf,
            "lecturas": lecturas, "lecturas_coinciden": lecturas, "acuerdo": acuerdo,
            "hueco": hueco, "cuadro": 24, "recorte_etiqueta": f"recortes/{id_}_etiqueta.jpg",
            "recorte_posicion": f"recortes/{id_}.jpg"}


def test_cruce_libre():
    obs = {"video": "ia.mp4", "fps": 24, "segundos_proceso": 20, "etiquetas": [
        etiqueta("E1", 33.90, "RROZBLANCO KG", lecturas=2),
        etiqueta("E2", 32.90, "ARROZ BLANCO 1KG", lecturas=7),
        etiqueta("E3", 15.90, hueco=True),
        etiqueta("E4", 18.83, conf=0.4, acuerdo=0.3),  # precio dudoso
    ]}
    d = cruce_libre.construir(obs, "/motor/x")
    tipos = {h["ubicacion"]: h["tipo"] for h in d["hallazgos"]}
    assert tipos == {"Etiqueta E1": "precio_inconsistente", "Etiqueta E3": "hueco"}
    h1 = next(h for h in d["hallazgos"] if h["ubicacion"] == "Etiqueta E1")
    assert h1["producto"] == "ARROZ BLANCO 1KG"  # el nombre de la etiqueta mejor leída
    assert h1["impacto_diario"] == pytest.approx(1.0 * cruce_libre.VENTA_SUPUESTA)
    assert h1["precio_sistema"] is None and h1["segundo"] == 1.0
    assert h1["evidencia_crop"] == "/motor/x/recortes/E1_etiqueta.jpg"
    h3 = next(h for h in d["hallazgos"] if h["ubicacion"] == "Etiqueta E3")
    assert h3["evidencia_crop"] == "/motor/x/recortes/E3.jpg"
    # la dudosa queda en ámbar y cuenta, pero no es hallazgo
    e4 = next(p for p in d["posiciones"] if p["ubicacion"] == "Etiqueta E4")
    assert e4["estado"] == "revisar" and e4["hallazgo_id"] is None
    r = d["resumen"]
    assert (r["modo"], r["moneda"], r["total_problemas"], r["lecturas_dudosas"]) == \
        ("libre", "$", 2, 1)
    assert r["frase"].startswith("2 problemas en este anaquel · $")


def test_hueco_con_precio_dudoso_usa_la_mediana():
    obs = {"fps": 30, "etiquetas": [etiqueta("E1", 10.0), etiqueta("E2", 20.0),
                                    etiqueta("E3", 99.0, hueco=True, acuerdo=0.4)]}
    h = cruce_libre.construir(obs)["hallazgos"][0]
    assert h["impacto_diario"] == pytest.approx(15.0 * cruce_libre.VENTA_SUPUESTA)
    assert "precio dudoso" in h["descripcion"]
