"""Pruebas del asistente (cruce/chat.py) sin red: Gemini se sustituye por un falso.

    python -m pytest -q tests/
"""
import json

import pytest

from cruce import chat
from cruce import hallazgos as cruce
from cruce import libre as cruce_libre
from motor import contrato

PLAN = [contrato.Posicion(f"R1-P{k + 1}", 1, 1, 30.0 * k, 30.0 * (k + 1), 120.0, 3,
                          sku=f"SKU-00000{k + 1}", nombre=n)
        for k, n in enumerate(["Muffin", "Café"])]
PRODUCTOS = {
    "SKU-000001": cruce.Producto("SKU-000001", "Muffin", 7.69, 7.09, 24, 18),
    "SKU-000002": cruce.Producto("SKU-000002", "Café", 24.99, 23.49, 10, 6),
}
SISTEMA = cruce.Sistema(PLAN, PRODUCTOS)
CFG = chat.Config("clave-falsa", ("modelo-a", "modelo-b"), "embeddings-falso")


def obs(pos, **cambios):
    o = {"posicion": pos, "etiqueta_visible": True, "sku_leido": None, "precio_leido": 7.69,
         "confianza_precio": 0.98, "lecturas_coinciden": 6, "hueco": False,
         "frentes_vistos": 3, "cuadro": 60, "recorte_etiqueta": f"recortes/{pos}_etiqueta.jpg",
         "recorte_posicion": f"recortes/{pos}.jpg"}
    o.update(cambios)
    return o


@pytest.fixture
def corrida(tmp_path):
    """Corrida con contrato: R1-P1 con precio viejo y R1-P2 bien."""
    observaciones = {"video": "clip.mp4", "segundos_proceso": 9.5,
                     "posiciones": [obs("R1-P1", precio_leido=7.09), obs("R1-P2", precio_leido=24.99)]}
    (tmp_path / "observaciones.json").write_text(json.dumps(observaciones), encoding="utf-8")
    (tmp_path / "diagnostico.json").write_text(json.dumps({
        "cuadros_elegidos": 10, "tiempos_s": {"ocr": 3.0, "yolo": 1.5},
        "posiciones": {"R1-P1": {"lecturas": [
            {"cuadro": 5, "precio": 7.09, "conf": 0.99, "sku": "SKU-000001", "textos": ["$7.09"]},
            {"cuadro": 9, "precio": 7.09, "conf": 0.97, "sku": None, "textos": ["$7.0"]}]}}}),
        encoding="utf-8")
    (tmp_path / "README.md").write_text("# Motor\n\nIntro.\n\n## Dinero\n\nPrecio menor: "
                                        "diferencia × venta diaria.\n", encoding="utf-8")
    datos = cruce.construir(observaciones, SISTEMA)
    return chat.Corrida("demo", tmp_path, tmp_path, datos, {"id": "demo", "nombre": "clip.mp4"},
                        SISTEMA, [tmp_path / "README.md"])


def test_leer_env(tmp_path):
    ruta = tmp_path / ".env"
    ruta.write_text("# comentario\nAPIGEMINI='abc 123'\nexport GEMINI_MODELO=a, b\n\nX\n",
                    encoding="utf-8")
    assert chat.leer_env(ruta) == {"APIGEMINI": "abc 123", "GEMINI_MODELO": "a, b"}
    assert chat.leer_env(tmp_path / "no_existe") == {}


def test_configuracion_lee_el_env_de_la_raiz_y_el_entorno_gana(tmp_path, monkeypatch):
    for k in (*chat.VARIABLES_CLAVE, "GEMINI_MODELO", "GEMINI_EMBEDDINGS", "GEMINI_RAZONAMIENTO"):
        monkeypatch.delenv(k, raising=False)
    motor = tmp_path / "motor-procesamiento"
    motor.mkdir()
    (tmp_path / ".env").write_text("APIGEMINI=de-la-raiz\nGEMINI_MODELO=a, b\n", encoding="utf-8")
    cfg = chat.configuracion(motor)
    assert cfg.clave == "de-la-raiz" and cfg.modelos == ("a", "b") and cfg.razonamiento == "low"
    monkeypatch.setenv("GEMINI_API_KEY", "del-entorno")
    monkeypatch.setenv("APIGEMINI", "")
    assert chat.configuracion(motor).clave == "del-entorno"


def test_fragmentos_con_contrato(corrida):
    frags = chat.fragmentos(corrida)
    ids = [f.id for f in frags]
    assert ids[:3] == ["resumen", "R1-P1", "R1-P2"] and "motor" in ids
    assert "README#Dinero" in ids
    resumen, r1p1 = frags[0].texto, frags[1].texto
    assert "R1-P1 · precio_anterior (Etiqueta con precio viejo)" in resumen
    assert "- R1-P2 · ok · Café · US$24.99" in resumen
    # lo que dice el sistema y lo que vio el motor, sin rutas de archivos
    assert "precio_anterior: 7.09" in r1p1 and "venta_diaria: 18" in r1p1
    assert 'precios_por_lectura: {"7.09": 2}' in r1p1
    assert "recortes/" not in r1p1


def test_fragmentos_modo_libre(tmp_path):
    etiquetas = [
        {"id": "E1", "nombre_leido": "ARROZ", "precio_leido": 32.9, "confianza_precio": 0.95,
         "lecturas": 5, "lecturas_coinciden": 5, "acuerdo": 1.0, "hueco": True,
         "votos_hueco": [4, 1], "cuadro": 24, "recorte_etiqueta": "recortes/E1_etiqueta.jpg",
         "recorte_posicion": "recortes/E1.jpg"}]
    observaciones = {"video": "ia.mp4", "modo": "libre", "fps": 24.0, "etiquetas": etiquetas}
    (tmp_path / "observaciones_libre.json").write_text(json.dumps(observaciones), encoding="utf-8")
    datos = cruce_libre.construir(observaciones)
    c = chat.Corrida("x", tmp_path, tmp_path, datos, {"nombre": "ia.mp4", "detector": "libre"})
    resumen, e1 = chat.fragmentos(c)[:2]
    assert c.libre and e1.id == "E1" and e1.titulo == "Etiqueta E1"
    assert "Etiqueta E1 · hueco (Hueco en anaquel) · ARROZ · $197.40 al día" in resumen.texto
    assert "repisa:" not in e1.texto and "votos_hueco: [4, 1]" in e1.texto


def test_buscar():
    vectores = [[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]]
    assert chat.buscar([0.0, 1.0], vectores, 2) == [1, 2]


class GeminiFalso:
    """Embeddings: 1 en la dimensión de la primera palabra clave que aparece. El primer
    modelo de texto está saturado (503)."""
    CLAVES = ("precio", "café", "dinero")

    def __init__(self):
        self.llamadas = []

    def vector(self, texto):
        texto = texto.lower()
        i = next((k for k, c in enumerate(self.CLAVES) if c in texto), len(self.CLAVES))
        return [1.0 if k == i else 0.0 for k in range(len(self.CLAVES) + 1)]

    def __call__(self, modelo, metodo, cuerpo, clave, timeout):
        self.llamadas.append((modelo, metodo, cuerpo))
        if metodo == "batchEmbedContents":
            return {"embeddings": [{"values": self.vector(r["content"]["parts"][0]["text"])}
                                   for r in cuerpo["requests"]]}
        if modelo == "modelo-a":
            raise chat.ErrorGemini("modelo-a: saturado", 503)
        return {"modelVersion": "modelo-b-001", "candidates": [{"content": {"parts": [
            {"text": "pensando…", "thought": True}, {"text": "R1-P1 tiene el precio viejo."}]}}]}


def test_responder(corrida, monkeypatch):
    falso = GeminiFalso()
    monkeypatch.setattr(chat, "_post", falso)
    historial = [{"rol": "asistente", "texto": "Hola"}, {"rol": "usuario", "texto": "¿Y el café?"},
                 {"rol": "asistente", "texto": "Está bien."}]
    r = chat.responder(corrida, "¿Qué precio está mal?", historial, CFG)

    assert r["respuesta"] == "R1-P1 tiene el precio viejo." and r["modelo"] == "modelo-b-001"
    assert r["fuentes"][0]["id"] == "resumen"
    assert len(r["fuentes"]) == 6  # hay menos fragmentos que K_FRAGMENTOS: van todos
    _, _, cuerpo = falso.llamadas[-1]
    roles = [m["role"] for m in cuerpo["contents"]]
    assert roles == ["user", "model", "user"]  # el saludo del asistente no puede ir primero
    assert "Pregunta: ¿Qué precio está mal?" in cuerpo["contents"][-1]["parts"][0]["text"]
    assert cuerpo["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "low"
    assert (corrida.carpeta / "chat_indice.json").exists()

    # segunda pregunta: los fragmentos ya están en la caché, solo se embebe la consulta
    falso.llamadas.clear()
    chat.responder(corrida, "¿Cuánto dinero?", [], CFG)
    embebidos = [c for c in falso.llamadas if c[1] == "batchEmbedContents"]
    assert len(embebidos) == 1 and len(embebidos[0][2]["requests"]) == 1


def test_errores(corrida, monkeypatch, tmp_path):
    with pytest.raises(chat.SinClave):
        chat.responder(corrida, "hola", [], chat.Config(None, ("a",), "e"))

    def clave_mala(modelo, metodo, cuerpo, clave, timeout):
        raise chat.ErrorGemini("API key not valid", 400)
    monkeypatch.setattr(chat, "_post", clave_mala)
    with pytest.raises(chat.ErrorGemini, match="API key"):
        chat.responder(corrida, "hola", [], CFG)

    with pytest.raises(chat.CorridaNoDisponible):
        chat.cargar_corrida(tmp_path, "../fuera")
    (tmp_path / "analisis/a1").mkdir(parents=True)
    (tmp_path / "analisis/a1/meta.json").write_text('{"status": "procesando"}', encoding="utf-8")
    with pytest.raises(chat.CorridaNoDisponible) as e:
        chat.cargar_corrida(tmp_path, "a1")
    assert e.value.status == 409
