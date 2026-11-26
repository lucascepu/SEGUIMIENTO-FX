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

def set_source(src):
    """Informa a GitHub Actions qué fuente terminó usándose, para que el
    paso de commit arme un mensaje acorde (en vez de uno fijo que puede
    quedar desactualizado respecto al dato real)."""
    gh_env = os.environ.get("GITHUB_ENV")
    if gh_env:
        with open(gh_env, "a") as f:
            f.write(f"FX_SOURCE={src}\n")

# Determinar fecha AR
import json
FERIADOS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "feriados-ar.json"), encoding="utf-8"))["feriados"]

def es_habil(d):
    return d.weekday() < 5 and d.isoformat() not in FERIADOS

if raw_fecha:
    raw = raw_fecha.replace("-", "")
    fecha = datetime.date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
else:
    ahora_ar = datetime.datetime.utcnow() - datetime.timedelta(hours=3)
    fecha = ahora_ar.date()
    # GitHub puede demorar el cron horas (a veces pasa de medianoche AR). Si todavia no cerro la rueda
    # de "hoy" (antes de las 15:30 AR) la corrida corresponde a la ultima rueda habil anterior; si no, se
    # cargaria un valor viejo/provisorio en un dia que todavia no opero (paso el 24-nov-2026 a las 00:56).
    if ahora_ar.hour * 60 + ahora_ar.minute < 15 * 60 + 30:
        fecha -= datetime.timedelta(days=1)
        while not es_habil(fecha):
            fecha -= datetime.timedelta(days=1)
        print(f"[workflow] Corrida antes del cierre ({ahora_ar:%H:%M} AR): se procesa la ultima rueda habil {fecha}.")

fecha_iso = fecha.strftime("%Y-%m-%d")
print(f"[workflow] Fecha: {fecha_iso}")

if fecha.weekday() >= 5:
    print("[workflow] Fin de semana — no se actualiza.")
    sys.exit(0)
if fecha_iso in FERIADOS:
    print(f"[workflow] Feriado ({FERIADOS[fecha_iso]}) — no se actualiza.")
    sys.exit(0)

# ── Paso 1: valor manual o criptoya (provisorio) ─────────────────────────────
if raw_valor:
    valor_provisorio = round(float(raw_valor), 2)
    print(f"[workflow] Valor manual: {valor_provisorio}")
    r = subprocess.run([sys.executable, "update_fx_diario.py", str(valor_provisorio), fecha_iso])
    if r.returncode == 0:
        set_source("manual")
    sys.exit(r.returncode)

hoy_ar = (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).date()
if fecha < hoy_ar and api_key:
    # Fecha pasada: criptoya devuelve el precio de HOY, no el de esa rueda -> solo MAE (cierre historico).
    print("[workflow] Fecha pasada: se omite criptoya, solo MAE.")
    r1 = subprocess.CompletedProcess([], 1)
else:
    print("[workflow] Paso 1: criptoya (provisorio)...")
    r1 = subprocess.run([sys.executable, "scripts/auto_update_fx.py", fecha_iso, "--source", "criptoya"])
if r1.returncode != 0:
    print("[workflow] Criptoya falló, intentando directo con MAE...")
elif not api_key:
    set_source("criptoya.com")

# ── Paso 2: MAE (oficial) ────────────────────────────────────────────────────
if api_key:
    print("[workflow] Paso 2: MAE (oficial)...")
    r2 = subprocess.run([sys.executable, "scripts/auto_update_fx.py", fecha_iso, "--source", "mae", "--force"])
    if r2.returncode == 0:
        set_source("MAE (oficial)")
        sys.exit(0)
    # MAE falló: si criptoya ya había escrito un valor válido en el Paso 1,
    # NO hay que cortar el job con error -- eso hace que GitHub Actions
    # saltee el paso de "Commit y push" siguiente y se pierda el dato
    # provisorio de criptoya que sí se guardó bien. Se sale OK con lo que
    # haya quedado del Paso 1.
    print("[workflow] MAE falló -- se conserva el valor provisorio de criptoya ya guardado (si lo hubo).")
    if r1.returncode == 0:
        set_source("criptoya.com (MAE no disponible)")
        sys.exit(0)
    sys.exit(r1.returncode)
else:
    print("[workflow] MAE_API_KEY no disponible, usando solo criptoya.")
    sys.exit(r1.returncode)
