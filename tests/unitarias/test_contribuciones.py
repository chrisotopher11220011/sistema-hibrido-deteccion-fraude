import numpy as np
import pytest

from fraude import contribuciones, modelo

VARIABLES = ["V1", "V2", "V3", "V4", "V5"]
PARAMS = {"n_estimators": 60, "max_samples": 256, "max_features": 1.0, "bootstrap": False}


@pytest.fixture(scope="module")
def bosque():
    X = np.random.default_rng(1).normal(size=(3000, 5))
    return modelo.entrenar_bosque(X, PARAMS, 42)


def test_aditividad_con_la_version_instalada(bosque):
    # Si una version de scikit-learn o de SHAP rompe la explicacion, esta prueba lo dice.
    X = np.random.default_rng(2).normal(size=(200, 5))
    assert contribuciones.error_aditividad(bosque, X) < 1e-9


def test_la_variable_desplazada_encabeza_la_lista(bosque):
    punto = np.zeros((1, 5))
    punto[0, 2] = 7.0
    lista = contribuciones.contribuciones(bosque, punto, VARIABLES, k=3)[0]
    assert lista[0]["variable"] == "V3"
    assert lista[0]["peso"] > 0
    assert [c["peso"] for c in lista] == sorted((c["peso"] for c in lista), reverse=True)


def test_k_limita_la_longitud_y_sin_filas_devuelve_vacio(bosque):
    X = np.random.default_rng(3).normal(size=(4, 5))
    listas = contribuciones.contribuciones(bosque, X, VARIABLES, k=2)
    assert len(listas) == 4 and all(len(lista) == 2 for lista in listas)
    assert contribuciones.contribuciones(bosque, np.empty((0, 5)), VARIABLES, k=2) == []


def test_el_metodo_queda_descrito():
    assert "SHAP" in contribuciones.METODO
