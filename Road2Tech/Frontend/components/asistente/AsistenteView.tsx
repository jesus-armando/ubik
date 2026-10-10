'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import {
  AlertTriangle,
  BookOpen,
  CircleDollarSign,
  Cpu,
  FileText,
  FileVideo,
  Info,
  KeyRound,
  Layers,
  ListOrdered,
  Loader2,
  RotateCcw,
  Search,
  Send,
  ServerOff,
  ShieldCheck,
  Sparkles,
  Timer,
  type LucideIcon,
} from 'lucide-react';
import { AnalisisMeta, EstadoAsistente, MensajeChat } from '@/types/analisis';
import { estadoAsistente, listarAnalisis, preguntarCorrida } from '@/lib/api/analisis';
import { ICONO_PANTALLA, iconoTipo } from '@/components/iconos';
import { TituloPagina } from '@/components/layout/TituloPagina';

const SUGERENCIAS: { icono: LucideIcon; texto: string }[] = [
  { icono: ListOrdered, texto: '¿Qué debo corregir primero y por qué?' },
  { icono: CircleDollarSign, texto: '¿Cuánto dinero está en juego y cómo se calculó?' },
  { icono: iconoTipo('revisar'), texto: '¿Qué lecturas son dudosas y por qué?' },
  { icono: Timer, texto: '¿Cuánto tardó el motor y qué etapa fue la más lenta?' },
];

const COMO_RESPONDE: { icono: LucideIcon; texto: string }[] = [
  {
    icono: Layers,
    texto: 'Parte la corrida en fragmentos: resumen, una ficha por posición o etiqueta, tiempos del motor y las reglas del cruce.',
  },
  {
    icono: Search,
    texto: 'Busca los fragmentos más parecidos a tu pregunta y solo con ellos responde Gemini; abajo de cada respuesta están las fuentes.',
  },
  { icono: ShieldCheck, texto: 'Si el dato no está en la corrida, lo dice en lugar de inventarlo.' },
];

interface Corrida {
  id: string; // id del análisis o "demo"
  nombre: string;
  detalle: string;
}

const DEMO: Corrida = {
  id: 'demo',
  nombre: 'Recorrido de demostración',
  detalle: 'Video simulado incluido en el tablero',
};

function formatearFecha(iso: string): string {
  const d = new Date(iso);
  return isNaN(d.getTime())
    ? iso
    : d.toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short', hour12: false });
}

function aCorrida(a: AnalisisMeta): Corrida {
  return {
    id: a.id,
    nombre: a.nombre,
    detalle: `${formatearFecha(a.creado)}${
      a.detector === 'libre' ? (a.planograma ? ' · sin marcadores, con planograma' : ' · sin estructura') : ''
    }${
      a.resumen ? ` · ${a.resumen.frase}` : ''
    }`,
  };
}

/** Fuente en una línea: el resumen va siempre, el resto es lo que encontró la búsqueda. */
function nombreFuente(f: { id: string; titulo: string }): string {
  return f.id === 'resumen' ? 'Resumen' : f.titulo.replace(/`/g, '');
}

export function AsistenteView({ idInicial }: { idInicial?: string }) {
  const [corridas, setCorridas] = useState<Corrida[]>([DEMO]);
  const [corridaId, setCorridaId] = useState('demo');
  const [estado, setEstado] = useState<EstadoAsistente | null>(null);
  const [apiCaida, setApiCaida] = useState(false);
  const [mensajes, setMensajes] = useState<MensajeChat[]>([]);
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listaRef = useRef<HTMLDivElement>(null);
  const entradaRef = useRef<HTMLTextAreaElement>(null);

  // Corridas terminadas y si hay clave de Gemini; sin ?id= se abre la que muestra el tablero
  useEffect(() => {
    Promise.all([listarAnalisis(), estadoAsistente()])
      .then(([lista, est]) => {
        const terminadas = lista.analisis.filter((a) => a.status === 'completado').map(aCorrida);
        setCorridas([DEMO, ...terminadas]);
        setEstado(est);
        const pedida = idInicial === 'demo' || terminadas.some((c) => c.id === idInicial);
        setCorridaId(pedida && idInicial ? idInicial : lista.activo ?? 'demo');
      })
      .catch(() => setApiCaida(true));
  }, [idInicial]);

  useEffect(() => {
    listaRef.current?.scrollTo({ top: listaRef.current.scrollHeight, behavior: 'smooth' });
  }, [mensajes, enviando]);

  const cambiarCorrida = (id: string) => {
    setCorridaId(id);
    setMensajes([]);
    setError(null);
  };

  const enviar = async (pregunta: string) => {
    const q = pregunta.trim();
    if (!q || enviando) return;
    const historial = mensajes;
    setMensajes([...historial, { rol: 'usuario', texto: q }]);
    setTexto('');
    setError(null);
    setEnviando(true);
    try {
      const r = await preguntarCorrida(corridaId, q, historial);
      setMensajes([
        ...historial,
        { rol: 'usuario', texto: q },
        { rol: 'asistente', texto: r.respuesta, fuentes: r.fuentes, modelo: r.modelo },
      ]);
    } catch (e) {
      // la pregunta regresa a la caja para reintentarla
      setMensajes(historial);
      setTexto(q);
      setError((e as Error).message);
    } finally {
      setEnviando(false);
      entradaRef.current?.focus();
    }
  };

  const sinClave = estado !== null && !estado.configurado;
  const bloqueado = apiCaida || sinClave;
  const corrida = corridas.find((c) => c.id === corridaId) ?? DEMO;

  return (
    <div className="space-y-6">
      <TituloPagina icono={ICONO_PANTALLA.asistente} titulo="Asistente">
        Pregúntale a una corrida del motor. Gemini responde solo con los datos de esa corrida.
      </TituloPagina>

      {apiCaida && (
        <div className="p-4 rounded-xl border border-amber-200 bg-amber-50 text-amber-900 text-sm flex items-start gap-3">
          <ServerOff className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <strong>La API del motor no responde.</strong> En <code className="font-mono">motor-procesamiento/</code>{' '}
            arráncala con <code className="font-mono text-[13px] bg-amber-100 px-1.5 py-0.5 rounded">python -m cruce.api</code>{' '}
            y recarga esta página.
          </div>
        </div>
      )}

      {sinClave && (
        <div className="p-4 rounded-xl border border-amber-200 bg-amber-50 text-amber-900 text-sm flex items-start gap-3">
          <KeyRound className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <strong>Falta la clave de Gemini.</strong> Ponla en el <code className="font-mono">.env</code> de la raíz del
            repositorio como <code className="font-mono text-[13px] bg-amber-100 px-1.5 py-0.5 rounded">APIGEMINI=tu-clave</code>{' '}
            y recarga esta página; no hace falta reiniciar la API.
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Conversación */}
        <div className="lg:col-span-8 bg-white rounded-xl border border-slate-200 flex flex-col h-[calc(100vh-13rem)] min-h-[26rem]">
          <div ref={listaRef} className="flex-1 overflow-y-auto p-5 space-y-5" aria-live="polite">
            {mensajes.length === 0 && !enviando && (
              <div className="h-full flex flex-col items-center justify-center text-center gap-4 px-4">
                <span className="w-11 h-11 rounded-full bg-teal-50 text-teal-600 ring-1 ring-inset ring-teal-100 flex items-center justify-center">
                  <Sparkles className="w-5 h-5" />
                </span>
                <div>
                  <p className="text-base font-semibold text-slate-900">¿Qué quieres saber de esta corrida?</p>
                  <p className="text-sm text-slate-500 mt-1">
                    Hallazgos, dinero en juego, lecturas de cada etiqueta, inventario o tiempos del motor.
                  </p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-xl">
                  {SUGERENCIAS.map(({ icono: Icono, texto: s }) => (
                    <button
                      key={s}
                      onClick={() => enviar(s)}
                      disabled={bloqueado}
                      className="group text-left text-sm px-3 py-2 rounded-lg border border-slate-200 text-slate-700 hover:border-teal-400 hover:bg-teal-50/40 transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 flex items-start gap-2"
                    >
                      <Icono className="w-4 h-4 text-slate-400 group-hover:text-teal-600 shrink-0 mt-0.5 transition-colors" />
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {mensajes.map((m, i) =>
              m.rol === 'usuario' ? (
                <div key={i} className="flex justify-end">
                  <p className="max-w-[85%] bg-slate-100 text-slate-900 text-sm rounded-xl px-4 py-2.5 whitespace-pre-wrap">
                    {m.texto}
                  </p>
                </div>
              ) : (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                  className="max-w-[92%] flex items-start gap-3"
                >
                  <span className="w-7 h-7 rounded-full bg-teal-50 text-teal-600 ring-1 ring-inset ring-teal-100 flex items-center justify-center shrink-0">
                    <Sparkles className="w-3.5 h-3.5" />
                  </span>
                  <div className="min-w-0 space-y-1.5 pt-0.5">
                    <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">{m.texto}</p>
                    {m.fuentes && m.fuentes.length > 0 && (
                      <p className="text-xs text-slate-500 flex items-start gap-1.5">
                        <FileText className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-px" />
                        <span>Fuentes: {m.fuentes.map(nombreFuente).join(' · ')}</span>
                      </p>
                    )}
                  </div>
                </motion.div>
              )
            )}

            {enviando && (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Loader2 className="w-4 h-4 animate-spin text-teal-600" />
                Buscando en la corrida y preguntando a Gemini…
              </div>
            )}
          </div>

          {error && (
            <div className="mx-4 mb-3 p-3 rounded-lg border border-rose-200 bg-rose-50 text-rose-800 text-sm flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
              <span>{error}</span>
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              enviar(texto);
            }}
            className="border-t border-slate-200 p-3 flex items-end gap-2"
          >
            <label htmlFor="pregunta" className="sr-only">
              Pregunta
            </label>
            <textarea
              id="pregunta"
              ref={entradaRef}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={(e) => {
                // Enter envía; Shift+Enter hace un salto de línea
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  enviar(texto);
                }
              }}
              rows={2}
              maxLength={2000}
              disabled={bloqueado}
              placeholder="Escribe tu pregunta… (Enter envía, Shift+Enter salto de línea)"
              className="flex-1 resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent disabled:bg-slate-50"
            />
            <button
              type="submit"
              disabled={bloqueado || enviando || !texto.trim()}
              aria-label="Enviar pregunta"
              className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-teal-600 hover:bg-teal-700 text-white font-semibold text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2"
            >
              <Send className="w-4 h-4" />
              Enviar
            </button>
          </form>
        </div>

        {/* Corrida y cómo responde */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-white p-5 rounded-xl border border-slate-200 space-y-3">
            <label htmlFor="corrida" className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <FileVideo className="w-4 h-4 text-slate-400" />
              Corrida
            </label>
            <select
              id="corrida"
              value={corridaId}
              onChange={(e) => cambiarCorrida(e.target.value)}
              disabled={enviando}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-teal-500 disabled:opacity-60"
            >
              {corridas.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 leading-snug flex items-start gap-1.5">
              <Info className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-px" />
              <span>{corrida.detalle}</span>
            </p>
            {mensajes.length > 0 && (
              <button
                onClick={() => cambiarCorrida(corridaId)}
                disabled={enviando}
                className="text-xs font-semibold text-teal-700 hover:text-teal-900 inline-flex items-center gap-1 disabled:opacity-40"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Empezar otra conversación
              </button>
            )}
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 space-y-3">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-slate-400" />
              Cómo responde
            </h3>
            <ul className="text-sm text-slate-600 space-y-2">
              {COMO_RESPONDE.map(({ icono: Icono, texto }) => (
                <li key={texto} className="flex items-start gap-2.5">
                  <Icono className="w-4 h-4 text-teal-600 shrink-0 mt-0.5" />
                  <span>{texto}</span>
                </li>
              ))}
            </ul>
            {estado && (
              <p className="text-xs text-slate-500 flex items-start gap-1.5 pt-1">
                <Cpu className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-px" />
                <span>
                  Modelo: {estado.modelos[0]}
                  {estado.modelos.length > 1 ? ` (respaldo: ${estado.modelos.slice(1).join(', ')})` : ''}
                </span>
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
