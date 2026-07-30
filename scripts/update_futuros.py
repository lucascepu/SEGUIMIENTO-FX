#!/usr/bin/env python3
"""
update_futuros.py — Actualiza FUT_DEFAULT en index.html con el cierre de ROFEX via API de IOL (invertirOnline).
Uso: python3 scripts/update_futuros.py [fecha YYYY-MM-DD]
Requiere: IOL_USER, IOL_PASS en env

Historial de fuentes probadas:
- MAE: no tiene datos de futuros DLR (devolvia [] siempre). Descartado.
- Primary/reMarkets: resulto ser un ambiente de simulacion/paper-trading, no datos reales. Descartado.
- IOL: cuenta real del usuario con API activada. En uso.

El endpoint exacto de cotizacion de futuros de IOL no esta 100% confirmado por documentacion
publica, asi que este script PRUEBA varias combinaciones de mercado/simbolo para un solo
contrato de referencia (DIC 26) y deja el detalle completo de cada intento en
scripts/futuros_debug.json. Con eso se ajusta el mercado/formato correcto en la siguiente
iteracion sin tener que adivinar a ciegas.

Deja SIEMPRE un registro en scripts/futuros_debug.json (exito o fallo).
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

IOL_URL = 'https://api.invertironline.com'
IOL_USER = os.environ.get('IOL_USER', '').strip()
IOL_PASS = os.environ.get('IOL_PASS', '').strip()

# Meses -> sufijo de simbolo de 2 digitos + año 2 digitos (varias convenciones posibles)
KEYS_ORDEN = ['JUL 26','AGO 26','SEP 26','OCT 26','NOV 26','DIC 26',
              'ENE 27','FEB 27','MAR 27','ABR 27','MAY 27','JUN 27']

# Simbolo de referencia para la sonda inicial (probamos formatos con DIC 26, el mas liquido)
PROBE_SYMBOLS = ['DLR/DIC26', 'DLR/DIC26M', 'DLRDIC26', 'DLR/DIC2026']
PROBE_MERCADOS = ['rofex', 'ROFX', 'matba', 'rOFX']

def get_token():
    data = urllib.parse.urlencode({
        'username': IOL_USER, 'password': IOL_PASS, 'grant_type': 'password'
    }).encode('utf-8')
    req = urllib.request.Request(
        f"{IOL_URL}/token", data=data, method='POST',
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read())
        token = body.get('access_token')
        if not token:
            raise RuntimeError(f'Sin access_token en la respuesta: {body}')
        return token

def try_get(url, token):
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace')[:300]
    except Exception as e:
        return None, str(e)

try:
    if len(sys.argv) >= 2 and sys.argv[1]:
        raw = sys.argv[1].replace("-","")
        fecha = datetime.date(int(raw[:4]),int(raw[4:6]),int(raw[6:]))
    else:
        fecha = (datetime.datetime.utcnow()-datetime.timedelta(hours=3)).date()
    fecha_iso = fecha.strftime("%Y-%m-%d")
    print(f"[futuros] Fecha: {fecha_iso}")

    if not IOL_USER or not IOL_PASS:
        fail("IOL_USER o IOL_PASS no definidas (variables de entorno vacias)")

    cred_diag = {'user_len': len(IOL_USER), 'pass_len': len(IOL_PASS)}
    try:
        token = get_token()
        print("[futuros] Login IOL OK")
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:500]
        fail(f"Login IOL fallo: HTTP {e.code}", http_status=e.code, response_body=body, cred_diag=cred_diag)
    except Exception as e:
        fail(f"Login IOL fallo: {e}", traceback=traceback.format_exc(), cred_diag=cred_diag)

    # ── Sondeo: probar combinaciones mercado/simbolo con un contrato de referencia ──
    intentos = []
    encontrado = None
    for mercado in PROBE_MERCADOS:
        for simbolo in PROBE_SYMBOLS:
            url = f"{IOL_URL}/api/v2/{mercado}/Titulos/{urllib.parse.quote(simbolo, safe='')}/Cotizacion"
            status, body = try_get(url, token)
            intentos.append({'mercado': mercado, 'simbolo': simbolo, 'url': url,
                              'status': status, 'body_preview': body[:300] if body else None})
            print(f"[futuros] probe mercado={mercado} simbolo={simbolo} -> {status}")
            if status == 200:
                try:
                    parsed = json.loads(body)
                    if parsed.get('ultimoPrecio') or parsed.get('precio'):
                        encontrado = {'mercado': mercado, 'simbolo_formato': simbolo, 'respuesta': parsed}
                        break
                except Exception:
                    pass
        if encontrado:
            break

    if not encontrado:
        fail("Ningun formato de mercado/simbolo probado devolvio una cotizacion valida. "
             "Revisar 'intentos' para ver los status/respuestas de IOL y ajustar el formato.",
             intentos=intentos)

    print(f"[futuros] Formato encontrado: mercado={encontrado['mercado']}, simbolo={encontrado['simbolo_formato']}")
    print(f"[futuros] Respuesta ejemplo: {encontrado['respuesta']}")

    # Con el formato ya identificado, guardamos el diagnostico completo para construir
    # el resto de los 12 contratos en la proxima iteracion del script.
    write_debug('probe_ok', fecha=fecha_iso, encontrado=encontrado, intentos=intentos, cred_diag=cred_diag)
    print("[futuros] Sonda exitosa. Revisar futuros_debug.json y confirmar formato antes de traer los 12 contratos.")

except SystemExit:
    raise
except Exception as e:
    fail(f"Excepcion no manejada: {e}", traceback=traceback.format_exc())
