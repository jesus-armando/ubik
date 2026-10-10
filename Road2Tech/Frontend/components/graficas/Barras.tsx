import React from 'react';

/**
 * Barras en HTML para las gráficas pequeñas del tablero: rankings, partes de un total y avance.
 * Cada cifra que dibujan va escrita junto a la barra, así que la barra es decorativa para lectores
 * de pantalla (aria-hidden). El color de la barra dice qué es lo importante; los textos van en tinta.
 */

const recorta = (pct: number) => (Number.isFinite(pct) ? Math.min(100, Math.max(0, pct)) : 0);

/** Barra de un ranking: crece desde la base (recta) y termina redondeada. */
export function Barra({
  pct,
  tono = 'bg-teal-600',
  className = '',
}: {
  pct: number;
  tono?: string;
  className?: string;
}) {
  const ancho = recorta(pct);
  return (
    <div className={`h-2.5 ${className}`} aria-hidden="true">
      {ancho > 0 && (
        <div className={`barra-crece h-full rounded-r ${tono}`} style={{ width: `max(${ancho}%, 3px)` }} />
      )}
    </div>
  );
}

/** Proporción sobre un total: riel gris claro y encima la parte que importa. */
export function Proporcion({
  pct,
  tono = 'bg-teal-600',
  className = '',
}: {
  pct: number;
  tono?: string;
  className?: string;
}) {
  return (
    <div className={`h-2 rounded-full bg-slate-100 overflow-hidden ${className}`} aria-hidden="true">
      <div
        className={`h-full rounded-full transition-[width] duration-300 ease-out ${tono}`}
        style={{ width: `${recorta(pct)}%` }}
      />
    </div>
  );
}

export interface ParteApilada {
  clave: string;
  valor: number;
  tono: string;
}

/** Partes de un todo en una sola barra, separadas por 2 px de aire en lugar de bordes. */
export function BarraApilada({ partes, className = '' }: { partes: ParteApilada[]; className?: string }) {
  const visibles = partes.filter((p) => p.valor > 0);
  if (visibles.length === 0) {
    return <div className={`h-2.5 rounded bg-slate-100 ${className}`} aria-hidden="true" />;
  }
  return (
    <div className={`flex h-2.5 gap-0.5 ${className}`} aria-hidden="true">
      {visibles.map((p, i) => (
        <div
          key={p.clave}
          className={`h-full ${p.tono} ${i === 0 ? 'rounded-l' : ''} ${i === visibles.length - 1 ? 'rounded-r' : ''}`}
          style={{ flex: `${p.valor} 1 0%`, minWidth: 3 }}
        />
      ))}
    </div>
  );
}

/**
 * Frentes de una posición como puntos: llenos los que se vieron, vacíos los que faltan. Con más de
 * 6 esperados los puntos dejan de leerse de un vistazo y quien la usa debe mostrar solo el texto.
 */
export function PuntosFrentes({ hay, esperados }: { hay: number; esperados: number }) {
  return (
    <span className="inline-flex items-center gap-1" aria-hidden="true">
      {Array.from({ length: Math.max(hay, esperados) }, (_, i) => (
        <span
          key={i}
          className={`w-2 h-2 rounded-full ${i < hay ? 'bg-slate-600' : 'bg-white ring-1 ring-inset ring-slate-400'}`}
        />
      ))}
    </span>
  );
}
