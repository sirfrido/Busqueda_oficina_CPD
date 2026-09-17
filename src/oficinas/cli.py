"""Interfaz de línea de comandos del agente.

    oficinas buscar                  # pasada completa (la que corre a diario)
    oficinas buscar --sin-email      # sin enviar: deja el HTML en data/out
    oficinas diagnostico             # ¿qué fuentes responden y cuáles no?
    oficinas contactos               # cola de emails a la propiedad
    oficinas contactar --aprobar 3   # envía ese email
    oficinas estado                  # estadísticas acumuladas
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import Config
from .pipeline import Agente
from .storage import Almacen, rehidratar
from .outreach.sender import aprobar_y_enviar


def _log(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# --------------------------------------------------------------------------
def cmd_buscar(args: argparse.Namespace) -> int:
    cfg = Config.cargar()
    agente = Agente(cfg)
    try:
        resumen = agente.ejecutar(
            solo_fuentes=args.fuentes,
            limite=args.limite,
            enviar=not args.sin_email,
            reenviar_vistos=args.reenviar,
        )
    finally:
        agente.cerrar()

    print("\n=== Pasada completada ===")
    print(f"  Anuncios analizados : {resumen.analizados}")
    print(f"  Nuevos              : {resumen.nuevos}")
    print(f"  Descartados         : {resumen.descartados}")
    print(f"  Candidatos al email : {resumen.candidatos}")
    print(f"  En vigilancia       : {resumen.en_vigilancia}")
    if resumen.desmentidos_por_las_fotos:
        print(f"  Caídos por las fotos: {resumen.desmentidos_por_las_fotos}")
    print(f"  Contactos redactados: {resumen.contactos_preparados}")
    print(f"  Fuentes OK / error  : {resumen.fuentes_ok} / {resumen.fuentes_error}")
    if resumen.por_fuente:
        print("  Por fuente          : " + ", ".join(f"{k}={v}" for k, v in resumen.por_fuente.items()))
    for error in resumen.errores:
        print(f"  ! {error}")
    print(f"  {resumen.mensaje_email}")
    return 0


def cmd_diagnostico(args: argparse.Namespace) -> int:
    """Comprueba fuente a fuente: robots, respuesta y nº de anuncios."""
    from .sources import crear_fuente

    cfg = Config.cargar()
    agente = Agente(cfg)
    print(f"{'fuente':24s} {'estado':10s} {'anuncios':>8s}  detalle")
    print("-" * 78)
    try:
        for cfg_fuente in cfg.fuentes.get("fuentes", []):
            id_fuente = cfg_fuente.get("id")
            if args.fuentes and id_fuente not in args.fuentes:
                continue
            if not cfg_fuente.get("activo") and not args.todas:
                print(f"{id_fuente:24s} {'inactiva':10s} {'-':>8s}", flush=True)
                continue
            fuente = crear_fuente(cfg_fuente, agente.fetcher, agente.defaults)
            if fuente is None:
                print(f"{id_fuente:24s} {'sin-adapt':10s} {'-':>8s}", flush=True)
                continue
            bloqueadas = [
                u for u in (cfg_fuente.get("urls") or []) if not agente.fetcher.permitido(u)
            ]
            try:
                encontrados = fuente.buscar()
                errores_red = getattr(fuente, "errores_red", [])
                if encontrados:
                    estado, detalle = "ok", ""
                elif bloqueadas:
                    estado = "robots"
                    detalle = "robots.txt no permite: " + ", ".join(bloqueadas)
                elif errores_red:
                    estado = "sin-red"
                    detalle = errores_red[0]
                else:
                    estado = "vacía"
                    detalle = "el portal respondió pero no se extrajo nada: revisar selectores"
                print(f"{id_fuente:24s} {estado:10s} {len(encontrados):>8d}  {detalle}", flush=True)
            except Exception as exc:
                print(f"{id_fuente:24s} {'ERROR':10s} {'-':>8s}  {exc}", flush=True)
    finally:
        agente.cerrar()
    return 0


def cmd_contactos(args: argparse.Namespace) -> int:
    cfg = Config.cargar()
    almacen = Almacen(cfg.ruta(cfg.db))
    filas = almacen.listar_contactos(args.estado)
    if not filas:
        print("No hay contactos en esa situación.")
        return 0
    for fila in filas:
        print(f"\n[{fila['id']}] {fila['estado'].upper()} · {fila['creado_en'][:16]}")
        print(f"  Para   : {fila['destinatario'] or '(sin email: usar formulario del portal)'}")
        print(f"  Asunto : {fila['asunto']}")
        print(f"  Anuncio: {fila['url']}")
        if args.completo:
            print("  ---")
            print("\n".join("  " + l for l in (fila["cuerpo"] or "").splitlines()))
    almacen.cerrar()
    return 0


def cmd_contactar(args: argparse.Namespace) -> int:
    cfg = Config.cargar()
    almacen = Almacen(cfg.ruta(cfg.db))
    try:
        if args.descartar:
            almacen.actualizar_contacto(args.descartar, "descartado", "descartado manualmente")
            print(f"Contacto {args.descartar} descartado.")
            return 0
        objetivos = []
        if args.aprobar_todos:
            objetivos = [f["id"] for f in almacen.listar_contactos("pendiente")]
        elif args.aprobar:
            objetivos = [args.aprobar]
        if not objetivos:
            print("Nada que enviar. Usa --aprobar ID, --aprobar-todos o --descartar ID.")
            return 1
        for id_contacto in objetivos:
            print(aprobar_y_enviar(almacen, cfg, id_contacto, args.para))
    finally:
        almacen.cerrar()
    return 0


def cmd_estado(args: argparse.Namespace) -> int:
    cfg = Config.cargar()
    almacen = Almacen(cfg.ruta(cfg.db))
    stats = almacen.estadisticas()
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print("\nMejores candidatos guardados:")
    for datos in almacen.candidatos_recientes(args.limite):
        cand = rehidratar(datos)
        print(f"  [{cand.puntuacion:5g}] {cand.anuncio.titulo[:64]:64s} {cand.anuncio.url}")
    almacen.cerrar()
    return 0


def cmd_informe(args: argparse.Namespace) -> int:
    """Regenera el informe HTML con lo mejor que hay en base de datos."""
    from .notify.email_digest import construir_html, enviar_digest

    cfg = Config.cargar()
    almacen = Almacen(cfg.ruta(cfg.db))
    candidatos = [rehidratar(d) for d in almacen.candidatos_recientes(args.limite)]
    contactos = {}
    for cand in candidatos:
        fila = almacen.contacto_existente(cand.id)
        if fila:
            contactos[cand.id] = {
                "id_contacto": fila["id"], "estado": fila["estado"],
                "destinatario": fila["destinatario"], "asunto": fila["asunto"],
                "cuerpo": fila["cuerpo"], "url": fila["url"],
            }
    resumen = {"analizados": len(candidatos), "fuentes_ok": 0, "descartados": 0}
    if args.enviar:
        print(enviar_digest(candidatos, contactos, cfg, resumen))
    else:
        destino = Path(cfg.ruta(cfg.salida_dir)) / "informe-manual.html"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(construir_html(candidatos, contactos, cfg, resumen), encoding="utf-8")
        print(f"Informe escrito en {destino}")
    almacen.cerrar()
    return 0


# --------------------------------------------------------------------------
def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="oficinas", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true", help="log detallado")
    sub = p.add_subparsers(dest="comando", required=True)

    b = sub.add_parser("buscar", help="pasada completa de búsqueda")
    b.add_argument("--fuentes", nargs="*", help="ids de fuente concretos")
    b.add_argument("--limite", type=int, help="máximo de anuncios a evaluar")
    b.add_argument("--sin-email", action="store_true", help="no enviar, sólo generar el HTML")
    b.add_argument("--reenviar", action="store_true", help="incluir anuncios ya enviados")
    b.set_defaults(func=cmd_buscar)

    d = sub.add_parser("diagnostico", help="comprobar fuente a fuente")
    d.add_argument("--fuentes", nargs="*")
    d.add_argument("--todas", action="store_true", help="incluir fuentes inactivas")
    d.set_defaults(func=cmd_diagnostico)

    c = sub.add_parser("contactos", help="cola de emails a la propiedad")
    c.add_argument("--estado", choices=["pendiente", "enviado", "descartado"])
    c.add_argument("--completo", action="store_true", help="mostrar el cuerpo del email")
    c.set_defaults(func=cmd_contactos)

    ct = sub.add_parser("contactar", help="aprobar y enviar contactos")
    ct.add_argument("--aprobar", type=int, metavar="ID")
    ct.add_argument("--aprobar-todos", action="store_true")
    ct.add_argument("--descartar", type=int, metavar="ID")
    ct.add_argument("--para", default="", help="email de destino si el anuncio no lo trae")
    ct.set_defaults(func=cmd_contactar)

    e = sub.add_parser("estado", help="estadísticas y mejores candidatos")
    e.add_argument("--limite", type=int, default=10)
    e.set_defaults(func=cmd_estado)

    i = sub.add_parser("informe", help="regenerar el informe desde la base de datos")
    i.add_argument("--limite", type=int, default=20)
    i.add_argument("--enviar", action="store_true")
    i.set_defaults(func=cmd_informe)

    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    _log(args.verbose)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrumpido.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
