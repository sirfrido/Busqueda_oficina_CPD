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
