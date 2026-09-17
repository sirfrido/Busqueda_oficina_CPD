"""Adaptador genérico de listados HTML dirigido por selectores CSS.

Dos estrategias en cascada, porque los portales cambian el maquetado a menudo:
  1. Selectores CSS declarados en config/fuentes.yaml.
  2. JSON-LD (schema.org) incrustado en la página, que suele sobrevivir a los
     rediseños. Si (1) no devuelve nada, se intenta (2).

Si ambas fallan, la fuente reporta 0 anuncios y `oficinas diagnostico` lo
señala para que se ajusten los selectores.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import Anuncio
from ..textutils import extraer_precio_eur, extraer_superficie_m2, limpiar, normalizar
from .base import FuenteBase, registrar

log = logging.getLogger(__name__)

_TIPOLOGIAS = (
    ("nave", ("nave", "industrial", "almacen", "almacén")),
    ("oficina", ("oficina", "despacho", "terciario")),
    ("local", ("local", "bajo comercial")),
    ("edificio", ("edificio",)),
)


def deducir_tipologia(texto: str) -> str:
    txt = normalizar(texto)
    for etiqueta, claves in _TIPOLOGIAS:
        if any(normalizar(c) in txt for c in claves):
            return etiqueta
    return ""


@registrar("html")
class FuenteHTML(FuenteBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.selectores: dict[str, str] = self.cfg.get("selectores") or {}
        self.urls: list[str] = self.cfg.get("urls") or []
        self.selectores_detalle: dict[str, str] = self.cfg.get("selectores_detalle") or {}

    # -- listado ------------------------------------------------------------
    def buscar(self) -> list[Anuncio]:
        anuncios: list[Anuncio] = []
        self.errores_red = []
        for url in self.urls:
            try:
                resp = self.fetcher.get(url)
            except Exception as exc:
                log.warning("[%s] no se pudo leer %s: %s", self.id, url, exc)
                self.errores_red.append(f"{url}: {_resumen_error(exc)}")
                continue
            sopa = BeautifulSoup(resp.texto, "lxml")
            encontrados = list(self._por_selectores(sopa, url))
            if not encontrados:
                encontrados = list(self._por_jsonld(sopa, url))
            if not encontrados:
                log.warning("[%s] 0 resultados en %s (¿selectores obsoletos?)", self.id, url)
            anuncios.extend(encontrados)
        return anuncios

    def _por_selectores(self, sopa: BeautifulSoup, url_base: str) -> Iterable[Anuncio]:
        sel_item = self.selectores.get("item")
        if not sel_item:
            return []
        for nodo in sopa.select(sel_item):
            enlace = self._texto_attr(nodo, self.selectores.get("url"), attr="href")
            if not enlace:
                a = nodo.find("a", href=True)
                enlace = a["href"] if a else ""
            if not enlace:
                continue
            titulo = self._texto(nodo, self.selectores.get("titulo")) or limpiar(nodo.get_text(" "))[:180]
            descripcion = self._texto(nodo, self.selectores.get("descripcion"))
            ubicacion = self._texto(nodo, self.selectores.get("ubicacion"))
            precio_txt = self._texto(nodo, self.selectores.get("precio"))
            superficie_txt = self._texto(nodo, self.selectores.get("superficie"))
            bruto = " ".join([titulo, descripcion, superficie_txt])
            yield Anuncio(
                fuente=self.id,
                url=urljoin(url_base, enlace),
                titulo=titulo,
                descripcion=descripcion,
                precio_eur=extraer_precio_eur(precio_txt) or extraer_precio_eur(bruto),
                superficie_m2=extraer_superficie_m2(superficie_txt) or extraer_superficie_m2(bruto),
                zona=ubicacion,
                municipio=ubicacion,
                tipologia=deducir_tipologia(f"{titulo} {descripcion}"),
                operacion=self.cfg.get("operacion", "venta"),
                extra={"fuente_nombre": self.nombre},
            )

    def _por_jsonld(self, sopa: BeautifulSoup, url_base: str) -> Iterable[Anuncio]:
        for script in sopa.find_all("script", type="application/ld+json"):
            try:
                datos = json.loads(script.string or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            for item in _aplanar_jsonld(datos):
                url = item.get("url") or item.get("@id")
                nombre = limpiar(item.get("name", ""))
                if not url or not nombre:
                    continue
                descripcion = limpiar(item.get("description", ""))
                oferta = item.get("offers") or {}
                if isinstance(oferta, list):
                    oferta = oferta[0] if oferta else {}
                precio = oferta.get("price") or item.get("price")
                direccion = item.get("address") or {}
                if isinstance(direccion, dict):
                    localidad = limpiar(
                        direccion.get("addressLocality") or direccion.get("addressRegion") or ""
                    )
                    calle = limpiar(direccion.get("streetAddress", ""))
                else:
                    localidad, calle = limpiar(str(direccion)), ""
                superficie = None
                area = item.get("floorSize") or {}
                if isinstance(area, dict) and area.get("value"):
                    try:
                        superficie = float(str(area["value"]).replace(",", "."))
                    except ValueError:
                        superficie = None
                yield Anuncio(
                    fuente=self.id,
                    url=urljoin(url_base, str(url)),
                    titulo=nombre,
                    descripcion=descripcion,
                    precio_eur=float(precio) if _es_numero(precio) else extraer_precio_eur(descripcion),
                    superficie_m2=superficie or extraer_superficie_m2(f"{nombre} {descripcion}"),
                    municipio=localidad,
                    direccion=calle,
                    zona=localidad,
                    tipologia=deducir_tipologia(f"{nombre} {descripcion}"),
                    operacion=self.cfg.get("operacion", "venta"),
                    extra={"fuente_nombre": self.nombre, "origen": "json-ld"},
                )

    # -- ficha de detalle ---------------------------------------------------
    def detalle(self, anuncio: Anuncio) -> Anuncio:
        """Completa el anuncio con el texto de la ficha (descripción larga).

        Es donde suelen estar las señales que importan: potencia, cubierta,
        tipo de edificio. Sólo se llama para los candidatos que ya pasaron
        el primer corte, para no descargar de más.
        """
        try:
            resp = self.fetcher.get(anuncio.url)
        except Exception as exc:
            log.debug("[%s] sin detalle para %s: %s", self.id, anuncio.url, exc)
            return anuncio
        sopa = BeautifulSoup(resp.texto, "lxml")
        cuerpo = self._descripcion_real(sopa)
        if cuerpo and len(cuerpo) > len(anuncio.descripcion):
            anuncio.descripcion = cuerpo
        if anuncio.superficie_m2 is None:
            anuncio.superficie_m2 = extraer_superficie_m2(sopa.get_text(" ")[:20000])
        if anuncio.precio_eur is None:
            anuncio.precio_eur = extraer_precio_eur(sopa.get_text(" ")[:20000])
        anuncio.imagenes = anuncio.imagenes or _imagenes(sopa) or _imagenes_crudas(resp.texto)
        anuncio.contacto_email = anuncio.contacto_email or _primer_email(resp.texto)
        anuncio.contacto_telefono = anuncio.contacto_telefono or _primer_telefono(resp.texto)
        anuncio.extra["detalle_descargado"] = True
        return anuncio

    def _descripcion_real(self, sopa: BeautifulSoup) -> str:
        """La descripción que escribió el anunciante, no el decorado del portal.

        Importa más de lo que parece: una ficha de seis palabras es la señal
        de que puede no haber nada construido. Si aquí se cuela el texto
        publicitario del portal ("Accede a la vista 3D..."), esa señal
        desaparece y acabamos recomendando un solar.
        """
        # El meta social es la versión más limpia: sólo el texto del anunciante,
        # sin selectores de idioma ni "Mostrar más".
        for busqueda in ({"property": "og:description"}, {"name": "description"}):
            meta = sopa.find("meta", attrs=busqueda)
            if meta and _es_descripcion(limpiar(meta.get("content", ""))):
                return limpiar(meta["content"])

        sel = self.selectores_detalle.get("descripcion")
        if sel:
            texto = _sin_ruido(self._texto(sopa, sel))
            if _es_descripcion(texto):
                return texto

        for candidato in sopa.select(
            "[class*=description], [class*=descripcion], [id*=description], "
            "[itemprop=description], .detail-description"
        ):
            texto = limpiar(candidato.get_text(" "))
            if _es_descripcion(texto) and len(texto) > 120:
                return texto
        return ""

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _texto(nodo, selector: str | None) -> str:
        if not selector:
            return ""
        encontrado = nodo.select_one(selector)
        return limpiar(encontrado.get_text(" ")) if encontrado else ""

    @staticmethod
    def _texto_attr(nodo, selector: str | None, attr: str) -> str:
        if not selector:
            return ""
        encontrado = nodo.select_one(selector)
        if encontrado and encontrado.has_attr(attr):
            return encontrado[attr]
        return ""


def _aplanar_jsonld(datos: Any) -> Iterable[dict]:
    """Recorre @graph / listas anidadas y devuelve los nodos de inmueble."""
    if isinstance(datos, list):
        for d in datos:
            yield from _aplanar_jsonld(d)
        return
    if not isinstance(datos, dict):
        return
    if "@graph" in datos:
        yield from _aplanar_jsonld(datos["@graph"])
    tipo = datos.get("@type", "")
    tipos = tipo if isinstance(tipo, list) else [tipo]
    interesantes = {
        "Product", "Offer", "RealEstateListing", "Residence", "Place",
        "Accommodation", "SingleFamilyResidence", "Apartment", "Office",
    }
    if any(t in interesantes for t in tipos):
        yield datos
    for valor in datos.values():
        if isinstance(valor, (list, dict)) and valor is not datos.get("@graph"):
            yield from _aplanar_jsonld(valor)


def _resumen_error(exc: Exception) -> str:
    """Mensaje corto y legible a partir de una excepción de requests."""
    texto = str(exc)
    for marca, resumen in (
        ("Tunnel connection failed", "bloqueado por el proxy de salida"),
        ("NameResolutionError", "dominio no resuelve"),
        ("SSLError", "error de TLS"),
        ("timed out", "tiempo de espera agotado"),
        ("403", "403 Forbidden (el portal rechaza al agente)"),
        ("404", "404: la URL de búsqueda ya no existe"),
    ):
        if marca in texto:
            return resumen
    return texto[:120]


def _es_numero(valor: Any) -> bool:
    try:
        float(str(valor).replace(",", "."))
        return True
    except (TypeError, ValueError):
        return False


# Texto que ponen los portales y que no describe el inmueble.
DECORADO = [
    "vista 3d", "modo satelite", "modo satélite", "puntos de interes",
    "puntos de interés", "calcula tu hipoteca", "cookies", "crea una alerta",
    "sé el primero", "se el primero", "guarda tu búsqueda", "guarda tu busqueda",
    "descarga la app", "politica de privacidad", "política de privacidad",
]


# Muletillas del propio portal dentro del bloque de descripción.
RUIDO = [
    "Traducciones disponibles:", "Mostrar más", "Mostrar menos", "Ver más",
    "Español", "Català", "English", "Deutsch", "Français",
]


def _sin_ruido(texto: str) -> str:
    for marca in RUIDO:
        texto = texto.replace(marca, " ")
    return limpiar(texto)


def _es_descripcion(texto: str) -> bool:
    """¿Esto lo escribió el anunciante o es el decorado del portal?"""
    if not texto or len(texto) < 15:
        return False
    minusculas = texto.lower()
    return not any(marca in minusculas for marca in DECORADO)


def _imagenes(sopa: BeautifulSoup, limite: int = 4) -> list[str]:
    """Fotos de la ficha, para poder mirarlas antes de recomendar nada.

    Prioriza la imagen social (og:image), que siempre es la principal, y
    completa con las de la galería.
    """
    urls: list[str] = []
    for meta in sopa.find_all("meta", property="og:image"):
        if meta.get("content", "").startswith("http"):
            urls.append(meta["content"])
    for img in sopa.find_all("img"):
        for attr in ("src", "data-src", "data-lazy", "data-original"):
            valor = img.get(attr, "")
            if valor.startswith("http") and any(
                ext in valor.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")
            ):
                urls.append(valor)
                break
    vistas: list[str] = []
    for u in urls:
        if u not in vistas and not any(x in u.lower() for x in ("logo", "icon", "sprite", "avatar")):
            vistas.append(u)
        if len(vistas) >= limite:
            break
    return vistas


_RE_FOTO = re.compile(r'https://[^"\'\s\\]+?\.(?:jpg|jpeg|png|webp)', re.IGNORECASE)


def _imagenes_crudas(html_bruto: str, limite: int = 4) -> list[str]:
    """Fotos rescatadas del HTML en bruto, para galerías cargadas por JS."""
    vistas: list[str] = []
    for url in _RE_FOTO.findall(html_bruto):
        bajo = url.lower()
        if any(x in bajo for x in ("logo", "icon", "sprite", "avatar", "placeholder", "banner")):
            continue
        if url not in vistas:
            vistas.append(url)
        if len(vistas) >= limite:
            break
    return vistas


_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_RE_TEL = re.compile(r"(?:\+34[\s.-]?)?(?:6|7|8|9)\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}")


def _primer_email(html: str) -> str:
    for m in _RE_EMAIL.findall(html):
        if not any(x in m.lower() for x in ("sentry", "example.com", ".png", ".jpg", "wixpress")):
            return m
    return ""


def _primer_telefono(html: str) -> str:
    m = _RE_TEL.search(html)
    return limpiar(m.group(0)) if m else ""
