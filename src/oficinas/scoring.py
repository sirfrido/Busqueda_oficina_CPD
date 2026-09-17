"""Puntuación 0-100 de un candidato, con desglose auditable.

El desglose viaja hasta el email: cada punto sumado o restado se explica,
para poder ajustar los pesos viendo resultados reales.
"""

from __future__ import annotations

from typing import Any

from .bandas import Bandas
from .bandas import evaluar as evaluar_bandas
from .models import Anuncio, Evaluacion
from .textutils import normalizar

PESOS = {
    "base": 25.0,
    "edificio_oficinas_si": 14.0,
    "edificio_oficinas_verificar": 3.0,
    "edificio_viviendas_verificar": -4.0,
    "cubierta_si": 14.0,
    "cubierta_verificar": 3.0,
    "potencia_si": 16.0,
    "potencia_verificar": 3.0,
    "potencia_kw_suficiente": 8.0,
    "poca_reforma_si": 8.0,
    "poca_reforma_verificar": 0.0,
    "poca_reforma_no": -10.0,
    "superficie_optima": 6.0,
    "superficie_desconocida": -4.0,
    "riesgo_medio": -10.0,        # el agua es el miedo número uno
    "riesgo_desconocido": -4.0,
    "planta_alta": 8.0,
    "planta_baja_oficina": -6.0,
    "superficie_ampliada": -8.0,   # 300-500 m²: sólo compensa si está impecable
    "precio_ok": 4.0,
    "precio_alto": -6.0,
    "precio_desconocido": -2.0,
    "extra": 1.5,            # por extra valorado, con tope
    "extras_tope": 9.0,
    "penalizacion_minutos": -0.6,   # por minuto por encima de 10
}


def puntuar(
    anuncio: Anuncio,
    ev: Evaluacion,
    criterios: dict[str, Any],
    bonus_zona: float = 0.0,
    bandas: Bandas | None = None,
) -> tuple[float, dict[str, float]]:
    """Puntúa 0-100 con desglose. Las rampas de metros, precio y distancia
    las calcula `bandas.py`; aquí se suman al resto de méritos."""
    d: dict[str, float] = {"base": PESOS["base"]}
    duros = criterios.get("requisitos_duros", {})
    prefs = criterios.get("preferencias", {})

    # --- Requisitos del CPD ---
    if ev.edificio_oficinas == "si":
        d["Edificio de oficinas / nave"] = PESOS["edificio_oficinas_si"]
    elif ev.edificio_oficinas == "verificar":
        d["Tipo de edificio por confirmar"] = PESOS["edificio_oficinas_verificar"]
    if ev.en_edificio_viviendas == "verificar":
        d["Riesgo de comunidad de vecinos"] = PESOS["edificio_viviendas_verificar"]

    if ev.cubierta_ampliable == "si":
        d["Cubierta/azotea para clima"] = PESOS["cubierta_si"]
    elif ev.cubierta_ampliable == "verificar":
        d["Cubierta por confirmar"] = PESOS["cubierta_verificar"]

    if ev.potencia_ampliable == "si":
        d["Potencia ampliable"] = PESOS["potencia_si"]
    elif ev.potencia_ampliable == "verificar":
        d["Potencia por confirmar"] = PESOS["potencia_verificar"]

    kw = anuncio.extra.get("kw_declarados")
    objetivo = float(duros.get("potencia", {}).get("objetivo_kw", 250))
    if kw:
        if kw >= objetivo:
            d[f"Potencia declarada {kw:g} kW ≥ objetivo"] = PESOS["potencia_kw_suficiente"]
        elif kw >= float(duros.get("potencia", {}).get("minimo_aceptable_kw", 200)):
            d[f"Potencia declarada {kw:g} kW"] = PESOS["potencia_kw_suficiente"] / 2

    # --- Tipología preferida y altura ---
    es_nave = normalizar(anuncio.tipologia).startswith("nave") or "nave" in normalizar(anuncio.titulo)
    if es_nave:
        d["Nave: azotea propia y sin vecinos"] = float(prefs.get("bonus_nave", 8))
    else:
        if ev.planta_alta == "si":
            d["Oficina en planta alta"] = float(prefs.get("bonus_oficina_planta_alta", 8))
        elif ev.planta_alta == "no":
            d["Oficina en planta baja o sin altura"] = PESOS["planta_baja_oficina"]

    # --- Estado ---
    if ev.poca_reforma == "si":
        d["Poca reforma"] = PESOS["poca_reforma_si"]
    elif ev.poca_reforma == "no":
        d["Requiere reforma"] = PESOS["poca_reforma_no"]

    # --- Superficie: premio por estar en la banda ideal (el castigo por
    #     salirse lo pone bandas.py con su rampa).
    sup = criterios["superficie"]
    if anuncio.superficie_m2 is None:
        d["Superficie no declarada"] = PESOS["superficie_desconocida"]
    else:
        ideal_min = float(sup.get("ideal_min_m2", sup["min_m2"]))
        ideal_max = float(sup.get("ideal_max_m2", sup["max_m2"]))
        centro = (ideal_min + ideal_max) / 2
        ancho = (ideal_max - ideal_min) / 2 or 1.0
        cercania = max(0.0, 1 - abs(anuncio.superficie_m2 - centro) / ancho)
        d[f"Superficie {anuncio.superficie_m2:g} m²"] = round(PESOS["superficie_optima"] * cercania, 2)

    # --- Zona ---
    if bonus_zona:
        d["Zona preferente"] = round(bonus_zona, 2)
    if ev.riesgo_inundacion == "medio":
        d["Riesgo de inundación medio"] = PESOS["riesgo_medio"]
    elif ev.riesgo_inundacion == "desconocido":
        d["Riesgo de inundación sin evaluar"] = PESOS["riesgo_desconocido"]

    # --- Precio: sólo el caso "no lo publican"; el resto lo pone bandas.py.
    if anuncio.precio_eur is None:
        d["Precio no publicado"] = PESOS["precio_desconocido"]

    # --- Extras valorados ---
    texto = normalizar(anuncio.texto_completo)
    encontrados = [e for e in prefs.get("extras_valorados", []) if normalizar(e).replace("_", " ") in texto]
    if encontrados:
        d[f"Extras ({', '.join(encontrados[:4])})"] = min(
            PESOS["extras_tope"], PESOS["extra"] * len(encontrados)
        )

    # --- Confianza del cualificador LLM ---
    if ev.evaluado_por != "heuristica" and ev.confianza:
        d["Confianza del análisis"] = round((ev.confianza - 0.5) * 6, 2)

    # --- Rampas de metros, precio y distancia ---
    if bandas is None:
        bandas = evaluar_bandas(anuncio, ev, criterios)
    for etiqueta, valor in bandas.penalizaciones.items():
        d[etiqueta] = round(valor, 2)

    total = max(0.0, min(100.0, sum(d.values())))
    return round(total, 1), d
