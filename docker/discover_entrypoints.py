"""Mapeia, por projeto, como o `app` e' definido e qual o alvo do uvicorn.

Analise estatica (AST): nao importa nada, nao precisa de dependencias.
Varre a arvore inteira (incluindo blocos try/if) e ignora atribuicoes dentro
de funcoes/classes. Para cada src/**/*.py reporta atribuicoes de `app` a
nivel de modulo e chamadas a uvicorn.run com o alvo do autor.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROJECTS = [
    "pvsolar-auth",
    "pvsolar-scheduler",
    "pvsolar-gateway",
    "pvsolar-analytics",
    "pvsolar-reports",
    "pvsolar-fleet",
    "pvsolar-alert",
    "pvsolar-grid",
    "pvsolar-twin",
    "pvsolar-backup",
    "pvsolar-exporter",
    "pvsolar-scada",
]

SCOPED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def describe_value(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name):
            return f"Call:{func.id}()"
        if isinstance(func, ast.Attribute):
            return f"Call:{func.attr}()"
        return "Call:?"
    if isinstance(node, ast.Name):
        return f"Name:{node.id}"
    if isinstance(node, ast.Constant):
        return f'"{node.value}"'
    return type(node).__name__


def analyze(base: Path) -> dict:
    out = {}
    for py in sorted((base / "src").rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue

        # mapa pai -> filho para descartar escopos de funcao/classe
        parent: dict = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent[child] = node

        def in_scope(node) -> bool:
            cur = parent.get(node)
            while cur is not None:
                if isinstance(cur, SCOPED):
                    return True
                cur = parent.get(cur)
            return False

        apps, runs = [], []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id in ("app", "application") and not in_scope(node):
                        apps.append(f"L{node.lineno}:{describe_value(node.value)}")
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id in ("app", "application") and node.value and not in_scope(node):
                    apps.append(f"L{node.lineno}:{describe_value(node.value)}")
            elif isinstance(node, ast.ImportFrom) and not in_scope(node):
                for alias in node.names:
                    if alias.asname in ("app", "application") or (alias.name in ("app", "application") and alias.asname is None):
                        apps.append(f"L{node.lineno}:from {node.module} import {alias.name}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "run" and isinstance(node.func.value, ast.Name) and node.func.value.id == "uvicorn":
                    arg = node.args[0] if node.args else None
                    desc = describe_value(arg) if arg is not None else "?"
                    runs.append(f"L{node.lineno}:uvicorn.run({desc})")
        if apps or runs:
            rel = py.relative_to(base).with_suffix("")
            parts = ["src" if p == "src" else p for p in rel.parts]
            if parts and parts[-1] == "__init__":
                parts = parts[:-1]
            out[".".join(parts)] = {"app": apps, "main": runs}
    return out


for proj in PROJECTS:
    base = ROOT / proj
    info = analyze(base) if (base / "src").exists() else {}
    print(proj)
    if not info:
        print("    (nada encontrado)")
    for mod, data in info.items():
        print(f"    {mod:<26} app={data['app']} main={data['main']}")
