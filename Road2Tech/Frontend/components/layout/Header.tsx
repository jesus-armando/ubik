'use client';

import React from 'react';
import { CalendarClock, FlaskConical } from 'lucide-react';

function formatearFechaEscaneo(fecha?: string): string | null {
  if (!fecha) return null;
  const d = new Date(fecha);
  if (isNaN(d.getTime())) return null;
  const dia = d.toLocaleDateString('es-MX', { day: '2-digit', month: '2-digit', year: 'numeric' });
  const hora = d.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', hour12: false });
  return `${dia} ${hora} hrs`;
}

export function Header({
  fechaEscaneo,
  disclaimer = 'Video simulado · Datos sintéticos de Glazed Co.',
}: {
  fechaEscaneo?: string;
  disclaimer?: string;
}) {
  const fecha = formatearFechaEscaneo(fechaEscaneo);
  return (
    <header className="h-12 bg-white/90 backdrop-blur border-b border-slate-200 px-6 flex items-center gap-5 text-xs text-slate-500 sticky top-0 z-20">
      {/* Aviso obligatorio de honestidad: de dónde salen el video y los datos */}
      <span className="flex items-center gap-1.5 text-slate-600">
        <FlaskConical className="w-3.5 h-3.5 text-amber-600" aria-hidden />
        {disclaimer}
      </span>
      {fecha && (
        <span className="hidden md:inline-flex items-center gap-1.5">
          <CalendarClock className="w-3.5 h-3.5 text-slate-400" aria-hidden />
          Escaneo {fecha}
        </span>
      )}
    </header>
  );
}
