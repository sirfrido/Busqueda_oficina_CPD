"""Tipos y configuración de la vigilancia de marcas."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from oficinas.config import RAIZ, cargar_env


@dataclass
class Solicitud:
    """Una solicitud de marca publicada en el BOPI."""

    numero: str
    denominacion: str
    fecha_bopi: date
    clases: list[int] = field(default_factory=list)
    fuente: str = ""
    url: str = ""

    @property
    def fin_plazo_oposicion(self) -> date:
        """Dos meses desde la publicación (art. 19.3 Ley 17/2001 de Marcas)."""
        mes = self.fecha_bopi.month + 2
        anio = self.fecha_bopi.year + (mes - 1) // 12
        mes = (mes - 1) % 12 + 1
        dia = self.fecha_bopi.day
        while True:
            try:
                return date(anio, mes, dia)
            except ValueError:  # 31 de diciembre + 2 meses -> 28/29 de febrero
                dia -= 1


@dataclass
class Alerta:
    solicitud: Solicitud
    riesgo: str  # alto | medio | bajo
    similitud: list[str]
    motivo: str
    recomendacion: str = ""
    puntuacion_local: float = 0.0


@dataclass
class ConfigMarcas:
    marca: str
    nucleo: str
    actividad: str = ""
    clases_niza: list[int] = field(default_factory=list)
    ventana_dias: int = 21
    fuentes: list[str] = field(default_factory=lambda: ["imarcas", "oepm"])
    umbral_local: float = 0.85
    canario: str = ""
    modelo: str = "claude-opus-5-5"
    effort: str = "high"
    lote: int = 700
    salida_dir: str = "data/out/marcas"
    # Correo: las mismas variables que el informe de oficinas.
    smtp_host: str = ""
    smtp_puerto: int = 587
    smtp_usuario: str = ""
    smtp_password: str = ""
    smtp_tls: bool = True
    remitente: str = ""
    destinatarios: list[str] = field(default_factory=list)

    @property
    def email_configurado(self) -> bool:
        return bool(self.smtp_host and self.remitente and self.destinatarios)

    @classmethod
    def cargar(cls, ruta: Path | str = "config/marcas.yaml") -> "ConfigMarcas":
        cargar_env()
        archivo = Path(ruta)
        if not archivo.is_absolute():
            archivo = RAIZ / archivo
        datos: dict[str, Any] = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
        local = RAIZ / "config" / "local.yaml"
        if local.exists():
            datos.update((yaml.safe_load(local.read_text(encoding="utf-8")) or {}).get("marcas", {}))

        destinatarios = [
            d.strip()
            for d in (os.getenv("MARCAS_DESTINATARIOS") or os.getenv("EMAIL_DESTINATARIOS", "")).split(",")
            if d.strip()
        ]
        return cls(
            marca=os.getenv("MARCA_VIGILADA", datos.get("marca", "")),
            nucleo=os.getenv("MARCA_NUCLEO", datos.get("nucleo", "")),
            actividad=datos.get("actividad", ""),
            clases_niza=[int(c) for c in datos.get("clases_niza") or []],
            ventana_dias=int(datos.get("ventana_dias", 21)),
            fuentes=list(datos.get("fuentes") or ["imarcas", "oepm"]),
            umbral_local=float(datos.get("umbral_local", 0.85)),
            canario=datos.get("canario", ""),
            modelo=os.getenv("MODELO_MARCAS", datos.get("modelo", "claude-opus-5-5")),
            effort=os.getenv("EFFORT_MARCAS", datos.get("effort", "high")),
            lote=int(datos.get("lote", 700)),
            salida_dir=datos.get("salida_dir", "data/out/marcas"),
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_puerto=int(os.getenv("SMTP_PUERTO") or 587),
            smtp_usuario=os.getenv("SMTP_USUARIO", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_tls=os.getenv("SMTP_TLS", "1") not in ("0", "false", "False"),
            remitente=os.getenv("EMAIL_REMITENTE", ""),
            destinatarios=destinatarios,
        )
