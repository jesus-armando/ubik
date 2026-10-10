'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  UploadCloud,
  Upload,
  FileVideo,
  Film,
  Loader2,
  CheckCircle2,
  Check,
  AlertTriangle,
  RotateCcw,
  Trash2,
  Eye,
  ServerOff,
  MessageSquareText,
  ClipboardList,
  FolderClock,
  Grid3X3,
  QrCode,
  Smartphone,
  Hourglass,
  Info,
  Lightbulb,
  MonitorCheck,
  XCircle,
  CircleDollarSign,
  Timer,
  ScanSearch,
  type LucideIcon,
} from 'lucide-react';
import { AnalisisMeta, DetectorMotor, ListaAnalisis } from '@/types/analisis';
import {
  EXTENSIONES_VIDEO,
  MAX_BYTES_VIDEO,
  activarAnalisis,
  borrarAnalisis,
  consultarAnalisis,
  listarAnalisis,
  subirVideo,
} from '@/lib/api/analisis';
import { formatearMoneda } from '@/lib/formatters/contract';
import { ICONO_DATO, ICONO_PANTALLA } from '@/components/iconos';
import { TituloPagina } from '@/components/layout/TituloPagina';

const PASOS = [
  'Subiendo video',
  'Eligiendo cuadros',
  'Leyendo etiquetas',
  'Generando video anotado',
  'Comparando con el sistema',
];

const DETECTORES: { id: DetectorMotor; icono: LucideIcon; titulo: string; desc: string }[] = [
  {
    id: 'anaquel',
    icono: Grid3X3,
    titulo: 'Anaquel de la demo',
    desc: 'Detector entrenado con el anaquel del simulador (etiqueta, producto y hueco).',
  },
  {
    id: 'sku110k',
    icono: QrCode,
    titulo: 'Anaquel real con marcadores',
    desc: 'Detector general de productos (SKU-110K) para clips grabados en tienda.',
  },
  {
    id: 'libre',
    icono: Smartphone,
    titulo: 'Sin estructura',
    desc: 'Videos de IA o del celular, sin marcadores ni planograma: lee etiquetas y busca huecos.',
  },
];

// Qué necesita el video según el detector; el último renglón es un consejo, no un requisito
const REQUISITOS_PLANOGRAMA = [
  'Recorre las repisas en orden: en serpentina o repisa por repisa, sin saltarte posiciones ni regresar.',
  'Que se lea el SKU de cada etiqueta (SKU-100664): con él se confirma en qué posición va.',
  'Si el empaque trae el nombre impreso, también se detecta el producto en lugar equivocado.',
  'Los frentes no se cuentan en este modo.',
];
const REQUISITOS_LIBRE = [
  'No necesita marcadores, etiquetas especiales ni planograma: sirve para videos de IA o del celular.',
  'Cada etiqueta de precio que se lee se vuelve una posición; entre más cerca y de frente, mejor se leen los precios.',
  'Detecta huecos (sin producto encima de una etiqueta) y el mismo producto con dos precios distintos.',
  'Sin datos del sistema, los montos son una estimación con el precio leído en la etiqueta.',
];
const REQUISITOS_MARCADORES = [
  'Marcadores ArUco (DICT_4X4_100) de 5 cm visibles en cada repisa: con ellos ubica cada posición.',
  'Etiquetas con borde naranja, de frente y a unos 80 cm.',
  '4K de preferencia: a 1080p el SKU de la etiqueta casi no se lee.',
  'El anaquel debe ser el del planograma del sistema (12 posiciones de la demo).',
];

type Fase =
  | { tipo: 'inicio' }
  | { tipo: 'subiendo'; fraccion: number }
  | { tipo: 'procesando'; meta: AnalisisMeta }
  | { tipo: 'listo'; meta: AnalisisMeta }
  | { tipo: 'error'; mensaje: string };

function formatearBytes(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function formatearFecha(iso: string): string {
  const d = new Date(iso);
  return isNaN(d.getTime())
    ? iso
    : d.toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short', hour12: false });
}

function validar(archivo: File): string | null {
  const ext = archivo.name.slice(archivo.name.lastIndexOf('.')).toLowerCase();
  if (!EXTENSIONES_VIDEO.includes(ext)) {
    return `Formato no soportado. Usa ${EXTENSIONES_VIDEO.join(', ')}.`;
  }
  if (archivo.size > MAX_BYTES_VIDEO) return 'El video pesa más de 4 GB.';
  if (archivo.size === 0) return 'El archivo está vacío.';
  return null;
}

export function AnalizarView() {
  const router = useRouter();
  const [archivo, setArchivo] = useState<File | null>(null);
  const [detector, setDetector] = useState<DetectorMotor>('anaquel');
  const [identificar, setIdentificar] = useState(true);
  const [conPlanograma, setConPlanograma] = useState(false);
  const [arrastrando, setArrastrando] = useState(false);
  const [fase, setFase] = useState<Fase>({ tipo: 'inicio' });
  const [lista, setLista] = useState<ListaAnalisis | null>(null);
  const [apiCaida, setApiCaida] = useState(false);
  const [avisoLista, setAvisoLista] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const recargarLista = useCallback(async () => {
    try {
      const datos = await listarAnalisis();
      setLista(datos);
      setApiCaida(false);
      return datos;
    } catch {
      setApiCaida(true);
      return null;
    }
  }, []);

  const seguir = useCallback(
    (id: string) => {
      if (pollingRef.current) clearInterval(pollingRef.current);
      pollingRef.current = setInterval(async () => {
        try {
          const meta = await consultarAnalisis(id);
          if (meta.status === 'procesando') {
            setFase({ tipo: 'procesando', meta });
            return;
          }
          if (pollingRef.current) clearInterval(pollingRef.current);
          if (meta.status === 'completado') {
            setFase({ tipo: 'listo', meta });
            router.refresh(); // el encabezado y las pantallas leen el análisis activo
          } else {
            setFase({ tipo: 'error', mensaje: meta.mensaje || 'El motor no pudo procesar el video.' });
          }
          recargarLista();
        } catch {
          // error de red puntual: se reintenta en el siguiente ciclo
        }
      }, 1000);
    },
    [recargarLista, router]
  );

  // Al entrar: historial y, si hay un video en proceso (p. ej. se recargó la página), seguirlo
  useEffect(() => {
    recargarLista().then((datos) => {
      const enCurso = datos?.analisis.find((a) => a.status === 'procesando');
      if (enCurso) {
        setFase({ tipo: 'procesando', meta: enCurso });
        seguir(enCurso.id);
      }
    });
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [recargarLista, seguir]);

  const elegir = (f: File | undefined | null) => {
    if (!f) return;
    const error = validar(f);
    if (error) {
      setFase({ tipo: 'error', mensaje: error });
      return;
    }
    setArchivo(f);
    setFase({ tipo: 'inicio' });
  };

  const procesar = async () => {
    if (!archivo) return;
    setFase({ tipo: 'subiendo', fraccion: 0 });
    try {
      const meta = await subirVideo(archivo, { detector, identificar, planograma: conPlanograma }, (fraccion) =>
        setFase({ tipo: 'subiendo', fraccion })
      );
      setFase({ tipo: 'procesando', meta });
      seguir(meta.id);
      recargarLista();
    } catch (e) {
      setFase({ tipo: 'error', mensaje: (e as Error).message });
      recargarLista();
    }
  };

  const reiniciar = () => {
    setArchivo(null);
    setFase({ tipo: 'inicio' });
    if (inputRef.current) inputRef.current.value = '';
  };

  const mostrar = async (id: string | null) => {
    try {
      await activarAnalisis(id);
      setAvisoLista(id ? 'Ese análisis es el que se muestra ahora en el tablero.' : 'El tablero muestra el recorrido de demostración.');
      await recargarLista();
      router.refresh();
    } catch (e) {
      setAvisoLista((e as Error).message);
    }
  };

  const borrar = async (a: AnalisisMeta) => {
    if (!window.confirm(`¿Borrar el análisis de "${a.nombre}"? Se elimina el video y sus resultados.`)) return;
    try {
      await borrarAnalisis(a.id);
      setAvisoLista(null);
      await recargarLista();
      router.refresh();
    } catch (e) {
      setAvisoLista((e as Error).message);
    }
  };

  const ocupado = fase.tipo === 'subiendo' || fase.tipo === 'procesando';
  const pasoActual =
    fase.tipo === 'subiendo' ? 0 : fase.tipo === 'procesando' ? fase.meta.pasoNumero ?? 1 : PASOS.length;
  const progreso =
    fase.tipo === 'subiendo'
      ? Math.round(fase.fraccion * 100)
      : fase.tipo === 'procesando'
      ? fase.meta.progreso ?? 2
      : 100;

  return (
    <div className="space-y-6">
      {/* Encabezado */}
      <TituloPagina icono={ICONO_PANTALLA.analizar} titulo="Subir video">
        El motor lo procesa en esta laptop y el resultado aparece en todo el tablero.
      </TituloPagina>

      {apiCaida && (
        <div className="p-4 rounded-xl border border-amber-200 bg-amber-50 text-amber-900 text-sm flex items-start gap-3">
          <ServerOff className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <strong>La API del motor no responde.</strong> En <code className="font-mono">motor-procesamiento/</code>{' '}
            arráncala con <code className="font-mono text-[13px] bg-amber-100 px-1.5 py-0.5 rounded">python -m cruce.api</code>{' '}
            y recarga esta página. Mientras tanto el tablero muestra el recorrido de demostración.
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Columna principal: subir, avance o resultado */}
        <div className="lg:col-span-7 space-y-4">
          {(fase.tipo === 'inicio' || fase.tipo === 'error') && (
            <div className="bg-white p-6 rounded-xl border border-slate-200 space-y-5">
              {/* Zona para soltar el archivo */}
              <label
                onDragOver={(e) => {
                  e.preventDefault();
                  setArrastrando(true);
                }}
                onDragLeave={() => setArrastrando(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setArrastrando(false);
                  elegir(e.dataTransfer.files?.[0]);
                }}
                className={`flex flex-col items-center justify-center text-center gap-2 p-8 rounded-xl border-2 border-dashed cursor-pointer transition-colors focus-within:ring-2 focus-within:ring-teal-500 focus-within:ring-offset-2 ${
                  arrastrando
                    ? 'border-teal-500 bg-teal-50'
                    : archivo
                    ? 'border-teal-300 bg-teal-50/40'
                    : 'border-slate-300 hover:border-teal-400 hover:bg-slate-50'
                }`}
              >
                <input
                  ref={inputRef}
                  type="file"
                  accept={`video/*,${EXTENSIONES_VIDEO.join(',')}`}
                  className="sr-only"
                  onChange={(e) => elegir(e.target.files?.[0])}
                />
                {archivo ? (
                  <>
                    <FileVideo className="w-8 h-8 text-teal-600" />
                    <span className="text-sm font-semibold text-slate-900 break-all">{archivo.name}</span>
                    <span className="text-xs text-slate-500">{formatearBytes(archivo.size)} · toca para cambiarlo</span>
                  </>
                ) : (
                  <>
                    <UploadCloud className="w-8 h-8 text-slate-400" />
                    <span className="text-sm font-semibold text-slate-800">Arrastra aquí el video del dron o toca para elegirlo</span>
                    <span className="text-xs text-slate-500">MP4, MOV, M4V, AVI, MKV o WEBM · hasta 4 GB</span>
                  </>
                )}
              </label>

              {/* Opciones del motor */}
              <fieldset className="space-y-2">
                <legend className="text-sm font-semibold text-slate-900 mb-2 flex items-center gap-2">
                  <ScanSearch className="w-4 h-4 text-slate-400" />
                  Detector
                </legend>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {DETECTORES.map((d) => (
                    <label
                      key={d.id}
                      className={`relative p-3 rounded-lg border cursor-pointer transition-colors focus-within:ring-2 focus-within:ring-teal-500 ${
                        detector === d.id ? 'border-teal-500 bg-teal-50/50' : 'border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      <input
                        type="radio"
                        name="detector"
                        value={d.id}
                        checked={detector === d.id}
                        onChange={() => setDetector(d.id)}
                        className="sr-only"
                      />
                      <span className="flex items-center justify-between mb-2">
                        <span
                          className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                            detector === d.id ? 'bg-teal-600 text-white' : 'bg-slate-100 text-slate-500'
                          }`}
                        >
                          <d.icono className="w-4 h-4" />
                        </span>
                        {detector === d.id && <CheckCircle2 className="w-4 h-4 text-teal-600" />}
                      </span>
                      <span className="text-sm font-semibold text-slate-900 block">{d.titulo}</span>
                      <span className="text-xs text-slate-500 leading-snug block mt-0.5">{d.desc}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              {detector === 'libre' && (
                <label className="flex items-start gap-3 text-sm text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={conPlanograma}
                    onChange={(e) => setConPlanograma(e.target.checked)}
                    className="mt-0.5 w-4 h-4 accent-teal-600"
                  />
                  <span>
                    <span className="font-medium text-slate-900">Comparar con el planograma de la demo</span>: el
                    anaquel tiene los mismos productos en el mismo orden, pero sin marcadores (p. ej. armado a mano).
                    Cada etiqueta se ubica por el orden del recorrido y su SKU, y se cruza con el sistema de la demo
                    en pesos.
                  </span>
                </label>
              )}
              {detector !== 'libre' && (
                <label className="flex items-start gap-3 text-sm text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={identificar}
                    onChange={(e) => setIdentificar(e.target.checked)}
                    className="mt-0.5 w-4 h-4 accent-teal-600"
                  />
                  <span>
                    <span className="font-medium text-slate-900">Identificar qué producto hay</span> en cada
                    posición (detecta producto en lugar equivocado; tarda unos segundos más).
                  </span>
                </label>
              )}

              {fase.tipo === 'error' && (
                <div className="p-3 rounded-lg border border-rose-200 bg-rose-50 text-rose-800 text-sm flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
                  <span>{fase.mensaje}</span>
                </div>
              )}

              <button
                onClick={procesar}
                disabled={!archivo || apiCaida || !!lista?.ocupado}
                className="w-full inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-teal-600 hover:bg-teal-700 text-white font-semibold text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2"
              >
                {lista?.ocupado ? <Hourglass className="w-4 h-4" /> : <Upload className="w-4 h-4" />}
                {lista?.ocupado ? 'El motor está ocupado con otro video' : 'Subir y procesar'}
              </button>
            </div>
          )}

          {/* Avance: subida y pasos del motor */}
          {ocupado && (
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-white p-6 rounded-xl border border-slate-200 space-y-5"
            >
              <div className="flex items-center gap-3">
                <Loader2 className="w-5 h-5 text-teal-600 animate-spin shrink-0" />
                <div className="min-w-0">
                  <h3 className="text-base font-semibold text-slate-900">
                    {fase.tipo === 'subiendo' ? 'Subiendo video' : 'El motor está procesando el video'}
                  </h3>
                  <p className="text-xs text-slate-500 truncate">
                    {fase.tipo === 'procesando'
                      ? `${fase.meta.nombre}${
                          fase.meta.video
                            ? ` · ${fase.meta.video.segundos} s · ${fase.meta.video.ancho}×${fase.meta.video.alto}`
                            : ''
                        }${fase.meta.segundos !== undefined ? ` · ${Math.round(fase.meta.segundos)} s transcurridos` : ''}`
                      : archivo?.name}
                  </p>
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-teal-600 rounded-full"
                    animate={{ width: `${progreso}%` }}
                    transition={{ duration: 0.3 }}
                  />
                </div>
                <div className="text-right text-xs text-slate-500 font-tabular">{progreso} %</div>
              </div>

              <ol className="space-y-2">
                {PASOS.map((nombre, i) => {
                  const hecho = pasoActual > i;
                  const actual = pasoActual === i;
                  return (
                    <li
                      key={nombre}
                      className={`flex items-center gap-3 text-sm ${
                        hecho ? 'text-slate-700' : actual ? 'text-slate-900 font-medium' : 'text-slate-400'
                      }`}
                    >
                      {hecho ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      ) : actual ? (
                        <Loader2 className="w-4 h-4 animate-spin text-teal-600" />
                      ) : (
                        <span className="w-4 h-4 flex items-center justify-center">
                          <span className="w-2 h-2 rounded-full bg-slate-300" />
                        </span>
                      )}
                      <span>{nombre}</span>
                    </li>
                  );
                })}
              </ol>
            </motion.div>
          )}

          {/* Resultado */}
          {fase.tipo === 'listo' && (
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-white p-6 rounded-xl border border-slate-200 space-y-5"
            >
              <div className="flex items-center gap-2 text-emerald-700 text-sm font-medium">
                <CheckCircle2 className="w-4 h-4" />
                <span>Video procesado · ya se muestra en el tablero</span>
              </div>
              <h3 className="text-xl sm:text-2xl font-bold text-slate-900 leading-tight">
                {fase.meta.resumen?.frase}
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {(
                  [
                    [AlertTriangle, 'Problemas', String(fase.meta.resumen?.total_problemas ?? 0)],
                    [
                      CircleDollarSign,
                      fase.meta.detector === 'libre' ? 'En juego al día (estimado)' : 'En juego al día',
                      formatearMoneda(
                        fase.meta.resumen?.dinero_en_riesgo_diario,
                        fase.meta.detector === 'libre' ? '$' : 'US$'
                      ),
                    ],
                    [
                      fase.meta.detector === 'libre' ? ICONO_DATO.etiqueta : Grid3X3,
                      fase.meta.detector === 'libre' ? 'Etiquetas seguidas' : 'Posiciones vistas',
                      String(fase.meta.posiciones ?? '—'),
                    ],
                    [Timer, 'Tiempo del motor', `${fase.meta.resumen?.segundos_proceso ?? '—'} s`],
                  ] as [LucideIcon, string, string][]
                ).map(([Icono, etiqueta, valor]) => (
                  <div key={etiqueta}>
                    <div className="text-xs text-slate-500 flex items-center gap-1.5">
                      <Icono className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      {etiqueta}
                    </div>
                    <div className="text-lg font-semibold text-slate-900 font-tabular">{valor}</div>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <Link
                  href="/resumen"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-700 text-white font-semibold text-sm transition-colors"
                >
                  <ICONO_PANTALLA.resumen className="w-4 h-4" />
                  Ver resumen
                </Link>
                <Link
                  href="/recorrido"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-800 font-semibold text-sm transition-colors"
                >
                  <ICONO_PANTALLA.recorrido className="w-4 h-4 text-slate-500" />
                  Ver recorrido anotado
                </Link>
                <button
                  onClick={reiniciar}
                  className="inline-flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-100 text-slate-600 font-medium text-sm transition-colors"
                >
                  <RotateCcw className="w-4 h-4" />
                  Subir otro video
                </button>
              </div>
            </motion.div>
          )}
        </div>

        {/* Columna lateral: requisitos e historial */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-white p-5 rounded-xl border border-slate-200 space-y-3">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <ClipboardList className="w-4 h-4 text-slate-400" />
              Qué necesita el video
            </h3>
            <ul className="text-sm text-slate-600 space-y-2">
              {(detector !== 'libre'
                ? REQUISITOS_MARCADORES
                : conPlanograma
                ? REQUISITOS_PLANOGRAMA
                : REQUISITOS_LIBRE
              ).map((texto) => (
                <li key={texto} className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-teal-600 shrink-0 mt-0.5" />
                  <span>{texto}</span>
                </li>
              ))}
              {detector !== 'libre' && (
                <li className="flex items-start gap-2.5">
                  <Lightbulb className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <span>
                    ¿Video sin marcadores (p. ej. generado con IA)? Usa el detector{' '}
                    <span className="font-medium text-slate-900">Sin estructura</span>.
                  </span>
                </li>
              )}
            </ul>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 space-y-3">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <FolderClock className="w-4 h-4 text-slate-400" />
              Videos procesados
            </h3>
            {avisoLista && (
              <p className="text-xs text-teal-800 bg-teal-50 border border-teal-200 rounded-lg px-3 py-2 flex items-start gap-1.5">
                <Info className="w-3.5 h-3.5 text-teal-600 shrink-0 mt-px" />
                <span>{avisoLista}</span>
              </p>
            )}

            <div className="space-y-2 max-h-[28rem] overflow-y-auto pr-1">
              {/* Recorrido de demostración incluido en public/salida/ */}
              <div className="p-3 rounded-lg border border-slate-200 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-slate-900 flex items-center gap-1.5">
                    <Film className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    Recorrido de demostración
                  </div>
                  <div className="text-xs text-slate-500">Video simulado incluido en el tablero</div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <Link
                    href="/asistente?id=demo"
                    className="text-xs font-semibold text-teal-700 hover:text-teal-900 inline-flex items-center gap-1"
                  >
                    <MessageSquareText className="w-3.5 h-3.5" /> Preguntar
                  </Link>
                  {lista && lista.activo === null ? (
                    <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-teal-100 text-teal-800 inline-flex items-center gap-1">
                      <MonitorCheck className="w-3 h-3" /> En el tablero
                    </span>
                  ) : (
                    <button
                      onClick={() => mostrar(null)}
                      disabled={!lista}
                      className="text-xs font-semibold text-teal-700 hover:text-teal-900 inline-flex items-center gap-1 disabled:opacity-40"
                    >
                      <Eye className="w-3.5 h-3.5" /> Mostrar
                    </button>
                  )}
                </div>
              </div>

              {lista?.analisis.map((a) => (
                <div key={a.id} className="p-3 rounded-lg border border-slate-200 space-y-1">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-slate-900 flex items-center gap-1.5" title={a.nombre}>
                        <FileVideo className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        <span className="truncate">{a.nombre}</span>
                      </div>
                      <div className="text-xs text-slate-500">
                        {formatearFecha(a.creado)}
                        {a.detector === 'sku110k'
                          ? ' · anaquel real'
                          : a.detector === 'libre'
                          ? a.planograma
                            ? ' · sin marcadores, con planograma'
                            : ' · sin estructura'
                          : ''}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {a.status === 'procesando' && (
                        <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-sky-100 text-sky-800 inline-flex items-center gap-1">
                          <Loader2 className="w-3 h-3 animate-spin" /> Procesando
                        </span>
                      )}
                      {a.status === 'error' && (
                        <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 inline-flex items-center gap-1">
                          <XCircle className="w-3 h-3" /> Falló
                        </span>
                      )}
                      {a.status === 'completado' && (
                        <Link
                          href={`/asistente?id=${a.id}`}
                          className="text-xs font-semibold text-teal-700 hover:text-teal-900 inline-flex items-center gap-1"
                        >
                          <MessageSquareText className="w-3.5 h-3.5" /> Preguntar
                        </Link>
                      )}
                      {a.status === 'completado' &&
                        (a.activo ? (
                          <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-teal-100 text-teal-800 inline-flex items-center gap-1">
                            <MonitorCheck className="w-3 h-3" /> En el tablero
                          </span>
                        ) : (
                          <button
                            onClick={() => mostrar(a.id)}
                            className="text-xs font-semibold text-teal-700 hover:text-teal-900 inline-flex items-center gap-1"
                          >
                            <Eye className="w-3.5 h-3.5" /> Mostrar
                          </button>
                        ))}
                      {a.status !== 'procesando' && (
                        <button
                          onClick={() => borrar(a)}
                          className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50"
                          aria-label={`Borrar ${a.nombre}`}
                          title="Borrar"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                  {a.status === 'completado' && a.resumen && (
                    <p className="text-xs text-slate-600">{a.resumen.frase}</p>
                  )}
                  {a.status === 'error' && a.mensaje && <p className="text-xs text-rose-700">{a.mensaje}</p>}
                </div>
              ))}
              {lista && lista.analisis.length === 0 && (
                <p className="text-xs text-slate-500">Aún no se ha subido ningún video.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
