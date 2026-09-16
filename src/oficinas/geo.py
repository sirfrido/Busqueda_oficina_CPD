"""Resolución geográfica: municipio, riesgo de inundación y minutos en coche.

Dos niveles:
  1. Tabla de zonas (config/zonas.yaml): inmediata, sin red, y es la que
     materializa el veto de l'Horta Sud / DANA.
  2. Routing real (OSRM) cuando el anuncio trae coordenadas: afina los
     minutos en coche. Si no hay red o el servicio falla, se usa la tabla.
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .textutils import normalizar

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"


@dataclass
class ResultadoZona:
    admitida: bool
    municipio: str = ""
    motivo: str = ""
    riesgo_inundacion: str = "desconocido"
    minutos_coche: float | None = None
    bonus: float = 0.0
    zona_prime: str = ""


class MapaZonas:
    """Índice consultable construido desde config/zonas.yaml."""

    def __init__(self, zonas: dict[str, Any]) -> None:
        self.raw = zonas
        exc = zonas.get("excluidos", {})
        self.motivo_exclusion = exc.get("motivo_por_defecto", "Zona excluida")
        self.municipios_excluidos: dict[str, dict] = {
            normalizar(m["nombre"]): m for m in exc.get("municipios", [])
        }
        self.barrios_excluidos: list[str] = [normalizar(b) for b in exc.get("barrios_valencia", [])]
        self.terminos_veto: list[str] = [normalizar(t) for t in exc.get("terminos_veto", [])]

        cap = zonas.get("valencia_capital", {})
        self.capital_nombre = cap.get("nombre_municipio", "València")
        self.capital_alias = {normalizar(a) for a in (self.capital_nombre, "Valencia", "València", "Valencia capital")}
        self.zonas_prime: list[dict] = cap.get("zonas_prime", []) + cap.get("poligonos", [])
        self.capital_riesgo = cap.get("riesgo_inundacion", "bajo")

        self.alrededores: dict[str, dict] = {
            normalizar(m["nombre"]): m for m in zonas.get("alrededores", [])
        }

    # -- consulta principal -------------------------------------------------
    def resolver(self, texto_ubicacion: str, max_minutos: float = 20.0) -> ResultadoZona:
        """Decide si una ubicación textual entra en el ámbito de búsqueda."""
        txt = normalizar(texto_ubicacion)
        if not txt:
            return ResultadoZona(admitida=True, motivo="Ubicación no declarada: requiere verificación")

        for termino in self.terminos_veto:
            if termino and termino in txt:
                return ResultadoZona(
                    admitida=False,
                    motivo=f"Término vetado en el anuncio: «{termino}»",
                    riesgo_inundacion="alto",
                )

        for clave, muni in self.municipios_excluidos.items():
            if _menciona(txt, clave):
                return ResultadoZona(
                    admitida=False,
                    municipio=muni["nombre"],
                    motivo=muni.get("motivo") or self.motivo_exclusion,
                    riesgo_inundacion=muni.get("riesgo_inundacion", "alto"),
                )

        for clave, muni in self.alrededores.items():
            if _menciona(txt, clave):
                minutos = float(muni.get("minutos_coche", 99))
                if minutos > max_minutos:
                    return ResultadoZona(
                        admitida=False,
                        municipio=muni["nombre"],
                        motivo=f"A {minutos:.0f} min en coche (máximo {max_minutos:.0f})",
                        riesgo_inundacion=muni.get("riesgo_inundacion", "desconocido"),
                        minutos_coche=minutos,
                    )
                return ResultadoZona(
                    admitida=True,
                    municipio=muni["nombre"],
                    riesgo_inundacion=muni.get("riesgo_inundacion", "desconocido"),
                    minutos_coche=minutos,
                    bonus=float(muni.get("bonus", 0)),
                )

        if any(_menciona(txt, alias) for alias in self.capital_alias):
            for barrio in self.barrios_excluidos:
                if barrio and barrio in txt:
                    return ResultadoZona(
                        admitida=False,
                        municipio=self.capital_nombre,
                        motivo=f"Barrio descartado de València: «{barrio}»",
                        riesgo_inundacion="alto",
                    )
            bonus, prime = 0.0, ""
            for z in self.zonas_prime:
                if normalizar(z["nombre"]) in txt:
                    if float(z.get("bonus", 0)) > bonus:
                        bonus, prime = float(z.get("bonus", 0)), z["nombre"]
            return ResultadoZona(
                admitida=True,
                municipio=self.capital_nombre,
                riesgo_inundacion=self.capital_riesgo,
                minutos_coche=0.0,
                bonus=bonus,
                zona_prime=prime,
            )

        return ResultadoZona(
            admitida=True,
            motivo="Municipio no reconocido: pendiente de verificar distancia y riesgo",
            riesgo_inundacion="desconocido",
        )


def _menciona(texto: str, clave: str) -> bool:
    """Coincidencia por palabra completa para que 'albal' no case con 'albalat'."""
    if not clave:
        return False
    idx = 0
    while (idx := texto.find(clave, idx)) != -1:
        antes = texto[idx - 1] if idx > 0 else " "
        despues = texto[idx + len(clave)] if idx + len(clave) < len(texto) else " "
        if not antes.isalnum() and not despues.isalnum():
            return True
        idx += len(clave)
    return False


def distancia_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distancia haversine en km."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def minutos_en_coche(origen: tuple[float, float], destino: tuple[float, float], timeout: float = 12.0) -> float | None:
    """Minutos en coche reales vía OSRM. Devuelve None si no hay servicio."""
    url = OSRM_URL.format(lat1=origen[0], lon1=origen[1], lat2=destino[0], lon2=destino[1])
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
        rutas = datos.get("routes") or []
        if not rutas:
            return None
        return round(float(rutas[0]["duration"]) / 60.0, 1)
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError):
        return None


def estimar_minutos(distancia: float) -> float:
    """Estimación conservadora cuando sólo hay distancia en línea recta.

    Factor 1,35 de sinuosidad y 32 km/h de media en entorno metropolitano.
    """
    return round((distancia * 1.35) / 32.0 * 60.0, 1)
