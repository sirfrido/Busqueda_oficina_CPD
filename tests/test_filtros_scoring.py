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


def test_tolerancia_admite_un_poco_menos_de_150(criterios):
    a = anuncio(superficie_m2=140)
    assert aplicar(a, Evaluacion(), criterios)[0] is True


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
        superficie_m2=225, precio_eur=520000,
        titulo="Oficina en edificio de oficinas",
        descripcion="Azotea de uso exclusivo, centro de transformación, 300 kW, listo para entrar",
    )
    flojo = anuncio(superficie_m2=290, precio_eur=880000, descripcion="Local a reformar")
    p_bueno, desglose = puntuar(bueno, detectar(bueno), criterios, bonus_zona=10)
    p_flojo, _ = puntuar(flojo, detectar(flojo), criterios)
    assert p_bueno > 85 and p_flojo < 50
    assert sum(desglose.values()) >= p_bueno - 0.01 or p_bueno == 100.0


def test_la_puntuacion_se_mantiene_en_rango(criterios):
    a = anuncio(superficie_m2=225)
    p, _ = puntuar(a, detectar(a), criterios, bonus_zona=99)
    assert 0 <= p <= 100
