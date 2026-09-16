from oficinas.textutils import (
    clasificar_terminos,
    extraer_altura_libre,
    extraer_kw,
    extraer_precio_eur,
    extraer_superficie_m2,
    normalizar,
)


def test_normalizar_quita_acentos_y_espacios():
    assert normalizar("  Benetússer   L'HORTA  ") == "benetusser l'horta"


def test_superficie_toma_la_mayor_cifra_plausible():
    assert extraer_superficie_m2("235 m2 construidos y 210 m² útiles") == 235.0
    assert extraer_superficie_m2("Oficina luminosa") is None


def test_precios_en_formato_espanol():
    assert extraer_precio_eur("485.000 €") == 485000.0
    assert extraer_precio_eur("1.250.000€") == 1250000.0
    assert extraer_precio_eur("395.000 euros") == 395000.0


def test_kva_se_convierte_a_kw():
    assert extraer_kw("acometida de 300 kVA") == 270.0
    assert extraer_kw("potencia contratada 150 kW") == 150.0


def test_altura_libre():
    assert extraer_altura_libre("nave con 7,5 m de altura libre") == 7.5


def test_negacion_rotunda_frente_a_dato_desconocido():
    presentes, negados, dudosos = clasificar_terminos(
        normalizar("Sin acceso a cubierta"), ["acceso a cubierta"]
    )
    assert negados == ["acceso a cubierta"] and not presentes

    presentes, negados, dudosos = clasificar_terminos(
        normalizar("No se especifica la potencia ni el acceso a cubierta"), ["acceso a cubierta"]
    )
    assert dudosos == ["acceso a cubierta"] and not negados


def test_la_negacion_no_atraviesa_una_oracion_nueva():
    presentes, negados, _ = clasificar_terminos(
        normalizar("Oficina sin aparcamiento pero con azotea de uso exclusivo"), ["azotea"]
    )
    assert presentes == ["azotea"] and not negados
