// Cliente del navegador para los videos subidos. /motor/* llega a la API del motor por el
// rewrite de next.config.ts, así que todo sale del mismo origen.
import {
  AnalisisMeta,
  DetectorMotor,
  EstadoAsistente,
  ListaAnalisis,
  MensajeChat,
  RespuestaChat,
} from '@/types/analisis';

const BASE = '/motor/analisis';

export const EXTENSIONES_VIDEO = ['.mp4', '.mov', '.m4v', '.avi', '.mkv', '.webm'];
export const MAX_BYTES_VIDEO = 4 * 1024 ** 3;

async function pedir<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, { cache: 'no-store', ...init });
  } catch {
    throw new Error('La API del motor no responde.');
  }
  const datos = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(datos?.error || `La API del motor respondió ${res.status}.`);
  }
  return datos as T;
}

export const listarAnalisis = () => pedir<ListaAnalisis>(BASE);
export const consultarAnalisis = (id: string) => pedir<AnalisisMeta>(`${BASE}/${id}`);
export const activarAnalisis = (id: string | null) =>
  pedir<{ activo: string | null }>(`${BASE}/${id ?? 'demo'}/activar`, { method: 'POST' });
export const borrarAnalisis = (id: string) => pedir<{ borrado: string }>(`${BASE}/${id}`, { method: 'DELETE' });

/** Asistente: `id` es el del análisis o "demo"; el historial va sin las fuentes. */
export const preguntarCorrida = (id: string, pregunta: string, historial: MensajeChat[]) =>
  pedir<RespuestaChat>(`${BASE}/${id}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pregunta, historial: historial.map(({ rol, texto }) => ({ rol, texto })) }),
  });
export const estadoAsistente = () => pedir<EstadoAsistente>('/motor/chat');

/**
 * Sube el video y arranca el motor. Usa XMLHttpRequest porque fetch no informa el avance
 * de la subida.
 */
export function subirVideo(
  archivo: File,
  opciones: { detector: DetectorMotor; identificar: boolean; planograma: boolean },
  alAvanzar: (fraccion: number) => void
): Promise<AnalisisMeta> {
  const q = new URLSearchParams({
    nombre: archivo.name,
    detector: opciones.detector,
    identificar: opciones.identificar ? '1' : '0',
    planograma: opciones.detector === 'libre' && opciones.planograma ? '1' : '0',
  });
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${BASE}?${q}`);
    xhr.setRequestHeader('Content-Type', archivo.type || 'application/octet-stream');
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) alAvanzar(e.loaded / e.total);
    };
    xhr.onload = () => {
      let datos: any = null;
      try {
        datos = JSON.parse(xhr.responseText);
      } catch {
        // respuesta sin JSON: la API no está detrás del rewrite
      }
      if (xhr.status >= 200 && xhr.status < 300 && datos) {
        resolve(datos as AnalisisMeta);
      } else {
        reject(new Error(datos?.error || `La API del motor respondió ${xhr.status}.`));
      }
    };
    xhr.onerror = () => reject(new Error('La API del motor no responde.'));
    xhr.send(archivo);
  });
}
