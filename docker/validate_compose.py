"""Valida o docker-compose.yml da raiz do ecossistema pvSolar.

Checagens:
  - YAML parseavel e servico esperado presente (16);
  - context/dockerfile de build existem no disco;
  - volumes com bind (caminho relativo) existem;
  - portas publicadas sem conflito;
  - portas internas dos servicos batem com o mapa do ecossistema.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.yml"

EXPECTED_PORTS = {
    "gateway": 8000,
    "analytics": 8001,
    "reports": 8002,
    "fleet": 8003,
    "alert": 8004,
    "grid": 8005,
    "twin": 8006,
    "auth": 8007,
    "backup": 8008,
    "scheduler": 8009,
    "exporter": 8010,
    "scada": 5000,
    "web": 3001,
}

errors: list[str] = []

with open(COMPOSE, encoding="utf-8") as fh:
    doc = yaml.safe_load(fh)

services = doc.get("services", {})
print(f"servicos: {len(services)} -> {', '.join(services)}")

# 1) servicos esperados
expected = {"postgres", "mosquitto", "caddy"} | set(EXPECTED_PORTS)
missing = expected - set(services)
if missing:
    errors.append(f"servicos faltando: {sorted(missing)}")

# 2) builds
for name, svc in services.items():
    build = svc.get("build")
    if not build:
        continue
    ctx = (ROOT / build["context"]).resolve()
    df = ctx / build.get("dockerfile", "Dockerfile")
    if not ctx.is_dir():
        errors.append(f"{name}: context inexistente: {ctx}")
    elif not df.is_file():
        errors.append(f"{name}: Dockerfile inexistente: {df}")

# 3) binds de volume
for name, svc in services.items():
    for vol in svc.get("volumes", []):
        if not isinstance(vol, str):
            continue
        src = vol.split(":", 1)[0]
        if src.startswith(".") or src.startswith("/"):
            path = (ROOT / src).resolve()
            if not path.exists():
                errors.append(f"{name}: volume inexistente: {src}")

# 4) portas publicadas sem conflito
published: dict[str, str] = {}
for name, svc in services.items():
    for port in svc.get("ports", []):
        host = str(port).rsplit(":", 2)[-2] if str(port).count(":") else None
        key = str(port)
        if key in published:
            errors.append(f"porta duplicada {key}: {published[key]} e {name}")
        published[key] = name

# 5) porta interna do servico == mapa do ecossistema
for name, internal in EXPECTED_PORTS.items():
    svc = services.get(name, {})
    ports = [str(p) for p in svc.get("ports", [])]
    if not any(str(internal) == p.rsplit(":", 1)[-1] for p in ports):
        errors.append(f"{name}: porta interna {internal} nao publicada (ports={ports})")

# 6) initdb com os bancos
sql = (ROOT / "docker" / "initdb" / "01-databases.sql").read_text(encoding="utf-8")
for db in (
    "pvsolar_auth",
    "pvsolar_auth_test",
    "pvsolar_scheduler",
    "pvsolar_scheduler_test",
    "pvsolar_analytics",
):
    if f"CREATE DATABASE {db};" not in sql:
        errors.append(f"initdb sem CREATE DATABASE {db}")

# 7) variante de config de cada servico que monta volume
for name in ("gateway", "analytics", "scada", "exporter", "backup", "reports", "fleet"):
    if not (ROOT / "docker" / "config" / f"{name}.yaml").is_file():
        errors.append(f"variante docker/config/{name}.yaml inexistente")

if errors:
    print("\nFALHAS:")
    for err in errors:
        print(f"  - {err}")
    raise SystemExit(1)

print("\nOK - compose, builds, volumes, portas e initdb consistentes")
