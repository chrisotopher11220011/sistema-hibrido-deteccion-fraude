"""Paso `entrenar` (docs/spec.md, secciones 8.8 y 11; ADR 0003 y 0008).

Entrena Isolation Forest con la parte de ajuste, sin etiquetas, y elige los dos umbrales con
la parte de validacion. Deja el artefacto en `datos/modelo/` (o `datos/muestra/modelo/`) y
una copia de `modelo.json` en `resultados/en_curso/` para la evidencia. Nunca mira la prueba.
"""

import hashlib
import json
import platform
import time
from datetime import UTC, datetime
from importlib.metadata import version as version_paquete
from pathlib import Path

from fraude import modelo
from fraude.configuracion import cargar
from fraude.contribuciones import METODO
from fraude.preparar import AVISO_MUESTRA, cargar_preparados

DESCRIPCION_PUNTUACION = (
    "-score_samples de scikit-learn: puntuacion de anomalia de Liu et al. en (0, 1]; "
    "mayor = mas anomalo. Prioriza la revision; no prueba el fraude."
)


def carpeta_modelo(raiz: Path, muestra: bool) -> Path:
    base = Path(raiz) / "datos"
    return (base / "muestra" if muestra else base) / "modelo"


def _base(raiz: Path, muestra: bool) -> Path:
    return Path(raiz) / "datos" / ("muestra" if muestra else "")


def huellas_datos(raiz: Path, muestra: bool) -> dict:
    """Huella del contenido y de la particion con que se preparo lo que hay en disco."""
    preparados = _base(raiz, muestra) / "preparados"
    origen = json.loads((preparados / "origen.json").read_text(encoding="utf-8"))
    particion = json.loads(
        (preparados / "particion" / "particion.json").read_text(encoding="utf-8")
    )
    return {
        "sha256_contenido": origen["sha256_contenido"],
        "huella_particion": particion["huella_indices"],
    }


def versiones() -> dict:
    paquetes = ("scikit-learn", "numpy", "pandas", "shap", "joblib")
    return {"python": platform.python_version(), **{p: version_paquete(p) for p in paquetes}}


def _escribir(ruta: Path, contenido: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(contenido, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def entrenar(raiz: Path, muestra: bool = False) -> dict:
    """Ejecuta el paso. Devuelve el contenido de `modelo.json`."""
    raiz = Path(raiz)
    salida = raiz / "resultados" / "en_curso" / "modelo.json"
    momento = datetime.now(UTC)
    informe: dict = {"fecha": momento.strftime("%Y-%m-%dT%H:%M:%SZ"), "estado": "en_curso"}
    try:
        config = cargar(raiz, "modelo")
        df, partes = cargar_preparados(raiz, muestra)
        variables = list(config["variables"])
        params = dict(config["isolation_forest"])
        semilla = int(config["semilla"])
        informe.update(
            reportable=not muestra,
            fuente="muestra" if muestra else "real",
            semilla=semilla,
            parametros=params,
            variables=variables,
            puntuacion=DESCRIPCION_PUNTUACION,
        )
        if muestra:
            informe["aviso"] = AVISO_MUESTRA

        ajuste = df[partes == "ajuste"]
        validacion = df[partes == "validacion"]
        inicio = time.monotonic()
        bosque = modelo.entrenar_bosque(ajuste[variables].to_numpy(), params, semilla)
        informe["tiempo_entrenamiento_s"] = round(time.monotonic() - inicio, 3)

        inicio = time.monotonic()
        puntuacion = modelo.puntuar(bosque, validacion[variables].to_numpy())
        umbrales = modelo.elegir_umbrales(validacion["Class"].to_numpy(), puntuacion)
        informe["tiempo_umbrales_s"] = round(time.monotonic() - inicio, 3)
        informe["umbrales"] = {
            **umbrales,
            "parte": "validacion",
            "criterio": "revision: maximo F1; prioritaria: maximo F0,5 y no menor que revision",
        }
        informe["datos"] = {
            **huellas_datos(raiz, muestra),
            "filas_ajuste": int(len(ajuste)),
            "filas_validacion": int(len(validacion)),
            "fraudes_validacion": int(validacion["Class"].sum()),
        }
        informe["contribuciones"] = {"metodo": METODO, "k": int(config["contribuciones"]["k"])}
        informe["versiones"] = versiones()
        firma = json.dumps(
            {k: informe[k] for k in ("semilla", "parametros", "variables", "umbrales", "datos")},
            sort_keys=True,
        )
        corta = hashlib.sha256(firma.encode()).hexdigest()[:6]
        informe["version"] = f"{momento:%Y-%m-%dT%H:%MZ}-{corta}"
        informe["estado"] = "ok"
        informe = modelo.guardar_artefacto(carpeta_modelo(raiz, muestra), bosque, informe)
        return informe
    except Exception as error:
        informe["estado"] = "fallo"
        informe["error"] = str(error) or repr(error)
        raise
    finally:
        _escribir(salida, informe)
