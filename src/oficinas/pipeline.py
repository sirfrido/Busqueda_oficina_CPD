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

from .bandas import evaluar as evaluar_bandas, resumen_excesos
from .config import Config
from .fetch import Fetcher
from .filtros import aplicar as aplicar_filtros, limites_absolutos
from .geo import (
    Geocodificador,
    MapaZonas,
    ResultadoZona,
    distancia_km,
    estimar_minutos,
    minutos_en_coche,
)
from .models import Anuncio, Candidato
from .notify.email_digest import enviar_digest
from .outreach.sender import preparar_contactos
from .qualifier import Cualificador
from .scoring import puntuar
from .senales import detectar
from .verificacion import pregunta_prioritaria, verificar
from .vision import OjoCritico
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
    umbral_aplicado: float = 0.0
    desmentidos_por_las_fotos: int = 0
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
        self.geocodificador = Geocodificador(
            cache=cfg.ruta(cfg.cache_dir) / "geo.json",
            user_agent=f"BusquedaOficinaCPD/0.1 ({cfg.email_contacto or 'sin-contacto'})",
        )
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
        self.ojo = OjoCritico(modelo=cfg.modelo_llm, activo=cfg.llm_activo)
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
            max_minutos=self.cfg.veto_minutos,
        )
        if zona.municipio:
            anuncio.municipio = anuncio.municipio or zona.municipio

        # Con coordenadas, tiempo real en coche; si no, la tabla de zonas; y
        # si el municipio no está en la tabla, se localiza y se mide: así no
        # se cuela una nave de Gandía o de Ademuz por no estar en la lista.
        centro = tuple(self.cfg.criterios.get("geo", {}).get("centro_referencia", [39.4699, -0.3763]))
        # Se mide SIEMPRE que se pueda: la tabla de `zonas.yaml` es sólo el
        # respaldo cuando no hay red. (La tabla decía 20 min a Náquera; el
        # cálculo real dice 31.)
        minutos = zona.minutos_coche
        destino: tuple[float, float] | None = None
        if anuncio.lat and anuncio.lon:
            destino = (anuncio.lat, anuncio.lon)
        elif self.cfg.geocodificar and (anuncio.municipio or zona.municipio):
            destino = self.geocodificador.coordenadas(anuncio.municipio or zona.municipio)
        radio_max = float(self.cfg.criterios.get("geo", {}).get("radio_max_km", 30))
        if destino and self.cfg.geocodificar:
            # Filtro barato antes de pedir ruta: los listados de los portales
            # mezclan municipios de otras provincias (salieron pueblos del
            # Penedès entre las naves de Valencia).
            en_linea_recta = distancia_km(centro, destino)
            if en_linea_recta > radio_max:
                zona = ResultadoZona(
                    admitida=False,
                    municipio=anuncio.municipio or zona.municipio,
                    motivo=f"A {en_linea_recta:.0f} km en línea recta: fuera del área de búsqueda",
                )
                minutos = None
            else:
                real = minutos_en_coche(centro, destino)
                if real is None:
                    real = estimar_minutos(en_linea_recta)
                if real is not None:
                    minutos = real
                    anuncio.extra["distancia_calculada"] = f"{real:.0f} min en coche (medido)"
        elif zona.desconocido and self.cfg.geocodificar:
            # Municipio que no está en las listas y que ni siquiera se puede
            # situar: no se recomienda a ciegas ni se deja en "Casi".
            zona = ResultadoZona(
                admitida=False,
                municipio=anuncio.municipio,
                motivo=f"No se ha podido situar «{anuncio.municipio or 'el municipio'}»: fuera",
            )

        # Ficha de detalle: ahí está la letra pequeña (potencia, cubierta).
        if fuente is not None and hasattr(fuente, "detalle") and zona.admitida:
            try:
                anuncio = fuente.detalle(anuncio)
            except Exception as exc:
                log.debug("detalle no disponible para %s: %s", anuncio.url, exc)

        ev = detectar(anuncio)

        # ¿Hay realmente algo construido? Una ficha de seis palabras sin un
        # solo elemento constructivo no acredita nada.
        verificacion = verificar(anuncio)
        ev.es_construido = verificacion.es_construido
        ev.avisos_ficha = verificacion.avisos
        primera = pregunta_prioritaria(verificacion, anuncio)
        if primera:
            ev.preguntas_clave.insert(0, primera)
        if verificacion.sospecha_solar or verificacion.ficha_pobre:
            anuncio.extra["verificar_ficha"] = "; ".join(verificacion.avisos[:2])

        ev.zona_admitida = zona.admitida
        ev.motivo_descarte = "" if zona.admitida else zona.motivo
        ev.riesgo_inundacion = zona.riesgo_inundacion
        ev.minutos_coche = minutos
        # Municipio desconocido y sin distancia medible: no se recomienda a
        # ciegas, se queda en "Casi" para revisión.
        municipio_sin_medir = zona.desconocido and minutos is None

        if usar_llm and zona.admitida:
            ev = self.cualificador.evaluar(anuncio, ev)
            ev.zona_admitida = zona.admitida
            ev.riesgo_inundacion = zona.riesgo_inundacion
            ev.minutos_coche = minutos

        se_mantiene, motivo = aplicar_filtros(anuncio, ev, self.cfg.criterios)
        if not se_mantiene:
            ev.motivo_descarte = motivo

        bandas = evaluar_bandas(anuncio, ev, self.cfg.criterios)
        puntuacion, desglose = puntuar(
            anuncio, ev, self.cfg.criterios, bonus_zona=zona.bonus, bandas=bandas
        )

        # Regla de compensación: pasarse en un eje se perdona; pasarse en dos
        # sólo lo salva una puntuación sobresaliente en todo lo demás.
        scoring = self.cfg.criterios.get("scoring", {})
        max_excesos = int(scoring.get("max_excesos_sin_excelencia", 1))
        excelencia = float(scoring.get("puntuacion_excelencia", 85))
        if se_mantiene and len(bandas.ejes_excedidos) > max_excesos and puntuacion < excelencia:
            se_mantiene = False
            ev.motivo_descarte = (
                f"Se sale por varios sitios a la vez ({resumen_excesos(bandas)}) "
                f"y no compensa con el resto"
            )

        if bandas.excesos:
            anuncio.extra["excesos"] = resumen_excesos(bandas)
        return Candidato(
            anuncio=anuncio,
            evaluacion=ev,
            puntuacion=puntuacion,
            desglose=desglose,
            descartado=not se_mantiene or puntuacion < self.cfg.umbral_descartar,
            solo_casi=not verificacion.recomendable or municipio_sin_medir,
        )

    def umbral_efectivo(self) -> float:
        """Listón del día, ajustado al caudal de las últimas semanas.

        Si apenas ha entrado nada, se baja para no dejar al usuario a ciegas;
        si ha entrado mucho, se sube para que el email siga siendo corto.
        """
        base = self.cfg.umbral_email
        cfg = self.cfg.criterios.get("scoring", {}).get("adaptativo", {})
        if not cfg.get("activo", False):
            return base
        recientes = self.almacen.enviados_ultimos_dias(int(cfg.get("dias_ventana", 7)))
        if recientes < int(cfg.get("pocos_si_menos_de", 3)):
            return max(self.cfg.umbral_descartar, base - float(cfg.get("baja_umbral", 10)))
        if recientes > int(cfg.get("muchos_si_mas_de", 12)):
            return base + float(cfg.get("sube_umbral", 8))
        return base

    def _prefiltro(self, anuncio: Anuncio) -> str:
        """Descarte barato antes de gastar red o modelo. '' = sigue vivo.

        Por arriba se usa el tramo ampliado (hasta 500 m²): si el inmueble
        está impecable puede compensar, y eso lo decide la evaluación
        completa, no este corte previo.
        """
        minimo, maximo = limites_absolutos(self.cfg.criterios)
        if anuncio.superficie_m2 is not None and not (minimo <= anuncio.superficie_m2 <= maximo):
            return f"{anuncio.superficie_m2:g} m² fuera de {minimo:g}-{maximo:g}"
        zona = self.zonas.resolver(
            " ".join(x for x in (anuncio.municipio, anuncio.zona, anuncio.direccion, anuncio.titulo) if x),
            max_minutos=self.cfg.veto_minutos,
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
        umbral = self.umbral_efectivo()
        resumen.umbral_aplicado = umbral
        para_email = [c for c in candidatos if c.puntuacion >= umbral and not c.solo_casi]
        # Cumplen los filtros duros pero el anuncio calla lo importante: se
        # listan aparte en vez de tirarlos, que es donde está media Valencia.
        # "Casi": los que se quedan a tiro del umbral. No se tiran nunca en
        # silencio; van al final del email con una línea de qué les falta.
        margen = float(self.cfg.criterios.get("scoring", {}).get("margen_casi", 15))
        ids_email = {c.id for c in para_email}
        vigilar = [
            c for c in candidatos
            if c.id not in ids_email and (c.solo_casi or c.puntuacion >= umbral - margen)
        ]
        resumen.candidatos = len(para_email)
        resumen.en_vigilancia = len(vigilar)

        # Último control antes de recomendar: mirar las fotos. Un solar
        # publicado como nave se cae aquí aunque el texto fuese impecable.
        para_email, desmentidos = self._revisar_fotos(para_email)
        resumen.desmentidos_por_las_fotos = len(desmentidos)
        vigilar = desmentidos + vigilar
        resumen.candidatos = len(para_email)

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

    def _revisar_fotos(self, candidatos: list[Candidato], maximo: int = 6) -> tuple[list[Candidato], list[Candidato]]:
        """Devuelve (los que las fotos confirman, los que las fotos desmienten)."""
        if not self.ojo.activo:
            return candidatos, []
        confirmados: list[Candidato] = []
        desmentidos: list[Candidato] = []
        for cand in candidatos:
            if len(confirmados) + len(desmentidos) >= maximo:
                confirmados.append(cand)
                continue
            vistazo = self.ojo.mirar(cand.anuncio)
            if vistazo is None:
                confirmados.append(cand)
                continue
            cand.anuncio.extra["vistazo"] = {
                "tipo": vistazo.tipo,
                "estado": vistazo.estado_aparente,
                "cubierta_visible": vistazo.cubierta_visible,
                "descripcion": vistazo.descripcion,
                "fotos": vistazo.fotos_vistas,
            }
            if vistazo.desmiente_el_anuncio:
                cand.descartado = True
                cand.solo_casi = True
                cand.evaluacion.motivo_descarte = (
                    f"Las fotos desmienten el anuncio: se ve {vistazo.tipo}. {vistazo.descripcion}"
                )
                cand.anuncio.extra["verificar_ficha"] = cand.evaluacion.motivo_descarte
                desmentidos.append(cand)
                log.info("[fotos] descartado %s: %s", cand.anuncio.url, vistazo.tipo)
            else:
                if vistazo.cubierta_visible == "si" and cand.evaluacion.cubierta_ampliable == "verificar":
                    cand.evaluacion.senales_positivas.append("En las fotos se ve la cubierta")
                confirmados.append(cand)
        return confirmados, desmentidos

    def cerrar(self) -> None:
        self.almacen.cerrar()
