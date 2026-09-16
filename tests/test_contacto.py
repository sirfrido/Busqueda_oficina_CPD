from oficinas.models import Anuncio
from oficinas.outreach.composer import componer_contacto
from oficinas.senales import detectar
from oficinas.storage import Almacen


def test_email_a_la_propiedad_no_repite_preguntas(plantillas):
    a = Anuncio(
        fuente="fotocasa", url="https://portal.test/1",
        titulo="Oficina de 230 m² en edificio de oficinas",
        descripcion="Diáfana, buen estado", municipio="València",
        extra={"fuente_nombre": "Fotocasa"},
    )
    asunto, cuerpo = componer_contacto(a, detectar(a), plantillas, "Alex", "Empresa", "alex@test.com")
    preguntas = [l for l in cuerpo.splitlines() if l.strip()[:2].rstrip(".").isdigit()]
    assert 3 <= len(preguntas) <= 6
    # Una sola pregunta por tema: no puede haber dos sobre potencia.
    assert sum("potencia" in p.lower() for p in preguntas) == 1
    assert sum("cubierta" in p.lower() or "azotea" in p.lower() for p in preguntas) == 1
    assert "https://portal.test/1" in cuerpo
    assert asunto.startswith("Interés en")


def test_email_menciona_el_uso_real_como_cpd(plantillas):
    a = Anuncio(fuente="x", url="https://portal.test/2", titulo="Nave 260 m²")
    _, cuerpo = componer_contacto(a, detectar(a), plantillas, "Alex")
    assert "centro de proceso de datos" in cuerpo.lower()


def test_cola_de_contactos(tmp_path):
    almacen = Almacen(tmp_path / "db.sqlite3")
    cid = almacen.crear_contacto("abc", "agencia@test.com", "Asunto", "Cuerpo", "https://portal.test/1")
    assert almacen.listar_contactos("pendiente")[0]["id"] == cid
    almacen.actualizar_contacto(cid, "enviado", "ok")
    fila = almacen.obtener_contacto(cid)
    assert fila["estado"] == "enviado" and fila["enviado_en"]
    assert almacen.estadisticas()["contactos_enviados"] == 1
    almacen.cerrar()
