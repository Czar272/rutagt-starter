"""Fixtures compartidas para las pruebas del recolector."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

MODULE_NAME = "rutagt_collect"
MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "pipeline" / "collectors" / "collect.py"
)


def load_collect_module() -> ModuleType:
    """Carga `collect.py` por ruta, reutilizando el módulo si ya fue cargado."""
    if MODULE_NAME in sys.modules:
        return sys.modules[MODULE_NAME]
    spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def collect() -> ModuleType:
    return load_collect_module()
