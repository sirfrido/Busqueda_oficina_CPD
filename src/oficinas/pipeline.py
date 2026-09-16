"""Orquestación de la pasada diaria.

    fuentes → deduplicación → filtro geográfico y de superficie → ficha de
    detalle → señales → cualificador LLM → filtros duros → puntuación →
    informe por email → cola de contacto

El orden importa por coste: lo barato y determinista descarta primero, así el
modelo sólo ve los anuncios que de verdad pueden encajar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import yaml

from .config import Config
from .fetch import Fetcher
from .filtros import aplicar as aplicar_filtros, rango_superficie
from .geo import MapaZonas, estimar_minutos, distancia_km, minutos_en_coche
from .models import Anuncio, Candidato
from .notify.email_digest import enviar_digest
from .outreach.sender import preparar_contactos
from .qualifier import Cualificador
from .scoring import puntuar
from .senales import detectar
from .sources import crear_fuente
from .storage import Almacen
from .textutils import normalizar

log = logging.getLogger(__name__)


@dataclass
class Resumen:
    analizados: int = 0
    nuevos: int = 0
    descartados: int = 0
    candidatos: int = 0
    en_vigilancia: int = 0
    fuentes_ok: int = 0
    fuentes_error: int = 0
    por_fuente: dict[str, int] = field(default_factory=dict)
    errores: list[str] = field(default_factory=list)
    mensaje_email: str = ""
    contactos_preparados: int = 0

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class Agente:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.zonas = MapaZonas(cfg.zonas)
        self.almacen = Almacen(cfg.ruta(cfg.db))
        defaults = cfg.fuentes.get("defaults", {})
        self.defaults = defaults
        self.fetcher = Fetcher(
            user_agent=str(defaults.get("user_agent", "BusquedaOficinaCPD/0.1")).replace(
                "{EMAIL_CONTACTO}", cfg.email_contacto or "sin-contacto"
            ),
            cache_dir=cfg.ruta(cfg.cache_dir),
            rate_limit=float(defaults.get("rate_limit_segundos", 4)),
            timeout=float(defaults.get("timeout_segundos", 30)),
            reintentos=int(defaults.get("reintentos", 3)),
            respetar_robots=bool(defaults.get("respetar_robots", True)),
        )
        self.cualificador = Cualificador(
            modelo=cfg.modelo_llm,
            effort=cfg.llm_effort,
            activo=cfg.llm_activo,
            max_anuncios=cfg.llm_max_anuncios,
        )
        self.plantillas = yaml.safe_load(
            (cfg.ruta("config") / "plantillas.yaml").read_text(encoding="utf-8")
        )

    # -- 1. recolección -----------------------------------------------------
    def recolectar(self, solo: list[str] | None = None) -> tuple[list[Anuncio], dict[str, Any], Resumen]:
        resumen = Resumen()
        anuncios: list[Anuncio] = []
        fuentes_por_id: dict[str, Any] = {}

        for cfg_fuente in self.cfg.fuentes.get("fuentes", []):
            id_fuente = cfg_fuente.get("id")
            if solo and id_fuente not in solo:
                continue
            if not solo and not cfg_fuente.get("activo", False):
                continue
            fuente = crear_fuente(cfg_fuente, self.fetcher, self.defaults)
            if fuente is None:
                continue
            fuentes_por_id[id_fuente] = fuente
            try:
                encontrados = fuente.buscar()
                resumen.por_fuente[id_fuente] = len(encontrados)
                resumen.fuentes_ok += 1
                anuncios.extend(encontrados)
                log.info("[%s] %d anuncios", id_fuente, len(encontrados))
            except Exception as exc:
                resumen.fuentes_error += 1
                resumen.errores.append(f"{id_fuente}: {exc}")
                log.error("[%s] error: %s", id_fuente, exc)
        return anuncios, fuentes_por_id, resumen

    # -- 2. deduplicación ---------------------------------------------------
    @staticmethod
    def deduplicar(anuncios: list[Anuncio], tol_m2: float = 0.05, tol_precio: float = 0.03) -> list[Anuncio]:
        """Un mismo inmueble aparece en varios portales: se queda el primero.

        No se usan cubos fijos (dos anuncios casi idénticos pueden caer a
        ambos lados del corte) sino comparación por tolerancia: mismo
        municipio, superficie dentro del ±5 % y precio dentro del ±3 % es,
        en la práctica, el mismo inmueble publicado dos veces.
        """
        vistos: set[str] = set()
        salida: list[Anuncio] = []
        for a in anuncios:
            if a.id in vistos:
                continue
            vistos.add(a.id)
            if a.superficie_m2 and a.precio_eur and a.municipio:
                municipio = normalizar(a.municipio)
                duplicado = any(
                    normalizar(b.municipio) == municipio
                    and b.superficie_m2 and b.precio_eur
                    and abs(b.superficie_m2 - a.superficie_m2) <= tol_m2 * a.superficie_m2
                    and abs(b.precio_eur - a.precio_eur) <= tol_precio * a.precio_eur
                    for b in salida
                )
                if duplicado:
                    continue
            salida.append(a)
        return salida

    # -- 3. evaluación de un anuncio ---------------------------------------
    def evaluar(self, anuncio: Anuncio, fuente: Any | None, usar_llm: bool) -> Candidato:
        zona = self.zonas.resolver(
            " ".join(x for x in (anuncio.municipio, anuncio.zona, anuncio.direccion, anuncio.titulo) if x),
            max_minutos=self.cfg.max_minutos,
        )
        if zona.municipio:
            anuncio.municipio = anuncio.municipio or zona.municipio

        # Con coordenadas, tiempo real en coche; si no, la tabla de zonas.
        minutos = zona.minutos_coche
        if anuncio.lat and anuncio.lon:
            centro = tuple(self.cfg.criterios.get("geo", {}).get("centro_referencia", [39.4699, -0.3763]))
            real = minutos_en_coche(centro, (anuncio.lat, anuncio.lon))
            minutos = real if real is not None else estimar_minutos(distancia_km(centro, (anuncio.lat, anuncio.lon)))

        # Ficha de detalle: ahí está la letra pequeña (potencia, cubierta).
        if fuente is not None and hasattr(fuente, "detalle") and zona.admitida:
            try:
                anuncio = fuente.detalle(anuncio)
            except Exception as exc:
                log.debug("detalle no disponible para %s: %s", anuncio.url, exc)

        ev = detectar(anuncio)
        ev.zona_admitida = zona.admitida
        ev.motivo_descarte = "" if zona.admitida else zona.motivo
        ev.riesgo_inundacion = zona.riesgo_inundacion
        ev.minutos_coche = minutos

        if usar_llm and zona.admitida:
            ev = self.cualificador.evaluar(anuncio, ev)
            ev.zona_admitida = zona.admitida
            ev.riesgo_inundacion = zona.riesgo_inundacion
            ev.minutos_coche = minutos

        se_mantiene, motivo = aplicar_filtros(anuncio, ev, self.cfg.criterios)
        if not se_mantiene:
            ev.motivo_descarte = motivo
        puntuacion, desglose = puntuar(anuncio, ev, self.cfg.criterios, bonus_zona=zona.bonus)
        return Candidato(
            anuncio=anuncio,
            evaluacion=ev,
            puntuacion=puntuacion,
            desglose=desglose,
            descartado=not se_mantiene or puntuacion < self.cfg.umbral_descartar,
        )

    def _prefiltro(self, anuncio: Anuncio) -> str:
        """Descarte barato antes de gastar red o modelo. '' = sigue vivo."""
        minimo, maximo = rango_superficie(self.cfg.criterios)
        if anuncio.superficie_m2 is not None and not (minimo <= anuncio.superficie_m2 <= maximo):
            return f"{anuncio.superficie_m2:g} m² fuera de {minimo:g}-{maximo:g}"
        zona = self.zonas.resolver(
            " ".join(x for x in (anuncio.municipio, anuncio.zona, anuncio.direccion, anuncio.titulo) if x),
            max_minutos=self.cfg.max_minutos,
        )
        return "" if zona.admitida else zona.motivo

    # -- 4. pasada completa -------------------------------------------------
    def ejecutar(
        self,
        solo_fuentes: list[str] | None = None,
        limite: int | None = None,
        enviar: bool = True,
        reenviar_vistos: bool = False,
    ) -> Resumen:
        anuncios, fuentes, resumen = self.recolectar(solo_fuentes)
        anuncios = self.deduplicar(anuncios)
        resumen.analizados = len(anuncios)

        vivos: list[Anuncio] = []
        for anuncio in anuncios:
            es_nuevo = self.almacen.guardar_anuncio(anuncio)
            resumen.nuevos += int(es_nuevo)
            if not reenviar_vistos and self.almacen.ya_enviado(anuncio.id, "digest"):
                continue
            motivo = self._prefiltro(anuncio)
            if motivo:
                resumen.descartados += 1
                log.debug("descartado en prefiltro: %s (%s)", anuncio.url, motivo)
                continue
            vivos.append(anuncio)

        if limite:
            vivos = vivos[:limite]

        # El LLM se reserva para los que llegan vivos, y con tope diario.
        presupuesto_llm = self.cfg.llm_max_anuncios
        candidatos: list[Candidato] = []
        for anuncio in vivos:
            usar_llm = presupuesto_llm > 0
            cand = self.evaluar(anuncio, fuentes.get(anuncio.fuente), usar_llm=usar_llm)
            if usar_llm and cand.evaluacion.evaluado_por != "heuristica":
                presupuesto_llm -= 1
            self.almacen.guardar_evaluacion(cand)
            if cand.descartado:
                resumen.descartados += 1
            else:
                candidatos.append(cand)

        candidatos.sort(key=lambda c: c.puntuacion, reverse=True)
        para_email = [c for c in candidatos if c.puntuacion >= self.cfg.umbral_email]
        # Cumplen los filtros duros pero el anuncio calla lo importante: se
        # listan aparte en vez de tirarlos, que es donde está media Valencia.
        vigilar = [c for c in candidatos if c not in para_email]
        resumen.candidatos = len(para_email)
        resumen.en_vigilancia = len(vigilar)

        contactos_preparados = preparar_contactos(para_email, self.almacen, self.cfg, self.plantillas)
        resumen.contactos_preparados = len(contactos_preparados)
        contactos = {c["id_anuncio"]: c for c in contactos_preparados}
        for cand in para_email:
            if cand.id not in contactos:
                fila = self.almacen.contacto_existente(cand.id)
                if fila:
                    contactos[cand.id] = {
                        "id_contacto": fila["id"], "estado": fila["estado"],
                        "destinatario": fila["destinatario"], "asunto": fila["asunto"],
                        "cuerpo": fila["cuerpo"], "url": fila["url"],
                    }

        resumen.mensaje_email = enviar_digest(
            para_email, contactos, self.cfg, resumen.to_dict(),
            solo_guardar=not enviar, vigilar=vigilar,
        )
        if enviar:
            for cand in para_email:
                self.almacen.marcar_enviado(cand.id, "digest")
        return resumen

    def cerrar(self) -> None:
        self.almacen.cerrar()
