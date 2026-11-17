"""Particion estratificada con semilla fija (docs/spec.md, seccion 9; ADR 0003).

70 % desarrollo y 30 % prueba; el desarrollo se divide en 80 % ajuste y 20 % validacion.
Los indices se guardan antes de cualquier ajuste y no dependen de nada mas que de la clase.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

PARTES = ("ajuste", "validacion", "prueba")


def crear(clase: np.ndarray, semilla: int, prueba: float, validacion: float) -> np.ndarray:
    """Devuelve, para cada fila, el nombre de su parte."""
    indices = np.arange(len(clase))
    desarrollo, en_prueba = train_test_split(
        indices, test_size=prueba, stratify=clase, random_state=semilla
    )
    en_ajuste, en_validacion = train_test_split(
        desarrollo, test_size=validacion, stratify=clase[desarrollo], random_state=semilla
    )
    partes = np.empty(len(clase), dtype=object)
    partes[en_ajuste] = "ajuste"
    partes[en_validacion] = "validacion"
    partes[en_prueba] = "prueba"
    return partes.astype(str)


def _huella(partes: np.ndarray) -> str:
    return hashlib.sha256("\n".join(partes.tolist()).encode()).hexdigest()


def guardar(partes: np.ndarray, carpeta: Path, meta: dict) -> dict:
    """Guarda un archivo de indices por parte y `particion.json`. Devuelve los metadatos."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    for parte in PARTES:
        np.savetxt(carpeta / f"{parte}.txt", np.flatnonzero(partes == parte), fmt="%d")
    completo = {
        **meta,
        "filas_totales": int(len(partes)),
        "filas": {parte: int((partes == parte).sum()) for parte in PARTES},
        "huella_indices": _huella(partes),
    }
    (carpeta / "particion.json").write_text(
        json.dumps(completo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return completo


def cargar(carpeta: Path) -> np.ndarray:
    """Reconstruye la etiqueta de parte de cada fila a partir de los indices guardados."""
    carpeta = Path(carpeta)
    meta = json.loads((carpeta / "particion.json").read_text(encoding="utf-8"))
    partes = np.empty(meta["filas_totales"], dtype=object)
    for parte in PARTES:
        indices = np.loadtxt(carpeta / f"{parte}.txt", dtype=np.int64, ndmin=1)
        partes[indices] = parte
    return partes.astype(str)
