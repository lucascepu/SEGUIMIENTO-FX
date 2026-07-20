#!/usr/bin/env python3
"""
run_workflow.py — Orquestador del workflow GitHub Actions.
Flujo:
  1. Criptoya → actualiza hS[] con precio provisorio
  2. MAE → si difiere, sobreescribe con precio oficial (--force)
"""
import os, sys, datetime, subprocess

raw_fecha = os.environ.get("INPUT_FECHA", "").strip()
raw_valor = os.environ.get("INPUT_VALOR", "").strip()
api_key   = os.environ.get("MAE_API_KEY", "").strip()

# Determinar fecha AR
if raw_fecha:
    raw = raw_fecha.replace("-", "")
    fecha = datetime.date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
else:
    fecha = (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).date()

fecha_iso = fecha.strftime("%Y-%m-%d")
print(f"[workflow] Fecha: {fecha_iso}")

if fecha.weekday() >= 5:
    print("[workflow] Fin de semana — no se actualiza.")
    sys.exit(0)

# ── Paso 1: valor manual o criptoya (provisorio) ─────────────────────────────
if raw_valor:
    valor_provisorio = round(float(raw_valor), 2)
    print(f"[workflow] Valor manual: {valor_provisorio}")
    r = subprocess.run([sys.executable, "update_fx_diario.py", str(valor_provisorio), fecha_iso])
    sys.exit(r.returncode)

print("[workflow] Paso 1: criptoya (provisorio)...")
r1 = subprocess.run([sys.executable, "scripts/auto_update_fx.py", fecha_iso, "--source", "criptoya"])
if r1.returncode != 0:
    print("[workflow] Criptoya falló, intentando directo con MAE...")

# ── Paso 2: MAE (oficial) ────────────────────────────────────────────────────
if api_key:
    print("[workflow] Paso 2: MAE (oficial)...")
    r2 = subprocess.run([sys.executable, "scripts/auto_update_fx.py", fecha_iso, "--source", "mae", "--force"])
    sys.exit(r2.returncode)
else:
    print("[workflow] MAE_API_KEY no disponible, usando solo criptoya.")
    sys.exit(r1.returncode)
