import { AsistenteView } from '@/components/asistente/AsistenteView';

// ?id=<análisis> abre el asistente en esa corrida (desde "Subir video"); "demo" = recorrido de demo
export default async function AsistentePage({ searchParams }: { searchParams: Promise<{ id?: string }> }) {
  const { id } = await searchParams;
  return <AsistenteView idInicial={id} />;
}
