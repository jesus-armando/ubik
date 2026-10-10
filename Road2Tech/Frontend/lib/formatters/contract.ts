import { TipoHallazgo, EstadoPosicion } from '@/types/hallazgos';

/**
 * Diccionario de textos obligatorios según frontend.pdf
 */
export const DICCIONARIO_HALLAZGOS: Record<TipoHallazgo, string> = {
  precio_anterior: 'Etiqueta con precio viejo',
  etiqueta_faltante: 'Falta la etiqueta',
  etiqueta_otro_sku: 'Etiqueta de otro producto',
  hueco_con_inventario: 'Hueco, pero el sistema dice que hay',
  hueco_agotado: 'Agotado: pedir resurtido',
  frentes_bajos: 'Pocos frentes',
  revisar: 'Lectura dudosa: revisar',
  precio_distinto: 'Precio distinto al sistema',
  producto_equivocado: 'Producto en lugar equivocado',
  hueco: 'Hueco en anaquel',
  precio_inconsistente: 'Mismo producto, precios distintos',
};

/**
 * Familias de problema para agrupar el dinero en juego según quién lo corrige: reposición
 * (huecos), acomodo del anaquel o etiquetas y precios.
 */
export const FAMILIAS_HALLAZGO: { id: string; nombre: string; tipos: TipoHallazgo[] }[] = [
  { id: 'huecos', nombre: 'Huecos y existencias', tipos: ['hueco_con_inventario', 'hueco_agotado', 'hueco'] },
  { id: 'acomodo', nombre: 'Acomodo del anaquel', tipos: ['producto_equivocado', 'frentes_bajos'] },
  {
    id: 'etiquetas',
    nombre: 'Etiquetas y precios',
    tipos: ['precio_anterior', 'etiqueta_faltante', 'etiqueta_otro_sku', 'precio_distinto', 'precio_inconsistente'],
  },
  { id: 'revisar', nombre: 'Lecturas dudosas', tipos: ['revisar'] },
];

export interface TotalFamilia {
  id: string;
  nombre: string;
  cantidad: number;
  monto: number;
}

/** Cuántos problemas y cuánto dinero al día hay en cada familia, de mayor a menor monto. */
export function totalesPorFamilia(hallazgos: { tipo: string; impacto_diario: number }[]): TotalFamilia[] {
  const totales = new Map<string, TotalFamilia>();
  for (const h of hallazgos) {
    const f = FAMILIAS_HALLAZGO.find((fam) => (fam.tipos as string[]).includes(h.tipo)) ?? {
      id: 'otros',
      nombre: 'Otros',
    };
    const t = totales.get(f.id) ?? { id: f.id, nombre: f.nombre, cantidad: 0, monto: 0 };
    t.cantidad += 1;
    t.monto += h.impacto_diario || 0;
    totales.set(f.id, t);
  }
  return [...totales.values()].sort((a, b) => b.monto - a.monto || b.cantidad - a.cantidad);
}

/** Imagen neutra cuando el motor no dejó recorte de esa posición. */
export const EVIDENCIA_VACIA = '/evidencias/sin_recorte.svg';

/**
 * Traduce un valor interno a su texto amigable visible.
 */
export function traducirTipoHallazgo(tipo?: string | null): string {
  if (!tipo) return 'Sin incidencia';
  if (tipo in DICCIONARIO_HALLAZGOS) {
    return DICCIONARIO_HALLAZGOS[tipo as TipoHallazgo];
  }
  // En caso de un valor inesperado, mostrar etiqueta alternativa comprensible
  return `Incidencia no clasificada (${tipo})`;
}

/**
 * Traduce el estado de una posición del anaquel.
 */
export function traducirEstadoPosicion(estado: EstadoPosicion): string {
  switch (estado) {
    case 'ok':
      return 'Correcto';
    case 'error':
      return 'Error detectado';
    case 'revisar':
      return 'Lectura dudosa: revisar';
    default:
      return 'Desconocido';
  }
}

/**
 * Formateador de dinero en español de México (es-MX) con el símbolo dado: US$25.80 en el
 * recorrido de demostración, $32.90 en un video sin estructura (precios leídos tal cual).
 */
export function formatearMoneda(monto: number | null | undefined, simbolo = 'US$'): string {
  if (monto === null || monto === undefined || isNaN(monto)) {
    return `${simbolo}0.00`;
  }
  const valorFormateado = new Intl.NumberFormat('es-MX', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(monto);

  return `${simbolo}${valorFormateado}`;
}

/**
 * Formateador de dinero en formato US$25.80 y números en español de México (es-MX).
 */
export function formatearMonedaUSD(monto: number | null | undefined): string {
  return formatearMoneda(monto, 'US$');
}

/**
 * Formatea el precio de etiqueta considerando etiquetas ausentes o no detectadas.
 */
export function formatearPrecioEtiqueta(precio: number | null | undefined, simbolo = 'US$'): string {
  if (precio === null || precio === undefined || precio <= 0) {
    return 'Sin etiqueta';
  }
  return formatearMoneda(precio, simbolo);
}

/** Dónde está la posición: "R1-P2" con planograma, "E3" en un video sin estructura. */
export function ubicacionCorta(p: { repisa: number; posicion: number; ubicacion?: string }): string {
  return p.ubicacion ? p.ubicacion.replace(/^Etiqueta\s+/, '') : `R${p.repisa}-P${p.posicion}`;
}

/** "Repisa 1, Posición 2" con planograma, o la ubicación del modo sin estructura. */
export function ubicacionLarga(p: { repisa: number; posicion: number; ubicacion?: string }): string {
  return p.ubicacion ?? `Repisa ${p.repisa}, Posición ${p.posicion}`;
}

/**
 * Formateador de números enteros o decimales en español de México.
 */
export function formatearNumero(numero: number | null | undefined): string {
  if (numero === null || numero === undefined || isNaN(numero)) {
    return '0';
  }
  return new Intl.NumberFormat('es-MX').format(numero);
}

/**
 * Convierte un número de cuadro de video a segundos (segundo = cuadro / 30).
 */
export function cuadroASegundos(cuadro: number): number {
  return Number((cuadro / 30).toFixed(2));
}

/**
 * Formatea segundos a formato de video mm:ss.
 */
export function formatearTiempoVideo(segundos: number): string {
  const mins = Math.floor(segundos / 60);
  const secs = Math.floor(segundos % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}
