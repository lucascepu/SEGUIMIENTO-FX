#!/usr/bin/env python3
"""
update_futuros.py — Actualiza FUT_DEFAULT en index.html con los cierres de MAE
Uso: python3 scripts/update_futuros.py [fecha YYYY-MM-DD]
Requiere: MAE_API_KEY en env

Deja SIEMPRE un registro en scripts/futuros_debug.json (exito o fallo),
para poder diagnosticar sin depender de los logs de Actions.
"""
import sys, os, re, json, datetime, urllib.request, urllib.parse, traceback

DEBUG_FILE = os.path.join(os.path.dirname(__file__), 'futuros_debug.json')

def write_debug(status, **kwargs):
    payload = {
        'timestamp_utc': datetime.datetime.utcnow().isoformat() + 'Z',
        'status': status,
        **kwargs
    }
    with open(DEBUG_FILE, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[futuros] debug -> {DEBUG_FILE}: {status}")

def fail(msg, **extra):
    print(f"ERROR: {msg}")
    write_debug('error', error=msg, **extra)
    sys.exit(1)

# Mapeo posicion MAE -> key de FUT_DEFAULT
MESES = {
    '01':'ENE','02':'FEB','03':'MAR','04':'ABR','05':'MAY','06':'JUN',
    '07':'JUL','08':'AGO','09':'SEP','10':'OCT','11':'NOV','12':'DIC'
}
KEYS_ORDEN = ['JUL 26','AGO 26','SEP 26','OCT 26','NOV 26','DIC 26',
              'ENE 27','FEB 27','MAR 27','ABR 27','MAY 27','JUN 27']

def posicion_to_key(pos):
    """DLR072026 -> 'JUL 26'"""
    if not pos.startswith('DLR') or len(pos) < 9:
        return None
    mm = pos[3:5]
    yy = pos[7:9]
    mes = MESES.get(mm)
    if not mes: return None
    return f"{mes} {yy}"

try:
    # Fecha
    if len(sys.argv) >= 2 and sys.argv[1]:
        raw = sys.argv[1].replace("-","")
        fecha = datetime.date(int(raw[:4]),int(raw[4:6]),int(raw[6:]))
    else:
        fecha = (datetime.datetime.utcnow()-datetime.timedelta(hours=3)).date()
    fecha_iso = fecha.strftime("%Y-%m-%d")
    print(f"[futuros] Fecha: {fecha_iso}")

    # Llamar API MAE
    api_key = os.environ.get("MAE_API_KEY","")
    if not api_key:
        fail("MAE_API_KEY no definida (variable de entorno vacia)")

    payload = json.dumps({"fechaDesde": fecha_iso, "fechaHasta": fecha_iso, "contratosSinVolumen": False})
    url = "https://api.marketdata.mae.com.ar/api/cem/monedas/fut?oData=" + urllib.parse.quote(payload)
    print(f"[futuros] Llamando API MAE futuros... url={url}")

    http_status = None
    raw_body = None
    data = None
    try:
        req = urllib.request.Request(url, headers={"x-api-key": api_key})
        with urllib.request.urlopen(req, timeout=15) as resp:
            http_status = resp.status
            raw_body = resp.read().decode('utf-8', errors='replace')
            data = json.loads(raw_body)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:500]
        fail(f"HTTPError {e.code}: {e.reason}", http_status=e.code, response_body=body, url=url)
    except urllib.error.URLError as e:
        fail(f"URLError: {e.reason}", url=url)
    except Exception as e:
        fail(f"Excepcion llamando MAE: {e}", traceback=traceback.format_exc(), url=url)

    # Extraer precios de ajuste por contrato
    nuevos = {}
    for item in data if isinstance(data, list) else []:
        key = posicion_to_key(item.get("posicion",""))
        if key and item.get("precioAjuste"):
            nuevos[key] = round(float(item["precioAjuste"]), 2)

    if not nuevos:
        fail("No se encontraron contratos DLR en la respuesta de MAE",
             http_status=http_status,
             response_preview=(raw_body[:1000] if raw_body else None),
             response_type=str(type(data)))

    print(f"[futuros] Contratos obtenidos: {nuevos}")

    # Actualizar index.html
    HTML = 'index.html'
    content = open(HTML, encoding='utf-8').read()

    m = re.search(r'var FUT_DEFAULT = \{([^}]+)\};', content)
    if not m:
        fail("Patron FUT_DEFAULT no encontrado en index.html")

    old_str = m.group(0)
    old_inner = m.group(1)

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

    # Actualizar fecha de cierre ROFEX (todas las apariciones del texto viejo)
    old_fecha = re.search(r'Cierre ROFEX (\d+/\d+/\d+)', content)
    if old_fecha:
        dia = fecha.day; mes = fecha.month; anio = fecha.year
        content = content.replace(f"Cierre ROFEX {old_fecha.group(1)}", f"Cierre ROFEX {dia}/{mes}/{anio}")
        print(f"[futuros] Fecha ROFEX actualizada: {dia}/{mes}/{anio}")

    # Actualizar version para limpiar localStorage
    content = re.sub(r"var ROFEX_VERSION = '[^']+';", f"var ROFEX_VERSION = '{fecha_iso.replace('-','')}';", content)

    open(HTML, 'w', encoding='utf-8').write(content)
    print(f"[futuros] OK index.html actualizado con {len(nuevos)} contratos")

    # Agregar fila al historico (futurosHistorico.json)
    HIST = 'futurosHistorico.json'
    hist_updated = False
    if os.path.exists(HIST):
        hist = json.load(open(HIST, encoding='utf-8'))
        if fecha_iso not in hist.get('dates', []):
            hist['dates'].append(fecha_iso)
            for k in KEYS_ORDEN:
                hist.setdefault(k, []).append(nuevos.get(k))
            json.dump(hist, open(HIST, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',',':'))
            hist_updated = True
            print(f"[futuros] {HIST} actualizado: fila {fecha_iso} agregada")
        else:
            print(f"[futuros] {HIST}: {fecha_iso} ya existia, no se duplica")
    else:
        print(f"[futuros] AVISO: {HIST} no encontrado, no se pudo actualizar el historico")

    write_debug('ok', fecha=fecha_iso, contratos=nuevos, http_status=http_status, historico_actualizado=hist_updated)

except SystemExit:
    raise
except Exception as e:
    fail(f"Excepcion no manejada: {e}", traceback=traceback.format_exc())
