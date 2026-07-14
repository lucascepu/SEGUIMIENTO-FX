#!/usr/bin/env python3
"""
run_workflow.py — Orquestador del workflow GitHub Actions.
Lee variables de entorno INPUT_FECHA, INPUT_VALOR, MAE_API_KEY
y decide qué hacer: API o valor manual, feriado o no.
"""
import os, sys, datetime, subprocess

# ── Leer entorno ─────────────────────────────────────────────────────────────
raw_fecha = os.environ.get("INPUT_FECHA", "").strip()
raw_valor = os.environ.get("INPUT_VALOR", "").strip()
api_key   = os.environ.get("MAE_API_KEY", "").strip()

# ── Determinar fecha ─────────────────────────────────────────────────────────
if raw_fecha:
    raw_fecha = raw_fecha.replace("-", "")
    fecha = datetime.date(int(raw_fecha[:4]), int(raw_fecha[4:6]), int(raw_fecha[6:]))
else:
    utc_now = datetime.datetime.utcnow()
    fecha = (utc_now - datetime.timedelta(hours=3)).date()

fecha_iso = fecha.strftime("%Y-%m-%d")
print(f"[workflow] Fecha: {fecha_iso}")

# ── Verificar día hábil (lun-vie) ────────────────────────────────────────────
if fecha.weekday() >= 5:
    print(f"[workflow] Fin de semana — no se actualiza.")
    sys.exit(0)

# ── Determinar valor ─────────────────────────────────────────────────────────
if raw_valor:
    valor = float(raw_valor)
    print(f"[workflow] Valor manual: {valor}")
    cmd = [sys.executable, "update_fx_diario.py", str(valor), fecha_iso]
else:
    print(f"[workflow] Llamando API MAE...")
    cmd = [sys.executable, "scripts/auto_update_fx.py", fecha_iso]

# ── Ejecutar ─────────────────────────────────────────────────────────────────
print(f"[workflow] Ejecutando: {' '.join(cmd)}")
result = subprocess.run(cmd)
sys.exit(result.returncode)
