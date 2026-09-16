"""Cliente HTTP educado: robots.txt, rate limit por host, caché y reintentos.

Un agente que se ejecuta a diario tiene que ser un buen ciudadano de la red:
identificarse, no machacar, cachear y no pisar lo que robots.txt prohíbe.
"""

from __future__ import annotations

import hashlib
import logging
import time
import urllib.robotparser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)


class RobotsBloqueado(RuntimeError):
    """La URL está prohibida por el robots.txt del sitio."""


@dataclass
class Respuesta:
    url: str
    texto: str
    desde_cache: bool = False
    status: int = 200


class Fetcher:
    def __init__(
        self,
        user_agent: str,
        cache_dir: Path | str = "data/cache",
        rate_limit: float = 4.0,
        timeout: float = 30.0,
        reintentos: int = 3,
        cache_ttl_horas: float = 6.0,
        respetar_robots: bool = True,
    ) -> None:
        self.user_agent = user_agent
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.reintentos = reintentos
        self.cache_ttl = cache_ttl_horas * 3600
        self.respetar_robots = respetar_robots
        self._ultimo_acceso: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.sesion = requests.Session()
        self.sesion.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Language": "es-ES,es;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            }
        )

    # -- robots -------------------------------------------------------------
    def _robots_para(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        host = urlparse(url).netloc
        if host not in self._robots:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(f"{urlparse(url).scheme}://{host}/robots.txt")
            try:
                parser.read()
            except Exception as exc:  # sin robots.txt accesible: se asume permitido
                log.debug("robots.txt no accesible en %s (%s)", host, exc)
                parser = None
            self._robots[host] = parser
        return self._robots[host]

    def permitido(self, url: str) -> bool:
        if not self.respetar_robots:
            return True
        parser = self._robots_para(url)
        if parser is None:
            return True
        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:
            return True

    def _espera(self, url: str) -> None:
        host = urlparse(url).netloc
        demora = self.rate_limit
        parser = self._robots.get(host)
        if parser is not None:
            try:
                crawl = parser.crawl_delay(self.user_agent)
                if crawl:
                    demora = max(demora, float(crawl))
            except Exception:
                pass
        ultimo = self._ultimo_acceso.get(host)
        if ultimo is not None:
            restante = demora - (time.monotonic() - ultimo)
            if restante > 0:
                time.sleep(restante)
        self._ultimo_acceso[host] = time.monotonic()

    # -- caché --------------------------------------------------------------
    def _ruta_cache(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.sha1(url.encode()).hexdigest()}.html"

    def _leer_cache(self, url: str) -> str | None:
        ruta = self._ruta_cache(url)
        if ruta.exists() and (time.time() - ruta.stat().st_mtime) < self.cache_ttl:
            return ruta.read_text(encoding="utf-8", errors="replace")
        return None

    # -- descarga -----------------------------------------------------------
    def get(self, url: str, *, usar_cache: bool = True, params: dict | None = None) -> Respuesta:
        if not self.permitido(url):
            raise RobotsBloqueado(f"robots.txt prohíbe {url}")

        if usar_cache and not params:
            cacheado = self._leer_cache(url)
            if cacheado is not None:
                return Respuesta(url=url, texto=cacheado, desde_cache=True)

        ultimo_error: Exception | None = None
        for intento in range(1, self.reintentos + 1):
            self._espera(url)
            try:
                resp = self.sesion.get(url, params=params, timeout=self.timeout)
                if resp.status_code in (429, 503):
                    espera = float(resp.headers.get("Retry-After", 2 ** intento))
                    log.warning("%s devolvió %s; esperando %.0fs", url, resp.status_code, espera)
                    time.sleep(min(espera, 60))
                    continue
                resp.raise_for_status()
                if usar_cache and not params:
                    self._ruta_cache(url).write_text(resp.text, encoding="utf-8")
                return Respuesta(url=resp.url, texto=resp.text, status=resp.status_code)
            except requests.RequestException as exc:
                ultimo_error = exc
                log.warning("Intento %d/%d falló en %s: %s", intento, self.reintentos, url, exc)
                time.sleep(2 ** intento)
        raise RuntimeError(f"No se pudo descargar {url}: {ultimo_error}")

    def post_json(self, url: str, **kwargs) -> dict:
        self._espera(url)
        resp = self.sesion.post(url, timeout=self.timeout, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def get_json(self, url: str, **kwargs) -> dict:
        self._espera(url)
        resp = self.sesion.get(url, timeout=self.timeout, **kwargs)
        resp.raise_for_status()
        return resp.json()
