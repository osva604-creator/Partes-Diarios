import os
from pathlib import Path

import pytest


@pytest.fixture
def source_data_dir() -> Path:
    configured = os.environ.get("PARTES_DIARIOS_DATA_DIR")
    data_dir = Path(configured) if configured else Path(__file__).resolve().parents[1] / "datos_fuente"
    if not data_dir.exists():
        pytest.skip("Los archivos maestros no están presentes en este checkout.")
    return data_dir
