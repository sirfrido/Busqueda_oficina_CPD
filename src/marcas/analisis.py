"""Análisis de riesgo de confusión con Claude.

Claude recibe TODAS las denominaciones de la semana (no sólo lo que el cribado
local marca), porque la similitud conceptual —«BAJOS FONDOS STUDIO» frente a
HAMPA— no la detecta ninguna distancia entre letras.

Control de calidad con canario: se mezcla una denominación inventada que se
parece mucho a la marca, con un número de solicitud de aspecto normal y sin
decirle al modelo cuál es. Si no la detecta, el informe lo dice. (En Make el
prompt anunciaba el canario por su nombre, así que «detectarlo» no probaba
nada.)
"""

from __future__ import annotations

import json
import logging
import os
import random
from typing import Any

from .modelos import Alerta, ConfigMarcas, Solicitud

log = logging.getLogger(__name__)

ESQUEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "alertas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "numero": {"type": "string", "description": "Número de solicitud tal cual aparece en la lista"},
                    "riesgo": {"type": "string", "enum": ["alto", "medio", "bajo"]},
                    "similitud": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["fonetica", "grafica", "conceptual"]},
                    },
                    "motivo": {"type": "string", "description": "Una o dos frases, en español"},
                    "recomendacion": {
                        "type": "string",
                        "description": "Qué haría un agente de la propiedad industrial: oponerse, vigilar o descartar",
                    },
                },
                "required": ["numero", "riesgo", "similitud", "motivo", "recomendacion"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["alertas"],
    "additionalProperties": False,
}


def sistema(cfg: ConfigMarcas) -> str:
    clases = (
        ", ".join(str(c) for c in cfg.clases_niza)
        if cfg.clases_niza
        else "no indicadas; considera relevantes las de un estudio creativo (9, 16, 35, 41, 42)"
    )
    return f"""Eres un agente de la propiedad industrial en España. Vigilas el Boletín
Oficial de la Propiedad Industrial (BOPI) para el titular de la marca «{cfg.marca}»
(elemento distintivo: «{cfg.nucleo}»), que tiene dos meses desde cada publicación
para presentar oposición (art. 19 de la Ley 17/2001 de Marcas).

Actividad del titular: {cfg.actividad or "no indicada"}
Clases de Niza del titular: {clases}

Recibirás la lista de solicitudes publicadas: número | denominación | clases.
Devuelve SOLO las que puedan generar riesgo de confusión con «{cfg.marca}»:

- Fonética: suena parecido en español o en inglés (la H es muda; JAMPA, AMPA,
  HANPA, HAMPAH...).
- Gráfica: se escribe parecido (letras cambiadas, añadidas o quitadas,
  separaciones como «HAM PA», números por letras).
- Conceptual: evoca la misma idea («el hampa»: bajos fondos, mafia, maleantes,
  underground) en un contexto que pueda asociarse con el titular.

Criterios de juicio:
- «STUDIO», «ESTUDIO», «DESIGN» y similares son genéricos: compartirlos no basta.
- El riesgo sube si las clases coinciden o son afines a las del titular; baja
  mucho si los productos o servicios no tienen relación, pero no desaparece si
  el parecido del nombre es muy alto.
- riesgo «alto» = recomendarías estudiar la oposición; «medio» = vigilar o
  consultar; «bajo» = parecido remoto, sólo para que conste.
- Ante la duda entre incluir o no una denominación muy parecida, inclúyela con
  riesgo bajo: un falso positivo cuesta un vistazo; uno perdido, la marca.
- Si nada se parece, devuelve la lista de alertas vacía. No inventes números:
  usa exactamente los de la lista."""


class Analizador:
    def __init__(self, cfg: ConfigMarcas, cliente: Any = None) -> None:
        self.cfg = cfg
        self._cliente = cliente
        self.activo = cliente is not None or bool(
            os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
        )

    @property
    def cliente(self):
        if self._cliente is None:
            import anthropic

            self._cliente = anthropic.Anthropic()
        return self._cliente

    def analizar(self, solicitudes: list[Solicitud]) -> tuple[list[dict[str, Any]], bool | None]:
        """Devuelve (alertas en bruto, ¿detectó el canario?).

        El canario es None si no se ha podido comprobar (sin canario configurado).
        """
        lista = list(solicitudes)
        numero_canario = ""
        if self.cfg.canario and lista:
            # Número de 7 cifras como los reales, que no choque con ninguno.
            existentes = {s.numero for s in lista}
            while not numero_canario or numero_canario in existentes:
                numero_canario = str(random.randint(4_000_000, 4_999_999))
            canario = Solicitud(numero_canario, self.cfg.canario, lista[0].fecha_bopi, [41, 42])
            lista.insert(random.randrange(len(lista) + 1), canario)

        alertas: list[dict[str, Any]] = []
        for i in range(0, len(lista), self.cfg.lote):
            alertas += self._llamar(lista[i : i + self.cfg.lote])

        detectado = None
        if numero_canario:
            detectado = any(a.get("numero") == numero_canario for a in alertas)
            alertas = [a for a in alertas if a.get("numero") != numero_canario]
        return alertas, detectado

    def _llamar(self, lote: list[Solicitud]) -> list[dict[str, Any]]:
        lineas = "\n".join(
            f"{s.numero} | {s.denominacion} | {', '.join(map(str, s.clases)) or '-'}" for s in lote
        )
        respuesta = self.cliente.beta.messages.create(
            model=self.cfg.modelo,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            thinking={"type": "adaptive"},
            output_config={
                "effort": self.cfg.effort,
                "format": {"type": "json_schema", "schema": ESQUEMA},
            },
            system=[{"type": "text", "text": sistema(self.cfg), "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": f"Solicitudes publicadas ({len(lote)}):\n\n{lineas}"}],
        )
        if respuesta.stop_reason == "refusal":
            raise RuntimeError("el modelo rechazó la petición")
        if respuesta.stop_reason == "max_tokens":
            raise RuntimeError("respuesta cortada por max_tokens: baja `lote` en config/marcas.yaml")
        texto = next(b.text for b in respuesta.content if b.type == "text")
        return json.loads(texto).get("alertas", [])


def combinar(
    solicitudes: list[Solicitud],
    del_modelo: list[dict[str, Any]],
    locales: dict[str, tuple[float, str]],
    umbral_local: float,
) -> tuple[list[Alerta], list[Alerta]]:
    """(alertas, coincidencias locales que el modelo no marcó).

    Las segundas van al informe en un bloque aparte: nada se descarta en silencio.
    """
    por_numero = {s.numero: s for s in solicitudes}
    alertas: list[Alerta] = []
    for a in del_modelo:
        s = por_numero.get(str(a.get("numero", "")).strip())
        if not s:
            log.warning("El modelo citó un número que no está en la lista: %s", a.get("numero"))
            continue
        alertas.append(
            Alerta(
                solicitud=s,
                riesgo=a.get("riesgo", "bajo"),
                similitud=list(a.get("similitud", [])),
                motivo=a.get("motivo", ""),
                recomendacion=a.get("recomendacion", ""),
                puntuacion_local=locales.get(s.numero, (0.0, ""))[0],
            )
        )
    marcadas = {a.solicitud.numero for a in alertas}
    sin_marcar = [
        Alerta(
            solicitud=por_numero[n],
            riesgo="local",
            similitud=[],
            motivo=motivo,
            puntuacion_local=p,
        )
        for n, (p, motivo) in locales.items()
        if p >= umbral_local and n not in marcadas and n in por_numero
    ]
    orden = {"alto": 0, "medio": 1, "bajo": 2}
    alertas.sort(key=lambda a: (orden.get(a.riesgo, 3), -a.puntuacion_local))
    sin_marcar.sort(key=lambda a: -a.puntuacion_local)
    return alertas, sin_marcar
