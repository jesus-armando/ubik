# Ubik: auditoría de anaqueles con video

> **Technology | Logistics | Efficiency**
>
> Documento base para armar el pitch y la presentación. Las cifras salen del prototipo que
> ya funciona (motor + tablero) con los datos sintéticos de Glazed Co. Lo que está marcado
> como **[verificar]** es contexto de mercado que hay que confirmar antes de ponerlo en una
> diapositiva.

---

## 1. En una frase

**Ubik convierte un recorrido en video del anaquel (con dron, celular o cámara) en una lista
de problemas ordenada por dinero: qué está mal, dónde, cuánto cuesta al día y qué hacer.**

Versión de 30 segundos (elevator pitch):

> En un supermercado, el sistema cree que todo está bien: el precio nuevo ya está cargado, el
> inventario dice que hay producto. Pero en el anaquel la etiqueta sigue con el precio viejo,
> hay un hueco donde el sistema dice que hay 6 piezas y un producto está en el lugar de otro.
> Nadie lo ve hasta que se pierde la venta. Ubik graba el anaquel, lee cada etiqueta y cada
> espacio, lo compara con el sistema de la tienda y en menos de un minuto le dice al gerente:
> "8 problemas en este anaquel, US$285 al día en juego, empieza por aquí". Cada hallazgo trae
> la foto como evidencia y la acción para corregirlo.

---

## 2. El problema

### Lo que pasa en el anaquel y el sistema no ve

El sistema de la tienda (precios, inventario, planograma) dice cómo **debería** estar el
anaquel. El anaquel real se desvía todos los días, y esas desviaciones son invisibles para el
sistema:

| Problema | Ejemplo real del demo | Por qué cuesta |
|---|---|---|
| **Etiqueta con precio viejo** | El corporativo subió el muffin a US$7.69 y la etiqueta sigue en US$7.09 | Se cobra el precio de la etiqueta: se pierde la diferencia en cada pieza |
| **Falta la etiqueta** | Pretzel Bites sin etiqueta | El cliente no sabe el precio y muchas veces no compra |
| **Etiqueta de otro producto** | La etiqueta de 12 Bagels está bajo Chocolate Chunk Cookie | Confusión, reclamos, cobro equivocado |
| **Hueco, pero el sistema dice que hay** | Tuna Salad Wrap: hueco con 6 piezas en el sistema | Venta perdida teniendo el producto en bodega |
| **Agotado** | 8 Donut Holes sin existencia | Venta perdida; hay que pedir resurtido |
| **Producto en el lugar equivocado** | Chicken Croissant ocupa el lugar de Bacon Roll Up | El producto correcto no se vende y el otro queda con la etiqueta equivocada |
| **Pocos frentes** | 12 Bagels con 1 de 3 frentes | El producto se ve menos y se vende menos |
| **Precio distinto al sistema** | El precio no es ni el vigente ni el anterior | Error de captura en la tienda |

### Por qué es difícil hoy

- **Es invisible para el sistema.** El ERP no sabe si la etiqueta se cambió o si el producto
  está en el anaquel o en la bodega. El error solo aparece cuando alguien camina el pasillo y
  lo nota.
- **La auditoría manual es lenta y por muestreo.** Alguien recorre los pasillos con la lista
  de precios, etiqueta por etiqueta. No se hace todos los días ni en todos los anaqueles, y no
  dice cuál error corregir primero.
- **Un cambio de precios del corporativo pega en toda la red a la vez.** Si la lista nueva se
  carga en el sistema pero las etiquetas no se cambian, el mismo error se repite en las 38
  tiendas.
- **Nadie le pone precio al error.** Sin un monto, una etiqueta vieja y un hueco de un
  producto que se vende mucho parecen igual de urgentes.

### Contexto de mercado **[verificar antes de usar]**

- El estudio clásico de faltantes en tienda (Gruen, Corsten y Bharadwaj, 2002, para la GMA)
  midió en promedio **~8 % de productos agotados en el anaquel** y encontró que ante un
  faltante una parte importante de los clientes compra en otra tienda o no compra.
- En México, mostrar en el anaquel un precio distinto al que se cobra es motivo de queja ante
  la **PROFECO**. Confirmar el artículo de la Ley Federal de Protección al Consumidor antes de
  citarlo.

---

## 3. La solución: Ubik

### Cómo funciona, en 4 pasos

```
 1. GRABAR            2. LEER                     3. CRUZAR                 4. ACTUAR
 Dron, celular o      Elige los cuadros más       Compara con el sistema:   Tablero ordenado por
 cámara recorre  ──▶  nítidos, encuentra cada ──▶ planograma, precios e ──▶ dinero, con foto y
 el anaquel           etiqueta, lee precio y SKU, inventario. Calcula       acción sugerida
                      detecta productos y huecos  cuánto cuesta cada error
```

1. **Grabar.** Un recorrido normal frente al anaquel. No hace falta parar en cada etiqueta.
2. **Leer (visión por computadora).** El motor toma los cuadros más nítidos, ubica el anaquel,
   encuentra las etiquetas, lee **precio y SKU** con OCR, cuenta los frentes de producto y
   detecta los huecos. Si un mismo dato se ve en varios cuadros, vota para quedarse con la
   lectura más confiable.
3. **Cruzar con el sistema.** Para cada posición compara lo que vio con lo que dice el
   sistema: qué producto va ahí (planograma), a qué precio (lista vigente y anterior) y
   cuánto hay (inventario y venta diaria).
4. **Priorizar y actuar.** Cada problema sale con su impacto en dinero al día, la foto de la
   etiqueta, el momento exacto del video y la acción concreta ("Cambiar la etiqueta por la del
   precio vigente, US$7.69"; "Surtir desde bodega: hay 6 piezas en sistema").

### Tres formas de usarlo según lo que tenga la tienda

| Modo | Cuándo | Qué necesita |
|---|---|---|
| **Con marcadores** (máxima precisión) | Anaqueles preparados, recorrido con dron o cámara fija | Marcadores ArUco en las repisas y el planograma |
| **Con planograma, sin marcadores** | Tienda real grabada con el celular | Solo el planograma y que se lea el SKU de las etiquetas |
| **Sin estructura** | Cualquier video (celular, IA), sin datos de la tienda | Nada: lee etiquetas, busca huecos y detecta el mismo producto con dos precios. El dinero sale como estimación |

---

## 4. Qué ve el usuario (el tablero)

Diseñado con la **regla de los 10 segundos**: en un vistazo, el gerente entiende el problema,
el dinero en juego, dónde está y qué hacer.

| Pantalla | Qué muestra |
|---|---|
| **Resumen** | Una frase grande: *"8 problemas en este anaquel · US$285.15 al día en juego"* y las cifras clave |
| **Recorrido** | El video con las cajas dibujadas (verde producto, rojo hueco, naranja etiqueta); cada hallazgo es una marca en la línea de tiempo que salta a ese momento |
| **Anaquel (gemelo digital)** | El anaquel dibujado: 3 repisas × 4 posiciones en verde (correcto), rojo (error) o ámbar (revisar). Al tocar una posición se abre su evidencia |
| **Hallazgos** | Tarjetas ordenadas por dinero: foto de la etiqueta, "La etiqueta dice US$7.09 · El sistema dice US$7.69", US$ al día, acción sugerida y botón "Marcar corregido" |
| **Impacto en la red** | Qué pasa si el mismo error está en las otras 37 tiendas (ver sección 5) |
| **Subir video** | Se arrastra un video nuevo y en ~1 minuto queda analizado; historial para comparar recorridos |
| **Asistente** | Preguntas en español sobre una corrida: "¿Qué corrijo primero?", "¿Por qué R2-P3 es dudosa?". Responde con las fuentes que usó |
| **Modo jurado** | El jurado elige un error, el motor procesa un video nuevo en vivo y aparece el hallazgo nuevo resaltado |

---

## 5. Beneficios esperados

### Para la tienda (gerente y operación)

- **Saber qué corregir primero.** La lista viene ordenada por dinero, no por orden de pasillo.
  En el demo, el hueco con inventario (US$80.91/día) va antes que la etiqueta vieja
  (US$10.80/día).
- **Recuperar ventas perdidas.** Huecos con inventario en bodega y productos fuera de lugar
  son venta que se recupera con solo acomodar.
- **Auditoría en minutos, no en horas.** Un recorrido de 23 s se procesa en ~40 s. Un clip de
  10 s en 4K tarda 19 s solo con CPU, en una laptop.
- **Acciones claras para el personal.** Cada hallazgo dice exactamente qué hacer, con la foto
  como evidencia.
- **Menos riesgo con el cliente y la PROFECO.** Precio de etiqueta igual al precio del
  sistema.

### Para el corporativo

- **Ver si un cambio de precios realmente llegó al anaquel.** Las etiquetas con el precio de
  la lista anterior son un error **sistémico**: nacen en el corporativo y pueden repetirse en
  toda la red.
- **Escenarios de impacto en la red, sin inflar la cifra.** Ubik solo proyecta a las otras
  tiendas lo que es sistémico. Huecos, etiquetas faltantes o fuera de lugar dependen de cada
  tienda y se reportan solo como medidos.
- **Datos para decidir.** Precisión del anaquel, tipos de error más frecuentes y tiempos.

### Para el cliente

- Encuentra el producto, con el precio correcto, en el lugar donde lo busca.

### Cifras del demo (datos sintéticos de Glazed Co.)

**Un anaquel de 12 posiciones:**

| Indicador | Valor |
|---|---|
| Problemas encontrados | **8** (los 8 errores sembrados en la escena) |
| Dinero en juego | **US$285.15 al día** (≈ US$8,550 al mes si nadie lo corrige) |
| Posiciones correctas | 33 % (4 de 12) |
| Tiempo de proceso | ~40 s para un video de 23 s en 4K |

**Desglose por hallazgo (ordenado por dinero):**

| Hallazgo | Producto | US$/día |
|---|---|---|
| Hueco, pero el sistema dice que hay | Tuna Salad Wrap | 80.91 |
| Producto en lugar equivocado | Chicken Croissant en lugar de Bacon Roll Up | 67.90 |
| Agotado: pedir resurtido | 8 Donut Holes | 62.86 |
| Pocos frentes | 12 Bagels (1 de 3) | 18.12 |
| Etiqueta de otro producto | Chocolate Chunk Cookie | 18.09 |
| Falta la etiqueta | Pretzel Bites | 16.47 |
| Etiqueta con precio viejo | Original Coffee Cake Muffin | 10.80 |
| Etiqueta con precio viejo | Caramel Iced Coffee | 10.00 |

**Impacto en la red (38 tiendas):** de los US$285.15, US$20.80 al día son las 2 etiquetas con
el precio de la lista anterior (sistémico). Si esa misma etiqueta sigue vieja en otras
tiendas:

| Escenario | Otras tiendas | US$/día | US$/mes |
|---|---|---|---|
| Bajo (10 %) | 4 | 83.20 | 2,496 |
| Central (25 %) | 9 | 187.20 | 5,616 |
| Alto (50 %) | 19 | 395.20 | 11,856 |
| Peor caso (todas) | 37 | 769.60 | 23,088 |

Y esto es **un solo anaquel y solo dos productos**. Un cambio de lista de precios toca cientos
de productos.

### Cómo se calcula el dinero (para defender la cifra)

Reglas simples y explícitas, visibles en el tablero:

| Error | Dinero al día |
|---|---|
| Precio de etiqueta menor al del sistema | Diferencia × piezas vendidas al día (se cobra el de la etiqueta) |
| Sin etiqueta o precio mayor | 25 % de la venta diaria (parte de los clientes no compra) |
| Hueco o producto equivocado | La venta diaria completa |
| Pocos frentes | 20 % de la venta diaria × frentes faltantes ÷ esperados |
| Lectura dudosa | No se estima (no se cuenta dinero sobre algo que no es seguro) |

Los porcentajes son supuestos del prototipo; con datos reales de la cadena se calibran.

---

## 6. Evidencia: ¿funciona?

### Precisión del motor (video del demo: 4K, 23 s, 8 errores sembrados)

El detector se entrenó **solo con 10 escenas generadas al azar**. El video del demo nunca se
usó para entrenar, así que las cifras no vienen de memorizar la escena.

| Métrica | Meta | Resultado |
|---|---|---|
| Etiquetas encontradas | ≥ 95 % | **100 %** (11/11), 0 falsas |
| Precio exacto por etiqueta | ≥ 95 % | **100 %** (11/11) |
| SKU exacto por etiqueta | — | **100 %** |
| Huecos encontrados / falsos | ≥ 90 % / ≤ 1 | **100 % / 0** |
| Frentes exactos | ≥ 85 % | **100 %** (12/12) |
| Producto correcto por imagen | ≥ 90 % | **100 %** (10/10) |
| Tiempo para un clip de 10 s | ≤ 60 s | **19 s** solo con CPU, 17.6 s con GPU |

Detector propio del anaquel: mAP50 de **0.995**. Detector general de productos para tiendas
reales (entrenado con SKU-110K): mAP50 de **0.856**.

### Prueba con un anaquel real y un celular

Un anaquel armado a mano (fotos de los productos, etiquetas impresas en pesos, **sin
marcadores**) grabado con un celular (1080p, 17 s):

- Se leyeron las **11 etiquetas con su SKU** y se acomodaron solas en el planograma.
- Salieron **7 de los 8 errores** sembrados: 2 precios viejos, 1 sin etiqueta, 1 etiqueta de
  otro producto, 1 hueco con inventario, 1 agotado y 1 producto equivocado. **$3,511.18 al
  día** en juego. El que falta (pocos frentes) no se cuenta en este modo.
- Las 5 posiciones correctas salieron correctas.
- Un segundo video del mismo anaquel con cambios, enviado por WhatsApp (comprimido a
  478 × 850), también se pudo procesar. **[verificar]** que los hallazgos coincidan con los
  cambios que se hicieron antes de usarlo en el pitch.

### El momento en vivo (modo jurado)

El jurado elige uno de 4 errores (precio viejo, etiqueta de otro producto, etiqueta quitada,
producto retirado). El motor procesa ese video **en 9 a 13 segundos**, frente al jurado, y el
tablero resalta el hallazgo nuevo en su posición exacta.

---

## 7. Qué hace diferente a Ubik

1. **Ordena por dinero, no solo lista errores.** El gerente sabe por dónde empezar.
2. **Cada hallazgo trae evidencia.** Foto de la etiqueta, foto de la posición y el segundo
   exacto del video. No hay que creerle a la máquina: se puede ver.
3. **Es honesto con lo que no sabe.** Una lectura dudosa sale en ámbar como "revisar" y no
   suma dinero. Si el video no alcanzó a leer dos posiciones seguidas, no las acusa de "falta
   la etiqueta". Las cifras de red son escenarios, no una cifra inflada.
4. **Separa lo sistémico de lo local.** Distingue el error que nace en el corporativo (se
   repite en la red) del que es de una tienda.
5. **Funciona con lo que hay.** Marcadores para máxima precisión, solo planograma para tiendas
   reales con celular, o sin nada para cualquier video.
6. **Corre en una laptop.** Sin servidores ni nube. El tablero funciona sin internet (el
   asistente sí necesita conexión).
7. **Se le puede preguntar.** El asistente responde en español con los datos de la corrida y
   dice de dónde sacó cada respuesta.

---

## 8. Por dentro (para preguntas técnicas)

| Pieza | Tecnología |
|---|---|
| Selección de cuadros | OpenCV: el cuadro más nítido de cada ventana (varianza del Laplaciano) |
| Ubicación en el anaquel | Marcadores ArUco + homografía (píxeles → centímetros); sin marcadores, alineación de la secuencia de etiquetas con el planograma, como un *diff* |
| Lectura de etiquetas | PaddleOCR PP-OCRv5: precio y SKU con votación entre cuadros |
| Productos, huecos y frentes | YOLO11n entrenado con escenas sintéticas (anaquel) y con SKU-110K (tiendas reales) |
| Producto equivocado | DINOv2: similitud de la imagen del producto con el catálogo |
| Video sin estructura | Seguimiento de etiquetas entre cuadros compensando el movimiento de la cámara (ORB + homografía) |
| Cruce y dinero | Python: reglas por posición contra planograma, precios e inventario |
| Tablero | Next.js + TypeScript + Tailwind, sin dependencias de internet |
| API | Python, biblioteca estándar: subir videos, progreso en vivo, historial |
| Asistente | Gemini con RAG sobre los datos de la corrida y la documentación |

---

## 9. A quién va dirigido

- **Usuario principal:** gerente de tienda y personal de piso, que reciben la lista de qué
  corregir.
- **Comprador:** cadenas de supermercados y tiendas de autoservicio con varias sucursales
  (área de operaciones, precios o prevención de pérdidas).
- **Momentos de uso:**
  - Después de cada cambio de lista de precios, para confirmar que llegó al anaquel.
  - Recorrido diario o semanal de los pasillos de mayor venta.
  - Auditorías del corporativo a sucursales.

**[Por definir con el equipo]:** modelo de cobro (por tienda al mes, por recorrido, por
anaquel), quién graba (personal con celular, dron, cámara fija) y frecuencia.

---

## 10. Límites actuales y siguientes pasos

Hay que decirlo antes de que lo pregunte el jurado:

| Hoy | Siguiente paso |
|---|---|
| Datos sintéticos (Glazed Co.) y un anaquel armado a mano | Piloto en una tienda real con su planograma, precios e inventario |
| Supuestos de dinero fijos (25 %, 20 %, venta diaria completa) | Calibrarlos con las ventas reales de la cadena |
| Sin marcadores no se cuentan frentes | Contar frentes con el detector de productos en ese modo |
| Etiquetas chicas o borrosas salen como dudosas | Mejor cámara o recorrido más cerca; el sistema ya las separa sin acusar |
| El recorrido debe ir en orden, sin saltarse repisas | Recorrido guiado (dron con ruta fija) |
| Se procesa un anaquel por video | Pasillo completo y tienda completa |
| Archivos CSV del sistema | Conexión directa con el ERP / punto de venta de la cadena |
| Comparar recorridos uno por uno en el historial | Vista que compare dos recorridos posición por posición |

---

## 11. Guion sugerido para el pitch (3 a 5 min)

| # | Diapositiva / momento | Qué decir | Tiempo |
|---|---|---|---|
| 1 | **Gancho** | "El sistema dice que hay 6 piezas de Tuna Salad Wrap. El anaquel está vacío. Esta tienda pierde US$81 al día y nadie lo sabe." | 20 s |
| 2 | **El problema** | Los 4 errores más caros (precio viejo, hueco con inventario, producto equivocado, sin etiqueta) y por qué el sistema no los ve | 40 s |
| 3 | **La solución** | Ubik en 4 pasos: grabar, leer, cruzar, actuar | 30 s |
| 4 | **Demo: Resumen** | "8 problemas en este anaquel · US$285 al día en juego" | 15 s |
| 5 | **Demo: Anaquel y Hallazgos** | El gemelo digital en rojo y verde; abrir una tarjeta con la foto y la acción | 40 s |
| 6 | **Demo en vivo (modo jurado)** | El jurado elige un error; en ~10 s aparece resaltado | 40 s |
| 7 | **Impacto en la red** | El precio viejo nace en el corporativo: en 38 tiendas, de US$83 a US$770 al día por 2 productos | 30 s |
| 8 | **Evidencia** | 100 % en etiquetas, precios y huecos; prueba con celular en anaquel real: 7 de 8 errores | 25 s |
| 9 | **Diferenciadores** | Ordena por dinero, trae evidencia, es honesto con lo dudoso, corre en una laptop | 20 s |
| 10 | **Siguiente paso / cierre** | Piloto en tienda real. "Ubik: lo que el sistema no ve, en dinero y con evidencia." | 20 s |

**Consejos para la demo:**
- Tener el tablero ya compilado y abierto (`./iniciar.sh`), con el recorrido de demo activo.
- Si la API no responde en el modo jurado, el tablero muestra el resultado de ensayo: no se
  rompe la demo.
- Llevar el video del celular ya subido en el historial para enseñar el caso real sin esperar.

---

## 12. Preguntas difíciles probables

**"¿Esos datos son reales?"**
Son sintéticos (Glazed Co.) y lo decimos en todas las pantallas. Además lo probamos con un
anaquel armado a mano y grabado con celular, y encontró 7 de los 8 errores sembrados.

**"¿De dónde sale el dinero?"**
De reglas simples y visibles: precio viejo = diferencia × piezas vendidas al día; hueco =
venta diaria completa; sin etiqueta = 25 % de la venta. Las lecturas dudosas no suman. Con
datos reales se calibran.

**"¿Y si el OCR se equivoca?"**
Cada dato se vota entre varios cuadros. Si la lectura es dudosa (poca confianza o pocas
lecturas), sale en ámbar como "revisar" y no cuenta como problema ni suma dinero. Además cada
hallazgo trae la foto para confirmarlo.

**"¿Necesito poner marcadores en toda la tienda?"**
No. Los marcadores dan máxima precisión, pero con solo el planograma y un celular ya funciona,
y sin nada se pueden leer etiquetas y buscar huecos.

**"¿Por qué no multiplican todo por las 38 tiendas?"**
Porque un hueco o una etiqueta faltante es de esta tienda. Solo se proyecta lo que nace en el
corporativo (el precio de la lista anterior), y en escenarios, no como una sola cifra.

**"¿Qué tan rápido es?"**
Un clip de 10 s en 4K tarda 19 s en una laptop solo con CPU; un recorrido de 23 s, unos 40 s.
En la demo en vivo, 9 a 13 s.

**"¿Qué pasa con la privacidad?"**
Todo corre en la laptop. Lo único que sale es lo que se le pregunta al asistente: los datos de
la corrida, no el video ni las fotos.

---

## 13. Cifras clave (acordeón)

| Dato | Valor |
|---|---|
| Problemas en un anaquel del demo | 8 |
| Dinero en juego en ese anaquel | US$285.15 al día |
| Error más caro | Hueco con inventario: US$80.91 al día |
| Red de la cadena | 38 tiendas |
| Precio viejo en la red (escenario central / peor caso) | US$187.20 / US$769.60 al día |
| Etiquetas y precios leídos bien | 100 % (11/11) |
| Huecos encontrados / falsos | 100 % / 0 |
| Tiempo, clip de 10 s en 4K | 19 s (CPU) |
| Demo en vivo | 9 a 13 s por video |
| Prueba con celular | 11 etiquetas leídas, 7 de 8 errores, $3,511.18 al día (pesos) |
