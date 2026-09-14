#!/usr/bin/env python3
"""
auto_update_fx.py — Obtiene el TC y actualiza index.html
Uso:
  python3 scripts/auto_update_fx.py [fecha] [--source criptoya|mae] [--force]

--source criptoya : usa criptoya.com (default)
--source mae      : usa API MAE (requiere MAE_API_KEY)
--force           : sobreescribe aunque ya haya valor hoy
"""
import sys, os, json, datetime, urllib.request, urllib.parse, subprocess

# ── Parsear args ─────────────────────────────────────────────────────────────
args = sys.argv[1:]
FORCE  = '--force' in args;  args = [a for a in args if a != '--force']
source = 'criptoya'
if '--source' in args:
    idx = args.index('--source')
    source = args[idx+1]
    args = args[:idx] + args[idx+2:]

fecha_arg = args[0] if args else None

if fecha_arg:
    raw = fecha_arg.replace("-", "")
    fecha = datetime.date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
else:
    fecha = (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).date()

fecha_iso = fecha.strftime("%Y-%m-%d")
print(f"[auto_update_fx] Fecha: {fecha_iso}, fuente: {source}, force: {FORCE}")

# ── Obtener precio ────────────────────────────────────────────────────────────
if source == 'mae':
    api_key = os.environ.get("MAE_API_KEY", "")
    if not api_key:
        print("ERROR: MAE_API_KEY no definida")
        sys.exit(1)
    payload = json.dumps({"fechaDesde": fecha_iso, "fechaHasta": fecha_iso})
    url = ("https://api.marketdata.mae.com.ar/api/mercado/titulo/historicoforex"
           "?oTitulo=" + urllib.parse.quote(payload))
    print(f"[auto_update_fx] Llamando API MAE...")
    try:
        req = urllib.request.Request(url, headers={"x-api-key": api_key})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"ERROR MAE: {e}"); sys.exit(1)
    siopel = None
    for dia in data:
        for det in dia.get("details", []):
            if det.get("ticker")=="UST$T" and det.get("codigoSegmento")=="M" and det.get("plazo")=="000":
                siopel = round(float(det.get("precioCierre")), 2); break
        if siopel: break
    if not siopel:
        print("ERROR: UST$T no encontrado en MAE"); sys.exit(1)
    print(f"[auto_update_fx] TC MAE: {siopel}")
    mep_val = None; ccl_val = None  # MAE no trae MEP/CCL, se omiten en este camino

else:  # criptoya
    print(f"[auto_update_fx] Llamando criptoya...")
    try:
        req = urllib.request.Request(
            'https://criptoya.com/api/dolar',
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"ERROR criptoya: {e}"); sys.exit(1)
    m = data.get("mayorista")
    if not m:
        print("ERROR: campo mayorista no encontrado"); sys.exit(1)
    siopel = round(float(m["price"] if isinstance(m, dict) else m), 2)
    print(f"[auto_update_fx] TC criptoya: {siopel}")

    # MEP/CCL en criptoya NO son un precio simple como mayorista -- vienen anidados
    # por bono (al30, gd30, letras, bpo27) y plazo de liquidacion (ci, 24hs), cada uno
    # con su propio price/variation/timestamp. AL30 es el bono mas liquido (los demas
    # suelen tener timestamps viejos, de semanas atras, cuando no operan). Se usa
    # AL30+CI como referencia (mismo criterio que el mercado usa habitualmente para
    # "el" MEP/CCL), con 24hs como respaldo si CI no estuviera disponible.
    def extract_bond_price(obj):
        if not isinstance(obj, dict): return None
        for bond in ("al30", "gd30"):
            b = obj.get(bond)
            if not isinstance(b, dict): continue
            for term in ("ci", "24hs"):
                t = b.get(term)
                if isinstance(t, dict) and t.get("price"):
                    return round(float(t["price"]), 2)
        return None

    mep_val = None; ccl_val = None
    try:
        mep_val = extract_bond_price(data.get("mep"))
        ccl_val = extract_bond_price(data.get("ccl"))
        print(f"[auto_update_fx] MEP criptoya (AL30/CI): {mep_val}, CCL criptoya (AL30/CI): {ccl_val}")
    except Exception as e:
        print(f"[auto_update_fx] AVISO: no se pudo leer MEP/CCL ({e}), se omiten hoy")

# ── Validar ───────────────────────────────────────────────────────────────────
if not (1000 < siopel < 5000):
    print(f"ERROR: valor {siopel} fuera de rango"); sys.exit(1)

# ── Ejecutar update ───────────────────────────────────────────────────────────
cmd = [sys.executable, "update_fx_diario.py", str(siopel), fecha_iso]
if mep_val is not None and ccl_val is not None:
    cmd += ["--mep", str(mep_val), "--ccl", str(ccl_val)]
if FORCE:
    cmd.append('--force')
print(f"[auto_update_fx] Ejecutando: {' '.join(cmd)}")
result = subprocess.run(cmd)
sys.exit(result.returncode)
