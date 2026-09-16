"""Fuente de fichero: anuncios en JSON, para pruebas y demostraciones.

Permite ejecutar el pipeline completo sin tocar la red:

    oficinas buscar --fuentes demo --sin-email
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import Anuncio
from .base import FuenteBase, registrar


@registrar("fixture")
class FuenteFixture(FuenteBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.archivo = Path(self.cfg.get("archivo", "tests/fixtures/anuncios.json"))

    def buscar(self) -> list[Anuncio]:
        ruta = self.archivo
        if not ruta.is_absolute():
            ruta = Path(__file__).resolve().parents[3] / ruta
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        anuncios = []
        for d in datos:
            d.setdefault("fuente", self.id)
            d.setdefault("extra", {}).setdefault("fuente_nombre", self.nombre)
            anuncios.append(Anuncio(**d))
        return anuncios
