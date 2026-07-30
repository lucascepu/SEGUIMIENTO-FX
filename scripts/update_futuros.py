#!/usr/bin/env python3
"""
update_futuros.py — Actualiza FUT_DEFAULT en index.html con el cierre de ROFEX via Primary API.
Uso: python3 scripts/update_futuros.py [fecha YYYY-MM-DD]
Requiere: PRIMARY_USER, PRIMARY_PASS en env

Nota: se abandono MAE (Mercado Abierto Electronico) como fuente porque los futuros DLR
no cotizan ahi -- cotizan en ROFEX/Matba-Rofex, que es lo que Primary provee. MAE devolvia
siempre una lista vacia (200 OK, [] contratos), por eso nunca actualizaba nada.

Deja SIEMPRE un registro en scripts/futuros_debug.json (exito o fallo),
para poder diagnosticar sin depender de los logs de Actions.
"""
import sys, os, re, json, datetime, urllib.request, urllib.error, urllib.parse, traceback

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

PRIMARY_URL = os.environ.get('PRIMARY_URL', 'https://api.primary.com.ar')
PRIMARY_USER = os.environ.get('PRIMARY_USER', '')
PRIMARY_PASS = os.environ.get('PRIMARY_PASS', '')

CONTRACTS = ['DLR/JUL26M','DLR/AGO26M','DLR/SEP26M','DLR/OCT26M',
             'DLR/NOV26M','DLR/DIC26M','DLR/ENE27M','DLR/FEB27M',
             'DLR/MAR27M','DLR/ABR27M','DLR/MAY27M','DLR/JUN27M']

TICKER_TO_KEY = {
    'DLR/JUL26M':'JUL 26','DLR/AGO26M':'AGO 26','DLR/SEP26M':'SEP 26',
    'DLR/OCT26M':'OCT 26','DLR/NOV26M':'NOV 26','DLR/DIC26M':'DIC 26',
    'DLR/ENE27M':'ENE 27','DLR/FEB27M':'FEB 27','DLR/MAR27M':'MAR 27',
    'DLR/ABR27M':'ABR 27','DLR/MAY27M':'MAY 27','DLR/JUN27M':'JUN 27'
}

KEYS_ORDEN = ['JUL 26','AGO 26','SEP 26','OCT 26','NOV 26','DIC 26',
              'ENE 27','FEB 27','MAR 27','ABR 27','MAY 27','JUN 27']

def get_token():
    req = urllib.request.Request(
        f"{PRIMARY_URL}/auth/getToken", method='POST',
        headers={'X-Username': PRIMARY_USER, 'X-Password': PRIMARY_PASS}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        token = resp.headers.get('X-Auth-Token')
        if not token:
            raise RuntimeError('Sin X-Auth-Token en la respuesta')
        return token

def get_market_data(token, ticker):
    url = f"{PRIMARY_URL}/rest/marketdata/get?marketId=ROFX&symbol={urllib.parse.quote(ticker)}&entries=LA,CL,SE"
    req = urllib.request.Request(url, headers={'X-Auth-Token': token})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

try:
    if len(sys.argv) >= 2 and sys.argv[1]:
        raw = sys.argv[1].replace("-","")
        fecha = datetime.date(int(raw[:4]),int(raw[4:6]),int(raw[6:]))
    else:
        fecha = (datetime.datetime.utcnow()-datetime.timedelta(hours=3)).date()
    fecha_iso = fecha.strftime("%Y-%m-%d")
    print(f"[futuros] Fecha: {fecha_iso}")

    if not PRIMARY_USER or not PRIMARY_PASS:
        fail("PRIMARY_USER o PRIMARY_PASS no definidas (variables de entorno vacias)")

    try:
        token = get_token()
        print("[futuros] Login Primary OK")
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:300]
        fail(f"Login Primary fallo: HTTP {e.code}", http_status=e.code, response_body=body)
    except Exception as e:
        fail(f"Login Primary fallo: {e}", traceback=traceback.format_exc())

    nuevos = {}
    detalles = {}
    for ticker in CONTRACTS:
        key = TICKER_TO_KEY[ticker]
        try:
            data = get_market_data(token, ticker)
        except Exception as e:
            detalles[key] = f"error consultando: {e}"
            continue
        if not data or data.get('status') != 'OK' or not data.get('marketData'):
            detalles[key] = f"sin marketData (status={data.get('status') if data else None})"
            continue
        md = data['marketData']
        # Para el cierre oficial del dia priorizamos SE (settlement) por sobre LA (ultimo operado)
        precio = None
        for campo in ('SE','LA','CL'):
            entry = md.get(campo)
            if entry and entry.get('price') and entry['price'] > 0:
                precio = round(float(entry['price']), 2)
                detalles[key] = f"{campo}={precio}"
                break
        if precio:
            nuevos[key] = precio
        else:
            detalles[key] = "sin precio valido en SE/LA/CL"

    print(f"[futuros] Contratos obtenidos: {nuevos}")
    print(f"[futuros] Detalle por contrato: {detalles}")

    if not nuevos:
        fail("No se pudo obtener precio para ningun contrato", detalles=detalles)

    if len(nuevos) < len(CONTRACTS):
        faltantes = [k for k in TICKER_TO_KEY.values() if k not in nuevos]
        print(f"[futuros] AVISO: faltan {faltantes} (se actualiza solo lo que se pudo obtener)")

    # Actualizar index.html
    HTML = 'index.html'
    content = open(HTML, encoding='utf-8').read()

    m = re.search(r'var FUT_DEFAULT = \{([^}]+)\};', content)
    if not m:
        fail("Patron FUT_DEFAULT no encontrado en index.html", detalles=detalles)

    old_str = m.group(0)
    old_inner = m.group(1)

    def parse_fut_dict(s):
        return dict(re.findall(r"'([^']+)':([\d.]+)", s))

    actual = parse_fut_dict(old_inner)
    for k, v in nuevos.items():
        if k in actual:
            actual[k] = str(v)

    new_inner = ','.join(f"'{k}':{v}" for k, v in actual.items())
    new_str = f"var FUT_DEFAULT = {{{new_inner}}};"

    n = content.count(old_str)
    print(f"[futuros] FUT_DEFAULT: {n} ocurrencias")
    content = content.replace(old_str, new_str)

    old_fecha = re.search(r'Cierre ROFEX (\d+/\d+/\d+)', content)
    if old_fecha:
        dia = fecha.day; mes = fecha.month; anio = fecha.year
        content = content.replace(f"Cierre ROFEX {old_fecha.group(1)}", f"Cierre ROFEX {dia}/{mes}/{anio}")
        print(f"[futuros] Fecha ROFEX actualizada: {dia}/{mes}/{anio}")

    content = re.sub(r"var ROFEX_VERSION = '[^']+';", f"var ROFEX_VERSION = '{fecha_iso.replace('-','')}';", content)

    open(HTML, 'w', encoding='utf-8').write(content)
    print(f"[futuros] OK index.html actualizado con {len(nuevos)} contratos")

    # Agregar o actualizar la fila del dia en el historico (upsert: puede correr 2 veces por dia)
    HIST = 'futurosHistorico.json'
    hist_updated = False
    if os.path.exists(HIST):
        hist = json.load(open(HIST, encoding='utf-8'))
        dates = hist.get('dates', [])
        if fecha_iso in dates:
            idx = dates.index(fecha_iso)
            for k in KEYS_ORDEN:
                if k in nuevos:
                    hist.setdefault(k, [None]*len(dates))[idx] = nuevos[k]
            print(f"[futuros] {HIST}: fila {fecha_iso} actualizada (ya existia)")
        else:
            hist['dates'].append(fecha_iso)
            for k in KEYS_ORDEN:
                hist.setdefault(k, []).append(nuevos.get(k))
            print(f"[futuros] {HIST} actualizado: fila {fecha_iso} agregada")
        json.dump(hist, open(HIST, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
        hist_updated = True
    else:
        print(f"[futuros] AVISO: {HIST} no encontrado")

    write_debug('ok', fecha=fecha_iso, contratos=nuevos, detalles=detalles, historico_actualizado=hist_updated)

except SystemExit:
    raise
except Exception as e:
    fail(f"Excepcion no manejada: {e}", traceback=traceback.format_exc())
