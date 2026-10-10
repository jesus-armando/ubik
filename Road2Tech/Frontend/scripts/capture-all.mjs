import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENS = [
  { name: '1_resumen', path: '/resumen' },
  { name: '2_recorrido', path: '/recorrido' },
  { name: '3_anaquel', path: '/anaquel' },
  { name: '4_hallazgos', path: '/hallazgos' },
];

const RESOLUTIONS = [
  { name: '1920x1080', width: 1920, height: 1080 },
  { name: '1280x720', width: 1280, height: 720 },
];

async function runCapture(outputDir = 'screenshots/baseline') {
  fs.makedirsSync ? fs.makedirsSync(outputDir) : fs.mkdirSync(outputDir, { recursive: true });

  console.log(`Iniciando captura de pantallas en: ${outputDir}`);
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/usr/bin/google-chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  for (const res of RESOLUTIONS) {
    const context = await browser.newContext({
      viewport: { width: res.width, height: res.height },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();

    for (const screen of SCREENS) {
      const url = `http://localhost:3000${screen.path}`;
      console.log(`Capturando ${screen.name} en ${res.name}...`);
      await page.goto(url, { waitUntil: 'networkidle' });
      await page.waitForTimeout(600); // esperar animaciones de Framer Motion

      const filename = `${screen.name}_${res.name}.png`;
      await page.screenshot({
        path: path.join(outputDir, filename),
        fullPage: false,
      });
      console.log(`  -> Guardado: ${filename}`);
    }

    await context.close();
  }

  await browser.close();
  console.log('Capturas completadas exitosamente.');
}

const outDir = process.argv[2] || 'screenshots/final';
runCapture(outDir).catch((err) => {
  console.error('Error durante la captura:', err);
  process.exit(1);
});
