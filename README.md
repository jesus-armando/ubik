<p align="center">
  <img src="logo.jpeg" alt="Ubik" width="360">
</p>

<p align="center">
  <b>Lo que el sistema de la tienda no ve, en dinero y con evidencia.</b><br>
  Auditoría de anaqueles de supermercado a partir de un video.
</p>

---

## La intención en una frase

**Ubik convierte un video del anaquel (grabado con dron, celular o cámara) en una lista de
problemas ordenada por dinero: qué está mal, dónde está, cuánto cuesta al día y qué hacer para
corregirlo.**

## El problema que resuelve

El sistema de una tienda (precios, inventario y planograma) dice cómo **debería** estar el
anaquel. El anaquel real se desvía todos los días y el sistema no se entera:

- El corporativo subió el precio, pero **la etiqueta sigue con el precio viejo** y en caja se
  cobra el de la etiqueta.
- El inventario dice que hay 6 piezas, pero **en el anaquel hay un hueco**: la venta se pierde
  teniendo el producto en bodega.
- **Un producto ocupa el lugar de otro**, falta una etiqueta o la etiqueta es de otro producto.

Hoy esto se encuentra con auditorías manuales: alguien recorre los pasillos con la lista de
precios, etiqueta por etiqueta. Es lento, se hace por muestreo y no dice qué error corregir
primero, porque nadie le pone precio a cada error.

## Qué hace Ubik

Se graba un recorrido normal frente al anaquel y, en menos de un minuto, el gerente recibe algo
como:

> **8 problemas en este anaquel · US$285 al día en juego.**
> Empieza por el hueco de Tuna Salad Wrap (US$80.91/día): hay 6 piezas en el sistema, surte
> desde bodega.

Cada hallazgo trae la foto de la etiqueta, el segundo exacto del video donde aparece y la
acción concreta para corregirlo.

### Cómo funciona

```
 1. GRABAR            2. LEER                      3. CRUZAR                  4. ACTUAR
 Dron, celular o      Elige los cuadros nítidos,   Compara contra el sistema: Tablero ordenado por
 cámara recorre  ──▶  lee precio y SKU de cada ──▶ planograma, precios e  ──▶ dinero, con foto y
 el anaquel           etiqueta, cuenta frentes y   inventario. Calcula cuánto acción sugerida
                      detecta huecos               cuesta cada error
```

### Qué detecta

| Problema | Ejemplo | Por qué cuesta |
|---|---|---|
| Etiqueta con precio viejo | El muffin subió a US$7.69 y la etiqueta sigue en US$7.09 | Se cobra el precio de la etiqueta |
| Precio distinto al sistema | El precio no es ni el vigente ni el anterior | Error de captura en la tienda |
| Falta la etiqueta | Pretzel Bites sin etiqueta | El cliente no sabe el precio y muchas veces no compra |
| Etiqueta de otro producto | La etiqueta de 12 Bagels bajo Chocolate Chunk Cookie | Confusión y cobro equivocado |
| Hueco, pero el sistema dice que hay | Tuna Salad Wrap: hueco con 6 piezas en el sistema | Venta perdida teniendo el producto |
| Agotado | 8 Donut Holes sin existencia | Venta perdida; hay que pedir resurtido |
| Producto en el lugar equivocado | Chicken Croissant en el lugar de Bacon Roll Up | El producto correcto no se vende |
| Pocos frentes | 12 Bagels con 1 de 3 frentes | El producto se ve menos y se vende menos |

## Para quién es

- **Gerente de tienda y personal de piso:** reciben la lista de qué corregir y en qué orden.
- **Cadenas con varias sucursales** (operaciones, precios, prevención de pérdidas): pueden
  confirmar que un cambio de lista de precios realmente llegó al anaquel en toda la red.

Momentos de uso: después de cada cambio de precios, en el recorrido diario o semanal de los
pasillos de mayor venta y en auditorías del corporativo a sucursales.

## Principios de diseño

1. **Ordenar por dinero, no solo listar errores.** El gerente sabe por dónde empezar.
2. **Cada hallazgo trae evidencia.** No hay que creerle a la máquina: se puede ver la foto.
3. **Ser honesto con lo que no sabe.** Una lectura dudosa sale como "revisar" y no suma
   dinero.
4. **Separar lo sistémico de lo local.** Una etiqueta con el precio de la lista anterior nace
   en el corporativo y puede repetirse en toda la red; un hueco es de una sola tienda.
5. **Funcionar con lo que haya:** con marcadores ArUco (máxima precisión), solo con el
   planograma (tienda real grabada con celular) o sin nada (cualquier video).
6. **Correr en una laptop.** Sin servidores ni nube; solo el asistente necesita internet.

## Estado del proyecto

Es un **prototipo funcional**. Los datos de la demo son **sintéticos** (la cadena ficticia
Glazed Co.) y el tablero lo indica en todas las pantallas.

| Resultado | Valor |
|---|---|
| Video de demo (4K, 23 s, 8 errores sembrados) | 8 de 8 errores; 100 % de etiquetas, precios y huecos; ~40 s de proceso |
| Anaquel armado a mano, grabado con celular y sin marcadores | 11 de 11 etiquetas leídas; 7 de 8 errores encontrados |
| Clip de 10 s en 4K | 19 s solo con CPU, en una laptop |

El detector se entrenó con escenas generadas al azar; el video de demo nunca se usó para
entrenar. Los supuestos para calcular el dinero (p. ej., 25 % de la venta diaria si falta la
etiqueta) son del prototipo y se calibrarían con datos reales de la cadena. El siguiente paso
es un piloto en una tienda real con su planograma, precios e inventario. Más detalle en
[`PITCH.md`](PITCH.md) y en las métricas de
[`motor-procesamiento/README.md`](motor-procesamiento/README.md).

## Estructura

| Carpeta | Qué es |
|---|---|
| [`motor-procesamiento/`](motor-procesamiento/README.md) | Motor en Python: OCR de etiquetas (PaddleOCR), detección de huecos y frentes (YOLO), cruce contra el sistema, API en `:8000` y asistente con Gemini |
| [`Road2Tech/Frontend/`](Road2Tech/Frontend/DISENO.md) | Tablero en Next.js 15 + Tailwind: resumen, recorrido anotado, anaquel, hallazgos, subir video y asistente |
| [`PITCH.md`](PITCH.md) | Documento base del pitch |
| `videos_ia/` | Videos generados con IA para probar el modo sin estructura (`motor.libre`) |
| [`no_usado/`](no_usado/README.md) | Lo archivado (no se versiona; solo su índice) |
| `iniciar.sh` | Arranca la API del motor y el tablero con un comando |

## Requisitos

- Python 3.12 y [uv](https://docs.astral.sh/uv/) para el motor (GPU opcional)
- Node.js 18.18+ y npm para el tablero
- Opcional: una clave de Gemini para el asistente

## Instalación

```bash
git clone <url-del-repositorio> ubik && cd ubik

# Motor (detalles y trampas conocidas en motor-procesamiento/README.md, "Instalación")
cd motor-procesamiento
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python torch torchvision --index-url https://download.pytorch.org/whl/cu130   # sin GPU: .../whl/cpu
uv pip install --python .venv/bin/python -r requirements.txt
uv pip uninstall --python .venv/bin/python opencv-python opencv-contrib-python
uv pip install --python .venv/bin/python opencv-contrib-python==4.10.0.84
cd ..

# Clave del asistente (opcional)
cp .env.example .env    # y pon APIGEMINI=tu-clave
```

Las dependencias del tablero se instalan solas la primera vez que corre `iniciar.sh`.

## Uso

```bash
./iniciar.sh            # tablero en http://localhost:3000, API del motor en :8000
./iniciar.sh --build    # recompila el tablero aunque no haya cambios
PUERTO=3001 ./iniciar.sh
```

El tablero trae una copia del recorrido de demo en `Road2Tech/Frontend/public/salida/`, así que
se ve completo aunque la API esté apagada. Desde **Subir video** se procesan videos nuevos.

### Datos que no están en el repositorio

Los videos de prueba (`motor-procesamiento/video/`), las salidas del motor (`salida*/`) y los
análisis subidos (`analisis/`) no se versionan porque pesan y se regeneran. Las tarjetas del
jurado de la API (`POST /procesar`) y el asistente sobre el recorrido de demo los necesitan:
genéralos con los pasos de **Datos de prueba** y luego los pasos 1 a 3 de **Integración con el
tablero** en [`motor-procesamiento/README.md`](motor-procesamiento/README.md). Los modelos
entrenados (`motor-procesamiento/modelos/*.pt`) sí vienen incluidos.

## Documentación

- [`motor-procesamiento/README.md`](motor-procesamiento/README.md): módulos, datos de prueba, API, asistente, entrenamiento y métricas
- [`motor-procesamiento/CONTRATO.md`](motor-procesamiento/CONTRATO.md): esquema de `observaciones.json`
- [`Road2Tech/Frontend/DISENO.md`](Road2Tech/Frontend/DISENO.md): diseño del tablero
