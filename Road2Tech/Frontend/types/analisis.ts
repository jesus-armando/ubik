// Videos subidos desde el tablero y procesados por el motor (motor-procesamiento/cruce/api.py)

export type DetectorMotor = 'anaquel' | 'sku110k' | 'libre';
export type EstadoAnalisis = 'procesando' | 'completado' | 'error';

export interface AnalisisMeta {
  id: string;
  nombre: string;
  creado: string;
  detector: DetectorMotor;
  identificar: boolean;
  planograma?: boolean; // solo con libre: etiquetas acomodadas en el planograma de la demo por orden
  status: EstadoAnalisis;
  paso?: string;
  pasoNumero?: number; // 1 eligiendo cuadros … 4 comparando con el sistema; 5 = terminado
  progreso?: number;
  segundos?: number;
  mensaje?: string;
  bytes?: number;
  terminado?: string;
  posiciones?: number;
  activo?: boolean;
  video?: { fps: number; cuadros: number; ancho: number; alto: number; segundos: number };
  resumen?: {
    frase: string;
    total_problemas: number;
    dinero_en_riesgo_diario: number;
    precision_anaquel_pct: number;
    segundos_proceso?: number;
  };
}

export interface ListaAnalisis {
  analisis: AnalisisMeta[];
  activo: string | null;
  ocupado: boolean;
}

// Asistente: preguntas sobre una corrida (motor-procesamiento/cruce/chat.py, Gemini)
export type RolMensaje = 'usuario' | 'asistente';

export interface FuenteRespuesta {
  id: string; // "resumen", "R1-P1", "E3", "motor" o "README#<sección>"
  titulo: string;
}

export interface MensajeChat {
  rol: RolMensaje;
  texto: string;
  fuentes?: FuenteRespuesta[];
  modelo?: string;
}

export interface RespuestaChat {
  respuesta: string;
  fuentes: FuenteRespuesta[];
  modelo: string;
  corrida: string;
}

export interface EstadoAsistente {
  configurado: boolean; // hay clave de Gemini en el .env
  modelos: string[];
  embeddings: string;
}
