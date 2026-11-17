"""Lectura, descarga e integridad del conjunto (docs/spec.md, seccion 9; ADR 0002).

Acepta el ARFF de OpenML y el CSV de Kaggle. `Time` es opcional: OpenML la marca como
identificador de fila y algunas herramientas la omiten. El modelo no depende de ella.
"""

import hashlib
import io
import re
import urllib.request
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from fraude.transaccion import VARIABLES

OBLIGATORIAS = (*VARIABLES, "Amount", "Class")
ORDEN = ("Time", *OBLIGATORIAS)
ALTERNATIVA_MANUAL = (
    "Alternativa manual: descarga creditcard.csv de Kaggle "
    "(https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud) y dejalo en "
    "datos/crudos/creditcard.csv; luego repite el paso."
)
_ATRIBUTO = re.compile(r"^@attribute\s+(?:'([^']+)'|\"([^\"]+)\"|(\S+))", re.IGNORECASE)


class ErrorDatos(Exception):
    """Problema con los datos que impide continuar. El mensaje dice que hacer."""


def _leer_arff(ruta: Path) -> pd.DataFrame:
    nombres: list[str] = []
    with ruta.open(encoding="utf-8", errors="replace") as archivo:
        for linea in archivo:
            limpia = linea.strip()
            if not limpia or limpia.startswith("%"):
                continue
            coincidencia = _ATRIBUTO.match(limpia)
            if coincidencia:
                nombres.append(next(g for g in coincidencia.groups() if g))
            elif limpia.lower().startswith("@data"):
                break
        else:
            raise ErrorDatos(f"{ruta.name}: no encuentro la seccion @DATA del ARFF")
        return pd.read_csv(
            archivo,
            header=None,
            names=nombres,
            quotechar="'",
            na_values=["?"],
            keep_default_na=False,
            comment="%",
            skipinitialspace=True,
        )


def _normalizar(df: pd.DataFrame, nombre: str) -> pd.DataFrame:
    df.columns = [str(c).strip().strip("'\"") for c in df.columns]
    faltan = [c for c in OBLIGATORIAS if c not in df.columns]
    if faltan:
        raise ErrorDatos(f"{nombre}: faltan columnas obligatorias: {', '.join(faltan)}")
    df = df[[c for c in ORDEN if c in df.columns]].copy()
    if df["Class"].dtype == object:
        df["Class"] = df["Class"].astype(str).str.strip().str.strip("'\"")
    try:
        df = df.apply(pd.to_numeric)
    except (ValueError, TypeError) as error:
        raise ErrorDatos(f"{nombre}: hay valores que no son numeros ({error})") from error
    vacias = [c for c in df.columns if df[c].isna().any()]
    if vacias:
        raise ErrorDatos(f"{nombre}: hay valores vacios en {', '.join(vacias)}")
    if not df["Class"].isin([0, 1]).all():
        raise ErrorDatos(f"{nombre}: la columna Class solo puede valer 0 o 1")
    df["Class"] = df["Class"].astype(np.int64)
    return df.reset_index(drop=True)


def leer_conjunto(ruta: Path) -> pd.DataFrame:
    """Lee el conjunto (ARFF o CSV) y lo deja con las columnas en el orden del original."""
    ruta = Path(ruta)
    sufijo = ruta.suffix.lower()
    if sufijo == ".arff":
        df = _leer_arff(ruta)
    elif sufijo == ".csv":
        df = pd.read_csv(ruta)
    else:
        raise ErrorDatos(f"{ruta.name}: formato no reconocido (se espera .arff o .csv)")
    return _normalizar(df, ruta.name)


def huella_archivo(ruta: Path, algoritmo: str = "sha256") -> str:
    """Suma del archivo tal como esta en disco."""
    suma = hashlib.new(algoritmo)
    with Path(ruta).open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            suma.update(bloque)
    return suma.hexdigest()


def huella_contenido(df: pd.DataFrame) -> str:
    """SHA-256 de los valores de `V1`..`V28`, `Amount` y `Class`, sin `Time`.

    No depende del formato del archivo (ARFF o CSV) ni de que traiga `Time`: sirve para
    comprobar que OpenML y Kaggle entregan el mismo conjunto (supuesto S3).
    """
    suma = hashlib.sha256(",".join(OBLIGATORIAS).encode())
    valores = np.ascontiguousarray(df[list(OBLIGATORIAS)].to_numpy(dtype=np.float64))
    suma.update(valores.tobytes())
    return suma.hexdigest()


def comprobar_conteos(df: pd.DataFrame, filas: int, fraudes: int) -> list[str]:
    """Problemas de conteo frente a lo esperado; lista vacia si todo coincide."""
    problemas = []
    if len(df) != filas:
        problemas.append(f"Se esperaban {filas} transacciones y hay {len(df)}")
    reales = int(df["Class"].sum())
    if reales != fraudes:
        problemas.append(f"Se esperaban {fraudes} fraudes y hay {reales}")
    return problemas


def descargar(
    urls: list[str],
    destino: Path,
    tiempo_limite: float,
    abrir: Callable = urllib.request.urlopen,
    md5: str | None = None,
) -> str:
    """Descarga el primer archivo que llegue completo. Devuelve la direccion usada.

    Escribe primero en un archivo temporal y solo lo renombra si la descarga termino y la
    suma MD5 (si se indica) coincide, para no dejar archivos a medias.
    """
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".parcial")
    fallos = []
    for url in urls:
        try:
            suma = hashlib.md5()
            with abrir(url, timeout=tiempo_limite) as respuesta, temporal.open("wb") as salida:
                for bloque in iter(lambda r=respuesta: r.read(1 << 20), b""):
                    salida.write(bloque)
                    suma.update(bloque)
            if md5 and suma.hexdigest() != md5:
                fallos.append(f"{url}: la suma MD5 no coincide con la publicada")
                continue
            temporal.replace(destino)
            return url
        except (OSError, ValueError, io.UnsupportedOperation) as error:
            fallos.append(f"{url}: {type(error).__name__}: {error}")
        finally:
            temporal.unlink(missing_ok=True)
    raise ErrorDatos(
        "No pude descargar el conjunto de OpenML.\n  "
        + "\n  ".join(fallos)
        + f"\n{ALTERNATIVA_MANUAL}"
    )
