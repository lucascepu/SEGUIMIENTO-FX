# SEGUIMIENTO-FX — Dashboard SIOPEL vs Banda Cambiaria BCRA

> **Última revisión de esta documentación:** 19 de junio de 2026

Dashboard web estático que visualiza el tipo de cambio mayorista (SIOPEL Divisa Venta) versus el techo de la banda cambiaria del BCRA, con proyecciones hasta diciembre 2026.

**URL de producción:** https://seguimiento-fx.vercel.app/

---

## Stack

| Componente | Tecnología |
|---|---|
| Frontend | HTML + JS vanilla + Chart.js v4 |
| Hosting | Vercel (deploy automático desde `main`) |
| Automatización | GitHub Actions |
| Fuente de datos | API oficial BCRA (`api.bcra.gob.ar`) |

No hay backend, base de datos ni dependencias de npm. Todo el estado histórico vive en arrays de JS dentro de `index.html`.

---

## Estructura del repositorio

```
SEGUIMIENTO-FX/
├── index.html                     ← Dashboard completo (UI + datos + lógica)
├── scripts/
│   └── update_fx.py               ← Script de actualización diaria
├── test/
│   └── smoke-test.js              ← Validación JS (sin browser)
└── .github/
    └── workflows/
        └── update-fx.yml          ← Workflow de automatización diaria
```

---

## Arquitectura de datos en `index.html`

Todos los datos históricos están embebidos como arrays de JS en el mismo `index.html`. No hay fetch de datos externos en el frontend.

### Arrays principales (313 elementos, abr 2025 – jul 2026)

| Variable | Tipo | Contenido |
|---|---|---|
| `hS` | Estático | SIOPEL Divisa Venta diario (null = sin dato) |
| `hT` | Estático | Techo oficial BCRA diario (pre-calculado) |
| `hLbl` / `hDispLbl` | Estático | Labels de fechas para el eje X |
| `hPt` | Estático | Radio de cada punto (3 = normal, 7 = último dato) |
| `brechaVals` | **Dinámico** | Calculado en JS: `(hT[i]-hS[i])/hS[i]*100` |
| `hA` | **Dinámico** | Calculado por `setAvgWindow()`: techo/(1+avgBrecha/100) |
| `avgRef` | **Dinámico** | Rolling average de brecha (30d/90d/6M) |

### Arrays de proyección (51 elementos, may–dic 2026)

| Variable | Contenido |
|---|---|
| `pLbl` | Fechas: 4 mayo + 21 junio + 21 julio + 5 mensuales (ago–dic) |
| `pS` | SIOPEL real (hasta última rueda) + null para fechas futuras |
| `pT` | Techo proyectado (pre-calculado con crawling peg ~2.5%/mes) |
| `pREM` / `pSCA` / `pSCB` / `pSCC` | Escenarios: REM, brecha actual, brecha 15%, brecha 5% |

### Variable de control

```javascript
var ia = mode==='proj' ? 16 : 283;  // índice del último dato real
```

Controla la zona divisoria "con datos / sin SIOPEL" en el gráfico.

---

## Flujo de actualización automática

### Trigger
GitHub Actions corre todos los días hábiles a las **17:30 hs Argentina (UTC-3)**, es decir `cron: '30 20 * * 1-5'`.

### Pasos del workflow
```
update-fx.yml (17:30 ARG)
  → checkout del repo
  → python3 scripts/update_fx.py YYYY-MM-DD
      → consulta api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones/USD
      → identifica el valor SIOPEL del día
      → actualiza index.html (ver detalle abajo)
      → node test/smoke-test.js (valida los 3 modos del chart)
      → si smoke test OK → commit + push
  → Vercel detecta el push → redeploya (~20 segundos)
```

### Qué modifica `update_fx.py` en cada actualización

1. `hS[new_idx]` — agrega el nuevo valor SIOPEL
2. `hPt[prev]=3; hPt[new]=7` — mueve el punto destacado
3. `ia` — incrementa el índice de la zona divisoria
4. Zona label — actualiza el texto "18-JUN ←"
5. `sJunActual` — agrega valor al sub-array de junio (modo proyección)
6. `pPt` — mueve el punto en modo proyección
7. Cards KPI — SIOPEL, Techo, Brecha %
8. Barra inferior — "Última actualización"
9. Título del modo histórico

### Fuente de datos BCRA
- **Primaria:** `GET /estadisticascambiarias/v1.0/Cotizaciones/USD?fechaDesde=X&fechaHasta=X`
  - Busca la cotización con mayor valor (desc: "DOLAR E.E.U.U." o "DIVISA VENTA")
- **Sin autenticación requerida.** API pública del BCRA.

### Fallback manual
Si la API falla o el dato no está disponible:
```bash
# Desde GitHub Actions → Run workflow → campo "valor_manual"
# O localmente:
python3 scripts/update_fx.py 2026-06-19 1455.0
```

---

## Modos del dashboard

| Modo | Descripción |
|---|---|
| **Histórico** | Serie completa abr 2025 – presente vs techo BCRA |
| **Proyección** | Mayo–diciembre 2026 con 4 escenarios (REM, brecha actual, 15%, 5%) |
| **Brecha %** | Evolución diaria de la brecha (techo−SIOPEL)/SIOPEL |

---

## Validación

El smoke test (`test/smoke-test.js`) corre en Node.js sin browser. Valida:
- El script principal ejecuta sin errores de sintaxis/referencia
- `window.sw()` está definida y funciona
- Los 3 modos (`hist`, `proj`, `brecha`) ejecutan sin excepciones
- Todos los datasets coinciden en largo con sus labels

```bash
node test/smoke-test.js
# ✅ SMOKE TEST OK — todo funciona correctamente
```

---

## Actualizaciones manuales pendientes (jun 2026)

| Evento | Acción requerida |
|---|---|
| Publicación REM julio 2026 | Actualizar `pREM`, `pSCA`, `pSCB`, `pSCC` en `index.html` |
| Inicio ruedas julio 2026 | El automático lo maneja (pLbl ya tiene fechas de julio) |
| Agosto 2026 en adelante | Ampliar arrays históricos y de proyección |

---

## Consideraciones de diseño

- **Single-file architecture:** todo en `index.html` facilita el deploy estático pero hace que los datos históricos estén hardcodeados. Cada actualización es un commit que modifica el HTML.
- **Sin build step:** Chart.js y plugins se cargan desde CDN. No hay bundler.
- **Rolling average:** `brechaVals`, `hA` y `avgRef` se recalculan en el cliente al cargar la página. Solo `hS` (precios SIOPEL) necesita actualizarse via script.
- **Indexing:** los arrays tienen 313 slots pre-allocados (abr 2025 – jul 31, 2026). Las fechas futuras son `null` y se visualizan como "sin datos".

---

## Posibles mejoras / puntos de revisión

- [ ] Separar los datos históricos del código de presentación (ej: JSON externo + fetch al cargar)
- [ ] Agregar feriados argentinos al workflow para no intentar actualizar en días sin rueda
- [ ] Manejar el caso de agosto–diciembre 2026 cuando los arrays actuales se agoten
- [ ] Considerar persistencia de datos via GitHub API directa desde el browser (eliminar el script Python)
- [ ] Agregar alertas si la brecha supera cierto umbral
