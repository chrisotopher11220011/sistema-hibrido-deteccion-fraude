"""Las respuestas reales de la API cumplen los esquemas de docs/contratos/."""

import pytest
from contratos import completar_variables, cumple, validar
from fastapi.testclient import TestClient

from apoyo import variables_transaccion
from fraude.api import crear_app


@pytest.fixture
def cliente(raiz_api):
    return TestClient(crear_app(raiz_api), raise_server_exceptions=False)


@pytest.fixture
def cliente_con_modelo(raiz_api, entrenar_modelo):
    entrenar_modelo(raiz_api)
    return TestClient(crear_app(raiz_api), raise_server_exceptions=False)


def _validar_respuesta(respuesta, esquema_ok: str) -> None:
    validar(esquema_ok if respuesta.status_code < 400 else "error", respuesta.json())


def _transacciones(ejemplo_8_2: dict) -> list[dict]:
    completo = completar_variables(ejemplo_8_2)
    return [
        completo,
        {**completo, "variables": variables_transaccion(50.0)},
        {**completo, "variables": None, "origen": "original"},
        {"id_transaccion": "s-1", "origen": "sintetico", "monto": 1500.0,
         "ubicacion": {"pais_habitual": "EC", "pais_transaccion": "US"}},
        {"id_transaccion": "s-2", "origen": "sintetico", "monto": 10.0,
         "ubicacion": {"pais_habitual": "EC", "pais_transaccion": "EC"}},
        {"id_transaccion": "s-3", "origen": "sintetico", "monto": 1500.0},
    ]  # fmt: skip


def test_salud_cumple_el_contrato(cliente, raiz_api, entrenar_modelo):
    validar("salud", cliente.get("/salud").json())
    entrenar_modelo(raiz_api)
    validar("salud", cliente.get("/salud").json())


def test_evaluar_con_modelo_cumple_el_contrato(cliente_con_modelo, ejemplos):
    for t in _transacciones(ejemplos["transaccion"]):
        validar("transaccion", t)
        respuesta = cliente_con_modelo.post("/evaluar", json=t)
        assert respuesta.status_code == 200, respuesta.text
        validar("evaluacion", respuesta.json())


def test_evaluar_sin_modelo_cumple_el_contrato(cliente, ejemplos):
    codigos = set()
    for t in _transacciones(ejemplos["transaccion"]):
        respuesta = cliente.post("/evaluar", json=t)
        codigos.add(respuesta.status_code)
        _validar_respuesta(respuesta, "evaluacion")
    assert codigos == {200, 503}


def test_respuesta_200_tiene_exactamente_los_campos_del_contrato(cliente_con_modelo, ejemplos):
    t = completar_variables(ejemplos["transaccion"])

    cuerpo = cliente_con_modelo.post("/evaluar", json=t).json()

    assert set(cuerpo) == set(ejemplos["evaluacion"])
    assert set(cuerpo["modelo"]) - {"contribuciones"} == set(ejemplos["evaluacion"]["modelo"])
    assert set(cuerpo["versiones"]) == set(ejemplos["evaluacion"]["versiones"])
    assert {r["id"] for r in cuerpo["reglas"]} == {"MONTO_ALTO", "MONTO_ALTO_UBICACION_INUSUAL"}


def test_el_contrato_y_la_api_rechazan_lo_mismo(cliente, ejemplos):
    base = completar_variables(ejemplos["transaccion"])
    invalidas = [
        {**base, "Class": 1},
        {**base, "origen": "real"},
        {**base, "monto": -1},
        {**base, "id_transaccion": ""},
        {**base, "origen": "sintetico"},
        {**base, "ubicacion": {"pais_habitual": "ec", "pais_transaccion": "US"}},
        {**base, "variables": {"V1": 1.0}},
    ]
    for t in invalidas:
        respuesta = cliente.post("/evaluar", json=t)
        assert respuesta.status_code == 422, t
        validar("error", respuesta.json())


def test_rutas_desconocidas_y_tipos_no_numericos_cumplen_el_contrato(cliente, ejemplos):
    base = completar_variables(ejemplos["transaccion"])
    respuestas = [
        cliente.get("/evaluar"),
        cliente.get("/no-existe"),
        cliente.post("/evaluar", json={**base, "monto": "1250"}),
        cliente.post("/evaluar", json={**base, "monto": True}),
    ]

    assert [r.status_code for r in respuestas] == [405, 404, 422, 422]
    for respuesta in respuestas:
        validar("error", respuesta.json())
    for t in ({**base, "monto": "1250"}, {**base, "monto": True}):
        assert not cumple("transaccion", t)
