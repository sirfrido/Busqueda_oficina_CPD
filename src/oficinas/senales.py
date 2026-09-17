"""Detección heurística de señales en el texto del anuncio.

Es la primera pasada, barata y determinista: marca lo que se puede afirmar
leyendo el anuncio. Lo que quede en "verificar" lo intenta resolver el
cualificador LLM (qualifier.py) y, si sigue abierto, se convierte en una
pregunta para la propiedad.
"""

from __future__ import annotations

import re

from .models import Anuncio, Evaluacion
from .textutils import (
    clasificar_terminos,
    contiene_alguno,
    extraer_altura_libre,
    extraer_kw,
    normalizar,
)

# --- Edificio de oficinas vs. edificio de viviendas -------------------------
EDIFICIO_OFICINAS = [
    "edificio de oficinas", "edificio exclusivo de oficinas", "edificio corporativo",
    "torre de oficinas", "centro de negocios", "parque empresarial", "business center",
    "edificio singular", "uso terciario", "uso administrativo", "edificio administrativo",
    "complejo empresarial", "edificio de uso exclusivo oficinas",
]
EDIFICIO_VIVIENDAS = [
    "edificio de viviendas", "edificio residencial", "bloque de viviendas",
    "comunidad de vecinos", "comunidad de propietarios", "entre vecinos",
    "uso residencial", "vivienda", "piso alto", "apartamento",
]
NAVE = [
    "nave industrial", "nave", "poligono industrial", "polígono industrial",
    "parcela industrial", "uso industrial", "almacen industrial",
]

# --- Altura dentro del edificio -------------------------------------------
# En oficinas interesan las ÚLTIMAS plantas: las máquinas van a la azotea y
# cuanto menos recorrido de tubería, mejor (y el agua nunca llega arriba).
PLANTA_ALTA = [
    "ultima planta", "última planta", "ultimo piso", "atico", "ático",
    "planta alta", "plantas altas", "ultimas plantas", "últimas plantas",
    "planta superior", "torre", "azotea propia",
]
# Lo que queda descartado de plano: a cota cero, con escaparate o entresuelo.
BAJO_O_CALLE = [
    "bajo comercial", "bajos comerciales", "local a pie de calle",
    "a pie de calle", "pie de calle", "entresuelo", "entreplanta",
    "semisotano", "semisótano", "sotano", "sótano", "escaparate",
    "planta baja", "en bajo", "local comercial",
]

# --- Cubierta / azotea para clima (y crecimiento en nº de máquinas) ---------
CUBIERTA_OK = [
    "azotea", "cubierta transitable", "cubierta propia", "cubierta de uso exclusivo",
    "uso exclusivo de cubierta", "salida a cubierta", "acceso a cubierta",
    "maquinas en cubierta", "unidades exteriores en cubierta", "terraza propia",
    "patio de uso exclusivo", "patio privado", "cubierta libre", "solarium",
    "espacio para maquinaria en cubierta",
]
CUBIERTA_KO = [
    "sin acceso a cubierta", "cubierta comunitaria", "azotea comunitaria",
    "prohibido instalar en cubierta", "no permite maquinaria",
]

# --- Potencia eléctrica -----------------------------------------------------
POTENCIA_OK = [
    "centro de transformacion", "transformador propio", "alta tension",
    "media tension", "acometida industrial", "acometida propia", "trifasica",
    "trifasico", "potencia contratada", "grupo electrogeno", "sai", "ups",
    "suministro industrial", "cuadro electrico industrial", "linea directa",
]
POTENCIA_KO = [
    "sin suministro", "sin luz", "sin acometida", "monofasica", "sin boletin",
    "potencia limitada", "baja potencia",
]

# --- Estado / reforma -------------------------------------------------------
BUEN_ESTADO = [
    "listo para entrar", "entrar a trabajar", "perfecto estado", "buen estado",
    "poca obra", "obra menor", "sin necesidad de reforma", "apenas reforma",
    "reformado", "recien reformado", "seminuevo", "obra nueva", "a estrenar",
    "llave en mano", "acondicionado", "equipado", "impecable", "muy cuidado",
]
A_REFORMAR = [
    "a reformar", "para reformar", "necesita reforma", "reforma integral",
    "obra a realizar", "en bruto", "sin acondicionar", "estado original",
    "ruina", "rehabilitar", "para actualizar",
]

# --- Extras que suman para un CPD ------------------------------------------
EXTRAS_CPD = {
    "montacargas": 3,
    "ascensor de carga": 3,
    "muelle de carga": 3,
    "acceso para camion": 2,
    "acceso de camiones": 2,
    "puerta de camion": 2,
    "grupo electrogeno": 6,
    "centro de transformacion": 6,
    "fibra optica": 4,
    "falso suelo": 4,
    "suelo tecnico": 4,
    "climatizacion industrial": 3,
    "24 horas": 2,
    "seguridad 24": 3,
    "videovigilancia": 2,
    "aparcamiento": 2,
    "parking": 2,
    "planta baja": 3,
    "diafano": 2,
    "diáfano": 2,
}

PREGUNTAS_BASE = {
    "potencia": "¿Qué potencia eléctrica hay contratada actualmente y hasta cuánto es ampliable "
                "(200-300 kW o más)? ¿El edificio dispone de centro de transformación propio o "
                "hay uno de la distribuidora a pie de calle?",
    "cubierta": "¿Se pueden instalar máquinas de aire acondicionado en la azotea/cubierta y ampliar "
                "el número de unidades en el futuro? ¿Hay servidumbre o permiso de comunidad para ello?",
    "edificio": "¿El inmueble está en un edificio exclusivo de oficinas (uso terciario) o comparte "
                "portal con viviendas?",
    "reforma": "¿En qué estado está el inmueble y qué obra haría falta para uso de oficina/CPD?",
    "acceso": "¿Hay acceso para meter equipamiento pesado (montacargas, muelle, puerta ancha) y "
              "sitio para un grupo electrógeno?",
    "24x7": "¿Permite el edificio acceso y funcionamiento 24x7?",
    "planta": "¿En qué planta está y cuántas tiene el edificio? Nos interesan las "
              "plantas altas, por el recorrido de tubería hasta las máquinas de la azotea.",
}


_RE_PLANTA = re.compile(r"\bplanta\s+(\d{1,2})\b|\b(\d{1,2})[ªº]\s*planta\b")


def _planta_numerica(texto_normalizado: str) -> int | None:
    """Número de planta citado en el anuncio ('planta 4', '3ª planta')."""
    m = _RE_PLANTA.search(texto_normalizado)
    if not m:
        return None
    valor = m.group(1) or m.group(2)
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None
    return numero if 0 <= numero <= 30 else None


def _veredicto(positivas: list[str], negativas: list[str]) -> str:
    if negativas and not positivas:
        return "no"
    if positivas and not negativas:
        return "si"
    if positivas and negativas:
        return "verificar"
    return "verificar"


def detectar(anuncio: Anuncio) -> Evaluacion:
    """Rellena una Evaluacion con lo que se deduce del texto del anuncio."""
    txt = normalizar(anuncio.texto_completo)
    ev = Evaluacion()
    pos: list[str] = []
    neg: list[str] = []

    es_nave = bool(contiene_alguno(txt, NAVE)) or normalizar(anuncio.tipologia).startswith("nave")

    # Tipo de edificio
    ofi = contiene_alguno(txt, EDIFICIO_OFICINAS)
    viv = contiene_alguno(txt, EDIFICIO_VIVIENDAS)
    if es_nave:
        # Una nave en polígono nunca es un edificio de viviendas: cumple el
        # requisito por naturaleza.
        ev.edificio_oficinas = "si"
        ev.en_edificio_viviendas = "no"
        pos.append("Nave/industrial: sin comunidad de vecinos")
    else:
        ev.edificio_oficinas = _veredicto(ofi, viv)
        ev.en_edificio_viviendas = "si" if viv and not ofi else ("no" if ofi and not viv else "verificar")
        pos += [f"Edificio terciario: «{t}»" for t in ofi]
        neg += [f"Indicio de edificio residencial: «{t}»" for t in viv]

    # Cubierta / azotea
    cub_ok, cub_negados, _cub_dudosos = clasificar_terminos(txt, CUBIERTA_OK)
    cub_ko = contiene_alguno(txt, CUBIERTA_KO) + [f"negado: {t}" for t in cub_negados]
    if es_nave and not cub_ko:
        ev.cubierta_ampliable = "si" if cub_ok else "verificar"
        if not cub_ok:
            pos.append("Nave con cubierta propia: escalado de máquinas habitualmente viable")
    else:
        ev.cubierta_ampliable = _veredicto(cub_ok, cub_ko)
    pos += [f"Cubierta: «{t}»" for t in cub_ok]
    neg += [f"Cubierta restringida: «{t}»" for t in cub_ko]

    # Potencia
    kw = extraer_kw(anuncio.texto_completo)
    pot_ok, pot_negados, _pot_dudosos = clasificar_terminos(txt, POTENCIA_OK)
    pot_ko = contiene_alguno(txt, POTENCIA_KO) + [f"negado: {t}" for t in pot_negados]
    if kw:
        ev.senales_positivas.append(f"Potencia declarada: {kw:g} kW")
        anuncio.extra.setdefault("kw_declarados", kw)
    ev.potencia_ampliable = _veredicto(pot_ok, pot_ko)
    if kw and kw >= 200:
        ev.potencia_ampliable = "si"
    pos += [f"Eléctrico: «{t}»" for t in pot_ok]
    neg += [f"Eléctrico: «{t}»" for t in pot_ko]

    # Estado / reforma
    bueno = contiene_alguno(txt, BUEN_ESTADO)
    malo = contiene_alguno(txt, A_REFORMAR)
    ev.poca_reforma = _veredicto(bueno, malo)
    pos += [f"Estado: «{t}»" for t in bueno]
    neg += [f"Estado: «{t}»" for t in malo]

    # Planta: alta (bien) frente a bajo comercial / pie de calle (descartado).
    # En una nave esto no aplica: es su propio edificio, a cota de calle y con
    # cubierta propia, que es justo lo que se busca.
    if es_nave:
        ev.planta_alta = "no"
        ev.bajo_o_calle = "no"
    else:
        altas = contiene_alguno(txt, PLANTA_ALTA)
        bajos = contiene_alguno(txt, BAJO_O_CALLE)
        numero = _planta_numerica(txt)
        if altas or (numero is not None and numero >= 2):
            ev.planta_alta = "si"
            pos.append(f"Planta alta: «{altas[0] if altas else f'planta {numero}'}»")
        elif bajos or numero == 0:
            ev.planta_alta = "no"
        if bajos:
            ev.bajo_o_calle = "si"
            neg += [f"A pie de calle: «{t}»" for t in bajos]
        elif altas or (numero is not None and numero >= 1):
            ev.bajo_o_calle = "no"

    # Altura libre (relevante para falso suelo + clima)
    altura = extraer_altura_libre(anuncio.texto_completo)
    if altura:
        anuncio.extra.setdefault("altura_libre_m", altura)
        if altura >= 3.5:
            pos.append(f"Altura libre {altura:g} m: permite falso suelo y clima")

    # Extras (respetando negaciones: "sin aparcamiento" no suma)
    for extra in contiene_alguno(txt, list(EXTRAS_CPD)):
        pos.append(f"Extra: {extra}")

    ev.senales_positivas.extend(pos)
    ev.senales_negativas.extend(neg)
    ev.preguntas_clave = preguntas_pendientes(ev)
    ev.evaluado_por = "heuristica"
    return ev


def preguntas_pendientes(ev: Evaluacion) -> list[str]:
    """Preguntas que siguen abiertas tras evaluar; van al email a la propiedad."""
    preguntas: list[str] = []
    if ev.potencia_ampliable != "si":
        preguntas.append(PREGUNTAS_BASE["potencia"])
    if ev.cubierta_ampliable != "si":
        preguntas.append(PREGUNTAS_BASE["cubierta"])
    if ev.edificio_oficinas != "si" or ev.en_edificio_viviendas != "no":
        preguntas.append(PREGUNTAS_BASE["edificio"])
    if ev.poca_reforma != "si":
        preguntas.append(PREGUNTAS_BASE["reforma"])
    if ev.planta_alta == "verificar":
        preguntas.append(PREGUNTAS_BASE["planta"])
    preguntas.append(PREGUNTAS_BASE["acceso"])
    preguntas.append(PREGUNTAS_BASE["24x7"])
    return preguntas
