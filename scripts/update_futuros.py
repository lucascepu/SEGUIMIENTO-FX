"""
update_futuros.py — Actualización automática de futuros ROFEX (DLR) en el dashboard.

Uso:
  1. Configurar credenciales en el bloque CONFIG más abajo (o como variables de entorno)
  2. pip install requests
  3. python update_futuros.py              # corre hoy
  4. python update_futuros.py --dry-run    # muestra precios sin actualizar

Cron / Task Scheduler: ejecutar L-V a las 17:30 ARG (20:30 UTC)

Repo: https://github.com/lucascepu/SEGUIMIENTO-FX
"""

import requests
import json
import base64
import re
import sys
import os
from datetime import datetime, date

# ═══════════════════════════════════════════════════════════════
# CONFIG — completar con tus credenciales
# ═══════════════════════════════════════════════════════════════
A3_USER     = os.getenv("A3_USER", "TU_USUARIO_A3")
A3_PASSWORD = os.getenv("A3_PASSWORD", "TU_PASSWORD_A3")
GITHUB_PAT  = os.getenv("GITHUB_PAT", "TU_GITHUB_PAT")
GITHUB_REPO = "lucascepu/SEGUIMIENTO-FX"

# API Primary/A3
PRIMARY_BASE = "https://api.primary.com.ar"

# Contratos a traer (formato A3: DLR/MESyy donde MES = 3 letras EN INGLÉS)
CONTRATOS = {
    "JUN 26": "DLR/JUN26",
    "JUL 26": "DLR/JUL26",
    "AGO 26": "DLR/AUG26",   # Agosto = AUG en inglés
    "SEP 26": "DLR/SEP26",
    "OCT 26": "DLR/OCT26",
    "NOV 26": "DLR/NOV26",
    "DIC 26": "DLR/DEC26",   # Diciembre = DEC
    "ENE 27": "DLR/JAN27",   # Enero = JAN
    "FEB 27": "DLR/FEB27",
    "MAR 27": "DLR/MAR27",
    "ABR 27": "DLR/APR27",   # Abril = APR
    "MAY 27": "DLR/MAY27",
}
# ═══════════════════════════════════════════════════════════════


def get_token():
    """Autenticarse con Primary API y obtener token."""
    url = f"{PRIMARY_BASE}/auth/getToken"
    resp = requests.post(url, json={"username": A3_USER, "password": A3_PASSWORD}, timeout=10)
    resp.raise_for_status()
    token = resp.headers.get("X-Auth-Token") or resp.json().get("token")
    if not token:
        raise ValueError(f"No se pudo obtener token. Respuesta: {resp.text[:200]}")
    print(f"✓ Autenticado con Primary API")
    return token


def get_last_price(token, symbol):
    """Obtener el último precio de un contrato."""
    url = f"{PRIMARY_BASE}/rest/md/liveData"
    params = {"marketId": "ROFX", "symbol": symbol}
    headers = {"X-Auth-Token": token}
    resp = requests.get(url, params=params, headers=headers, timeout=10)
    if resp.status_code == 404:
        return None  # Contrato sin datos (vencido o no negociado)
    resp.raise_for_status()
    data = resp.json()
    # El precio puede estar en diferentes lugares según el endpoint
    last = (data.get("market", {}).get("lP") or      # lastPrice
            data.get("last") or
            data.get("data", [{}])[0].get("last") if data.get("data") else None)
    return float(last) if last else None


def fetch_all_prices(token):
    """Traer precios de todos los contratos definidos en CONTRATOS."""
    prices = {}
    for label, symbol in CONTRATOS.items():
        try:
            price = get_last_price(token, symbol)
            if price:
                prices[label] = price
                print(f"  {label}: ${price:,.1f}")
            else:
                print(f"  {label}: sin dato (contrato sin precio)")
        except Exception as e:
            print(f"  {label}: error — {e}")
    return prices


def update_dashboard(prices, dry_run=False):
    """Actualizar FUT_DEFAULT en index.html via GitHub API."""
    # Construir string del nuevo FUT_DEFAULT
    entries = []
    for label in CONTRATOS.keys():
        if label in prices:
            entries.append(f"'{label}':{prices[label]}")
    new_default = "var FUT_DEFAULT = {" + ",".join(entries) + "};"

    if dry_run:
        print(f"\n[DRY RUN] FUT_DEFAULT que se actualizaría:\n  {new_default}")
        return

    # Descargar index.html actual
    headers = {"Authorization": f"Bearer {GITHUB_PAT}"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/index.html"
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    file_data = resp.json()
    sha = file_data["sha"]
    html = base64.b64decode(file_data["content"]).decode("utf-8")

    # Reemplazar FUT_DEFAULT
    old_default = re.search(r"var FUT_DEFAULT\s*=\s*\{[^}]+\};", html)
    if not old_default:
        raise ValueError("No se encontró FUT_DEFAULT en index.html")
    html = html.replace(old_default.group(0), new_default)

    # También actualizar la nota de fecha en el pie del FUTUROS tab
    today_str = date.today().strftime("%-d/%-m/%Y").replace("//", "/")
    html = re.sub(r"Cierre ROFEX \d+/\d+/\d+", f"Cierre ROFEX {today_str}", html)

    # Commit
    content_b64 = base64.b64encode(html.encode("utf-8")).decode()
    commit_msg = f"data: ROFEX futuros DLR cierre {today_str} (auto via update_futuros.py)"
    payload = {"message": commit_msg, "content": content_b64, "sha": sha}
    resp2 = requests.put(url, headers={**headers, "Content-Type": "application/json"},
                         json=payload, timeout=15)
    resp2.raise_for_status()
    commit_sha = resp2.json()["commit"]["sha"][:10]
    print(f"\n✅ Dashboard actualizado — commit {commit_sha}")
    print(f"   {commit_msg}")


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN — sin cambios al dashboard ===\n")

    print(f"Fetching ROFEX DLR futures — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("-" * 50)

    token = get_token()
    prices = fetch_all_prices(token)

    if not prices:
        print("\n⚠ Sin precios disponibles. ¿Mercado cerrado o credenciales incorrectas?")
        sys.exit(0)

    print(f"\n{len(prices)}/{len(CONTRATOS)} contratos con precio.")
    update_dashboard(prices, dry_run=dry_run)


if __name__ == "__main__":
    main()
