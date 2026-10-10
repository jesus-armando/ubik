# Motor de procesamiento (Persona 2)

Un comando recibe el video del recorrido y dice, por cada posición del anaquel, qué precio
y SKU tiene la etiqueta, si hay hueco y cuántos frentes hay. P4 compara contra el sistema
y calcula el dinero.

```bash
python -m motor.pipeline --video video/recorrido_realista.mp4 \
    --planograma datos/sistema/planograma.csv --salida salida/
```

Salidas (esquema exacto en [CONTRATO.md](CONTRATO.md)):

- `salida/observaciones.json`: interfaz con P4.
- `salida/recorrido_anotado.mp4`: H.264, 1920 px, mismos cuadros y fps que la entrada;
  verde = producto, rojo = hueco, naranja = etiqueta.
- `salida/recortes/`: `<posicion>_etiqueta.jpg` (600 × 350, enderezada) y `<posicion>.jpg`.
- `salida/diagnostico.json`: tiempos por etapa y todas las lecturas por cuadro (no es
  parte del contrato; sirve para depurar).

Regla de oro: `motor/` nunca lee `escena/` ni `video/verdad/`. Solo
`motor/preparar_yolo.py` usa `video/verdad/` como anotaciones para entrenar.

## Instalación

Python 3.12 (PaddlePaddle aún no publica ruedas para 3.14). Ver `requirements.txt`:

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python torch torchvision --index-url https://download.pytorch.org/whl/cu130
uv pip install --python .venv/bin/python -r requirements.txt
uv pip uninstall --python .venv/bin/python opencv-python opencv-contrib-python
uv pip install --python .venv/bin/python opencv-contrib-python==4.10.0.84
```

Dos trampas que ya están resueltas en `requirements.txt`:

- **PaddlePaddle 3.3** truena en CPU con oneDNN (`ConvertPirAttribute2RuntimeAttribute
  not support`). Con **3.2.2** oneDNN funciona y el OCR es ~2.5× más rápido. Si alguien
  instala 3.3, `motor/ocr.py` lo detecta y se recarga sin oneDNN (más lento, pero corre).
- Ultralytics instala `opencv-python` y PaddleX fija `opencv-contrib-python`; los dos
  escriben la misma carpeta `cv2`. Hay que dejar solo uno.

Los modelos de PP-OCRv5 se bajan solos la primera vez (`~/.paddlex/official_models/`).

## Módulos (orden del PDF)

| # | Archivo | Qué hace |
|---|---|---|
| 0 | `entrenamiento/sku110k.py` | Sustituye el Colab: YOLO nano con 1,500 imágenes de SKU-110K, 30 épocas, 640, clase `producto`; reanudable; deja `modelos/sku110k.pt` y muestra mAP50 |
| 1 | `motor/cuadros.py` | El cuadro más nítido de cada ventana de 12 (varianza del Laplaciano) |
| 2 | `motor/marcadores.py` | ArUco `DICT_4X4_100` con `cv2.aruco.ArucoDetector`, homografía px → cm, `pixel_a_cm(cuadro, x, y)` |
| 3 | `motor/etiquetas.py` | Borde naranja en HSV + contornos + `approxPolyDP`, enderezado a 600 × 350, posición por la x en cm |
| 4 | `motor/ocr.py` | PaddleOCR 3.x (PP-OCRv5) cargado una vez, precio y SKU por expresión regular, votación entre cuadros |
| 5 | `motor/preparar_yolo.py`, `entrenamiento/entrenar_yolo.py`, `motor/huecos.py`, `motor/frentes.py` | Verdad → YOLO (1 de cada 5, 80/20 por pasada), entrenamiento de 40 épocas (sustituye el notebook), huecos por mayoría, frentes por mediana |
| 6 | `motor/anotar.py` | Video anotado y recortes |
| 7 | `motor/pipeline.py` | Une todo, mide el tiempo y escribe `observaciones.json` |
| H14 | `motor/identificar.py` | Opcional (`--catalogo DIR`): qué producto hay, con DINOv2 y similitud coseno |

Pruebas de cada módulo por separado:

```bash
python -m motor.cuadros video/recorrido_realista.mp4
python -m motor.marcadores video/cuadros/000001.png    # debug/marcadores_000001.png con rejilla de 10 cm
python -m motor.etiquetas video/cuadros/000001.png     # debug/etiqueta_<pos>.png enderezadas
python -m motor.ocr debug/etiqueta_R1-P1.png
```

## Datos de prueba (sustituyen a P1 y P4 mientras no lleguen)

En el repositorio no había video, planograma ni verdad, así que `simulador/` los genera
siguiendo el mismo contrato. Cuando lleguen los de P1 y P4, se usan esos y nada del motor
cambia.

```bash
python -m simulador.datos_prueba            # planograma, escena con los 8 errores, 4 tarjetas, PNG
python -m simulador.render --escena escena/escena.json --planograma datos/sistema/planograma.csv \
    --empaques escena/empaques --etiquetas escena/etiquetas --video video/recorrido.mp4 \
    --verdad video/verdad --primer-cuadro video/cuadros/000001.png
python -m simulador.realismo video/recorrido.mp4 video/recorrido_realista.mp4
python -m simulador.tarjetas                # video/tarjetas/<tarjeta>.mp4 (una pasada, ~10 s)
python -m simulador.escenas_entrenamiento --n 10   # escenas al azar para entrenar YOLO
```

El render es una cámara estenopeica con los parámetros de P1 (sensor de 36 mm, focal de
21.5 mm, 80 cm, 3 pasadas en serpentina a 0.3 m/s, 3840 × 2160 a 30 fps: 693 cuadros,
23.1 s) que pinta el anaquel con caras planas texturizadas: repisas, poste, panel
perforado, cajas de 8 × 8 cm con su empaque, etiquetas y marcadores. La verdad por cuadro
sale de proyectar cada objeto, igual que en el script de Blender.

## Integración con el tablero (Road2Tech/Frontend)

El tablero lee `hallazgos.json` (lo que dice el sistema contra lo que vio el motor, con el
dinero) y llama a la API de P4 en el modo jurado. Ninguno de los dos existía, así que
`cruce/` los sustituye con el mismo contrato, igual que `simulador/` sustituye a P1. Cuando
lleguen los de P4, el tablero apunta a su API (`P4_API_URL`) y el motor no cambia.

```bash
# 1. Recorrido completo (con --catalogo también sale el producto equivocado de R3-P3)
python -m motor.pipeline --video video/recorrido_realista.mp4 \
    --planograma datos/sistema/planograma.csv --salida salida/ --catalogo escena/empaques
# 2. Tarjetas del jurado: son el "resultado de ensayo" si la API no responde
for t in precio_viejo etiqueta_otro_sku etiqueta_quitada producto_retirado; do
  python -m motor.pipeline --video video/tarjetas/$t.mp4 \
      --planograma datos/sistema/planograma.csv --salida salida_tarjetas/$t/
done
# 3. Cruce y copia al tablero (antes de npm run build: Next solo sirve lo que había al compilar)
python -m cruce.publicar --web ../Road2Tech/Frontend/public
# 4. API del motor en http://localhost:8000 (déjala corriendo durante la demo)
python -m cruce.api
# 5. Tablero
cd ../Road2Tech/Frontend && npm run build && npm start
```

**Videos nuevos (p. ej., del dron): desde el tablero, pantalla "Subir video"** (`/analizar`).
Se arrastra el archivo, se elige el detector (anaquel de la demo, anaquel real con
SKU-110K, o sin estructura para videos sin marcadores: ver abajo) y si se identifica el producto; la API guarda el video en `analisis/<id>/`, corre
el motor completo (con video anotado) y el cruce, y al terminar ese análisis queda **activo**:
Resumen, Recorrido, Anaquel y Hallazgos lo muestran en la siguiente carga. Desde el
historial de esa pantalla se cambia cuál se muestra o se regresa al recorrido de demo. Si la
API está apagada, el tablero muestra el demo de `public/salida/`. El modo jurado siempre
compara contra el demo (`salida/`). Si el video no trae marcadores ArUco, el análisis sale
como fallido con la razón y el tablero no cambia.

| Archivo | Qué hace |
|---|---|
| `cruce/hallazgos.py` | `observaciones.json` + `datos/sistema/` (planograma, `precios.csv`, `inventario.csv`) → `hallazgos.json` con el esquema de `Frontend/types/hallazgos.ts` |
| `cruce/publicar.py` | Escribe `public/salida/` (hallazgos, recortes, `recorrido_anotado.mp4`), `public/red.json` y `public/ensayos/<tarjeta>/` |
| `cruce/red.py` | `hallazgos.json` → `red.json` de la pantalla "Impacto en red": solo proyecta a las otras 37 tiendas las etiquetas con el precio de la lista anterior (nacen en el corporativo), en escenarios de 10, 25, 50 y 100 % de las tiendas; lo demás se queda como medido en el anaquel |
| `cruce/api.py` | `POST /procesar {"tarjeta"}` corre el motor sobre `video/tarjetas/<tarjeta>.mp4` en otro proceso (`--progreso`, `--sin-video`); `GET /estado` da el paso (1 eligiendo cuadros, 2 leyendo etiquetas, 3 comparando) y al final el **hallazgo nuevo**: el que no estaba en `salida/`. Sirve los recortes en `/archivos/...` (el tablero los pide por `/motor/...`). Solo biblioteca estándar |
| `cruce/api.py` (videos subidos) | `POST /analisis?nombre=&detector=anaquel\|sku110k&identificar=1` con el video como cuerpo; `GET /analisis`, `GET /analisis/<id>` (paso y progreso), `GET /analisis/activo` (el `hallazgos.json` que lee el tablero), `GET /analisis/activo/red` (su `red.json`), `POST /analisis/<id>/activar` (`demo` para el recorrido de demo), `DELETE /analisis/<id>`; el video anotado se sirve con Range |

Reglas del cruce (una por posición, en este orden): hueco → `hueco_con_inventario` si el
sistema tiene existencia, si no `hueco_agotado`; sin etiqueta → `etiqueta_faltante`; SKU
de la etiqueta distinto → `etiqueta_otro_sku`; producto identificado distinto (solo con
`--catalogo`) → `producto_equivocado`; etiqueta ilegible, o precio que no cuadra con
confianza < 0.6 o < 2 lecturas → `revisar`; precio = anterior → `precio_anterior`; otro
precio → `precio_distinto`; frentes < esperados → `frentes_bajos` (`null` no cuenta).

Dinero al día (supuestos de prueba, en `cruce/hallazgos.py`): precio de etiqueta menor →
diferencia × piezas vendidas al día; sin etiqueta o precio mayor → 25 % de la venta diaria;
hueco o producto equivocado → la venta diaria completa; pocos frentes → 20 % de la venta
diaria × faltantes ÷ esperados; `revisar` → 0. Con los datos de prueba salen los 8 errores
sembrados: **US$285.15 al día**, y cada tarjeta del jurado da exactamente su error nuevo
(R2-P1 precio viejo, R2-P3 etiqueta de otro producto, R1-P2 sin etiqueta, R3-P4 hueco con
inventario) en 9–13 s.

## Modo sin estructura (videos de IA o del celular)

Para videos que no traen nada del contrato: sin marcadores ArUco, sin etiquetas de borde
naranja ni SKU, sin planograma (p. ej. los de `../videos_ia/`, generados con IA). En el
tablero: "Subir video" → detector **Sin estructura**. Por línea de comandos:

```bash
python -m motor.libre --video ../videos_ia/gemini_generated_video_ea815464.mp4 --salida salida_libre/
python -m cruce.libre --salida-motor salida_libre/    # -> salida_libre/hallazgos.json
```

| Archivo | Qué hace |
|---|---|
| `motor/libre.py` | ~8 cuadros/s: productos con SKU-110K y movimiento de la cámara (ORB + homografía). ~2 cuadros/s (el más nítido de cada ventana): OCR del cuadro a 1920 px; un texto con forma de precio sobre papel claro es una etiqueta, que se recorta, se amplía y se relee (precio con centavos en superíndice y nombre). Cada etiqueta se sigue entre cuadros compensando el movimiento y se vota precio, nombre y hueco. Escribe `observaciones_libre.json`, `recortes/`, `recorrido_anotado.mp4` y `diagnostico.json` |
| `cruce/libre.py` | Cada etiqueta seguida es una posición. Hallazgos: **hueco** (encima de la etiqueta no hay producto: YOLO no ve nada y la zona es lisa) y **mismo producto con precios distintos** (dos etiquetas con nombre parecido y precios distintos, ambos leídos con seguridad). Las etiquetas con precio dudoso quedan en ámbar y en "lecturas a verificar", sin contar como problema |

Sin sistema de la tienda no hay precio vigente, inventario ni ventas: el dinero es una
**estimación** con el precio leído y una venta supuesta de 6 piezas al día por posición
(`VENTA_SUPUESTA` en `cruce/libre.py`), y el tablero lo dice en el aviso superior. Los
montos se muestran con `$` (el símbolo de la etiqueta), no `US$`.

Con los videos de `../videos_ia/` (720p, 24 fps, 10 s; ~25–30 s de proceso cada uno):

| Video | Qué muestra | Resultado |
|---|---|---|
| `…ea815464` | Etiquetas de cerca | 7 etiquetas leídas (ARROZ BLANCO, FRIJOL NEGRO, ACEITE VEGETAL, PASTA FIDEOS, AZÚCAR BLANCA…) y **ARROZ BLANCO a $33.90 y a $32.90** |
| `…68a7f2d8` | Góndola con huecos | **2 huecos** sobre etiquetas; 11 etiquetas, 8 con precio dudoso (etiquetas de ~100 px: los centavos en superíndice no se alcanzan a leer) |
| `…41d44c74` | Pasillo y botanas | Etiquetas de $3.49 y $5.49 leídas; sin problemas |

Límites: el precio de etiquetas chicas o borrosas sale como dudoso (es lo esperado, no un
error); la etiqueta es la unidad, así que un hueco sin etiqueta debajo no se reporta; y si
la cámara salta (corte de escena) las pistas empiezan de nuevo.

### Sin marcadores, con el planograma de la demo (anaquel armado a mano)

Para el anaquel de la demo armado sin marcadores ArUco (p. ej. en un pizarrón, con fotos de
los productos y las etiquetas impresas en pesos) y grabado con el celular. En el tablero:
detector **Sin estructura** → "Comparar con el planograma de la demo". Por línea de comandos:

```bash
python -m motor.libre --video celular.mp4 --salida salida_orden/ --planograma datos/sistema/planograma.csv
python -m cruce.orden --salida-motor salida_orden/    # -> salida_orden/hallazgos.json
```

| Archivo | Qué hace |
|---|---|
| `motor/libre.py` | Además lee el SKU impreso en cada etiqueta y las palabras impresas encima (el nombre en el empaque), y descarta las cajas de SKU-110K que caen sobre una etiqueta. Con `--planograma`, el video rotula cada etiqueta con su posición y no dibuja las que no se acomodaron |
| `motor/orden.py` | Acomoda las etiquetas en el planograma alineando la secuencia del video con la del recorrido, como un diff: SKU leído (mucho peso), nombre (algo) y orden. Prueba serpentina y repisa por repisa, desde arriba o abajo y desde cada lado, y se queda con la que mejor alinea. Una etiqueta que no cabe en el orden (la misma vista otra vez, un número suelto) se descarta |
| `cruce/orden.py` | Escribe `observaciones.json` con el contrato del modo con marcadores y aplica las reglas de `cruce/hallazgos.py` contra `datos/sistema/` con los precios en pesos de `precios_pesos.csv` (un SKU que no esté ahí: `precios.csv` × 17.5). Una posición por la que pasó la cámara sin etiqueta es **etiqueta faltante**; si encima de la etiqueta se lee el nombre de otro producto del catálogo y no el de la posición, **producto equivocado** |
| `datos/sistema/precios_pesos.csv` | Precios del anaquel armado, en pesos, para que se parezca al recorrido de demo: el precio vigente es el de su etiqueta impresa (y el anterior guarda la proporción de `precios.csv`), salvo R1-P1 y R1-P3, cuyas etiquetas traen el precio anterior (US$ × 17.5), y los productos sin etiqueta propia (US$ × 17.5). Inventario y ventas son los de la demo |

Con `VID_20261010_102108.mp4` (celular, 1080p a 60 fps, 17 s; ~50 s de proceso) se leen las 11
etiquetas con su SKU, se descarta la lectura suelta que antes salía como hueco y salen 7 de los
8 errores sembrados, igual que en el recorrido de demo: R1-P1 y R1-P3 con precio anterior,
R2-P2 sin etiqueta, R2-P4 con la etiqueta de 12 Bagels, R3-P1 hueco con inventario, R3-P2
agotado y R3-P3 con Chicken Croissant (**$3,511.18 al día**). El que falta es R1-P4 con 1 de 3
frentes: en este modo no se cuentan frentes. R1-P2, R1-P4, R2-P1, R2-P3 y R3-P4 salen correctas.

Con la otra toma, `VID_20261010_101438.mp4`, el motor no alcanza a leer las etiquetas de
R2-P4 y R2-P3 (la cámara baja rápido de repisa). Cuando faltan dos o más posiciones seguidas
(`SIN_LEER`) no se reportan como etiqueta faltante sino como lectura dudosa: lo más probable
es que el video no las leyó. Los demás errores salen igual.

Para que sirva hay que recorrer las repisas en orden, sin saltarse posiciones ni regresar, y
que se alcance a leer el SKU de las etiquetas.

## Asistente: preguntas sobre una corrida (Gemini)

En el tablero, pantalla **Asistente** (`/asistente`; desde "Subir video", "Preguntar" en
cada análisis): se elige la corrida (el recorrido de demo o un video subido) y se le pregunta
en español, p. ej. "¿qué corrijo primero?", "¿por qué R2-P3 es dudosa?" o "¿qué etapa del
motor tardó más?". Necesita la API corriendo y la clave de Gemini en el `.env` de la raíz del
repositorio (está en `.gitignore`); se relee en cada pregunta, sin reiniciar la API:

```bash
echo 'APIGEMINI=tu-clave' >> ../.env
python -m cruce.chat --corrida demo --fuentes "¿Qué problema cuesta más?"   # sin tablero
```

| Archivo | Qué hace |
|---|---|
| `cruce/chat.py` | RAG: parte la corrida en fragmentos (resumen con todas las posiciones y hallazgos; una ficha por posición o etiqueta con lo que dice el tablero, el planograma, el sistema, lo que vio el motor y el diagnóstico de sus lecturas; tiempos del motor; secciones de este README y de `CONTRATO.md`), los vuelve vectores con `gemini-embedding-2` (caché en `<corrida>/chat_indice.json`), busca los 6 más parecidos a la pregunta y se los pasa a Gemini junto con el resumen y la conversación. Responde con las fuentes que usó |
| `cruce/api.py` | `POST /analisis/<id>/chat` (`demo` para el recorrido de demo) y `GET /chat` (si hay clave) |

Modelos: `gemini-3.5-flash` con razonamiento `low` (2–5 s por respuesta); si está saturado
pasa a `gemini-3.5-flash-lite` y luego a `gemini-3.1-flash-lite`. Se cambian con
`GEMINI_MODELO` (lista separada por comas), `GEMINI_EMBEDDINGS` y `GEMINI_RAZONAMIENTO` en el
mismo `.env`. Lo que se manda a Gemini son los datos de la corrida, no el video ni los recortes.

## Entrenamiento

Los modelos ya están entrenados (`modelos/`), así que los datos de entrenamiento
(`datasets/`, `datos_entrenamiento/`, `yolo11n.pt`) y las bitácoras (`runs/`) están en
`../no_usado/motor-procesamiento/`. Antes de reentrenar, regrésalos:

```bash
for d in datasets datos_entrenamiento yolo11n.pt; do mv ../no_usado/motor-procesamiento/$d .; done
```

```bash
# Detector del anaquel (etiqueta, producto, hueco). Con la verdad de P1:
python -m motor.preparar_yolo --fuente video/verdad video/recorrido_realista.mp4
# Con las escenas al azar del simulador (lo que se usó aquí):
python -m motor.preparar_yolo --cada 2 $(for k in 0 1 2 3 4 5 6 7 8 9; do \
    echo --fuente datos_entrenamiento/escena_0$k/verdad datos_entrenamiento/escena_0$k/recorrido_realista.mp4; done)
python -m entrenamiento.entrenar_yolo        # -> modelos/anaquel.pt

# Detector general para el clip real (H18)
python -m entrenamiento.sku110k              # -> modelos/sku110k.pt
python -m motor.pipeline --video clip_real.mp4 --planograma datos/sistema/planograma_real.csv \
    --modelo modelos/sku110k.pt --salida salida_real/
```

Si se corta la red o el entrenamiento, se vuelve a correr el mismo comando y sigue donde
iba.

## Métricas

```bash
python -m herramientas.evaluar_motor --observaciones salida/observaciones.json --escena escena/escena.json
```

Resultados con los datos del simulador. El detector YOLO se entrenó **solo** con 10
escenas al azar (`datos_entrenamiento/`); el video del demo nunca se usó para entrenar, así
que estas cifras no están infladas por memorizar la escena.

**Video del demo** (`video/recorrido_realista.mp4`: 4K, 693 cuadros, 23.1 s, 8 errores):

| Métrica | Mínimo | Resultado |
|---|---|---|
| Etiquetas encontradas | ≥ 95 % | 100 % (11/11) y 0 falsas |
| Precio exacto por etiqueta, tras votar | ≥ 95 % | 100 % (11/11) |
| Precio exacto por cuadro (diagnóstico) | ≥ 85 % | 100 % (88/88 lecturas) |
| SKU exacto por etiqueta (extra) | — | 100 % |
| Huecos encontrados / huecos falsos | ≥ 90 % / ≤ 1 | 100 % (2/2) / 0 |
| Frentes exactos | ≥ 85 % | 100 % (12/12) |
| Producto correcto por imagen (H14, `--catalogo`) | ≥ 90 % | 100 % (10/10) |

**Tiempo** para un clip de 10 s en 4K a 30 fps (`video/clip_10s.mp4`): **19.3 s solo con
CPU** (18.9 s de reloj contando el arranque de Python) y 17.6 s con la RTX 3050. Límite:
60 s. El video completo de 23 s tarda 35 s con GPU. Lo más caro es el OCR (~0.2 s por
etiqueta en CPU) y el video anotado.

**Tarjetas del juez** (`video/tarjetas/`, una pasada en 4K a 10 fps, ~10 s, 9–12 s de
proceso cada una): las 4 salen sin fallas y la posición de cada tarjeta muestra el error
nuevo: precio 3.99 en R2-P1, `SKU-100936` leído en la etiqueta de R2-P3, R1-P2 sin
etiqueta y R3-P4 como hueco.

**Detector del anaquel** (`modelos/anaquel.pt`, YOLO11n, 40 épocas a 960 px, 930 imágenes):
mAP50 en validación 0.995 (etiqueta 0.995, producto 0.995, hueco 0.994).

**SKU-110K** (`modelos/sku110k.pt`, YOLO11n, 1,500 imágenes, 30 épocas a 640 px, ~13 min
en la RTX 3050): mAP50 en validación **0.856** (300 imágenes; mAP50-95 0.502).

Usado como detector de respaldo sobre el video del demo (sin clase `hueco`; el hueco sale
de "no hay producto"), el tamaño de entrada importa mucho: SKU-110K tiene productos chicos
y apretados, así que hay que achicar la imagen hasta que el producto mida lo que medía en
el entrenamiento (~30–40 px de ancho):

| `--imgsz` | `--confianza` | Huecos | Huecos falsos | Frentes exactos |
|---|---|---|---|---|
| 960 | 0.2 | 100 % | 10 | 16.7 % |
| 640 | 0.2 | 100 % | 1 | 75.0 % |
| 480 | 0.2 | 100 % | 0 | 91.7 % |

Para el clip real: empezar con `--modelo modelos/sku110k.pt --imgsz 480 --confianza 0.2`
y ajustar `--imgsz` con el primer clip.

Pruebas unitarias: `python -m pytest -q tests/` (51 pruebas del motor, del cruce, del modo sin
estructura y del asistente, sin video, modelos ni red).

## Decisiones y desviaciones del PDF

- **Colab → scripts.** `entrenamiento/sku110k.py` y `entrenamiento/entrenar_yolo.py`
  hacen lo que pedían los notebooks y se reanudan solos (`resume` de Ultralytics y
  descargas reanudables).
- **SKU-110K desde un espejo en parquet** (`benjamintli/sku110k` en Hugging Face): baja
  solo los 4 fragmentos necesarios para 1,500 imágenes (~2 GB) en lugar de los 13.6 GB
  del `SKU-110K.yaml` oficial, que sigue disponible con `--fuente ultralytics`.
  Validación: 300 imágenes del split de validación. Lote de 8 para que quepa en 4 GB.
- **No existía `CONTRATO.md`**: lo reconstruí con los 4 PDF. Lo que es decisión propia
  está marcado ahí (p. ej., la etiqueta va centrada en su posición para no encimarse con
  los marcadores de x = 0, 55 y 110 cm).
- **Etiqueta encontrada pero ilegible** → `etiqueta_visible: true` con precio `null` y
  confianza 0, para que P4 no la confunda con una etiqueta faltante. Visible = hubo
  lectura, o el borde naranja apareció en 2 o más cuadros.
- **Solo se reportan las posiciones que el video cubrió.** En un clip de una repisa, las
  otras no aparecen (antes salían como "etiqueta faltante"). Si la zona de producto no se
  vio completa, `frentes_vistos: null`: **P4 debe saltarse la regla de frentes con `null`**.
- **Regla de hueco.** La caja `hueco` cuenta solo si cubre ≥ 80 % del ancho de la
  posición; así un frente solo con espacio libre al lado (R1-P4) sale como frentes bajos
  y no como hueco.
- **Verdad del simulador.** Las cajas de producto son el frente (más la tapa si se ve),
  no las 8 esquinas del volumen: con 8 esquinas las cajas de frentes contiguos se enciman
  y estorban al entrenar. Si la verdad de Blender trae 8 esquinas, `preparar_yolo.py`
  igual la lee; conviene recortarla a las caras visibles.
- **OCR.** PP-OCRv5 *mobile* (más rápido en CPU; *server* con `--ocr-modelo server`),
  detección de texto a 480 px y se unen las cajas del mismo renglón (el detector parte
  `$24` | `99` en el punto). Se leen como máximo 8 recortes por posición, los más
  centrados (`--max-lecturas`).
- **Tarjetas en 4K.** P1 propone 1920 × 1080 para renderizar rápido, pero a esa
  resolución el SKU de la etiqueta mide ~9 px y no se lee (el precio sí): la tarjeta
  "etiqueta de otro SKU" saldría como precio distinto. En 4K a 10 fps el render y el
  proceso siguen tardando segundos. Recomendación para P1: tarjetas en 4K.
- **Opcionales ya implementados:** `--geometria` (corte H5: recorta donde debe estar la
  etiqueta si no se ve el borde naranja; probado sin etiquetas falsas), `--ampliar 2`
  (corte H8), `--cache DIR` (corte H16: reutiliza el resultado de clips ensayados),
  `--catalogo DIR` (corte H14: agrega `sku_producto` y `similitud_producto`; sin la
  opción el esquema queda exacto) y `--progreso RUTA` (paso y porcentaje para el
  `GET /estado` de la API de P4).
- **Pendiente con datos reales del equipo:** cuando lleguen el video y la verdad de
  Blender, reentrenar con `preparar_yolo.py` sobre esa verdad (unos 15 min en la RTX
  3050) y volver a medir. En H14 la galería son las mismas texturas del render, lo que
  lo hace más fácil que con fotos reales de catálogo.
