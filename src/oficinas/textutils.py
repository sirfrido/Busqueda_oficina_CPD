"""Utilidades de texto: normalización y extracción de cifras de anuncios ES."""

from __future__ import annotations

import re
import unicodedata

_ESPACIOS = re.compile(r"\s+")


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y sin espacios redundantes.

    Sirve para comparar municipios ("Benetússer" == "benetusser") y para
    buscar señales en la descripción sin preocuparse de tildes.
    """
    if not texto:
        return ""
    txt = unicodedata.normalize("NFD", texto)
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
    txt = txt.replace("ʼ", "'").replace("´", "'").replace("`", "'")
    return _ESPACIOS.sub(" ", txt.lower()).strip()


def limpiar(texto: str | None) -> str:
    return _ESPACIOS.sub(" ", (texto or "").replace("\xa0", " ")).strip()


def _a_float_es(bruto: str) -> float | None:
    """Convierte '1.250,50' o '1250.5' o '1,250' al float correspondiente."""
    s = bruto.strip().replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        # El último separador que aparece es el decimal.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        entero, _, dec = s.partition(",")
        s = f"{entero}.{dec}" if len(dec) in (1, 2) else entero + dec
    elif "." in s:
        entero, _, dec = s.rpartition(".")
        # '1.250' en español es mil doscientos cincuenta, no 1,25.
        s = f"{entero.replace('.', '')}.{dec}" if len(dec) in (1, 2) and len(entero.replace(".", "")) <= 3 else s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


_RE_SUPERFICIE = re.compile(
    r"(\d[\d.,\s]{0,9}\d|\d)\s*(?:m2|m²|m\.?\s?c\.?|metros?\s+cuadrados?)", re.IGNORECASE
)
_RE_PRECIO = re.compile(r"(\d[\d.,\s]{2,12})\s*(?:€|eur\b|euros)", re.IGNORECASE)
_RE_KW = re.compile(r"(\d[\d.,]{0,8})\s*(kw|kva|kilovatios?)\b", re.IGNORECASE)
_RE_ALTURA = re.compile(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:m|metros)\s*(?:de\s*)?(?:altura|libres?)", re.IGNORECASE)


def extraer_superficie_m2(texto: str) -> float | None:
    """Mayor superficie plausible citada en el texto (m²).

    Se queda con el máximo porque los anuncios suelen listar primero la
    superficie útil y luego la construida; para un CPD manda la construida.
    """
    candidatos: list[float] = []
    for bruto in _RE_SUPERFICIE.findall(texto or ""):
        val = _a_float_es(bruto)
        if val and 10 <= val <= 20000:
            candidatos.append(val)
    return max(candidatos) if candidatos else None


def extraer_precio_eur(texto: str) -> float | None:
    candidatos: list[float] = []
    for bruto in _RE_PRECIO.findall(texto or ""):
        val = _a_float_es(bruto)
        if val and val >= 1000:
            candidatos.append(val)
    return max(candidatos) if candidatos else None


def extraer_kw(texto: str) -> float | None:
    """Potencia eléctrica citada en el anuncio, en kW (kVA ≈ kW·0,9)."""
    mejor: float | None = None
    for bruto, unidad in _RE_KW.findall(texto or ""):
        val = _a_float_es(bruto)
        if not val:
            continue
        if unidad.lower() == "kva":
            val *= 0.9
        if 1 <= val <= 5000 and (mejor is None or val > mejor):
            mejor = val
    return round(mejor, 1) if mejor else None


def extraer_altura_libre(texto: str) -> float | None:
    for bruto in _RE_ALTURA.findall(texto or ""):
        val = _a_float_es(bruto)
        if val and 2 <= val <= 20:
            return val
    return None


# Marcas de negación: "sin acceso a cubierta", "no dispone de potencia",
# "no se especifica ni acceso a cubierta"... Sin esto, un anuncio que niega
# algo puntuaría como si lo ofreciera.
# "sin acceso a cubierta" NIEGA; "no se especifica el acceso a cubierta"
# sólo dice que no se sabe. Son cosas distintas: la primera descarta el
# inmueble, la segunda se convierte en una pregunta para la propiedad.
NEGACIONES_ROTUNDAS = (
    "no ", "sin ", "ni ", "nunca", "carece", "imposible", "prohibid",
    "no dispone", "no cuenta", "no permite", "no admite", "no tiene", "no hay",
)
NEGACIONES_DUDOSAS = (
    "no se especifica", "no especifica", "no consta", "no indica", "pendiente de",
    "por confirmar", "a consultar", "se desconoce", "no detalla", "consultar",
)
VENTANA_NEGACION = 45
# Estas partículas abren una oración nueva: lo que hubiera antes ya no niega
# lo que viene después ("sin aparcamiento PERO CON azotea de uso exclusivo").
CORTES_ORACION = (".", ";", "!", "?", ",", " pero ", " aunque ", " con ", " si bien ")

PRESENTE, NEGADO, DUDOSO = "presente", "negado", "dudoso"


def _estado_termino(texto: str, inicio: int) -> str:
    contexto = texto[max(0, inicio - VENTANA_NEGACION):inicio]
    for corte in CORTES_ORACION:
        if corte in contexto:
            contexto = contexto.rsplit(corte, 1)[1]
    if any(marca in contexto for marca in NEGACIONES_DUDOSAS):
        return DUDOSO
    if any(marca in contexto for marca in NEGACIONES_ROTUNDAS):
        return NEGADO
    return PRESENTE


def clasificar_terminos(
    texto_normalizado: str, terminos: list[str]
) -> tuple[list[str], list[str], list[str]]:
    """Reparte los términos en (presentes, negados, dudosos).

    Si un término aparece varias veces, gana la aparición más favorable:
    un anuncio que dice "sin acceso a cubierta" y después "acceso a la
    cubierta del edificio" merece al menos una verificación.
    """
    presentes: list[str] = []
    negados: list[str] = []
    dudosos: list[str] = []
    for termino in terminos:
        clave = normalizar(termino)
        if not clave:
            continue
        estados: set[str] = set()
        idx = texto_normalizado.find(clave)
        while idx != -1:
            estados.add(_estado_termino(texto_normalizado, idx))
            idx = texto_normalizado.find(clave, idx + len(clave))
        if not estados:
            continue
        if PRESENTE in estados:
            presentes.append(termino)
        elif DUDOSO in estados:
            dudosos.append(termino)
        else:
            negados.append(termino)
    return presentes, negados, dudosos


def contiene_alguno(texto_normalizado: str, terminos: list[str]) -> list[str]:
    """Términos presentes de forma afirmativa (atajo sobre clasificar_terminos)."""
    return clasificar_terminos(texto_normalizado, terminos)[0]
