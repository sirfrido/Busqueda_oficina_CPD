"""Bandas y rampas: el cribado que no tira nada por un pelo.

La idea es sencilla y es la que rige todo el agente:

    Hay muy pocas cosas que no tienen arreglo (filtros.py). Todo lo demás
    es cuestión de grado. Un inmueble de 310 m² no es "de 300 m² fallado":
    es de 300 m² con un punto menos. Un anuncio a 430.000 € no está fuera
    de un presupuesto de 400.000: está a un 7 % de negociación.

Cada eje (superficie, precio, distancia) define cuatro puntos:

    veto_min   gris_min        banda plena        gris_max   veto_max
      |-----------|==================================|----------|
      fuera      resta mucho    no resta      resta mucho     fuera
                  ↘ rampa                      rampa ↙

Y cada vez que un inmueble sale de la banda plena se anota un "exceso" con
su frase en castellano ("se pasa 30.000 €", "le faltan 12 m²"). Los excesos
sirven para dos cosas: explicarle al usuario por qué algo entra rozando, y
aplicar la regla de compensación — pasarse en un eje se perdona, pasarse en
dos exige que el resto sea sobresaliente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import Anuncio, Evaluacion


@dataclass
class Bandas:
    penalizaciones: dict[str, float] = field(default_factory=dict)
    excesos: list[str] = field(default_factory=list)   # frases legibles
    ejes_excedidos: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return sum(self.penalizaciones.values())


def _rampa(valor: float, desde: float, hasta: float, penalizacion_max: float) -> float:
    """Penalización proporcional entre `desde` (0) y `hasta` (máxima).

    Fuera del tramo se satura, nunca se dispara.
    """
    if hasta == desde:
        return penalizacion_max
    proporcion = (valor - desde) / (hasta - desde)
    return -abs(penalizacion_max) * max(0.0, min(1.0, proporcion))


def _euros(valor: float) -> str:
    return f"{valor:,.0f} €".replace(",", ".")


def evaluar(anuncio: Anuncio, ev: Evaluacion, criterios: dict[str, Any]) -> Bandas:
    b = Bandas()
    sup_cfg = criterios["superficie"]
    duros = criterios.get("requisitos_duros", {})
    prefs = criterios.get("preferencias", {})
    precio_cfg = prefs.get("precio", {})

    # --- Superficie ---------------------------------------------------------
    metros = anuncio.superficie_m2
    if metros is not None:
        min_pleno = float(sup_cfg["min_m2"])
        max_pleno = float(sup_cfg["max_m2"])
        gris_min = float(sup_cfg.get("gris_min_m2", min_pleno))
        gris_max = float(sup_cfg.get("gris_max_m2", max_pleno))
        veto_max = float(sup_cfg.get("veto_max_m2", gris_max))
        if metros < min_pleno:
            b.penalizaciones[f"Se queda corto: {metros:g} m²"] = _rampa(metros, min_pleno, gris_min, 14)
            b.excesos.append(f"le faltan {min_pleno - metros:.0f} m²")
            b.ejes_excedidos.append("superficie")
        elif metros > max_pleno:
            if metros <= gris_max:
                castigo = _rampa(metros, max_pleno, gris_max, 14)
            else:
                castigo = -14 + _rampa(metros, gris_max, veto_max, 12)
            b.penalizaciones[f"Se pasa de metros: {metros:g} m²"] = castigo
            b.excesos.append(f"se pasa {metros - max_pleno:.0f} m²")
            b.ejes_excedidos.append("superficie")
            # Metros de más con obra por hacer es la peor combinación: se paga
            # más suelo del necesario y encima hay que invertir en él.
            if ev.poca_reforma == "no":
                b.penalizaciones["Metros de más y además con obra"] = -10.0

    # --- Precio -------------------------------------------------------------
    precio = anuncio.precio_eur
    objetivo = float(duros.get("precio_objetivo_eur", 0) or 0)
    veto_precio = float(duros.get("precio_veto_eur", 0) or 0)
    if precio and objetivo:
        bueno = float(precio_cfg.get("bueno_eur", objetivo * 0.85))
        if precio <= bueno:
            b.penalizaciones[f"Precio holgado: {_euros(precio)}"] = 5.0
        elif precio > objetivo:
            b.penalizaciones[f"Por encima del presupuesto: {_euros(precio)}"] = _rampa(
                precio, objetivo, veto_precio or objetivo * 1.4, 18
            )
            b.excesos.append(f"se pasa {_euros(precio - objetivo)}")
            b.ejes_excedidos.append("precio")

    # Precio por m²: una nave grande y barata puede compensar los metros de más.
    precio_m2 = anuncio.precio_m2
    if precio_m2:
        chollo = float(precio_cfg.get("chollo_eur_m2", 0) or 0)
        techo = float(precio_cfg.get("max_eur_m2", 0) or 0)
        if chollo and precio_m2 <= chollo:
            b.penalizaciones[f"Muy buen precio por m²: {precio_m2:,.0f} €/m²".replace(",", ".")] = 6.0
        elif techo and precio_m2 > techo:
            b.penalizaciones[f"Caro por m²: {precio_m2:,.0f} €/m²".replace(",", ".")] = _rampa(
                precio_m2, techo, techo * 2, 8
            )

    # --- Distancia ----------------------------------------------------------
    # Distancia. Ojo a la distinción: a partir de `comodo` ya resta puntos,
    # pero sólo se anota como "exceso" (y cuenta para la regla de
    # compensación) cuando pasa de `minutos_exceso`. Si no, cualquier sitio a
    # 18 minutos arrastraría un exceso y bastaría un metro de más para caer.
    minutos = ev.minutos_coche
    comodo = float(duros.get("max_minutos_coche", 15))
    umbral_exceso = float(duros.get("minutos_exceso", comodo + 5))
    veto_min = float(duros.get("veto_minutos_coche", umbral_exceso + 2))
    if minutos is not None and minutos > comodo:
        b.penalizaciones[f"A {minutos:g} min en coche"] = _rampa(minutos, comodo, veto_min, 14)
        if minutos > umbral_exceso:
            b.excesos.append(f"a {minutos:.0f} min en coche")
            b.ejes_excedidos.append("distancia")

    return b


def resumen_excesos(b: Bandas) -> str:
    """Frase corta para el email: qué se le perdona a este inmueble."""
    if not b.excesos:
        return ""
    return "; ".join(b.excesos)
