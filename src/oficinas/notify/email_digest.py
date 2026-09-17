"""Informe diario: un email con lo que cumple, por qué cumple y qué falta.

Cada ficha lleva:
  · puntuación y desglose (para poder discutir con el agente, no sólo creerle)
  · semáforo de los cuatro requisitos innegociables
  · enlace al anuncio
  · enlace `mailto:` con el email a la propiedad YA REDACTADO (un clic y sale
    desde tu cuenta), y el comando para que lo envíe el agente si lo prefieres
"""

from __future__ import annotations

import html
from datetime import date
from typing import Any
from urllib.parse import quote

from ..config import Config
from ..models import Candidato
from ..outreach.sender import EnviadorEmail

SEMAFORO = {"si": ("✅", "#1a7f37"), "no": ("❌", "#c62828"), "verificar": ("❓", "#b26a00")}

CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;
 background:#f4f5f7;color:#1f2328;margin:0;padding:24px 12px;}
.wrap{max-width:760px;margin:0 auto;}
h1{font-size:20px;margin:0 0 4px;} .sub{color:#57606a;font-size:13px;margin:0 0 20px;}
.card{background:#fff;border:1px solid #d8dee4;border-radius:10px;padding:16px 18px;margin-bottom:14px;}
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;}
.title{font-size:16px;font-weight:600;margin:0 0 6px;line-height:1.35;}
.title a{color:#0b5cad;text-decoration:none;}
.score{font-size:22px;font-weight:700;padding:6px 12px;border-radius:8px;background:#eaf5ea;color:#1a7f37;white-space:nowrap;}
.score.medio{background:#fff4e0;color:#b26a00;} .score.bajo{background:#fdeaea;color:#c62828;}
.meta{color:#57606a;font-size:13px;margin:0 0 10px;}
.chips{margin:8px 0;} .chip{display:inline-block;font-size:12px;border:1px solid #d8dee4;
 border-radius:999px;padding:3px 10px;margin:0 6px 6px 0;background:#fafbfc;}
.resumen{font-size:14px;line-height:1.5;margin:8px 0;color:#24292f;}
.detalle{font-size:12px;color:#57606a;margin-top:8px;}
.acciones{margin-top:12px;padding-top:12px;border-top:1px solid #eaeef2;font-size:13px;}
.btn{display:inline-block;background:#0b5cad;color:#fff!important;text-decoration:none;
 padding:8px 14px;border-radius:6px;font-size:13px;margin-right:8px;}
.btn.sec{background:#fff;color:#0b5cad!important;border:1px solid #0b5cad;}
code{background:#f0f2f5;padding:2px 6px;border-radius:4px;font-size:12px;}
.foot{color:#8b949e;font-size:12px;text-align:center;margin-top:20px;line-height:1.6;}
.aviso{background:#fff8e6;border:1px solid #f0d58c;border-radius:8px;padding:10px 14px;font-size:13px;margin-bottom:16px;}
"""


def _clase_score(p: float) -> str:
    return "" if p >= 75 else ("medio" if p >= 60 else "bajo")


def _chip(etiqueta: str, veredicto: str) -> str:
    icono, color = SEMAFORO.get(veredicto, ("❓", "#b26a00"))
    return f'<span class="chip" style="color:{color}">{icono} {html.escape(etiqueta)}</span>'


def _mailto(destinatario: str, asunto: str, cuerpo: str) -> str:
    return f"mailto:{quote(destinatario)}?subject={quote(asunto)}&body={quote(cuerpo)}"


def _euros(valor: float | None) -> str:
    return f"{valor:,.0f} €".replace(",", ".") if valor else "precio a consultar"


def _fila_vigilar(cand: Candidato) -> str:
    """Una línea por inmueble que se queda a las puertas, diciendo por qué."""
    a, ev = cand.anuncio, cand.evaluacion
    motivos: list[str] = []
    if a.extra.get("verificar_ficha"):
        motivos.append("⚠️ ficha sin datos: confirmar que hay nave construida y no un solar")
    if a.extra.get("excesos"):
        motivos.append(str(a.extra["excesos"]))
    faltan = [
        etiqueta for etiqueta, veredicto in (
            ("potencia", ev.potencia_ampliable), ("cubierta", ev.cubierta_ampliable),
            ("tipo de edificio", ev.edificio_oficinas), ("estado", ev.poca_reforma),
        ) if veredicto == "verificar"
    ]
    if faltan:
        motivos.append("sin datos de " + ", ".join(faltan))
    datos = " · ".join(x for x in (
        f"{a.superficie_m2:g} m²" if a.superficie_m2 else "",
        _euros(a.precio_eur), a.municipio or a.zona,
    ) if x)
    return (
        f"<li><a href='{html.escape(a.url)}'>{html.escape(a.titulo or a.url)}</a> "
        f"<span class='detalle'>({cand.puntuacion:g} · {html.escape(datos)}"
        + (f" — {html.escape('; '.join(motivos))}" if motivos else "")
        + ")</span></li>"
    )


def construir_html(
    candidatos: list[Candidato],
    contactos: dict[str, dict[str, Any]],
    cfg: Config,
    resumen_ejecucion: dict[str, Any],
    vigilar: list[Candidato] | None = None,
) -> str:
    hoy = date.today().strftime("%d/%m/%Y")
    partes = [
        f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='wrap'>",
        f"<h1>Oficinas y naves para el CPD — {hoy}</h1>",
        f"<p class='sub'>{len(candidatos)} inmueble(s) que cumplen los criterios · "
        f"{resumen_ejecucion.get('analizados', 0)} anuncios revisados en "
        f"{resumen_ejecucion.get('fuentes_ok', 0)} fuentes · "
        f"{resumen_ejecucion.get('descartados', 0)} descartados</p>",
    ]

    if not candidatos:
        partes.append(
            "<div class='card'><p class='resumen'>Hoy no ha entrado nada nuevo que cumpla. "
            "El agente sigue vigilando: en cuanto salga algo de 150-300 m² en zona admitida, llega aquí.</p></div>"
        )

    for cand in candidatos:
        a, ev = cand.anuncio, cand.evaluacion
        contacto = contactos.get(cand.id, {})
        meta = " · ".join(
            x for x in (
                f"{a.superficie_m2:g} m²" if a.superficie_m2 else "m² a confirmar",
                _euros(a.precio_eur),
                f"{a.precio_m2:,.0f} €/m²".replace(",", ".") if a.precio_m2 else "",
                a.municipio or a.zona,
                f"{ev.minutos_coche:g} min en coche" if ev.minutos_coche is not None else "",
                a.extra.get("fuente_nombre", a.fuente),
            ) if x
        )
        chips = "".join([
            _chip("Edificio de oficinas/nave", ev.edificio_oficinas),
            _chip("Cubierta ampliable", ev.cubierta_ampliable),
            _chip("Potencia 200-300 kW", ev.potencia_ampliable),
            _chip("Poca reforma", ev.poca_reforma),
        ])
        if a.extra.get("verificar_ficha"):
            chips += ('<span class="chip" style="color:#c62828">⚠️ Ficha sin datos: '
                      'confirmar que hay algo construido</span>')
        if a.extra.get("es_subasta"):
            chips += '<span class="chip" style="color:#b26a00">⚖️ Subasta: revisar cargas y ocupación</span>'
        if ev.riesgo_inundacion in ("medio", "desconocido"):
            chips += f'<span class="chip" style="color:#b26a00">💧 Riesgo inundación: {ev.riesgo_inundacion}</span>'

        desglose = " · ".join(f"{k}: {v:+g}" for k, v in sorted(cand.desglose.items(), key=lambda kv: -abs(kv[1])))
        acciones = [f"<a class='btn' href='{html.escape(a.url)}'>Ver anuncio</a>"]
        if contacto:
            if contacto.get("estado") == "enviado":
                acciones.append("<span class='chip'>✉️ Contacto ya enviado por el agente</span>")
            else:
                if contacto.get("destinatario"):
                    acciones.append(
                        f"<a class='btn sec' href=\"{_mailto(contacto['destinatario'], contacto['asunto'], contacto['cuerpo'])}\">"
                        f"Pedir visita (se abre tu correo)</a>"
                    )
                acciones.append(
                    f"<div class='detalle'>O que lo envíe el agente: "
                    f"<code>oficinas contactar --aprobar {contacto['id_contacto']}"
                    + ("" if contacto.get("destinatario") else " --para correo@agencia.com")
                    + "</code></div>"
                )

        partes.append(
            "<div class='card'>"
            f"<div class='top'><div><p class='title'><a href='{html.escape(a.url)}'>{html.escape(a.titulo or a.url)}</a></p>"
            f"<p class='meta'>{html.escape(meta)}</p></div>"
            f"<div class='score {_clase_score(cand.puntuacion)}'>{cand.puntuacion:g}</div></div>"
            f"<div class='chips'>{chips}</div>"
            + (f"<p class='resumen'>{html.escape(ev.resumen)}</p>" if ev.resumen else "")
            + (f"<p class='detalle'><b>Se le perdona:</b> {html.escape(str(a.extra['excesos']))}</p>"
               if a.extra.get("excesos") else "")
            + (f"<p class='detalle'><b>Por confirmar:</b> {html.escape(' / '.join(ev.preguntas_clave[:3]))}</p>"
               if ev.preguntas_clave else "")
            + f"<p class='detalle'>Puntuación: {html.escape(desglose)}</p>"
            + f"<div class='acciones'>{''.join(acciones)}</div>"
            "</div>"
        )

    if vigilar:
        partes.append(
            "<div class='card'><p class='title'>Casi — se quedan a las puertas</p>"
            "<p class='detalle'>Ninguno se ha tirado: se quedan cerca del listón porque se pasan un poco "
            "en algo o porque el anuncio no dice lo que hace falta. Si alguno te interesa, el agente "
            "pregunta y lo sube al bloque principal.</p><ul>"
            + "".join(_fila_vigilar(c) for c in vigilar[:12])
            + "</ul></div>"
        )

    pendientes = sum(1 for c in contactos.values() if c.get("estado") == "pendiente")
    if pendientes:
        partes.insert(
            3,
            f"<div class='aviso'>✍️ {pendientes} email(s) a la propiedad redactados y esperando tu aprobación. "
            f"Nada sale sin que lo apruebes (modo <code>{html.escape(cfg.modo_contacto)}</code>).</div>",
        )

    partes.append(
        "<p class='foot'>Agente de búsqueda de oficinas/naves para CPD · Valencia<br>"
        "Criterios: 150-300 m², edificio terciario o nave, cubierta ampliable, 200-300 kW, "
        "máx. 20 min en coche, sin l'Horta Sud ni zona DANA.<br>"
        "Para ajustar criterios: <code>config/criteria.yaml</code></p></div></body></html>"
    )
    return "".join(partes)


def construir_texto(candidatos: list[Candidato]) -> str:
    lineas = ["Oficinas y naves para el CPD\n"]
    for c in candidatos:
        a = c.anuncio
        lineas.append(
            f"[{c.puntuacion:g}] {a.titulo}\n"
            f"    {a.superficie_m2 or '?'} m² · {_euros(a.precio_eur)} · {a.municipio}\n"
            f"    {a.url}\n"
        )
    if not candidatos:
        lineas.append("Hoy no ha entrado nada nuevo que cumpla los criterios.")
    return "\n".join(lineas)


def enviar_digest(
    candidatos: list[Candidato],
    contactos: dict[str, dict[str, Any]],
    cfg: Config,
    resumen: dict[str, Any],
    solo_guardar: bool = False,
    vigilar: list[Candidato] | None = None,
) -> str:
    """Envía (o sólo guarda) el informe. Devuelve un mensaje de estado."""
    cuerpo_html = construir_html(candidatos, contactos, cfg, resumen, vigilar)
    cuerpo_texto = construir_texto(candidatos)
    asunto = f"[Oficinas CPD] {len(candidatos)} inmueble(s) para revisar — {date.today():%d/%m/%Y}"
    if not candidatos and vigilar:
        asunto = f"[Oficinas CPD] {len(vigilar)} para vigilar — {date.today():%d/%m/%Y}"

    salida = cfg.ruta(cfg.salida_dir) / f"informe-{date.today():%Y-%m-%d}.html"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(cuerpo_html, encoding="utf-8")

    if solo_guardar:
        return f"Informe guardado en {salida} (no se ha enviado)"

    enviador = EnviadorEmail(cfg)
    if not enviador.configurado:
        return f"SMTP sin configurar: informe guardado en {salida}"
    enviador.enviar(cfg.email.destinatarios, asunto, cuerpo_texto, cuerpo_html)
    return f"Informe enviado a {', '.join(cfg.email.destinatarios)} (copia en {salida})"
