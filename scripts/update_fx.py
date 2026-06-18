#!/usr/bin/env python3
"""
update_fx.py — Actualización automática SIOPEL
================================================
Fuente: API oficial del BCRA
  https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones/USD
  y/o Variables Principales (variable 4 = tipo cambio mayorista A3500)

Ejecutar:
  python3 scripts/update_fx.py              # usa fecha de hoy
  python3 scripts/update_fx.py 2026-06-17   # fecha específica
"""

import sys, re, json, datetime, urllib.request, subprocess

# ── Configuración ──────────────────────────────────────────────────────────
HTML_PATH  = "index.html"
SMOKE_TEST = "test/smoke-test.js"

# ── 1. Determinar fecha de consulta ────────────────────────────────────────
if len(sys.argv) > 1:
    fecha_str = sys.argv[1]
    fecha = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
else:
    fecha = datetime.date.today()

fecha_api = fecha.strftime("%Y-%m-%d")
fecha_lbl = fecha.strftime("%-d/%m").lstrip("0").replace("/0", "/")  # "16/6"
fecha_stamp = fecha.strftime("%-d %b %Y").lower()                     # "16 jun 2026"

print(f"Fecha de actualización: {fecha_api}")

# ── 2. Fetch desde BCRA API oficial ────────────────────────────────────────
def fetch_bcra_cotizacion(fecha_api):
    """
    API oficial BCRA — Estadísticas Cambiarias
    https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones/USD
    
    Busca el tipo de cambio DIVISA VENTA (SIOPEL).
    El campo 'descripcion' contiene el tipo de cotización.
    """
    url = (
        f"https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones/USD"
        f"?fechaDesde={fecha_api}&fechaHasta={fecha_api}&limit=50"
    )
    req = urllib.request.Request(url, headers={
        "Accept":     "application/json",
        "User-Agent": "SIOPEL-Dashboard/1.0 (github.com/lucascepu/SEGUIMIENTO-FX)"
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)

    results = data.get("results", [])
    if not results:
        return None

    detalle = results[0].get("detalle", [])
    print(f"  Tipos disponibles para {fecha_api}:")
    for d in detalle:
        print(f"    tipoPase={d.get('tipoPase')} "
              f"tipoCotizacion={d.get('tipoCotizacion')} "
              f"desc={d.get('descripcion')}")

    # Buscar DIVISA VENTA — descripcion suele contener "DIVISA" y "VENTA"
    for d in detalle:
        desc = (d.get("descripcion") or "").upper()
        if "DIVISA" in desc and "VENTA" in desc:
            val = d.get("tipoCotizacion")
            print(f"  ✓ DIVISA VENTA encontrada: {val}")
            return float(val)

    # Fallback: buscar mayor valor entre entradas "DIVISA" (venta > compra)
    divisas = [d for d in detalle if "DIVISA" in (d.get("descripcion") or "").upper()]
    if divisas:
        val = max(float(d.get("tipoCotizacion", 0)) for d in divisas)
        print(f"  ~ Fallback mayor DIVISA: {val}")
        return val

    return None


def fetch_bcra_variable4(fecha_api):
    """
    Fallback: Principales Variables BCRA
    Variable 4 = Tipo de cambio mayorista ($ por USD) Com. A3500 - Referencia
    https://api.bcra.gob.ar/estadisticas/v2.0/DatosVariable/4/{desde}/{hasta}
    """
    url = (
        f"https://api.bcra.gob.ar/estadisticas/v2.0/DatosVariable/4"
        f"/{fecha_api}/{fecha_api}"
    )
    req = urllib.request.Request(url, headers={
        "Accept":     "application/json",
        "User-Agent": "SIOPEL-Dashboard/1.0"
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)

    results = data.get("results", [])
    if results:
        val = float(results[-1].get("valor", 0))
        print(f"  ✓ Variable 4 (mayorista ref): {val}")
        return val
    return None


# Intentar ambas fuentes
siopel_new = None
try:
    print("Consultando API Estadísticas Cambiarias BCRA...")
    siopel_new = fetch_bcra_cotizacion(fecha_api)
except Exception as e:
    print(f"  Error API cotizaciones: {e}")

if not siopel_new:
    try:
        print("Consultando API Principales Variables BCRA (variable 4)...")
        siopel_new = fetch_bcra_variable4(fecha_api)
    except Exception as e:
        print(f"  Error API variables: {e}")

if not siopel_new:
    print("ERROR: No se pudo obtener el valor del BCRA.")
    print("Podés pasar el valor manualmente:")
    print(f"  python3 scripts/update_fx.py {fecha_api} 1436.5")
    if len(sys.argv) > 2:
        siopel_new = float(sys.argv[2])
        print(f"  Usando valor manual: {siopel_new}")
    else:
        sys.exit(1)

print(f"\nSIOPEL {fecha.strftime('%d/%m/%Y')}: ${siopel_new:,.2f}")

# ── 3. Leer HTML y detectar índice ─────────────────────────────────────────
with open(HTML_PATH, "r", encoding="utf-8") as f:
    html = f.read()

# Detectar lri actual (índice del último dato real)
m = re.search(r"var ia=mode===.proj.\?(\d+):(\d+)", html)
if not m:
    print("ERROR: no se encontró 'var ia' en el HTML")
    sys.exit(1)
ia_proj = int(m.group(1))
ia_hist = int(m.group(2))
prev_idx = ia_hist       # índice del dato anterior
new_idx  = prev_idx + 1  # nuevo índice

print(f"Índice anterior: {prev_idx} → nuevo: {new_idx}")

# Detectar techo en nuevo índice
m2 = re.search(r"var hT=\[(.+?)\];", html, re.DOTALL)
if m2:
    techo_vals = [v.strip() for v in m2.group(1).split(",")]
    techo_new = float(techo_vals[new_idx]) if new_idx < len(techo_vals) else None
else:
    techo_new = None

if not techo_new:
    print(f"WARN: no se encontró hT[{new_idx}]. Ingresá el techo manualmente.")
    sys.exit(1)

print(f"Techo {fecha_lbl}: ${techo_new:,.2f}")

# ── 4. Calcular métricas ───────────────────────────────────────────────────
brecha_new = round((techo_new - siopel_new) / siopel_new * 100, 2)
print(f"Brecha: {brecha_new}%")

# Obtener valores previos
m3 = re.search(r"var hS=\[(.+?)\];", html, re.DOTALL)
hs_parts = [v.strip() for v in m3.group(1).split(",")]
prev_siopel = float(hs_parts[prev_idx]) if hs_parts[prev_idx] != "null" else None

prev_brecha = None
if prev_siopel:
    prev_techo = float(techo_vals[prev_idx])
    prev_brecha = round((prev_techo - prev_siopel) / prev_siopel * 100, 2)

delta_s = round(siopel_new - prev_siopel, 1) if prev_siopel else None
delta_pct = round(delta_s / prev_siopel * 100, 2) if prev_siopel else None
delta_b = round(brecha_new - prev_brecha, 2) if prev_brecha else None

hA_new = round(techo_new / 1.152, 0)   # usando rolling ~15.2%
prev_lbl = re.search(r"prevLbl='([^']+)'", html)
prev_lbl = prev_lbl.group(1) if prev_lbl else fecha_lbl

# ── 5. Aplicar cambios al HTML ─────────────────────────────────────────────
print("\nActualizando HTML...")

def safe_replace(html, old, new, label):
    if old in html:
        html = html.replace(old, new, 1)
        print(f"  ✓ {label}")
    else:
        print(f"  ✗ {label} — patrón no encontrado: {repr(old[:60])}")
    return html

# 5a. hS[new_idx]
old_hs = re.search(r"var hS=\[(.+?)\];", html, re.DOTALL).group(0)
parts = old_hs[7:-1].split(",")   # strip "var hS=[" and "];"
if parts[new_idx].strip() == "null":
    parts[new_idx] = str(siopel_new)
    html = html.replace(old_hs, "var hS=[" + ",".join(parts) + "];", 1)
    print(f"  ✓ hS[{new_idx}] = {siopel_new}")
else:
    print(f"  ✗ hS[{new_idx}] ya tiene valor: {parts[new_idx]} (¿ya actualizado?)")
    sys.exit(0)

# 5b. hPt: mover dot grande
html = html.replace(f"hPt[{prev_idx}]=7;", f"hPt[{prev_idx}]=3; hPt[{new_idx}]=7;")
print(f"  ✓ hPt: [{prev_idx}]=3, [{new_idx}]=7")

# 5c. brechaVals + hA + avgRef
html = html.replace(
    f"brechaVals[{prev_idx}]={prev_brecha};",
    f"brechaVals[{prev_idx}]={prev_brecha};\n  brechaVals[{new_idx}]={brecha_new};"
)
html = html.replace(
    f"hA[{prev_idx}]={int(round(techo_vals[prev_idx] if isinstance(techo_vals[prev_idx], float) else float(techo_vals[prev_idx]), 0) / 1.152)};",
    f"hA[{prev_idx}]={int(round(float(techo_vals[prev_idx]) / 1.152))};\n  hA[{new_idx}]={int(hA_new)};\n  avgRef[{new_idx}]=15.2;"
) if False else html  # handled separately below

# Simpler hA/avgRef update
old_ha_line = f"hA[{prev_idx}]="
ha_line_end = html.find(";", html.find(old_ha_line)) if old_ha_line in html else -1
if ha_line_end > 0:
    ha_old_full = html[html.find(old_ha_line):ha_line_end+1]
    html = html.replace(ha_old_full,
        ha_old_full + f"\n  hA[{new_idx}]={int(hA_new)};\n  avgRef[{new_idx}]=15.2;", 1)
    print(f"  ✓ hA[{new_idx}]={int(hA_new)}, avgRef[{new_idx}]=15.2")

# 5d. Zone ia (hist and proj)
new_ia_proj = ia_proj + 1
html = html.replace(
    f"var ia=mode==='proj'?{ia_proj}:{ia_hist}",
    f"var ia=mode==='proj'?{new_ia_proj}:{new_idx}"
)
print(f"  ✓ zone ia: hist={new_idx}, proj={new_ia_proj}")

# 5e. Zone label (fecha)
prev_date_lbl = prev_lbl.replace("-JUN", "").replace("-JUL", "")
html = html.replace(f"'{prev_idx}-JUN ←'", f"'{new_idx}-JUN ←'")  # try numeric
html = html.replace(
    f"'{fecha.strftime('%-d').lstrip('0')}-JUN ←'",
    f"'{fecha.strftime('%-d').lstrip('0')}-JUN ←'"
)
# More reliable: replace by pattern
html = re.sub(r"'\d+-JUN ←'", f"'{new_idx}-JUN ←'", html, count=1)
print(f"  ✓ zone label → {new_idx}-JUN")

# 5f. sJunActual (proj mode)
m_sja = re.search(r"var sJunActual=\[([^\]]+)\]", html)
if m_sja:
    html = html.replace(m_sja.group(0),
        m_sja.group(0).rstrip("]") + f",{siopel_new}]")
    # adjust N count
    old_n = re.search(r"sJunActual, N\((\d+)\)", html)
    if old_n:
        html = html.replace(f"N({old_n.group(1)})",
            f"N({int(old_n.group(1)) - 1})", 1)
    print(f"  ✓ sJunActual += {siopel_new}")

# 5g. pPt: mover dot grande en modo proj
html = html.replace(f"pPt[{ia_proj}]=7;",
    f"pPt[{ia_proj}]=3; pPt[{new_ia_proj}]=7;")
print(f"  ✓ pPt: [{ia_proj}]=3, [{new_ia_proj}]=7")

# 5h. Cards
dia_str = fecha.strftime("%-d").lstrip("0")  # "16"
html = re.sub(
    r"SIOPEL \(\d+/\d+\)</div><div class=\"card-val\">[^<]+</div>",
    f"SIOPEL ({dia_str}/{fecha.month})</div>"
    f"<div class=\"card-val\">${siopel_new:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + "</div>",
    html, count=1
)
html = re.sub(
    r"TECHO BCRA</div><div class=\"card-val\">[^<]+</div>",
    f"TECHO BCRA</div><div class=\"card-val\">${techo_new:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + "</div>",
    html, count=1
)
html = re.sub(r">\+[\d.]+%<", f">+{brecha_new}%<", html, count=1)
print(f"  ✓ cards: SIOPEL={siopel_new}, Techo={techo_new}, Brecha={brecha_new}%")

# 5i. Stamp date
html = re.sub(
    r"<span>\d+ \w+ 2026</span>",
    f"<span>{fecha_stamp}</span>",
    html, count=1
)
print(f"  ✓ stamp: {fecha_stamp}")

# 5j. Descripción modo hist
html = re.sub(
    r"– \d+-[A-Z]+ 2026 vs techo banda BCRA",
    f"– {dia_str}-{fecha.strftime('%b').upper()} 2026 vs techo banda BCRA",
    html
)

# ── 6. Guardar y validar ────────────────────────────────────────────────────
with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(html)
print("\nHTML guardado.")

# Smoke test
print("\nEjecutando smoke test...")
result = subprocess.run(["node", SMOKE_TEST], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print("ERROR: smoke test falló. Revisar antes de commitear.")
    print(result.stderr)
    sys.exit(1)

print(f"""
══ RESUMEN ══════════════════════════════════════════════
  Fecha:    {fecha.strftime('%d/%m/%Y')}
  SIOPEL:   ${siopel_new:>10,.2f}
  Techo:    ${techo_new:>10,.2f}
  Brecha:   {brecha_new:>8.2f}%
  Δ SIOPEL: {f'+{delta_s} (+{delta_pct}%)' if delta_s else 'N/A'}
  Δ Brecha: {f'{delta_b:+.2f}pp' if delta_b else 'N/A'}
═══════════════════════════════════════════════════════
""")
