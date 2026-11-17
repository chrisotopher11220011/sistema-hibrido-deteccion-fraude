"""Flujo de revision humana (n8n/flujos/revision.json; docs/spec.md, seccion 12).

Recibe caso, decision, revisor y comentario, y los guarda con `POST /casos/{id}/revision`.
Devuelve el codigo y el cuerpo de la API; un `id_caso` con otra forma no llega a la API.
"""

import json

import pytest
from simulacion import FLUJOS, simular, validar_contrato

FLUJO = json.loads((FLUJOS / "revision.json").read_text(encoding="utf-8"))
NODOS = {n["name"]: n for n in FLUJO["nodes"]}
GUARDAR = "Guardar revisión"
REVISION = {
    "id_caso": "c-0123456789ab",
    "decision": "sospecha_confirmada",
    "revisor": "Ana",
    "comentario": "Patrón conocido",
}


def _ejecutar(cuerpo, respuestas: list[dict] | None = None) -> dict:
    return simular(FLUJO, cuerpo, {GUARDAR: respuestas} if respuestas is not None else {})


def test_ids_fijos_y_webhook_de_la_seccion_8_7():
    assert FLUJO["id"] == "FraudeRevision01"
    webhook = NODOS["Webhook revisión"]
    assert webhook["parameters"]["httpMethod"] == "POST"
    assert webhook["parameters"]["path"] == "revision"
    assert webhook["parameters"]["responseMode"] == "responseNode"
    assert webhook["webhookId"]


def test_reenvia_la_revision_y_devuelve_el_caso():
    revisado = {"id_caso": "c-0123456789ab", "estado": "revisado"}
    resultado = _ejecutar(REVISION, [{"statusCode": 200, "body": revisado}])
    assert resultado["peticiones"] == [
        {
            "nodo": GUARDAR,
            "metodo": "POST",
            "url": "http://api:8000/casos/c-0123456789ab/revision",
            "cuerpo": {
                "decision": "sospecha_confirmada",
                "revisor": "Ana",
                "comentario": "Patrón conocido",
            },
            "intento": 1,
        }
    ]
    assert resultado["respuesta"] == {"codigo": 200, "cuerpo": revisado}


def test_sin_comentario_no_envia_el_campo():
    sin = {k: v for k, v in REVISION.items() if k != "comentario"}
    resultado = _ejecutar(sin, [{"statusCode": 200, "body": {}}])
    assert "comentario" not in resultado["peticiones"][0]["cuerpo"]


@pytest.mark.parametrize(
    ("codigo", "tipo"),
    [(404, "caso_no_encontrado"), (409, "caso_ya_revisado"), (422, "entrada_invalida")],
)
def test_errores_de_la_api_se_devuelven_tal_cual(codigo, tipo):
    cuerpo = {"id_transaccion": None, "error": {"tipo": tipo, "mensaje": "x", "detalles": []}}
    resultado = _ejecutar(REVISION, [{"statusCode": codigo, "body": cuerpo}])
    assert resultado["respuesta"] == {"codigo": codigo, "cuerpo": cuerpo}


@pytest.mark.parametrize(
    "cuerpo",
    [
        {**REVISION, "id_caso": "../salud"},
        {**REVISION, "id_caso": "c-0123456789AB"},
        {**REVISION, "id_caso": 5},
        {k: v for k, v in REVISION.items() if k != "id_caso"},
        [REVISION],
        None,
    ],
)
def test_id_caso_invalido_responde_422_sin_llamar_a_la_api(cuerpo):
    resultado = _ejecutar(cuerpo)
    assert resultado["peticiones"] == []
    assert resultado["respuesta"]["codigo"] == 422
    validar_contrato("error", resultado["respuesta"]["cuerpo"])
    error = resultado["respuesta"]["cuerpo"]["error"]
    assert error["tipo"] == "entrada_invalida" and "id_caso" in error["mensaje"]


def test_api_caida_responde_502():
    resultado = _ejecutar(REVISION, [{"error": {"message": "connect ECONNREFUSED"}}])
    assert len(resultado["peticiones"]) == 1  # sin reintento: no duplicar la revision
    assert resultado["respuesta"]["codigo"] == 502
    validar_contrato("error_flujo", resultado["respuesta"]["cuerpo"])
    error = resultado["respuesta"]["cuerpo"]["error"]
    assert error["tipo"] == "revision_no_registrada" and "ECONNREFUSED" in error["mensaje"]


def test_sin_nodos_code_ni_variables_de_entorno():
    texto = json.dumps(FLUJO)
    assert "n8n-nodes-base.code" not in texto and "$env" not in texto
