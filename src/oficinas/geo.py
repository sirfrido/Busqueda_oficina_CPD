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
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .textutils import normalizar

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"


@dataclass
class ResultadoZona:
    admitida: bool
    municipio: str = ""
    desconocido: bool = False        # el municipio no está en la tabla
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
        # Municipios que no son zona inundable, simplemente quedan lejos para
        # el día a día. Se rechazan con su tiempo medido, para poder decir en
        # el email por qué no aparecen.
        lejos = zonas.get("lejos", {})
        self.motivo_lejos = lejos.get("motivo_por_defecto", "Demasiado lejos")
        self.municipios_lejos: dict[str, dict] = {
            normalizar(m["nombre"]): m for m in lejos.get("municipios", [])
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

        for clave, muni in self.municipios_lejos.items():
            if _menciona(txt, clave):
                minutos = float(muni.get("minutos_coche", 0) or 0)
                detalle = f" ({minutos:.0f} min en coche)" if minutos else ""
                return ResultadoZona(
                    admitida=False,
                    municipio=muni["nombre"],
                    motivo=f"{muni.get('nota') or self.motivo_lejos}{detalle}",
                    minutos_coche=minutos or None,
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

        # Municipio fuera de la tabla. No se da por bueno (así se colaban
        # naves de Gandía o de Ademuz): queda marcado para que el pipeline
        # calcule la distancia real antes de decidir.
        return ResultadoZona(
            admitida=True,
            desconocido=True,
            motivo="Municipio no reconocido: hay que calcular la distancia real",
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


class Geocodificador:
    """Traduce nombres de municipio a coordenadas, con caché en disco.

    Sirve para los municipios que no están en `zonas.yaml`: en vez de darlos
    por buenos (que es como se colaron naves a 100 km), se localizan y se
    mide el tiempo real en coche.
    """

    URL = "https://nominatim.openstreetmap.org/search"
    ESPERA = 1.1     # la política de uso de Nominatim pide 1 petición/segundo

    def __init__(self, cache: Path | str = "data/cache/geo.json", user_agent: str = "BusquedaOficinaCPD/0.1") -> None:
        self.ruta = Path(cache)
        self.user_agent = user_agent
        self._ultimo = 0.0
        try:
            self._cache: dict[str, list[float] | None] = json.loads(self.ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._cache = {}

    def _guardar(self) -> None:
        try:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            self.ruta.write_text(json.dumps(self._cache, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def coordenadas(self, municipio: str) -> tuple[float, float] | None:
        clave = normalizar(municipio)
        if not clave:
            return None
        if clave in self._cache:
            valor = self._cache[clave]
            return (valor[0], valor[1]) if valor else None

        espera = self.ESPERA - (time.monotonic() - self._ultimo)
        if espera > 0:
            time.sleep(espera)
        self._ultimo = time.monotonic()

        consulta = urllib.parse.urlencode(
            {"q": f"{municipio}, Valencia, España", "format": "json", "limit": 1}
        )
        peticion = urllib.request.Request(
            f"{self.URL}?{consulta}", headers={"User-Agent": self.user_agent}
        )
        try:
            with urllib.request.urlopen(peticion, timeout=15) as resp:
                datos = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            return None

        if not datos:
            self._cache[clave] = None
            self._guardar()
            return None
        punto = (float(datos[0]["lat"]), float(datos[0]["lon"]))
        self._cache[clave] = [punto[0], punto[1]]
        self._guardar()
        return punto


def estimar_minutos(distancia: float) -> float:
    """Estimación conservadora cuando sólo hay distancia en línea recta.

    Factor 1,35 de sinuosidad y 32 km/h de media en entorno metropolitano.
    """
    return round((distancia * 1.35) / 32.0 * 60.0, 1)
