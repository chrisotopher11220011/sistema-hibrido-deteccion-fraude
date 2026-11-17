"""El simulador de flujos reproduce la semantica de n8n 2.47.7 que usan los flujos.

Cada prueba fija un comportamiento comprobado en el codigo de n8n (docs/planes/fase-5.md):
si el simulador se equivocara, las pruebas de los flujos no valdrian nada.
"""

import pytest
from simulacion import ErrorSimulador

WEBHOOK = {
    "parameters": {"httpMethod": "POST", "path": "x", "responseMode": "responseNode"},
    "name": "Webhook",
    "type": "n8n-nodes-base.webhook",
    "typeVersion": 2,
    "webhookId": "w-1",
}


def _nodo(nombre: str, tipo: str, version: float, parametros: dict, **extra) -> dict:
    return {
        "parameters": parametros,
        "name": nombre,
        "type": f"n8n-nodes-base.{tipo}",
        "typeVersion": version,
        **extra,
    }


def _set(nombre: str, campos: dict[str, tuple[str, object]], otros: bool = False) -> dict:
    asignaciones = [
        {"id": f"{nombre}-{i}", "name": n, "type": t, "value": v}
        for i, (n, (t, v)) in enumerate(campos.items())
    ]
    parametros = {"assignments": {"assignments": asignaciones}, "options": {}}
    if otros:
        parametros["includeOtherFields"] = True
    return _nodo(nombre, "set", 3.4, parametros)


def _condicion(campo: str, operacion: str = "true", tipo: str = "boolean", derecha=None) -> dict:
    operador = {"type": tipo, "operation": operacion}
    if tipo == "boolean":
        operador["singleValue"] = True
    return {"leftValue": f"={{{{ $json.{campo} }}}}", "rightValue": derecha, "operator": operador}


def _condiciones(*condiciones: dict, combinador: str = "and") -> dict:
    return {
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
        "conditions": list(condiciones),
        "combinator": combinador,
    }


def _responder(nombre: str, cuerpo: str, codigo=None) -> dict:
    opciones = {} if codigo is None else {"responseCode": codigo}
    parametros = {"respondWith": "json", "responseBody": cuerpo, "options": opciones}
    return _nodo(nombre, "respondToWebhook", 1.1, parametros)


def _destino(nodo: str) -> dict:
    return {"node": nodo, "type": "main", "index": 0}


def _flujo(nodos: list[dict], conexiones: dict[str, list[list[str]]]) -> dict:
    return {
        "id": "SimPrueba0000001",
        "name": "Prueba",
        "nodes": nodos,
        "connections": {
            origen: {"main": [[_destino(d) for d in salida] for salida in salidas]}
            for origen, salidas in conexiones.items()
        },
        "settings": {"executionOrder": "v1"},
    }


def _http(nombre: str, url: str, cuerpo: str | None = None, **ajustes) -> dict:
    parametros = {
        "method": "POST",
        "url": url,
        "options": {
            "timeout": 1000,
            "response": {"response": {"fullResponse": True, "neverError": True}},
        },
    }
    if cuerpo is not None:
        parametros.update({"sendBody": True, "specifyBody": "json", "jsonBody": cuerpo})
    return _nodo(nombre, "httpRequest", 4.2, parametros, **ajustes)


# --- Set, If y Respond --------------------------------------------------------------------


def test_set_e_if_eligen_la_rama_y_responden(simulador):
    flujo = _flujo(
        [
            WEBHOOK,
            _set("Calcular", {"grande": ("boolean", "={{ $json.body.n > 10 }}")}),
            _nodo("¿Grande?", "if", 2.2, {"conditions": _condiciones(_condicion("grande"))}),
            _responder("Si", "={{ { rama: 'si', n: $('Webhook').first().json.body.n } }}"),
            _responder("No", '={"rama": "no"}', 202),
        ],
        {"Webhook": [["Calcular"]], "Calcular": [["¿Grande?"]], "¿Grande?": [["Si"], ["No"]]},
    )
    esperada = {"codigo": 200, "cuerpo": {"rama": "si", "n": 50}}
    assert simulador(flujo, {"n": 50})["respuesta"] == esperada
    resultado = simulador(flujo, {"n": 1})
    assert resultado["respuesta"] == {"codigo": 202, "cuerpo": {"rama": "no"}}
    assert resultado["recorrido"] == ["Webhook", "Calcular", "¿Grande?", "No"]


def test_set_sin_include_other_fields_solo_deja_lo_asignado(simulador):
    flujo = _flujo(
        [
            WEBHOOK,
            _set("Solo", {"a": ("number", "={{ 1 }}")}),
            _set("Con otros", {"b": ("string", "x")}, otros=True),
            _responder("R", "={{ $json }}"),
        ],
        {"Webhook": [["Solo"]], "Solo": [["Con otros"]], "Con otros": [["R"]]},
    )
    assert simulador(flujo, {})["respuesta"]["cuerpo"] == {"a": 1, "b": "x"}


def test_set_acepta_null_y_rechaza_tipos_que_no_coinciden(simulador):
    nulo = _flujo(
        [WEBHOOK, _set("S", {"o": ("object", "={{ null }}")}), _responder("R", "={{ $json }}")],
        {"Webhook": [["S"]], "S": [["R"]]},
    )
    assert simulador(nulo, {})["respuesta"]["cuerpo"] == {"o": None}
    mal = _flujo(
        [WEBHOOK, _set("S", {"b": ("boolean", "={{ 'si' }}")}), _responder("R", "={{ $json }}")],
        {"Webhook": [["S"]], "S": [["R"]]},
    )
    with pytest.raises(ErrorSimulador, match="boolean"):
        simulador(mal, {})


def test_if_estricto_falla_si_el_valor_no_es_booleano(simulador):
    flujo = _flujo(
        [
            WEBHOOK,
            _nodo("¿?", "if", 2.2, {"conditions": _condiciones(_condicion("body.n"))}),
            _responder("R", "={{ $json }}"),
        ],
        {"Webhook": [["¿?"]], "¿?": [["R"], ["R"]]},
    )
    with pytest.raises(ErrorSimulador, match="tipo"):
        simulador(flujo, {"n": 1})


def test_if_con_numero_igual(simulador):
    flujo = _flujo(
        [
            WEBHOOK,
            _nodo(
                "¿200?",
                "if",
                2.2,
                {"conditions": _condiciones(_condicion("body.c", "equals", "number", 200))},
            ),
            _responder("Si", '={"ok": true}'),
            _responder("No", '={"ok": false}'),
        ],
        {"Webhook": [["¿200?"]], "¿200?": [["Si"], ["No"]]},
    )
    assert simulador(flujo, {"c": 200})["respuesta"]["cuerpo"] == {"ok": True}
    assert simulador(flujo, {"c": 503})["respuesta"]["cuerpo"] == {"ok": False}


# --- Switch -------------------------------------------------------------------------------


def _switch() -> dict:
    reglas = [
        {"conditions": _condiciones(_condicion("a")), "renameOutput": True, "outputKey": "a"},
        {
            "conditions": _condiciones(_condicion("b"), _condicion("c"), combinador="or"),
            "renameOutput": True,
            "outputKey": "b_o_c",
        },
    ]
    parametros = {
        "rules": {"values": reglas},
        "options": {"fallbackOutput": "extra", "renameFallbackOutput": "resto"},
    }
    return _nodo("Switch", "switch", 3.2, parametros)


@pytest.mark.parametrize(
    ("a", "b", "c", "esperada"),
    [
        (True, True, True, "a"),  # solo la primera regla que se cumple
        (False, True, False, "b_o_c"),
        (False, False, True, "b_o_c"),
        (False, False, False, "resto"),  # salida extra al final
    ],
)
def test_switch_primera_regla_y_salida_extra(simulador, a, b, c, esperada):
    flujo = _flujo(
        [
            WEBHOOK,
            _set(
                "Valores",
                {
                    "a": ("boolean", "={{ $json.body.a }}"),
                    "b": ("boolean", "={{ $json.body.b }}"),
                    "c": ("boolean", "={{ $json.body.c }}"),
                },
            ),
            _switch(),
            _responder("A", '={"salida": "a"}'),
            _responder("BC", '={"salida": "b_o_c"}'),
            _responder("Resto", '={"salida": "resto"}'),
        ],
        {"Webhook": [["Valores"]], "Valores": [["Switch"]], "Switch": [["A"], ["BC"], ["Resto"]]},
    )
    assert simulador(flujo, {"a": a, "b": b, "c": c})["respuesta"]["cuerpo"]["salida"] == esperada


# --- HTTP Request -------------------------------------------------------------------------


def _flujo_http(**ajuste) -> dict:
    return _flujo(
        [
            WEBHOOK,
            _http("Pedir", "=http://api:8000/x/{{ $json.body.id }}", "={{ $json.body }}", **ajuste),
            _responder("Bien", "={{ { codigo: $json.statusCode, cuerpo: $json.body } }}"),
            _responder("Mal", "={{ { fallo: $json.error.message, entrada: $json.body } }}", 502),
        ],
        {"Webhook": [["Pedir"]], "Pedir": [["Bien"], ["Mal"]]},
    )


def test_http_envia_cuerpo_y_devuelve_respuesta_completa(simulador):
    resultado = simulador(
        _flujo_http(onError="continueErrorOutput"),
        {"id": "a b"},
        {"Pedir": [{"statusCode": 503, "body": {"error": {"tipo": "x"}}}]},
    )
    assert resultado["peticiones"] == [
        {
            "nodo": "Pedir",
            "metodo": "POST",
            "url": "http://api:8000/x/a b",
            "cuerpo": {"id": "a b"},
            "intento": 1,
        }
    ]
    # neverError: un 503 no es un fallo del nodo y no se reintenta.
    assert resultado["respuesta"]["cuerpo"] == {"codigo": 503, "cuerpo": {"error": {"tipo": "x"}}}


def test_http_reintenta_errores_de_red_y_usa_la_salida_de_error(simulador):
    error = {"error": {"message": "connect ECONNREFUSED"}}
    resultado = simulador(
        _flujo_http(
            onError="continueErrorOutput", retryOnFail=True, maxTries=3, waitBetweenTries=1000
        ),
        {"id": "1"},
        {"Pedir": [error, error, error]},
    )
    assert [p["intento"] for p in resultado["peticiones"]] == [1, 2, 3]
    assert resultado["esperas_ms"] == 2000
    # La salida de error lleva la entrada del nodo mas `error` (handleNodeErrorOutput).
    assert resultado["respuesta"] == {
        "codigo": 502,
        "cuerpo": {"fallo": "connect ECONNREFUSED", "entrada": {"id": "1"}},
    }


def test_http_un_reintento_que_acierta_sigue_por_la_salida_normal(simulador):
    resultado = simulador(
        _flujo_http(onError="continueErrorOutput", retryOnFail=True, maxTries=3),
        {"id": "1"},
        {"Pedir": [{"error": {"message": "timeout"}}, {"statusCode": 200, "body": {"ok": 1}}]},
    )
    assert resultado["respuesta"]["cuerpo"] == {"codigo": 200, "cuerpo": {"ok": 1}}
    assert len(resultado["peticiones"]) == 2


def test_http_max_tries_se_acota_como_en_n8n(simulador):
    error = {"error": {"message": "x"}}
    resultado = simulador(
        _flujo_http(onError="continueErrorOutput", retryOnFail=True, maxTries=9),
        {"id": "1"},
        {"Pedir": [error] * 9},
    )
    assert len(resultado["peticiones"]) == 5


def test_http_sin_salida_de_error_detiene_el_flujo(simulador):
    resultado = simulador(_flujo_http(), {"id": "1"}, {"Pedir": [{"error": {"message": "caida"}}]})
    assert resultado["respuesta"] is None
    assert "caida" in resultado["fallo_flujo"]


def test_http_sin_respuesta_simulada_es_un_error_del_simulador(simulador):
    with pytest.raises(ErrorSimulador, match="respuesta simulada"):
        simulador(_flujo_http(onError="continueErrorOutput"), {"id": "1"}, {})


# --- Reglas del subconjunto ---------------------------------------------------------------


def test_expresion_con_doble_llave_interna_se_rechaza(simulador):
    # n8n cierra la expresion en el primer «}}»: `{a: {b: 1}}` se partiria.
    flujo = _flujo([WEBHOOK, _responder("R", "={{ {a: {b: 1}} }}")], {"Webhook": [["R"]]})
    with pytest.raises(ErrorSimulador):
        simulador(flujo, {})


def test_nodo_fuera_del_subconjunto_se_rechaza(simulador):
    codigo = _nodo("Codigo", "code", 2, {"jsCode": "return items"})
    flujo = _flujo([WEBHOOK, codigo], {"Webhook": [["Codigo"]]})
    with pytest.raises(ErrorSimulador, match="no admitido"):
        simulador(flujo, {})


def test_nombre_de_campo_con_punto_se_rechaza(simulador):
    flujo = _flujo(
        [WEBHOOK, _set("S", {"a.b": ("number", "={{ 1 }}")}), _responder("R", "={{ $json }}")],
        {"Webhook": [["S"]], "S": [["R"]]},
    )
    with pytest.raises(ErrorSimulador, match="punto"):
        simulador(flujo, {})


def test_referencia_a_un_nodo_no_ejecutado_falla(simulador):
    flujo = _flujo(
        [
            WEBHOOK,
            _set("Otro", {"a": ("number", "={{ 1 }}")}),
            _responder("R", "={{ $('Otro').first().json }}"),
        ],
        {"Webhook": [["R"]]},
    )
    with pytest.raises(ErrorSimulador, match="no se ha ejecutado"):
        simulador(flujo, {})


def test_responder_dos_veces_es_un_error(simulador):
    flujo = _flujo(
        [WEBHOOK, _responder("R1", '={"a": 1}'), _responder("R2", '={"a": 2}')],
        {"Webhook": [["R1"]], "R1": [["R2"]]},
    )
    with pytest.raises(ErrorSimulador, match="dos veces"):
        simulador(flujo, {})
