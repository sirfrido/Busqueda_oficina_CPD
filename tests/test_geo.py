import pytest

from oficinas.geo import MapaZonas, distancia_km, estimar_minutos


@pytest.fixture(scope="module")
def mapa(zonas):
    return MapaZonas(zonas)


@pytest.mark.parametrize(
    "texto",
    [
        "Oficina en Paiporta",
        "Nave en Catarroja, Valencia",
        "Local en Riba-roja de Túria",
        "Oficina en La Torre, València",
        "Nave afectada por la DANA en polígono",
    ],
)
def test_zonas_vetadas(mapa, texto):
    assert mapa.resolver(texto).admitida is False


@pytest.mark.parametrize(
    "texto,municipio",
    [
        ("Nave en Fuente del Jarro, Paterna", "Paterna"),
        ("Oficina en Avenida Aragón, Valencia", "València"),
        ("Local en Alboraya junto al mar", "Alboraya"),
    ],
)
def test_zonas_admitidas(mapa, texto, municipio):
    r = mapa.resolver(texto)
    assert r.admitida and r.municipio == municipio


def test_albal_no_casa_con_albalat(mapa):
    """'Albal' está vetado; 'Albalat dels Sorells' no debe arrastrarse con él."""
    assert mapa.resolver("Nave en Albal").admitida is False
    assert mapa.resolver("Nave en Albalat dels Sorells").admitida is True


def test_municipio_desconocido_no_se_descarta_a_ciegas(mapa):
    r = mapa.resolver("Oficina en Sagunto")
    assert r.admitida and r.riesgo_inundacion == "desconocido"


def test_distancia_y_estimacion():
    km = distancia_km((39.4699, -0.3763), (39.5027, -0.4409))
    assert 6 < km < 7
    assert estimar_minutos(km) > 0
