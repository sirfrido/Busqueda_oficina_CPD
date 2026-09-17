"""Vetos: lo poco que descarta un anuncio de forma inapelable.

Este módulo se ha quedado deliberadamente corto. Antes descartaba por
metros, por precio y por minutos con cortes secos, y así se perdían
inmuebles buenos por 10 m² o por 20.000 € negociables. Eso ahora vive en
`bandas.py`, que penaliza en vez de matar.

Aquí sólo queda lo que no tiene arreglo posible:

  · zona inundable o afectada por la DANA        (no se negocia con el agua)
  · edificio de viviendas / comunidad de vecinos (no hay CPD posible)
  · bajo comercial o local a pie de calle        (agua, ruido y escaparate)
  · alquiler cuando se busca compra
  · tipologías que no son ni nave ni oficina
  · estar tan fuera de banda que no hay conversación: menos de 100 m²,
    más de 700 m², más de 550.000 € o más de 30 minutos en coche

Y una regla que no cambia: la falta de dato nunca descarta. Que un anuncio
no diga nada de la potencia significa "hay que preguntarlo", no "no vale".
"""

from __future__ import annotations

from typing import Any

from .models import Anuncio, Evaluacion
from .textutils import normalizar


def rango_superficie(criterios: dict[str, Any]) -> tuple[float, float]:
    """Banda plena de superficie (la que no resta puntos)."""
    sup = criterios["superficie"]
    return float(sup["min_m2"]), float(sup["max_m2"])


def limites_absolutos(criterios: dict[str, Any]) -> tuple[float, float]:
    """Metros fuera de los cuales ni se mira."""
    sup = criterios["superficie"]
    return float(sup.get("veto_min_m2", 0)), float(sup.get("veto_max_m2", 10000))


def aplicar(anuncio: Anuncio, ev: Evaluacion, criterios: dict[str, Any]) -> tuple[bool, str]:
    """Devuelve (se_mantiene, motivo_de_veto)."""
    duros = criterios.get("requisitos_duros", {})
    tip = criterios.get("tipologias", {})

    # 1. Operación (venta/alquiler)
    operacion = criterios.get("operacion", "venta")
    if operacion != "ambos" and anuncio.operacion and normalizar(anuncio.operacion) != normalizar(operacion):
        return False, f"Operación {anuncio.operacion} (se busca {operacion})"

    # 2. Tipología vetada
    texto = normalizar(f"{anuncio.tipologia} {anuncio.titulo}")
    for excluida in tip.get("excluir", []):
        etiqueta = normalizar(excluida).replace("_", " ")
        if normalizar(anuncio.tipologia).replace("_", " ") == etiqueta:
            return False, f"Tipología excluida: {excluida}"
        if etiqueta in ("vivienda", "garaje", "trastero", "terreno") and etiqueta in texto:
            # Sólo veta si domina el título; 'oficina con plaza de garaje' no cuenta.
            if not any(ok in texto for ok in ("oficina", "nave", "local", "edificio")):
                return False, f"Tipología excluida: {excluida}"

    # 3. Superficie: sólo los extremos absolutos.
    veto_min, veto_max = limites_absolutos(criterios)
    if anuncio.superficie_m2 is not None:
        if anuncio.superficie_m2 < veto_min:
            return False, f"{anuncio.superficie_m2:g} m²: demasiado pequeño (mínimo {veto_min:g} m²)"
        if anuncio.superficie_m2 > veto_max:
            return False, f"{anuncio.superficie_m2:g} m²: demasiado grande (máximo {veto_max:g} m²)"

    # 4. Precio: sólo el veto. El objetivo de 400.000 € lo gestiona bandas.py.
    veto_precio = float(duros.get("precio_veto_eur", 0) or 0)
    if veto_precio and anuncio.precio_eur and anuncio.precio_eur > veto_precio:
        return False, f"{anuncio.precio_eur:,.0f} €: fuera de toda negociación".replace(",", ".")

    # 5. Zona (l'Horta Sud / DANA)
    if duros.get("excluir_zonas_inundables", True) and not ev.zona_admitida:
        return False, ev.motivo_descarte or "Zona excluida"
    veto_minutos = float(duros.get("veto_minutos_coche", 30))
    if ev.minutos_coche is not None and ev.minutos_coche > veto_minutos:
        return False, f"A {ev.minutos_coche:g} min en coche: demasiado lejos"

    # 6. Edificio de viviendas demostrado
    if duros.get("no_edificio_viviendas", True) and ev.en_edificio_viviendas == "si":
        return False, "En edificio de viviendas (el CPD necesita edificio terciario)"

    # 7. Bajo comercial, local a pie de calle o entresuelo
    if duros.get("no_bajo_comercial", True) and ev.bajo_o_calle == "si":
        return False, "Bajo comercial / local a pie de calle (descartado: agua y vecinos)"

    # 8. Cubierta explícitamente vetada
    if duros.get("cubierta_o_azotea_ampliable", True) and ev.cubierta_ampliable == "no":
        return False, "Sin posibilidad de instalar/ampliar máquinas en cubierta"

    # 9. Suministro eléctrico insuficiente y sin margen
    if ev.potencia_ampliable == "no":
        return False, "Suministro eléctrico insuficiente y sin margen de ampliación"

    return True, ""
