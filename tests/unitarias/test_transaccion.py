"""Forma de la transaccion (docs/spec.md, seccion 8.2)."""

import math

import pytest
from pydantic import ValidationError

from fraude.configuracion import cargar
from fraude.transaccion import VARIABLES, Transaccion

EJEMPLO = {
    "id_transaccion": "t-000457",
    "origen": "original",
    "monto": 1250.0,
    "variables": {v: 0.0 for v in [f"V{i}" for i in range(1, 29)]},
    "ubicacion": {"pais_habitual": "EC", "pais_transaccion": "US"},
}


def test_variables_son_v1_a_v28():
    assert tuple(f"V{i}" for i in range(1, 29)) == VARIABLES


def test_acepta_el_ejemplo_del_contrato():
    t = Transaccion.model_validate(EJEMPLO)
    assert t.monto == 1250.0
    assert t.ubicacion.pais_transaccion == "US"


def test_variables_y_ubicacion_son_opcionales():
    t = Transaccion.model_validate({"id_transaccion": "t-1", "origen": "original", "monto": 5})
    assert t.variables is None and t.ubicacion is None


def test_rechaza_la_etiqueta_real():
    with pytest.raises(ValidationError):
        Transaccion.model_validate({**EJEMPLO, "Class": 1})


@pytest.mark.parametrize("monto", [-1.0, math.inf, math.nan])
def test_rechaza_montos_imposibles(monto):
    with pytest.raises(ValidationError):
        Transaccion.model_validate({**EJEMPLO, "monto": monto})


def test_rechaza_origen_desconocido():
    with pytest.raises(ValidationError):
        Transaccion.model_validate({**EJEMPLO, "origen": "inventado"})


def test_rechaza_sintetico_con_variables():
    with pytest.raises(ValidationError, match="sintetic"):
        Transaccion.model_validate({**EJEMPLO, "origen": "sintetico"})


def test_rechaza_variables_incompletas():
    variables = dict(EJEMPLO["variables"])
    del variables["V28"]
    with pytest.raises(ValidationError):
        Transaccion.model_validate({**EJEMPLO, "variables": variables})


def test_rechaza_variables_de_mas():
    with pytest.raises(ValidationError):
        Transaccion.model_validate({**EJEMPLO, "variables": {**EJEMPLO["variables"], "Time": 3}})


def test_rechaza_pais_mal_escrito():
    with pytest.raises(ValidationError):
        Transaccion.model_validate(
            {**EJEMPLO, "ubicacion": {"pais_habitual": "Ecuador", "pais_transaccion": "US"}}
        )


def test_configuracion_de_datos(tmp_path):
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    modelo = cargar(raiz, "modelo")
    assert modelo["datos"]["filas_esperadas"] == 284807
    assert modelo["datos"]["fraudes_esperados"] == 492
    assert modelo["datos"]["md5_openml"] == "178bcf9bb1f31a3dfe12d0e577884add"
    assert modelo["particion"]["prueba"] == 0.30
    assert modelo["particion"]["validacion"] == 0.20
    with pytest.raises(FileNotFoundError):
        cargar(tmp_path, "modelo")
