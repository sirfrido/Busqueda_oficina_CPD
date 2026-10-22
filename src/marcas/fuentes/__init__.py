"""Fuentes de solicitudes publicadas en el BOPI."""

from __future__ import annotations

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class FuenteNoDisponible(RuntimeError):
    """La fuente no respondió o respondió algo que no se puede leer."""


def sesion() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "es-ES,es;q=0.9"})
    return s
