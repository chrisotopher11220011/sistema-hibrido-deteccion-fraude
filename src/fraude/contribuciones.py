"""Contribucion por variable de cada puntuacion (docs/spec.md, seccion 11; ADR 0012).

Metodo: SHAP para arboles (`shap.TreeExplainer`), que admite `IsolationForest` de
scikit-learn y explica la profundidad media de aislamiento de cada fila. Una profundidad
menor es mas anomala, asi que el peso de una variable es el valor SHAP con el signo
cambiado: positivo empuja hacia «mas anomalo».

Es una explicacion tecnica: las variables son componentes anonimos (PCA), asi que dice
cuales pesaron, no por que.
"""

import numpy as np
import shap
from sklearn.ensemble import IsolationForest
from sklearn.ensemble._iforest import _average_path_length

METODO = (
    f"SHAP para arboles (shap.TreeExplainer {shap.__version__}) sobre la profundidad media de "
    "aislamiento; peso = -valor SHAP (positivo empuja hacia mas anomalo)"
)


class Explicador:
    """Explicador SHAP de un bosque, creado una vez y reutilizado (la API lo guarda)."""

    def __init__(self, bosque: IsolationForest):
        self._explicador = shap.TreeExplainer(bosque)

    def valores(self, X: np.ndarray) -> tuple[np.ndarray, float]:
        valores = self._explicador.shap_values(np.asarray(X, dtype=np.float64))
        base = float(np.ravel(self._explicador.expected_value)[0])
        return np.asarray(valores, dtype=np.float64), base

    def contribuciones(self, X: np.ndarray, variables: list[str], k: int) -> list[list[dict]]:
        """Para cada fila, las `k` variables con mayor peso hacia la anomalia."""
        X = np.asarray(X, dtype=np.float64)
        if len(X) == 0:
            return []
        pesos = -self.valores(X)[0]
        orden = np.argsort(-pesos, axis=1, kind="stable")[:, :k]
        return [
            [{"variable": variables[j], "peso": round(float(fila[j]), 6)} for j in indices]
            for fila, indices in zip(pesos, orden, strict=True)
        ]


def _valores(bosque: IsolationForest, X: np.ndarray) -> tuple[np.ndarray, float]:
    return Explicador(bosque).valores(X)


def contribuciones(
    bosque: IsolationForest, X: np.ndarray, variables: list[str], k: int
) -> list[list[dict]]:
    """Para cada fila, las `k` variables con mayor peso hacia la anomalia."""
    return Explicador(bosque).contribuciones(X, variables, k)


def error_aditividad(bosque: IsolationForest, X: np.ndarray) -> float:
    """Mayor diferencia entre la puntuacion del modelo y la reconstruida desde SHAP."""
    valores, base = _valores(bosque, X)
    profundidad = base + valores.sum(axis=1)
    c = _average_path_length(np.array([bosque.max_samples_]))[0]
    reconstruida = 2.0 ** (-profundidad / c)
    return float(np.abs(reconstruida + bosque.score_samples(np.asarray(X, np.float64))).max())
