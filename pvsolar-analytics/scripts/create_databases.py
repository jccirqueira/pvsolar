"""Cria o banco de dados do pvSolar Analytics (executar uma vez antes do primeiro start).

O Analytics faz um ``SELECT 1`` eager no startup (init_database), entao o
banco precisa existir antes de subir o servico.

Uso:
    python scripts\\create_databases.py
"""

import asyncio
import sys
from pathlib import Path

import asyncpg

# Permite executar como `python scripts\create_databases.py` a partir de
# qualquer diretorio (o Python so adiciona a pasta do script ao sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import load_config  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "analytics.yaml"

# Banco de manutencao usado para criar o banco do servico.
MAINTENANCE_DB = "postgres"


def _strip_driver(url: str) -> str:
    """Remove o driver do esquema: ``postgresql+asyncpg://`` -> ``postgresql://``."""
    scheme, sep, rest = url.partition("://")
    if not sep:
        return url
    return f"{scheme.split('+', 1)[0]}://{rest}"


def maintenance_dsn(database_url: str) -> str:
    """Converte a URL do servico para a URL de manutencao (banco postgres)."""
    base = _strip_driver(database_url).rsplit("/", 1)[0]
    return base + "/" + MAINTENANCE_DB


def database_name(database_url: str) -> str:
    return database_url.rsplit("/", 1)[1].split("?")[0]


async def main() -> None:
    config = load_config(str(CONFIG_PATH))
    url = config.database.url
    if not url:
        raise SystemExit("database.url nao configurado (veja config/analytics.example.yaml)")

    db = database_name(url)
    conn = await asyncpg.connect(maintenance_dsn(url))
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db
        )
        if exists:
            print(f"banco '{db}' ja existe")
        else:
            await conn.execute(f'CREATE DATABASE "{db}"')
            print(f"banco '{db}' CRIADO")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
