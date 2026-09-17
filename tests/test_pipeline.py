"""Pruebas de extremo a extremo con la fuente de fichero (sin red)."""

from pathlib import Path

import pytest

from oficinas.config import Config
from oficinas.models import Anuncio
from oficinas.pipeline import Agente

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def agente(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_ACTIVO", "0")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.sqlite3"))
    cfg = Config.cargar()
    cfg.db = str(tmp_path / "test.sqlite3")
    cfg.salida_dir = str(tmp_path / "out")
    cfg.cache_dir = str(tmp_path / "cache")
    cfg.llm_activo = False
    a = Agente(cfg)
    yield a
    a.cerrar()


def test_pasada_completa_clasifica_como_se_espera(agente):
    resumen = agente.ejecutar(solo_fuentes=["demo"], enviar=False)

    assert resumen.analizados == 10
    assert resumen.nuevos == 10
    # Descartados: Paiporta (DANA), 120 m² (por debajo del mínimo), oficina de
    # 595.000 € (precio), nave de 460 m² a reformar, bajo comercial y entresuelo.
    assert resumen.descartados == 6
    assert resumen.candidatos >= 2
    assert resumen.fuentes_error == 0
    assert "Informe guardado" in resumen.mensaje_email


def test_no_repite_lo_ya_enviado(agente):
    agente.ejecutar(solo_fuentes=["demo"], enviar=True)
    segunda = agente.ejecutar(solo_fuentes=["demo"], enviar=True)
    assert segunda.candidatos == 0, "un anuncio ya enviado no debe repetirse al día siguiente"


def test_reenviar_fuerza_la_repeticion(agente):
    agente.ejecutar(solo_fuentes=["demo"], enviar=True)
    forzada = agente.ejecutar(solo_fuentes=["demo"], enviar=False, reenviar_vistos=True)
    assert forzada.candidatos >= 2


def test_contactos_quedan_pendientes_de_aprobacion(agente):
    agente.ejecutar(solo_fuentes=["demo"], enviar=False)
    pendientes = agente.almacen.listar_contactos("pendiente")
    assert pendientes, "el agente debe dejar redactado el email a la propiedad"
    for fila in pendientes:
        assert fila["estado"] == "pendiente"
        assert "potencia" in fila["cuerpo"].lower()
        assert "visita" in fila["asunto"].lower() or "visitar" in fila["cuerpo"].lower()


def test_deduplicacion_entre_portales():
    mismo_1 = Anuncio(fuente="a", url="https://a.test/1", municipio="València",
                      superficie_m2=220, precio_eur=485000)
    mismo_2 = Anuncio(fuente="b", url="https://b.test/9", municipio="València",
                      superficie_m2=222, precio_eur=485500)
    distinto = Anuncio(fuente="c", url="https://c.test/3", municipio="Paterna",
                       superficie_m2=280, precio_eur=390000)
    salida = Agente.deduplicar([mismo_1, mismo_2, distinto])
    assert len(salida) == 2


def test_informe_html_incluye_enlaces_y_semaforo(agente):
    agente.ejecutar(solo_fuentes=["demo"], enviar=False)
    informes = list(Path(agente.cfg.salida_dir).glob("informe-*.html"))
    assert informes
    html = informes[0].read_text(encoding="utf-8")
    assert "https://ejemplo.test/nave-fuente-del-jarro-280" in html
    assert "Potencia 200-300 kW" in html
    # Nada de lo descartado puede aparecer en el email.
    assert "bajo-comercial-benimaclet" not in html
    assert "oficina-cara-cortes-240" not in html
    assert "local-paiporta-200" not in html
