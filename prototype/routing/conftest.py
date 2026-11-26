"""Permite importar los módulos del spike desde sus pruebas."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
