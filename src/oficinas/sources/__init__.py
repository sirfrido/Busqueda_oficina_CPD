"""Adaptadores de fuentes. Cada uno devuelve una lista de Anuncio."""

from .base import Fuente, registrar, crear_fuente, ADAPTADORES  # noqa: F401
from . import html_generico, idealista_api, boe_subastas, sitemap, fixture  # noqa: F401
