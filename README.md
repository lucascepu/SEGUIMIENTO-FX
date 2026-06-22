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

---

## Lógica de ventana temporal y mantenimiento mensual

> Documentado: 19 de junio de 2026

### Principio de diseño

El modo **Histórico Completo** solo contiene techos BCRA **reales y oficiales**. Nunca proyectados.

El BCRA calcula el techo del mes M+2 usando la inflación real del mes M-1:

```
Techo julio 2026    ← inflación real de mayo 2026   → ya informado ✓
Techo agosto 2026   ← inflación real de junio 2026  → se informa ~mediados de julio
Techo septiembre    ← inflación real de julio 2026  → se informa ~mediados de agosto
```

### Ventana de período por defecto ("May-Jul")

La vista por defecto muestra siempre: **mes anterior + mes actual + mes siguiente**.

Esta ventana se desplaza automáticamente — el cálculo es dinámico basado en `lri`
(índice del último dato real) e `IDX_END`. No se borra ningún dato histórico;
los meses más viejos simplemente quedan fuera de la vista por defecto
y siguen accesibles desde "Serie completa" o el date picker.

### Qué pasa automáticamente cada mes

- Las ruedas diarias se agregan solas (GitHub Actions, 17:30 hs Argentina)
- La ventana se desplaza sola a medida que `lri` avanza
- `brechaVals`, `hA`, `avgRef` se recalculan en el cliente al cargar

### Intervención manual única por mes (cuando BCRA publica inflación real)

1. **Calcular los valores diarios del nuevo techo** usando la fórmula del crawling peg
   con la inflación real recién publicada
2. **Extender `hT`** con los nuevos valores diarios del mes siguiente
3. **Extender `hLbl` / `hDispLbl`** con las fechas del nuevo mes
4. **Actualizar `IDX_END`** al último día del nuevo mes
5. **Actualizar el label del botón** (ej: "May-Jul" → "Jun-Ago")

Todo esto se hace en una sola pasada al momento del anuncio del BCRA,
típicamente a mediados del mes siguiente al que se está cerrando.

### Meses proyectados

Los valores para meses futuros sin techo oficial viven exclusivamente en la
solapa **Proyección** (`pT`, `pS`, `pSCA`, `pSCB`, `pSCC`, `pREM`).
Nunca se mezclan con el array `hT` del modo Histórico.

---

## Feriados, fines de semana y días sin operaciones

> Documentado: 22 de junio de 2026

### Comportamiento del workflow por tipo de día

| Tipo de día | El workflow corre? | La API del BCRA tiene dato? | Resultado |
|---|---|---|---|
| **Lunes a Viernes hábil** | ✅ Sí (17:30 hs ARG) | ✅ Sí | Dashboard actualizado automáticamente |
| **Sábado / Domingo** | ❌ No (cron `1-5`) | ❌ No (mercado cerrado) | Sin acción, normal |
| **Feriado nacional** | ✅ Sí (GitHub no sabe que es feriado) | ❌ No (BCRA cerrado) | Script detecta "sin datos" → `exit(0)` limpio → sin commit, dashboard sin cambios |

### Lógica para feriados en `update_fx.py`

Cuando la API del BCRA no devuelve datos, el script termina con código 0:
```
INFO: Sin datos BCRA para YYYY-MM-DD.
Causas posibles: feriado, mercado cerrado, o dato aún no publicado.
El workflow termina sin cambios (exit 0 → verde en GitHub Actions).
```

El workflow queda **verde** (no es un error). El dashboard mantiene el último dato válido.

### Feriados nacionales restantes en 2026

| Fecha | Feriado | Tipo |
|---|---|---|
| Jue 9 Jul | Día de la Independencia | Inamovible |
| Vie 10 Jul | Día no laborable turístico | Puente oficial |
| Lun 17 Ago | Paso a la Inmortalidad Gral. San Martín | Inamovible |
| Lun 12 Oct | Día de la Raza | Inamovible |
| Lun 23 Nov | Día de la Soberanía Nacional | Trasladado (era 20 Nov) |
| Lun 7 Dic | Día no laborable turístico | Puente oficial |
| Mar 8 Dic | Inmaculada Concepción de María | Inamovible |
| Vie 25 Dic | Navidad | Inamovible |

### Notas históricas sobre días sin dato

- **Jun 15, 2026**: Feriado por Güemes (originalmente 17 Jun, trasladado al lunes 15)
- **Jun 20, 2026**: Día de la Bandera (inamovible, cayó sábado — no afectó ruedas)
