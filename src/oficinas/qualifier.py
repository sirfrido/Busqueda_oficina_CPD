"""Cualificador con Claude: lee la ficha y resuelve lo que la heurística deja
en «verificar».

Por qué un LLM aquí: los anuncios describen lo mismo de cien maneras
("salida a terraza superior de uso privativo", "el edificio permite unidades
exteriores en la cubierta"). Un diccionario de palabras no cubre eso; un
modelo sí, y además redacta las preguntas concretas que faltan.

Se usa salida estructurada (`output_config.format`) para que el resultado sea
JSON válido siempre, y caché de prompt en el bloque de sistema porque se
repite idéntico en cada anuncio de la pasada diaria.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .models import Anuncio, Evaluacion
from .senales import preguntas_pendientes

log = logging.getLogger(__name__)

MODELO_POR_DEFECTO = "claude-opus-5"

SISTEMA = """Eres un analista inmobiliario especializado en localizar inmuebles para
centros de proceso de datos (CPD) pequeños en el área de Valencia.

Evalúas anuncios de oficinas, locales en edificios terciarios y naves industriales
pequeñas contra estos requisitos:

1. EDIFICIO: debe ser un edificio de oficinas/terciario o una nave industrial.
   Queda descartado cualquier inmueble en un edificio de viviendas (comunidad de
   vecinos, portal residencial), porque el CPD necesita acometida propia, ruido de
   máquinas y acceso 24x7.
2. CLIMATIZACIÓN: debe poder instalar máquinas de aire acondicionado en la azotea,
   cubierta o patio propio, Y poder AMPLIAR el número de máquinas en el futuro.
3. POTENCIA ELÉCTRICA: debe ser viable llegar a 200-300 kW o más de potencia.
   Señales favorables: centro de transformación propio o cercano, acometida en
   media/alta tensión, suministro industrial, potencia contratada alta, nave en
   polígono, grupo electrógeno.
4. REFORMA: se busca poca obra; se penaliza "a reformar" o estado en bruto.
5. SUPERFICIE: entre 150 y 300 m².

Regla previa a todo lo demás: los portales clasifican mal. Un SOLAR o una
parcela se publican a menudo como "nave industrial en venta", con una foto del
terreno y una línea de descripción. Antes de valorar nada, decide si el anuncio
acredita que existe un inmueble construido: si habla de parcela, solar, suelo
urbanizable o edificable, es "no"; si la ficha es tan escueta que no menciona
ni un elemento constructivo (altura libre, puertas, oficinas, aseos, año de
construcción, metros construidos), es "verificar", nunca "si".

Reglas de juicio:
- Responde "si" o "no" SÓLO con evidencia razonable en el texto.
- Si el anuncio no lo dice, responde "verificar". No inventes.
- Una nave en polígono industrial cumple por naturaleza el punto 1 y casi siempre
  el 2 (cubierta propia); dilo así cuando aplique.
- Un "entresuelo", "planta X" o "local a pie de calle" en una finca con viviendas
  encima es un edificio de viviendas salvo que se indique lo contrario.
- Las preguntas que propongas van en un email real a la propiedad: concretas,
  educadas y en español de España, máximo 6."""

ESQUEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "edificio_oficinas": {"type": "string", "enum": ["si", "no", "verificar"]},
        "en_edificio_viviendas": {"type": "string", "enum": ["si", "no", "verificar"]},
        "cubierta_ampliable": {"type": "string", "enum": ["si", "no", "verificar"]},
        "potencia_ampliable": {"type": "string", "enum": ["si", "no", "verificar"]},
        "poca_reforma": {"type": "string", "enum": ["si", "no", "verificar"]},
        "es_construido": {
            "type": "string",
            "enum": ["si", "no", "verificar"],
            "description": "¿El anuncio acredita que hay un inmueble CONSTRUIDO? "
                           "'no' si describe suelo, solar o parcela; 'verificar' si la "
                           "ficha es tan pobre que no permite afirmarlo",
        },
        "resumen": {"type": "string", "description": "2-3 frases en español sobre el encaje para un CPD"},
        "senales_positivas": {"type": "array", "items": {"type": "string"}},
        "senales_negativas": {"type": "array", "items": {"type": "string"}},
        "preguntas_clave": {"type": "array", "items": {"type": "string"}},
        "confianza": {"type": "number", "description": "0-1: cuánta información útil traía el anuncio"},
    },
    "required": [
        "edificio_oficinas", "en_edificio_viviendas", "cubierta_ampliable",
        "potencia_ampliable", "poca_reforma", "es_construido", "resumen",
        "senales_positivas", "senales_negativas", "preguntas_clave", "confianza",
    ],
    "additionalProperties": False,
}


class Cualificador:
    """Envoltorio del SDK de Anthropic. Si no hay API key, no hace nada."""

    def __init__(
        self,
        modelo: str = MODELO_POR_DEFECTO,
        effort: str = "medium",
        activo: bool = True,
        max_anuncios: int = 40,
    ) -> None:
        self.modelo = modelo
        self.effort = effort
        self.max_anuncios = max_anuncios
        self._cliente = None
        self.activo = activo and bool(
            os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
        )
        if activo and not self.activo:
            log.info("Cualificador LLM desactivado: no hay credenciales de Anthropic")

    @property
    def cliente(self):
        if self._cliente is None:
            import anthropic  # import perezoso: el resto del pipeline no lo necesita

            self._cliente = anthropic.Anthropic()
        return self._cliente

    # -- API pública --------------------------------------------------------
    def evaluar(self, anuncio: Anuncio, previa: Evaluacion) -> Evaluacion:
        """Devuelve la evaluación refinada; ante cualquier fallo, la previa."""
        if not self.activo:
            return previa
        try:
            datos = self._llamar(anuncio)
        except Exception as exc:
            log.warning("Cualificador falló en %s: %s", anuncio.url, exc)
            return previa
        return self._fusionar(previa, datos)

    # -- interno ------------------------------------------------------------
    def _llamar(self, anuncio: Anuncio) -> dict[str, Any]:
        ficha = _ficha(anuncio)
        respuesta = self.cliente.messages.create(
            model=self.modelo,
            max_tokens=4000,
            thinking={"type": "adaptive"},
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": ESQUEMA},
            },
            system=[{"type": "text", "text": SISTEMA, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": f"Analiza este anuncio:\n\n{ficha}"}],
        )
        if getattr(respuesta, "stop_reason", None) == "refusal":
            raise RuntimeError("la petición fue rechazada por el modelo")
        texto = next(b.text for b in respuesta.content if b.type == "text")
        return json.loads(texto)

    @staticmethod
    def _fusionar(previa: Evaluacion, datos: dict[str, Any]) -> Evaluacion:
        ev = Evaluacion(**previa.to_dict())
        for campo in (
            "edificio_oficinas", "en_edificio_viviendas", "cubierta_ampliable",
            "potencia_ampliable", "poca_reforma", "es_construido",
        ):
            valor = datos.get(campo)
            if valor in ("si", "no", "verificar"):
                # La heurística sólo se impone cuando afirma algo y el LLM duda.
                actual = getattr(ev, campo)
                setattr(ev, campo, actual if (valor == "verificar" and actual != "verificar") else valor)
        ev.resumen = datos.get("resumen", "") or ev.resumen
        ev.confianza = float(datos.get("confianza", 0) or 0)
        for señal in datos.get("senales_positivas", []):
            if señal not in ev.senales_positivas:
                ev.senales_positivas.append(señal)
        for señal in datos.get("senales_negativas", []):
            if señal not in ev.senales_negativas:
                ev.senales_negativas.append(señal)
        preguntas = [p for p in datos.get("preguntas_clave", []) if p.strip()]
        ev.preguntas_clave = preguntas or preguntas_pendientes(ev)
        ev.evaluado_por = "heuristica+llm"
        return ev


def _ficha(anuncio: Anuncio) -> str:
    campos = {
        "Título": anuncio.titulo,
        "Fuente": anuncio.extra.get("fuente_nombre", anuncio.fuente),
        "Tipología declarada": anuncio.tipologia,
        "Municipio/zona": " / ".join(x for x in (anuncio.municipio, anuncio.zona) if x),
        "Dirección": anuncio.direccion,
        "Superficie": f"{anuncio.superficie_m2:g} m²" if anuncio.superficie_m2 else "no declarada",
        "Precio": f"{anuncio.precio_eur:,.0f} €".replace(",", ".") if anuncio.precio_eur else "no publicado",
        "URL": anuncio.url,
    }
    cabecera = "\n".join(f"{k}: {v}" for k, v in campos.items() if v)
    return f"{cabecera}\n\nDescripción:\n{anuncio.descripcion[:6000] or '(sin descripción)'}"
