"""Informe semanal: asunto, texto plano y HTML."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from html import escape

from .modelos import Alerta

LOCALIZADOR = "https://consultas2.oepm.es/LocalizadorWeb/"
COLOR = {"alto": "#b42318", "medio": "#b54708", "bajo": "#475467", "local": "#475467"}


@dataclass
class Resultado:
    marca: str
    desde: date
    hasta: date
    revisadas: int = 0
    dias_bopi: list[date] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)
    solo_locales: list[Alerta] = field(default_factory=list)
    canario: bool | None = None
    con_modelo: bool = False
    fuentes_ok: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def periodo(self) -> tuple[date, date]:
        """Los BOPI realmente revisados; si no hubo ninguno, la ventana pedida."""
        return (min(self.dias_bopi), max(self.dias_bopi)) if self.dias_bopi else (self.desde, self.hasta)

    @property
    def fiable(self) -> bool:
        return self.revisadas > 0 and self.canario is not False

    @property
    def asunto(self) -> str:
        ini, fin = self.periodo
        periodo = f"{ini:%d/%m}–{fin:%d/%m}"
        if not self.revisadas:
            return f"⚠️ Vigilancia {self.marca}: no hay BOPI nuevos que revisar ({periodo})"
        altas = sum(a.riesgo == "alto" for a in self.alertas)
        if altas:
            return f"🔴 Vigilancia {self.marca}: {altas} marca(s) a estudiar para oposición ({periodo})"
        if self.alertas or self.solo_locales:
            return f"🟡 Vigilancia {self.marca}: {len(self.alertas) + len(self.solo_locales)} marca(s) a revisar ({periodo})"
        aviso = "" if self.fiable else " — ⚠️ revisar el sistema"
        return f"🟢 Vigilancia {self.marca}: sin marcas parecidas ({periodo}){aviso}"


def _linea(a: Alerta) -> str:
    s = a.solicitud
    clases = ", ".join(map(str, s.clases)) or "-"
    partes = [
        f"[{a.riesgo.upper()}] {s.denominacion} — nº {s.numero} — clases {clases}",
        f"    BOPI {s.fecha_bopi:%d/%m/%Y} · oposición hasta el {s.fin_plazo_oposicion:%d/%m/%Y}",
        f"    {('/'.join(a.similitud) + ': ') if a.similitud else ''}{a.motivo}",
    ]
    if a.recomendacion:
        partes.append(f"    → {a.recomendacion}")
    return "\n".join(partes)


def _estado(r: Resultado) -> str:
    dias = ", ".join(f"{d:%d/%m}" for d in r.dias_bopi) or "ninguno"
    lineas = [f"Solicitudes revisadas: {r.revisadas} (BOPI de: {dias})"]
    lineas.append(f"Fuentes que respondieron: {', '.join(r.fuentes_ok) or 'ninguna'}")
    if not r.con_modelo:
        lineas.append("Análisis: sólo cribado local (sin ANTHROPIC_API_KEY o el modelo falló).")
    elif r.canario is True:
        lineas.append("Test del sistema: FUNCIONANDO (detectó la marca de control).")
    elif r.canario is False:
        lineas.append("Test del sistema: FALLO — no detectó la marca de control; revisa el análisis a mano.")
    lineas += [f"Aviso: {e}" for e in r.errores]
    return "\n".join(lineas)


def texto(r: Resultado) -> str:
    ini, fin = r.periodo
    bloques = [f"Vigilancia de la marca {r.marca} en el BOPI, del {ini:%d/%m/%Y} al {fin:%d/%m/%Y}."]
    if r.alertas:
        bloques.append("MARCAS PARECIDAS\n\n" + "\n\n".join(_linea(a) for a in r.alertas))
    elif r.revisadas:
        bloques.append("No se han detectado marcas similares esta semana.")
    if r.solo_locales:
        bloques.append(
            "PARECIDO EN LA ESCRITURA (el análisis no las considera un riesgo; échales un vistazo)\n\n"
            + "\n".join(
                f"- {a.solicitud.denominacion} — nº {a.solicitud.numero} — {a.motivo} "
                f"(oposición hasta el {a.solicitud.fin_plazo_oposicion:%d/%m/%Y})"
                for a in r.solo_locales
            )
        )
    bloques.append(f"Expedientes: {LOCALIZADOR} (busca por número de solicitud).")
    bloques.append(_estado(r))
    return "\n\n".join(bloques)


def _tarjeta(a: Alerta) -> str:
    s = a.solicitud
    color = COLOR.get(a.riesgo, "#475467")
    clases = ", ".join(map(str, s.clases)) or "—"
    similitud = " · ".join(a.similitud)
    return f"""
<div style="border-left:4px solid {color};padding:8px 12px;margin:12px 0;background:#f9fafb">
  <div style="font-size:12px;color:{color};font-weight:600;text-transform:uppercase">Riesgo {escape(a.riesgo)}{(' · ' + escape(similitud)) if similitud else ''}</div>
  <div style="font-size:17px;font-weight:600;margin:2px 0">{escape(s.denominacion)}</div>
  <div style="font-size:13px;color:#475467">Solicitud nº {escape(s.numero)} · clases {escape(clases)} · BOPI {s.fecha_bopi:%d/%m/%Y}</div>
  <div style="font-size:13px;margin-top:6px">{escape(a.motivo)}</div>
  {f'<div style="font-size:13px;margin-top:4px"><b>→</b> {escape(a.recomendacion)}</div>' if a.recomendacion else ''}
  <div style="font-size:13px;margin-top:6px;color:#b42318">Plazo de oposición: hasta el <b>{s.fin_plazo_oposicion:%d/%m/%Y}</b></div>
</div>"""


def html(r: Resultado) -> str:
    ini, fin = r.periodo
    cuerpo = [
        f'<h2 style="margin:0 0 4px">Vigilancia de «{escape(r.marca)}»</h2>',
        f'<div style="color:#475467">BOPI del {ini:%d/%m/%Y} al {fin:%d/%m/%Y} · {r.revisadas} solicitudes revisadas</div>',
    ]
    if r.alertas:
        cuerpo.append("".join(_tarjeta(a) for a in r.alertas))
    elif r.revisadas:
        cuerpo.append('<p style="font-size:16px">✅ No se han detectado marcas similares esta semana.</p>')
    else:
        cuerpo.append('<p style="font-size:16px">⚠️ No hay BOPI nuevos que revisar: o no respondió ninguna fuente o ya estaban revisados (mira los avisos al pie).</p>')
    if r.solo_locales:
        filas = "".join(
            f"<li>{escape(a.solicitud.denominacion)} — nº {escape(a.solicitud.numero)} — {escape(a.motivo)}"
            f" (oposición hasta el {a.solicitud.fin_plazo_oposicion:%d/%m/%Y})</li>"
            for a in r.solo_locales
        )
        cuerpo.append(
            "<h3>Parecido en la escritura</h3><p style='color:#475467;font-size:13px'>"
            "El análisis no las considera un riesgo, pero se parecen sobre el papel.</p>"
            f"<ul>{filas}</ul>"
        )
    cuerpo.append(
        f'<p style="font-size:13px">Expedientes en el <a href="{LOCALIZADOR}">Localizador de la OEPM</a> '
        "(busca por número de solicitud).</p>"
    )
    estado = escape(_estado(r)).replace("\n", "<br>")
    cuerpo.append(f'<p style="font-size:12px;color:#667085;border-top:1px solid #eaecf0;padding-top:8px">{estado}</p>')
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        f"<title>Vigilancia {escape(r.marca)}</title></head>"
        '<body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:680px;margin:24px auto;padding:0 16px;color:#101828">'
        + "\n".join(cuerpo)
        + "</body></html>"
    )
