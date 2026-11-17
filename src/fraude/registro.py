"""Registro de casos en SQLite (docs/spec.md, seccion 8.5; ADR 0005 y 0013).

Un archivo, `datos/casos/casos.sqlite` por defecto. Los objetos del caso (senales, razones,
explicacion, notificacion, revision y versiones) se guardan como JSON. Una conexion por
operacion: SQLite admite un solo escritor a la vez, suficiente para una simulacion local.

Los casos `sin_alerta` se cierran solos; los demas quedan `pendiente_revision` hasta que alguien
los revisa, una sola vez.
"""

import json
import os
import secrets
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

CAMPOS_JSON = ("senales", "razones", "explicacion", "notificacion", "revision", "versiones")
CAMPOS = (
    "id_caso",
    "id_transaccion",
    "origen",
    "monto",
    "fecha_procesamiento",
    "senales",
    "puntuacion",
    "nivel",
    "razones",
    "explicacion",
    "notificacion",
    "estado",
    "decision_final",
    "revision",
    "versiones",
)
ESQUEMA = """
CREATE TABLE IF NOT EXISTS casos (
    orden INTEGER PRIMARY KEY AUTOINCREMENT,
    id_caso TEXT NOT NULL UNIQUE,
    id_transaccion TEXT,
    origen TEXT,
    monto REAL,
    fecha_procesamiento TEXT NOT NULL,
    senales TEXT,
    puntuacion REAL,
    nivel TEXT NOT NULL,
    razones TEXT NOT NULL,
    explicacion TEXT NOT NULL,
    notificacion TEXT NOT NULL,
    estado TEXT NOT NULL,
    decision_final TEXT NOT NULL,
    revision TEXT,
    versiones TEXT NOT NULL
)
"""


def ruta_bd_casos(raiz: Path) -> Path:
    """`FRAUDE_BD_CASOS` o `datos/casos/casos.sqlite` bajo la raiz."""
    propia = os.environ.get("FRAUDE_BD_CASOS")
    return Path(propia) if propia else Path(raiz) / "datos" / "casos" / "casos.sqlite"


class CasoNoEncontrado(Exception):
    pass


class CasoYaRevisado(Exception):
    pass


def fecha_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _a_fila(caso: dict) -> tuple:
    return tuple(
        json.dumps(caso[c], ensure_ascii=False) if c in CAMPOS_JSON else caso[c] for c in CAMPOS
    )


def _de_fila(fila: sqlite3.Row) -> dict:
    return {c: json.loads(fila[c]) if c in CAMPOS_JSON else fila[c] for c in CAMPOS}


class RegistroCasos:
    def __init__(self, ruta: Path):
        self.ruta = Path(ruta)

    def _conectar(self) -> sqlite3.Connection:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        conexion = sqlite3.connect(self.ruta, timeout=10)
        conexion.row_factory = sqlite3.Row
        conexion.execute(ESQUEMA)
        return conexion

    def crear(self, nuevo: dict) -> dict:
        """Registra un caso calculado por n8n y devuelve el caso completo."""
        cerrado = nuevo["nivel"] == "sin_alerta"
        caso = {
            **{c: None for c in CAMPOS},
            **nuevo,
            "id_caso": f"c-{secrets.token_hex(6)}",
            "fecha_procesamiento": nuevo.get("fecha_procesamiento") or fecha_utc(),
            "estado": "cerrado" if cerrado else "pendiente_revision",
            "decision_final": "sin_alerta" if cerrado else "pendiente",
            "revision": None,
        }
        marcas = ", ".join("?" for _ in CAMPOS)
        with closing(self._conectar()) as conexion, conexion:
            conexion.execute(
                f"INSERT INTO casos ({', '.join(CAMPOS)}) VALUES ({marcas})", _a_fila(caso)
            )
        return {c: caso[c] for c in CAMPOS}

    def obtener(self, id_caso: str) -> dict:
        with closing(self._conectar()) as conexion:
            fila = conexion.execute("SELECT * FROM casos WHERE id_caso = ?", (id_caso,)).fetchone()
        if fila is None:
            raise CasoNoEncontrado(id_caso)
        return _de_fila(fila)

    def listar(self, estado: str | None = None, limite: int = 100) -> dict:
        """Casos del mas reciente al mas antiguo; `total` cuenta todos los que cumplen el filtro."""
        filtro, parametros = ("WHERE estado = ?", (estado,)) if estado else ("", ())
        with closing(self._conectar()) as conexion:
            total = conexion.execute(f"SELECT COUNT(*) FROM casos {filtro}", parametros).fetchone()
            filas = conexion.execute(
                f"SELECT * FROM casos {filtro} ORDER BY orden DESC LIMIT ?", (*parametros, limite)
            ).fetchall()
        return {"total": int(total[0]), "casos": [_de_fila(f) for f in filas]}

    def todos(self) -> list[dict]:
        """Todos los casos en el orden en que se registraron (para la evidencia)."""
        with closing(self._conectar()) as conexion:
            filas = conexion.execute("SELECT * FROM casos ORDER BY orden").fetchall()
        return [_de_fila(f) for f in filas]

    def revisar(self, id_caso: str, revision: dict) -> dict:
        """Guarda la decision del revisor sobre un caso pendiente. Solo una vez."""
        registro = {
            "revisor": revision["revisor"],
            "comentario": revision.get("comentario", ""),
            "fecha": fecha_utc(),
        }
        with closing(self._conectar()) as conexion, conexion:
            cambio = conexion.execute(
                "UPDATE casos SET estado = 'revisado', decision_final = ?, revision = ? "
                "WHERE id_caso = ? AND estado = 'pendiente_revision'",
                (revision["decision"], json.dumps(registro, ensure_ascii=False), id_caso),
            )
            if cambio.rowcount == 0:
                existe = conexion.execute(
                    "SELECT estado FROM casos WHERE id_caso = ?", (id_caso,)
                ).fetchone()
                if existe is None:
                    raise CasoNoEncontrado(id_caso)
                raise CasoYaRevisado(f"{id_caso} esta {existe['estado']}")
        return self.obtener(id_caso)
