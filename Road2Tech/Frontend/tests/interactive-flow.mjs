import { chromium } from 'playwright';

async function testInteractiveFlow() {
  console.log('Iniciando prueba interactiva con Playwright...');
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/usr/bin/google-chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

  // 1. Probar Anaquel e Interacción de Posición
  console.log('1. Probando interacción de Anaquel...');
  await page.goto('http://localhost:3000/anaquel', { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);

  // Clic en la posición P1 de la repisa 1 (precio viejo detectado por el motor)
  const posButton = page.locator('text=Original Coffee Cake Muffin').first();
  await posButton.click();
  await page.waitForTimeout(400);

  // Verificar que el panel lateral muestra el detalle y la acción recomendada
  const detailHeader = page.locator('img[alt="Evidencia de Original Coffee Cake Muffin"]');
  if (await detailHeader.isVisible()) {
    console.log('  ✔ Panel lateral de posición abierto correctamente con evidencia.');
  } else {
    throw new Error('Fallo al abrir panel lateral de posición en Anaquel.');
  }

  // 2. Probar Hallazgos y botón "Marcar corregido"
  console.log('2. Probando botón "Marcar corregido" en Hallazgos...');
  await page.goto('http://localhost:3000/hallazgos', { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);

  const marcarButton = page.locator('text=Marcar corregido').first();
  await marcarButton.click();
  await page.waitForTimeout(400);

  const deshacerButton = page.locator('text=Deshacer corrección').first();
  if (await deshacerButton.isVisible()) {
    console.log('  ✔ Hallazgo marcado como corregido exitosamente; estado visual actualizado.');
  } else {
    throw new Error('Fallo en la acción de marcar corregido.');
  }

  await browser.close();
  console.log('Todas las pruebas interactivas pasaron con éxito.');
}

testInteractiveFlow().catch((err) => {
  console.error('Error en prueba interactiva:', err);
  process.exit(1);
});
