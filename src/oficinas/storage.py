"""Persistencia en SQLite: memoria del agente entre ejecuciones diarias.

Responde a tres preguntas: ¿esto ya lo vi?, ¿ya te lo mandé?, ¿en qué estado
está el contacto con la propiedad?
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .models import Anuncio, Candidato, Evaluacion

ESQUEMA = """
CREATE TABLE IF NOT EXISTS anuncios (
    id            TEXT PRIMARY KEY,
    fuente        TEXT NOT NULL,
    url           TEXT NOT NULL,
    titulo        TEXT,
    municipio     TEXT,
    superficie_m2 REAL,
    precio_eur    REAL,
    primera_vez   TEXT NOT NULL,
    ultima_vez    TEXT NOT NULL,
    datos         TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evaluaciones (
    id_anuncio  TEXT NOT NULL,
    fecha       TEXT NOT NULL,
    puntuacion  REAL,
    descartado  INTEGER,
    motivo      TEXT,
    datos       TEXT NOT NULL,
    PRIMARY KEY (id_anuncio, fecha)
);
CREATE TABLE IF NOT EXISTS envios (
    id_anuncio  TEXT NOT NULL,
    tipo        TEXT NOT NULL,        -- digest | contacto
    fecha       TEXT NOT NULL,
    PRIMARY KEY (id_anuncio, tipo)
);
CREATE TABLE IF NOT EXISTS contactos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    id_anuncio   TEXT NOT NULL,
    estado       TEXT NOT NULL,       -- pendiente | aprobado | enviado | descartado
    destinatario TEXT,
    asunto       TEXT,
    cuerpo       TEXT,
    url          TEXT,
    creado_en    TEXT NOT NULL,
    enviado_en   TEXT,
    nota         TEXT
);
CREATE INDEX IF NOT EXISTS idx_contactos_estado ON contactos(estado);
CREATE INDEX IF NOT EXISTS idx_eval_fecha ON evaluaciones(fecha);
"""


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Almacen:
    def __init__(self, ruta: str | Path = "data/oficinas.sqlite3") -> None:
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.ruta)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA)
        self.con.commit()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.con
            self.con.commit()
        except Exception:
            self.con.rollback()
            raise

    def cerrar(self) -> None:
        self.con.close()

    # -- anuncios -----------------------------------------------------------
    def es_nuevo(self, anuncio: Anuncio) -> bool:
        cur = self.con.execute("SELECT 1 FROM anuncios WHERE id = ?", (anuncio.id,))
        return cur.fetchone() is None

    def guardar_anuncio(self, anuncio: Anuncio) -> bool:
        """Inserta o actualiza. Devuelve True si era nuevo."""
        nuevo = self.es_nuevo(anuncio)
        with self.tx() as con:
            if nuevo:
                con.execute(
                    "INSERT INTO anuncios (id, fuente, url, titulo, municipio, superficie_m2,"
                    " precio_eur, primera_vez, ultima_vez, datos) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        anuncio.id, anuncio.fuente, anuncio.url, anuncio.titulo, anuncio.municipio,
                        anuncio.superficie_m2, anuncio.precio_eur, ahora(), ahora(),
                        json.dumps(anuncio.to_dict(), ensure_ascii=False),
                    ),
                )
            else:
                con.execute(
                    "UPDATE anuncios SET ultima_vez = ?, precio_eur = ?, datos = ? WHERE id = ?",
                    (ahora(), anuncio.precio_eur, json.dumps(anuncio.to_dict(), ensure_ascii=False), anuncio.id),
                )
        return nuevo

    def precio_anterior(self, id_anuncio: str) -> float | None:
        cur = self.con.execute("SELECT precio_eur FROM anuncios WHERE id = ?", (id_anuncio,))
        fila = cur.fetchone()
        return fila["precio_eur"] if fila else None

    # -- evaluaciones -------------------------------------------------------
    def guardar_evaluacion(self, cand: Candidato) -> None:
        with self.tx() as con:
            con.execute(
                "INSERT OR REPLACE INTO evaluaciones (id_anuncio, fecha, puntuacion, descartado, motivo, datos)"
                " VALUES (?,?,?,?,?,?)",
                (
                    cand.id, ahora(), cand.puntuacion, int(cand.descartado),
                    cand.evaluacion.motivo_descarte,
                    json.dumps(cand.to_dict(), ensure_ascii=False),
                ),
            )

    # -- envíos -------------------------------------------------------------
    def ya_enviado(self, id_anuncio: str, tipo: str = "digest") -> bool:
        cur = self.con.execute(
            "SELECT 1 FROM envios WHERE id_anuncio = ? AND tipo = ?", (id_anuncio, tipo)
        )
        return cur.fetchone() is not None

    def marcar_enviado(self, id_anuncio: str, tipo: str = "digest") -> None:
        with self.tx() as con:
            con.execute(
                "INSERT OR REPLACE INTO envios (id_anuncio, tipo, fecha) VALUES (?,?,?)",
                (id_anuncio, tipo, ahora()),
            )

    # -- contactos con la propiedad ----------------------------------------
    def crear_contacto(
        self, id_anuncio: str, destinatario: str, asunto: str, cuerpo: str, url: str, estado: str = "pendiente"
    ) -> int:
        with self.tx() as con:
            cur = con.execute(
                "INSERT INTO contactos (id_anuncio, estado, destinatario, asunto, cuerpo, url, creado_en)"
                " VALUES (?,?,?,?,?,?,?)",
                (id_anuncio, estado, destinatario, asunto, cuerpo, url, ahora()),
            )
            return int(cur.lastrowid)

    def contacto_existente(self, id_anuncio: str) -> sqlite3.Row | None:
        cur = self.con.execute(
            "SELECT * FROM contactos WHERE id_anuncio = ? ORDER BY id DESC LIMIT 1", (id_anuncio,)
        )
        return cur.fetchone()

    def listar_contactos(self, estado: str | None = None) -> list[sqlite3.Row]:
        if estado:
            cur = self.con.execute(
                "SELECT * FROM contactos WHERE estado = ? ORDER BY id DESC", (estado,)
            )
        else:
            cur = self.con.execute("SELECT * FROM contactos ORDER BY id DESC")
        return list(cur.fetchall())

    def obtener_contacto(self, id_contacto: int) -> sqlite3.Row | None:
        cur = self.con.execute("SELECT * FROM contactos WHERE id = ?", (id_contacto,))
        return cur.fetchone()

    def actualizar_contacto(self, id_contacto: int, estado: str, nota: str = "") -> None:
        with self.tx() as con:
            con.execute(
                "UPDATE contactos SET estado = ?, nota = ?, enviado_en = CASE WHEN ? = 'enviado'"
                " THEN ? ELSE enviado_en END WHERE id = ?",
                (estado, nota, estado, ahora(), id_contacto),
            )

    # -- consultas de informe ----------------------------------------------
    def candidatos_recientes(self, limite: int = 50) -> list[dict[str, Any]]:
        cur = self.con.execute(
            "SELECT datos FROM evaluaciones WHERE descartado = 0 ORDER BY puntuacion DESC, fecha DESC LIMIT ?",
            (limite,),
        )
        return [json.loads(f["datos"]) for f in cur.fetchall()]

    def estadisticas(self) -> dict[str, int]:
        def uno(sql: str) -> int:
            return int(self.con.execute(sql).fetchone()[0])

        return {
            "anuncios_vistos": uno("SELECT COUNT(*) FROM anuncios"),
            "evaluaciones": uno("SELECT COUNT(*) FROM evaluaciones"),
            "enviados_email": uno("SELECT COUNT(*) FROM envios WHERE tipo='digest'"),
            "contactos_pendientes": uno("SELECT COUNT(*) FROM contactos WHERE estado='pendiente'"),
            "contactos_enviados": uno("SELECT COUNT(*) FROM contactos WHERE estado='enviado'"),
        }


def rehidratar(datos: dict[str, Any]) -> Candidato:
    """Reconstruye un Candidato desde el JSON guardado."""
    return Candidato(
        anuncio=Anuncio(**datos["anuncio"]),
        evaluacion=Evaluacion(**datos["evaluacion"]),
        puntuacion=datos.get("puntuacion", 0.0),
        desglose=datos.get("desglose", {}),
        descartado=datos.get("descartado", False),
    )
