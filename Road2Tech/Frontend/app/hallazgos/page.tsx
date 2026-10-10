import { getHallazgosData } from '@/lib/data/loader';
import { HallazgosView } from '@/components/hallazgos/HallazgosView';

export default async function HallazgosPage() {
  const data = await getHallazgosData();
  return <HallazgosView data={data} />;
}
