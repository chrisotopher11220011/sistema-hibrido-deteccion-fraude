"""Isolation Forest y eleccion de umbrales (docs/spec.md, seccion 11; ADR 0008).

- Se entrena sin etiquetas, solo con la parte de ajuste (lo garantiza `entrenar.py`).
- Puntuacion = `-score_samples`: la puntuacion de anomalia de Liu et al., en (0, 1].
  Un valor mayor significa mas anomalo.
- Umbrales elegidos en validacion: `umbral_revision` maximiza F1 y `umbral_prioritaria`
  maximiza F0,5 sin bajar de `umbral_revision`. Entre umbrales empatados se toma el mayor,
  que produce menos alertas.

La puntuacion prioriza la revision humana; no prueba el fraude.
"""

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_recall_curve

ARCHIVO_MODELO = "modelo.joblib"
ARCHIVO_META = "modelo.json"


class ErrorModelo(Exception):
    """Fallo con un mensaje que dice que hacer."""


def entrenar_bosque(X: np.ndarray, params: dict, semilla: int) -> IsolationForest:
    """Ajusta un Isolation Forest con los parametros de `config/modelo.yaml`."""
    bosque = IsolationForest(**params, random_state=semilla)
    return bosque.fit(np.asarray(X, dtype=np.float64))


def puntuar(bosque: IsolationForest, X: np.ndarray) -> np.ndarray:
    """Puntuacion de anomalia en (0, 1]: mayor = mas anomalo."""
    return -bosque.score_samples(np.asarray(X, dtype=np.float64))


def umbral_por_fbeta(
    y: np.ndarray, puntuacion: np.ndarray, beta: float, minimo: float | None = None
) -> tuple[float, float]:
    """Umbral (alerta si `puntuacion >= umbral`) que maximiza F-beta, y ese F-beta."""
    y = np.asarray(y)
    if y.sum() == 0:
        raise ErrorModelo(
            "La parte de validacion no tiene fraudes: no se pueden elegir umbrales. "
            "Revisa la particion (paso preparar)."
        )
    precision, exhaustividad, umbrales = precision_recall_curve(y, puntuacion)
    precision, exhaustividad = precision[:-1], exhaustividad[:-1]
    b2 = beta**2
    with np.errstate(divide="ignore", invalid="ignore"):
        f = (1 + b2) * precision * exhaustividad / (b2 * precision + exhaustividad)
    f = np.nan_to_num(f, nan=0.0)
    if minimo is not None:
        f = np.where(umbrales >= minimo, f, -1.0)
    mejor = f.max()
    candidatos = np.flatnonzero(np.isclose(f, mejor, rtol=0, atol=1e-12))
    i = candidatos[np.argmax(umbrales[candidatos])]
    return float(umbrales[i]), float(f[i])


def elegir_umbrales(y: np.ndarray, puntuacion: np.ndarray) -> dict:
    """Los dos umbrales del ADR 0008, elegidos con las etiquetas de validacion."""
    revision, f1 = umbral_por_fbeta(y, puntuacion, 1.0)
    prioritaria, f05 = umbral_por_fbeta(y, puntuacion, 0.5, minimo=revision)
    return {
        "umbral_revision": revision,
        "umbral_prioritaria": prioritaria,
        "f1_validacion": f1,
        "f05_validacion": f05,
    }


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def guardar_artefacto(carpeta: Path, bosque: IsolationForest, meta: dict) -> dict:
    """Guarda el modelo y `modelo.json`. Devuelve los metadatos con la huella del artefacto."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / ARCHIVO_MODELO
    joblib.dump(bosque, ruta)
    completo = {**meta, "huella_artefacto": _sha256(ruta)}
    (carpeta / ARCHIVO_META).write_text(
        json.dumps(completo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return completo


def cargar_artefacto(carpeta: Path) -> tuple[IsolationForest, dict]:
    """Carga el modelo y sus metadatos, comprobando que el archivo no cambio."""
    carpeta = Path(carpeta)
    ruta, ruta_meta = carpeta / ARCHIVO_MODELO, carpeta / ARCHIVO_META
    if not ruta.is_file() or not ruta_meta.is_file():
        raise ErrorModelo("No hay modelo entrenado. Ejecuta antes el paso entrenar.")
    meta = json.loads(ruta_meta.read_text(encoding="utf-8"))
    if _sha256(ruta) != meta.get("huella_artefacto"):
        raise ErrorModelo("El archivo del modelo no coincide con su modelo.json: repite entrenar.")
    return joblib.load(ruta), meta
