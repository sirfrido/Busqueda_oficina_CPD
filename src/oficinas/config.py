"""Carga de configuración: YAML + variables de entorno + overrides locales.

Precedencia (de menor a mayor): config/*.yaml  <  config/local.yaml  <  entorno.
`config/local.yaml` está en .gitignore: es donde van los ajustes propios
(activar fuentes agresivas, cambiar umbrales) sin tocar el repositorio.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

def _raiz() -> Path:
    """Directorio de trabajo del agente (donde viven config/ y data/).

    Prioridad: $OFICINAS_HOME > el repositorio (ejecución desde el checkout) >
    el directorio actual (paquete instalado en otro sitio).
    """
    desde_entorno = os.getenv("OFICINAS_HOME")
    if desde_entorno:
        return Path(desde_entorno).resolve()
    repo = Path(__file__).resolve().parents[2]
    if (repo / "config" / "criteria.yaml").exists():
        return repo
    return Path.cwd()


RAIZ = _raiz()


def cargar_env(ruta: Path | str = ".env") -> None:
    """Lee un .env sencillo (KEY=valor) sin dependencias externas."""
    archivo = Path(ruta)
    if not archivo.is_absolute():
        archivo = RAIZ / archivo
    if not archivo.exists():
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def _fusionar(base: dict, encima: dict) -> dict:
    salida = dict(base)
    for clave, valor in (encima or {}).items():
        if isinstance(valor, dict) and isinstance(salida.get(clave), dict):
            salida[clave] = _fusionar(salida[clave], valor)
        else:
            salida[clave] = valor
    return salida


def _fusionar_fuentes(base: dict, encima: dict) -> dict:
    """Como _fusionar, pero la lista de fuentes se combina por `id`.

    Así config/local.yaml puede activar o retocar una fuente concreta sin
    tener que recopiar las veinte del repositorio.
    """
    salida = _fusionar(base, {k: v for k, v in (encima or {}).items() if k != "fuentes"})
    por_id = {f.get("id"): dict(f) for f in base.get("fuentes", [])}
    orden = list(por_id)
    for fuente in (encima or {}).get("fuentes", []) or []:
        fid = fuente.get("id")
        if fid in por_id:
            por_id[fid] = _fusionar(por_id[fid], fuente)
        else:
            por_id[fid] = dict(fuente)
            orden.append(fid)
    salida["fuentes"] = [por_id[fid] for fid in orden]
    return salida


def _leer_yaml(ruta: Path) -> dict:
    if not ruta.exists():
        return {}
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}


@dataclass
class ConfigEmail:
    remitente: str = ""
    destinatarios: list[str] = field(default_factory=list)
    smtp_host: str = ""
    smtp_puerto: int = 587
    smtp_usuario: str = ""
    smtp_password: str = ""
    smtp_tls: bool = True
    responder_a: str = ""

    @property
    def configurado(self) -> bool:
        return bool(self.smtp_host and self.remitente and self.destinatarios)


@dataclass
class Config:
    criterios: dict[str, Any]
    zonas: dict[str, Any]
    fuentes: dict[str, Any]
    email: ConfigEmail
    contacto_nombre: str = "Dirección de IT"
    contacto_empresa: str = ""
    contacto_telefono: str = ""
    email_contacto: str = ""
    db: str = "data/oficinas.sqlite3"
    cache_dir: str = "data/cache"
    salida_dir: str = "data/out"
    modelo_llm: str = "claude-opus-5"
    llm_effort: str = "medium"
    llm_activo: bool = True
    llm_max_anuncios: int = 40
    # Modo de contacto con la propiedad:
    #   borrador -> deja el email preparado y esperando aprobación (por defecto)
    #   auto     -> el agente envía solo (requiere activarlo a conciencia)
    #   off      -> no se preparan contactos
    modo_contacto: str = "borrador"
    # Medir la distancia real (Nominatim + OSRM). Se apaga en los tests y
    # cuando no hay red: entonces manda la tabla de `zonas.yaml`.
    geocodificar: bool = True

    @classmethod
    def cargar(cls, dir_config: Path | str = "config") -> "Config":
        cargar_env()
        base = Path(dir_config)
        if not base.is_absolute():
            base = RAIZ / base
        local = _leer_yaml(base / "local.yaml")

        criterios = _fusionar(_leer_yaml(base / "criteria.yaml"), local.get("criteria", {}))
        zonas = _fusionar(_leer_yaml(base / "zonas.yaml"), local.get("zonas", {}))
        fuentes = _fusionar_fuentes(_leer_yaml(base / "fuentes.yaml"), local.get("fuentes", {}))

        destinatarios = [
            d.strip() for d in os.getenv("EMAIL_DESTINATARIOS", "").split(",") if d.strip()
        ] or local.get("email", {}).get("destinatarios", [])

        email = ConfigEmail(
            remitente=os.getenv("EMAIL_REMITENTE", local.get("email", {}).get("remitente", "")),
            destinatarios=destinatarios,
            smtp_host=os.getenv("SMTP_HOST", local.get("email", {}).get("smtp_host", "")),
            smtp_puerto=int(os.getenv("SMTP_PUERTO", local.get("email", {}).get("smtp_puerto", 587))),
            smtp_usuario=os.getenv("SMTP_USUARIO", local.get("email", {}).get("smtp_usuario", "")),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_tls=os.getenv("SMTP_TLS", "1") not in ("0", "false", "False"),
            responder_a=os.getenv("EMAIL_RESPONDER_A", local.get("email", {}).get("responder_a", "")),
        )

        agente = local.get("agente", {})
        return cls(
            criterios=criterios,
            zonas=zonas,
            fuentes=fuentes,
            email=email,
            contacto_nombre=os.getenv("CONTACTO_NOMBRE", agente.get("contacto_nombre", "Dirección de IT")),
            contacto_empresa=os.getenv("CONTACTO_EMPRESA", agente.get("contacto_empresa", "")),
            contacto_telefono=os.getenv("CONTACTO_TELEFONO", agente.get("contacto_telefono", "")),
            email_contacto=os.getenv("EMAIL_CONTACTO", email.remitente),
            db=os.getenv("DB_PATH", agente.get("db", "data/oficinas.sqlite3")),
            cache_dir=agente.get("cache_dir", "data/cache"),
            salida_dir=agente.get("salida_dir", "data/out"),
            modelo_llm=os.getenv("MODELO_LLM", agente.get("modelo_llm", "claude-opus-5")),
            llm_effort=os.getenv("LLM_EFFORT", agente.get("llm_effort", "medium")),
            llm_activo=os.getenv("LLM_ACTIVO", "1") not in ("0", "false", "False"),
            llm_max_anuncios=int(os.getenv("LLM_MAX_ANUNCIOS", agente.get("llm_max_anuncios", 40))),
            modo_contacto=os.getenv("MODO_CONTACTO", agente.get("modo_contacto", "borrador")),
            geocodificar=os.getenv("GEOCODIFICAR", "1") not in ("0", "false", "False"),
        )

    # -- atajos -------------------------------------------------------------
    @property
    def umbral_email(self) -> float:
        return float(self.criterios.get("scoring", {}).get("umbral_email", 60))

    @property
    def umbral_contacto(self) -> float:
        return float(self.criterios.get("scoring", {}).get("umbral_contacto", 75))

    @property
    def umbral_descartar(self) -> float:
        return float(self.criterios.get("scoring", {}).get("umbral_descartar", 45))

    @property
    def max_minutos(self) -> float:
        """Minutos a partir de los cuales empieza a restar puntos."""
        return float(self.criterios.get("requisitos_duros", {}).get("max_minutos_coche", 15))

    @property
    def veto_minutos(self) -> float:
        """Minutos a partir de los cuales el inmueble queda descartado."""
        return float(
            self.criterios.get("requisitos_duros", {}).get("veto_minutos_coche", self.max_minutos + 7)
        )

    def ruta(self, relativa: str) -> Path:
        p = Path(relativa)
        return p if p.is_absolute() else RAIZ / p
