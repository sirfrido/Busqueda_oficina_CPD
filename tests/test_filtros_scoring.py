import pytest

from oficinas.filtros import aplicar
from oficinas.models import Anuncio, Evaluacion
from oficinas.scoring import puntuar
from oficinas.senales import detectar


def anuncio(**kw):
    base = dict(fuente="test", url="https://ejemplo.test/1", titulo="Oficina", descripcion="")
    base.update(kw)
    return Anuncio(**base)


def test_descarta_por_superficie_pequena(criterios):
    a = anuncio(superficie_m2=90)
    ok, motivo = aplicar(a, Evaluacion(), criterios)
    assert not ok and "mínimo" in motivo


def test_el_minimo_de_130_es_estricto(criterios):
    """130 m² es un mínimo de trabajo: 120 no cuela por tolerancia."""
    assert aplicar(anuncio(superficie_m2=130), Evaluacion(), criterios)[0] is True
    ok, motivo = aplicar(anuncio(superficie_m2=120), Evaluacion(), criterios)
    assert not ok and "mínimo" in motivo


def test_precio_por_encima_del_tope_descarta(criterios):
    ok, motivo = aplicar(anuncio(superficie_m2=200, precio_eur=450000), Evaluacion(), criterios)
    assert not ok and "tope" in motivo
    assert aplicar(anuncio(superficie_m2=200, precio_eur=399000), Evaluacion(), criterios)[0] is True


def test_entre_300_y_500_solo_si_no_hay_que_reformar(criterios):
    impecable = anuncio(
        superficie_m2=450, precio_eur=395000,
        titulo="Nave de 450 m² seminueva",
        descripcion="Nave seminueva, listo para entrar, sin necesidad de reforma. Cubierta propia.",
    )
    assert aplicar(impecable, detectar(impecable), criterios)[0] is True

    con_obra = anuncio(
        superficie_m2=450, precio_eur=300000,
        titulo="Nave de 450 m² a reformar", descripcion="Necesita reforma integral.",
    )
    ok, motivo = aplicar(con_obra, detectar(con_obra), criterios)
    assert not ok and "supera" in motivo

    demasiado = anuncio(superficie_m2=620, precio_eur=390000, descripcion="Impecable, listo para entrar")
    assert aplicar(demasiado, detectar(demasiado), criterios)[0] is False


def test_descarta_bajo_comercial_y_local_a_pie_de_calle(criterios):
    for texto in (
        "Local comercial a pie de calle de 200 m² con escaparate",
        "Bajo comercial de 180 m² totalmente diáfano",
        "Entresuelo de 160 m² en finca céntrica",
    ):
        a = anuncio(superficie_m2=180, precio_eur=250000, titulo=texto)
        ok, motivo = aplicar(a, detectar(a), criterios)
        assert not ok, f"debería descartarse: {texto}"
        assert "calle" in motivo or "viviendas" in motivo


def test_oficina_en_planta_alta_puntua_mas_que_en_baja(criterios):
    alta = anuncio(
        superficie_m2=200, precio_eur=350000,
        titulo="Oficina en la última planta de un edificio de oficinas",
        descripcion="Buen estado, azotea con acceso, centro de transformación",
    )
    baja = anuncio(
        superficie_m2=200, precio_eur=350000,
        titulo="Oficina en planta baja de un edificio de oficinas",
        descripcion="Buen estado, azotea con acceso, centro de transformación",
    )
    p_alta, _ = puntuar(alta, detectar(alta), criterios)
    p_baja, _ = puntuar(baja, detectar(baja), criterios)
    assert p_alta > p_baja


def test_la_nave_tiene_preferencia(criterios):
    nave = anuncio(
        superficie_m2=250, precio_eur=350000, tipologia="nave",
        titulo="Nave industrial de 250 m² en polígono",
        descripcion="Cubierta propia, centro de transformación, listo para entrar",
    )
    # bonus_zona 12 = el que aplica el pipeline a un polígono de Paterna.
    p, desglose = puntuar(nave, detectar(nave), criterios, bonus_zona=12)
    assert any("Nave" in k for k in desglose)
    assert p > 80


def test_descarta_edificio_de_viviendas(criterios):
    a = anuncio(superficie_m2=200, descripcion="Entresuelo en edificio de viviendas")
    ok, motivo = aplicar(a, detectar(a), criterios)
    assert not ok and "viviendas" in motivo


def test_superficie_desconocida_no_descarta(criterios):
    """Si el anuncio no dice los metros, se verifica; no se tira."""
    a = anuncio(superficie_m2=None, descripcion="Oficina en edificio de oficinas")
    assert aplicar(a, detectar(a), criterios)[0] is True


def test_zona_no_admitida_descarta(criterios):
    ev = Evaluacion(zona_admitida=False, motivo_descarte="Zona inundable")
    assert aplicar(anuncio(superficie_m2=200), ev, criterios) == (False, "Zona inundable")


def test_exceso_de_minutos_descarta(criterios):
    ev = Evaluacion(minutos_coche=35)
    ok, motivo = aplicar(anuncio(superficie_m2=200), ev, criterios)
    assert not ok and "min en coche" in motivo


def test_puntuacion_premia_el_encaje_completo(criterios):
    bueno = anuncio(
        superficie_m2=225, precio_eur=380000,
        titulo="Oficina en edificio de oficinas",
        descripcion="Azotea de uso exclusivo, centro de transformación, 300 kW, listo para entrar",
    )
    flojo = anuncio(superficie_m2=290, precio_eur=395000, descripcion="Local a reformar")
    p_bueno, desglose = puntuar(bueno, detectar(bueno), criterios, bonus_zona=10)
    p_flojo, _ = puntuar(flojo, detectar(flojo), criterios)
    assert p_bueno > 85 and p_flojo < 50
    assert sum(desglose.values()) >= p_bueno - 0.01 or p_bueno == 100.0


def test_la_puntuacion_se_mantiene_en_rango(criterios):
    a = anuncio(superficie_m2=225)
    p, _ = puntuar(a, detectar(a), criterios, bonus_zona=99)
    assert 0 <= p <= 100
