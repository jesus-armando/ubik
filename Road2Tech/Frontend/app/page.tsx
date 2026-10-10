import { getHallazgosData } from '@/lib/data/loader';
import { ResumenView } from '@/components/resumen/ResumenView';

export default async function HomePage() {
  const data = await getHallazgosData();
  return <ResumenView data={data} />;
}
