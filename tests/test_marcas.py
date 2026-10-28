"""Vigilancia de marcas: fuentes, cribado, análisis (con un Claude simulado) e informe."""

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from marcas import informe
from marcas.analisis import Analizador, combinar
from marcas.cli import revisar
from marcas.fuentes import imarcas, oepm
from marcas.modelos import ConfigMarcas, Solicitud
from marcas.similitud import puntuar

FIXTURES = Path(__file__).parent / "fixtures"


def cfg(**extra) -> ConfigMarcas:
    base = dict(marca="HAMPA STUDIO", nucleo="HAMPA", canario="HAMPAH DESIGN STUDIO", fuentes=["imarcas"])
    base.update(extra)
    return ConfigMarcas(**base)


# -- fuentes ---------------------------------------------------------------
def test_imarcas_lee_la_tabla_de_una_entrada():
    html = (FIXTURES / "imarcas_entrada.html").read_text(encoding="utf-8")
    sols = imarcas.solicitudes(html, date(2026, 10, 19))
    assert len(sols) == 12
    assert sols[0].numero == "4372028"
    assert sols[0].denominacion == "EL PODER DE LA TIERRA"
    assert sols[1].clases == [3, 14, 25, 35]


def test_imarcas_fecha_desde_el_slug_incluido_el_sufijo_de_republicacion():
    html = (FIXTURES / "imarcas_categoria.html").read_text(encoding="utf-8")
    fechas = imarcas.entradas(html)
    assert date(2026, 10, 19) in fechas
    assert fechas[date(2026, 10, 14)].endswith("-14-10-2026-2/")


TOMO1 = """1. MARCAS
20 DE OCTUBRE DE 2026 - BOLETÍN OFICIAL DE LA PROPIEDAD INDUSTRIAL 1
1
CVE-BOPI-T1-20261020-00000001
SOLICITUDES
A partir de la fecha de publicación del presente Boletín Oficial de la Propiedad Industrial queda
abierto el plazo de dos meses para que toda persona que se considere perjudicada pueda formular
210 M \xa0 4380114 \xa0 \xa0(  )5
220 \xa013-05-2026
731 Hadrath ,  Yara
08017   Barcelona   ( BARCELONA )  ES
541
 The Compass Atelier

511 35 SERVICIOS DE CONSULTORIA Y ASESORAMIENTO EN ESTRATEGIA EMPRESARIAL;
210 M   4384838      (  )9
220  04-06-2026
546


531 27 05 10
511 41 EDUCACION; FORMACION; SERVICIOS DE ENTRETENIMIENTO
210 M   4388499      (  )7
731 Méndez García ,  Javier
20 DE OCTUBRE DE 2026 - BOLETÍN OFICIAL DE LA PROPIEDAD INDUSTRIAL 2
2
CVE-BOPI-T1-20261020-00000002
541
 Xoves Cálidos

511 41 EDUCACION; FORMACION; SERVICIOS DE ENTRETENIMIENTO
43 SERVICIOS DE RESTAURACION (ALIMENTACION); HOSPEDAJE TEMPORAL; BAR
SUSPENSOS DE SOLICITUD
210 M   4300000      (  )1
541
 NO CUENTA
"""


def test_oepm_lee_el_tomo_1_del_bopi_nuevo():
    sols = oepm.solicitudes_desde_texto(TOMO1, date(2026, 10, 20))
    assert [(s.numero, s.denominacion, s.clases) for s in sols] == [
        ("4380114", "The Compass Atelier", [35]),
        ("4384838", oepm.SIN_DENOMINACION, [41]),
        # La ficha cruza un salto de página: la cabecera no se confunde con el 541.
        ("4388499", "Xoves Cálidos", [41, 43]),
    ]


def test_oepm_no_descarga_los_dias_ya_revisados(monkeypatch):
    pedidos = []
    monkeypatch.setattr(oepm, "hay_bopi", lambda d, http: pedidos.append(d) or False)
    oepm.descargar(date(2026, 10, 19), date(2026, 10, 25), http=object(), saltar={date(2026, 10, 20)})
    assert pedidos == [date(2026, 10, 19), date(2026, 10, 21), date(2026, 10, 22), date(2026, 10, 23)]


# -- similitud -------------------------------------------------------------
@pytest.mark.parametrize("nombre", ["HAMPAH DESIGN STUDIO", "JAMPA", "HANPA STUDIO", "HAM PA", "AMPA STUDIO", "HAMMPA"])
def test_parecidos_evidentes_pasan_el_umbral(nombre):
    assert puntuar(nombre, "HAMPA")[0] >= 0.85


@pytest.mark.parametrize("nombre", ["EL PODER DE LA TIERRA", "Alma Terra VINOS", "LAMPARAS GARCIA", "Ama, Legado", "MANGOSUR DEL CAMPO A TU CASA", "HALMA ABOGADAS"])
def test_lo_que_no_se_parece_no_pasa(nombre):
    assert puntuar(nombre, "HAMPA")[0] < 0.85


# -- plazo -----------------------------------------------------------------
def test_plazo_de_oposicion_dos_meses_y_fin_de_mes():
    assert Solicitud("1", "X", date(2026, 10, 19)).fin_plazo_oposicion == date(2026, 12, 19)
    assert Solicitud("1", "X", date(2026, 12, 31)).fin_plazo_oposicion == date(2027, 2, 28)


# -- análisis con Claude simulado -----------------------------------------
class ClaudeFalso:
    """Marca todo lo que contenga HAMPA/HAMPAH, como haría el modelo."""

    def __init__(self, ve_canario=True):
        self.ve_canario = ve_canario
        self.peticiones = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.peticiones.append(kw)
        lineas = kw["messages"][0]["content"].split("\n\n", 1)[1].splitlines()
        alertas = []
        for linea in lineas:
            numero, nombre, _ = (p.strip() for p in linea.split("|"))
            if "HAMPA" in nombre.upper() and (self.ve_canario or "HAMPAH" not in nombre):
                alertas.append(
                    {"numero": numero, "riesgo": "alto", "similitud": ["grafica"], "motivo": "m", "recomendacion": "oponerse"}
                )
        texto = json.dumps({"alertas": alertas})
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=texto)])


SEMANA = [
    Solicitud("4400001", "EL PODER DE LA TIERRA", date(2026, 10, 19), [35]),
    Solicitud("4400002", "HAMPA RECORDS", date(2026, 10, 19), [9, 41]),
    Solicitud("4400003", "JAMPA STUDIO", date(2026, 10, 20), [42]),
]


def test_el_canario_se_detecta_y_nunca_sale_en_las_alertas():
    falso = ClaudeFalso()
    alertas, canario = Analizador(cfg(), cliente=falso).analizar(SEMANA)
    assert canario is True
    assert [a["numero"] for a in alertas] == ["4400002"]
    enviado = falso.peticiones[0]["messages"][0]["content"]
    assert "HAMPAH DESIGN STUDIO" in enviado
    # El modelo no sabe cuál es el canario: ni el prompt ni el sistema lo nombran.
    assert "canario" not in json.dumps(falso.peticiones[0]["system"]).lower()


def test_si_el_modelo_no_ve_el_canario_el_informe_lo_avisa():
    _, canario = Analizador(cfg(), cliente=ClaudeFalso(ve_canario=False)).analizar(SEMANA)
    assert canario is False


def test_lotes_respetan_el_tamano():
    falso = ClaudeFalso()
    Analizador(cfg(lote=2), cliente=falso).analizar(SEMANA)
    assert len(falso.peticiones) == 2  # 3 + canario = 4 -> 2 lotes


def test_lo_que_el_modelo_descarta_pero_se_parece_no_se_pierde():
    locales = {s.numero: puntuar(s.denominacion, "HAMPA") for s in SEMANA}
    alertas, solo_locales = combinar(SEMANA, [{"numero": "4400002", "riesgo": "alto"}], locales, 0.8)
    assert [a.solicitud.numero for a in alertas] == ["4400002"]
    assert [a.solicitud.numero for a in solo_locales] == ["4400003"]


def test_pasada_completa_sin_red(monkeypatch):
    monkeypatch.setattr("marcas.cli.FUENTES", {"imarcas": lambda *_: list(SEMANA)})
    r = revisar(cfg(), date(2026, 10, 15), date(2026, 10, 21), analizador=Analizador(cfg(), cliente=ClaudeFalso()))
    assert r.revisadas == 3 and r.canario is True
    assert "🔴" in r.resumen
    assert r.asunto == "[VIGILANCIA-BOPI] HAMPA STUDIO M2723901"
    cuerpo = informe.texto(r)
    assert "HAMPA RECORDS" in cuerpo and "HAMPAH" not in cuerpo
    assert "FUNCIONANDO" in cuerpo
    assert "oposición hasta el 19/12/2026" in cuerpo


def test_sin_api_key_avisa_con_el_cribado_local(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr("marcas.cli.FUENTES", {"imarcas": lambda *_: list(SEMANA)})
    r = revisar(cfg(), date(2026, 10, 15), date(2026, 10, 21))
    assert not r.con_modelo
    assert {a.solicitud.numero for a in r.alertas} == {"4400002", "4400003"}


def test_los_bopi_ya_revisados_se_saltan(monkeypatch):
    monkeypatch.setattr("marcas.cli.FUENTES", {"imarcas": lambda *_: list(SEMANA)})
    r = revisar(
        cfg(), date(2026, 10, 1), date(2026, 10, 21),
        analizador=Analizador(cfg(), cliente=ClaudeFalso()),
        ya_revisados={date(2026, 10, 19)},
    )
    assert r.revisadas == 1 and r.dias_bopi == [date(2026, 10, 20)]


def test_fuente_caida_no_tumba_la_pasada(monkeypatch):
    def rota(*_):
        raise oepm.FuenteNoDisponible("oepm: HTTP 403")

    monkeypatch.setattr("marcas.cli.FUENTES", {"oepm": rota, "imarcas": lambda *_: list(SEMANA)})
    r = revisar(cfg(fuentes=["oepm", "imarcas"]), date(2026, 10, 15), date(2026, 10, 21),
                analizador=Analizador(cfg(), cliente=ClaudeFalso()))
    assert r.revisadas == 3
    assert any("403" in e for e in r.errores)
