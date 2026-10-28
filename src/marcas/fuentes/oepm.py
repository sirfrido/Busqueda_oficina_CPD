"""Tomo 1 del BOPI (marcas) en PDF, directamente de la OEPM.

Es la fuente oficial. La aplicación antigua (`.../bopiweb/descargaPublicaciones/
formBusqueda.action`, la que usaba el escenario de Make) se retiró en octubre de
2026: ahora responde 410. La nueva (`sede.oepm.gob.es/bopi/`) es una aplicación
web que pide los datos a una API pública, sin registro:

    GET  /apibopiweb/publicacionesBopiTomoYFecha/1/DD-MM-AAAA  -> ¿hay BOPI ese día?
    POST /apibopiweb/descargarDocumentoPdfCompleto?fecha=DD-MM-AAAA&tomo=1 -> PDF

El XML, que sería más cómodo, exige iniciar sesión, así que se lee el PDF.

Limitación: en las marcas mixtas o gráficas (código 546) la denominación va
dentro de la imagen y el PDF no la trae en texto; esas solicitudes salen como
«(marca gráfica o mixta)».
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date, timedelta
from pathlib import Path

import requests

from ..modelos import Solicitud
from . import FuenteNoDisponible, sesion

log = logging.getLogger(__name__)

API = "https://sede.oepm.gob.es/apibopiweb"
# Si se fija (revisar --guardar-pdf), cada Tomo 1 descargado se guarda aquí para
# sacar después las hojas de logotipos (marcas.logos).
GUARDAR_PDF: Path | None = None
SIN_DENOMINACION = "(marca gráfica o mixta)"

# Cabecera de página que el texto del PDF intercala entre los campos; la siguen
# el número de página suelto y el código CVE.
_CABECERA = re.compile(r"^\d{1,2} DE [A-ZÁÉÍÓÚ]+ DE \d{4} - BOLETÍN OFICIAL DE LA PROPIEDAD INDUSTRIAL")
_CVE = re.compile(r"^CVE-BOPI-\S+$")
# Fin de una sección «SOLICITUDES»: el siguiente apartado del tomo.
_FIN_SECCION = re.compile(r"^(SUSPENSOS DE SOLICITUD|SOLICITUDES TENIDAS POR DESISTIDAS|\d{1,2}\. [A-ZÁÉÍÓÚ]{4,})")
_EXPEDIENTE = re.compile(r"^210\s+([MN])\s+(\d{5,8})", re.M)
_CLASE = re.compile(r"^(?:511\s+)?(\d{1,2})\s+[A-ZÁÉÍÓÚÑ(]", re.M)


def _fecha(d: date) -> str:
    return f"{d:%d-%m-%Y}"


def secciones_de_solicitudes(texto: str) -> str:
    """Sólo los apartados «SOLICITUDES» (marcas, nombres comerciales,
    internacionales): las únicas publicaciones contra las que cabe oposición."""
    dentro, salida, tras_cabecera = False, [], False
    for linea in texto.splitlines():
        limpia = linea.strip()
        if _CABECERA.match(limpia):
            tras_cabecera = True
            continue
        if _CVE.match(limpia):  # cierra la cabecera: lo que sigue ya es contenido
            tras_cabecera = False
            continue
        if tras_cabecera and limpia.isdigit():  # número de página, no un código INID
            continue
        tras_cabecera = False
        if limpia == "SOLICITUDES":
            dentro = True
            continue
        if dentro and _FIN_SECCION.match(limpia):
            dentro = False
        if dentro:
            salida.append(limpia)
    return "\n".join(salida)


def solicitudes_desde_texto(texto: str, fecha: date) -> list[Solicitud]:
    cuerpo = secciones_de_solicitudes(texto)
    marcas = list(_EXPEDIENTE.finditer(cuerpo))
    salida: list[Solicitud] = []
    for i, m in enumerate(marcas):
        ficha = cuerpo[m.end() : marcas[i + 1].start() if i + 1 < len(marcas) else len(cuerpo)]
        lineas = ficha.splitlines()
        nombre = ""
        if "541" in lineas:
            siguientes = [l for l in lineas[lineas.index("541") + 1 :] if l.strip()]
            nombre = siguientes[0].strip() if siguientes else ""
        clases: list[int] = []
        if "511" in ficha:
            for c in _CLASE.findall(ficha[ficha.index("511") :]):
                if 1 <= int(c) <= 45 and int(c) not in clases:
                    clases.append(int(c))
        salida.append(
            Solicitud(
                numero=m.group(2),
                denominacion=nombre or SIN_DENOMINACION,
                fecha_bopi=fecha,
                clases=clases,
                fuente="oepm",
            )
        )
    return salida


def _texto_pdf(datos: bytes) -> str:
    from pypdf import PdfReader  # import perezoso: sólo esta fuente lo necesita

    logging.getLogger("pypdf").setLevel(logging.ERROR)  # avisa de cada objeto mal enlazado
    lector = PdfReader(io.BytesIO(datos))
    return "\n".join(p.extract_text() or "" for p in lector.pages)


def hay_bopi(d: date, http: requests.Session) -> bool:
    r = http.get(f"{API}/publicacionesBopiTomoYFecha/1/{_fecha(d)}", timeout=60)
    r.raise_for_status()
    return bool(r.text.strip()) and bool(r.json().get("idPdfUcm"))


def descargar(
    desde: date, hasta: date, http: requests.Session | None = None, saltar: set[date] = frozenset()
) -> list[Solicitud]:
    http = http or sesion()
    salida: list[Solicitud] = []
    errores: list[str] = []
    d = desde
    while d <= hasta:
        if d.weekday() < 5 and d not in saltar:  # el BOPI sale de lunes a viernes
            try:
                if hay_bopi(d, http):
                    pdf = http.post(
                        f"{API}/descargarDocumentoPdfCompleto",
                        params={"fecha": _fecha(d), "tomo": 1},
                        timeout=300,
                    )
                    if not pdf.content.startswith(b"%PDF"):
                        raise RuntimeError(f"la descarga no es un PDF (HTTP {pdf.status_code})")
                    if GUARDAR_PDF:
                        GUARDAR_PDF.mkdir(parents=True, exist_ok=True)
                        (GUARDAR_PDF / f"{_fecha(d)}.pdf").write_bytes(pdf.content)
                    del_dia = solicitudes_desde_texto(_texto_pdf(pdf.content), d)
                    log.info("oepm: BOPI %s -> %d solicitudes", d, len(del_dia))
                    salida.extend(del_dia)
            except (requests.RequestException, ValueError, RuntimeError) as exc:
                errores.append(f"{d:%d/%m}: {exc}")
        d += timedelta(days=1)
    if errores and not salida:
        raise FuenteNoDisponible("oepm: " + "; ".join(errores))
    for e in errores:
        log.warning("oepm: %s", e)
    return salida
