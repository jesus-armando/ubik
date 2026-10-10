import {
  AlertCircle,
  AlertTriangle,
  ArrowLeftRight,
  Barcode,
  Boxes,
  CheckCircle2,
  CircleHelp,
  Columns3,
  Database,
  Grid3X3,
  History,
  LayoutDashboard,
  LayoutGrid,
  Lightbulb,
  MapPin,
  MessageSquareText,
  PackageOpen,
  PackageSearch,
  PackageX,
  Replace,
  Scale,
  ScanSearch,
  Shuffle,
  SquareDashed,
  Tag,
  TagX,
  UploadCloud,
  Video,
  type LucideIcon,
} from 'lucide-react';
import { TipoHallazgo } from '@/types/hallazgos';

/**
 * Íconos del tablero en un solo lugar, para que cada concepto se vea igual en todas las pantallas:
 * la pantalla en el menú y en su título, cada tipo de hallazgo, su familia y cada dato de una posición.
 * El ícono siempre acompaña a un texto; nunca lo reemplaza.
 */

export const ICONO_PANTALLA = {
  analizar: UploadCloud,
  resumen: LayoutDashboard,
  recorrido: Video,
  anaquel: Grid3X3,
  hallazgos: AlertTriangle,
  asistente: MessageSquareText,
} satisfies Record<string, LucideIcon>;

export const ICONO_ESTADO = {
  ok: CheckCircle2,
  error: AlertTriangle,
  revisar: AlertCircle,
} satisfies Record<string, LucideIcon>;

const ICONO_TIPO: Record<TipoHallazgo, LucideIcon> = {
  precio_anterior: History,
  precio_distinto: ArrowLeftRight,
  precio_inconsistente: Scale,
  etiqueta_faltante: TagX,
  etiqueta_otro_sku: Replace,
  hueco_con_inventario: PackageSearch,
  hueco_agotado: PackageX,
  hueco: SquareDashed,
  frentes_bajos: Columns3,
  producto_equivocado: Shuffle,
  revisar: ScanSearch,
};

export const iconoTipo = (tipo?: string | null): LucideIcon => ICONO_TIPO[tipo as TipoHallazgo] ?? CircleHelp;

// Mismos ids que FAMILIAS_HALLAZGO
const ICONO_FAMILIA: Record<string, LucideIcon> = {
  huecos: PackageOpen,
  acomodo: LayoutGrid,
  etiquetas: Tag,
  revisar: ScanSearch,
};

export const iconoFamilia = (id: string): LucideIcon => ICONO_FAMILIA[id] ?? CircleHelp;

/** Datos de una posición o hallazgo que se repiten entre pantallas. */
export const ICONO_DATO = {
  ubicacion: MapPin,
  sku: Barcode,
  etiqueta: Tag,
  sistema: Database,
  frentes: Columns3,
  existencia: Boxes,
  accion: Lightbulb,
} satisfies Record<string, LucideIcon>;
