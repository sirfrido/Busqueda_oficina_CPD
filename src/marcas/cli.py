"""Línea de comandos de la vigilancia de marcas.

    vigilancia-marcas revisar                       # semana anterior a hoy
    vigilancia-marcas revisar --sin-email
    vigilancia-marcas revisar --desde 2026-10-14 --hasta 2026-10-20
    vigilancia-marcas diagnostico
"""

from __future__ import annotations

import argparse
import json
import logging
import smtplib
import sys
from datetime import date, timedelta
from email.message import EmailMessage
from pathlib import Path

from oficinas.config import RAIZ

from . import informe
from .analisis import Analizador, combinar
from .fuentes import FuenteNoDisponible, imarcas, oepm, sesion
from .modelos import ConfigMarcas, Solicitud
from .similitud import puntuar

log = logging.getLogger("marcas")

FUENTES = {"imarcas": imarcas.descargar, "oepm": oepm.descargar}
# BOPI ya revisados: si imarcas publica tarde el listado de un día, la pasada
# siguiente lo recoge en vez de perderlo entre dos semanas.
ESTADO = RAIZ / "data" / "marcas" / "bopi_revisados.json"


def leer_estado() -> set[date]:
    try:
        return {date.fromisoformat(d) for d in json.loads(ESTADO.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return set()


def guardar_estado(fechas: set[date]) -> None:
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    recientes = sorted(d.isoformat() for d in fechas if d >= date.today() - timedelta(days=120))
    ESTADO.write_text(json.dumps(recientes, indent=0) + "\n", encoding="utf-8")


def recoger(
    cfg: ConfigMarcas, desde: date, hasta: date, r: informe.Resultado, saltar: set[date] = frozenset()
) -> list[Solicitud]:
    """Todas las fuentes que respondan, sin duplicar números de solicitud.

    `saltar` son los BOPI ya revisados: las fuentes no los descargan.
    """
    http = sesion()
    por_numero: dict[str, Solicitud] = {}
    for nombre in cfg.fuentes:
        try:
            lote = FUENTES[nombre](desde, hasta, http, saltar)
        except (FuenteNoDisponible, KeyError) as exc:
            r.errores.append(str(exc) if not isinstance(exc, KeyError) else f"fuente desconocida: {nombre}")
            continue
        except Exception as exc:  # una fuente rota no tumba la pasada
            log.exception("Fuente %s", nombre)
            r.errores.append(f"{nombre}: {exc}")
            continue
        r.fuentes_ok.append(f"{nombre} ({len(lote)})")
        for s in lote:
            por_numero.setdefault(s.numero, s)
    return list(por_numero.values())


def revisar(
    cfg: ConfigMarcas,
    desde: date,
    hasta: date,
    analizador: Analizador | None = None,
    ya_revisados: set[date] = frozenset(),
    exportar: str | None = None,
) -> informe.Resultado:
    r = informe.Resultado(marca=cfg.marca, desde=desde, hasta=hasta)
    solicitudes = [s for s in recoger(cfg, desde, hasta, r, ya_revisados) if s.fecha_bopi not in ya_revisados]
    if exportar:
        # Lista completa (número | denominación | clases | fecha) para que la
        # revise otro proceso, p. ej. una sesión de Claude sin API key.
        Path(exportar).parent.mkdir(parents=True, exist_ok=True)
        Path(exportar).write_text(
            "".join(
                f"{s.numero} | {s.denominacion} | {', '.join(map(str, s.clases)) or '-'} | {s.fecha_bopi:%d/%m/%Y}\n"
                for s in solicitudes
            ),
            encoding="utf-8",
        )
    r.revisadas = len(solicitudes)
    r.dias_bopi = sorted({s.fecha_bopi for s in solicitudes})
    if not solicitudes:
        return r

    locales = {s.numero: puntuar(s.denominacion, cfg.nucleo) for s in solicitudes}
    del_modelo: list[dict] = []
    analizador = analizador or Analizador(cfg)
    if analizador.activo:
        try:
            del_modelo, r.canario = analizador.analizar(solicitudes)
            r.con_modelo = True
        except Exception as exc:
            log.exception("Análisis con Claude")
            r.errores.append(f"Claude: {exc}")
    r.alertas, r.solo_locales = combinar(solicitudes, del_modelo, locales, cfg.umbral_local)
    if not r.con_modelo:
        # Sin modelo, lo que pasa el umbral local ES la alerta.
        for a in r.solo_locales:
            a.riesgo = "medio" if a.puntuacion_local >= 0.9 else "bajo"
            a.similitud = ["grafica/fonetica"]
        r.alertas, r.solo_locales = r.solo_locales, []
    return r


def enviar(cfg: ConfigMarcas, r: informe.Resultado) -> None:
    mail = EmailMessage()
    mail["From"] = cfg.remitente
    mail["To"] = ", ".join(cfg.destinatarios)
    mail["Subject"] = r.asunto
    mail.set_content(informe.texto(r))
    mail.add_alternative(informe.html(r), subtype="html")
    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_puerto, timeout=30) as smtp:
        if cfg.smtp_tls:
            smtp.starttls()
        if cfg.smtp_usuario and cfg.smtp_password:
            smtp.login(cfg.smtp_usuario, cfg.smtp_password)
        smtp.send_message(mail)


def cmd_revisar(args: argparse.Namespace) -> int:
    cfg = ConfigMarcas.cargar()
    hasta = date.fromisoformat(args.hasta) if args.hasta else date.today() - timedelta(days=1)
    desde = date.fromisoformat(args.desde) if args.desde else hasta - timedelta(days=cfg.ventana_dias - 1)
    if args.fuentes:
        cfg.fuentes = args.fuentes.split(",")
    if args.guardar_pdf:
        oepm.GUARDAR_PDF = Path(args.guardar_pdf)
    # Con fechas explícitas se revisa todo; en la pasada normal se saltan los
    # BOPI que ya salieron en un informe anterior.
    explicito = bool(args.desde or args.hasta)
    revisados = set() if explicito else leer_estado()

    r = revisar(cfg, desde, hasta, ya_revisados=revisados, exportar=args.exportar)
    if not explicito and r.dias_bopi and not any(e.startswith("Claude") for e in r.errores):
        guardar_estado(revisados | set(r.dias_bopi))

    salida = RAIZ / cfg.salida_dir
    salida.mkdir(parents=True, exist_ok=True)
    ruta = salida / f"informe-{hasta:%Y-%m-%d}.html"
    ruta.write_text(informe.html(r), encoding="utf-8")
    (salida / "ultimo-informe.html").write_text(informe.html(r), encoding="utf-8")

    print(r.asunto)
    print()
    print(informe.texto(r))
    print(f"\nInforme: {ruta}")

    if not args.sin_email:
        if cfg.email_configurado:
            enviar(cfg, r)
            print(f"Email enviado a {', '.join(cfg.destinatarios)}")
        else:
            print("SMTP sin configurar: no se envía email (ver .env.example).")
    return 0 if r.revisadas else 2


def cmd_diagnostico(args: argparse.Namespace) -> int:
    hasta = date.today()
    desde = hasta - timedelta(days=7)
    http = sesion()
    for nombre, funcion in FUENTES.items():
        try:
            lote = funcion(desde, hasta, http)
            dias = sorted({s.fecha_bopi for s in lote})
            print(f"{nombre:8} ok       {len(lote):5} solicitudes, BOPI de {', '.join(f'{d:%d/%m}' for d in dias) or '-'}")
        except Exception as exc:
            print(f"{nombre:8} FALLA    {exc}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="vigilancia-marcas", description=__doc__.splitlines()[0])
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    rv = sub.add_parser("revisar", help="revisa la semana y envía el informe")
    rv.add_argument("--sin-email", action="store_true")
    rv.add_argument("--desde", help="AAAA-MM-DD (por defecto: ventana_dias antes de --hasta)")
    rv.add_argument("--hasta", help="AAAA-MM-DD (por defecto: ayer)")
    rv.add_argument("--fuentes", help="lista separada por comas: imarcas,oepm")
    rv.add_argument("--exportar", help="guarda aquí la lista completa de solicitudes revisadas")
    rv.add_argument("--guardar-pdf", help="guarda aquí los Tomo 1 descargados de la OEPM (para marcas.logos)")
    rv.set_defaults(func=cmd_revisar)

    dg = sub.add_parser("diagnostico", help="¿qué fuentes responden?")
    dg.set_defaults(func=cmd_diagnostico)

    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
