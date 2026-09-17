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


def test_pasarse_un_poco_no_descarta_nunca(criterios):
    """El corazón del cribado: 310 m² o 420.000 € no son un 'no'."""
    for metros, precio in ((310, 380000), (125, 350000), (200, 420000), (340, 300000)):
        a = anuncio(superficie_m2=metros, precio_eur=precio)
        ok, motivo = aplicar(a, Evaluacion(), criterios)
        assert ok, f"{metros} m² / {precio} € no debería vetarse: {motivo}"


def test_los_vetos_siguen_siendo_vetos(criterios):
    """Lo que no tiene arreglo sí se corta: extremos absolutos."""
    casos = [
        (anuncio(superficie_m2=60, precio_eur=200000), "pequeño"),
        (anuncio(superficie_m2=800, precio_eur=300000), "grande"),
        (anuncio(superficie_m2=200, precio_eur=700000), "negociación"),
    ]
    for a, esperado in casos:
        ok, motivo = aplicar(a, Evaluacion(), criterios)
        assert not ok and esperado in motivo, motivo


def test_la_rampa_castiga_mas_cuanto_mas_te_pasas(criterios):
    from oficinas.bandas import evaluar as evaluar_bandas

    ev = Evaluacion(minutos_coche=12)
    justo = evaluar_bandas(anuncio(superficie_m2=330, precio_eur=380000), ev, criterios).total
    lejos = evaluar_bandas(anuncio(superficie_m2=480, precio_eur=380000), ev, criterios).total
    assert justo > lejos, "pasarse 10 m² no puede costar lo mismo que pasarse 160"


def test_un_buen_precio_por_m2_compensa_los_metros_de_mas(criterios):
    """El caso real: nave de 400 m² a 300.000 € (750 €/m²)."""
    from oficinas.bandas import evaluar as evaluar_bandas

    barata = anuncio(superficie_m2=400, precio_eur=300000, tipologia="nave")
    bandas = evaluar_bandas(barata, Evaluacion(minutos_coche=13), criterios)
    assert bandas.total > 0, "un chollo por m² debe compensar el exceso de metros"
    assert "se pasa 80 m²" in bandas.excesos


def test_metros_de_mas_con_obra_es_la_peor_combinacion(criterios):
    """Pagar suelo de más y encima tener que invertir en él: doble castigo."""
    from oficinas.bandas import evaluar as evaluar_bandas

    impecable = anuncio(
        superficie_m2=450, precio_eur=395000,
        titulo="Nave de 450 m² seminueva",
        descripcion="Nave seminueva, listo para entrar, sin necesidad de reforma. Cubierta propia.",
    )
    con_obra = anuncio(
        superficie_m2=450, precio_eur=395000,
        titulo="Nave de 450 m² a reformar", descripcion="Necesita reforma integral.",
    )
    b_ok = evaluar_bandas(impecable, detectar(impecable), criterios)
    b_obra = evaluar_bandas(con_obra, detectar(con_obra), criterios)
    assert b_obra.total < b_ok.total - 5
    # Ninguno de los dos se veta: el que tiene obra simplemente no puntúa.
    assert aplicar(impecable, detectar(impecable), criterios)[0] is True
    assert puntuar(impecable, detectar(impecable), criterios)[0] > puntuar(
        con_obra, detectar(con_obra), criterios
    )[0]

    # El doble del máximo ya no es "pasarse un poco": ahí sí hay veto.
    demasiado = anuncio(superficie_m2=650, precio_eur=390000, descripcion="Impecable, listo para entrar")
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


def test_regla_de_compensacion(criterios):
    """Pasarse en un eje se perdona; en dos, sólo con el resto sobresaliente."""
    from oficinas.bandas import evaluar as evaluar_bandas

    un_exceso = anuncio(superficie_m2=340, precio_eur=360000, tipologia="nave")
    dos_excesos = anuncio(superficie_m2=340, precio_eur=460000, tipologia="nave")
    ev = Evaluacion(minutos_coche=14)

    assert len(evaluar_bandas(un_exceso, ev, criterios).ejes_excedidos) == 1
    excedidos = evaluar_bandas(dos_excesos, ev, criterios).ejes_excedidos
    assert set(excedidos) == {"superficie", "precio"}
    # Ninguno de los dos está vetado: la decisión es de puntuación, no de corte.
    assert aplicar(un_exceso, ev, criterios)[0] is True
    assert aplicar(dos_excesos, ev, criterios)[0] is True


# --- Verificación de la ficha: solares disfrazados de nave -----------------

def test_un_solar_publicado_como_nave_no_pasa(criterios):
    """Caso real: 'Nave industrial en venta en Burjassot' que era un solar."""
    from oficinas.verificacion import verificar

    a = anuncio(
        superficie_m2=400, precio_eur=300000, tipologia="nave",
        titulo="Nave industrial en venta en Burjassot",
        descripcion="Nave en venta en Mendizabal, burjassot.",
    )
    v = verificar(a)
    assert v.ficha_pobre, "seis palabras de descripción no acreditan nada"
    assert not v.recomendable, "no puede recomendarse como candidato"
    assert v.es_construido == "verificar"


def test_parcela_declarada_es_veto(criterios):
    from oficinas.verificacion import verificar

    a = anuncio(
        superficie_m2=350, precio_eur=210000, tipologia="nave",
        titulo="Nave industrial en venta en Moncada",
        descripcion="Parcela industrial edificable en suelo urbano, lista para construir la nave.",
    )
    ev = detectar(a)
    ev.es_construido = verificar(a).es_construido
    ok, motivo = aplicar(a, ev, criterios)
    assert not ok and "suelo sin edificar" in motivo


def test_una_nave_descrita_de_verdad_se_acredita():
    from oficinas.verificacion import verificar

    a = anuncio(
        superficie_m2=280, precio_eur=390000, tipologia="nave",
        titulo="Nave industrial de 280 m²",
        descripcion=(
            "Nave de 280 m2 construidos, altura libre de 7 m, puerta de camión, "
            "oficinas en altillo reformadas, aseos y vestuarios."
        ),
    )
    v = verificar(a)
    assert v.es_construido == "si" and v.recomendable


def test_placas_solares_no_convierten_una_nave_en_solar():
    from oficinas.verificacion import verificar

    a = anuncio(
        superficie_m2=280, precio_eur=350000, tipologia="nave",
        titulo="Nave con placas solares",
        descripcion=(
            "Nave de 280 m2 construidos con altura libre de 8 m, puerta seccional, "
            "oficinas, aseos y placas solares en cubierta."
        ),
    )
    assert verificar(a).sospecha_solar is False
