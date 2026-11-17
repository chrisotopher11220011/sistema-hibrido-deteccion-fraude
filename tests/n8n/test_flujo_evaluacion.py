"""Flujo de evaluacion de transaccion (n8n/flujos/evaluacion.json; docs/spec.md, seccion 12).

Se ejecuta en el simulador con respuestas de la API simuladas. La prueba de paridad recorre
todas las combinaciones de senales y exige el mismo nivel que `decision.clasificar`, la copia
en Python de la tabla 8.4. Las ramas de error terminan siempre en `error_evaluacion`.
"""

import itertools
import json
from pathlib import Path

import pytest
from simulacion import FLUJOS, simular, validar_contrato

from fraude import __version__
from fraude.casos import CasoNuevo
from fraude.decision import clasificar

FLUJO = json.loads((FLUJOS / "evaluacion.json").read_text(encoding="utf-8"))
NODOS = {n["name"]: n for n in FLUJO["nodes"]}
EVALUAR, REGISTRAR = "Consultar evaluación", "Registrar caso"
VERSION_FLUJO = f"transaccion-{__version__}"

TRANSACCION = {
    "id_transaccion": "t-000457",
    "origen": "original",
    "monto": 1250.0,
    "variables": {f"V{i}": 0.1 for i in range(1, 29)},
}
REGISTRADO = {"id_caso": "c-0123456789ab", "estado": "simulado"}


def _regla(id_regla: str, alto_riesgo: bool, estado: str) -> dict:
    razones = {
        "no_evaluable": "No evaluable: la transaccion no trae ubicacion",
        "no_activada": "El monto 10.00 no supera el umbral 1000.00",
        "activada": "El monto 1250.00 supera el umbral 1000.00",
    }
    return {
        "id": id_regla,
        "evaluable": estado != "no_evaluable",
        "activada": estado == "activada",
        "alto_riesgo": alto_riesgo,
        "razon": razones[estado],
    }


MODELOS = {
    "no_evaluable": (False, None, False, False),
    "normal": (True, 0.40, False, False),
    "anomalia": (True, 0.65, True, False),
    "anomalia_alta": (True, 0.80, True, True),
    # anomalia_alta sin anomalia no sale de la API (umbral_prioritaria >= umbral_revision),
    # pero la tabla se define sobre los booleanos: tambien se comprueba.
    "solo_alta": (True, 0.80, False, True),
}


def _senales(estado_monto: str, estado_ubicacion: str, estado_modelo: str) -> dict:
    evaluable, puntuacion, anomalia, alta = MODELOS[estado_modelo]
    modelo = {
        "evaluable": evaluable,
        "puntuacion": puntuacion,
        "umbral_revision": 0.62,
        "umbral_prioritaria": 0.74,
        "anomalia": anomalia,
        "anomalia_alta": alta,
    }
    if anomalia:
        modelo["contribuciones"] = [{"variable": "V14", "peso": 0.21}]
    return {
        "id_transaccion": TRANSACCION["id_transaccion"],
        "reglas": [
            _regla("MONTO_ALTO", False, estado_monto),
            _regla("MONTO_ALTO_UBICACION_INUSUAL", True, estado_ubicacion),
        ],
        "modelo": modelo,
        "versiones": {"reglas": "0.2.0", "modelo": "2026-11-20T15:04Z-a1b2c3"},
    }


ESTADOS_REGLA = ("no_evaluable", "no_activada", "activada")
COMBINACIONES = list(itertools.product(ESTADOS_REGLA, ESTADOS_REGLA, MODELOS))


def _ejecutar(cuerpo, evaluar: list[dict] | None = None, registrar: list[dict] | None = None):
    respuestas = {REGISTRAR: registrar or [{"statusCode": 201, "body": REGISTRADO}]}
    if evaluar is not None:
        respuestas[EVALUAR] = evaluar
    return simular(FLUJO, cuerpo, respuestas)


def _caso_enviado(resultado: dict) -> dict:
    peticiones = [p for p in resultado["peticiones"] if p["nodo"] == REGISTRAR]
    assert len(peticiones) == 1, resultado["recorrido"]
    caso = peticiones[0]["cuerpo"]
    # El cuerpo de POST /casos cumple el contrato y el validador de la API.
    validar_contrato("caso_nuevo", caso)
    CasoNuevo.model_validate(caso)
    return caso


# --- Estructura ---------------------------------------------------------------------------


def test_ids_fijos_y_webhook_de_la_seccion_8_7():
    assert FLUJO["id"] == "FraudeEvalTx0001"
    webhook = NODOS["Webhook transacción"]
    assert webhook["parameters"]["httpMethod"] == "POST"
    assert webhook["parameters"]["path"] == "transaccion"
    assert webhook["parameters"]["responseMode"] == "responseNode"
    assert webhook["webhookId"]


def test_la_tabla_esta_en_el_nodo_clasificar_nivel_con_un_switch():
    nodo = NODOS["Clasificar nivel"]
    assert nodo["type"] == "n8n-nodes-base.switch"
    salidas = [r["outputKey"] for r in nodo["parameters"]["rules"]["values"]]
    assert salidas == ["error_evaluacion", "alerta_prioritaria", "revision_recomendada"]
    assert nodo["parameters"]["options"]["fallbackOutput"] == "extra"
    assert nodo["parameters"]["options"]["renameFallbackOutput"] == "sin_alerta"


def test_sin_nodos_code_ni_variables_de_entorno():
    texto = json.dumps(FLUJO)
    assert "n8n-nodes-base.code" not in texto
    assert "$env" not in texto


def test_consulta_a_evaluar_con_reintento_y_tiempo_limite():
    nodo = NODOS[EVALUAR]
    assert nodo["parameters"]["url"] == "http://api:8000/evaluar"
    assert nodo["parameters"]["options"]["timeout"] > 0
    assert nodo["retryOnFail"] is True and nodo["maxTries"] >= 2
    assert nodo["onError"] == "continueErrorOutput"
    assert nodo["parameters"]["options"]["response"]["response"]["neverError"] is True


def test_registro_sin_reintento_para_no_duplicar_casos():
    nodo = NODOS[REGISTRAR]
    assert nodo["parameters"]["url"] == "http://api:8000/casos"
    assert not nodo.get("retryOnFail")
    assert nodo["onError"] == "continueErrorOutput"


# --- Paridad con la tabla en Python ------------------------------------------------------


@pytest.mark.parametrize(("monto", "ubicacion", "modelo"), COMBINACIONES)
def test_paridad_con_decision_clasificar(monto, ubicacion, modelo):
    senales = _senales(monto, ubicacion, modelo)
    resultado = _ejecutar(TRANSACCION, [{"statusCode": 200, "body": senales}])
    caso = _caso_enviado(resultado)
    assert caso["nivel"] == clasificar(senales["reglas"], senales["modelo"])
    assert resultado["respuesta"] == {"codigo": 200, "cuerpo": REGISTRADO}


def test_la_paridad_cubre_los_dieciseis_casos_de_la_tabla():
    vistos = set()
    for monto, ubicacion, modelo in COMBINACIONES:
        s = _senales(monto, ubicacion, modelo)
        activadas = [r for r in s["reglas"] if r["evaluable"] and r["activada"]]
        m = s["modelo"]
        vistos.add(
            (
                any(r["alto_riesgo"] for r in activadas),
                bool(activadas),
                m["evaluable"] and m["anomalia"],
                m["evaluable"] and m["anomalia_alta"],
            )
        )
    # R_alto implica R: 12 combinaciones posibles de (R_alto, R, A, A_alta).
    assert len(vistos) == 12


# --- Contenido del caso ------------------------------------------------------------------


def test_caso_con_senales_razones_y_versiones():
    senales = _senales("activada", "no_evaluable", "anomalia_alta")
    caso = _caso_enviado(_ejecutar(TRANSACCION, [{"statusCode": 200, "body": senales}]))
    assert caso["nivel"] == "alerta_prioritaria"
    assert caso["senales"] == senales  # tal como las devolvio /evaluar
    assert caso["id_transaccion"] == "t-000457"
    assert caso["origen"] == "original" and caso["monto"] == 1250.0
    assert caso["puntuacion"] == 0.80
    assert caso["versiones"] == {
        "reglas": "0.2.0",
        "modelo": "2026-11-20T15:04Z-a1b2c3",
        "flujo": VERSION_FLUJO,
    }
    razones = " | ".join(caso["razones"])
    assert "El monto 1250.00 supera el umbral 1000.00" in razones
    assert "0.800" in razones and "0.740" in razones
    # La senal no evaluable queda anotada.
    assert "MONTO_ALTO_UBICACION_INUSUAL" in razones and "No evaluable" in razones


def test_explicacion_por_plantilla_sin_lenguaje_de_confirmacion():
    for monto, modelo, nivel in [
        ("activada", "anomalia_alta", "alerta_prioritaria"),
        ("activada", "normal", "revision_recomendada"),
        ("no_activada", "normal", "sin_alerta"),
    ]:
        senales = _senales(monto, "no_evaluable", modelo)
        caso = _caso_enviado(_ejecutar(TRANSACCION, [{"statusCode": 200, "body": senales}]))
        assert caso["nivel"] == nivel
        explicacion = caso["explicacion"]
        assert explicacion["origen"] == "plantilla"
        texto = explicacion["texto"].lower()
        assert "confirma" not in texto and "es fraude" not in texto
        if nivel == "sin_alerta":
            assert "no se genera alerta" in texto
        else:
            assert "señala" in texto and "revis" in texto
            # Solo menciona lo que se activo.
            assert "supera el umbral" in texto
            assert "ubicacion" not in texto


def test_notificacion_de_prueba_solo_con_alerta():
    alerta = _senales("activada", "no_evaluable", "normal")
    caso = _caso_enviado(_ejecutar(TRANSACCION, [{"statusCode": 200, "body": alerta}]))
    assert caso["notificacion"]["canal"] == "simulada"
    assert caso["notificacion"]["estado"] == "simulada_enviada"
    tranquila = _senales("no_activada", "no_evaluable", "normal")
    caso = _caso_enviado(_ejecutar(TRANSACCION, [{"statusCode": 200, "body": tranquila}]))
    assert caso["notificacion"]["estado"] == "no_aplica"


def test_sin_alerta_puede_no_tener_razones_de_alerta():
    senales = _senales("no_activada", "no_activada", "normal")
    caso = _caso_enviado(_ejecutar(TRANSACCION, [{"statusCode": 200, "body": senales}]))
    assert caso["nivel"] == "sin_alerta"
    assert caso["razones"] == []


# --- Rama de error: entrada invalida -------------------------------------------------------


ENTRADAS_INVALIDAS = {
    "no es objeto": [1, 2],
    "texto": "hola",
    "nulo": None,
    "sin id": {"origen": "original", "monto": 10.0},
    "id vacio": {"id_transaccion": "", "origen": "original", "monto": 10.0},
    "id largo": {"id_transaccion": "x" * 101, "origen": "original", "monto": 10.0},
    "id numero": {"id_transaccion": 7, "origen": "original", "monto": 10.0},
    "origen raro": {"id_transaccion": "t-1", "origen": "otro", "monto": 10.0},
    "monto texto": {"id_transaccion": "t-1", "origen": "original", "monto": "1500"},
    "monto negativo": {"id_transaccion": "t-1", "origen": "original", "monto": -1},
    "monto booleano": {"id_transaccion": "t-1", "origen": "original", "monto": True},
    "con Class": {"id_transaccion": "t-1", "origen": "original", "monto": 1.0, "Class": 1},
}


@pytest.mark.parametrize("nombre", ENTRADAS_INVALIDAS)
def test_entrada_invalida_es_error_evaluacion_sin_llamar_a_la_api(nombre):
    resultado = _ejecutar(ENTRADAS_INVALIDAS[nombre])
    assert not [p for p in resultado["peticiones"] if p["nodo"] == EVALUAR]
    caso = _caso_enviado(resultado)
    assert caso["nivel"] == "error_evaluacion"
    assert caso["senales"] is None and caso["puntuacion"] is None
    assert caso["razones"] and caso["razones"][0].startswith("Entrada inválida")
    assert caso["notificacion"]["estado"] == "simulada_enviada"
    assert resultado["respuesta"]["codigo"] == 200


def test_entrada_invalida_conserva_lo_que_si_es_identificable():
    caso = _caso_enviado(_ejecutar(ENTRADAS_INVALIDAS["monto texto"]))
    assert caso["id_transaccion"] == "t-1" and caso["origen"] == "original"
    assert caso["monto"] is None
    caso = _caso_enviado(_ejecutar(ENTRADAS_INVALIDAS["id numero"]))
    assert caso["id_transaccion"] is None and caso["monto"] == 10.0


def test_la_validacion_de_n8n_no_es_mas_estricta_que_la_api():
    # Lo que la API acepta, n8n lo deja pasar a /evaluar (si no, la paridad se romperia).
    aceptadas = [
        TRANSACCION,
        {"id_transaccion": "x" * 100, "origen": "sintetico", "monto": 0},
        {
            "id_transaccion": "s-1",
            "origen": "sintetico",
            "monto": 2000.5,
            "ubicacion": {"pais_habitual": "EC", "pais_transaccion": "US"},
        },
    ]
    for t in aceptadas:
        senales = _senales("no_activada", "no_evaluable", "normal")
        resultado = _ejecutar(t, [{"statusCode": 200, "body": senales}])
        evaluar = [p for p in resultado["peticiones"] if p["nodo"] == EVALUAR]
        assert len(evaluar) == 1 and evaluar[0]["cuerpo"] == t


# --- Rama de error: evaluacion fallida -----------------------------------------------------


def _error_api(codigo: int, tipo: str) -> dict:
    cuerpo = {
        "id_transaccion": "t-000457",
        "error": {"tipo": tipo, "mensaje": f"mensaje de {tipo}", "detalles": []},
    }
    return {"statusCode": codigo, "body": cuerpo}


@pytest.mark.parametrize(
    ("codigo", "tipo"),
    [(422, "entrada_invalida"), (503, "modelo_no_disponible"), (500, "error_interno")],
)
def test_evaluar_responde_error_y_el_caso_es_error_evaluacion(codigo, tipo):
    resultado = _ejecutar(TRANSACCION, [_error_api(codigo, tipo)])
    # Un codigo de error no se reintenta: la API ya respondio.
    assert len([p for p in resultado["peticiones"] if p["nodo"] == EVALUAR]) == 1
    caso = _caso_enviado(resultado)
    assert caso["nivel"] == "error_evaluacion"
    assert caso["senales"] is None
    assert caso["id_transaccion"] == "t-000457" and caso["monto"] == 1250.0
    assert str(codigo) in caso["razones"][0] and tipo in caso["razones"][0]
    assert "pendiente de revisión" in caso["explicacion"]["texto"]


def test_respuesta_200_que_no_es_un_objeto_es_error_evaluacion():
    resultado = _ejecutar(TRANSACCION, [{"statusCode": 200, "body": "no json"}])
    caso = _caso_enviado(resultado)
    assert caso["nivel"] == "error_evaluacion"


def test_evaluar_sin_respuesta_tras_tres_intentos():
    caida = {"error": {"message": "connect ECONNREFUSED 172.18.0.2:8000"}}
    resultado = _ejecutar(TRANSACCION, [caida, caida, caida])
    assert [p["intento"] for p in resultado["peticiones"] if p["nodo"] == EVALUAR] == [1, 2, 3]
    caso = _caso_enviado(resultado)
    assert caso["nivel"] == "error_evaluacion"
    assert "ECONNREFUSED" in caso["razones"][0]
    assert caso["versiones"]["flujo"] == VERSION_FLUJO


def test_evaluar_se_recupera_en_el_segundo_intento():
    senales = _senales("activada", "no_evaluable", "normal")
    respuestas = [{"error": {"message": "timeout"}}, {"statusCode": 200, "body": senales}]
    resultado = _ejecutar(TRANSACCION, respuestas)
    assert _caso_enviado(resultado)["nivel"] == "revision_recomendada"


# --- Registro del caso ------------------------------------------------------------------


def test_registro_rechazado_responde_502_con_el_caso():
    senales = _senales("activada", "no_evaluable", "normal")
    resultado = _ejecutar(
        TRANSACCION,
        [{"statusCode": 200, "body": senales}],
        [_error_api(422, "entrada_invalida")],
    )
    respuesta = resultado["respuesta"]
    assert respuesta["codigo"] == 502
    assert respuesta["cuerpo"]["error"]["tipo"] == "caso_no_registrado"
    assert respuesta["cuerpo"]["caso"]["nivel"] == "revision_recomendada"
    assert "422" in respuesta["cuerpo"]["error"]["mensaje"]


def test_api_caida_responde_502_con_el_caso_en_error_evaluacion():
    caida = {"error": {"message": "connect ECONNREFUSED"}}
    resultado = _ejecutar(TRANSACCION, [caida, caida, caida], [caida])
    # Sin reintento al registrar.
    assert len([p for p in resultado["peticiones"] if p["nodo"] == REGISTRAR]) == 1
    respuesta = resultado["respuesta"]
    assert respuesta["codigo"] == 502
    assert respuesta["cuerpo"]["caso"]["nivel"] == "error_evaluacion"
    assert "ECONNREFUSED" in respuesta["cuerpo"]["error"]["mensaje"]
    assert resultado["fallo_flujo"] is None


def test_ninguna_rama_deja_respuestas_simuladas_sin_usar():
    senales = _senales("activada", "activada", "anomalia")
    resultado = _ejecutar(TRANSACCION, [{"statusCode": 200, "body": senales}])
    assert resultado["sobrantes"] == {}
    assert Path(FLUJOS / "evaluacion.json").is_file()
