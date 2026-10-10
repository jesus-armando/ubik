'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MousePointerClick } from 'lucide-react';
import { SalidaHallazgos, PosicionAnaquel } from '@/types/hallazgos';
import {
  EVIDENCIA_VACIA,
  formatearMoneda,
  traducirTipoHallazgo,
  traducirEstadoPosicion,
  ubicacionCorta,
  ubicacionLarga,
} from '@/lib/formatters/contract';
import { PuntosFrentes } from '@/components/graficas/Barras';
import { ICONO_DATO, ICONO_ESTADO, ICONO_PANTALLA, iconoTipo } from '@/components/iconos';
import { TituloPagina } from '@/components/layout/TituloPagina';

// Color + ícono + texto: el color nunca es el único canal
const ESTADO = {
  ok: { icono: ICONO_ESTADO.ok, texto: 'Correcto', celda: 'bg-emerald-50/60 border-emerald-200', marca: 'text-emerald-700' },
  error: { icono: ICONO_ESTADO.error, texto: 'Error', celda: 'bg-rose-50/60 border-rose-200', marca: 'text-rose-700' },
  revisar: { icono: ICONO_ESTADO.revisar, texto: 'Revisar', celda: 'bg-amber-50/60 border-amber-200', marca: 'text-amber-700' },
} as const;
const estadoDe = (e: string) => ESTADO[e as keyof typeof ESTADO] ?? ESTADO.revisar;

// Frentes como puntos (llenos los vistos, vacíos los que faltan) cuando hay cuántos esperar
const conPuntos = (p: PosicionAnaquel): p is PosicionAnaquel & { frentes: number; frentes_esperados: number } =>
  p.frentes !== null && !!p.frentes_esperados && Math.max(p.frentes, p.frentes_esperados) <= 6;

interface AnaquelViewProps {
  data: SalidaHallazgos;
}

export function AnaquelView({ data }: AnaquelViewProps) {
  const { posiciones } = data;
  const fm = (monto: number | null | undefined) => formatearMoneda(monto, data.resumen.moneda ?? 'US$');
  // Sin planograma (video sin estructura) no hay repisas: las etiquetas van de 4 en 4
  const libre = data.resumen.modo === 'libre';
  const filas = libre
    ? Array.from({ length: Math.ceil(posiciones.length / 4) }, (_, i) => ({
        nombre: `Etiquetas ${i * 4 + 1}–${Math.min(i * 4 + 4, posiciones.length)}`,
        items: posiciones.slice(i * 4, i * 4 + 4),
      }))
    : [1, 2, 3].map((r) => ({
        nombre: `Repisa ${r}`,
        items: posiciones.filter((p) => p.repisa === r),
      }));
  const [selectedPos, setSelectedPos] = useState<PosicionAnaquel | null>(
    posiciones.find((p) => p.estado === 'error') || posiciones[0] || null
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <TituloPagina icono={ICONO_PANTALLA.anaquel} titulo={libre ? 'Etiquetas del video' : 'Anaquel'}>
          {libre
            ? `${posiciones.length} etiquetas en el orden en que aparecen. Sin marcadores ni planograma, cada etiqueta es una posición.`
            : 'Toca una posición para ver su evidencia.'}
        </TituloPagina>
        <div className="flex items-center gap-4 text-xs text-slate-500">
          {Object.entries(ESTADO).map(([clave, { icono: Icono, texto, marca }]) => (
            <span key={texto} className="inline-flex items-center gap-1.5">
              <Icono className={`w-3.5 h-3.5 ${marca}`} />
              {texto}
              <span className="font-tabular text-slate-400">({posiciones.filter((p) => p.estado === clave).length})</span>
            </span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Repisas */}
        <div className="lg:col-span-8 bg-white p-5 sm:p-6 rounded-xl border border-slate-200 space-y-6">
          {filas.map(({ nombre, items }) => (
            <div key={nombre}>
              <div className="text-xs font-medium text-slate-500 mb-2">{nombre}</div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {items.map((pos, idx) => {
                  const e = estadoDe(pos.estado);
                  const Icono = e.icono;
                  const isSelected = selectedPos?.id === pos.id;
                  return (
                    <motion.button
                      key={pos.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2, delay: idx * 0.04 }}
                      onClick={() => setSelectedPos(pos)}
                      aria-pressed={isSelected}
                      className={`text-left p-3 rounded-lg border transition-shadow flex flex-col justify-between h-28 select-none focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 ${e.celda} ${
                        isSelected ? 'ring-2 ring-teal-500 ring-offset-1' : 'hover:shadow-sm'
                      }`}
                    >
                      <div className="flex items-center justify-between w-full text-xs">
                        <span className="text-slate-400">{libre ? ubicacionCorta(pos) : `P${pos.posicion}`}</span>
                        <span className={`inline-flex items-center gap-1 font-medium ${e.marca}`}>
                          <Icono className="w-3 h-3" />
                          {e.texto}
                        </span>
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-slate-900 line-clamp-1 leading-tight">{pos.producto}</div>
                        {pos.sku && <div className="text-[11px] text-slate-400">{pos.sku}</div>}
                      </div>
                      <div className="flex items-center justify-between text-xs text-slate-500 font-tabular">
                        {!libre && conPuntos(pos) ? (
                          <span className="inline-flex items-center gap-1.5" title={`${pos.frentes} de ${pos.frentes_esperados} frentes`}>
                            <PuntosFrentes hay={pos.frentes} esperados={pos.frentes_esperados} />
                            <span>
                              {pos.frentes}/{pos.frentes_esperados}
                              <span className="sr-only"> frentes</span>
                            </span>
                          </span>
                        ) : (
                          <span>
                            {libre ? (pos.tipo === 'hueco' ? 'sin producto' : 'etiqueta') : `${pos.frentes ?? '—'} frentes`}
                          </span>
                        )}
                        <span className="font-semibold text-slate-800">
                          {libre
                            ? pos.precio_etiqueta !== null ? fm(pos.precio_etiqueta) : '?'
                            : pos.precio_sistema ? fm(pos.precio_sistema) : '-'}
                        </span>
                      </div>
                    </motion.button>
                  );
                })}
              </div>
              {/* Repisa */}
              <div className="mt-2 h-1 rounded-full bg-slate-200" />
            </div>
          ))}
        </div>

        {/* Detalle de la posición */}
        <div className="lg:col-span-4">
          <AnimatePresence mode="wait">
            {selectedPos ? (
              <motion.div
                key={selectedPos.id}
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 12 }}
                transition={{ duration: 0.15 }}
                className="bg-white p-5 rounded-xl border border-slate-200 space-y-4 sticky top-16"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="inline-flex items-center gap-1 text-slate-500">
                      <ICONO_DATO.ubicacion className="w-3.5 h-3.5 text-slate-400" />
                      {ubicacionLarga(selectedPos)}
                    </span>
                    {(() => {
                      const e = estadoDe(selectedPos.estado);
                      const Icono = e.icono;
                      return (
                        <span className={`inline-flex items-center gap-1 font-medium ${e.marca}`}>
                          <Icono className="w-3.5 h-3.5" />
                          {traducirEstadoPosicion(selectedPos.estado)}
                        </span>
                      );
                    })()}
                  </div>
                  <h3 className="mt-1 text-base font-semibold text-slate-900 leading-tight">{selectedPos.producto}</h3>
                  {selectedPos.sku && (
                    <p className="mt-0.5 inline-flex items-center gap-1 text-xs text-slate-500">
                      <ICONO_DATO.sku className="w-3.5 h-3.5 text-slate-400" />
                      SKU: {selectedPos.sku}
                    </p>
                  )}
                </div>

                <div className="rounded-lg overflow-hidden bg-slate-900 aspect-video">
                  <img
                    src={selectedPos.evidencia || EVIDENCIA_VACIA}
                    alt={`Evidencia de ${selectedPos.producto}`}
                    className="w-full h-full object-cover"
                  />
                </div>

                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                  <div>
                    <dt className="flex items-center gap-1 text-xs text-slate-500">
                      <ICONO_DATO.etiqueta className="w-3.5 h-3.5 text-slate-400" />
                      Precio en etiqueta
                    </dt>
                    <dd className="font-semibold text-rose-600 font-tabular">
                      {selectedPos.precio_etiqueta !== null && selectedPos.precio_etiqueta > 0
                        ? fm(selectedPos.precio_etiqueta)
                        : 'Sin etiqueta'}
                    </dd>
                  </div>
                  <div>
                    <dt className="flex items-center gap-1 text-xs text-slate-500">
                      <ICONO_DATO.sistema className="w-3.5 h-3.5 text-slate-400" />
                      Precio en sistema
                    </dt>
                    <dd className="font-semibold text-slate-900 font-tabular">
                      {selectedPos.precio_sistema !== null ? fm(selectedPos.precio_sistema) : 'Sin datos'}
                    </dd>
                  </div>
                  <div>
                    <dt className="flex items-center gap-1 text-xs text-slate-500">
                      <ICONO_DATO.frentes className="w-3.5 h-3.5 text-slate-400" />
                      Frentes
                    </dt>
                    <dd className="font-semibold text-slate-900 font-tabular inline-flex items-center gap-2">
                      {selectedPos.frentes === null
                        ? libre ? 'Sin dato' : data.resumen.modo === 'orden' ? 'No se cuentan aquí' : 'No se vio completa'
                        : `${selectedPos.frentes}${selectedPos.frentes_esperados ? ` de ${selectedPos.frentes_esperados}` : ''}`}
                      {conPuntos(selectedPos) && (
                        <PuntosFrentes hay={selectedPos.frentes} esperados={selectedPos.frentes_esperados} />
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="flex items-center gap-1 text-xs text-slate-500">
                      <ICONO_DATO.existencia className="w-3.5 h-3.5 text-slate-400" />
                      Existencia en sistema
                    </dt>
                    <dd className="font-semibold text-slate-900 font-tabular">
                      {selectedPos.inventario_sistema === null ? 'Sin dato' : `${selectedPos.inventario_sistema} piezas`}
                    </dd>
                  </div>
                </dl>

                {selectedPos.tipo && (
                  <div className="pt-4 border-t border-slate-100 space-y-1.5">
                    <div className="flex items-center justify-between gap-3 text-sm">
                      <span className="inline-flex items-center gap-1.5 font-medium text-rose-700">
                        {(() => {
                          const Icono = iconoTipo(selectedPos.tipo);
                          return <Icono className="w-4 h-4 shrink-0" />;
                        })()}
                        {traducirTipoHallazgo(selectedPos.tipo)}
                      </span>
                      {selectedPos.impacto_diario !== undefined && (
                        <span className="font-semibold text-rose-600 font-tabular">{fm(selectedPos.impacto_diario)}/día</span>
                      )}
                    </div>
                    {selectedPos.accion && (
                      <p className="flex items-start gap-1.5 text-sm text-slate-600 leading-snug">
                        <ICONO_DATO.accion className="w-4 h-4 text-teal-600 shrink-0 mt-px" />
                        <span>
                          <span className="font-medium text-slate-900">Acción sugerida:</span> {selectedPos.accion}
                        </span>
                      </p>
                    )}
                  </div>
                )}
              </motion.div>
            ) : (
              <div className="bg-white p-8 rounded-xl border border-slate-200 text-center text-sm text-slate-500 space-y-2">
                <MousePointerClick className="w-6 h-6 text-slate-300 mx-auto" />
                <p>Selecciona una posición del anaquel para ver su detalle.</p>
              </div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
