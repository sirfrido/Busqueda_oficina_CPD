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


def test_municipio_desconocido_queda_marcado_para_medirlo(mapa):
    """No se descarta a ciegas ni se acepta a ciegas: se marca para medirlo."""
    r = mapa.resolver("Oficina en Alcublas")
    assert r.admitida and r.desconocido and r.riesgo_inundacion == "desconocido"


def test_el_camp_de_turia_interior_queda_fuera_por_distancia(mapa):
    """Llíria, Bétera y compañía: no son zona inundable, están lejos."""
    for texto, minutos in (("Nave en Llíria", 26), ("Nave en Bétera", 23),
                           ("Nave en La Pobla de Vallbona", 23), ("Nave en Benaguasil", 27)):
        r = mapa.resolver(texto, max_minutos=22)
        assert not r.admitida, texto
        assert "lejos" in r.motivo.lower() and r.minutos_coche == minutos


def test_distancia_y_estimacion():
    km = distancia_km((39.4699, -0.3763), (39.5027, -0.4409))
    assert 6 < km < 7
    assert estimar_minutos(km) > 0


def test_el_radio_en_linea_recta_descarta_otras_provincias():
    """Los listados de los portales mezclan municipios de otras provincias:
    aparecieron pueblos del Penedès entre las naves de Valencia."""
    from oficinas.geo import distancia_km

    centro = (39.4699, -0.3763)
    assert distancia_km(centro, (39.5060, -0.4406)) < 30      # Paterna
    assert distancia_km(centro, (41.3833, 1.7667)) > 30       # Avinyonet del Penedès
