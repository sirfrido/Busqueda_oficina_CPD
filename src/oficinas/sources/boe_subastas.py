"""Portal de Subastas del BOE: inmuebles embargados (judiciales y notariales).

El buscador del BOE es un formulario con muchos campos; aquí se consulta la
vista de resultados filtrada por provincia y tipo de bien, y se parsea la
tabla. Es la fuente con precios más bajos y con más letra pequeña: el email
marca siempre estos resultados como «subasta» para revisarlos con cuidado
(cargas, ocupación, depósito previo).
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from ..models import Anuncio
from ..textutils import extraer_precio_eur, extraer_superficie_m2, limpiar, normalizar
from .base import FuenteBase, registrar

log = logging.getLogger(__name__)

BASE = "https://subastas.boe.es/"
BUSQUEDA = "https://subastas.boe.es/subastas_ava.php"

PALABRAS_INMUEBLE_UTIL = ("local", "nave", "oficina", "industrial", "almacen", "almacén")


@registrar("boe_subastas")
class FuenteBOE(FuenteBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.params = self.cfg.get("params", {})

    def buscar(self) -> list[Anuncio]:
        provincia = str(self.params.get("provincia", "46"))
        consulta = {
            "accion": "Buscar",
            "dato[0]": "",                 # texto libre
            "campo[1]": "SUBASTA.ESTADO",
            "dato[1]": "EJ",               # en ejecución / celebrándose
            "campo[3]": "BIEN.TIPO",
            "dato[3]": "I",                # inmuebles
            "campo[4]": "BIEN.PROVINCIA",
            "dato[4]": provincia,
            "sort_field[0]": "SUBASTA.FECHA_FIN_YMD",
            "sort_order[0]": "desc",
            "page_hits": "50",
        }
        url = f"{BUSQUEDA}?{urlencode(consulta)}"
        self.errores_red = []
        try:
            resp = self.fetcher.get(url)
        except Exception as exc:
            log.warning("[%s] no se pudo consultar el BOE: %s", self.id, exc)
            self.errores_red.append(str(exc)[:120])
            return []

        sopa = BeautifulSoup(resp.texto, "lxml")
        anuncios: list[Anuncio] = []
        for bloque in sopa.select("div.resultado-busqueda, li.resultado-busqueda, div.panel"):
            texto = limpiar(bloque.get_text(" "))
            if not texto or len(texto) < 40:
                continue
            txt_norm = normalizar(texto)
            if not any(p in txt_norm for p in PALABRAS_INMUEBLE_UTIL):
                continue
            enlace = bloque.find("a", href=True)
            if not enlace:
                continue
            superficie = extraer_superficie_m2(texto)
            valor = self._valor_subasta(texto)
            tope = self.params.get("valor_max_eur")
            if tope and valor and valor > float(tope):
                continue
            anuncios.append(
                Anuncio(
                    fuente=self.id,
                    url=urljoin(BASE, enlace["href"]),
                    titulo=limpiar(enlace.get_text(" "))[:200] or texto[:120],
                    descripcion=texto[:4000],
                    precio_eur=valor,
                    superficie_m2=superficie,
                    municipio=self._municipio(texto),
                    tipologia="nave" if "nave" in txt_norm else ("oficina" if "oficina" in txt_norm else "local"),
                    operacion="venta",
                    extra={"fuente_nombre": self.nombre, "es_subasta": True},
                )
            )
        if not anuncios:
            log.info("[%s] sin resultados aprovechables en esta pasada", self.id)
        return anuncios

    @staticmethod
    def _valor_subasta(texto: str) -> float | None:
        m = re.search(r"(?:valor subasta|puja m[ií]nima|tipo)\D{0,20}([\d.,]+)\s*€", texto, re.IGNORECASE)
        if m:
            return extraer_precio_eur(f"{m.group(1)} €")
        return extraer_precio_eur(texto)

    @staticmethod
    def _municipio(texto: str) -> str:
        m = re.search(r"(?:Localidad|Municipio)\s*:?\s*([A-ZÁÉÍÓÚÑ][\w'’\- ]{2,40})", texto)
        return limpiar(m.group(1)) if m else ""
