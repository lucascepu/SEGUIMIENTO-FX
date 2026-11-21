#!/usr/bin/env python3
"""
audit_calendario.py -- Auditoria de feriados y cotizaciones de dias habiles de index.html.

Controles (ERROR = sale con codigo 1 y el workflow avisa por mail de GitHub):
  1. Dia habil (lun-vie, no feriado segun data/feriados-ar.json) AUSENTE del calendario hDates:
     se consulta MAE; si MAE tiene UST$T ese dia -> ERROR (rueda real fuera del calendario).
  2. Feriado que SI esta en el calendario: si MAE tiene dato ese dia -> ERROR (feriado mal cargado);
     si hS tiene valor y MAE no -> ERROR (cotizacion cargada en un dia sin mercado).
  3. Dia del calendario ya pasado (< hoy AR) con hS vacio -> ERROR (cotizacion faltante).
  4. MEP/CCL: dia con SIOPEL en los ultimos 15 dias habiles sin fila en hDatesMC -> ERROR; mas antiguos -> aviso.
  5. El calendario de feriados no cubre el anio en curso/siguiente, o el calendario hDates termina pronto -> AVISO.
Uso: python3 scripts/audit_calendario.py [--sin-mae]   (MAE_API_KEY en el entorno para verificar contra MAE)
"""
import re, sys, os, json, datetime as D, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
html = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
fer = json.load(open(os.path.join(ROOT, 'data', 'feriados-ar.json'), encoding='utf-8'))
FER = fer['feriados']
SIN_MAE = '--sin-mae' in sys.argv
KEY = os.environ.get('MAE_API_KEY')

def arr(name):
    m = re.search(r'var\s+' + name + r'\s*=\s*\[(.*?)\];', html, re.S)
    return [x.strip().strip("'\"") for x in m.group(1).split(',')]

hDates, hS = arr('hDates'), arr('hS')
dmc, mep, ccl = arr('hDatesMC'), arr('hMEP'), arr('hCCL')
try:
    from zoneinfo import ZoneInfo
    hoy = D.datetime.now(ZoneInfo('America/Argentina/Buenos_Aires')).date()
except Exception:
    hoy = (D.datetime.utcnow() - D.timedelta(hours=3)).date()

errores, avisos = [], []
cache = {}
def mae_tiene_dato(iso):
    """True/False si MAE informa UST$T ese dia; None si no se pudo consultar."""
    if SIN_MAE or not KEY: return None
    if iso in cache: return cache[iso]
    try:
        q = urllib.parse.quote(json.dumps({"fechaDesde": iso, "fechaHasta": iso}))
        req = urllib.request.Request(
            'https://api.marketdata.mae.com.ar/api/mercado/titulo/historicoforex?oTitulo=' + q,
            headers={'x-api-key': KEY, 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        ok = any(d.get('ticker') == 'UST$T' and d.get('precioCierre') for dia in (data if isinstance(data, list) else []) for d in dia.get('details', []))
    except Exception as e:
        print(f"  [aviso] no se pudo consultar MAE para {iso}: {e}")
        ok = None
    cache[iso] = ok
    return ok

# 5. cobertura
for y in (hoy.year, hoy.year + 1):
    if y not in fer['anios_cubiertos'] and (y == hoy.year or hoy.month >= 10):
        avisos.append(f"data/feriados-ar.json no cubre {y}: cargar el calendario oficial")
if D.date.fromisoformat(hDates[-1]) < hoy + D.timedelta(days=45):
    avisos.append(f"el calendario hDates termina el {hDates[-1]}: extenderlo antes de fin de anio")

ds = set(hDates)
a, b = D.date.fromisoformat(hDates[0]), min(D.date.fromisoformat(hDates[-1]), hoy - D.timedelta(days=1))
x = a
while x <= b:
    i = x.isoformat()
    if x.weekday() < 5:
        if i not in ds and i not in FER:
            m = mae_tiene_dato(i)
            if m is True:
                errores.append(f"{i}: dia habil con dato en MAE y FUERA del calendario hDates")
            elif m is None:
                avisos.append(f"{i}: dia habil fuera del calendario (no verificado contra MAE)")
            else:
                avisos.append(f"{i}: dia habil fuera del calendario y MAE no tiene dato (probable asueto no listado; confirmar y agregar a feriados-ar.json)")
        if i in ds and i in FER:
            idx = hDates.index(i)
            m = mae_tiene_dato(i)
            if m is True:
                errores.append(f"{i}: figura como feriado ({FER[i]}) pero MAE tiene dato -> sacarlo de feriados-ar.json y cargar la rueda")
            elif hS[idx] != 'null' and m is False:
                errores.append(f"{i}: feriado ({FER[i]}) con cotizacion cargada (hS={hS[idx]}) y MAE sin dato -> borrar")
            elif hS[idx] != 'null':
                avisos.append(f"{i}: feriado ({FER[i]}) dentro del calendario con cotizacion hS={hS[idx]} (no verificado contra MAE)")
    x += D.timedelta(1)

# 3. cotizaciones faltantes en dias del calendario ya pasados
for i, d in enumerate(hDates):
    if D.date.fromisoformat(d) < hoy and hS[i] == 'null':
        errores.append(f"{d}: rueda del calendario sin cotizacion SIOPEL cargada")

# 4. MEP/CCL
sdm = set(dmc)
cargados = [d for i, d in enumerate(hDates) if hS[i] != 'null' and d >= dmc[0]]
faltan = [d for d in cargados if d not in sdm]
recientes = cargados[-15:]
for d in faltan:
    (errores if d in recientes else avisos).append(f"{d}: tiene SIOPEL pero no MEP/CCL en hDatesMC")
for i, d in enumerate(dmc):
    if mep[i] in ('null', '') or ccl[i] in ('null', ''):
        avisos.append(f"{d}: MEP o CCL vacio")

print(f"Auditoria al {hoy} | calendario {hDates[0]}..{hDates[-1]} ({len(hDates)} ruedas) | MEP/CCL {len(dmc)} dias | MAE: {'no' if (SIN_MAE or not KEY) else 'si'}")
for t, l in (("AVISO", avisos), ("ERROR", errores)):
    for m in l: print(f"  [{t}] {m}")
print(f"Resultado: {len(errores)} error(es), {len(avisos)} aviso(s)")
sys.exit(1 if errores else 0)
