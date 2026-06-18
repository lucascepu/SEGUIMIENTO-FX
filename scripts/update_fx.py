#!/usr/bin/env python3
"""
update_fx.py — Actualización automática SIOPEL
================================================
Fuente: API oficial BCRA — api.bcra.gob.ar
  - Primaria:  /estadisticascambiarias/v1.0/Cotizaciones/USD (Divisa Venta)
  - Fallback:  /estadisticas/v2.0/DatosVariable/4/{desde}/{hasta} (Com. A3500)

Uso:
  python3 scripts/update_fx.py              # fecha de hoy
  python3 scripts/update_fx.py 2026-06-18   # fecha específica
  python3 scripts/update_fx.py 2026-06-18 1440.0  # valor manual si API falla
"""

import sys, re, json, datetime, urllib.request, subprocess, time

HTML_PATH  = "index.html"
SMOKE_TEST = "test/smoke-test.js"

# ── 1. Fecha de actualización ───────────────────────────────────────────────
if len(sys.argv) >= 2:
    fecha = datetime.datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
else:
    fecha = datetime.date.today()

fecha_api  = fecha.strftime("%Y-%m-%d")
target_lbl = f"{fecha.day}/{fecha.month}"   # "18/6"
mes_upper  = fecha.strftime("%b").upper()   # "JUN"

print(f"Fecha objetivo: {fecha_api}  label: {target_lbl}")

# ── 2. Leer HTML ─────────────────────────────────────────────────────────────
with open(HTML_PATH, "r", encoding="utf-8") as f:
    html = f.read()

# ── 3. Detectar índices usando pLbl (fuente de verdad de fechas) ─────────────
m_plbl = re.search(r"var pLbl=\[(.+?)\];", html, re.DOTALL)
if not m_plbl:
    print("ERROR: no se encontró pLbl en el HTML")
    sys.exit(1)

proj_labels = [p.strip().strip("'\"") for p in m_plbl.group(1).split(",")]

if target_lbl not in proj_labels:
    print(f"ERROR: la fecha {target_lbl} no está en pLbl (¿es feriado o está fuera del rango Jul 2026?)")
    print(f"Fechas disponibles en pLbl: {[l for l in proj_labels if l]}")
    sys.exit(1)

new_proj_idx = proj_labels.index(target_lbl)

# ia_proj e ia_hist actuales
m_ia = re.search(r"var ia=mode===.proj.\?(\d+):(\d+)", html)
if not m_ia:
    print("ERROR: no se encontró 'var ia' en el HTML")
    sys.exit(1)

cur_proj_idx = int(m_ia.group(1))
cur_hist_idx = int(m_ia.group(2))

# Offset de proyección → offset equivalente en histórico
offset = new_proj_idx - cur_proj_idx
new_hist_idx = cur_hist_idx + offset

print(f"Índice histórico:  {cur_hist_idx} → {new_hist_idx}  (offset={offset})")
print(f"Índice proyección: {cur_proj_idx} → {new_proj_idx}")

if offset <= 0:
    print("INFO: el índice objetivo ya es el actual o es anterior. Sin cambios.")
    sys.exit(0)

# ── 4. Verificar que hS[new_hist_idx] sea null ──────────────────────────────
m_hs = re.search(r"var hS=\[(.+?)\];", html, re.DOTALL)
hs_parts = [p.strip() for p in m_hs.group(1).split(",")]

if new_hist_idx >= len(hs_parts):
    print(f"ERROR: new_hist_idx={new_hist_idx} fuera del array hS (len={len(hs_parts)})")
    sys.exit(1)

if hs_parts[new_hist_idx] != "null":
    print(f"INFO: hS[{new_hist_idx}] ya tiene valor {hs_parts[new_hist_idx]}. Sin cambios.")
    sys.exit(0)

# ── 5. Obtener techo del array hT ──────────────────────────────────────────
m_ht = re.search(r"var hT=\[(.+?)\];", html, re.DOTALL)
ht_parts = [p.strip() for p in m_ht.group(1).split(",")]
techo_new = float(ht_parts[new_hist_idx])
print(f"Techo {target_lbl}: ${techo_new:,.2f}")

# ── 6. Obtener valor SIOPEL desde API BCRA oficial ──────────────────────────
siopel_new = None

# Valor manual si se pasa como argumento
if len(sys.argv) >= 3:
    siopel_new = float(sys.argv[2])
    print(f"Valor manual recibido: ${siopel_new}")

def bcra_cotizacion(fecha_api):
    """API Estadísticas Cambiarias BCRA — Divisa Venta USD"""
    url = (f"https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones/USD"
           f"?fechaDesde={fecha_api}&fechaHasta={fecha_api}&limit=50")
    req = urllib.request.Request(url, headers={
        "Accept":     "application/json",
        "User-Agent": "SIOPEL-Dashboard/1.0"
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)

    results = data.get("results", [])
    if not results:
        print(f"  API cotizaciones: sin datos para {fecha_api}")
        return None

    detalle = results[0].get("detalle", [])
    print(f"  Tipos disponibles:")
    for d in detalle:
        print(f"    tipoPase={d.get('tipoPase')}  tipoCotizacion={d.get('tipoCotizacion')}  desc={d.get('descripcion')}")

    # Buscar DIVISA VENTA
    for d in detalle:
        desc = (d.get("descripcion") or "").upper()
        if "DIVISA" in desc and "VENTA" in desc:
            val = float(d.get("tipoCotizacion", 0))
            print(f"  ✓ DIVISA VENTA: {val}")
            return val

    # Fallback: mayor valor entre DIVISA (venta > compra)
    divs = [float(d.get("tipoCotizacion", 0))
            for d in detalle if "DIVISA" in (d.get("descripcion") or "").upper()]
    if divs:
        val = max(divs)
        print(f"  ~ Fallback max DIVISA: {val}")
        return val
    return None

def bcra_variable4(fecha_api):
    """API Principales Variables BCRA — Variable 4: Tipo cambio mayorista A3500"""
    url = (f"https://api.bcra.gob.ar/estadisticas/v2.0/DatosVariable/4"
           f"/{fecha_api}/{fecha_api}")
    req = urllib.request.Request(url, headers={
        "Accept":     "application/json",
        "User-Agent": "SIOPEL-Dashboard/1.0"
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)
    results = data.get("results", [])
    if results:
        val = float(results[-1].get("valor", 0))
        print(f"  ✓ Variable 4 (mayorista A3500): {val}")
        return val
    return None

if not siopel_new:
    print("Consultando API Estadísticas Cambiarias BCRA...")
    try:
        siopel_new = bcra_cotizacion(fecha_api)
    except Exception as e:
        print(f"  Error: {e}")

if not siopel_new:
    print("Consultando API Variables Principales BCRA (variable 4)...")
    try:
        siopel_new = bcra_variable4(fecha_api)
    except Exception as e:
        print(f"  Error: {e}")

if not siopel_new:
    print(f"\nERROR: No se pudo obtener el valor SIOPEL para {fecha_api}.")
    print("El dato puede no estar disponible aún (BCRA publica después de las 18 hs).")
    print("Si necesitás actualizar manualmente:")
    print(f"  python3 scripts/update_fx.py {fecha_api} 1440.0")
    sys.exit(1)

print(f"\nSIOPEL {fecha_api}: ${siopel_new:,.2f}")

# ── 7. Calcular métricas ────────────────────────────────────────────────────
brecha_new = round((techo_new - siopel_new) / siopel_new * 100, 2)
prev_siopel = float(hs_parts[cur_hist_idx])
prev_techo  = float(ht_parts[cur_hist_idx])
prev_brecha = round((prev_techo - prev_siopel) / prev_siopel * 100, 2)
delta_s     = round(siopel_new - prev_siopel, 1)
delta_pct   = round(delta_s / prev_siopel * 100, 2)
delta_b     = round(brecha_new - prev_brecha, 2)
hA_new      = int(round(techo_new / 1.152))

print(f"Brecha: {brecha_new}%  |  Δ: {delta_s:+} ({delta_pct:+.2f}%)")

# ── 8. Aplicar todos los cambios ─────────────────────────────────────────────
print("\nActualizando HTML...")

# 8a. hS[new_hist_idx]
hs_parts[new_hist_idx] = str(siopel_new)
html = re.sub(
    r"var hS=\[.+?\];",
    "var hS=[" + ",".join(hs_parts) + "];",
    html, flags=re.DOTALL
)
print(f"  ✓ hS[{new_hist_idx}] = {siopel_new}")

# 8b. hPt: mover punto grande al nuevo índice
html = re.sub(rf"hPt\[{cur_hist_idx}\]=7;",
              f"hPt[{cur_hist_idx}]=3; hPt[{new_hist_idx}]=7;", html)
print(f"  ✓ hPt: [{cur_hist_idx}]=3 → [{new_hist_idx}]=7")

# 8c. brechaVals
html = re.sub(
    rf"(brechaVals\[{cur_hist_idx}\]={re.escape(str(prev_brecha))};)",
    rf"\1\n  brechaVals[{new_hist_idx}]={brecha_new};",
    html
)
print(f"  ✓ brechaVals[{new_hist_idx}] = {brecha_new}")

# 8d. hA + avgRef: append after cur line
html = re.sub(
    rf"(hA\[{cur_hist_idx}\]=\d+;)",
    rf"\1\n  hA[{new_hist_idx}]={hA_new};\n  avgRef[{new_hist_idx}]=15.2;",
    html
)
print(f"  ✓ hA[{new_hist_idx}]={hA_new}  avgRef[{new_hist_idx}]=15.2")

# 8e. Zone ia
html = html.replace(
    f"var ia=mode==='proj'?{cur_proj_idx}:{cur_hist_idx}",
    f"var ia=mode==='proj'?{new_proj_idx}:{new_hist_idx}"
)
print(f"  ✓ ia: hist={new_hist_idx}, proj={new_proj_idx}")

# 8f. Zone label
dia = str(fecha.day)
html = re.sub(r"'\d+-[A-Z]+ ←'", f"'{dia}-{mes_upper} ←'", html, count=1)
print(f"  ✓ zone label → {dia}-{mes_upper}")

# 8g. sJunActual si estamos en junio
if fecha.month == 6:
    m_sja = re.search(r"var sJunActual=\[([^\]]+)\]", html)
    if m_sja:
        html = html.replace(
            m_sja.group(0),
            m_sja.group(0)[:-1] + f",{siopel_new}]"
        )
        html = re.sub(
            r"(\.concat\(sJunActual,\s*N\()(\d+)(\)\))",
            lambda mo: f"{mo.group(1)}{int(mo.group(2))-1}{mo.group(3)}",
            html, count=1
        )
        print(f"  ✓ sJunActual += {siopel_new}")

# 8h. pPt
html = re.sub(rf"pPt\[{cur_proj_idx}\]=7;",
              f"pPt[{cur_proj_idx}]=3; pPt[{new_proj_idx}]=7;", html)
print(f"  ✓ pPt: [{cur_proj_idx}]=3 → [{new_proj_idx}]=7")

# 8i. Cards — formato ARS: $1.436,50
def fmt_ars(v):
    s = f"{v:,.2f}"          # "1,436.50"
    return s.replace(",","X").replace(".",",").replace("X",".")  # "1.436,50"

html = re.sub(
    r"(SIOPEL \()\d+/\d+(\))</div><div class=\"card-val\">\$[^<]+</div>",
    rf"\g<1>{fecha.day}/{fecha.month}\2</div><div class=\"card-val\">${fmt_ars(siopel_new)}</div>",
    html, count=1
)
html = re.sub(
    r"(TECHO BCRA</div><div class=\"card-val\">)\$[^<]+</div>",
    rf"\g<1>${fmt_ars(techo_new)}</div>",
    html, count=1
)
html = re.sub(r">\+[\d.]+%<", f">+{brecha_new}%<", html, count=1)
print(f"  ✓ Cards actualizadas")

# 8j. Stamp date
html = re.sub(r"<span>\d+ \w+ 2026</span>",
              f"<span>{fecha.day} {fecha.strftime('%b').lower()} 2026</span>",
              html, count=1)
print(f"  ✓ Stamp: {fecha.day} {fecha.strftime('%b').lower()} 2026")

# ── 9. Guardar ──────────────────────────────────────────────────────────────
with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(html)
print("\nHTML guardado.")

# ── 10. Smoke test ──────────────────────────────────────────────────────────
print("Ejecutando smoke test...")
result = subprocess.run(["node", SMOKE_TEST], capture_output=True, text=True)
if result.returncode != 0:
    print("ERROR: smoke test falló:")
    print(result.stdout)
    sys.exit(1)
print(result.stdout.split("\n")[-2])  # última línea del test

print(f"""
══ ACTUALIZACIÓN COMPLETA ══════════════════════════
  Fecha:    {fecha.strftime('%d/%m/%Y')}
  SIOPEL:   ${siopel_new:>10,.2f}
  Techo:    ${techo_new:>10,.2f}
  Brecha:   {brecha_new:>8.2f}%
  Δ SIOPEL: {delta_s:+.1f} ({delta_pct:+.2f}%)
  Δ Brecha: {delta_b:+.2f} pp
════════════════════════════════════════════════════
""")
