'use client';

import React from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  CalendarDays,
  ChartPie,
  CircleDollarSign,
  Ellipsis,
  FileVideo,
  HeartPulse,
  ListOrdered,
  Tags,
  Timer,
} from 'lucide-react';
import { SalidaHallazgos } from '@/types/hallazgos';
import {
  formatearMoneda,
  totalesPorFamilia,
  traducirTipoHallazgo,
  ubicacionCorta,
} from '@/lib/formatters/contract';
import { Barra, BarraApilada, Proporcion } from '@/components/graficas/Barras';
import { ICONO_ESTADO, ICONO_PANTALLA, iconoFamilia, iconoTipo } from '@/components/iconos';

interface ResumenViewProps {
  data: SalidaHallazgos;
}

const ESTADO = {
  ok: { icono: ICONO_ESTADO.ok, celda: 'bg-emerald-50 border-emerald-200 text-emerald-800', punto: 'bg-emerald-500', marca: 'text-emerald-600', texto: 'Correcto' },
  error: { icono: ICONO_ESTADO.error, celda: 'bg-rose-50 border-rose-200 text-rose-800', punto: 'bg-rose-500', marca: 'text-rose-600', texto: 'Error' },
  revisar: { icono: ICONO_ESTADO.revisar, celda: 'bg-amber-50 border-amber-200 text-amber-800', punto: 'bg-amber-500', marca: 'text-amber-600', texto: 'Revisar' },
} as const;

// Ranking de hallazgos: los que juntan este tanto del dinero van resaltados y el resto en gris
const PARTE_PRIORITARIA = 0.7;
// Más filas que esto y la cola se junta en "Otros" (la lista completa está en Hallazgos)
const MAX_FILAS = 6;

const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`;
const pct = (parte: number, total: number) => (total > 0 ? Math.round((parte / total) * 100) : 0);

export function ResumenView({ data }: ResumenViewProps) {
  const { resumen, posiciones, hallazgos } = data;
  const moneda = resumen.moneda ?? 'US$';
  const fm = (monto: number | null | undefined) => formatearMoneda(monto, moneda);
  const libre = resumen.modo === 'libre';
  // Sin planograma no hay repisas: las etiquetas encontradas se acomodan de 4 en 4
  const filas = libre
    ? Array.from({ length: Math.ceil(posiciones.length / 4) }, (_, i) => ({
        titulo: `Etiquetas ${i * 4 + 1}–${Math.min(i * 4 + 4, posiciones.length)}`,
        items: posiciones.slice(i * 4, i * 4 + 4),
      }))
    : [1, 2, 3].map((r) => ({ titulo: `Repisa ${r}`, items: posiciones.filter((p) => p.repisa === r) }));
  const cuenta = (estado: string) => posiciones.filter((p) => p.estado === estado).length;

  // Dinero: de dónde sale (familias) y qué corregir primero (ranking con su parte acumulada)
  const familias = totalesPorFamilia(hallazgos);
  const ordenados = [...hallazgos].sort((a, b) => b.impacto_diario - a.impacto_diario);
  const totalDinero = ordenados.reduce((s, h) => s + (h.impacto_diario || 0), 0);
  let acumulado = 0;
  let prioritarios = 0;
  while (prioritarios < ordenados.length && acumulado < totalDinero * PARTE_PRIORITARIA) {
    acumulado += ordenados[prioritarios].impacto_diario || 0;
    prioritarios += 1;
  }
  const cola = ordenados.length > MAX_FILAS ? ordenados.slice(MAX_FILAS - 1) : [];
  const ranking = cola.length ? ordenados.slice(0, MAX_FILAS - 1) : ordenados;
  const montoCola = cola.reduce((s, h) => s + (h.impacto_diario || 0), 0);
  const mayor = Math.max(ordenados[0]?.impacto_diario || 0, montoCola);
  const conPrioridad = totalDinero > 0 && prioritarios < ordenados.length;

  const indicadores = [
    {
      titulo: 'Exposición diaria',
      icono: CircleDollarSign,
      valor: fm(resumen.dinero_en_riesgo_diario),
      iconoDetalle: CalendarDays,
      detalle: 'Proyección a 30 días',
      dato: fm(resumen.dinero_en_riesgo_diario * 30),
    },
    {
      titulo: 'Errores en etiquetas',
      icono: Tags,
      valor: (
        <>
          {resumen.etiquetas_con_error}
          <span className="text-base font-normal text-slate-400"> / {posiciones.length}</span>
        </>
      ),
      grafica: (
        <Proporcion
          pct={posiciones.length ? (resumen.etiquetas_con_error / posiciones.length) * 100 : 0}
          tono="bg-rose-500"
        />
      ),
      iconoDetalle: iconoFamilia('huecos'),
      detalle: 'Huecos en anaquel',
      dato: resumen.huecos_inventario,
    },
    {
      titulo: 'Salud del anaquel',
      icono: HeartPulse,
      valor: `${resumen.precision_anaquel_pct}%`,
      // Las posiciones por estado, en el orden de la leyenda del anaquel
      grafica: (
        <>
          <BarraApilada
            partes={(['ok', 'error', 'revisar'] as const).map((e) => ({
              clave: e,
              valor: cuenta(e),
              tono: ESTADO[e].punto,
            }))}
          />
          <div className="mt-1.5 text-xs text-slate-500 font-tabular">
            {libre
              ? plural(cuenta('ok'), 'etiqueta correcta', 'etiquetas correctas')
              : plural(cuenta('ok'), 'posición correcta', 'posiciones correctas')}{' '}
            de {posiciones.length}
          </div>
        </>
      ),
      iconoDetalle: iconoTipo('revisar'),
      detalle: 'Lecturas a verificar',
      dato: resumen.lecturas_dudosas,
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="space-y-6"
    >
      {/* Frase principal y de dónde sale el dinero */}
      <section className="bg-white rounded-xl p-6 border border-slate-200 grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className={familias.length ? 'lg:col-span-6 2xl:col-span-7' : 'lg:col-span-12'}>
          <h2 className="text-2xl xl:text-3xl font-bold text-slate-900 tracking-tight leading-tight">
            <span className="text-rose-600">
              {resumen.total_problemas} {resumen.total_problemas === 1 ? 'problema' : 'problemas'}
            </span>{' '}
            en este anaquel
            <span className="block">
              <span className="text-teal-700">{fm(resumen.dinero_en_riesgo_diario)}</span> al día en juego
              {libre ? ' (estimado)' : ''}
            </span>
          </h2>
          <p className="mt-2 text-sm text-slate-500 max-w-3xl">
            {libre
              ? 'Video sin estructura: el motor siguió cada etiqueta de precio, buscó huecos encima de ellas y comparó precios del mismo producto. Sin datos del sistema, los montos son estimados.'
              : 'Precios desactualizados, etiquetas faltantes y huecos con inventario en sistema, detectados en el video del recorrido.'}
          </p>
          {resumen.video && (
            <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
              <span className="inline-flex items-center gap-1.5 min-w-0">
                <FileVideo className="w-3.5 h-3.5 shrink-0" />
                {resumen.analisis_id ? 'Video subido' : 'Video'}: {resumen.video}
              </span>
              {resumen.segundos_proceso ? (
                <span className="inline-flex items-center gap-1.5">
                  <Timer className="w-3.5 h-3.5" />
                  Procesado en {resumen.segundos_proceso} s
                </span>
              ) : null}
            </p>
          )}
          <Link
            href="/recorrido"
            className="mt-5 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-700 text-white font-semibold text-sm transition-colors"
          >
            <ICONO_PANTALLA.recorrido className="w-4 h-4" />
            Ver recorrido
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        {familias.length > 0 && (
          <div className="lg:col-span-6 2xl:col-span-5 pt-5 border-t lg:pt-0 lg:border-t-0 lg:border-l border-slate-200 lg:pl-6">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <ChartPie className="w-4 h-4 text-slate-400" />
              De dónde sale el dinero
            </h3>
            <p className="text-xs text-slate-500 pl-6">Al día, por tipo de problema</p>
            <ul className="mt-4 space-y-3.5">
              {familias.map((f) => {
                const Icono = iconoFamilia(f.id);
                return (
                  <li key={f.id}>
                    <div className="flex items-baseline justify-between gap-3 text-sm">
                      <span className="text-slate-700 min-w-0 truncate">
                        <Icono className="w-4 h-4 text-slate-400 inline-block align-[-3px] mr-2" />
                        {f.nombre}
                        <span className="text-xs text-slate-400"> · {plural(f.cantidad, 'problema', 'problemas')}</span>
                      </span>
                      {f.monto > 0 ? (
                        <span className="shrink-0 font-tabular">
                          <span className="font-semibold text-slate-900">{fm(f.monto)}</span>
                          <span className="text-xs text-slate-400 inline-block w-10 text-right">
                            {pct(f.monto, totalDinero)} %
                          </span>
                        </span>
                      ) : (
                        <span className="shrink-0 text-xs text-slate-400">sin estimar</span>
                      )}
                    </div>
                    <Proporcion pct={totalDinero > 0 ? (f.monto / totalDinero) * 100 : 0} className="mt-1.5 ml-6" />
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </section>

      {/* Indicadores */}
      <section className="grid grid-cols-1 md:grid-cols-3 bg-white rounded-xl border border-slate-200 divide-y md:divide-y-0 md:divide-x divide-slate-200">
        {indicadores.map((k) => (
          <div key={k.titulo} className="p-6 flex flex-col">
            <div className="flex items-center gap-2.5 text-sm text-slate-500">
              <span className="w-8 h-8 rounded-lg bg-slate-100 text-slate-600 flex items-center justify-center shrink-0">
                <k.icono className="w-4 h-4" />
              </span>
              {k.titulo}
            </div>
            <div className="mt-2 text-3xl font-bold text-slate-900">{k.valor}</div>
            {k.grafica && <div className="mt-3">{k.grafica}</div>}
            <div className="mt-auto pt-4 flex items-center justify-between text-xs text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <k.iconoDetalle className="w-3.5 h-3.5 text-slate-400" />
                {k.detalle}
              </span>
              <span className="font-tabular font-semibold text-slate-700">{k.dato}</span>
            </div>
          </div>
        ))}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Miniatura del anaquel */}
        <section className="bg-white p-6 rounded-xl border border-slate-200">
          <div className="flex items-baseline justify-between mb-4">
            <h3 className="font-semibold text-slate-900 flex items-center gap-2">
              <ICONO_PANTALLA.anaquel className="w-4 h-4 text-slate-400" />
              Estado del anaquel
            </h3>
            <Link href="/anaquel" className="text-xs font-semibold text-teal-700 hover:text-teal-800 inline-flex items-center gap-1 shrink-0">
              Ver detalle <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="space-y-3">
            {filas.map(({ titulo, items }) => (
              <div key={titulo}>
                <div className="text-xs text-slate-400 mb-1">{titulo}</div>
                <div className="grid grid-cols-4 gap-2">
                  {items.map((pos) => {
                    const e = ESTADO[pos.estado as keyof typeof ESTADO] ?? ESTADO.revisar;
                    return (
                      <div
                        key={pos.id}
                        title={e.texto}
                        className={`px-2 py-1.5 rounded-md border text-center ${e.celda}`}
                      >
                        <div className="flex items-center justify-center gap-1 text-[10px]">
                          <e.icono className={`w-3 h-3 ${e.marca}`} />
                          <span className="opacity-70">{libre ? ubicacionCorta(pos) : `P${pos.posicion}`}</span>
                        </div>
                        <div className="text-xs font-semibold font-tabular truncate">
                          {pos.sku || (pos.precio_etiqueta !== null ? fm(pos.precio_etiqueta) : '?')}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 flex items-center gap-5 text-xs text-slate-500">
            {(['ok', 'error', 'revisar'] as const).map((k) => {
              const Icono = ESTADO[k].icono;
              return (
                <span key={k} className="inline-flex items-center gap-1.5">
                  <Icono className={`w-3.5 h-3.5 ${ESTADO[k].marca}`} />
                  {ESTADO[k].texto} ({cuenta(k)})
                </span>
              );
            })}
          </div>
        </section>

        {/* Qué corregir primero: ranking por dinero al día */}
        <section className="bg-white p-6 rounded-xl border border-slate-200">
          <div className="flex items-baseline justify-between gap-4">
            <h3 className="font-semibold text-slate-900 flex items-center gap-2">
              <ListOrdered className="w-4 h-4 text-slate-400" />
              Qué corregir primero
            </h3>
            <Link
              href="/hallazgos"
              className="text-xs font-semibold text-teal-700 hover:text-teal-800 inline-flex items-center gap-1 shrink-0"
            >
              Ver todos ({resumen.total_problemas}) <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          <p className="text-xs text-slate-500 mt-0.5 pl-6">
            {conPrioridad
              ? `${prioritarios === 1 ? 'El primero suma' : `Los ${prioritarios} primeros suman`} ${fm(acumulado)} al día: el ${pct(acumulado, totalDinero)} % del total.`
              : 'De mayor a menor dinero en juego al día.'}
          </p>

          {ordenados.length === 0 ? (
            <p className="mt-6 text-sm text-slate-500">Sin hallazgos en este recorrido.</p>
          ) : (
            <ul className="mt-3">
              {ranking.map((h, i) => {
                const Icono = iconoTipo(h.tipo);
                return (
                  <li key={h.id}>
                    <Link
                      href={`/hallazgos#${h.id}`}
                      title={h.descripcion}
                      className="grid grid-cols-[1.75rem_minmax(0,12rem)_minmax(0,1fr)_5.5rem] items-center gap-x-3 -mx-2 px-2 py-1.5 rounded-lg hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
                    >
                      <span className="w-7 h-7 rounded-md bg-slate-100 text-slate-500 flex items-center justify-center">
                        <Icono className="w-3.5 h-3.5" />
                      </span>
                      <span className="min-w-0">
                        <span className="block text-sm font-medium text-slate-900 truncate">{h.producto}</span>
                        <span className="block text-xs text-slate-500 truncate">
                          {ubicacionCorta(h)} · {traducirTipoHallazgo(h.tipo)}
                        </span>
                      </span>
                      <Barra
                        pct={mayor > 0 ? (h.impacto_diario / mayor) * 100 : 0}
                        tono={!conPrioridad || i < prioritarios ? 'bg-teal-600' : 'bg-slate-300'}
                      />
                      <span className="text-right text-sm font-semibold text-slate-900 font-tabular">
                        {h.impacto_diario > 0 ? fm(h.impacto_diario) : <span className="text-xs font-normal text-slate-400">sin estimar</span>}
                      </span>
                    </Link>
                  </li>
                );
              })}
              {cola.length > 0 && (
                <li>
                  <Link
                    href="/hallazgos"
                    className="grid grid-cols-[1.75rem_minmax(0,12rem)_minmax(0,1fr)_5.5rem] items-center gap-x-3 -mx-2 px-2 py-1.5 rounded-lg hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
                  >
                    <span className="w-7 h-7 rounded-md bg-slate-100 text-slate-400 flex items-center justify-center">
                      <Ellipsis className="w-3.5 h-3.5" />
                    </span>
                    <span className="text-sm text-slate-600">Otros {cola.length} hallazgos</span>
                    <Barra pct={mayor > 0 ? (montoCola / mayor) * 100 : 0} tono="bg-slate-300" />
                    <span className="text-right text-sm font-semibold text-slate-900 font-tabular">{fm(montoCola)}</span>
                  </Link>
                </li>
              )}
            </ul>
          )}
        </section>
      </div>
    </motion.div>
  );
}
