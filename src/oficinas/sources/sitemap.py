"""Adaptador de sitemap/feed: descubre fichas a partir de sitemap.xml.

Útil para portales pequeños de agencias que no tienen listado paginable
cómodo pero sí publican su sitemap. Filtra por patrón de URL.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from ..models import Anuncio
from ..textutils import limpiar
from .base import FuenteBase, registrar
from .html_generico import deducir_tipologia

log = logging.getLogger(__name__)


@registrar("sitemap")
class FuenteSitemap(FuenteBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.urls: list[str] = self.cfg.get("urls") or []
        self.patron = re.compile(self.cfg.get("patron_url", r"(oficina|nave|local)"), re.IGNORECASE)
        self.limite = int(self.cfg.get("limite", 200))

    def buscar(self) -> list[Anuncio]:
        anuncios: list[Anuncio] = []
        for url in self.urls:
            try:
                resp = self.fetcher.get(url)
            except Exception as exc:
                log.warning("[%s] sitemap %s inaccesible: %s", self.id, url, exc)
                continue
            sopa = BeautifulSoup(resp.texto, "xml")
            for loc in sopa.find_all("loc"):
                destino = limpiar(loc.get_text())
                if not self.patron.search(destino):
                    continue
                anuncios.append(
                    Anuncio(
                        fuente=self.id,
                        url=destino,
                        titulo=destino.rsplit("/", 1)[-1].replace("-", " ")[:180],
                        tipologia=deducir_tipologia(destino),
                        operacion=self.cfg.get("operacion", "venta"),
                        extra={"fuente_nombre": self.nombre, "origen": "sitemap"},
                    )
                )
                if len(anuncios) >= self.limite:
                    return anuncios
        return anuncios
