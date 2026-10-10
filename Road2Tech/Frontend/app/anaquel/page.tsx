import { getHallazgosData } from '@/lib/data/loader';
import { AnaquelView } from '@/components/anaquel/AnaquelView';

export default async function AnaquelPage() {
  const data = await getHallazgosData();
  return <AnaquelView data={data} />;
}
