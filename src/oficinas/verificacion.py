"""¿Esto es de verdad lo que dice ser?

Los portales clasifican fatal. Un solar vallado se publica como "nave
industrial en venta" con una foto del terreno y una línea de descripción, y
por metros, precio y zona pasa todos los filtros. Nos pasó con una supuesta
nave de 400 m² en Burjassot a 750 €/m² que era un solar con maleza.

No podemos ver las fotos (los portales bloquean el acceso automático), así
que la verificación se hace por lo que el anuncio dice y —sobre todo— por lo
que NO dice: un anuncio de una nave real habla de altura libre, de puerta de
camión, de oficinas, de aseos, de año de construcción. Una ficha de seis
palabras no acredita nada.

Regla de oro que impone este módulo: un inmueble cuya ficha no demuestra que
hay algo construido NO se recomienda como candidato. Va al bloque "Casi" con
la advertencia, y la primera pregunta a la propiedad pasa a ser si hay nave.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Anuncio
from .textutils import clasificar_terminos, contiene_alguno, normalizar

# Suelo sin edificar, dicho sin ambigüedad. Basta con que aparezca.
SUELO_ROTUNDO = [
    "solar edificable", "parcela edificable", "parcela industrial",
    "terreno edificable", "suelo urbano", "suelo industrial", "suelo urbanizable",
    "urbanizable", "sin edificar", "para construir", "listo para construir",
    "a construir", "posibilidad de construir", "posibilidad de edificar",
    "finca rustica", "uso agricola",
]
# Palabras ambiguas: "en la parcela hay un centro de transformación" describe
# una nave, y "placas solares" no tiene nada que ver con un solar. Sólo
# cuentan cuando el anuncio no cita ningún elemento construido.
SUELO_DEBIL = ["solar", "parcela", "terreno", "campo", "huerto", "rustico"]
# ...salvo cuando aparecen dentro de estas expresiones, que son otra cosa.
FALSOS_AMIGOS = [
    "placas solares", "paneles solares", "energia solar", "placa solar",
    "solarium", "solario", "captacion solar", "orientacion solar",
]

# Elementos que sólo existen si hay algo construido.
ELEMENTOS_CONSTRUIDOS = [
    "altura libre", "puerta de camion", "puerta camion", "muelle", "montacargas",
    "oficinas", "oficina", "aseo", "aseos", "vestuario", "entreplanta", "altillo",
    "cubierta", "tejado", "nave construida", "metros construidos", "m2 construidos",
    "superficie construida", "estructura", "forjado", "pilares", "año de construccion",
    "construido en", "diafano", "diáfano", "suelo de hormigon", "puerta seccional",
    "ventanas", "climatizacion", "luz natural", "instalacion electrica", "ascensor",
    "planta baja", "primera planta", "reformado", "a reformar", "acondicionado",
]

# Con menos texto que esto, la ficha no acredita nada.
MINIMO_PALABRAS = 18
MINIMO_CARACTERES = 110


@dataclass
class Verificacion:
    es_construido: str = "verificar"      # si | no | verificar
    ficha_pobre: bool = False
    sospecha_solar: bool = False
    avisos: list[str] = field(default_factory=list)

    @property
    def recomendable(self) -> bool:
        """¿Se puede poner delante del usuario como candidato serio?"""
        return self.es_construido != "no" and not self.sospecha_solar and not self.ficha_pobre


def _palabra_suelta(texto: str, palabra: str) -> bool:
    """Coincidencia por palabra completa, para que 'solar' no case con 'solares'."""
    clave = normalizar(palabra)
    idx = texto.find(clave)
    while idx != -1:
        antes = texto[idx - 1] if idx > 0 else " "
        despues = texto[idx + len(clave)] if idx + len(clave) < len(texto) else " "
        if not antes.isalnum() and not despues.isalnum():
            return True
        idx = texto.find(clave, idx + len(clave))
    return False


def verificar(anuncio: Anuncio) -> Verificacion:
    v = Verificacion()
    texto = anuncio.texto_completo
    txt = normalizar(texto)
    descripcion = normalizar(anuncio.descripcion)

    construidos = contiene_alguno(txt, ELEMENTOS_CONSTRUIDOS)

    # Limpia las expresiones que contienen una palabra sospechosa sin serlo
    # ("placas solares" no convierte una nave en un solar).
    txt_limpio = txt
    for falso in FALSOS_AMIGOS:
        txt_limpio = txt_limpio.replace(normalizar(falso), " ")

    rotundos, _negados, _dudosos = clasificar_terminos(txt_limpio, SUELO_ROTUNDO)
    debiles = [t for t in SUELO_DEBIL if _palabra_suelta(txt_limpio, t)]

    if rotundos:
        v.sospecha_solar = True
        v.es_construido = "no" if not construidos else "verificar"
        v.avisos.append(
            "El anuncio menciona " + ", ".join(f"«{t}»" for t in rotundos[:3])
            + ": es suelo sin edificar"
        )
    elif debiles and not construidos:
        # Ambiguo + ficha sin un solo elemento construido = mala señal.
        v.sospecha_solar = True
        v.avisos.append(
            "Habla de " + ", ".join(f"«{t}»" for t in debiles[:2])
            + " y no cita nada construido: puede ser un solar"
        )

    palabras = len(descripcion.split())
    if palabras < MINIMO_PALABRAS or len(descripcion) < MINIMO_CARACTERES:
        v.ficha_pobre = True
        v.avisos.append(
            f"Ficha sin datos ({palabras} palabras de descripción): no acredita que haya "
            f"nada construido. Hay que ver fotos y preguntar antes de nada"
        )

    if construidos:
        if not v.sospecha_solar:
            v.es_construido = "si"
        v.avisos.append("Elementos construidos citados: " + ", ".join(construidos[:4]))
    elif not v.sospecha_solar:
        # Ni habla de suelo ni de nada construido: no se puede afirmar nada.
        v.avisos.append(
            "El anuncio no menciona ningún elemento construido (altura, puertas, "
            "oficinas, año): confirmar que no es un solar"
        )

    # Un precio por m² de gama de suelo en algo que se vende como nave es un
    # indicio más, no una prueba: hay naves antiguas realmente baratas.
    if anuncio.precio_m2 and anuncio.precio_m2 < 500 and not construidos:
        v.avisos.append(f"{anuncio.precio_m2:,.0f} €/m²: precio de suelo, no de nave".replace(",", "."))
        v.sospecha_solar = True

    return v


def pregunta_prioritaria(v: Verificacion, anuncio: Anuncio) -> str | None:
    """La pregunta que hay que hacer ANTES que ninguna otra."""
    if v.es_construido == "si" and not v.ficha_pobre:
        return None
    if v.sospecha_solar:
        return (
            "Antes de nada: ¿el inmueble es una nave construida o se trata de un solar? "
            "Si hay nave, ¿qué superficie construida tiene y en qué año se construyó?"
        )
    return (
        "El anuncio no detalla el inmueble: ¿es una nave/oficina ya construida? "
        "¿Qué superficie construida tiene, qué altura libre y en qué estado está?"
    )
