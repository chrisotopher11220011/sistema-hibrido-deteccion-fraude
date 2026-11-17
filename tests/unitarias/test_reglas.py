"""Reglas deterministas (docs/spec.md, secciones 8.3 y 10)."""

import copy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fraude.configuracion import cargar
from fraude.reglas import evaluar_reglas, version

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = cargar(RAIZ, "reglas")


def tx(monto, origen="sintetico", habitual=None, actual=None):
    datos = {"id_transaccion": "t-1", "origen": origen, "monto": monto}
    if habitual:
        datos["ubicacion"] = {"pais_habitual": habitual, "pais_transaccion": actual}
    return datos


def por_id(resultado):
    return {r["id"]: r for r in resultado}


def test_cada_resultado_tiene_la_forma_del_contrato():
    for r in evaluar_reglas(tx(10), CONFIG):
        assert set(r) == {"id", "evaluable", "activada", "alto_riesgo", "razon"}
        assert isinstance(r["razon"], str) and r["razon"]


def test_evalua_las_dos_reglas_de_la_especificacion_en_orden():
    ids = [r["id"] for r in evaluar_reglas(tx(10), CONFIG)]
    assert ids == ["MONTO_ALTO", "MONTO_ALTO_UBICACION_INUSUAL"]


def test_monto_alto_se_activa_con_la_razon_del_contrato():
    r = por_id(evaluar_reglas(tx(1250, origen="original"), CONFIG))["MONTO_ALTO"]
    assert r == {
        "id": "MONTO_ALTO",
        "evaluable": True,
        "activada": True,
        "alto_riesgo": False,
        "razon": "El monto 1250.00 supera el umbral 1000.00",
    }


def test_monto_igual_al_umbral_no_activa():
    r = por_id(evaluar_reglas(tx(1000), CONFIG))["MONTO_ALTO"]
    assert r["evaluable"] and not r["activada"]
    assert "no supera" in r["razon"]


def test_ubicacion_inusual_con_monto_alto_es_alto_riesgo():
    r = por_id(evaluar_reglas(tx(1500, habitual="EC", actual="US"), CONFIG))
    regla = r["MONTO_ALTO_UBICACION_INUSUAL"]
    assert regla["evaluable"] and regla["activada"] and regla["alto_riesgo"]
    assert "EC" in regla["razon"] and "US" in regla["razon"] and "1500.00" in regla["razon"]


def test_ubicacion_igual_no_activa():
    regla = por_id(evaluar_reglas(tx(1500, habitual="EC", actual="EC"), CONFIG))
    assert not regla["MONTO_ALTO_UBICACION_INUSUAL"]["activada"]
    assert regla["MONTO_ALTO"]["activada"]


def test_pais_distinto_con_monto_bajo_no_activa():
    regla = por_id(evaluar_reglas(tx(50, habitual="EC", actual="US"), CONFIG))
    assert regla["MONTO_ALTO_UBICACION_INUSUAL"]["evaluable"]
    assert not regla["MONTO_ALTO_UBICACION_INUSUAL"]["activada"]


def test_sin_ubicacion_la_regla_no_es_evaluable_y_no_se_activa():
    regla = por_id(evaluar_reglas(tx(5000), CONFIG))["MONTO_ALTO_UBICACION_INUSUAL"]
    assert regla["evaluable"] is False and regla["activada"] is False
    assert "no evaluable" in regla["razon"].lower()


def test_con_datos_originales_la_regla_de_ubicacion_no_es_evaluable():
    """El conjunto original no trae ubicacion: la regla solo vale para sinteticos (ADR 0006)."""
    regla = por_id(evaluar_reglas(tx(5000, "original", "EC", "US"), CONFIG))
    assert regla["MONTO_ALTO_UBICACION_INUSUAL"]["evaluable"] is False
    assert regla["MONTO_ALTO_UBICACION_INUSUAL"]["activada"] is False


def test_el_umbral_sale_de_la_configuracion():
    config = copy.deepcopy(CONFIG)
    config["reglas"]["MONTO_ALTO"]["umbral_monto"] = 100
    r = por_id(evaluar_reglas(tx(150), config))["MONTO_ALTO"]
    assert r["activada"] and r["razon"] == "El monto 150.00 supera el umbral 100.00"


def test_alto_riesgo_sale_de_la_configuracion():
    config = copy.deepcopy(CONFIG)
    config["reglas"]["MONTO_ALTO"]["alto_riesgo"] = True
    assert por_id(evaluar_reglas(tx(1), config))["MONTO_ALTO"]["alto_riesgo"] is True


def test_rechaza_una_transaccion_invalida():
    with pytest.raises(ValidationError):
        evaluar_reglas({"id_transaccion": "x", "origen": "original", "monto": -3}, CONFIG)


def test_configuracion_sin_una_regla_conocida_falla_con_mensaje():
    config = copy.deepcopy(CONFIG)
    del config["reglas"]["MONTO_ALTO"]
    with pytest.raises(KeyError, match="MONTO_ALTO"):
        evaluar_reglas(tx(1), config)


def test_version_de_las_reglas():
    assert version(CONFIG) == "0.2.0"
