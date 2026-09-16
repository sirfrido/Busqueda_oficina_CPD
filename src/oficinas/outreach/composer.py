"""Redacción del email a la propiedad.

Plantilla fija + las preguntas concretas que ese anuncio dejó abiertas.
Es deliberadamente sobrio: se presenta el uso real (oficina + CPD pequeño),
porque ocultarlo sólo adelanta un "no" en la segunda visita.
"""

from __future__ import annotations

from typing import Any

from ..models import Anuncio, Evaluacion
from ..textutils import normalizar

# Cada pregunta cubre un tema; sólo se envía una por tema para que el email a
# la propiedad no repita la misma duda con otras palabras.
TEMAS = {
    "potencia": ("potencia", "kw", "transformacion", "electric", "acometida"),
    "cubierta": ("cubierta", "azotea", "climatiz", "aire acondicionado", "maquinas"),
    "edificio": ("edificio", "viviendas", "vecinos", "terciario", "24x7", "24 x 7"),
    "reforma": ("reforma", "estado", "obra"),
    "acceso": ("montacargas", "muelle", "acceso", "grupo electrogeno"),
}


def _tema(pregunta: str) -> str:
    txt = normalizar(pregunta)
    for tema, claves in TEMAS.items():
        if any(clave in txt for clave in claves):
            return tema
    return txt[:40]


def _titulo_corto(anuncio: Anuncio) -> str:
    base = anuncio.titulo or f"inmueble en {anuncio.municipio or 'Valencia'}"
    return base[:70].strip().rstrip(",.")


def componer_contacto(
    anuncio: Anuncio,
    ev: Evaluacion,
    plantillas: dict[str, Any],
    firma_nombre: str,
    firma_empresa: str = "",
    firma_contacto: str = "",
    max_preguntas: int = 6,
) -> tuple[str, str]:
    """Devuelve (asunto, cuerpo) del email dirigido a la propiedad/agencia."""
    cfg = plantillas.get("contacto_propiedad", {})
    imprescindibles: list[str] = list(cfg.get("preguntas_imprescindibles", []))

    preguntas: list[str] = []
    temas_cubiertos: set[str] = set()
    for pregunta in imprescindibles + list(ev.preguntas_clave):
        pregunta = pregunta.strip()
        if not pregunta:
            continue
        tema = _tema(pregunta)
        if tema in temas_cubiertos:
            continue
        temas_cubiertos.add(tema)
        preguntas.append(pregunta)
        if len(preguntas) >= max_preguntas:
            break

    bloque = "\n".join(f"  {i}. {p}" for i, p in enumerate(preguntas, 1))
    fuente = anuncio.extra.get("fuente_nombre", anuncio.fuente)

    asunto = cfg.get("asunto", "Interés en {titulo_corto}").format(
        titulo_corto=_titulo_corto(anuncio), fuente=fuente, municipio=anuncio.municipio
    )
    cuerpo = cfg.get("cuerpo", "").format(
        titulo_corto=_titulo_corto(anuncio),
        url=anuncio.url,
        fuente=fuente,
        municipio=anuncio.municipio or "Valencia",
        preguntas=bloque,
        firma_nombre=firma_nombre,
        firma_empresa=f"\n{firma_empresa}" if firma_empresa else "",
        firma_contacto=firma_contacto,
    )
    return asunto.strip(), cuerpo.strip() + "\n"
