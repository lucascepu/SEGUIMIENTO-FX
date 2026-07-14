#!/usr/bin/env python3
"""
auto_update_fx.py — Obtiene el TC de cierre de MAE y actualiza index.html
==========================================================================
Fuente: API MAE/A3 Market Data
  URL: https://api.marketdata.mae.com.ar/api/mercado/titulo/historicoforex
  Ticker: UST$T (USA Transf a Pesos Transf), Segmento Mayorista (M), Plazo 000

Uso:
  python3 scripts/auto_update_fx.py                    # fecha de hoy
  python3 scripts/auto_update_fx.py 2026-07-14         # fecha específica
  python3 scripts/auto_update_fx.py 2026-07-14 1490.5  # valor manual (override)

Variables de entorno:
  MAE_API_KEY  — API Key de MAE/A3 (requerida si no se pasa valor manual)
"""

import sys, os, re, json, datetime, urllib.request, urllib.parse

# ── Parámetros ──────────────────────────────────────────────────────────────
fecha_arg    = sys.argv[1] if len(sys.argv) >= 2 else None
valor_manual = float(sys.argv[2]) if len(sys.argv) >= 3 else None

if fecha_arg:
    fecha = datetime.datetime.strptime(fecha_arg, "%Y-%m-%d").date()
else:
    # Hora Argentina (UTC-3)
    fecha = (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).date()

fecha_iso = fecha.strftime("%Y-%m-%d")
print(f"[auto_update_fx] Fecha objetivo: {fecha_iso}")

# ── Obtener valor FX ─────────────────────────────────────────────────────────
if valor_manual is not None:
    siopel = valor_manual
    print(f"[auto_update_fx] Usando valor manual: {siopel}")
else:
    api_key = os.environ.get("MAE_API_KEY", "")
    if not api_key:
        print("ERROR: MAE_API_KEY no está definida")
        sys.exit(1)

    # Construir URL con el parámetro oTitulo como JSON URL-encoded
    payload = json.dumps({"fechaDesde": fecha_iso, "fechaHasta": fecha_iso})
    url = (
        "https://api.marketdata.mae.com.ar/api/mercado/titulo/historicoforex"
        "?oTitulo=" + urllib.parse.quote(payload)
    )
    print(f"[auto_update_fx] Llamando API MAE: {url[:80]}...")

    req = urllib.request.Request(url, headers={"x-api-key": api_key})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            body   = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"ERROR HTTP {e.code}: {e.read().decode()[:200]}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR de conexión: {e}")
        sys.exit(1)

    print(f"[auto_update_fx] Status: {status}")

    if status != 200:
        print(f"ERROR: API devolvió {status}")
        sys.exit(1)

    data = json.loads(body)

    # Estructura esperada: lista de días → details por ticker
    # Buscar UST$T / Mayorista (codigoSegmento=M) / Plazo 000
    siopel = None
    for dia in data:
        for det in dia.get("details", []):
            if (det.get("ticker") == "UST$T"
                    and det.get("codigoSegmento") == "M"
                    and det.get("plazo") == "000"):
                siopel = det.get("precioCierre")
                break
        if siopel is not None:
            break

    if siopel is None:
        # Fallback: buscar USMEP / Mayorista / 000
        print("[auto_update_fx] UST$T no encontrado, buscando fallback USMEP...")
        for dia in data:
            for det in dia.get("details", []):
                if (det.get("ticker") == "USMEP"
                        and det.get("codigoSegmento") == "M"
                        and det.get("plazo") == "000"):
                    siopel = det.get("precioCierre")
                    break
            if siopel is not None:
                break

    if siopel is None:
        print("ERROR: no se encontró UST$T ni USMEP mayorista en la respuesta")
        print("Respuesta (primeros 500 chars):", body[:500])
        sys.exit(1)

    print(f"[auto_update_fx] TC obtenido de API: {siopel}")

# ── Verificar que el valor sea plausible ─────────────────────────────────────
if not (1000 < siopel < 5000):
    print(f"ERROR: valor {siopel} fuera de rango plausible (1000-5000)")
    sys.exit(1)

# ── Llamar al script de update ────────────────────────────────────────────────
import subprocess
cmd = [sys.executable, "update_fx_diario.py", str(siopel), fecha_iso]
print(f"[auto_update_fx] Ejecutando: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=False)
sys.exit(result.returncode)
