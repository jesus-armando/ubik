# No usado (de momento)

Lo que ni el tablero ni el motor usan hoy. Cada cosa conserva su ruta original debajo de
`no_usado/`, así que para regresarla basta con:

```bash
mv no_usado/<ruta> <ruta>      # p. ej. mv no_usado/motor-procesamiento/datasets motor-procesamiento/datasets
```

El contenido no se versiona (ver `.gitignore`); solo este índice.

## motor-procesamiento/

| Ruta | Qué es | Cuándo regresarlo |
|---|---|---|
| `debug/` | Imágenes que dejan las pruebas sueltas de `motor.marcadores` y `motor.etiquetas` | Nunca: se vuelve a crear al correrlas |
| `runs/` | Bitácoras y pesos intermedios de Ultralytics; los modelos finales ya están en `modelos/` | Para revisar curvas o métricas de un entrenamiento |
| `weights/yolo26n.pt` | Pesos que Ultralytics bajó solo; ningún script los usa | Nunca |
| `yolo11n.pt` | Pesos base para entrenar (`--base` de `entrenamiento/`) | Al reentrenar (si falta, Ultralytics lo vuelve a bajar) |
| `datasets/` (4.7 GB) | `anaquel/` (de `motor.preparar_yolo`) y `sku110k/` (descargado por `entrenamiento.sku110k`) | Al reentrenar, para no volver a bajar ni a generar |
| `datos_entrenamiento/` | Las 10 escenas al azar del simulador con las que se entrenó `modelos/anaquel.pt` | Al reentrenar el detector del anaquel |

## Road2Tech/

| Ruta | Qué es | Cuándo regresarlo |
|---|---|---|
| `chatbot/` | Carpeta vacía | Cuando empiece el chatbot |
| `Frontend/lib/utils.ts` | Ayudante `cn()` (clsx + tailwind-merge); ningún componente lo importa | Si un componente lo necesita |
| `Frontend/public/evidencias/r?_p?.svg` | 12 recortes de relleno de antes de que el motor diera recortes reales; solo se usa `sin_recorte.svg`, que sigue en su lugar | Nunca |
| `Frontend/screenshots/` | Capturas viejas (`baseline/`, `final/`) | Nunca: `node scripts/capture-all.mjs` las vuelve a sacar |
