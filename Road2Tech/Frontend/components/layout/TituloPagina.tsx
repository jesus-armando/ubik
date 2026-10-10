import React from 'react';
import type { LucideIcon } from 'lucide-react';

/** Título de pantalla con el mismo ícono que la pantalla tiene en el menú lateral. */
export function TituloPagina({
  icono: Icono,
  titulo,
  children,
}: {
  icono: LucideIcon;
  titulo: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3">
      <span
        className="mt-0.5 w-9 h-9 rounded-lg bg-teal-50 text-teal-700 ring-1 ring-inset ring-teal-100 flex items-center justify-center shrink-0"
        aria-hidden="true"
      >
        <Icono className="w-5 h-5" />
      </span>
      <div className="min-w-0">
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">{titulo}</h2>
        {children && <p className="text-slate-500 text-sm mt-1">{children}</p>}
      </div>
    </div>
  );
}
