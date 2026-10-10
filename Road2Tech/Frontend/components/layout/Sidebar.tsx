'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Store } from 'lucide-react';
import { ICONO_PANTALLA } from '@/components/iconos';

interface NavItem {
  nombre: string;
  ruta: string;
  icono: React.ElementType;
}

// Entrada de datos: un video nuevo que procesa el motor
const ENTRADA: NavItem[] = [{ nombre: 'Subir video', ruta: '/analizar', icono: ICONO_PANTALLA.analizar }];

const NAVEGACION: NavItem[] = [
  { nombre: 'Resumen', ruta: '/resumen', icono: ICONO_PANTALLA.resumen },
  { nombre: 'Recorrido', ruta: '/recorrido', icono: ICONO_PANTALLA.recorrido },
  { nombre: 'Anaquel', ruta: '/anaquel', icono: ICONO_PANTALLA.anaquel },
  { nombre: 'Hallazgos', ruta: '/hallazgos', icono: ICONO_PANTALLA.hallazgos },
  { nombre: 'Asistente', ruta: '/asistente', icono: ICONO_PANTALLA.asistente },
];

export function Sidebar() {
  const pathname = usePathname();

  const enlace = (item: NavItem) => {
    const Icon = item.icono;
    const isActive = pathname === item.ruta || (item.ruta === '/resumen' && pathname === '/');
    return (
      <Link
        key={item.ruta}
        href={item.ruta}
        className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
          isActive
            ? 'bg-slate-800 text-white font-semibold'
            : 'text-slate-400 hover:bg-slate-800/60 hover:text-white'
        }`}
      >
        <Icon className={`w-4 h-4 ${isActive ? 'text-teal-400' : 'text-slate-500'}`} />
        {item.nombre}
      </Link>
    );
  };

  return (
    <aside className="w-60 bg-slate-900 text-slate-100 flex flex-col h-screen fixed left-0 top-0 z-30 select-none">
      <div className="px-5 h-16 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-teal-600 flex items-center justify-center text-white">
          <Store className="w-4 h-4" />
        </div>
        <div className="leading-tight">
          <h1 className="font-semibold text-sm text-white">Glazed Co.</h1>
          <p className="text-xs text-slate-400">T04 · Aeropuerto AICM</p>
        </div>
      </div>

      <nav className="flex-1 py-3 px-3 space-y-0.5 overflow-y-auto">
        {ENTRADA.map(enlace)}
        <div className="my-3 border-t border-slate-800" />
        {NAVEGACION.map(enlace)}
      </nav>
    </aside>
  );
}
