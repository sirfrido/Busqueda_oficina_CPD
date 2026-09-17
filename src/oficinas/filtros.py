"""Filtros duros: lo que descarta un anuncio sin llegar al email.

Regla de oro: sólo se descarta con evidencia. La ausencia de dato ("no dice
nada de la cubierta") nunca descarta — pasa a "verificar" y acaba siendo una
pregunta a la propiedad. Lo que sí descarta es un incumplimiento demostrado
(está en l'Horta Sud, está en un edificio de viviendas, tiene 80 m²...).
"""

from __future__ import annotations

from typing import Any

from .models import Anuncio, Evaluacion
from .textutils import normalizar


def rango_superficie(criterios: dict[str, Any]) -> tuple[float, float]:
    """Rango habitual. El tramo ampliado (hasta 500 m²) se trata aparte.

    La tolerancia sólo se aplica por arriba: 130 m² es un mínimo real de
    trabajo, mientras que un anuncio de 310 m² puede ser en realidad de 295.
    """
    sup = criterios["superficie"]
    tol = float(sup.get("tolerancia_pct", 0)) / 100.0
    return float(sup["min_m2"]), float(sup["max_m2"]) * (1 + tol)


def aplicar(anuncio: Anuncio, ev: Evaluacion, criterios: dict[str, Any]) -> tuple[bool, str]:
    """Devuelve (se_mantiene, motivo_de_descarte)."""
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

    # 3. Superficie. Por encima del máximo sólo pasa lo que está impecable:
    #    hasta 500 m² se acepta si el anuncio deja claro que no hay que
    #    reformar. Si hay que meter obra, no compensa el sobrecoste.
    sup_cfg = criterios["superficie"]
    minimo, maximo = rango_superficie(criterios)
    ampliado = float(sup_cfg.get("max_m2_si_impecable", sup_cfg["max_m2"]))
    if anuncio.superficie_m2 is not None:
        if anuncio.superficie_m2 < minimo:
            return False, f"{anuncio.superficie_m2:g} m² < mínimo {minimo:g} m²"
        if anuncio.superficie_m2 > maximo:
            if anuncio.superficie_m2 > ampliado:
                return False, f"{anuncio.superficie_m2:g} m² > máximo ampliado {ampliado:g} m²"
            if ev.poca_reforma != "si":
                return False, (
                    f"{anuncio.superficie_m2:g} m² supera los {maximo:g} m² y el anuncio no "
                    f"acredita que esté listo para entrar"
                )

    # 3 bis. Precio: tope duro.
    tope = float(duros.get("precio_max_eur", 0) or 0)
    if tope and anuncio.precio_eur and anuncio.precio_eur > tope:
        return False, f"{anuncio.precio_eur:,.0f} € > tope {tope:,.0f} €".replace(",", ".")

    # 4. Zona (l'Horta Sud / DANA / distancia)
    if duros.get("excluir_zonas_inundables", True) and not ev.zona_admitida:
        return False, ev.motivo_descarte or "Zona excluida"
    max_min = float(duros.get("max_minutos_coche", 20))
    if ev.minutos_coche is not None and ev.minutos_coche > max_min:
        return False, f"A {ev.minutos_coche:g} min en coche (máximo {max_min:g})"

    # 5. Edificio de viviendas demostrado
    if duros.get("no_edificio_viviendas", True) and ev.en_edificio_viviendas == "si":
        return False, "En edificio de viviendas (el CPD necesita edificio terciario)"

    # 5 bis. Bajo comercial, local a pie de calle o entresuelo: fuera.
    if duros.get("no_bajo_comercial", True) and ev.bajo_o_calle == "si":
        return False, "Bajo comercial / local a pie de calle (descartado: agua y vecinos)"

    # 6. Cubierta explícitamente vetada
    if duros.get("cubierta_o_azotea_ampliable", True) and ev.cubierta_ampliable == "no":
        return False, "Sin posibilidad de instalar/ampliar máquinas en cubierta"

    # 7. Potencia explícitamente insuficiente y no ampliable
    if ev.potencia_ampliable == "no":
        return False, "Suministro eléctrico insuficiente y sin margen de ampliación"
    kw = anuncio.extra.get("kw_declarados")
    minimo_kw = float(duros.get("potencia", {}).get("minimo_aceptable_kw", 0))
    if kw and kw < minimo_kw and ev.potencia_ampliable == "no":
        return False, f"Sólo {kw:g} kW y sin ampliación posible (mínimo {minimo_kw:g} kW)"

    return True, ""
