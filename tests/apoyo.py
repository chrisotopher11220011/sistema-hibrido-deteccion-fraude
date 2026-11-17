"""Apoyo comun a las pruebas unitarias y de contrato de la API (fase 4).

`raiz_api` es una raiz de trabajo con la configuracion del repositorio. `entrenar_modelo` deja
un Isolation Forest pequeno, entrenado con datos inventados, donde lo deja el paso `entrenar`.
No representa el fraude real: solo sirve para probar la carga y la forma de las respuestas.
"""

from pathlib import Path

import numpy as np
import yaml

from fraude import modelo
from fraude.entrenar import carpeta_modelo

RAIZ_REPO = Path(__file__).resolve().parents[1]
VARIABLES = yaml.safe_load((RAIZ_REPO / "config" / "modelo.yaml").read_text())["variables"]


def fila(valor: float = 0.0) -> dict[str, float]:
    """Una fila con todas las variables del modelo al mismo valor."""
    return {v: float(valor) for v in VARIABLES}


def variables_transaccion(valor: float = 0.0) -> dict[str, float]:
    """`variables` de una transaccion (V1 a V28) al mismo valor."""
    return {f"V{i}": float(valor) for i in range(1, 29)}


def entrenar(
    raiz: Path,
    muestra: bool = True,
    version: str = "v-prueba",
    semilla: int = 0,
    **cambios,
) -> dict:
    generador = np.random.default_rng(semilla)
    X = generador.normal(size=(400, len(VARIABLES)))
    params = {"n_estimators": 20, "max_samples": 64}
    bosque = modelo.entrenar_bosque(X, params, semilla)
    puntuaciones = modelo.puntuar(bosque, X)
    meta = {
        "estado": "ok",
        "fuente": "muestra" if muestra else "real",
        "reportable": not muestra,
        "variables": list(VARIABLES),
        "version": version,
        "umbrales": {
            "umbral_revision": float(np.quantile(puntuaciones, 0.95)),
            "umbral_prioritaria": float(np.quantile(puntuaciones, 0.995)),
        },
        **cambios,
    }
    return modelo.guardar_artefacto(carpeta_modelo(raiz, muestra), bosque, meta)
