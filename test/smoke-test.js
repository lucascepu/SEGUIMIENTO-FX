/**
 * SMOKE TEST — SIOPEL Dashboard
 * ─────────────────────────────────────────────────────────────────────────
 * Corre el JS real del index.html en un DOM simulado y valida que:
 *   1) El script entero ejecuta sin errores (sintaxis, referencias rotas)
 *   2) sw('hist'), sw('proj'), sw('brecha') funcionan sin tirar excepciones
 *   3) Todos los datasets de cada modo tienen el mismo largo que sus labels
 *   4) pointRadius (cuando es array) coincide en largo con su dataset
 *
 * Uso:
 *   node test/smoke-test.js
 *
 * Exit code 0 = todo OK · Exit code 1 = se encontró al menos un problema
 * ─────────────────────────────────────────────────────────────────────────
 */

const fs = require('fs');
const path = require('path');

const HTML_PATH = path.join(__dirname, '..', 'index.html');
let failed = false;

function fail(msg) {
  console.log('  ✗ ' + msg);
  failed = true;
}
function ok(msg) {
  console.log('  ✓ ' + msg);
}

// ── 1. Extraer el <script> principal del index.html ──
const html = fs.readFileSync(HTML_PATH, 'utf8');
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
  .map(m => m[1])
  .filter(s => s.includes('Chart') || s.includes('window.sw'));

if (scripts.length === 0) {
  console.log('✗ No se encontró el <script> principal en index.html');
  process.exit(1);
}
const mainScript = scripts[scripts.length - 1];
console.log(`Script extraído: ${mainScript.length} caracteres\n`);

// ── 2. DOM / Chart.js mock mínimo ──
function mockEl() {
  return {
    style: {}, value: '', textContent: '', innerHTML: '',
    addEventListener: () => {}, getAttribute: () => null,
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 800, height: 500 }),
    classList: { add: () => {}, remove: () => {} },
    width: 800, height: 500,
  };
}

global.window = global;
global.document = {
  getElementById: () => mockEl(),
  querySelectorAll: () => ({ forEach: () => {} }),
  addEventListener: () => {},
};
global.navigator = { userAgent: 'node-smoketest' };
global.addEventListener = () => {};

let lastChartInstance = null;
global.Chart = function (ctx, cfg) {
  this.data = cfg.data;
  this.options = cfg.options;
  this.chartArea = { left: 50, right: 780, top: 10, bottom: 450, width: 730, height: 440 };
  this.scales = {
    x: { min: 0, max: 100, width: 730 },
    y: { min: 0, max: 100, height: 440 },
  };
  this.update = () => {};
  this.resetZoom = () => {};
  lastChartInstance = this;
};

// ── 3. Ejecutar el script completo ──
console.log('── Ejecutando script completo ──');
try {
  eval(mainScript);
  ok('Script ejecuta sin errores de sintaxis/referencia');
} catch (e) {
  fail(`Excepción al ejecutar: ${e.message}`);
  console.log(e.stack.split('\n').slice(0, 4).join('\n'));
  process.exit(1); // sin esto no tiene sentido seguir
}

// ── 4. Validar que window.sw existe ──
console.log('\n── Validando función sw() ──');
if (typeof window.sw !== 'function') {
  fail('window.sw no es una función (¿fue sobreescrita con algo roto?)');
  process.exit(1);
}
ok('window.sw está definida');

// ── 5. Probar los 3 modos ──
const modes = ['hist', 'proj', 'brecha'];
for (const mode of modes) {
  console.log(`\n── Modo: ${mode} ──`);
  try {
    window.sw(mode);
    ok(`sw('${mode}') ejecuta sin excepciones`);
  } catch (e) {
    fail(`sw('${mode}') tiró: ${e.message}`);
    continue;
  }

  const chart = lastChartInstance;
  if (!chart || !chart.data) {
    fail('No se pudo leer chart.data después de sw()');
    continue;
  }

  const labelLen = chart.data.labels.length;
  let modeOk = true;
  chart.data.datasets.forEach((ds, i) => {
    const name = ds.label || `dataset[${i}]`;
    if (Array.isArray(ds.data) && ds.data.length !== labelLen) {
      fail(`"${name}": data.length=${ds.data.length} ≠ labels.length=${labelLen}`);
      modeOk = false;
    }
    if (Array.isArray(ds.pointRadius) && ds.pointRadius.length !== ds.data.length) {
      fail(`"${name}": pointRadius.length=${ds.pointRadius.length} ≠ data.length=${ds.data.length}`);
      modeOk = false;
    }
  });
  if (modeOk) ok(`Todos los datasets (${chart.data.datasets.length}) coinciden en largo con labels (${labelLen})`);
}

// ── 6. Resumen ──
console.log('\n' + '─'.repeat(50));
if (failed) {
  console.log('❌ SMOKE TEST FALLÓ — revisar los ✗ arriba antes de pushear');
  process.exit(1);
} else {
  console.log('✅ SMOKE TEST OK — todo funciona correctamente');
  process.exit(0);
}
