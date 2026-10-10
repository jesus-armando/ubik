import { getHallazgosData } from '@/lib/data/loader';
import { RecorridoView } from '@/components/recorrido/RecorridoView';

export default async function RecorridoPage() {
  const data = await getHallazgosData();
  return <RecorridoView data={data} />;
}
