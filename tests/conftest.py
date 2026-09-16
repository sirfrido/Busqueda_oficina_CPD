import sys
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))


@pytest.fixture(scope="session")
def criterios():
    return yaml.safe_load((RAIZ / "config" / "criteria.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def zonas():
    return yaml.safe_load((RAIZ / "config" / "zonas.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def plantillas():
    return yaml.safe_load((RAIZ / "config" / "plantillas.yaml").read_text(encoding="utf-8"))
