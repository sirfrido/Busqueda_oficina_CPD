"""Idealista vía API oficial (OAuth2 client_credentials).

Es la vía limpia para el portal con más inventario: sin scraping, con
condiciones de uso claras. Requiere dar de alta la API en
https://developers.idealista.com y exportar:

    IDEALISTA_API_KEY / IDEALISTA_API_SECRET

Si no hay credenciales, la fuente se salta sin romper la ejecución diaria.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

from ..models import Anuncio
from .base import FuenteBase, registrar

log = logging.getLogger(__name__)

TOKEN_URL = "https://api.idealista.com/oauth/token"
SEARCH_URL = "https://api.idealista.com/3.5/es/search"

# La API distingue estos tipos; para un CPD interesan locales, oficinas,
# naves (dentro de 'premises') y edificios enteros.
TIPOS_POR_DEFECTO = ["premises", "offices", "buildings"]


@registrar("idealista_api")
class FuenteIdealistaAPI(FuenteBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.params = self.cfg.get("params", {})
        self.api_key = os.getenv("IDEALISTA_API_KEY", "")
        self.api_secret = os.getenv("IDEALISTA_API_SECRET", "")
        self._token: str | None = None

    @property
    def disponible(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def _obtener_token(self) -> str:
        if self._token:
            return self._token
        credenciales = base64.b64encode(f"{self.api_key}:{self.api_secret}".encode()).decode()
        datos = self.fetcher.post_json(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {credenciales}",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            },
            data={"grant_type": "client_credentials", "scope": "read"},
        )
        self._token = datos["access_token"]
        return self._token

    def buscar(self) -> list[Anuncio]:
        if not self.disponible:
            log.info("[%s] sin credenciales IDEALISTA_API_KEY/SECRET: fuente omitida", self.id)
            return []

        token = self._obtener_token()
        cabeceras = {"Authorization": f"Bearer {token}", "Content-Type": "application/x-www-form-urlencoded"}
        tipos = self.params.get("propertyTypes") or [self.params.get("propertyType")] or TIPOS_POR_DEFECTO
        tipos = [t for t in tipos if t] or TIPOS_POR_DEFECTO

        anuncios: list[Anuncio] = []
        for busqueda in self.params.get("busquedas", []):
            for tipo in tipos:
                anuncios.extend(self._buscar_una(cabeceras, busqueda, tipo))
        return anuncios

    def _buscar_una(self, cabeceras: dict, busqueda: dict, tipo: str) -> list[Anuncio]:
        resultados: list[Anuncio] = []
        for pagina in range(1, self.max_paginas + 1):
            cuerpo = {
                "country": self.params.get("country", "es"),
                "operation": self.params.get("operation", "sale"),
                "propertyType": tipo,
                "center": busqueda["center"],
                "distance": busqueda.get("distance", 5000),
                "minSize": self.params.get("minSize", 140),
                "maxSize": self.params.get("maxSize", 330),
                "maxItems": 50,
                "numPage": pagina,
                "order": "publicationDate",
                "sort": "desc",
            }
            try:
                datos = self.fetcher.post_json(SEARCH_URL, headers=cabeceras, data=cuerpo)
            except Exception as exc:
                log.warning("[%s] búsqueda '%s'/%s falló: %s", self.id, busqueda.get("nombre"), tipo, exc)
                break
            elementos = datos.get("elementList", [])
            resultados.extend(self._a_anuncio(e, busqueda, tipo) for e in elementos)
            if pagina >= int(datos.get("totalPages", 1)):
                break
        return resultados

    def _a_anuncio(self, e: dict, busqueda: dict, tipo: str) -> Anuncio:
        detalle = e.get("detailedType", {}) or {}
        subtipo = detalle.get("subTypology") or detalle.get("typology") or tipo
        return Anuncio(
            fuente=self.id,
            url=e.get("url", ""),
            titulo=f"{subtipo} {e.get('size', '')} m² en {e.get('address', '')}".strip(),
            descripcion=e.get("description", "") or "",
            precio_eur=float(e["price"]) if e.get("price") else None,
            superficie_m2=float(e["size"]) if e.get("size") else None,
            municipio=e.get("municipality", ""),
            zona=" ".join(x for x in (e.get("district"), e.get("neighborhood")) if x),
            direccion=e.get("address", ""),
            tipologia="nave" if "nave" in str(subtipo).lower() else ("oficina" if tipo == "offices" else "local"),
            operacion="venta" if e.get("operation") == "sale" else e.get("operation", ""),
            referencia=str(e.get("propertyCode", "")),
            lat=e.get("latitude"),
            lon=e.get("longitude"),
            contacto_telefono=(e.get("contactInfo") or {}).get("phone1", {}).get("phoneNumber", "")
            if isinstance((e.get("contactInfo") or {}).get("phone1"), dict)
            else "",
            contacto_nombre=(e.get("contactInfo") or {}).get("commercialName", ""),
            imagenes=[e["thumbnail"]] if e.get("thumbnail") else [],
            extra={
                "fuente_nombre": self.nombre,
                "busqueda": busqueda.get("nombre", ""),
                "planta": e.get("floor"),
                "exterior": e.get("exterior"),
                "estado": e.get("status"),
                "ascensor": e.get("hasLift"),
            },
        )
