# Manual de Diseño y Sistema Visual: Road2Tech / Glazed Co. Dashboard

## 1. Objetivos Visuales y Filosofía de Diseño

Este sistema de interfaz está concebido específicamente para **gerentes de supermercado y miembros del jurado evaluador**. Su propósito primordial es la **comunicación operativa inmediata**:
- **Regla de los 10 segundos**: El usuario debe entender en un primer vistazo el problema detectado en el anaquel, el monto económico diario en riesgo, la ubicación precisa del producto y la acción correctiva recomendada.
- **Tono y Personalidad**: Preciso, confiable, sobrio e industrial (*Precision Retail / Industrial Slate*). Evita decoraciones innecesarias, gradientes estridentes o modas de software genérico de TI que resten legibilidad a las métricas numéricas.
- **Honestidad e Integridad de Datos**: Se exhibe de manera discreta pero permanente en la barra superior: `"Video simulado · Datos sintéticos de Glazed Co."`.

---

## 2. Paleta de Colores y Tokens Semánticos

La paleta sigue una estricta jerarquía de contraste WCAG AA (mínimo 4.5:1 para texto normal, 3:1 para componentes y bordes interactivos):

### 2.1 Colores Principales y Estructura
- **Fondo General (`--bg-app`)**: `#F8FAFC` (Slate 50) — superficie limpia, sin fatiga visual.
- **Fondo de Tarjetas y Paneles (`--bg-surface`)**: `#FFFFFF` (Blanco puro) — contraste nítido.
- **Superficie Secundaria / Muted (`--bg-muted`)**: `#F1F5F9` (Slate 100) — fondos de tablas, badges y chips.
- **Bordes y Divisores (`--border-subtle`)**: `#E2E8F0` (Slate 200) — delimitación estructural nítida.
- **Borde de Énfasis (`--border-strong`)**: `#CBD5E1` (Slate 300).
- **Texto Principal (`--text-main`)**: `#0F172A` (Slate 900) — máxima legibilidad para proyector.
- **Texto Secundario (`--text-muted`)**: `#475569` (Slate 600) — descripciones y metadatos.
- **Color Principal de Acento / CTA (`--accent-primary`)**: `#0D9488` (Teal 600) / Hover: `#0F766E` (Teal 700).

### 2.2 Colores de Estado Semántico
Cada estado incorpora un color de alto contraste, un ícono distintivo y un texto descriptivo, garantizando que el color nunca sea el único canal de información:
- **Correcto (OK)**:
  - Color: `#16A34A` (Green 600) | Fondo suave: `#DCFCE7` (Green 100) | Borde: `#86EFAC` (Green 300)
  - Ícono: `CheckCircle2` | Texto: `"Correcto / Alineado"`
- **Error Crítico (Alerta)**:
  - Color: `#DC2626` (Red 600) | Fondo suave: `#FEE2E2` (Red 100) | Borde: `#FCA5A5` (Red 300)
  - Ícono: `AlertTriangle` | Texto: `"Error / Discrepancia"`
- **Requiere Revisión (Atención)**:
  - Color: `#D97706` (Amber 600) | Fondo suave: `#FEF3C7` (Amber 100) | Borde: `#FCD34D` (Amber 300)
  - Ícono: `AlertCircle` | Texto: `"Lectura dudosa / Revisar"`

---

## 3. Tipografía Local y Escala para Proyectores

Para garantizar el funcionamiento **100% offline (sin Wi-Fi)**, no se utiliza Google Fonts ni CDN. Se instalan y empaquetan localmente:
- **Fuente Principal de Interfaz**: `Inter` (vía `@fontsource/inter`) — excelente legibilidad en pantalla y proyector.
- **Cifras y moneda**: la misma `Inter` con dígitos tabulares (clase `font-tabular`, `font-variant-numeric: tabular-nums`) — ancho fijo para que las cifras no salten ni se desalineen en columnas, sin mezclar una segunda tipografía.

### Escala Tipográfica (Optimizada para 1920x1080 y 1280x720)
| Rol | Tamaño | Peso | Interlínea | Uso |
| :--- | :--- | :--- | :--- | :--- |
| **Hero Frase Principal** | `32px` (`2rem`) en FHD / `24px` en HD | Bold (700) | `1.2` | Frase gigante de resumen de impacto |
| **KPI Gigante** | `28px` (`1.75rem`) | SemiBold (600) | `1.1` | Cifras económicas en tarjetas principales |
| **Título de Sección H1** | `22px` (`1.375rem`) | Bold (700) | `1.3` | Encabezados de pantalla |
| **Subtítulo H2 / Tarjetas**| `16px` (`1rem`) | SemiBold (600) | `1.4` | Títulos de hallazgos y repisas |
| **Texto de Cuerpo** | `14px` (`0.875rem`) | Normal (400) | `1.5` | Descripciones, acciones y tablas |
| **Metadato / Badge** | `12px` (`0.75rem`) | Medium (500) | `1.4` | SKUs, etiquetas y notas técnicas |

---

## 4. Reglas de Espaciado y Cuadrícula

- Sistema modular basado en múltiplos de **4px** y **8px**:
  - `space-1`: 4px | `space-2`: 8px | `space-3`: 12px | `space-4`: 16px | `space-6`: 24px | `space-8`: 32px
- **Contenedores de Pantalla**: `max-w-7xl` centrado, con padding horizontal de `24px` en 1920x1080 y `16px` en 1280x720.
- **Espaciado vertical estricto**: Evitar márgenes excesivos que obliguen a hacer scroll innecesario en laptops a 720p.

---

## 5. Componentes Clave y Estilos Específicos

### 5.1 Gemelo Digital del Anaquel (Pantalla 3)
- **Estructura física**: Rejilla de 3 filas horizontales (repisas) por 4 columnas (posiciones).
- **Repisas**: panel blanco; cada repisa es una fila de 4 posiciones sobre una línea gris tenue (`slate-200`).
- **Bloques de Producto**:
  - Proporción compacta con bordes redondeados (`rounded-lg`).
  - Estado en la esquina superior con ícono y texto (Correcto / Error / Revisar), sobre un fondo tenue del color del estado.
  - Precio legible en fuente tabular monoespaciada.
  - Al interactuar (`hover` / `focus`), elevación limpia de 2px y borde destacado.
  - Al hacer clic, apertura suave del panel lateral con evidencia fotográfica.

### 5.2 Tarjetas de Hallazgos (Pantalla 4)
- Ordenadas de mayor a menor impacto económico diario (`impacto_diario`).
- Cada tarjeta contiene:
  1. Recorte de evidencia fotográfica de la etiqueta con indicador de bounding box.
  2. Nombre del producto y SKU.
  3. Comparativa visual clara: `"Etiqueta dice US$X.XX"` vs `"Sistema dice US$Y.YY"`.
  4. Impacto económico diario resaltado en rojo suave / badge de alerta.
  5. Acción correctiva sugerida explícita.
  6. Botón `"Marcar corregido"` que actualiza el estado local y muestra feedback claro.

---

## 6. Reglas de Animación y Accesibilidad

- **Micro-interacciones**: Transiciones estándar de 150ms a 200ms con curva `cubic-bezier(0.16, 1, 0.3, 1)`.
- **Entrada escalonada (Framer Motion)**:
  - Repisas del anaquel y tarjetas de hallazgo: retardo de `0.04s` entre elementos.
  - Tiempo máximo total de aparición: menor a `400ms` para mantener la agilidad de la demo.
- **Soporte `prefers-reduced-motion`**: Si el usuario o el sistema tiene activada la reducción de movimiento, las transiciones se sustituyen por cambios inmediatos de opacidad sin desplazamiento.
- **Accesibilidad para Proyector**:
  - Controles navegables con teclado (`Tab` y `Enter/Space`).
  - Anillos de foco visibles (`ring-2 ring-teal-500 ring-offset-2`).
  - Todo dato numérico cuenta con su unidad y etiqueta comprensible.

---

## 7. Sobriedad

- Sin píldoras ni insignias decorativas: el estado se dice con texto (y color cuando es un estado).
- Cada dato aparece una sola vez por pantalla (p. ej., el tiempo del video vive en los controles, no encima del video).
- Etiquetas en tipografía normal; nada de mayúsculas con tracking ni monoespaciada salvo comandos de terminal.
- Tarjetas blancas con borde `slate-200`, sin sombras; un solo botón principal (teal) por bloque, los demás con contorno o como texto.
