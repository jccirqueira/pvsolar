"""Remove TODAS as tabelas do banco do pvSolar Scheduler (reset de desenvolvimento).

Uso:
    .\\venv\\Scripts\\python.exe scripts\\reset_database.py --yes

Requer o sinalizador --yes para evitar perda acidental de dados.
"""

import asyncio
import sys
from pathlib import Path

# Permite executar como `python scripts\reset_database.py` a partir de
# qualquer diretório (o Python só adiciona a pasta do script ao sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import load_config  # noqa: E402
from src.db.base import Base, create_engine  # noqa: E402
from src.db.service import _safe_url  # noqa: E402


async def main() -> None:
    if "--yes" not in sys.argv:
        raise SystemExit("Confirmacao necessaria: acrescente --yes ao comando")

    config = load_config()
    if not config.database.enabled or not config.database.url:
        raise SystemExit("database.url nao configurado")

    engine = create_engine(config.database)
    try:
        async with engine.begin() as conn:
            def drop_all(sync_conn):
                Base.metadata.drop_all(sync_conn)

            await conn.run_sync(drop_all)
        print(f"tabelas removidas de {_safe_url(config.database.url)}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
