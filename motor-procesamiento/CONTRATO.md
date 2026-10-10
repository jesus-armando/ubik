# Contrato (reconstruido)

No había `CONTRATO.md` en el repositorio. Este documento lo reconstruye a partir de los
PDF de P1 (video y escena), P2 (motor), P3 (frontend) y P4 (datos y cruce). Si el equipo
tiene la versión oficial, gana la oficial; los valores que aquí son **decisión propia**
están marcados así y viven en `motor/contrato.py` para cambiarlos en un solo lugar.

## Regla de oro

El motor (`motor/`) nunca lee `escena/` ni `video/verdad/`. La única excepción es
`motor/preparar_yolo.py`, que usa `video/verdad/` como anotaciones **solo para entrenar**.

## Coordenadas

Sistema de la sección, en centímetros: `x` hacia la derecha desde el borde izquierdo de la
sección, `y` hacia arriba desde el piso. Todo el frente del anaquel (bordes de repisa,
etiquetas y marcadores) está en el mismo plano, a 80 cm de la cámara.

## Anaquel

| Elemento | Valor |
|---|---|
| Sección | 120 cm de ancho, repisas de 40 cm de fondo |
| Repisas | `R1` superficie a 120 cm, `R2` a 75 cm, `R3` a 30 cm |
| Posiciones | 4 por repisa, de 30 cm: `x_ini_cm` = 0, 30, 60, 90 |
| Productos | cajas de 8 × 8 cm, alto 20–30 cm, alineadas desde `x_ini_cm + 2` |
| Etiqueta | 6 × 3.5 cm en el frente de la repisa, borde superior a la altura de la superficie. **Decisión propia:** centrada en su posición (`x_ini_cm + 12`), para no encimarse con los marcadores |
| Marcadores | ArUco `DICT_4X4_100`, 5 cm de lado, `id = seccion*20 + repisa*4 + k`, `k` = 0, 1, 2 con esquina superior izquierda en `x` = 0, 55 y 110 cm y a la altura de la superficie de su repisa |

## Etiqueta impresa (P4)

PNG de 600 × 350 px (100 px por cm), borde naranja `#FF6A00` de 30 px, nombre del
producto, precio con dígitos de 120 px de alto (`$7.09`), código SKU de 60 px
(`SKU-100664`), código UPC y "Vigente desde".

## `datos/sistema/planograma.csv` (P4)

```
posicion,seccion,repisa,sku,nombre,x_ini_cm,x_fin_cm,altura_cm,frentes_esperados
R1-P1,1,R1,SKU-100664,Original Coffee Cake Muffin,0,30,120,3
```

Columnas obligatorias para el motor: `posicion`, `repisa`, `x_ini_cm`, `x_fin_cm`.
Opcionales: `seccion` (1), `altura_cm` (según la repisa), `frentes_esperados` (3),
`sku`, `nombre`. `repisa` acepta `R1` o `1`.

## `escena/escena.json` (P4 → P1)

```json
{"tienda": "S012", "fecha": "2026-03-03", "seccion": 1,
 "posiciones": [
  {"posicion": "R1-P1", "repisa": "R1", "sku_planograma": "SKU-100664",
   "sku_fisico": "SKU-100664", "frentes_fisicos": 3,
   "etiqueta": {"visible": true, "sku": "SKU-100664", "nombre": "Original Coffee Cake Muffin",
                "precio": 7.09, "upc": "071006640005", "vigente_desde": "2026-02-01"},
   "error": {"id": 1, "tipo": "precio_anterior", "descripcion": "..."}}]}
```

## Video (P1)

3840 × 2160, 30 fps, sensor de 36 mm con focal de 21.5 mm (≈ 80° horizontal), cámara a
80 cm del frente. Tres pasadas en serpentina a 0.3 m/s: `R1` a 140 cm (x de −40 a 160),
bajada a 95 cm, `R2` (x de 160 a −40), bajada a 50 cm, `R3` (x de −40 a 160). Unos 693
cuadros, ~23 s.

## `video/verdad/cuadro_NNNNNN.json` (P1)

`NNNNNN` empieza en 1, igual que los PNG de Blender: `cuadro_000001.json` es el cuadro con
índice 0 del mp4.

```json
{"cuadro": 1, "indice": 0, "pasada": "R1", "ancho": 3840, "alto": 2160,
 "camara": {"x_cm": -40.0, "z_cm": 140.0, "distancia_cm": 80.0},
 "objetos": [
  {"clase": "etiqueta", "posicion": "R1-P1", "sku": "SKU-100664", "caja": [x1, y1, x2, y2], "visible": 1.0},
  {"clase": "producto", "posicion": "R1-P1", "sku": "SKU-100664", "caja": [...], "visible": 1.0},
  {"clase": "hueco", "posicion": "R3-P1", "caja": [...], "visible": 1.0}]}
```

Cajas en píxeles, recortadas al borde; se descartan las que tienen menos del 30 % visible.
Una caja `hueco` ocupa el espacio de producto de una posición sin frentes.

## `salida/observaciones.json` (P2 → P4)

```json
{"video": "recorrido_realista.mp4", "segundos_proceso": 38,
 "posiciones": [
  {"posicion": "R1-P1", "etiqueta_visible": true, "sku_leido": "SKU-100664",
   "precio_leido": 7.09, "confianza_precio": 0.97, "lecturas_coinciden": 4,
   "hueco": false, "frentes_vistos": 3, "cuadro": 312,
   "recorte_etiqueta": "recortes/R1-P1_etiqueta.jpg", "recorte_posicion": "recortes/R1-P1.jpg"}]}
```

- `cuadro` es el índice del cuadro en el mp4 (empieza en 0): segundo = `cuadro` ÷ fps.
- Rutas de recortes relativas a `salida/`.
- Sin etiqueta: `etiqueta_visible: false`, `sku_leido`, `precio_leido` y
  `recorte_etiqueta` en `null`, `confianza_precio: 0`, `lecturas_coinciden: 0`.
- Etiqueta encontrada pero ilegible (**decisión propia**): `etiqueta_visible: true`, precio
  y SKU en `null`, `confianza_precio: 0`. Así P4 no la confunde con una etiqueta faltante.
- Si un paso falla en una posición: `confianza_precio: 0` y se sigue con las demás.
- Solo se reportan las posiciones que el video cubrió (**decisión propia**): en un clip de
  una sola repisa no aparecen las otras repisas, en lugar de salir como etiqueta faltante.
- Si la zona de producto de una posición nunca se vio completa (p. ej. la repisa de arriba
  en un clip de una pasada): `hueco: false` y `frentes_vistos: null`. P4 no debe aplicar
  la regla de frentes cuando venga `null`.

Además: `salida/recorrido_anotado.mp4` (H.264, 1920 px de ancho, mismos cuadros y fps que
la entrada) con cajas verdes (producto), rojas (hueco) y naranjas (etiqueta).

## `datos/sistema/precios.csv` e `inventario.csv` (P4; de prueba en `simulador/datos_prueba.py`)

```
sku,nombre,precio_vigente,precio_anterior,vigente_desde
SKU-100664,Original Coffee Cake Muffin,7.69,7.09,2026-03-01
```
```
sku,existencia,venta_diaria
SKU-100664,24,18
```

## `public/salida/hallazgos.json` (cruce → P3)

Esquema exacto en `Road2Tech/Frontend/types/hallazgos.ts`. Lo escribe `cruce/publicar.py`.

- `resumen`: `total_problemas`, `dinero_en_riesgo_diario`, `frase`, `etiquetas_con_error`,
  `huecos_inventario` (huecos con o sin existencia), `lecturas_dudosas`,
  `precision_anaquel_pct` (posiciones sin hallazgo ÷ posiciones vistas), `fecha_escaneo`
  (hora de `observaciones.json`), `disclaimer`; extras: `video`, `segundos_proceso`, `fps`,
  `supuestos_calculo`.
- `posiciones[]`: una por posición que el video cubrió; `id` = `pos-r1-p1`, `repisa` y
  `posicion` numéricos, `estado` `ok | error | revisar`, `frentes` puede ser `null`.
- `hallazgos[]`: a lo más uno por posición, de mayor a menor `impacto_diario`;
  `segundo` = `cuadro` ÷ fps del video; `evidencia_crop` es el recorte de la etiqueta en los
  tipos de etiqueta y `revisar`, y el de la posición en los demás.
- Tipos: los 8 de `frontend.pdf` más `producto_equivocado` (**decisión propia**, solo con
  `--catalogo`).

## `public/red.json` (cruce → P3; **decisión propia**)

Esquema exacto en `Road2Tech/Frontend/types/red.ts`. Lo escribe `cruce/red.py` a partir de
un `hallazgos.json` (`cruce/publicar.py` lo deja en `public/` con el del recorrido de demo).

- Solo se proyecta a las otras tiendas lo sistémico: `precio_anterior` (la lista de precios la
  cambia el corporativo en toda la red a la vez). Lo demás es local: se reporta como medido y
  no se proyecta; `revisar` no cuenta.
- `red`: `tiendas_total` (38), `otras_tiendas`, `moneda`, `medido_diario` = `sistemico_diario`
  + `local_diario`, `problemas_sistemicos`, `problemas_locales`, `dias_mes`,
  `supuestos_calculo`, `dataset_label`, `fecha_corte` (día de `fecha_escaneo`), `origen`
  (video del anaquel).
- `escenarios[]`: `bajo`, `central`, `alto` y `peor_caso` = la etiqueta sigue vieja en el 10,
  25, 50 y 100 % de las otras tiendas; `tiendas` (redondeado), `diario` = `tiendas` ×
  `sistemico_diario` (cada tienda con las ventas de la auditada), `mensual` = `diario` × 30.
- `sistemicos[]`: `sku`, `producto`, `tipo`, `precio_etiqueta`, `precio_sistema`,
  `impacto_diario` (en la auditada), `peor_caso_diario` (× otras tiendas).
- `locales[]`: `tipo`, `cantidad`, `impacto_diario`, agrupados por tipo.

## API del modo jurado (`cruce/api.py`, puerto 8000)

- `POST /procesar` `{"tarjeta": "precio_viejo"}` → 202; 404 si no hay
  `video/tarjetas/<tarjeta>.mp4`; 409 si ya hay una en proceso.
- `GET /estado` → `{"status": "inactivo | procesando | completado | error", "completado",
  "tarjeta", "paso", "pasoNumero" (1–4), "progreso" (0–100), "segundos", "hallazgo_nuevo",
  "hallazgos_nuevos", "segundos_proceso", "mensaje"}`.
- `GET /archivos/tarjetas/<tarjeta>/recortes/<archivo>.jpg` → recortes de la corrida.

## API de videos subidos (`cruce/api.py`, mismo puerto)

Un trabajo del motor a la vez (tarjeta o video): el segundo recibe 409.

- `POST /analisis?nombre=<archivo>&detector=anaquel|sku110k|libre&identificar=0|1`, cuerpo = el video
  (`.mp4 .mov .m4v .avi .mkv .webm`, hasta 4 GB) → 202 con el análisis; 400 si OpenCV no lo
  puede leer.
- `GET /analisis/<id>` → `{"id", "nombre", "creado", "detector", "identificar", "status":
  "procesando | completado | error", "paso", "pasoNumero" (1 eligiendo cuadros, 2 leyendo
  etiquetas, 3 generando video anotado, 4 comparando; 5 terminado), "progreso", "segundos",
  "video": {fps, cuadros, ancho, alto, segundos}, "resumen", "posiciones", "mensaje", "activo"}`.
- `GET /analisis` → `{"analisis": [...], "activo": id | null, "ocupado": bool}`.
- `GET /analisis/activo` → `hallazgos.json` del análisis activo (404 = usar el de demo). Sus
  recortes y `resumen.video_url` apuntan a `/motor/archivos/analisis/<id>/...`; además trae
  `resumen.analisis_id` y `resumen.video` (nombre original).
- `GET /analisis/activo/red` → `red.json` del análisis activo (404 = usar el de demo).
- `POST /analisis/<id>/chat` (`<id>` = `demo` para el recorrido de demo) `{"pregunta",
  "historial": [{"rol": "usuario | asistente", "texto"}]}` → `{"respuesta", "fuentes": [{"id",
  "titulo"}], "modelo", "corrida"}`; 404 sin corrida, 409 si no terminó, 503 sin clave de Gemini,
  502 si Gemini falla. `GET /chat` → `{"configurado", "modelos", "embeddings"}`. No ocupa el motor.
- `POST /analisis/<id>/activar` (o `/analisis/demo/activar`), `DELETE /analisis/<id>`.
- Un video sin ninguna posición ubicada (sin marcadores ArUco) termina en `error`.

## Modo sin estructura (**decisión propia**)

`motor/libre.py` → `observaciones_libre.json` (en lugar de `observaciones.json`):

```json
{"video": "clip.mp4", "modo": "libre", "segundos_proceso": 26.3, "fps": 24.0, "cuadros": 240,
 "resolucion": [1280, 720],
 "etiquetas": [
  {"id": "E2", "nombre_leido": "ARROZ BLANCO", "precio_leido": 32.9, "confianza_precio": 0.925,
   "lecturas": 7, "lecturas_coinciden": 7, "acuerdo": 1.0, "precios_vistos": {"32.90": 7},
   "hueco": false, "votos_hueco": [0, 7], "ancho_relativo": 0.3, "cuadro": 111,
   "primer_cuadro": 60, "ultimo_cuadro": 132,
   "recorte_etiqueta": "recortes/E2_etiqueta.jpg", "recorte_posicion": "recortes/E2.jpg"}]}
```

`acuerdo` es la fracción (por confianza) de lecturas que dieron el precio ganador;
`recorte_posicion` es la etiqueta con la zona de producto de encima marcada. `cruce/libre.py`
lo convierte al mismo `hallazgos.json` del tablero con `resumen.modo: "libre"`,
`resumen.moneda: "$"`, posiciones con `repisa: 0`, `ubicacion: "Etiqueta E2"`, `sku: ""`,
`precio_sistema`/`inventario_sistema`/`frentes` en `null`, y dos tipos nuevos: `hueco` ("Hueco
en anaquel") y `precio_inconsistente` ("Mismo producto, precios distintos").

