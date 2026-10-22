"""Cribado local de similitud, sin red ni modelo.

Dos usos: es la red de seguridad (lo que puntúa alto sale en el informe aunque
Claude lo descarte) y es lo que queda si no hay ANTHROPIC_API_KEY.

Compara el núcleo distintivo (HAMPA) con cada palabra y cada par de palabras
contiguas de la denominación, por escritura y por cómo suena en español:
la H es muda, B/V suenan igual, C/K/Q y S/Z/C también, LL ~ Y.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


def normalizar(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return re.sub(r"[^A-Z0-9 ]+", " ", sin_tildes.upper()).strip()


def fonetica(palabra: str) -> str:
    p = palabra.upper()
    for viejo, nuevo in (
        ("CH", "#"), ("LL", "Y"), ("QU", "K"), ("PH", "F"), ("W", "U"),
        ("CE", "SE"), ("CI", "SI"), ("C", "K"), ("Z", "S"), ("V", "B"),
        ("J", "H"),  # HAMPA dicho a la inglesa suena JAMPA
        ("NP", "MP"), ("NB", "MB"),  # delante de P/B, la N suena M
    ):
        p = p.replace(viejo, nuevo)
    p = p.replace("H", "").replace("#", "CH").replace("Y", "I")
    return re.sub(r"(.)\1+", r"\1", p)  # letras dobles: HAMMPA ~ HAMPA


def _ventanas(denominacion: str) -> list[str]:
    palabras = normalizar(denominacion).split()
    salida = list(palabras)
    salida += [a + b for a, b in zip(palabras, palabras[1:])]  # «HAM PA», «HAMPA STUDIO»
    return [v for v in salida if len(v) >= 4]  # «AMA», «PA»: demasiado cortas


def puntuar(denominacion: str, nucleo: str) -> tuple[float, str]:
    """0-1 y el motivo legible de la mejor coincidencia."""
    n = normalizar(nucleo).replace(" ", "")
    nf = fonetica(n)
    compacto = normalizar(denominacion).replace(" ", "")
    mejor, motivo = 0.0, ""

    if n and n in compacto:
        return 1.0, f"contiene «{n}»"

    for v in _ventanas(denominacion):
        # Empieza sonando igual: «JAMPAS», «AMPA STUDIO»... (no «LAMPARA»).
        if nf and len(nf) >= 3 and fonetica(v).startswith(nf) and mejor < 0.9:
            mejor, motivo = 0.9, f"«{v}» empieza sonando como «{n}»"
        escrita = SequenceMatcher(None, n, v).ratio()
        sonora = SequenceMatcher(None, nf, fonetica(v)).ratio()
        if escrita > mejor:
            mejor, motivo = escrita, f"«{v}» se escribe parecido a «{n}»"
        if sonora > mejor:
            mejor, motivo = sonora, f"«{v}» suena parecido a «{n}»"
    return round(mejor, 3), motivo
