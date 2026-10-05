"""pvSolar Grid - Aplicação principal."""

from src.api.app import create_app
from src.core.config import load_config

config = load_config()
app = create_app(config)
