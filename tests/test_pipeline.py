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


def _clasificacion(agente):
    """{url: (pasa, motivo)} de la última pasada, leído de la base de datos."""
    import json

    salida = {}
    for fila in agente.almacen.con.execute("SELECT datos FROM evaluaciones"):
        d = json.loads(fila["datos"])
        salida[d["anuncio"]["url"]] = (not d["descartado"], d["evaluacion"]["motivo_descarte"])
    return salida


def test_pasada_completa_clasifica_como_se_espera(agente):
    resumen = agente.ejecutar(solo_fuentes=["demo"], enviar=False)
    assert resumen.analizados == 12
    assert resumen.nuevos == 12
    assert resumen.fuentes_error == 0
    assert "Informe guardado" in resumen.mensaje_email

    clas = _clasificacion(agente)

    # Lo que tiene que pasar el cribado.
    for url in (
        "https://ejemplo.test/nave-fuente-del-jarro-280",          # el caso ideal
        "https://ejemplo.test/oficina-atico-campanar-240",         # oficina en ático
        "https://ejemplo.test/nave-museros-450",                   # 450 m² pero impecable
    ):
        assert clas[url][0], f"debería pasar: {url}"

    # Lo que tiene que caer, y por el motivo correcto.
    vetados = {
        "https://ejemplo.test/parcela-moncada-350": "suelo sin edificar",
        "https://ejemplo.test/oficina-cara-cortes-240": "negociación",
        "https://ejemplo.test/bajo-comercial-benimaclet-200": "viviendas",
        "https://ejemplo.test/entresuelo-ruzafa-180": "viviendas",
    }
    for url, esperado in vetados.items():
        pasa, motivo = clas[url]
        assert not pasa and esperado in motivo, f"{url}: {motivo}"

    # Paiporta ni siquiera llega a evaluarse: lo corta el prefiltro de zona.
    assert "https://ejemplo.test/local-paiporta-200" not in clas


def test_lo_que_se_queda_cerca_no_se_pierde(agente):
    """Una oficina de 120 m² no se tira: entra marcada como 'le faltan 10 m²'."""
    import json

    agente.ejecutar(solo_fuentes=["demo"], enviar=False)
    fila = agente.almacen.con.execute(
        "SELECT datos FROM evaluaciones WHERE id_anuncio = ?",
        (_id_de(agente, "oficina-120-colon"),),
    ).fetchone()
    datos = json.loads(fila["datos"])
    assert not datos["descartado"]
    assert "le faltan" in datos["anuncio"]["extra"].get("excesos", "")


def _id_de(agente, fragmento_url):
    fila = agente.almacen.con.execute(
        "SELECT id FROM anuncios WHERE url LIKE ?", (f"%{fragmento_url}%",)
    ).fetchone()
    return fila["id"]


def test_umbral_se_adapta_al_caudal(agente):
    """Semana floja: baja el listón. Semana cargada: lo sube."""
    base = agente.cfg.umbral_email
    assert agente.umbral_efectivo() < base, "sin envíos recientes, el listón debe bajar"

    for i in range(15):
        agente.almacen.marcar_enviado(f"falso-{i}", "digest")
    assert agente.umbral_efectivo() > base, "con muchos envíos, el listón debe subir"


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
