"""Valida o HTML do Guia pvSolar: tags balanceadas e ancoras resolvidas."""

import re
import sys
from pathlib import Path

GUIDE = Path(__file__).resolve().parent.parent / "Guia Completo de Instalacao do Ecossistema pvSolar.html"

html = GUIDE.read_text(encoding="utf-8")

errors = []

for tag in ("div", "section", "table", "ul", "li", "tr", "td", "code"):
    opens = len(re.findall(rf"<{tag}[\s>]", html))
    closes = len(re.findall(rf"</{tag}>", html))
    status = "OK " if opens == closes else "DIF"
    print(f"  {status} <{tag}>: {opens} aberturas / {closes} fechamentos")
    if opens != closes:
        errors.append(f"<{tag}> desbalanceado: {opens} != {closes}")

# Ancoras do sidebar x ids das secoes
ids = set(re.findall(r'id="([^"]+)"', html))
hrefs = set(re.findall(r'href="#([^"]+)"', html))
dangling = sorted(hrefs - ids)
print(f"  ids={len(ids)} hrefs={len(hrefs)} dangling={dangling if dangling else 0}")
if dangling:
    errors.append(f"ancoras penduradas: {dangling}")

# Itens novos da secao Docker/VPS
for needle in (
    "Docker / VPS",
    "docker-compose.yml da raiz",
    "01-databases.sql",
    "docker/Caddyfile",
    ".env.example",
    "validate_compose.py",
    "uvicorn src.app:app --host 0.0.0.0 --port 8004",
    "python -m core.gateway -c config/gateway.yaml",
    "python -m src.core.app -c config/analytics.yaml",
    "python -m src.app -c config/scada.yaml",
    "<td>137 passed</td>",
    "<td>50 passed</td>",
    "<td>60 passed</td>",
):
    if needle not in html:
        errors.append(f"conteudo ausente: {needle!r}")

# Nada de comandos quebrados restantes (src.api.app para servicos sem src/api)
broken = re.findall(r"src\.api\.app:app[^<\n]*--port (?:8000|8001|5000|8004|8005|8006)\b", html)
if broken:
    errors.append(f"comandos quebrados restantes: {broken}")

if errors:
    print("\nFALHAS:")
    for err in errors:
        print(f"  - {err}")
    sys.exit(1)

print("\nOK - guia consistente")
