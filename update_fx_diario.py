#!/usr/bin/env python3
"""
update_fx_diario.py — Actualización diaria del SIOPEL en index.html
Uso: python3 update_fx_diario.py <valor> [fecha YYYY-MM-DD]

Ejemplo: python3 update_fx_diario.py 1482.0
         python3 update_fx_diario.py 1482.0 2026-07-14

Verifica todo antes de escribir y muestra un resumen de todos los cambios.
"""

import sys, re, datetime

HTML = 'index.html'
if len(sys.argv) < 2:
    print("Uso: python3 update_fx_diario.py <valor_siopel> [fecha YYYY-MM-DD]")
    sys.exit(1)

NUEVO_SIOPEL = round(float(sys.argv[1]), 2)
if len(sys.argv) >= 3:
    raw = sys.argv[2].strip()
    # Aceptar tanto YYYY-MM-DD como YYYYMMDD
    if len(raw) == 8 and '-' not in raw:
        raw = f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    HOY = raw
    datetime.datetime.strptime(HOY, "%Y-%m-%d")  # validar formato
else:
    HOY = datetime.date.today().isoformat()

content = open(HTML, encoding='utf-8').read()

# ── Extraer arrays principales ──────────────────────────────────────────────
def get_arr_str(name):
    m = re.search(r'var\s+'+name+r'\s*=\s*\[(.*?)\];', content, re.S)
    return m.group(1), m.start(1), m.end(1)

hDates_str, _, _ = get_arr_str('hDates')
hT_str, _, _     = get_arr_str('hT')
hS_str, hS_s, hS_e = get_arr_str('hS')

hDates = [x.strip().strip("'") for x in hDates_str.split(',')]
hT     = [None if x.strip()=='null' else float(x.strip()) for x in hT_str.split(',')]
hS     = [None if x.strip()=='null' else float(x.strip()) for x in hS_str.split(',')]

# ── Encontrar índice de hoy ─────────────────────────────────────────────────
if HOY not in hDates:
    print(f"ERROR: {HOY} no está en hDates (¿feriado o fuera del rango?)")
    sys.exit(1)

NEW_IDX = hDates.index(HOY)
LRI_PREV = max(i for i,v in enumerate(hS) if v is not None)
LRI_NEW  = NEW_IDX

if LRI_NEW != LRI_PREV + 1:
    print(f"ADVERTENCIA: idx hoy={LRI_NEW}, lri anterior={LRI_PREV} (diferencia={LRI_NEW-LRI_PREV})")
    print("¿Faltó alguna rueda intermedia? Verificar manualmente.")

if hS[LRI_NEW] is not None:
    print(f"ADVERTENCIA: hS[{LRI_NEW}]={hS[LRI_NEW]} ya tiene valor. ¿Ya se actualizó hoy?")
    sys.exit(1)

TECHO_HOY = hT[LRI_NEW]
SIOPEL_ANT = hS[LRI_PREV]
DELTA = NUEVO_SIOPEL - SIOPEL_ANT
DELTA_PCT = DELTA / SIOPEL_ANT * 100
BRECHA = (TECHO_HOY - NUEVO_SIOPEL) / NUEVO_SIOPEL * 100

print(f"── Resumen ─────────────────────────────")
print(f"  Fecha:    {HOY} (idx {LRI_NEW})")
print(f"  SIOPEL:   {SIOPEL_ANT} → {NUEVO_SIOPEL} ({DELTA:+.2f}, {DELTA_PCT:+.2f}%)")
print(f"  Techo:    {TECHO_HOY}")
print(f"  Brecha:   {BRECHA:.2f}%")
print(f"  LRI:      {LRI_PREV} → {LRI_NEW}")

# ── Fecha formateada para el hero ────────────────────────────────────────────
HOY_DT = datetime.date.fromisoformat(HOY)
MESES = ['','Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
HOY_LABEL = f"{HOY_DT.day} {MESES[HOY_DT.month]} {HOY_DT.year}"
HOY_CHART = f"{HOY_DT.day}-{MESES[HOY_DT.month].upper()}"
SIOPEL_FMT = f"${NUEVO_SIOPEL:,.2f}".replace(',','X').replace('.',',').replace('X','.')
TECHO_FMT  = f"${TECHO_HOY:,.2f}".replace(',','X').replace('.',',').replace('X','.')
BRECHA_FMT = f"+{BRECHA:.2f}%" if BRECHA >= 0 else f"{BRECHA:.2f}%"

# ── Función de reemplazo seguro ──────────────────────────────────────────────
errors = []
def replace_one(old, new, label):
    global content
    n = content.count(old)
    if n == 0:
        errors.append(f"NO ENCONTRADO: {label}\n  buscando: {repr(old[:80])}")
        return
    if n > 1:
        errors.append(f"AMBIGUO ({n}x): {label}")
        return
    content = content.replace(old, new, 1)
    print(f"  ✓ {label}")

# ── 1. hS[LRI_NEW] ──────────────────────────────────────────────────────────
# Encontrar el string exacto en el array y reemplazar el primer null tras lri_prev
hS_vals = hS_str.split(',')
# encontrar posición del null en LRI_NEW dentro de la lista
# Buscar el valor del lri tal como aparece en el array hS (puede ser "1482.0", "1482", "1482.00", etc.)
# Usar regex para matchear cualquier representación numérica del valor
def find_prev_val_str():
    """Encuentra la representación exacta del valor hS[LRI_PREV] en el string del array."""
    target = hS[LRI_PREV]
    # Buscar en la cola del array hS el patrón: <número>,null
    tail_match = re.search(r'((?:\d+\.?\d*)),null(?:,null)+\]', hS_str)
    if tail_match:
        # Verificar que el número encontrado sea el valor esperado
        found = float(tail_match.group(1))
        if abs(found - target) < 0.01:
            return tail_match.group(1)
    # Fallback: buscar el número exacto en cualquier representación
    for fmt in [str(target), f"{target:.1f}", f"{target:.2f}", str(int(target))]:
        if f"{fmt},null" in hS_str:
            return fmt
    return None

prev_val_str = find_prev_val_str()
if prev_val_str is None:
    errors.append(f"NO ENCONTRADO: hS[{LRI_NEW}]={NUEVO_SIOPEL}\n  No pude localizar hS[{LRI_PREV}]={hS[LRI_PREV]} en el array")
else:
    replace_one(
        f"{prev_val_str},null",
        f"{prev_val_str},{NUEVO_SIOPEL:.2f}",
        f"hS[{LRI_NEW}]={NUEVO_SIOPEL:.2f}"
    )

# ── 2. sSiopelActual ────────────────────────────────────────────────────────────
m_sJun = re.search(r'var sSiopelActual=\[(.*?)\];', content)
if m_sJun:
    old_sJun = f"var sSiopelActual=[{m_sJun.group(1)}];"
    new_sJun = f"var sSiopelActual=[{m_sJun.group(1)},{NUEVO_SIOPEL:.2f}];"
    replace_one(old_sJun, new_sJun, "sSiopelActual append")

# ── 3. hPt ─────────────────────────────────────────────────────────────────
replace_one(f'hPt[{LRI_PREV}]=7', f'hPt[{LRI_NEW}]=7', f"hPt {LRI_PREV}→{LRI_NEW}")

# ── 4. pPt (proj: 3 + len(sSiopelActual)) ────────────────────────────────────
m_pPt = re.search(r'var pPt=N\(51\); pPt\[(\d+)\]=7;', content)
if m_pPt:
    old_pPt_idx = int(m_pPt.group(1))
    new_pPt_idx = old_pPt_idx + 1
    replace_one(f'pPt[{old_pPt_idx}]=7', f'pPt[{new_pPt_idx}]=7', f"pPt {old_pPt_idx}→{new_pPt_idx}")

# ── 5. ia (zona sombreada) ─────────────────────────────────────────────────
m_ia = re.search(r"var ia=mode==='proj'\?(\d+):(\d+), ib=ia;", content)
if m_ia:
    old_ia_proj, old_ia_hist = m_ia.group(1), m_ia.group(2)
    new_ia_proj = str(int(old_ia_proj) + 1)
    new_ia_hist = str(LRI_NEW)
    replace_one(
        f"var ia=mode==='proj'?{old_ia_proj}:{old_ia_hist}, ib=ia;",
        f"var ia=mode==='proj'?{new_ia_proj}:{new_ia_hist}, ib=ia;",
        f"ia hist {old_ia_hist}→{new_ia_hist}, proj {old_ia_proj}→{new_ia_proj}"
    )

# ── 6. Label chart ─────────────────────────────────────────────────────────
m_lbl = re.search(r"ctx\.fillText\('(\d+-\w+) ←'", content)
if m_lbl:
    replace_one(
        f"ctx.fillText('{m_lbl.group(1)} ←',xA-3,ca.top+13);",
        f"ctx.fillText('{HOY_CHART} ←',xA-3,ca.top+13);",
        f"label chart {m_lbl.group(1)}→{HOY_CHART}"
    )

# ── 7. Hero HTML ────────────────────────────────────────────────────────────
# siopelVal
m_hero = re.search(r'id="siopelVal">(\$[\d\.,]+)<', content)
if m_hero:
    replace_one(f'id="siopelVal">{m_hero.group(1)}<', f'id="siopelVal">{SIOPEL_FMT}<', "siopelVal")

# siopelDate
m_date = re.search(r'id="siopelDate">([^<]+)<', content)
if m_date:
    replace_one(f'id="siopelDate">{m_date.group(1)}<', f'id="siopelDate">{HOY_LABEL}<', "siopelDate")

# techoVal
m_techo = re.search(r'id="techoVal">(\$[\d\.,]+)<', content)
if m_techo:
    replace_one(f'id="techoVal">{m_techo.group(1)}<', f'id="techoVal">{TECHO_FMT}<', "techoVal")

# cardBrecha
m_brecha = re.search(r'id="cardBrecha">([^<]+)<', content)
if m_brecha:
    replace_one(f'id="cardBrecha">{m_brecha.group(1)}<', f'id="cardBrecha">{BRECHA_FMT}<', "cardBrecha")

# ── Errores ─────────────────────────────────────────────────────────────────
if errors:
    print("\n── ERRORES ─────────────────────────────")
    for e in errors: print(f"  ✗ {e}")
    print("\nAbortando sin escribir el archivo.")
    sys.exit(1)

# ── Escribir ────────────────────────────────────────────────────────────────
open(HTML, 'w', encoding='utf-8').write(content)
print(f"\n✓ index.html actualizado correctamente")
print(f"  Verificar: lri={LRI_NEW}, delta={DELTA:+.2f}, brecha={BRECHA:.2f}%")
