from bs4 import BeautifulSoup

from oficinas.sources.html_generico import FuenteHTML, deducir_tipologia

LISTADO = """
<html><body>
<article class="card">
  <a class="t" href="/inmueble/1">Oficina 220 m2 en edificio de oficinas</a>
  <span class="p">485.000 €</span><span class="s">220 m²</span>
  <div class="l">Valencia, Campanar</div>
</article>
<script type="application/ld+json">
{"@type":"Product","name":"Nave 260 m2 en Paterna","url":"https://portal.test/n/2",
 "description":"Nave con cubierta propia","offers":{"price":"390000"},
 "address":{"addressLocality":"Paterna"}}
</script>
</body></html>
"""


def fuente():
    cfg = {
        "id": "demo_html", "nombre": "Demo",
        "selectores": {"item": "article.card", "url": "a.t", "titulo": "a.t",
                       "precio": ".p", "superficie": ".s", "ubicacion": ".l"},
        "urls": [],
    }
    return FuenteHTML(cfg=cfg, fetcher=None, defaults={})


def test_extraccion_por_selectores():
    sopa = BeautifulSoup(LISTADO, "lxml")
    anuncios = list(fuente()._por_selectores(sopa, "https://portal.test/listado"))
    assert len(anuncios) == 1
    a = anuncios[0]
    assert a.url == "https://portal.test/inmueble/1"
    assert a.precio_eur == 485000 and a.superficie_m2 == 220
    assert a.tipologia == "oficina"


def test_respaldo_por_json_ld():
    """Si cambian los selectores, el JSON-LD del portal sigue dando resultados."""
    sopa = BeautifulSoup(LISTADO, "lxml")
    anuncios = list(fuente()._por_jsonld(sopa, "https://portal.test/listado"))
    assert len(anuncios) == 1
    assert anuncios[0].municipio == "Paterna" and anuncios[0].precio_eur == 390000


def test_deduccion_de_tipologia():
    assert deducir_tipologia("Nave industrial en polígono") == "nave"
    assert deducir_tipologia("Despacho profesional") == "oficina"
    assert deducir_tipologia("Bajo comercial") == "local"


FICHA_CON_DECORADO = """
<html><head>
<meta property="og:description" content="Nave en venta en mendizabal, burjassot.">
</head><body>
<div class="description__content">Accede a la vista 3D, activa el modo satélite y consulta
 puntos de interés como transporte, salud, educación u otros servicios.</div>
<script>var fotos = ["https://fotos.imghs.net/xl-wp/1050/abc/foto1.jpg",
 "https://cdn.portal.test/logo.png"];</script>
</body></html>
"""


def test_la_descripcion_del_anunciante_gana_al_decorado_del_portal():
    """Si se cuela el texto publicitario del portal, una ficha de seis palabras
    parece completa y acabamos recomendando un solar. Pasó de verdad."""
    from bs4 import BeautifulSoup

    f = FuenteHTML(
        cfg={"id": "demo", "selectores_detalle": {"descripcion": ".description__content"}},
        fetcher=None, defaults={},
    )
    descripcion = f._descripcion_real(BeautifulSoup(FICHA_CON_DECORADO, "lxml"))
    assert descripcion == "Nave en venta en mendizabal, burjassot."
    assert "vista 3D" not in descripcion


def test_fotos_rescatadas_del_html_en_bruto():
    """Las galerías se cargan por JavaScript: hay que mirar el HTML crudo."""
    from oficinas.sources.html_generico import _imagenes_crudas

    fotos = _imagenes_crudas(FICHA_CON_DECORADO)
    assert fotos == ["https://fotos.imghs.net/xl-wp/1050/abc/foto1.jpg"], fotos
