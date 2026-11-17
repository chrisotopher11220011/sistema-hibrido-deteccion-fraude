"""Paso `preparar` (docs/spec.md, secciones 8.8 y 9; ADR 0002, 0003 y 0006).

Obtiene y verifica el conjunto, guarda la particion antes de cualquier ajuste, deja el
analisis exploratorio de la parte de ajuste y genera los datos sinteticos de ubicacion.

Carpetas, que nunca comparten archivos:
- `datos/crudos/` y `datos/preparados/`: conjunto real.
- `datos/muestra/crudos/` y `datos/muestra/preparados/`: muestra para pruebas.
- `datos/sinteticos/`: transacciones sinteticas de ubicacion.

Lo que vuelve al equipo (`datos.json` y `eda/`) se escribe en `resultados/en_curso/`.
"""

import json
import shutil
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from fraude import eda, muestra, particion, sinteticos
from fraude.configuracion import cargar
from fraude.datos import (
    ALTERNATIVA_MANUAL,
    ErrorDatos,
    comprobar_conteos,
    descargar,
    huella_archivo,
    huella_contenido,
    leer_conjunto,
)

AVISO_MUESTRA = (
    "Muestra para pruebas generada por el proyecto. No representa el fraude real: "
    "nada de lo calculado con ella es una metrica reportable."
)


def _fecha() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _escribir_json(ruta: Path, contenido) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(contenido, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _base(raiz: Path, es_muestra: bool) -> Path:
    return raiz / "datos" / "muestra" if es_muestra else raiz / "datos"


def _relativa(raiz: Path, ruta: Path) -> str:
    return str(ruta.relative_to(raiz))


def _obtener_muestra(raiz: Path, config: dict, informe: dict) -> Path:
    params = config["muestra"]
    crudos = _base(raiz, True) / "crudos"
    crudos.mkdir(parents=True, exist_ok=True)
    ruta = crudos / "muestra.csv"
    df = muestra.generar(
        params["filas"], params["fraudes"], params["semilla"], params.get("con_time", True)
    )
    df.to_csv(ruta, index=False)
    informe.update(
        fuente="muestra", reportable=False, aviso=AVISO_MUESTRA, url=None, semilla=params["semilla"]
    )
    informe["esperado"] = {"filas": params["filas"], "fraudes": params["fraudes"]}
    return ruta


def _obtener_real(raiz: Path, config: dict, informe: dict, abrir: Callable) -> Path:
    params = config["datos"]
    crudos = _base(raiz, False) / "crudos"
    manual, arff = crudos / "creditcard.csv", crudos / "creditcard.arff"
    informe.update(reportable=True, url=None)
    informe["esperado"] = {
        "filas": params["filas_esperadas"],
        "fraudes": params["fraudes_esperados"],
    }
    if manual.is_file():
        informe["fuente"] = "kaggle_manual"
        print("[preparar] Uso el archivo de Kaggle dejado a mano en datos/crudos/creditcard.csv.")
        return manual
    informe["fuente"] = "openml"
    md5 = params.get("md5_openml")
    if arff.is_file():
        print("[preparar] El conjunto ya estaba descargado; compruebo su suma MD5.")
        if md5 and huella_archivo(arff, "md5") != md5:
            raise ErrorDatos(
                "datos/crudos/creditcard.arff no coincide con la suma MD5 publicada por OpenML. "
                "Borra ese archivo y repite el paso para descargarlo de nuevo."
            )
        return arff
    print("[preparar] Descargando el conjunto de OpenML (unos 150 MB)...")
    informe["url"] = descargar(
        params["urls"], arff, float(params["tiempo_limite_s"]), abrir=abrir, md5=md5
    )
    print(f"[preparar] Descarga completa desde {informe['url']}.")
    return arff


def _verificar_huellas(base: Path, archivo: Path, df: pd.DataFrame, config: dict) -> dict:
    md5_publicado = config["datos"].get("md5_openml") if archivo.suffix == ".arff" else None
    huellas = {
        "sha256_archivo": huella_archivo(archivo),
        "md5_archivo": huella_archivo(archivo, "md5"),
        "md5_publicado": md5_publicado,
        "md5_coincide": None,
        "sha256_contenido": huella_contenido(df),
    }
    if md5_publicado and base.name != "muestra":
        huellas["md5_coincide"] = huellas["md5_archivo"] == md5_publicado
    conocidas = config["datos"].get("huellas_sha256_conocidas") or []
    if base.name != "muestra" and conocidas and huellas["sha256_contenido"] not in conocidas:
        raise ErrorDatos(
            "La huella del contenido no esta entre las conocidas de config/modelo.yaml: "
            f"{huellas['sha256_contenido']}"
        )
    if base.name == "muestra":
        # La muestra se regenera en cada ejecucion desde su configuracion: no se fija huella.
        huellas["estado"] = "no_aplica_muestra"
        return huellas
    guardada = base / "crudos" / "huella.json"
    if guardada.is_file():
        anterior = json.loads(guardada.read_text(encoding="utf-8"))
        if anterior["sha256_contenido"] != huellas["sha256_contenido"]:
            raise ErrorDatos(
                "La huella del contenido cambio respecto de la primera ejecucion "
                f"({anterior['sha256_contenido']} -> {huellas['sha256_contenido']}). "
                "Los datos no son los mismos: revisa datos/crudos/."
            )
        huellas["estado"] = "coincide"
        huellas["fijada"] = anterior.get("fecha")
    else:
        huellas["estado"] = "fijada_ahora"
        huellas["fijada"] = _fecha()
        _escribir_json(
            guardada,
            {"fecha": huellas["fijada"], "sha256_contenido": huellas["sha256_contenido"]},
        )
    return huellas


def _particion(base: Path, df: pd.DataFrame, config: dict, huella: str) -> tuple[np.ndarray, dict]:
    params = config["particion"]
    partes = particion.crear(
        df["Class"].to_numpy(), params["semilla"], params["prueba"], params["validacion"]
    )
    carpeta = base / "preparados" / "particion"
    meta = {
        "semilla": params["semilla"],
        "prueba": params["prueba"],
        "validacion": params["validacion"],
        "sha256_contenido": huella,
    }
    estado = "creada"
    if (carpeta / "particion.json").is_file():
        anterior = json.loads((carpeta / "particion.json").read_text(encoding="utf-8"))
        if all(anterior.get(k) == v for k, v in meta.items()):
            if not (particion.cargar(carpeta) == partes).all():
                raise ErrorDatos(
                    "La particion guardada no coincide con la recalculada con la misma semilla. "
                    "Puede deberse a otra version de scikit-learn; no se sobrescribe."
                )
            estado = "coincide"
        else:
            estado = "recreada_por_cambio_de_configuracion"
            shutil.rmtree(carpeta)
    guardado = particion.guardar(partes, carpeta, {**meta, "fecha": _fecha()})
    fraudes = {p: int(df.loc[partes == p, "Class"].sum()) for p in particion.PARTES}
    return partes, {**guardado, "fraudes": fraudes, "estado": estado}


def _sinteticos(raiz: Path, config: dict, config_reglas: dict) -> dict:
    params = config["sinteticos"]
    umbral = float(config_reglas["reglas"]["MONTO_ALTO_UBICACION_INUSUAL"]["umbral_monto"])
    lote = sinteticos.generar(
        params["cantidad"], params["semilla"], params["paises"], params["monto_maximo"], umbral
    )
    ruta = raiz / "datos" / "sinteticos" / "ubicacion.json"
    _escribir_json(ruta, lote)
    return {
        "archivo": _relativa(raiz, ruta),
        "cantidad": len(lote),
        "semilla": params["semilla"],
        "comprobacion": sinteticos.comprobacion_funcional(lote, config_reglas),
    }


def preparar(raiz: Path, muestra: bool = False, abrir: Callable = urllib.request.urlopen) -> dict:
    """Ejecuta el paso completo. Devuelve el contenido de `datos.json`, que tambien escribe."""
    raiz = Path(raiz)
    en_curso = raiz / "resultados" / "en_curso"
    salida = en_curso / "datos.json"
    informe: dict = {"fecha": _fecha(), "estado": "en_curso", "notas": []}
    inicio = time.monotonic()
    try:
        config = cargar(raiz, "modelo")
        config_reglas = cargar(raiz, "reglas")
        base = _base(raiz, muestra)
        if muestra:
            archivo = _obtener_muestra(raiz, config, informe)
        else:
            archivo = _obtener_real(raiz, config, informe, abrir)
        informe["archivo"] = _relativa(raiz, archivo)

        df = leer_conjunto(archivo)
        informe.update(
            filas=int(len(df)),
            fraudes=int(df["Class"].sum()),
            columnas=list(df.columns),
            tiene_time="Time" in df.columns,
        )
        if not informe["tiene_time"]:
            nota = (
                "Falta la columna Time. El modelo no la usa; se omite la particion temporal "
                "secundaria y la figura por hora."
            )
            informe["notas"].append(nota)
            print(f"[preparar] AVISO: {nota}")

        problemas = comprobar_conteos(
            df, informe["esperado"]["filas"], informe["esperado"]["fraudes"]
        )
        informe["conteos_coinciden"] = not problemas
        if problemas:
            raise ErrorDatos("; ".join(problemas) + ". " + ALTERNATIVA_MANUAL)

        informe["huellas"] = _verificar_huellas(base, archivo, df, config)
        partes, informe["particion"] = _particion(
            base, df, config, informe["huellas"]["sha256_contenido"]
        )
        _escribir_json(
            base / "preparados" / "origen.json",
            {
                "archivo": informe["archivo"],
                "sha256_contenido": informe["huellas"]["sha256_contenido"],
            },
        )

        carpeta_eda = en_curso / "eda"
        shutil.rmtree(carpeta_eda, ignore_errors=True)
        umbral = float(config_reglas["reglas"]["MONTO_ALTO"]["umbral_monto"])
        archivos = eda.escribir(df[partes == "ajuste"], umbral, carpeta_eda)
        informe["eda"] = {"parte": "ajuste", "archivos": archivos}

        informe["sinteticos"] = _sinteticos(raiz, config, config_reglas)
        if not informe["sinteticos"]["comprobacion"]["correcta"]:
            raise ErrorDatos("La regla de ubicacion no se comporta como define la seccion 10")
        informe["estado"] = "ok"
        return informe
    except Exception as error:
        informe["estado"] = "fallo"
        informe["error"] = f"{error}" if isinstance(error, ErrorDatos) else repr(error)
        raise
    finally:
        informe["duracion_s"] = round(time.monotonic() - inicio, 2)
        _escribir_json(salida, informe)


def cargar_preparados(raiz: Path, muestra: bool = False) -> tuple[pd.DataFrame, np.ndarray]:
    """Datos y parte de cada fila, para las fases siguientes. Verifica la huella."""
    raiz = Path(raiz)
    base = _base(raiz, muestra)
    origen = base / "preparados" / "origen.json"
    if not origen.is_file():
        opcion = " --muestra" if muestra else ""
        raise ErrorDatos(f"No hay datos preparados. Ejecuta antes: preparar{opcion}")
    referencia = json.loads(origen.read_text(encoding="utf-8"))
    df = leer_conjunto(raiz / referencia["archivo"])
    if huella_contenido(df) != referencia["sha256_contenido"]:
        raise ErrorDatos("Los datos cambiaron desde preparar: repite el paso preparar")
    return df, particion.cargar(base / "preparados" / "particion")
