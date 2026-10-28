"""Listados diarios del BOPI publicados por imarcas.com.

Cada día hábil publican una entrada «Patentes y Marcas. OEPM. DD-MM-AAAA» con
una tabla de las solicitudes de marca de ese BOPI: número, denominación y
clases de Niza. No es la fuente oficial, pero es HTML limpio, cubre cualquier
fecha pasada y no bloquea servidores en la nube (la OEPM sí).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from ..modelos import Solicitud
from . import FuenteNoDisponible, sesion

log = logging.getLogger(__name__)

CATEGORIA = "https://www.imarcas.com/registrodemarcas/category/bopi/"
# El slug lleva la fecha del BOPI; a veces con sufijo («-2») si se republica.
_ENTRADA = re.compile(r"https://www\.imarcas\.com/registrodemarcas/patentes-y-marcas-oepm-(\d{2})-(\d{2})-(\d{4})(?:-\d+)?/")
MAX_PAGINAS = 6


def entradas(html: str) -> dict[date, str]:
    """Fecha del BOPI -> URL de su entrada, a partir de una página de la categoría."""
    salida: dict[date, str] = {}
    for m in _ENTRADA.finditer(html):
        dia, mes, anio = (int(x) for x in m.groups())
        try:
            salida.setdefault(date(anio, mes, dia), m.group(0))
        except ValueError:
            continue
    return salida


def solicitudes(html: str, fecha: date, url: str = "") -> list[Solicitud]:
    """Lee la tabla «núm. / denominación / clases Niza» de una entrada."""
    sopa = BeautifulSoup(html, "lxml")
    salida: list[Solicitud] = []
    for tabla in sopa.find_all("table"):
        cabecera = [c.get_text(" ", strip=True).lower() for c in tabla.find_all("th")]
        if not any("denominaci" in c for c in cabecera):
            continue
        for fila in tabla.find_all("tr"):
            celdas = [c.get_text(" ", strip=True) for c in fila.find_all("td")]
            if len(celdas) < 2 or not celdas[0]:
                continue
            clases = [int(x) for x in re.findall(r"\d+", celdas[2])] if len(celdas) > 2 else []
            salida.append(
                Solicitud(
                    numero=celdas[0],
                    denominacion=celdas[1],
                    fecha_bopi=fecha,
                    clases=clases,
                    fuente="imarcas",
                    url=url,
                )
            )
    return salida


def descargar(
    desde: date, hasta: date, http: requests.Session | None = None, saltar: set[date] = frozenset()
) -> list[Solicitud]:
    http = http or sesion()
    urls: dict[date, str] = {}
    for pagina in range(1, MAX_PAGINAS + 1):
        url = CATEGORIA if pagina == 1 else f"{CATEGORIA}page/{pagina}/"
        try:
            r = http.get(url, timeout=30)
            r.raise_for_status()
        except requests.RequestException as exc:
            if pagina == 1:
                raise FuenteNoDisponible(f"imarcas: {exc}") from exc
            break
        encontradas = entradas(r.text)
        urls.update({f: u for f, u in encontradas.items() if desde <= f <= hasta and f not in saltar})
        if not encontradas or min(encontradas) < desde:
            break

    salida: list[Solicitud] = []
    for fecha, url in sorted(urls.items()):
        try:
            r = http.get(url, timeout=30)
            r.raise_for_status()
        except requests.RequestException as exc:
            log.warning("imarcas: no se pudo leer el BOPI del %s: %s", fecha, exc)
            continue
        del_dia = solicitudes(r.text, fecha, url)
        log.info("imarcas: BOPI %s -> %d solicitudes", fecha, len(del_dia))
        salida.extend(del_dia)
    return salida
