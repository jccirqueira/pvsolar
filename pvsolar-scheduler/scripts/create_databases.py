"""Cria o banco de dados do pvSolar Scheduler (executar uma vez antes do primeiro start).

Uso:
    .\\venv\\Scripts\\python.exe scripts\\create_databases.py
"""

import asyncio
import sys
from pathlib import Path

import asyncpg

# Permite executar como `python scripts\create_databases.py` a partir de
# qualquer diretório (o Python só adiciona a pasta do script ao sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import load_config  # noqa: E402

# Banco de manutencao usado para criar o banco do servico.
MAINTENANCE_DB = "postgres"


def _strip_driver(url: str) -> str:
    """Remove o driver do esquema: ``postgresql+asyncpg://`` -> ``postgresql://``.

    O asyncpg aceita apenas ``postgresql://`` ou ``postgres://``.
    """
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
    config = load_config()
    url = config.database.url
    if not url:
        raise SystemExit("database.url nao configurado (veja config/scheduler.example.yaml)")

    # Banco do servico + banco dedicado aos testes de persistencia.
    # Os testes dropam/recriam o schema a cada teste, entao NUNCA devem
    # apontar para o banco de producao (o sufixo _test isola isso).
    service_db = database_name(url)
    databases = (service_db, f"{service_db}_test")

    conn = await asyncpg.connect(maintenance_dsn(url))
    try:
        for db in databases:
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
