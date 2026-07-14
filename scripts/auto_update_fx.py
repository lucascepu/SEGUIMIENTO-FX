#!/usr/bin/env python3
"""
auto_update_fx.py — Obtiene el TC mayorista de criptoya.com y actualiza index.html
====================================================================================
Fuente: https://criptoya.com/api/dolar
  Campo: mayorista.price

Uso:
  python3 scripts/auto_update_fx.py                    # fecha de hoy AR
  python3 scripts/auto_update_fx.py 2026-07-14         # fecha específica
  python3 scripts/auto_update_fx.py 2026-07-14 1490.5  # valor manual (override)
"""

import sys, os, re, json, datetime, urllib.request, subprocess

# ── Parámetros ──────────────────────────────────────────────────────────────
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
    url = "https://criptoya.com/api/dolar"
    print(f"[auto_update_fx] Llamando {url}...")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"ERROR al llamar criptoya: {e}")
        sys.exit(1)

    mayorista = data.get("mayorista")
    if mayorista is None:
        print("ERROR: clave 'mayorista' no encontrada en la respuesta")
        print("Claves disponibles:", list(data.keys()))
        sys.exit(1)

    # Puede ser un dict {"price": ..., "variation": ...} o un número directo
    if isinstance(mayorista, dict):
        siopel = round(float(mayorista["price"]), 2)
    else:
        siopel = round(float(mayorista), 2)

    print(f"[auto_update_fx] TC mayorista obtenido: {siopel}")

# ── Verificar que el valor sea plausible ─────────────────────────────────────
if not (1000 < siopel < 5000):
    print(f"ERROR: valor {siopel} fuera de rango plausible (1000-5000)")
    sys.exit(1)

# ── Llamar al script de update ────────────────────────────────────────────────
cmd = [sys.executable, "update_fx_diario.py", str(siopel), fecha_iso]
print(f"[auto_update_fx] Ejecutando: {' '.join(cmd)}")
result = subprocess.run(cmd)
sys.exit(result.returncode)
