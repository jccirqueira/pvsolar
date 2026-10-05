"""
Unit tests for the package-level metadata and re-exports.

Importing the packages is what executes the statements of
``src/__init__.py`` and ``src/pvsolar/__init__.py``; the assertions below
pin down the public contract they declare.
"""

import re
import sys
from pathlib import Path

# O pacote de nivel superior vive na raiz do projeto; os submodulos
# (core, drivers, ...) ficam dentro de src (ja adicionado pelo conftest).
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

import pvsolar
import src
from core.config import GatewayConfig, load_config
from core.gateway import SolarGateway, main


class TestRootPackageMetadata:
    """Tests for the metadata declared in src/__init__.py."""

    def test_version_is_semver(self):
        assert re.fullmatch(r"\d+\.\d+\.\d+", src.__version__)

    def test_author_email_and_license_are_declared(self):
        assert src.__author__ == "pvSolar Team"
        assert src.__email__ == "dev@pvsolar.io"
        assert src.__license__ == "GPL-3.0"


class TestPvsolarReExports:
    """Tests for the re-exports declared in src/pvsolar/__init__.py."""

    def test_all_lists_the_public_api(self):
        assert pvsolar.__all__ == [
            "SolarGateway", "GatewayConfig", "load_config", "main"
        ]

    def test_all_names_exist_on_the_package(self):
        missing = [name for name in pvsolar.__all__ if not hasattr(pvsolar, name)]
        assert missing == []

    def test_reexports_point_to_the_source_objects(self):
        assert pvsolar.SolarGateway is SolarGateway
        assert pvsolar.GatewayConfig is GatewayConfig
        assert pvsolar.load_config is load_config
        assert pvsolar.main is main
