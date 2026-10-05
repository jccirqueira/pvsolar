import uvicorn

from src.api.app import config


def main() -> None:
    uvicorn.run(
        "src.api.app:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.debug,
    )


if __name__ == "__main__":
    main()
