"""Muestra para pruebas (docs/spec.md, seccion 9).

Datos con la misma forma que el conjunto real (columnas, tipos, desbalance) para las pruebas
N1 y N2. Las distribuciones son inventadas: la muestra NO representa el fraude real y nada
de lo que se calcule con ella es una metrica reportable.
"""

import numpy as np
import pandas as pd

from fraude.transaccion import VARIABLES

COLUMNAS = ("Time", *VARIABLES, "Amount", "Class")
SEGUNDOS_EN_DOS_DIAS = 172_800


def generar(filas: int, fraudes: int, semilla: int, con_time: bool = True) -> pd.DataFrame:
    """Genera `filas` transacciones, exactamente `fraudes` de ellas con `Class = 1`."""
    if not 0 <= fraudes <= filas:
        raise ValueError("fraudes debe estar entre 0 y filas")
    rng = np.random.default_rng(semilla)
    clase = np.zeros(filas, dtype=np.int64)
    clase[rng.choice(filas, size=fraudes, replace=False)] = 1

    variables = rng.normal(0.0, 1.0, size=(filas, len(VARIABLES)))
    # Los fraudes se desplazan en unas pocas variables para que el modelo tenga algo que
    # separar en las pruebas. Es un artificio de la muestra, no un hallazgo sobre el fraude.
    desplazamiento = np.zeros(len(VARIABLES))
    desplazamiento[[2, 9, 11, 13, 16]] = [-3.0, -2.5, -3.0, -4.0, -2.5]
    variables[clase == 1] += desplazamiento + rng.normal(0, 1.5, size=(fraudes, len(VARIABLES)))

    monto = rng.lognormal(mean=3.0, sigma=1.4, size=filas)
    monto = np.round(np.clip(monto, 0.0, 25_000.0), 2)
    tiempo = np.sort(rng.integers(0, SEGUNDOS_EN_DOS_DIAS, size=filas)).astype(np.float64)

    df = pd.DataFrame(variables, columns=list(VARIABLES))
    df.insert(0, "Time", tiempo)
    df["Amount"] = monto
    df["Class"] = clase
    if not con_time:
        df = df.drop(columns="Time")
    return df
