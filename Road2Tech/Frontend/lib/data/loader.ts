import fs from 'fs';
import path from 'path';
import { SalidaHallazgos } from '@/types/hallazgos';
import { API_MOTOR_URL } from '@/lib/api/session';

/**
 * Hallazgos que muestra el tablero: el último video subido y procesado por el motor (análisis
 * activo en la API), o el recorrido de demostración de public/salida/ si no hay o la API está
 * apagada. Se lee en cada petición (fetch sin caché), así que las pantallas son dinámicas.
 */
export async function getHallazgosData(): Promise<SalidaHallazgos> {
  try {
    const res = await fetch(`${API_MOTOR_URL}/analisis/activo`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(1500),
    });
    if (res.ok) {
      return (await res.json()) as SalidaHallazgos;
    }
  } catch {
    // API del motor apagada: recorrido de demostración
  }
  return getHallazgosDemo();
}

/**
 * Carga segura de hallazgos.json desde public/salida/ (recorrido de demostración)
 */
export function getHallazgosDemo(): SalidaHallazgos {
  try {
    const filePath = path.join(process.cwd(), 'public', 'salida', 'hallazgos.json');
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, 'utf-8');
      return JSON.parse(content) as SalidaHallazgos;
    }
  } catch (error) {
    console.error('Error al leer public/salida/hallazgos.json:', error);
  }

  // Estado seguro por defecto en caso de ausencia
  return {
    resumen: {
      total_problemas: 0,
      dinero_en_riesgo_diario: 0,
      frase: '0 problemas detectados · Anaquel sin incidencias reportadas',
      etiquetas_con_error: 0,
      huecos_inventario: 0,
      lecturas_dudosas: 0,
      precision_anaquel_pct: 100,
      disclaimer: 'Video simulado · Datos sintéticos de Glazed Co.',
    },
    posiciones: [],
    hallazgos: [],
  };
}
