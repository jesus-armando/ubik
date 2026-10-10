export type TipoHallazgo =
  | 'precio_anterior'
  | 'etiqueta_faltante'
  | 'etiqueta_otro_sku'
  | 'hueco_con_inventario'
  | 'hueco_agotado'
  | 'frentes_bajos'
  | 'revisar'
  | 'precio_distinto'
  | 'producto_equivocado'
  // modo sin estructura (videos sin marcadores ni planograma)
  | 'hueco'
  | 'precio_inconsistente';

export type EstadoPosicion = 'ok' | 'error' | 'revisar';

export interface ResumenAnaquel {
  total_problemas: number;
  dinero_en_riesgo_diario: number;
  frase: string;
  etiquetas_con_error: number;
  huecos_inventario: number;
  lecturas_dudosas: number;
  precision_anaquel_pct: number;
  tienda_id?: string;
  tienda_nombre?: string;
  fecha_escaneo?: string;
  disclaimer: string;
  // Extras del cruce con la salida del motor (motor-procesamiento/cruce)
  modo?: 'contrato' | 'libre' | 'orden'; // libre: sin marcadores ni planograma (p. ej. video de IA); orden: sin marcadores, con el planograma de la demo
  recorrido?: string; // modo orden: cómo pasó la cámara por el anaquel
  moneda?: string; // símbolo de los montos; por omisión US$
  video?: string;
  video_url?: string | null; // video anotado; sin él, el del recorrido de demostración
  analisis_id?: string; // solo en videos subidos desde la pantalla "Subir video"
  segundos_proceso?: number;
  fps?: number;
  supuestos_calculo?: string;
}

export interface PosicionAnaquel {
  id: string;
  repisa: number; // 1, 2, 3
  posicion: number; // 1, 2, 3, 4
  estado: EstadoPosicion;
  sku: string;
  producto: string;
  ubicacion?: string; // modo libre: "Etiqueta E3" en lugar de repisa y posición
  precio_etiqueta: number | null;
  precio_sistema: number | null; // null: sin datos del sistema (modo libre)
  frentes: number | null; // null: la zona de producto no se vio completa en el video
  frentes_esperados?: number;
  inventario_sistema: number | null;
  hallazgo_id: string | null;
  tipo?: TipoHallazgo;
  impacto_diario?: number;
  accion?: string;
  evidencia?: string | null;
}

export interface Hallazgo {
  id: string;
  tipo: TipoHallazgo;
  producto: string;
  sku: string;
  repisa: number;
  posicion: number;
  ubicacion?: string;
  precio_etiqueta: number | null;
  precio_sistema: number | null;
  impacto_diario: number;
  cuadro: number;
  segundo: number;
  descripcion: string;
  accion_sugerida: string;
  evidencia_crop: string | null;
  corregido: boolean;
  confianza_precio?: number;
}

export interface SalidaHallazgos {
  resumen: ResumenAnaquel;
  posiciones: PosicionAnaquel[];
  hallazgos: Hallazgo[];
}
