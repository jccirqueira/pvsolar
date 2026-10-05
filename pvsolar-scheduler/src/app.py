import uvicorn

from src.core.config import load_config

config = load_config()


def create_app():
    from src.api.app import app
    return app


if __name__ == "__main__":
    uvicorn.run("src.app:app", host=config.api.host, port=config.api.port, reload=config.debug)
