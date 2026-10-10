'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Clock, ListVideo, Pause, Play, RotateCcw, SkipBack, SkipForward, TrendingDown } from 'lucide-react';
import { SalidaHallazgos, Hallazgo } from '@/types/hallazgos';
import {
  EVIDENCIA_VACIA,
  formatearMoneda,
  formatearPrecioEtiqueta,
  ubicacionCorta,
  ubicacionLarga,
  traducirTipoHallazgo,
  cuadroASegundos,
  formatearTiempoVideo,
} from '@/lib/formatters/contract';
import { ICONO_DATO, ICONO_PANTALLA, iconoTipo } from '@/components/iconos';
import { TituloPagina } from '@/components/layout/TituloPagina';

interface RecorridoViewProps {
  data: SalidaHallazgos;
}

export function RecorridoView({ data }: RecorridoViewProps) {
  // En orden de aparición en el video
  const hallazgos = [...data.hallazgos].sort(
    (a, b) => (a.segundo || cuadroASegundos(a.cuadro)) - (b.segundo || cuadroASegundos(b.cuadro))
  );
  const fps = data.resumen.fps || 30;
  const moneda = data.resumen.moneda ?? 'US$';
  const fm = (monto: number | null | undefined) => formatearMoneda(monto, moneda);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(30);

  // Si los metadatos del video cargaron antes de la hidratación, onLoadedMetadata no se dispara
  useEffect(() => {
    const v = videoRef.current;
    if (v && v.readyState >= 1 && v.duration) {
      setDuration(v.duration);
    }
  }, []);
  const [selectedHallazgo, setSelectedHallazgo] = useState<Hallazgo>(hallazgos[0] || null);
  const IconoSeleccionado = iconoTipo(selectedHallazgo?.tipo);

  // Alternar reproducción
  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  // Actualización de tiempo
  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  // Salto a un hallazgo específico
  const jumpToHallazgo = (h: Hallazgo) => {
    const targetSecond = h.segundo || cuadroASegundos(h.cuadro);
    if (videoRef.current) {
      videoRef.current.currentTime = Math.min(targetSecond, duration);
      if (!isPlaying) {
        videoRef.current.play().catch(() => {});
        setIsPlaying(true);
      }
    }
    setSelectedHallazgo(h);
  };

  // Navegación anterior / siguiente
  const currentIndex = hallazgos.findIndex((h) => h.id === selectedHallazgo?.id);
  const handlePrev = () => {
    if (currentIndex > 0) {
      jumpToHallazgo(hallazgos[currentIndex - 1]);
    }
  };
  const handleNext = () => {
    if (currentIndex < hallazgos.length - 1) {
      jumpToHallazgo(hallazgos[currentIndex + 1]);
    }
  };

  return (
    <div className="space-y-6">
      {/* Encabezado */}
      <TituloPagina icono={ICONO_PANTALLA.recorrido} titulo="Recorrido anotado">
        Toca un hallazgo para saltar al momento del video en que aparece.
      </TituloPagina>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Columna Principal: Reproductor y Línea de Tiempo */}
        <div className="lg:col-span-8 space-y-4">
          {/* Contenedor del Video */}
          <div className="bg-slate-950 rounded-xl overflow-hidden relative aspect-video flex items-center justify-center">
            <video
              ref={videoRef}
              key={data.resumen.video_url || 'demo'}
              src={data.resumen.video_url || '/salida/recorrido_anotado.mp4'}
              className="w-full h-full object-contain"
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={() => {
                if (videoRef.current) {
                  setDuration(videoRef.current.duration || 30);
                }
              }}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
            >
              Tu navegador no soporta el elemento de video.
            </video>

            {/* Badge de hallazgo activo sobre el video; se oculta durante la reproducción */}
            {selectedHallazgo && !isPlaying && (
              <div className="absolute bottom-4 left-4 right-4 bg-slate-900/90 backdrop-blur-md p-3 rounded-lg text-white flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="min-w-7 h-7 px-1.5 rounded-lg bg-rose-600 text-white flex items-center justify-center font-bold text-xs whitespace-nowrap">
                    {ubicacionCorta(selectedHallazgo)}
                  </span>
                  <div>
                    <div className="text-xs font-bold text-slate-100 flex items-center gap-2">
                      {selectedHallazgo.producto}
                      <span className="text-rose-400 text-[11px] font-semibold inline-flex items-center gap-1">
                        <IconoSeleccionado className="w-3 h-3" />
                        {traducirTipoHallazgo(selectedHallazgo.tipo)}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-300 line-clamp-1 mt-0.5">
                      {selectedHallazgo.descripcion}
                    </div>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <span className="text-xs font-bold text-rose-400 font-tabular">
                    {fm(selectedHallazgo.impacto_diario)}/día
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Controles y Línea de Tiempo Interactiva */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
            {/* Barra de progreso con marcadores temporales de hallazgos */}
            <div className="relative w-full h-8 flex items-center select-none">
              {/* Pista de tiempo base */}
              <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden relative cursor-pointer"
                   onClick={(e) => {
                     const rect = e.currentTarget.getBoundingClientRect();
                     const clickX = e.clientX - rect.left;
                     const newTime = (clickX / rect.width) * duration;
                     if (videoRef.current) {
                       videoRef.current.currentTime = newTime;
                     }
                   }}
              >
                <div
                  className="h-full bg-teal-600 rounded-full transition-all duration-75"
                  style={{ width: `${(currentTime / duration) * 100}%` }}
                />
              </div>

              {/* Marcadores de hallazgos en la línea de tiempo */}
              {hallazgos.map((h) => {
                const markerTime = h.segundo || cuadroASegundos(h.cuadro);
                const percent = Math.min((markerTime / duration) * 100, 100);
                const isSelected = selectedHallazgo?.id === h.id;

                return (
                  <button
                    key={h.id}
                    onClick={() => jumpToHallazgo(h)}
                    title={`Saltar a ${h.producto} (${markerTime}s)`}
                    className={`absolute -translate-x-1/2 top-1.5 w-4 h-4 rounded-full border-2 transition-transform hover:scale-125 focus:outline-hidden ${
                      isSelected
                        ? 'bg-rose-500 border-white ring-2 ring-rose-500 z-20 scale-110'
                        : 'bg-amber-400 border-white z-10'
                    }`}
                    style={{ left: `${percent}%` }}
                  />
                );
              })}
            </div>

            {/* Controles de reproducción */}
            <div className="flex items-center justify-between pt-1">
              <div className="flex items-center gap-2">
                <button
                  onClick={togglePlay}
                  className="p-2.5 rounded-lg bg-teal-600 hover:bg-teal-700 text-white transition-colors"
                  aria-label={isPlaying ? 'Pausar' : 'Reproducir'}
                >
                  {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-white" />}
                </button>
                <button
                  onClick={() => {
                    if (videoRef.current) videoRef.current.currentTime = 0;
                  }}
                  className="p-2.5 rounded-lg hover:bg-slate-100 text-slate-600 transition-colors"
                  title="Reiniciar"
                  aria-label="Reiniciar"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
                <span className="text-xs font-tabular text-slate-600 ml-2 inline-flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  {formatearTiempoVideo(currentTime)} / {formatearTiempoVideo(duration)}
                  <span className="text-slate-400"> · cuadro {Math.floor(currentTime * fps)}</span>
                </span>
              </div>

              {/* Navegación entre hallazgos */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500 mr-1 hidden sm:inline">
                  Hallazgo {currentIndex + 1} de {hallazgos.length}
                </span>
                <button
                  onClick={handlePrev}
                  disabled={currentIndex <= 0}
                  className="p-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  title="Hallazgo anterior"
                  aria-label="Hallazgo anterior"
                >
                  <SkipBack className="w-4 h-4" />
                </button>
                <button
                  onClick={handleNext}
                  disabled={currentIndex >= hallazgos.length - 1}
                  className="p-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  title="Siguiente hallazgo"
                  aria-label="Siguiente hallazgo"
                >
                  <SkipForward className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Columna Lateral: Lista de "Saltar a" y Detalle del Hallazgo */}
        <div className="lg:col-span-4 space-y-4">
          {/* Tarjeta del Hallazgo Seleccionado */}
          {selectedHallazgo && (
            <motion.div
              key={selectedHallazgo.id}
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-white p-5 rounded-xl border border-slate-200 space-y-4"
            >
              <div>
                <div className="text-xs font-medium text-rose-600 inline-flex items-center gap-1">
                  <IconoSeleccionado className="w-3.5 h-3.5" />
                  {traducirTipoHallazgo(selectedHallazgo.tipo)}
                </div>
                <h3 className="font-semibold text-slate-900 text-base mt-0.5">
                  {selectedHallazgo.producto}
                </h3>
                <div className="text-xs text-slate-500 mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                  {selectedHallazgo.sku && (
                    <span className="inline-flex items-center gap-1">
                      <ICONO_DATO.sku className="w-3.5 h-3.5 text-slate-400" />
                      SKU: {selectedHallazgo.sku}
                    </span>
                  )}
                  <span className="inline-flex items-center gap-1">
                    <ICONO_DATO.ubicacion className="w-3.5 h-3.5 text-slate-400" />
                    {ubicacionLarga(selectedHallazgo)}
                  </span>
                </div>
              </div>

              {/* Imagen/Recorte de evidencia */}
              <div className="rounded-lg overflow-hidden bg-slate-900 aspect-video">
                <img
                  src={selectedHallazgo.evidencia_crop || EVIDENCIA_VACIA}
                  alt={`Recorte de ${selectedHallazgo.producto} (cuadro ${selectedHallazgo.cuadro})`}
                  className="w-full h-full object-cover"
                />
              </div>

              {/* Comparativa de Precios */}
              <div className="grid grid-cols-2 gap-2 bg-slate-50 p-3 rounded-lg text-center font-tabular">
                <div>
                  <div className="text-xs text-slate-500 inline-flex items-center gap-1">
                    <ICONO_DATO.etiqueta className="w-3.5 h-3.5 text-slate-400" />
                    Etiqueta
                  </div>
                  <div className="text-sm font-semibold text-rose-600">
                    {formatearPrecioEtiqueta(selectedHallazgo.precio_etiqueta, moneda)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-slate-500 inline-flex items-center gap-1">
                    <ICONO_DATO.sistema className="w-3.5 h-3.5 text-slate-400" />
                    Sistema
                  </div>
                  <div className="text-sm font-semibold text-slate-900">
                    {selectedHallazgo.precio_sistema !== null ? fm(selectedHallazgo.precio_sistema) : 'Sin datos'}
                  </div>
                </div>
              </div>

              <p className="flex items-start gap-1.5 text-sm text-slate-600 leading-relaxed">
                <ICONO_DATO.accion className="w-4 h-4 text-teal-600 shrink-0 mt-0.5" />
                <span>
                  <span className="font-medium text-slate-900">Acción sugerida:</span> {selectedHallazgo.accion_sugerida}
                </span>
              </p>

              <div className="flex items-center justify-between text-sm pt-3 border-t border-slate-100">
                <span className="text-slate-500 inline-flex items-center gap-1.5">
                  <TrendingDown className="w-4 h-4 text-slate-400" />
                  Impacto diario
                </span>
                <span className="font-semibold text-rose-600 font-tabular">
                  {fm(selectedHallazgo.impacto_diario)}/día
                </span>
              </div>
            </motion.div>
          )}

          {/* Lista de enlaces accesibles "Saltar a" */}
          <div className="bg-white p-4 rounded-xl border border-slate-200">
            <h3 className="text-sm font-semibold text-slate-900 mb-2 px-1 flex items-center gap-2">
              <ListVideo className="w-4 h-4 text-slate-400" />
              Hallazgos en el video
            </h3>
            <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
              {hallazgos.map((h, idx) => {
                const isSelected = selectedHallazgo?.id === h.id;
                const seg = h.segundo || cuadroASegundos(h.cuadro);
                const Icono = iconoTipo(h.tipo);
                return (
                  <button
                    key={h.id}
                    onClick={() => jumpToHallazgo(h)}
                    title={traducirTipoHallazgo(h.tipo)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-xs flex items-center justify-between transition-colors ${
                      isSelected
                        ? 'bg-teal-50 text-teal-800 font-semibold'
                        : 'hover:bg-slate-50 text-slate-700'
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <span className="w-4 text-slate-400 text-right shrink-0 font-tabular">{idx + 1}</span>
                      <Icono className={`w-3.5 h-3.5 shrink-0 ${isSelected ? 'text-teal-600' : 'text-slate-400'}`} />
                      <span className="truncate">{h.producto}</span>
                    </div>
                    <span className="font-tabular text-slate-500 shrink-0 ml-2">
                      {formatearTiempoVideo(seg)}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
