"""Las rutas de casos cumplen docs/contratos/ (caso_nuevo, caso, lista_casos, revision, error)."""

import pytest
from contratos import validar
from fastapi.testclient import TestClient

from fraude.api import crear_app

SINTETICA = {
    "id_transaccion": "s-1",
    "origen": "sintetico",
    "monto": 1250.0,
    "ubicacion": {"pais_habitual": "EC", "pais_transaccion": "US"},
}


@pytest.fixture
def cliente(raiz_api):
    return TestClient(crear_app(raiz_api), raise_server_exceptions=False)


def _caso_nuevo(cliente, nivel: str) -> dict:
    senales = cliente.post("/evaluar", json=SINTETICA).json()
    caso = {
        "id_transaccion": "s-1",
        "origen": "sintetico",
        "monto": 1250.0,
        "senales": senales,
        "puntuacion": None,
        "nivel": nivel,
        "razones": [] if nivel == "sin_alerta" else ["El monto supera el umbral"],
        "explicacion": {"texto": "t", "origen": "plantilla", "modelo": None, "duracion_ms": 1.5},
        "notificacion": {"canal": "simulada", "estado": "registrada", "detalle": None},
        "versiones": {"reglas": "0.2.0", "modelo": None, "flujo": None},
    }
    validar("caso_nuevo", caso)
    return caso


@pytest.mark.parametrize(
    "nivel", ["alerta_prioritaria", "revision_recomendada", "sin_alerta", "error_evaluacion"]
)
def test_post_casos_cumple_el_contrato(cliente, nivel):
    respuesta = cliente.post("/casos", json=_caso_nuevo(cliente, nivel))

    assert respuesta.status_code == 201
    validar("caso", respuesta.json())


def test_revision_y_lista_cumplen_el_contrato(cliente):
    caso = cliente.post("/casos", json=_caso_nuevo(cliente, "alerta_prioritaria")).json()
    cliente.post("/casos", json=_caso_nuevo(cliente, "sin_alerta"))
    revision = {"decision": "sospecha_descartada", "revisor": "ana", "comentario": "ok"}
    validar("revision", revision)

    revisado = cliente.post(f"/casos/{caso['id_caso']}/revision", json=revision)

    assert revisado.status_code == 200
    validar("caso", revisado.json())
    validar("lista_casos", cliente.get("/casos").json())


def test_errores_de_casos_cumplen_el_contrato(cliente):
    caso = cliente.post("/casos", json=_caso_nuevo(cliente, "alerta_prioritaria")).json()
    ruta = f"/casos/{caso['id_caso']}/revision"
    revision = {"decision": "sospecha_confirmada", "revisor": "ana"}
    cliente.post(ruta, json=revision)

    respuestas = [
        cliente.post(ruta, json=revision),
        cliente.post("/casos/c-000000000000/revision", json=revision),
        cliente.post("/casos", json={"nivel": "sin_alerta"}),
        cliente.get("/casos", params={"limite": 0}),
    ]

    assert [r.status_code for r in respuestas] == [409, 404, 422, 422]
    for respuesta in respuestas:
        validar("error", respuesta.json())
