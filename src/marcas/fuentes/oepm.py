"""Tomo 1 del BOPI (marcas) en PDF, directamente de la OEPM.

Es la fuente oficial, con dos limitaciones que explican los fallos del
escenario de Make:

* La página de descarga se movió: `sede.oepm.gob.es/bopiweb/...` redirige
  ahora a la portada de oepm.es; la aplicación sigue viva en
  `consultas2.oepm.es/bopiweb/...` mientras termina la migración al BOPI nuevo
  (`sede.oepm.gob.es/bopi/`).
* El cortafuegos de la OEPM rechaza (403) muchas IPs de centros de datos.
  Si el agente corre en uno de ellos, esta fuente cae y manda imarcas.

Y sólo ofrece el BOPI del día: para cubrir una semana hace falta la otra fuente.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import requests

from ..modelos import Solicitud
from . import FuenteNoDisponible, sesion

log = logging.getLogger(__name__)

HOSTS = ("https://consultas2.oepm.es", "https://sede.oepm.gob.es")
FORMULARIO = "/bopiweb/descargaPublicaciones/formBusqueda.action"
DESCARGA = "/bopiweb/DescargaDocumento"

_TOMO1 = re.compile(r"cargaForm\(\s*'([^']+)'\s*,\s*'pdf'\s*,\s*'[^']*TOMO 1", re.I)
_FECHA = re.compile(r"(\d{2})[/-](\d{2})[/-](\d{4})")
# Código INID 540/541 (denominación) seguido de la marca en la línea siguiente.
_DENOMINACION = re.compile(r"\(?54[01]\)?\s*\n\s*(?:\n\s*)*([^\n]{2,200}?)\s*\n")
_NUMERO = re.compile(r"\bM?\s?(\d{7})\b")


def id_tomo1(html: str) -> str | None:
    m = _TOMO1.search(html)
    return m.group(1) if m else None


def fecha_publicacion(html: str, por_defecto: date) -> date:
    for d, m, a in _FECHA.findall(html):
        try:
            return date(int(a), int(m), int(d))
        except ValueError:
            continue
    return por_defecto


def solicitudes_desde_texto(texto: str, fecha: date) -> list[Solicitud]:
    """Saca denominaciones (y su número, si está cerca) del texto del Tomo 1."""
    salida: list[Solicitud] = []
    vistos: set[str] = set()
    for m in _DENOMINACION.finditer(texto):
        nombre = m.group(1).strip()
        if not nombre or nombre.isdigit():
            continue
        previos = _NUMERO.findall(texto[max(0, m.start() - 800) : m.start()])
        numero = previos[-1] if previos else f"OEPM-{len(salida) + 1}"
        if numero in vistos:
            continue
        vistos.add(numero)
        salida.append(Solicitud(numero=numero, denominacion=nombre, fecha_bopi=fecha, fuente="oepm"))
    return salida


def _texto_pdf(datos: bytes) -> str:
    from pypdf import PdfReader  # import perezoso: sólo esta fuente lo necesita

    lector = PdfReader(io.BytesIO(datos))
    return "\n".join(p.extract_text() or "" for p in lector.pages)


def descargar(desde: date, hasta: date, http: requests.Session | None = None) -> list[Solicitud]:
    http = http or sesion()
    errores: list[str] = []
    for host in HOSTS:
        try:
            r = http.get(host + FORMULARIO, timeout=60)
        except requests.RequestException as exc:
            errores.append(f"{host}: {exc}")
            continue
        if r.status_code != 200 or "cargaForm" not in r.text:
            errores.append(f"{host}: HTTP {r.status_code}{' (redirigido)' if r.history else ''}")
            continue
        ident = id_tomo1(r.text)
        if not ident:
            errores.append(f"{host}: no aparece el enlace al Tomo 1")
            continue
        fecha = fecha_publicacion(r.text, por_defecto=date.today())
        if not desde <= fecha <= hasta:
            log.info("oepm: el BOPI publicado (%s) cae fuera de la ventana", fecha)
            return []
        pdf = http.post(
            host + DESCARGA,
            data={
                "idUcm": ident,
                "docTipo": "pdf",
                "descAuditoria": "Descarga TOMO 1 en formato PDF",
                "ipAuditoria": "",
                "varLo": "",
                "userN": "",
            },
            headers={"Referer": host + FORMULARIO},
            timeout=180,
        )
        if not pdf.content.startswith(b"%PDF"):
            errores.append(f"{host}: la descarga no es un PDF (HTTP {pdf.status_code})")
            continue
        salida = solicitudes_desde_texto(_texto_pdf(pdf.content), fecha)
        log.info("oepm: BOPI %s -> %d denominaciones", fecha, len(salida))
        return salida
    raise FuenteNoDisponible("oepm: " + "; ".join(errores))
