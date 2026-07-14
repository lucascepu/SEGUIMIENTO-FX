#!/usr/bin/env python3
"""
run_workflow.py — Orquestador del workflow GitHub Actions.
Lee INPUT_FECHA e INPUT_VALOR del entorno y decide qué hacer.
La fuente de datos es criptoya.com/api/dolar (pública, sin API key).
"""
import os, sys, datetime, subprocess

raw_fecha = os.environ.get("INPUT_FECHA", "").strip()
raw_valor = os.environ.get("INPUT_VALOR", "").strip()

# Determinar fecha
if raw_fecha:
    raw = raw_fecha.replace("-", "")
    fecha = datetime.date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
else:
    fecha = (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).date()

fecha_iso = fecha.strftime("%Y-%m-%d")
print(f"[workflow] Fecha: {fecha_iso}")

# Verificar día hábil
if fecha.weekday() >= 5:
    print("[workflow] Fin de semana — no se actualiza.")
    sys.exit(0)

# Ejecutar
if raw_valor:
    valor = round(float(raw_valor), 2)
    print(f"[workflow] Valor manual: {valor}")
    cmd = [sys.executable, "update_fx_diario.py", str(valor), fecha_iso]
else:
    print("[workflow] Llamando API criptoya...")
    cmd = [sys.executable, "scripts/auto_update_fx.py", fecha_iso]

print(f"[workflow] Ejecutando: {' '.join(cmd)}")
result = subprocess.run(cmd)
sys.exit(result.returncode)
