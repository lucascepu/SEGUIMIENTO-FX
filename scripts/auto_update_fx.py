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

def get_ambito_ref(indicador, fecha):
    """
    Trae la Referencia oficial de Ámbito Financiero (mercados.ambito.com) para
    una fecha puntual. indicador: 'dolarrava/mep' o 'dolarrava/cl'.
    Devuelve float o None si esa fecha todavía no fue publicada (Ámbito cierra
    y publica más tarde que el horario en que corre este workflow, así que
    algunos días esto va a dar None y cae al fallback de criptoya).
    """
    dmy = fecha.strftime("%d-%m-%Y")
    url = f"https://mercados.ambito.com/{indicador}/historico-general/{dmy}/{dmy}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            rows = json.loads(resp.read())
    except Exception as e:
        print(f"[auto_update_fx] AVISO: Ámbito ({indicador}) no respondió: {e}")
        return None
    for row in rows[1:]:  # rows[0] es el header ["Fecha","Referencia"]
        if len(row) >= 2 and row[0] == dmy:
            try:
                return round(float(row[1].replace('.', '').replace(',', '.')), 2)
            except (ValueError, AttributeError):
                return None
    return None  # Ámbito aún no publicó el cierre de esta fecha

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
    # con su propio price/variation/timestamp. AL30 es el bono mas liquido y siempre
    # se usa como base. GD30 solo se promedia con AL30 cuando su timestamp esta
    # fresco (a menos de 2hs del de AL30) -- si GD30 no opero hace dias/semanas
    # (timestamp viejo), promediarlo a ciegas ensuciaria el dato en vez de mejorarlo,
    # asi que en ese caso se usa unicamente AL30.
    def get_bond_quote(obj, bond, term):
        if not isinstance(obj, dict): return None
        b = obj.get(bond)
        if not isinstance(b, dict): return None
        t = b.get(term)
        if isinstance(t, dict) and t.get("price") and t.get("timestamp"):
            try:
                return (float(t["price"]), float(t["timestamp"]))
            except (TypeError, ValueError):
                return None
        return None

    def extract_bond_price(obj):
        al30 = get_bond_quote(obj, "al30", "ci") or get_bond_quote(obj, "al30", "24hs")
        if not al30:
            gd30_only = get_bond_quote(obj, "gd30", "ci") or get_bond_quote(obj, "gd30", "24hs")
            return round(gd30_only[0], 2) if gd30_only else None
        al30_price, al30_ts = al30
        gd30 = get_bond_quote(obj, "gd30", "ci") or get_bond_quote(obj, "gd30", "24hs")
        if gd30:
            gd30_price, gd30_ts = gd30
            if abs(al30_ts - gd30_ts) <= 7200:  # 2 horas -- GD30 fresco, promediar
                return round((al30_price + gd30_price) / 2, 2)
        return round(al30_price, 2)  # GD30 stale o ausente -- solo AL30

    # Fuente primaria: Ámbito Financiero (cierre de referencia oficial, el mismo
    # que usa el usuario para auditar). Si Ámbito todavía no publicó el cierre
    # de "fecha" (suele tardar más que el horario de este workflow), cae al
    # precio de bonos AL30/GD30 de criptoya como estimación provisoria -- ese
    # valor puede quedar desalineado con el cierre real (ver auditoría de
    # sep-2026) y en tal caso se corrige a mano cuando Ámbito lo publique.
    mep_val = get_ambito_ref("dolarrava/mep", fecha)
    ccl_val = get_ambito_ref("dolarrava/cl", fecha)
    if mep_val is not None and ccl_val is not None:
        print(f"[auto_update_fx] MEP Ámbito: {mep_val}, CCL Ámbito: {ccl_val}")
    else:
        print(f"[auto_update_fx] AVISO: Ámbito sin cierre de {fecha_iso} todavía, uso fallback criptoya (bonos)")
        try:
            mep_fb = extract_bond_price(data.get("mep"))
            ccl_fb = extract_bond_price(data.get("ccl"))
            mep_val = mep_val if mep_val is not None else mep_fb
            ccl_val = ccl_val if ccl_val is not None else ccl_fb
            print(f"[auto_update_fx] MEP criptoya (fallback): {mep_val}, CCL criptoya (fallback): {ccl_val}")
        except Exception as e:
            print(f"[auto_update_fx] AVISO: no se pudo leer MEP/CCL de ningún lado ({e}), se omiten hoy")

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
