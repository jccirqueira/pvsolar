from unittest.mock import patch

import src.app as app_module


class TestMain:
    def test_main_executa_uvicorn_com_config(self):
        """main() sobe o uvicorn apontando para src.api.app:app."""
        with patch.object(app_module.uvicorn, "run") as run:
            app_module.main()

        run.assert_called_once()
        args, kwargs = run.call_args
        assert args[0] == "src.api.app:app"
        assert kwargs["host"] == app_module.config.api.host
        assert kwargs["port"] == app_module.config.api.port
        assert kwargs["reload"] == app_module.config.debug
