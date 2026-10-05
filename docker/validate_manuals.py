"""Valida todos os Manual.html do ecossistema: tags, ancoras e sanidade."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ERRORS = []
manuals = sorted(ROOT.glob("pvsolar-*/Manual.html"))

if len(manuals) != 13:
    ERRORS.append(f"esperados 13 manuals, encontrados {len(manuals)}")

for path in manuals:
    name = path.parent.name
    html = path.read_text(encoding="utf-8")

    for tag in ("div", "section", "table", "tr", "li", "code"):
        opens = len(re.findall(rf"<{tag}[\s>]", html))
        closes = len(re.findall(rf"</{tag}>", html))
        if opens != closes:
            ERRORS.append(f"{name}: <{tag}> desbalanceado {opens}/{closes}")

    ids = set(re.findall(r'id="([^"]+)"', html))
    hrefs = set(re.findall(r'href="#([^"]+)"', html))
    dangling = sorted(hrefs - ids)
    if dangling:
        ERRORS.append(f"{name}: ancoras penduradas {dangling}")

    # Entrypoints quebrados (src.api.app em servicos sem src/api, porta errada)
    broken = re.findall(
        r"src\.api\.app:app[^<\n]*--port (?:8000|8001|5000|8004|8005|8006)\b", html
    )
    if broken:
        ERRORS.append(f"{name}: entrypoint quebrado {broken}")

    print(f"  {name}: OK ({len(html)} bytes, {len(ids)} ids)")

if ERRORS:
    print("\nFALHAS:")
    for err in ERRORS:
        print(f"  - {err}")
    sys.exit(1)

print("\nOK - 13 manuals consistentes")
