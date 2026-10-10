import './globals.css';
import type { Metadata } from 'next';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { getHallazgosData } from '@/lib/data/loader';

export const metadata: Metadata = {
  title: 'Auditoría de Anaqueles · Glazed Co. Dashboard',
  description: 'Sistema de detección de incidencias de precios, faltantes y gemelo digital de anaquel para supermercados.',
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { resumen } = await getHallazgosData();
  return (
    <html lang="es" className="h-full">
      <body className="h-full bg-slate-50 text-slate-900 antialiased font-sans">
        <div className="flex min-h-screen">
          {/* Navegación Lateral Fija */}
          <Sidebar />

          {/* Área Principal de Contenido */}
          <div className="flex-1 ml-60 flex flex-col min-w-0">
            <Header fechaEscaneo={resumen.fecha_escaneo} disclaimer={resumen.disclaimer} />
            <main className="flex-1 p-4 sm:p-5 lg:p-6 max-w-7xl mx-auto w-full">
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
