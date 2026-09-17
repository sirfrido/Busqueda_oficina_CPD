"""Modelos de datos del pipeline.

Flujo: Anuncio (crudo, de una fuente) -> Evaluacion (señales + LLM)
       -> Candidato (anuncio + evaluacion + puntuacion).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Literal

Veredicto = Literal["si", "no", "verificar"]


@dataclass
class Anuncio:
    """Anuncio tal y como lo devuelve una fuente, ya normalizado."""

    fuente: str
    url: str
    titulo: str = ""
    descripcion: str = ""
    precio_eur: float | None = None
    superficie_m2: float | None = None
    municipio: str = ""
    zona: str = ""
    direccion: str = ""
    tipologia: str = ""                      # oficina | nave | local | ...
    operacion: str = "venta"
    referencia: str = ""
    lat: float | None = None
    lon: float | None = None
    contacto_nombre: str = ""
    contacto_email: str = ""
    contacto_telefono: str = ""
    imagenes: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    visto_en: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def texto_completo(self) -> str:
        partes = [self.titulo, self.descripcion, self.direccion, self.zona, self.municipio]
        return " \n".join(p for p in partes if p)

    @property
    def id(self) -> str:
        """Identificador estable del anuncio (fuente + url normalizada)."""
        base = f"{self.fuente}|{self.url.split('?')[0].rstrip('/').lower()}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]

    @property
    def precio_m2(self) -> float | None:
        if self.precio_eur and self.superficie_m2:
            return round(self.precio_eur / self.superficie_m2, 2)
        return None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Evaluacion:
    """Resultado de evaluar un anuncio contra los requisitos del CPD."""

    edificio_oficinas: Veredicto = "verificar"
    cubierta_ampliable: Veredicto = "verificar"
    potencia_ampliable: Veredicto = "verificar"
    poca_reforma: Veredicto = "verificar"
    en_edificio_viviendas: Veredicto = "verificar"
    # Oficina en planta alta / última planta: menos tubería hasta las máquinas
    # de la azotea y menos exposición al agua.
    planta_alta: Veredicto = "verificar"
    # Bajo comercial, local a pie de calle o entresuelo: descartado.
    bajo_o_calle: Veredicto = "verificar"
    # ¿El anuncio acredita que hay algo CONSTRUIDO? Un solar publicado como
    # "nave industrial" pasa metros, precio y zona sin despeinarse.
    es_construido: Veredicto = "verificar"
    avisos_ficha: list[str] = field(default_factory=list)
    zona_admitida: bool = True
    minutos_coche: float | None = None
    riesgo_inundacion: str = "desconocido"     # alto | medio | bajo | desconocido
    motivo_descarte: str = ""
    senales_positivas: list[str] = field(default_factory=list)
    senales_negativas: list[str] = field(default_factory=list)
    preguntas_clave: list[str] = field(default_factory=list)
    resumen: str = ""
    confianza: float = 0.0                     # 0-1, la aporta el cualificador LLM
    evaluado_por: str = "heuristica"           # heuristica | llm | heuristica+llm

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Candidato:
    anuncio: Anuncio
    evaluacion: Evaluacion
    puntuacion: float = 0.0
    desglose: dict[str, float] = field(default_factory=dict)
    descartado: bool = False
    # Pasa los filtros pero el anuncio no da para recomendarlo: va al bloque
    # "Casi" con la advertencia, nunca como candidato de primera.
    solo_casi: bool = False

    @property
    def id(self) -> str:
        return self.anuncio.id

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "puntuacion": self.puntuacion,
            "descartado": self.descartado,
            "solo_casi": self.solo_casi,
            "desglose": self.desglose,
            "anuncio": self.anuncio.to_dict(),
            "evaluacion": self.evaluacion.to_dict(),
        }
