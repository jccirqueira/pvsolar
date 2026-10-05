#!/usr/bin/env python3
"""Validador de links relativos em arquivos Markdown (.md) do repositorio.

Garante que TODO link interno de README/Resumo/NOTES aponte para um arquivo
que exista (evita links mortos tipo docs/*.md inexistente). URLs http(s),
mailto: e ancora (#...) sao ignorados. Executar da raiz do repositorio:

    python docker/validate_md_links.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"venv", ".venv", "node_modules", ".git", "__pycache__", "site-packages"}
LINK = re.compile(r"\]\(([^)]+)\)")


def main() -> int:
    broken: list[str] = []
    checked = 0

    for md in sorted(ROOT.rglob("*.md")):
        if SKIP_DIRS & set(md.parts):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        for m in LINK.finditer(text):
            target = m.group(1).strip().strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            checked += 1
            resolved = (md.parent / target.replace("%20", " ")).resolve()
            if not resolved.exists():
                line = text[: m.start()].count("\n") + 1
                broken.append(f"{md.relative_to(ROOT)}:{line} -> {target}")

    if broken:
        print(f"FAIL - {len(broken)} link(s) relativos quebrado(s) em .md:")
        for b in broken:
            print(f"  {b}")
        return 1
    print(f"OK - {checked} links relativos em .md todos existem")
    return 0


if __name__ == "__main__":
    sys.exit(main())
