#!/usr/bin/env python3
"""
update_futuros.py — Actualiza FUT_DEFAULT en index.html con los cierres de MAE
Uso: python3 scripts/update_futuros.py [fecha YYYY-MM-DD]
Requiere: MAE_API_KEY en env
"""
import sys, os, re, json, datetime, urllib.request, urllib.parse

# Mapeo posición MAE → key de FUT_DEFAULT
MESES = {
    '01':'ENE','02':'FEB','03':'MAR','04':'ABR','05':'MAY','06':'JUN',
    '07':'JUL','08':'AGO','09':'SEP','10':'OCT','11':'NOV','12':'DIC'
}

def posicion_to_key(pos):
    """DLR072026 → 'JUL 26'"""
    if not pos.startswith('DLR') or len(pos) < 9:
        return None
    mm = pos[3:5]
    yy = pos[7:9]
    mes = MESES.get(mm)
    if not mes: return None
    return f"{mes} {yy}"

# Fecha
if len(sys.argv) >= 2:
    raw = sys.argv[1].replace("-","")
    fecha = datetime.date(int(raw[:4]),int(raw[4:6]),int(raw[6:]))
else:
    fecha = (datetime.datetime.utcnow()-datetime.timedelta(hours=3)).date()

fecha_iso = fecha.strftime("%Y-%m-%d")
print(f"[futuros] Fecha: {fecha_iso}")

# Llamar API MAE
api_key = os.environ.get("MAE_API_KEY","")
if not api_key:
    print("ERROR: MAE_API_KEY no definida"); sys.exit(1)

payload = json.dumps({"fechaDesde": fecha_iso, "fechaHasta": fecha_iso, "contratosSinVolumen": False})
url = "https://api.marketdata.mae.com.ar/api/cem/monedas/fut?oData=" + urllib.parse.quote(payload)
print(f"[futuros] Llamando API MAE futuros...")

try:
    req = urllib.request.Request(url, headers={"x-api-key": api_key})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
except Exception as e:
    print(f"ERROR: {e}"); sys.exit(1)

# Extraer precios de ajuste por contrato
nuevos = {}
for item in data:
    key = posicion_to_key(item.get("posicion",""))
    if key and item.get("precioAjuste"):
        nuevos[key] = round(float(item["precioAjuste"]), 2)

if not nuevos:
    print("ERROR: no se encontraron contratos DLR"); sys.exit(1)

print(f"[futuros] Contratos obtenidos: {nuevos}")

# Actualizar index.html
HTML = 'index.html'
content = open(HTML, encoding='utf-8').read()

# Buscar y actualizar FUT_DEFAULT
m = re.search(r'var FUT_DEFAULT = \{([^}]+)\};', content)
if not m:
    print("ERROR: FUT_DEFAULT no encontrado"); sys.exit(1)

# Parsear keys actuales y actualizar con los nuevos
old_str = m.group(0)
old_inner = m.group(1)

# Reconstruir manteniendo el orden y actualizando valores
def parse_fut_dict(s):
    return dict(re.findall(r"'([^']+)':([\d.]+)", s))

actual = parse_fut_dict(old_inner)
for k,v in nuevos.items():
    if k in actual:
        actual[k] = str(v)

new_inner = ','.join(f"'{k}':{v}" for k,v in actual.items())
new_str = f"var FUT_DEFAULT = {{{new_inner}}};"

n = content.count(old_str)
print(f"[futuros] FUT_DEFAULT: {n} ocurrencias")
content = content.replace(old_str, new_str)

# Actualizar fecha de cierre ROFEX
old_fecha = re.search(r'Cierre ROFEX (\d+/\d+/\d+)', content)
if old_fecha:
    dia = fecha.day; mes = fecha.month; anio = fecha.year
    content = content.replace(f"Cierre ROFEX {old_fecha.group(1)}", f"Cierre ROFEX {dia}/{mes}/{anio}")
    print(f"[futuros] Fecha ROFEX actualizada: {dia}/{mes}/{anio}")

# Actualizar versión para limpiar localStorage
import hashlib
nueva_version = fecha_iso.replace("-","")
content = re.sub(r"var ROFEX_VERSION = '[^']+';", f"var ROFEX_VERSION = '{nueva_version}';", content)

open(HTML, 'w', encoding='utf-8').write(content)
print(f"[futuros] ✓ index.html actualizado con {len(nuevos)} contratos")
