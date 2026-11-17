"""Los esquemas de docs/contratos/ expresan la seccion 8 de docs/spec.md."""

import copy

import jsonschema
import pytest
import yaml
from contratos import RAIZ, completar_variables, cumple, ejemplos_spec, esquemas, validar

ESPERADOS = {
    "transaccion",
    "evaluacion",
    "error",
    "caso_nuevo",
    "caso",
    "lista_casos",
    "revision",
    "salud",
    "error_flujo",
    "lote",
    "redaccion_pedida",
    "redaccion",
}
NIVELES = yaml.safe_load((RAIZ / "config" / "decision.yaml").read_text())["niveles"]


def _caso_nuevo(**cambios) -> dict:
    base = {
        "id_transaccion": "t-000457",
        "origen": "original",
        "monto": 1250.0,
        "senales": ejemplos_spec()["evaluacion"],
        "puntuacion": 0.81,
        "nivel": "alerta_prioritaria",
        "razones": ["El monto 1250.00 supera el umbral 1000.00"],
        "explicacion": {"texto": "Se señala para revisión.", "origen": "plantilla"},
        "notificacion": {"canal": "simulada", "estado": "registrada"},
        "versiones": {"reglas": "0.2.0", "modelo": "m", "flujo": "f"},
    }
    return {**base, **cambios}


def test_estan_todos_los_esquemas():
    assert set(esquemas()) == ESPERADOS


@pytest.mark.parametrize("nombre", sorted(ESPERADOS))
def test_cada_esquema_es_valido_y_tiene_id(nombre):
    esquema = esquemas()[nombre]
    jsonschema.Draft202012Validator.check_schema(esquema)
    assert esquema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert esquema["$id"] == f"urn:fraude:contratos:{nombre}"


def test_ejemplo_8_2_cumple_transaccion(ejemplos):
    validar("transaccion", completar_variables(ejemplos["transaccion"]))


def test_ejemplo_8_2_tal_cual_tiene_variables_abreviadas(ejemplos):
    # La especificacion abrevia el ejemplo; el contrato exige V1 a V28 completas.
    assert not cumple("transaccion", ejemplos["transaccion"])


def test_ejemplo_8_3_cumple_evaluacion(ejemplos):
    validar("evaluacion", ejemplos["evaluacion"])


@pytest.mark.parametrize(
    "cambio",
    [
        {"Class": 1},
        {"origen": "real"},
        {"monto": -1},
        {"id_transaccion": ""},
        {"ubicacion": {"pais_habitual": "ec", "pais_transaccion": "US"}},
    ],
)
def test_transaccion_rechaza(ejemplos, cambio):
    t = completar_variables(ejemplos["transaccion"])
    assert not cumple("transaccion", {**t, **cambio})


def test_transaccion_rechaza_variables_incompletas_o_extra(ejemplos):
    t = completar_variables(ejemplos["transaccion"])
    incompleta = copy.deepcopy(t)
    del incompleta["variables"]["V7"]
    extra = copy.deepcopy(t)
    extra["variables"]["Amount"] = 3.0
    assert not cumple("transaccion", incompleta)
    assert not cumple("transaccion", extra)


def test_transaccion_sintetica_sin_variables():
    sintetica = {
        "id_transaccion": "s-1",
        "origen": "sintetico",
        "monto": 1500.0,
        "ubicacion": {"pais_habitual": "EC", "pais_transaccion": "US"},
    }
    validar("transaccion", sintetica)
    validar("transaccion", {**sintetica, "variables": None})
    con_variables = completar_variables(sintetica)
    assert not cumple("transaccion", con_variables)


def test_transaccion_solo_con_lo_obligatorio():
    validar("transaccion", {"id_transaccion": "t-1", "origen": "original", "monto": 0})


def test_evaluacion_rechaza_campos_extra(ejemplos):
    ev = ejemplos["evaluacion"]
    assert not cumple("evaluacion", {**ev, "nivel": "sin_alerta"})
    assert not cumple("evaluacion", {**ev, "modelo": {**ev["modelo"], "extra": 1}})
    assert not cumple("evaluacion", {**ev, "reglas": [{**ev["reglas"][0], "extra": 1}]})


def test_evaluacion_admite_contribuciones(ejemplos):
    ev = copy.deepcopy(ejemplos["evaluacion"])
    ev["modelo"]["contribuciones"] = [{"variable": "V14", "peso": 0.12}]
    validar("evaluacion", ev)


def test_evaluacion_con_modelo_no_evaluable(ejemplos):
    ev = copy.deepcopy(ejemplos["evaluacion"])
    ev["modelo"] = {
        "evaluable": False,
        "puntuacion": None,
        "umbral_revision": None,
        "umbral_prioritaria": None,
        "anomalia": False,
        "anomalia_alta": False,
    }
    ev["versiones"]["modelo"] = None
    validar("evaluacion", ev)


def test_niveles_de_los_esquemas_son_los_de_la_configuracion():
    assert esquemas()["caso_nuevo"]["properties"]["nivel"]["enum"] == NIVELES
    assert esquemas()["caso"]["properties"]["nivel"]["enum"] == NIVELES


def test_caso_nuevo_valido():
    validar("caso_nuevo", _caso_nuevo())


def test_caso_con_alerta_exige_razones():
    assert not cumple("caso_nuevo", _caso_nuevo(razones=[]))
    validar("caso_nuevo", _caso_nuevo(nivel="sin_alerta", razones=[]))


def test_caso_de_error_puede_no_traer_la_transaccion():
    error = _caso_nuevo(
        id_transaccion=None,
        origen=None,
        monto=None,
        puntuacion=None,
        senales=None,
        nivel="error_evaluacion",
        razones=["Entrada invalida: monto debe ser mayor o igual que 0"],
    )
    validar("caso_nuevo", error)


def test_caso_sin_error_exige_la_transaccion():
    assert not cumple("caso_nuevo", _caso_nuevo(id_transaccion=None))
    assert not cumple("caso_nuevo", _caso_nuevo(monto=None))


def test_caso_nuevo_no_trae_campos_que_pone_la_api():
    for campo in ("id_caso", "estado", "decision_final", "revision"):
        assert not cumple("caso_nuevo", _caso_nuevo(**{campo: "x"}))


def test_caso_completo_y_coherente():
    caso = {
        **_caso_nuevo(),
        "id_caso": "c-0123456789ab",
        "fecha_procesamiento": "2026-11-17T10:00:00Z",
        "estado": "pendiente_revision",
        "decision_final": "pendiente",
        "revision": None,
    }
    validar("caso", caso)
    assert not cumple("caso", {**caso, "estado": "cerrado"})
    revisado = {
        **caso,
        "estado": "revisado",
        "decision_final": "sospecha_confirmada",
        "revision": {"revisor": "ana", "comentario": "", "fecha": "2026-11-17T10:05:00Z"},
    }
    validar("caso", revisado)
    assert not cumple("caso", {**revisado, "revision": None})
    cerrado = {**caso, "nivel": "sin_alerta", "estado": "cerrado", "decision_final": "sin_alerta"}
    validar("caso", cerrado)


def test_revision():
    validar("revision", {"decision": "sospecha_descartada", "revisor": "ana", "comentario": ""})
    validar("revision", {"decision": "sospecha_confirmada", "revisor": "ana"})
    assert not cumple("revision", {"decision": "fraude_confirmado", "revisor": "ana"})
    assert not cumple("revision", {"decision": "sospecha_confirmada", "revisor": ""})


def test_error():
    validar(
        "error",
        {
            "id_transaccion": None,
            "error": {"tipo": "entrada_invalida", "mensaje": "m", "detalles": []},
        },
    )
    assert not cumple(
        "error", {"id_transaccion": None, "error": {"tipo": "otro", "mensaje": "m", "detalles": []}}
    )


def test_error_flujo_de_caso_no_registrado_exige_el_caso():
    from contratos import cumple

    error = {"tipo": "caso_no_registrado", "mensaje": "POST /casos no respondio", "detalles": []}
    assert cumple("error_flujo", {"error": error, "caso": _caso_nuevo()})
    assert not cumple("error_flujo", {"error": error})
    assert not cumple("error_flujo", {"error": {**error, "tipo": "otro"}, "caso": _caso_nuevo()})


def test_error_flujo_de_revision_no_registrada():
    from contratos import cumple

    error = {"tipo": "revision_no_registrada", "mensaje": "sin respuesta", "detalles": []}
    assert cumple("error_flujo", {"id_transaccion": None, "error": error})


# --- Explicacion con LLM (fase 7, ADR 0016) ---------------------------------------------

RESPALDO = {
    "motivo": "comprobacion_fallida",
    "detalle": "El texto no paso la comprobacion: nivel_no_mencionado",
    "modelo": "qwen3.5:4b-q4_K_M",
    "duracion_ms": 812.5,
    "texto_descartado": "Texto del modelo",
}


def test_explicacion_del_caso_admite_respaldo_y_comprobacion():
    llm = {
        "texto": "Alerta prioritaria: se activo MONTO_ALTO.",
        "origen": "llm",
        "modelo": "qwen3.5:4b-q4_K_M",
        "duracion_ms": 640.0,
        "respaldo": None,
        "comprobacion": {"valida": True, "fallos": []},
    }
    validar("caso_nuevo", _caso_nuevo(explicacion=llm))
    plantilla = {
        "texto": "El sistema senala esta transaccion para revision prioritaria.",
        "origen": "plantilla",
        "modelo": None,
        "duracion_ms": None,
        "respaldo": RESPALDO,
        "comprobacion": {"valida": False, "fallos": ["nivel_no_mencionado"]},
    }
    validar("caso_nuevo", _caso_nuevo(explicacion=plantilla))
    n8n = {**plantilla, "respaldo": {"motivo": "api_sin_respuesta", "detalle": "ECONNREFUSED"}}
    validar("caso_nuevo", _caso_nuevo(explicacion=n8n))
    otro = {**plantilla, "respaldo": {**RESPALDO, "motivo": "inventado"}}
    assert not cumple("caso_nuevo", _caso_nuevo(explicacion=otro))


def test_redaccion_del_modelo_y_de_respaldo():
    validar(
        "redaccion",
        {
            "origen": "llm",
            "texto": "Alerta prioritaria: se activo MONTO_ALTO.",
            "modelo": "qwen3.5:4b-q4_K_M",
            "duracion_ms": 640.0,
            "respaldo": None,
            "comprobacion": {"valida": True, "fallos": []},
        },
    )
    respaldo = {
        "origen": "plantilla",
        "texto": None,
        "modelo": None,
        "duracion_ms": None,
        "respaldo": RESPALDO,
        "comprobacion": {"valida": False, "fallos": ["nivel_no_mencionado"]},
    }
    validar("redaccion", respaldo)
    # Un texto del modelo que no paso la comprobacion nunca sale como `llm`.
    assert not cumple("redaccion", {**respaldo, "origen": "llm", "texto": "x", "respaldo": None})
    # La plantilla siempre dice por que.
    assert not cumple("redaccion", {**respaldo, "respaldo": None})
    assert not cumple("redaccion", {**respaldo, "texto": "texto"})


def test_redaccion_pedida(ejemplos):
    validar(
        "redaccion_pedida",
        {"id_transaccion": "t-1", "nivel": "alerta_prioritaria", "senales": ejemplos["evaluacion"]},
    )
    error = {"id_transaccion": None, "nivel": "error_evaluacion", "senales": None}
    validar("redaccion_pedida", error)
    assert not cumple("redaccion_pedida", {**error, "nivel": "alerta_prioritaria"})
    assert not cumple(
        "redaccion_pedida",
        {"nivel": "alerta_prioritaria", "senales": ejemplos["evaluacion"], "Class": 1},
    )
