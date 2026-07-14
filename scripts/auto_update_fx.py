#!/usr/bin/env python3
"""
auto_update_fx.py — Obtiene el TC de cierre oficial de MAE y actualiza index.html
===================================================================================
Fuente: API MAE/A3 Market Data
  URL: https://api.marketdata.mae.com.ar/api/mercado/titulo/historicoforex
  Ticker: UST$T, Segmento Mayorista (M), Plazo 000

Uso:
  python3 scripts/auto_update_fx.py                    # fecha de hoy AR
  python3 scripts/auto_update_fx.py 2026-07-14         # fecha específica
  python3 scripts/auto_update_fx.py 2026-07-14 1490.5  # valor manual (override)
"""

import sys, os, json, datetime, urllib.request, urllib.parse, subprocess

# ── Parámetros ───────────────────────────────────────────────────────────────
fecha_arg    = sys.argv[1] if len(sys.argv) >= 2 else None
valor_manual = float(sys.argv[2]) if len(sys.argv) >= 3 else None

if fecha_arg:
    raw = fecha_arg.replace("-", "")
    fecha = datetime.date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
else:
    fecha = (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).date()

fecha_iso = fecha.strftime("%Y-%m-%d")
print(f"[auto_update_fx] Fecha objetivo: {fecha_iso}")

# ── Obtener valor FX ─────────────────────────────────────────────────────────
if valor_manual is not None:
    siopel = round(valor_manual, 2)
    print(f"[auto_update_fx] Usando valor manual: {siopel}")
else:
    api_key = os.environ.get("MAE_API_KEY", "")
    if not api_key:
        print("ERROR: MAE_API_KEY no está definida")
        sys.exit(1)

    payload = json.dumps({"fechaDesde": fecha_iso, "fechaHasta": fecha_iso})
    url = ("https://api.marketdata.mae.com.ar/api/mercado/titulo/historicoforex"
           "?oTitulo=" + urllib.parse.quote(payload))
    print(f"[auto_update_fx] Llamando API MAE...")

    try:
        req = urllib.request.Request(url, headers={"x-api-key": api_key})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"ERROR HTTP {e.code}: {e.read().decode()[:200]}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR de conexión: {e}")
        sys.exit(1)

    # Buscar UST$T / Mayorista (M) / Plazo 000
    siopel = None
    for dia in data:
        for det in dia.get("details", []):
            if (det.get("ticker") == "UST$T"
                    and det.get("codigoSegmento") == "M"
                    and det.get("plazo") == "000"):
                siopel = round(float(det.get("precioCierre")), 2)
                break
        if siopel is not None:
            break

    if siopel is None:
        print("ERROR: UST$T mayorista no encontrado en la respuesta MAE")
        print("Respuesta:", str(data)[:300])
        sys.exit(1)

    print(f"[auto_update_fx] TC cierre MAE: {siopel}")

# ── Verificar plausibilidad ──────────────────────────────────────────────────
if not (1000 < siopel < 5000):
    print(f"ERROR: valor {siopel} fuera de rango plausible")
    sys.exit(1)

# ── Ejecutar update ──────────────────────────────────────────────────────────
cmd = [sys.executable, "update_fx_diario.py", str(siopel), fecha_iso]
print(f"[auto_update_fx] Ejecutando: {' '.join(cmd)}")
result = subprocess.run(cmd)
sys.exit(result.returncode)
