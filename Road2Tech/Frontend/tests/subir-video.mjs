// Flujo "Subir video": sube un clip, espera al motor y revisa que las pantallas muestren el
// resultado. Necesita el tablero (npm run dev o npm start) y la API del motor
// (python -m cruce.api en motor-procesamiento/).
//
//   node tests/subir-video.mjs [ruta/al/video.mp4] [--sin-estructura]
//   node tests/subir-video.mjs ../../videos_ia/gemini_generated_video_ea815464.mp4 --sin-estructura
import { chromium } from 'playwright';
import path from 'path';

const args = process.argv.slice(2);
const SIN_ESTRUCTURA = args.includes('--sin-estructura');
const VIDEO = path.resolve(
  args.find((a) => !a.startsWith('--')) || '../../motor-procesamiento/video/clip_10s.mp4'
);
const BASE = 'http://localhost:3000';

async function probarSubida() {
  console.log(`Subiendo ${VIDEO}...`);
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/usr/bin/google-chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

  // 1. Elegir el archivo y procesarlo
  await page.goto(`${BASE}/analizar`, { waitUntil: 'networkidle' });
  if (await page.locator('text=La API del motor no responde').isVisible()) {
    throw new Error('La API del motor está apagada: python -m cruce.api');
  }
  if (SIN_ESTRUCTURA) {
    await page.locator('label:has-text("Sin estructura")').click();
  }
  await page.locator('input[type=file]').setInputFiles(VIDEO);
  await page.locator('button:has-text("Subir y procesar")').click();
  await page.waitForSelector('text=El motor está procesando el video', { timeout: 30000 });
  console.log('  ✔ Video subido; el motor está procesando.');

  await page.waitForSelector('text=Video procesado', { timeout: 300000 });
  const frase = await page.locator('h3:has-text("al día en juego")').textContent();
  console.log(`  ✔ Procesado: ${frase}`);

  // 2. El resumen y el encabezado muestran el video subido
  await page.locator('a:has-text("Ver resumen")').click();
  await page.waitForURL('**/resumen');
  await page.waitForSelector(`text=Video subido: ${path.basename(VIDEO)}`, { timeout: 10000 });
  const aviso = SIN_ESTRUCTURA ? 'Video sin estructura' : 'Video subido';
  if (!(await page.locator(`header >> text=${aviso}`).isVisible())) {
    throw new Error(`El encabezado no dice "${aviso}".`);
  }
  console.log('  ✔ Resumen y encabezado muestran el video subido.');

  // 3. El recorrido reproduce el video anotado del motor (servido por la API con Range)
  await page.goto(`${BASE}/recorrido`, { waitUntil: 'networkidle' });
  const src = await page.locator('video').getAttribute('src');
  if (!src?.startsWith('/motor/archivos/analisis/')) {
    throw new Error(`El recorrido no usa el video del análisis: ${src}`);
  }
  await page.waitForFunction(() => (document.querySelector('video')?.duration || 0) > 0, null, {
    timeout: 15000,
  });
  console.log(`  ✔ Recorrido con el video anotado del análisis (${src}).`);

  // 4. Regresar al recorrido de demostración desde el historial
  await page.goto(`${BASE}/analizar`, { waitUntil: 'networkidle' });
  await page
    .locator('div:has(> div > div:text("Recorrido de demostración")) >> button:has-text("Mostrar")')
    .click();
  await page.waitForSelector('text=El tablero muestra el recorrido de demostración.');
  await page.goto(`${BASE}/resumen`, { waitUntil: 'networkidle' });
  await page.waitForSelector('text=8 problemas', { timeout: 10000 });
  console.log('  ✔ De vuelta al recorrido de demostración.');

  await browser.close();
  console.log('Flujo de subida de video completo.');
}

probarSubida().catch((err) => {
  console.error('Error en la prueba de subida:', err);
  process.exit(1);
});
