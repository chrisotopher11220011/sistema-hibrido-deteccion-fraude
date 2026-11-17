import numpy as np
import pytest
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from fraude import metricas


def caso(semilla=0, n=400, fraudes=25):
    rng = np.random.default_rng(semilla)
    y = np.zeros(n, int)
    y[rng.choice(n, fraudes, replace=False)] = 1
    puntuacion = np.round(rng.uniform(size=n) + 0.6 * y, 2)  # con empates
    alerta = puntuacion > 0.9
    pesos = rng.integers(0, 4, size=n)
    pesos[np.flatnonzero(y)[0]] = 1  # al menos un fraude con peso
    return y, puntuacion, alerta, pesos


def test_binarias_coincide_con_sklearn_sobre_filas_repetidas():
    y, _, alerta, pesos = caso()
    r = metricas.binarias(y, alerta, pesos)
    yr, ar = np.repeat(y, pesos), np.repeat(alerta, pesos)
    assert r["precision"] == pytest.approx(precision_score(yr, ar))
    assert r["exhaustividad"] == pytest.approx(recall_score(yr, ar))
    assert r["f1"] == pytest.approx(f1_score(yr, ar))
    assert r["tp"] + r["fp"] + r["fn"] + r["tn"] == pesos.sum()
    assert r["alertas"] == r["tp"] + r["fp"]


def test_de_puntuacion_coincide_con_sklearn_sobre_filas_repetidas():
    y, p, _, pesos = caso(1)
    r = metricas.de_puntuacion(y, p, k=50, pesos=pesos)
    yr, pr = np.repeat(y, pesos), np.repeat(p, pesos)
    assert r["precision_media"] == pytest.approx(average_precision_score(yr, pr))
    assert r["auc_roc"] == pytest.approx(roc_auc_score(yr, pr))


def test_sin_pesos_coincide_con_sklearn():
    y, p, alerta, _ = caso(2)
    assert metricas.de_puntuacion(y, p, 10)["precision_media"] == pytest.approx(
        average_precision_score(y, p)
    )
    assert metricas.binarias(y, alerta)["f1"] == pytest.approx(f1_score(y, alerta))


def test_precision_en_los_k_primeros_a_mano():
    y = np.array([1, 0, 1, 0, 0, 1])
    p = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.1])
    assert metricas.de_puntuacion(y, p, k=3)["precision_k"] == pytest.approx(2 / 3)
    # Con pesos: la primera fila cuenta dos veces y llena 2 de los 3 puestos.
    pesos = np.array([2, 1, 1, 1, 1, 1])
    assert metricas.de_puntuacion(y, p, k=3, pesos=pesos)["precision_k"] == pytest.approx(2 / 3)
    pesos = np.array([3, 1, 1, 1, 1, 1])
    assert metricas.de_puntuacion(y, p, k=3, pesos=pesos)["precision_k"] == pytest.approx(1.0)


def test_sin_alertas_la_precision_queda_indefinida():
    y = np.array([1, 0, 0])
    r = metricas.binarias(y, np.zeros(3, bool))
    assert r["precision"] is None
    assert r["exhaustividad"] == 0.0
    assert r["f1"] == 0.0


def test_remuestreos_conservan_cada_clase():
    y = np.array([1] * 7 + [0] * 93)
    lista = list(metricas.remuestreos(y, 20, semilla=5))
    assert len(lista) == 20
    for pesos in lista:
        assert pesos.sum() == 100
        assert pesos[y == 1].sum() == 7
    assert not np.array_equal(lista[0], lista[1])
    again = list(metricas.remuestreos(y, 20, semilla=5))
    assert all(np.array_equal(a, b) for a, b in zip(lista, again, strict=True))


def test_intervalo_ignora_los_indefinidos_y_los_cuenta():
    valores = [None, *np.linspace(0, 1, 101).tolist()]
    r = metricas.intervalo(valores, 0.95)
    assert r["indefinidos"] == 1
    assert r["inferior"] == pytest.approx(0.025)
    assert r["superior"] == pytest.approx(0.975)
    assert metricas.intervalo([None, None], 0.95) == {
        "inferior": None,
        "superior": None,
        "indefinidos": 2,
    }
