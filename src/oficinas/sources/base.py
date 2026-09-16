"""Contrato común de las fuentes y registro de adaptadores."""

from __future__ import annotations

import logging
from typing import Any, Callable, Protocol

from ..fetch import Fetcher
from ..models import Anuncio

log = logging.getLogger(__name__)

ADAPTADORES: dict[str, Callable[..., "Fuente"]] = {}


class Fuente(Protocol):
    id: str
    nombre: str

    def buscar(self) -> list[Anuncio]:
        """Devuelve los anuncios del listado, sin filtrar."""


def registrar(nombre_adaptador: str):
    def deco(cls):
        ADAPTADORES[nombre_adaptador] = cls
        return cls
    return deco


def crear_fuente(cfg: dict[str, Any], fetcher: Fetcher, defaults: dict[str, Any]) -> Fuente | None:
    adaptador = cfg.get("adapter")
    cls = ADAPTADORES.get(adaptador)
    if cls is None:
        log.warning("Fuente %s: adaptador desconocido '%s'", cfg.get("id"), adaptador)
        return None
    return cls(cfg=cfg, fetcher=fetcher, defaults=defaults)


class FuenteBase:
    """Implementación común: id, nombre y captura de errores por fuente."""

    def __init__(self, cfg: dict[str, Any], fetcher: Fetcher, defaults: dict[str, Any]) -> None:
        self.cfg = cfg
        self.fetcher = fetcher
        self.defaults = defaults
        self.id = cfg.get("id", "desconocida")
        self.nombre = cfg.get("nombre", self.id)
        # Errores de red de la última pasada: sirven para que el diagnóstico
        # distinga "el portal no respondió" de "los selectores ya no valen".
        self.errores_red: list[str] = []
        self.max_paginas = int(cfg.get("max_paginas", defaults.get("max_paginas", 5)))

    def buscar(self) -> list[Anuncio]:  # pragma: no cover - lo implementan las hijas
        raise NotImplementedError
