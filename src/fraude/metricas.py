"""Metricas para clases desbalanceadas e incertidumbre (docs/spec.md, seccion 15; ADR 0011).

Todas aceptan `pesos`: cuantas veces cuenta cada fila. Asi un remuestreo bootstrap es solo un
vector de pesos y no hace falta copiar los datos mil veces. Con pesos enteros, cada funcion da
lo mismo que scikit-learn sobre las filas repetidas (lo comprueban las pruebas).

Una metrica que no puede calcularse (precision sin alertas, exhaustividad sin fraudes) vale
`None`: no se inventa un cero.
"""

from collections.abc import Iterator, Sequence

import numpy as np


def _pesos(n: int, pesos: np.ndarray | None) -> np.ndarray:
    return np.ones(n, dtype=np.float64) if pesos is None else np.asarray(pesos, np.float64)


def _division(a: float, b: float) -> float | None:
    return float(a / b) if b > 0 else None


def binarias(y: np.ndarray, alerta: np.ndarray, pesos: np.ndarray | None = None) -> dict:
    """Matriz de confusion, precision, exhaustividad y F1 de una salida si/no."""
    y, alerta = np.asarray(y).astype(bool), np.asarray(alerta).astype(bool)
    w = _pesos(len(y), pesos)
    tp = float(w[y & alerta].sum())
    fp = float(w[~y & alerta].sum())
    fn = float(w[y & ~alerta].sum())
    tn = float(w[~y & ~alerta].sum())
    return {
        "tp": int(round(tp)),
        "fp": int(round(fp)),
        "fn": int(round(fn)),
        "tn": int(round(tn)),
        "alertas": int(round(tp + fp)),
        "precision": _division(tp, tp + fp),
        "exhaustividad": _division(tp, tp + fn),
        "f1": _division(2 * tp, 2 * tp + fp + fn),
    }


def ordenar(puntuacion: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Orden de mayor a menor (estable) y ultima posicion de cada grupo de valores iguales."""
    puntuacion = np.asarray(puntuacion, dtype=np.float64)
    orden = np.argsort(-puntuacion, kind="stable")
    ordenada = puntuacion[orden]
    fines = np.r_[np.flatnonzero(np.diff(ordenada) != 0), len(ordenada) - 1]
    return orden, fines


def de_puntuacion(
    y: np.ndarray,
    puntuacion: np.ndarray,
    k: int,
    pesos: np.ndarray | None = None,
    orden: tuple[np.ndarray, np.ndarray] | None = None,
) -> dict:
    """Precision media, precision en los `k` primeros y area bajo la curva ROC."""
    y = np.asarray(y).astype(np.float64)
    w = _pesos(len(y), pesos)
    indices, fines = orden if orden is not None else ordenar(puntuacion)
    ys, ws = y[indices], w[indices]
    tps_fila = np.cumsum(ws * ys)
    fps_fila = np.cumsum(ws * (1 - ys))
    tps, fps = tps_fila[fines], fps_fila[fines]
    positivos, negativos = tps[-1], fps[-1]

    precision_media = None
    if positivos > 0:
        with np.errstate(divide="ignore", invalid="ignore"):
            precision = np.where(tps + fps > 0, tps / (tps + fps), 0.0)
        exhaustividad = tps / positivos
        precision_media = float(np.sum(np.diff(exhaustividad, prepend=0.0) * precision))

    auc = None
    if positivos > 0 and negativos > 0:
        tpr = np.r_[0.0, tps / positivos]
        fpr = np.r_[0.0, fps / negativos]
        auc = float(np.trapezoid(tpr, fpr))

    acumulado = np.cumsum(ws)
    cupo = min(float(k), float(acumulado[-1]))
    precision_k = None
    if cupo > 0:
        anterior = np.r_[0.0, acumulado[:-1]]
        dentro = np.clip(cupo - anterior, 0.0, ws)  # parte de cada fila que cabe en el cupo
        precision_k = float(np.sum(dentro * ys) / cupo)
    return {"precision_media": precision_media, "precision_k": precision_k, "auc_roc": auc}


def remuestreos(y: np.ndarray, n: int, semilla: int) -> Iterator[np.ndarray]:
    """`n` vectores de pesos de un bootstrap estratificado: cada clase conserva su tamano."""
    y = np.asarray(y).astype(bool)
    rng = np.random.default_rng(semilla)
    clases = [np.flatnonzero(y), np.flatnonzero(~y)]
    for _ in range(n):
        pesos = np.zeros(len(y), dtype=np.int64)
        for indices in clases:
            if len(indices):
                pesos += np.bincount(
                    rng.choice(indices, size=len(indices), replace=True), minlength=len(y)
                )
        yield pesos


def intervalo(valores: Sequence[float | None], confianza: float) -> dict:
    """Intervalo por percentiles; los valores indefinidos se cuentan y se excluyen."""
    definidos = np.array([v for v in valores if v is not None], dtype=np.float64)
    indefinidos = len(valores) - len(definidos)
    if len(definidos) == 0:
        return {"inferior": None, "superior": None, "indefinidos": indefinidos}
    alfa = (1 - confianza) / 2 * 100
    inferior, superior = np.percentile(definidos, [alfa, 100 - alfa])
    return {"inferior": float(inferior), "superior": float(superior), "indefinidos": indefinidos}
