"""Mirar las fotos antes de recomendar nada.

La lección del solar de Burjassot: la ficha decía "Nave industrial en venta"
y las fotos eran un terreno con maleza. Ningún análisis del texto habría
salvado eso — pero una mirada a la primera foto, sí.

Este módulo descarga las fotos del anuncio y se las enseña a Claude con una
pregunta muy concreta: ¿qué se ve aquí, una nave, una oficina o un solar?
Se usa sólo con los finalistas, porque cuesta dinero y tiempo.

Sin credenciales de Anthropic no hace nada y el pipeline sigue su curso: la
verificación por texto (verificacion.py) ya evita lo peor.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import requests

from .models import Anuncio

log = logging.getLogger(__name__)

MODELO_POR_DEFECTO = "claude-opus-5"
MAX_FOTOS = 3
TIPOS_MIME = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG": "image/png",
    b"RIFF": "image/webp",
    b"GIF8": "image/gif",
}

SISTEMA = """Miras fotos de anuncios inmobiliarios y dices lo que de verdad se ve,
sin dejarte llevar por el título del anuncio.

El encargo es localizar una NAVE INDUSTRIAL pequeña o una OFICINA en un edificio
de oficinas, para la sede de una empresa y un pequeño CPD (sala de servidores).

Los portales clasifican mal: es habitual que un SOLAR o una parcela se publiquen
como "nave industrial en venta". Tu trabajo es cortar eso de raíz.

Fíjate sobre todo en:
- ¿Hay una construcción, o es terreno (maleza, tierra, vallado, sin edificio)?
- Si hay nave: ¿está en pie y cerrada, o es una ruina o un esqueleto?
- Si es oficina: ¿se ve un edificio terciario o parece una vivienda o un bajo
  comercial con escaparate a la calle?
- ¿Se ve la cubierta o azotea? ¿Parece transitable y con sitio para máquinas de
  aire acondicionado?
- Estado aparente: listo para entrar, uso normal, o hay que reformar.

Si las fotos no permiten afirmar algo, dilo: "no se puede saber" es una
respuesta correcta y útil. No inventes."""

ESQUEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tipo": {
            "type": "string",
            "enum": ["nave", "oficina", "local", "solar", "vivienda", "ruina", "no_se_puede_saber"],
        },
        "hay_construccion": {"type": "string", "enum": ["si", "no", "no_se_puede_saber"]},
        "cubierta_visible": {"type": "string", "enum": ["si", "no", "no_se_puede_saber"]},
        "estado_aparente": {
            "type": "string",
            "enum": ["listo_para_entrar", "uso_normal", "a_reformar", "no_se_puede_saber"],
        },
        "descripcion": {"type": "string", "description": "Una o dos frases de lo que se ve"},
        "coincide_con_el_anuncio": {"type": "boolean"},
    },
    "required": [
        "tipo", "hay_construccion", "cubierta_visible", "estado_aparente",
        "descripcion", "coincide_con_el_anuncio",
    ],
    "additionalProperties": False,
}


@dataclass
class Vistazo:
    tipo: str = "no_se_puede_saber"
    hay_construccion: str = "no_se_puede_saber"
    cubierta_visible: str = "no_se_puede_saber"
    estado_aparente: str = "no_se_puede_saber"
    descripcion: str = ""
    coincide_con_el_anuncio: bool = True
    fotos_vistas: int = 0
    avisos: list[str] = field(default_factory=list)

    @property
    def desmiente_el_anuncio(self) -> bool:
        """¿Las fotos contradicen lo que dice el anuncio?"""
        return self.tipo in ("solar", "vivienda", "ruina") or self.hay_construccion == "no"


def _mime(datos: bytes) -> str | None:
    for firma, mime in TIPOS_MIME.items():
        if datos.startswith(firma):
            return mime
    return None


def descargar_fotos(anuncio: Anuncio, maximo: int = MAX_FOTOS, timeout: float = 20.0) -> list[tuple[str, bytes]]:
    """Descarga las fotos del anuncio (las que se puedan)."""
    salida: list[tuple[str, bytes]] = []
    cabeceras = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Referer": anuncio.url,
    }
    for url in anuncio.imagenes[: maximo * 2]:
        if len(salida) >= maximo:
            break
        try:
            resp = requests.get(url, headers=cabeceras, timeout=timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.debug("no se pudo descargar %s: %s", url, exc)
            continue
        mime = _mime(resp.content)
        if mime and len(resp.content) > 5000:      # descarta iconos y placeholders
            salida.append((mime, resp.content))
    return salida


class OjoCritico:
    """Mira las fotos del anuncio y dice si cuadra con lo que promete."""

    def __init__(self, modelo: str = MODELO_POR_DEFECTO, activo: bool = True, effort: str = "low") -> None:
        self.modelo = modelo
        self.effort = effort
        self._cliente = None
        self.activo = activo and bool(
            os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
        )

    @property
    def cliente(self):
        if self._cliente is None:
            import anthropic

            self._cliente = anthropic.Anthropic()
        return self._cliente

    def mirar(self, anuncio: Anuncio) -> Vistazo | None:
        if not self.activo or not anuncio.imagenes:
            return None
        fotos = descargar_fotos(anuncio)
        if not fotos:
            return None
        try:
            datos = self._preguntar(anuncio, fotos)
        except Exception as exc:
            log.warning("No se pudieron analizar las fotos de %s: %s", anuncio.url, exc)
            return None
        vistazo = Vistazo(**datos, fotos_vistas=len(fotos))
        if vistazo.desmiente_el_anuncio:
            vistazo.avisos.append(
                f"Las fotos no cuadran con el anuncio: se ve {vistazo.tipo}. {vistazo.descripcion}"
            )
        return vistazo

    def _preguntar(self, anuncio: Anuncio, fotos: list[tuple[str, bytes]]) -> dict[str, Any]:
        contenido: list[dict[str, Any]] = []
        for mime, bruto in fotos:
            contenido.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime,
                        "data": base64.standard_b64encode(bruto).decode("utf-8"),
                    },
                }
            )
        contenido.append(
            {
                "type": "text",
                "text": (
                    f"Estas fotos vienen de un anuncio titulado «{anuncio.titulo}»"
                    f" ({anuncio.superficie_m2 or '?'} m², {anuncio.municipio}).\n"
                    f"Descripción publicada: {anuncio.descripcion[:600] or '(sin descripción)'}\n\n"
                    f"¿Qué se ve realmente en las fotos?"
                ),
            }
        )
        respuesta = self.cliente.messages.create(
            model=self.modelo,
            max_tokens=2000,
            thinking={"type": "adaptive"},
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": ESQUEMA},
            },
            system=[{"type": "text", "text": SISTEMA, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": contenido}],
        )
        if getattr(respuesta, "stop_reason", None) == "refusal":
            raise RuntimeError("petición rechazada")
        texto = next(b.text for b in respuesta.content if b.type == "text")
        return json.loads(texto)
