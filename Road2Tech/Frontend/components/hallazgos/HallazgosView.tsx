'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, RotateCcw, Check, Clock, Filter, Layers, TrendingUp } from 'lucide-react';
import { SalidaHallazgos, Hallazgo } from '@/types/hallazgos';
import {
  EVIDENCIA_VACIA,
  formatearMoneda,
  traducirTipoHallazgo,
  ubicacionCorta,
} from '@/lib/formatters/contract';
import { Proporcion } from '@/components/graficas/Barras';
import { ICONO_DATO, ICONO_PANTALLA, iconoTipo } from '@/components/iconos';
import { TituloPagina } from '@/components/layout/TituloPagina';

interface HallazgosViewProps {
  data: SalidaHallazgos;
}

export function HallazgosView({ data }: HallazgosViewProps) {
  const fm = (monto: number | null | undefined) => formatearMoneda(monto, data.resumen.moneda ?? 'US$');
  const libre = data.resumen.modo === 'libre';
  // Estado local para correcciones
  const [hallazgosState, setHallazgosState] = useState<Hallazgo[]>(
    [...data.hallazgos].sort((a, b) => b.impacto_diario - a.impacto_diario)
  );
  const [filtroTipo, setFiltroTipo] = useState<string>('todos');
  const [filtroEstado, setFiltroEstado] = useState<'todos' | 'pendientes' | 'corregidos'>('todos');

  // Marcar corregido solo cambia esta vista: no se guarda en ningún lado
  const toggleCorregido = (id: string) => {
    setHallazgosState((prev) => prev.map((h) => (h.id === id ? { ...h, corregido: !h.corregido } : h)));
  };

  // Cálculo dinámico según correcciones locales
  const pendientes = hallazgosState.filter((h) => !h.corregido);
  const corregidos = hallazgosState.filter((h) => h.corregido);
  const totalRiesgoPendiente = pendientes.reduce((acc, h) => acc + h.impacto_diario, 0);
  const totalRecuperado = corregidos.reduce((acc, h) => acc + h.impacto_diario, 0);
  const totalRiesgo = totalRiesgoPendiente + totalRecuperado;

  // Filtrado de lista
  const hallazgosFiltrados = hallazgosState.filter((h) => {
    if (filtroEstado === 'pendientes' && h.corregido) return false;
    if (filtroEstado === 'corregidos' && !h.corregido) return false;
    if (filtroTipo !== 'todos' && h.tipo !== filtroTipo) return false;
    return true;
  });

  const filtrosEstado = [
    { id: 'todos', icono: Layers, texto: `Todos (${hallazgosState.length})` },
    { id: 'pendientes', icono: Clock, texto: `Pendientes (${pendientes.length})` },
    { id: 'corregidos', icono: CheckCircle2, texto: `Corregidos (${corregidos.length})` },
  ] as const;

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <TituloPagina icono={ICONO_PANTALLA.hallazgos} titulo="Hallazgos">
          De mayor a menor impacto diario. Marcar como corregido solo cambia esta vista; no se guarda.
        </TituloPagina>
        {/* Avance: el dinero de lo ya corregido sobre el total */}
        <div className="w-full md:w-80 text-sm text-slate-500">
          <div className="md:text-right">
            <span className="text-xl font-bold text-rose-600 font-tabular">{fm(totalRiesgoPendiente)}</span>
            <span className="text-slate-400">/día pendientes</span>
          </div>
          <Proporcion
            pct={totalRiesgo > 0 ? (totalRecuperado / totalRiesgo) * 100 : 0}
            tono="bg-emerald-600"
            className="mt-2"
          />
          <div className="mt-1.5 flex justify-between gap-3 text-xs font-tabular">
            <span className="inline-flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-slate-400" />
              {corregidos.length} de {hallazgosState.length} corregidos
            </span>
            <span className={`inline-flex items-center gap-1 ${totalRecuperado > 0 ? 'text-emerald-700 font-medium' : ''}`}>
              <TrendingUp className={`w-3.5 h-3.5 ${totalRecuperado > 0 ? 'text-emerald-600' : 'text-slate-400'}`} />
              {fm(totalRecuperado)}/día recuperados
            </span>
          </div>
        </div>
      </div>

      {/* Filtros */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center bg-slate-100 p-0.5 rounded-lg text-xs font-medium">
          {filtrosEstado.map((f) => (
            <button
              key={f.id}
              onClick={() => setFiltroEstado(f.id)}
              aria-pressed={filtroEstado === f.id}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors ${
                filtroEstado === f.id ? 'bg-white text-slate-900 shadow-sm font-semibold' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <f.icono className={`w-3.5 h-3.5 ${filtroEstado === f.id ? 'text-teal-600' : 'text-slate-400'}`} />
              {f.texto}
            </button>
          ))}
        </div>

        <div className="relative">
          <Filter className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <select
            value={filtroTipo}
            onChange={(e) => setFiltroTipo(e.target.value)}
            aria-label="Filtrar por tipo de problema"
            className="text-xs border border-slate-200 rounded-lg pl-8 pr-3 py-1.5 bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-teal-500"
          >
            <option value="todos">Todos los tipos</option>
            <option value="precio_anterior">Etiqueta con precio viejo</option>
            <option value="precio_distinto">Precio distinto al sistema</option>
            <option value="hueco_con_inventario">Hueco, pero el sistema dice que hay</option>
            <option value="etiqueta_faltante">Falta la etiqueta</option>
            <option value="frentes_bajos">Pocos frentes</option>
            <option value="etiqueta_otro_sku">Etiqueta de otro producto</option>
            <option value="producto_equivocado">Producto en lugar equivocado</option>
            <option value="hueco_agotado">Agotado: pedir resurtido</option>
            {libre && <option value="hueco">Hueco en anaquel</option>}
            {libre && <option value="precio_inconsistente">Mismo producto, precios distintos</option>}
            <option value="revisar">Lectura dudosa: revisar</option>
          </select>
        </div>
      </div>

      <div className="space-y-3">
        {hallazgosFiltrados.length === 0 ? (
          <div className="bg-white p-12 rounded-xl border border-slate-200 text-center space-y-2">
            <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
            <h4 className="font-semibold text-slate-800">Sin hallazgos en este filtro</h4>
          </div>
        ) : (
          hallazgosFiltrados.map((hallazgo, idx) => {
            const isCorregido = hallazgo.corregido;
            const Icono = isCorregido ? CheckCircle2 : iconoTipo(hallazgo.tipo);
            return (
              <motion.div
                key={hallazgo.id}
                id={hallazgo.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, delay: idx * 0.03 }}
                className={`bg-white rounded-xl border border-slate-200 p-5 transition-opacity scroll-mt-20 ${isCorregido ? 'opacity-60' : ''}`}
              >
                <div className="grid grid-cols-1 md:grid-cols-12 gap-5 items-center">
                  <div className="md:col-span-3 rounded-lg overflow-hidden bg-slate-900 aspect-video">
                    <img
                      src={hallazgo.evidencia_crop || EVIDENCIA_VACIA}
                      alt={`Recorte de ${hallazgo.producto} (cuadro ${hallazgo.cuadro})`}
                      className="w-full h-full object-cover"
                    />
                  </div>

                  <div className="md:col-span-6 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                      <span className={`inline-flex items-center gap-1 font-medium ${isCorregido ? 'text-emerald-700' : 'text-rose-600'}`}>
                        <Icono className="w-3.5 h-3.5" />
                        {traducirTipoHallazgo(hallazgo.tipo)}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <ICONO_DATO.ubicacion className="w-3.5 h-3.5 text-slate-400" />
                        {ubicacionCorta(hallazgo)}
                      </span>
                      {hallazgo.sku && (
                        <span className="inline-flex items-center gap-1">
                          <ICONO_DATO.sku className="w-3.5 h-3.5 text-slate-400" />
                          {hallazgo.sku}
                        </span>
                      )}
                    </div>
                    <h3 className={`text-base font-semibold text-slate-900 ${isCorregido ? 'line-through' : ''}`}>
                      {hallazgo.producto}
                    </h3>
                    <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600 font-tabular">
                      {hallazgo.precio_etiqueta && hallazgo.precio_etiqueta > 0 ? (
                        <span className="inline-flex items-center gap-1.5">
                          <ICONO_DATO.etiqueta className="w-3.5 h-3.5 text-slate-400" />
                          Etiqueta <span className="font-semibold text-rose-600">{fm(hallazgo.precio_etiqueta)}</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-amber-700">
                          <ICONO_DATO.etiqueta className="w-3.5 h-3.5" />
                          Sin etiqueta
                        </span>
                      )}
                      {hallazgo.precio_sistema !== null ? (
                        <span className="inline-flex items-center gap-1.5">
                          <ICONO_DATO.sistema className="w-3.5 h-3.5 text-slate-400" />
                          Sistema <span className="font-semibold text-slate-900">{fm(hallazgo.precio_sistema)}</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-slate-500">
                          <ICONO_DATO.sistema className="w-3.5 h-3.5 text-slate-400" />
                          Sin datos del sistema
                        </span>
                      )}
                    </p>
                    <p className="text-sm text-slate-500 leading-relaxed">{hallazgo.descripcion}</p>
                    <p className="flex items-start gap-1.5 text-sm text-slate-600 leading-relaxed">
                      <ICONO_DATO.accion className="w-4 h-4 text-teal-600 shrink-0 mt-0.5" />
                      <span>
                        <span className="font-medium text-slate-900">Acción sugerida:</span> {hallazgo.accion_sugerida}
                      </span>
                    </p>
                  </div>

                  <div className="md:col-span-3 flex md:flex-col items-center md:items-end justify-between gap-4">
                    <div className="text-2xl font-bold font-tabular">
                      <span className={isCorregido ? 'text-slate-400 line-through' : 'text-rose-600'}>
                        {fm(hallazgo.impacto_diario)}
                      </span>
                      <span className="text-sm font-normal text-slate-400">/día</span>
                    </div>
                    <button
                      onClick={() => toggleCorregido(hallazgo.id)}
                      className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold border transition-colors ${
                        isCorregido
                          ? 'border-slate-200 text-slate-600 hover:bg-slate-50'
                          : 'border-emerald-600 text-emerald-700 hover:bg-emerald-50'
                      }`}
                    >
                      {isCorregido ? <RotateCcw className="w-3.5 h-3.5" /> : <Check className="w-3.5 h-3.5" />}
                      {isCorregido ? 'Deshacer corrección' : 'Marcar corregido'}
                    </button>
                  </div>
                </div>
              </motion.div>
            );
          })
        )}
      </div>
    </div>
  );
}
