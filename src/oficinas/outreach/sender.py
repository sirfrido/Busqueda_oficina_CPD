"""Cola de contacto y envío por SMTP.

Política por defecto (`MODO_CONTACTO=borrador`): el agente REDACTA el email a
la propiedad y lo deja en estado «pendiente». No sale nada a un tercero sin
que tú lo apruebes, ni por error ni por una lectura optimista de un anuncio.

    oficinas contactos                 # ver la cola
    oficinas contactar --aprobar 3     # envía ese email
    oficinas contactar --aprobar-todos # envía todos los pendientes

Con `MODO_CONTACTO=auto` el agente envía él mismo los contactos de los
candidatos que superan el umbral. Es una decisión consciente: activa eso sólo
cuando lleves unos días viendo que lo que propone tiene sentido.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from ..config import Config
from ..models import Candidato
from ..storage import Almacen
from .composer import componer_contacto

log = logging.getLogger(__name__)


class EnviadorEmail:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    @property
    def configurado(self) -> bool:
        return self.cfg.email.configurado

    def enviar(
        self,
        destinatarios: list[str],
        asunto: str,
        cuerpo_texto: str,
        cuerpo_html: str | None = None,
        responder_a: str = "",
    ) -> None:
        mail = EmailMessage()
        mail["From"] = self.cfg.email.remitente
        mail["To"] = ", ".join(destinatarios)
        mail["Subject"] = asunto
        if responder_a or self.cfg.email.responder_a:
            mail["Reply-To"] = responder_a or self.cfg.email.responder_a
        mail.set_content(cuerpo_texto)
        if cuerpo_html:
            mail.add_alternative(cuerpo_html, subtype="html")

        e = self.cfg.email
        with smtplib.SMTP(e.smtp_host, e.smtp_puerto, timeout=30) as smtp:
            if e.smtp_tls:
                smtp.starttls()
            if e.smtp_usuario and e.smtp_password:
                smtp.login(e.smtp_usuario, e.smtp_password)
            smtp.send_message(mail)
        log.info("Email enviado a %s: %s", destinatarios, asunto)

    def guardar_borrador(self, ruta: Path, destinatarios: list[str], asunto: str, cuerpo: str) -> Path:
        """Escribe un .eml abrible desde cualquier cliente de correo."""
        mail = EmailMessage()
        mail["From"] = self.cfg.email.remitente
        mail["To"] = ", ".join(destinatarios) or "(destinatario por determinar)"
        mail["Subject"] = asunto
        if self.cfg.email.responder_a:
            mail["Reply-To"] = self.cfg.email.responder_a
        mail.set_content(cuerpo)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(bytes(mail))
        return ruta


def preparar_contactos(
    candidatos: list[Candidato],
    almacen: Almacen,
    cfg: Config,
    plantillas: dict[str, Any],
) -> list[dict[str, Any]]:
    """Redacta (y encola o envía) el contacto de los mejores candidatos."""
    if cfg.modo_contacto == "off":
        return []

    enviador = EnviadorEmail(cfg)
    preparados: list[dict[str, Any]] = []

    for cand in candidatos:
        if cand.puntuacion < cfg.umbral_contacto:
            continue
        if almacen.contacto_existente(cand.id):
            continue

        asunto, cuerpo = componer_contacto(
            cand.anuncio,
            cand.evaluacion,
            plantillas,
            firma_nombre=cfg.contacto_nombre,
            firma_empresa=cfg.contacto_empresa,
            firma_contacto=" · ".join(x for x in (cfg.email_contacto, cfg.contacto_telefono) if x),
        )
        destinatario = cand.anuncio.contacto_email
        estado = "pendiente"

        if cfg.modo_contacto == "auto" and destinatario and enviador.configurado:
            try:
                enviador.enviar([destinatario], asunto, cuerpo)
                estado = "enviado"
            except Exception as exc:
                log.error("No se pudo enviar el contacto de %s: %s", cand.anuncio.url, exc)

        id_contacto = almacen.crear_contacto(
            cand.id, destinatario, asunto, cuerpo, cand.anuncio.url, estado=estado
        )
        if estado == "enviado":
            almacen.actualizar_contacto(id_contacto, "enviado", "enviado automáticamente")
        else:
            ruta = cfg.ruta(cfg.salida_dir) / "borradores" / f"contacto-{id_contacto}.eml"
            enviador.guardar_borrador(ruta, [destinatario] if destinatario else [], asunto, cuerpo)

        almacen.marcar_enviado(cand.id, "contacto")
        preparados.append(
            {
                "id_contacto": id_contacto,
                "id_anuncio": cand.id,
                "estado": estado,
                "destinatario": destinatario,
                "asunto": asunto,
                "cuerpo": cuerpo,
                "url": cand.anuncio.url,
                "titulo": cand.anuncio.titulo,
            }
        )
    return preparados


def aprobar_y_enviar(almacen: Almacen, cfg: Config, id_contacto: int, destinatario: str = "") -> str:
    """Envía un contacto pendiente tras aprobación explícita."""
    fila = almacen.obtener_contacto(id_contacto)
    if fila is None:
        return f"No existe el contacto {id_contacto}"
    if fila["estado"] == "enviado":
        return f"El contacto {id_contacto} ya se envió el {fila['enviado_en']}"

    destino = destinatario or fila["destinatario"]
    if not destino:
        return (
            f"El contacto {id_contacto} no tiene email de destino (el anuncio sólo ofrece "
            f"formulario web). Usa el borrador o pásale el destinatario:\n"
            f"  oficinas contactar --aprobar {id_contacto} --para correo@agencia.com\n"
            f"  Anuncio: {fila['url']}"
        )

    enviador = EnviadorEmail(cfg)
    if not enviador.configurado:
        return "Falta configurar el SMTP (ver .env.example) para poder enviar."

    enviador.enviar([destino], fila["asunto"], fila["cuerpo"])
    almacen.actualizar_contacto(id_contacto, "enviado", f"aprobado manualmente → {destino}")
    return f"Contacto {id_contacto} enviado a {destino}"
