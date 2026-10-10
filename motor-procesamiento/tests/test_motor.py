"""Pruebas rápidas del motor (no necesitan video, modelos ni GPU).

    python -m pytest -q tests/
"""
import cv2
import numpy as np
import pytest

from motor import anotar, contrato, etiquetas, frentes, huecos, marcadores, ocr

PLAN = [contrato.Posicion(f"R{r}-P{k + 1}", 1, r, 30.0 * k, 30.0 * (k + 1),
                          contrato.ALTURA_REPISA_CM[r], 3) for r in (1, 2, 3) for k in range(4)]


def caja(x1, y1, x2, y2):
    return (x1, y1, x2, y2)


# ------------------------------------------------------------------ OCR
@pytest.mark.parametrize("textos, precio, sku", [
    ([("$7.09", 0.99, caja(10, 50, 300, 200)), ("Sku-100664", 0.9, caja(10, 210, 300, 260))],
     7.09, "SKU-100664"),
    # el detector parte el precio en el punto decimal
    ([("$24", 0.99, caja(10, 50, 200, 200)), ("99", 0.98, caja(230, 60, 330, 200))], 24.99, None),
    ([("$16.", 0.99, caja(10, 50, 250, 200)), (".99", 0.98, caja(240, 60, 360, 200))], 16.99, None),
    # "$" leído como "S" y letras por dígitos en el SKU
    ([("S2.39", 0.97, caja(10, 50, 300, 200)), ("SkU-1OO936", 0.9, caja(10, 210, 300, 260))],
     2.39, "SKU-100936"),
    # la fecha y el UPC no son precios
    ([("Vigente desde 2026-03-01", 0.9, caja(10, 290, 300, 315)),
      ("071010066409", 0.9, caja(320, 240, 500, 256))], None, None),
])
def test_interpretar(textos, precio, sku):
    p, _, s, _ = ocr.interpretar(textos)
    assert p == precio
    assert s == sku


def test_el_renglon_mas_alto_es_el_precio():
    textos = [("$1.50", 0.9, caja(10, 290, 100, 315)),   # texto chico
              ("$4.59", 0.95, caja(10, 50, 300, 200))]   # dígitos grandes
    assert ocr.interpretar(textos)[0] == 4.59


def test_votar():
    L = ocr.Lectura
    v = ocr.votar([L(1, "R1-P1", 7.09, 0.9, "SKU-100664", 0.9), L(2, "R1-P1", 7.09, 0.99),
                   L(3, "R1-P1", 1.09, 0.6), L(4, "R1-P1", None, 0.0, "SKU-100664", 0.8)])
    assert (v.precio, v.coinciden, v.sku, v.cuadro, v.lecturas) == (7.09, 2, "SKU-100664", 2, 3)
    assert v.confianza == pytest.approx((0.9 + 0.99) / 2)
    assert ocr.votar([]).precio is None


# ------------------------------------------------------------------ contrato
def test_ids_de_marcador():
    for s in (0, 1, 4):
        for r in (1, 2, 3):
            for k in range(3):
                assert contrato.decodificar_marcador(contrato.id_marcador(s, r, k)) == (s, r, k)


def test_posicion_de_etiqueta():
    # centro de la etiqueta de R2-P3: x = 75 cm, 1.75 cm bajo la superficie de 75 cm
    assert contrato.posicion_de_etiqueta(PLAN, 75.0, 73.25).posicion == "R2-P3"
    assert contrato.posicion_de_etiqueta(PLAN, 75.0, 90.0) is None


# ------------------------------------------------------------------ imagen sintética
def cuadro_sintetico(escala=18.0, x0_cm=-10.0, y0_cm=135.0):
    """Imagen de frente: 1 cm = `escala` px; (x0_cm, y0_cm) es la esquina sup-izq."""
    from simulador import graficos
    W, H = 2600, 1200
    img = np.full((H, W, 3), 175, np.uint8)

    def px(x, y):
        return int(round((x - x0_cm) * escala)), int(round((y0_cm - y) * escala))

    for k, xk in enumerate(contrato.MARCADOR_X_CM):
        m = graficos.dibujar_marcador(contrato.id_marcador(1, 1, k))
        lado = int(round(5 * escala * 500 / 400))
        m = cv2.resize(m, (lado, lado), interpolation=cv2.INTER_AREA)
        x, y = px(xk - 5 * 50 / 400, 120 + 5 * 50 / 400)
        img[y:y + lado, x:x + lado] = m
    et = graficos.dibujar_etiqueta("Prueba", 4.59, "SKU-101809")
    x1, y1 = px(72, 120)
    x2, y2 = px(78, 116.5)
    img[y1:y2, x1:x2] = cv2.resize(et, (x2 - x1, y2 - y1), interpolation=cv2.INTER_AREA)
    return img, px


def test_homografia_y_pixel_a_cm():
    img, px = cuadro_sintetico()
    h = marcadores.calcular_homografia(img, contrato.alturas_por_repisa(PLAN))
    assert h is not None and sorted(m.id for m in h.marcadores) == [24, 25, 26]
    for x_cm, y_cm in [(0, 120), (60, 100), (110, 130)]:
        u, v = px(x_cm, y_cm)
        x, y = marcadores.pixel_a_cm(h, u, v)
        assert x == pytest.approx(x_cm, abs=0.15) and y == pytest.approx(y_cm, abs=0.15)


def test_detectar_etiqueta():
    img, _ = cuadro_sintetico()
    h = marcadores.calcular_homografia(img, contrato.alturas_por_repisa(PLAN))
    dets = etiquetas.detectar_etiquetas(img, h, PLAN, indice=7)
    assert [(d.posicion, d.metodo, d.cuadro) for d in dets] == [("R1-P3", "color", 7)]
    assert dets[0].imagen.shape == (350, 600, 3)


def test_mancha_naranja_solida_no_es_etiqueta():
    img, px = cuadro_sintetico()
    x1, y1 = px(12, 120)
    x2, y2 = px(18, 116.5)
    img[y1:y2, x1:x2] = (0, 106, 255)  # mismo tamaño y lugar que una etiqueta, pero sólida
    h = marcadores.calcular_homografia(img, contrato.alturas_por_repisa(PLAN))
    assert [d.posicion for d in etiquetas.detectar_etiquetas(img, h, PLAN)] == ["R1-P3"]


# ------------------------------------------------------------------ huecos y frentes
def vista(n, cubre=0.0, visible=1.0, cuadro=0):
    return huecos.VistaPosicion(cuadro, visible, n, cubre, n == 0 or cubre >= huecos.COBERTURA_HUECO)


def test_hueco_por_mayoria():
    assert huecos.es_hueco([vista(0), vista(0), vista(1)])[0]
    assert not huecos.es_hueco([vista(0), vista(3), vista(3)])[0]
    # caja "hueco" que cubre casi toda la posición aunque haya un falso producto
    assert huecos.es_hueco([vista(1, 0.95), vista(1, 0.9), vista(3)])[0]
    # un frente con espacio libre al lado no es hueco
    assert not huecos.es_hueco([vista(1, 0.7), vista(1, 0.7)])[0]
    # solo cuentan los cuadros que ven la posición completa
    assert not huecos.es_hueco([vista(0, visible=0.6), vista(3)])[0]


def test_frentes_mediana():
    assert frentes.contar_frentes([vista(3), vista(2), vista(3), vista(3)]) == 3
    assert frentes.contar_frentes([vista(1, visible=0.6)]) == 1
    assert frentes.contar_frentes([]) == 0


# ------------------------------------------------------------------ video anotado
def test_interpolador():
    H0 = np.array([[1.0, 0, 0], [0, 1, 0], [0, 0, 1]])
    H1 = np.array([[1.0, 0, 120], [0, 1, 0], [0, 0, 1]])
    it = anotar.Interpolador({0: H0, 12: H1})
    assert it(6)[0, 2] == pytest.approx(60)
    assert it(12)[0, 2] == pytest.approx(120)
    assert it(500) is None
