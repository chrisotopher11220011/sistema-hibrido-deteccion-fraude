"""Fixtures comunes a las pruebas unitarias y de contrato de la API (fase 4)."""

import shutil
from pathlib import Path

import pytest

from apoyo import RAIZ_REPO, entrenar


@pytest.fixture
def raiz_api(tmp_path: Path) -> Path:
    shutil.copytree(RAIZ_REPO / "config", tmp_path / "config")
    return tmp_path


@pytest.fixture
def entrenar_modelo():
    """Funcion `entrenar_modelo(raiz, muestra=True, version=..., **cambios) -> modelo.json`."""
    return entrenar
