"""Paso `evaluar` (docs/spec.md, secciones 8.8, 15 y 16; ADR 0003, 0008 y 0011).

Protocolo completo de la seccion 15:

- Cuatro configuraciones sobre la parte de prueba: solo reglas, solo Isolation Forest,
  hibrido con cualquier alerta e hibrido con solo alertas prioritarias.
- Tres lineas base: no alertar nunca, alertar al azar con la misma cantidad de alertas que el
  hibrido con cualquier alerta, y ordenar por monto (corte elegido en validacion por F1).
- Matriz de confusion, precision, exhaustividad y F1; precision media, precision en los `k`
  primeros y AUC ROC (complementaria) para las puntuaciones continuas.
- Intervalos del 95 % por bootstrap estratificado y diferencias pareadas con los mismos
  remuestreos; entrenamiento repetido con varias semillas; particion temporal secundaria.

Los umbrales vienen de `entrenar` (validacion). La prueba solo da metricas agregadas. Los
archivos de analisis de errores salen de validacion. Con la muestra nada de esto es un
resultado: todo queda marcado `reportable: false`.
"""

import json
import shutil
import time
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve

from fraude import figuras, metricas, modelo
from fraude.comparativa import escribir as escribir_comparativa
from fraude.configuracion import cargar
from fraude.contribuciones import contribuciones
from fraude.decision import PRIORITARIA, SIN_ALERTA, clasificar_vector
from fraude.entrenar import carpeta_modelo, huellas_datos
from fraude.preparar import AVISO_MUESTRA, cargar_preparados
from fraude.reglas import evaluar_reglas

CONFIGURACIONES = ("solo_reglas", "solo_modelo", "hibrido_cualquier", "hibrido_prioritaria")
LINEAS_BASE = ("nunca", "azar", "monto")
PUNTUACIONES = ("modelo", "monto", "azar")
NOMBRES = {
    "solo_reglas": "Solo reglas",
    "solo_modelo": "Solo Isolation Forest",
    "hibrido_cualquier": "Híbrido, cualquier alerta",
    "hibrido_prioritaria": "Híbrido, solo prioritarias",
    "nunca": "No alertar nunca",
    "azar": "Alertar al azar",
    "monto": "Ordenar por monto",
    "modelo": "Puntuación de Isolation Forest",
}
DEFINICIONES = {
    "solo_reglas": "alerta si alguna regla se activa",
    "solo_modelo": "alerta si puntuacion >= umbral_revision",
    "hibrido_cualquier": "nivel alerta_prioritaria o revision_recomendada (tabla 8.4)",
    "hibrido_prioritaria": "solo nivel alerta_prioritaria (tabla 8.4)",
    "nunca": "ninguna alerta",
    "azar": "tantas alertas como el hibrido con cualquier alerta, al azar con semilla",
    "monto": "alerta si monto >= corte que maximiza F1 en validacion",
}
METRICAS_BINARIAS = ("precision", "exhaustividad", "f1")
METRICAS_PUNTUACION = ("precision_media", "precision_k", "auc_roc")
AVISO_PRUEBA = (
    "Muestra para pruebas: esto no es un resultado. Comprueba que el procedimiento funciona; "
    "las cifras no representan el fraude real y no se reportan."
)


def _fecha() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _escribir_json(ruta: Path, contenido) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(contenido, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# --- Reglas y niveles -----------------------------------------------------------------


def _motor_por_monto(montos: np.ndarray, config_reglas: dict):
    """Llama al motor de reglas una vez por monto distinto y reparte el resultado."""
    unicos, inversa = np.unique(np.asarray(montos, dtype=np.float64), return_inverse=True)
    r = np.zeros(len(unicos), dtype=bool)
    r_alto = np.zeros(len(unicos), dtype=bool)
    ids = np.empty(len(unicos), dtype=object)
    for i, monto in enumerate(unicos):
        resultado = evaluar_reglas(
            {"id_transaccion": "evaluacion", "origen": "original", "monto": float(monto)},
            config_reglas,
        )
        activadas = [x for x in resultado if x["activada"]]
        r[i] = bool(activadas)
        r_alto[i] = any(x["alto_riesgo"] for x in activadas)
        ids[i] = ";".join(x["id"] for x in activadas)
    return r[inversa], r_alto[inversa], ids[inversa]


def senales_reglas(montos: np.ndarray, config_reglas: dict) -> tuple[np.ndarray, np.ndarray]:
    """`R` y `R_alto` de la seccion 8.4 para transacciones originales."""
    r, r_alto, _ = _motor_por_monto(montos, config_reglas)
    return r, r_alto


def salidas(
    r: np.ndarray, r_alto: np.ndarray, puntuacion: np.ndarray, umbrales: dict
) -> tuple[dict, np.ndarray]:
    """Alerta si/no de cada configuracion y nivel de cada transaccion."""
    a = puntuacion >= umbrales["umbral_revision"]
    a_alta = puntuacion >= umbrales["umbral_prioritaria"]
    nivel = clasificar_vector(r_alto, r, a, a_alta)
    alertas = {
        "solo_reglas": np.asarray(r, dtype=bool),
        "solo_modelo": a,
        "hibrido_cualquier": nivel != SIN_ALERTA,
        "hibrido_prioritaria": nivel == PRIORITARIA,
    }
    return alertas, nivel


# --- Comparacion con intervalos -------------------------------------------------------


def _con_ic(valor, muestras: list, confianza: float) -> dict:
    return {"valor": valor, "ic95": metricas.intervalo(muestras, confianza)}


def comparar(
    y_val: np.ndarray,
    monto_val: np.ndarray,
    y: np.ndarray,
    monto: np.ndarray,
    puntuacion: np.ndarray,
    umbrales: dict,
    config_reglas: dict,
    ev: dict,
) -> dict:
    """Configuraciones, lineas base, puntuaciones y diferencias sobre una parte de prueba."""
    k, confianza = int(ev["k_revision"]), float(ev["confianza"])
    r, r_alto = senales_reglas(monto, config_reglas)
    alertas, _ = salidas(r, r_alto, puntuacion, umbrales)

    rng = np.random.default_rng(int(ev["semilla_azar"]))
    n_alertas = int(alertas["hibrido_cualquier"].sum())
    azar = np.zeros(len(y), dtype=bool)
    azar[rng.choice(len(y), size=n_alertas, replace=False)] = True
    puntuacion_azar = rng.uniform(size=len(y))
    umbral_monto, _ = modelo.umbral_por_fbeta(y_val, monto_val, 1.0)
    alertas_base = {
        "nunca": np.zeros(len(y), dtype=bool),
        "azar": azar,
        "monto": monto >= umbral_monto,
    }
    binarias = {**alertas, **alertas_base}
    continuas = {"modelo": puntuacion, "monto": monto, "azar": puntuacion_azar}
    ordenes = {n: metricas.ordenar(s) for n, s in continuas.items()}
    parejas = list(combinations(CONFIGURACIONES, 2))
    parejas_puntuacion = [("modelo", "monto"), ("modelo", "azar")]

    puntual = {n: metricas.binarias(y, b) for n, b in binarias.items()}
    puntual_p = {n: metricas.de_puntuacion(y, continuas[n], k, orden=ordenes[n]) for n in continuas}
    muestras = {n: {m: [] for m in METRICAS_BINARIAS} for n in binarias}
    muestras_p = {n: {m: [] for m in METRICAS_PUNTUACION} for n in continuas}
    for pesos in metricas.remuestreos(y, int(ev["remuestreos"]), int(ev["semilla_bootstrap"])):
        rb = {n: metricas.binarias(y, b, pesos) for n, b in binarias.items()}
        rp = {n: metricas.de_puntuacion(y, continuas[n], k, pesos, ordenes[n]) for n in continuas}
        for n in binarias:
            for m in METRICAS_BINARIAS:
                muestras[n][m].append(rb[n][m])
        for n in continuas:
            for m in METRICAS_PUNTUACION:
                muestras_p[n][m].append(rp[n][m])

    def entrada(nombre: str) -> dict:
        p = puntual[nombre]
        return {
            "nombre": NOMBRES[nombre],
            "definicion": DEFINICIONES[nombre],
            "matriz": {c: p[c] for c in ("tp", "fp", "fn", "tn")},
            "alertas": p["alertas"],
            **{m: _con_ic(p[m], muestras[nombre][m], confianza) for m in METRICAS_BINARIAS},
        }

    def diferencia(a: str, b: str, m: str, fuente_p: dict, fuente_m: dict) -> dict:
        va, vb = fuente_p[a][m], fuente_p[b][m]
        valores = [
            None if x is None or z is None else x - z
            for x, z in zip(fuente_m[a][m], fuente_m[b][m], strict=True)
        ]
        valor = None if va is None or vb is None else va - vb
        return {"a": a, "b": b, "metrica": m, "valor": valor, **_ic(valores, confianza)}

    puntuaciones = {}
    for n in continuas:
        puntuaciones[n] = {
            m: _con_ic(puntual_p[n][m], muestras_p[n][m], confianza) for m in METRICAS_PUNTUACION
        }
        puntuaciones[n]["precision_k"]["k"] = k
        puntuaciones[n]["auc_roc"]["nota"] = "complementaria; poco adaptada al desbalance"
    diferencias = [
        diferencia(a, b, m, puntual, muestras) for a, b in parejas for m in METRICAS_BINARIAS
    ] + [diferencia(a, b, "precision_media", puntual_p, muestras_p) for a, b in parejas_puntuacion]
    return {
        "parte": "prueba",
        "filas": int(len(y)),
        "fraudes": int(np.sum(y)),
        "umbral_monto": {"valor": umbral_monto, "parte": "validacion", "criterio": "maximo F1"},
        "configuraciones": {n: entrada(n) for n in CONFIGURACIONES},
        "lineas_base": {n: entrada(n) for n in LINEAS_BASE},
        "puntuaciones": puntuaciones,
        "diferencias": diferencias,
    }


def _ic(valores: list, confianza: float) -> dict:
    return {"ic95": metricas.intervalo(valores, confianza)}


# --- Estabilidad con varias semillas --------------------------------------------------


def _resumen(valores: list) -> dict:
    definidos = np.array([v for v in valores if v is not None], dtype=np.float64)
    if len(definidos) == 0:
        return {"media": None, "desviacion": None, "minimo": None, "maximo": None, "n": 0}
    return {
        "media": float(definidos.mean()),
        "desviacion": float(definidos.std(ddof=1)) if len(definidos) > 1 else None,
        "minimo": float(definidos.min()),
        "maximo": float(definidos.max()),
        "n": int(len(definidos)),
    }


def estabilidad(datos: dict, config: dict, config_reglas: dict) -> dict:
    """Entrena con cada semilla, elige sus umbrales en validacion y mide en prueba."""
    params, k = dict(config["isolation_forest"]), int(config["evaluacion"]["k_revision"])
    r, r_alto = senales_reglas(datos["monto"], config_reglas)
    por_semilla = []
    for semilla in config["evaluacion"]["semillas"]:
        bosque = modelo.entrenar_bosque(datos["X_ajuste"], params, int(semilla))
        umbrales = modelo.elegir_umbrales(datos["y_val"], modelo.puntuar(bosque, datos["X_val"]))
        puntuacion = modelo.puntuar(bosque, datos["X"])
        alertas, _ = salidas(r, r_alto, puntuacion, umbrales)
        fila = {
            "semilla": int(semilla),
            "umbral_revision": umbrales["umbral_revision"],
            "umbral_prioritaria": umbrales["umbral_prioritaria"],
            **metricas.de_puntuacion(datos["y"], puntuacion, k),
        }
        for n in ("solo_modelo", "hibrido_cualquier", "hibrido_prioritaria"):
            b = metricas.binarias(datos["y"], alertas[n])
            fila[n] = {m: b[m] for m in (*METRICAS_BINARIAS, "alertas")}
        por_semilla.append(fila)
    resumen = {
        clave: _resumen([f[clave] for f in por_semilla])
        for clave in ("umbral_revision", "umbral_prioritaria", *METRICAS_PUNTUACION)
    }
    for n in ("solo_modelo", "hibrido_cualquier", "hibrido_prioritaria"):
        resumen[n] = {
            m: _resumen([f[n][m] for f in por_semilla]) for m in (*METRICAS_BINARIAS, "alertas")
        }
    return {
        "nota": "Solo reglas no depende de la semilla. Desviacion estandar muestral (n - 1).",
        "k": k,
        "por_semilla": por_semilla,
        "resumen": resumen,
    }


# --- Particion temporal secundaria ----------------------------------------------------


def temporal(df: pd.DataFrame, config: dict, config_reglas: dict) -> dict:
    """Desarrollo con la primera parte cronologica y prueba con la ultima (seccion 15)."""
    ev = config["evaluacion"]
    if not ev.get("temporal", True):
        return {"estado": "omitida", "motivo": "Desactivada en config/modelo.yaml."}
    if "Time" not in df.columns:
        return {
            "estado": "omitida",
            "motivo": "Falta la columna Time: no puede comprobarse el orden de las filas.",
        }
    variables = list(config["variables"])
    orden = np.argsort(df["Time"].to_numpy(), kind="stable")
    n = len(df)
    n_desarrollo = n - int(round(n * float(config["particion"]["prueba"])))
    n_ajuste = n_desarrollo - int(round(n_desarrollo * float(config["particion"]["validacion"])))
    tramos = {
        "ajuste": orden[:n_ajuste],
        "validacion": orden[n_ajuste:n_desarrollo],
        "prueba": orden[n_desarrollo:],
    }
    partes = {
        p: {
            "filas": int(len(i)),
            "fraudes": int(df["Class"].to_numpy()[i].sum()),
            "time_desde": float(df["Time"].to_numpy()[i].min()) if len(i) else None,
            "time_hasta": float(df["Time"].to_numpy()[i].max()) if len(i) else None,
        }
        for p, i in tramos.items()
    }
    val, prueba = df.iloc[tramos["validacion"]], df.iloc[tramos["prueba"]]
    try:
        bosque = modelo.entrenar_bosque(
            df.iloc[tramos["ajuste"]][variables].to_numpy(),
            dict(config["isolation_forest"]),
            int(config["semilla"]),
        )
        umbrales = modelo.elegir_umbrales(
            val["Class"].to_numpy(), modelo.puntuar(bosque, val[variables].to_numpy())
        )
        if partes["prueba"]["fraudes"] == 0:
            raise modelo.ErrorModelo("La parte de prueba cronologica no tiene fraudes.")
    except modelo.ErrorModelo as error:
        return {"estado": "fallo", "motivo": str(error), "partes": partes}
    seccion = comparar(
        val["Class"].to_numpy(),
        val["Amount"].to_numpy(),
        prueba["Class"].to_numpy(),
        prueba["Amount"].to_numpy(),
        modelo.puntuar(bosque, prueba[variables].to_numpy()),
        umbrales,
        config_reglas,
        ev,
    )
    return {
        "estado": "ok",
        "descripcion": (
            "Filas ordenadas por Time (orden estable). Primer tramo: desarrollo, dividido en "
            "ajuste y validacion en el mismo orden; ultimo tramo: prueba. Mismas proporciones "
            "que la particion principal."
        ),
        "partes": partes,
        "umbrales": {k: umbrales[k] for k in ("umbral_revision", "umbral_prioritaria")},
        **seccion,
    }


# --- Validacion: sensibilidad y analisis de errores ------------------------------------


def sensibilidad(y_val: np.ndarray, p_val: np.ndarray, maximo: int = 200) -> dict:
    """Curvas de precision y exhaustividad segun el umbral, en validacion."""
    precision, exhaustividad, umbrales = precision_recall_curve(y_val, p_val)
    precision, exhaustividad = precision[:-1], exhaustividad[:-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        f1 = np.nan_to_num(2 * precision * exhaustividad / (precision + exhaustividad))
    paso = max(1, int(np.ceil(len(umbrales) / maximo)))
    indices = np.r_[np.arange(0, len(umbrales), paso), len(umbrales) - 1]
    indices = np.unique(indices)
    return {
        "parte": "validacion",
        "umbral": umbrales[indices].tolist(),
        "precision": precision[indices].tolist(),
        "exhaustividad": exhaustividad[indices].tolist(),
        "f1": f1[indices].tolist(),
    }


def analisis_errores(
    datos: dict,
    bosque,
    umbrales: dict,
    config: dict,
    config_reglas: dict,
    carpeta: Path,
    muestra: bool,
    metodo: str | None,
) -> dict:
    """Fraudes no detectados y falsas alarmas de la parte de validacion (seccion 16)."""
    variables, k = list(config["variables"]), int(config["contribuciones"]["k"])
    maximo = int(config["evaluacion"]["max_filas_errores"])
    y, monto, p = datos["y_val"], datos["monto_val"], datos["p_val"]
    r, r_alto, ids = _motor_por_monto(monto, config_reglas)
    alertas, nivel = salidas(r, r_alto, p, umbrales)
    alerta = alertas["hibrido_cualquier"]
    carpeta.mkdir(parents=True, exist_ok=True)
    resumen = {
        "parte": "validacion",
        "configuracion": "hibrido_cualquier",
        "reportable": not muestra,
        "nota": (
            "Sale de validacion, no de prueba: puede usarse para mejorar sin contaminar la "
            "evaluacion. Las contribuciones dicen que variables pesaron, no por que."
        ),
        "metodo_contribuciones": metodo,
    }
    for nombre, mascara in (
        ("fraudes_no_detectados", (y == 1) & ~alerta),
        ("falsas_alarmas", (y == 0) & alerta),
    ):
        posiciones = np.flatnonzero(mascara)
        posiciones = posiciones[np.argsort(-p[posiciones], kind="stable")]
        resumen[nombre] = int(len(posiciones))
        resumen[f"{nombre}_truncado"] = bool(len(posiciones) > maximo)
        posiciones = posiciones[:maximo]
        listas = contribuciones(bosque, datos["X_val"][posiciones], variables, k)
        tabla = pd.DataFrame(
            {
                "fila": datos["filas_val"][posiciones],
                "parte": "validacion",
                "clase_real": y[posiciones],
                "monto": monto[posiciones],
                "puntuacion": np.round(p[posiciones], 6),
                "umbral_revision": umbrales["umbral_revision"],
                "umbral_prioritaria": umbrales["umbral_prioritaria"],
                "nivel": nivel[posiciones],
                "reglas_activadas": ids[posiciones],
                "contribuciones": [
                    "; ".join(f"{c['variable']}:{c['peso']:+.4f}" for c in lista)
                    for lista in listas
                ],
            }
        )
        tabla.to_csv(carpeta / f"{nombre}.csv", index=False)
    if muestra:
        resumen["aviso"] = AVISO_MUESTRA
    _escribir_json(carpeta / "resumen.json", resumen)
    return resumen


# --- Paso completo --------------------------------------------------------------------


def _comprobar_modelo(meta: dict, raiz: Path, muestra: bool, config: dict) -> None:
    if meta.get("estado") != "ok":
        raise modelo.ErrorModelo("El ultimo entrenamiento no termino bien: repite entrenar.")
    actuales = huellas_datos(raiz, muestra)
    for clave, valor in actuales.items():
        if meta.get("datos", {}).get(clave) != valor:
            raise modelo.ErrorModelo(
                "El modelo se entreno con otros datos o con otra particion "
                f"({clave}). Repite el paso entrenar."
            )
    for clave, actual in (
        ("parametros", dict(config["isolation_forest"])),
        ("variables", list(config["variables"])),
        ("semilla", int(config["semilla"])),
    ):
        if meta.get(clave) != actual:
            raise modelo.ErrorModelo(
                f"config/modelo.yaml cambio desde el entrenamiento ({clave}). "
                "Repite el paso entrenar."
            )


def _limpiar(en_curso: Path) -> None:
    for nombre in ("comparativa.md", "metricas.json"):
        (en_curso / nombre).unlink(missing_ok=True)
    for nombre in ("figuras", "analisis_errores"):
        shutil.rmtree(en_curso / nombre, ignore_errors=True)


def evaluar(raiz: Path, muestra: bool = False) -> dict:
    """Ejecuta el paso. Devuelve el contenido de `metricas.json`."""
    raiz = Path(raiz)
    en_curso = raiz / "resultados" / "en_curso"
    _limpiar(en_curso)
    informe: dict = {"fecha": _fecha(), "estado": "en_curso", "notas": []}
    inicio = time.monotonic()
    try:
        config = cargar(raiz, "modelo")
        config_reglas = cargar(raiz, "reglas")
        ev = config["evaluacion"]
        df, partes = cargar_preparados(raiz, muestra)
        bosque, meta = modelo.cargar_artefacto(carpeta_modelo(raiz, muestra))
        _comprobar_modelo(meta, raiz, muestra, config)
        variables = list(config["variables"])
        umbrales = {k: meta["umbrales"][k] for k in ("umbral_revision", "umbral_prioritaria")}
        informe.update(
            reportable=not muestra,
            fuente="muestra" if muestra else "real",
            version_modelo=meta["version"],
            umbrales={**umbrales, "parte": "validacion", "origen": "modelo.json (entrenar)"},
            protocolo={
                "remuestreos": int(ev["remuestreos"]),
                "confianza": float(ev["confianza"]),
                "intervalo": "percentiles del bootstrap estratificado de la parte de prueba",
                "semilla_bootstrap": int(ev["semilla_bootstrap"]),
                "semilla_azar": int(ev["semilla_azar"]),
                "k_revision": int(ev["k_revision"]),
                "semillas": [int(s) for s in ev["semillas"]],
                "definiciones": DEFINICIONES,
            },
        )
        if muestra:
            informe["aviso"] = AVISO_PRUEBA

        val, prueba = df[partes == "validacion"], df[partes == "prueba"]
        datos = {
            "X_ajuste": df.loc[partes == "ajuste", variables].to_numpy(),
            "X_val": val[variables].to_numpy(),
            "y_val": val["Class"].to_numpy(),
            "monto_val": val["Amount"].to_numpy(),
            "filas_val": np.flatnonzero(partes == "validacion"),
            "X": prueba[variables].to_numpy(),
            "y": prueba["Class"].to_numpy(),
            "monto": prueba["Amount"].to_numpy(),
        }
        datos["p_val"] = modelo.puntuar(bosque, datos["X_val"])
        datos["p"] = modelo.puntuar(bosque, datos["X"])
        informe["datos"] = {
            **huellas_datos(raiz, muestra),
            "partes": {
                p: {
                    "filas": int((partes == p).sum()),
                    "fraudes": int(df["Class"][partes == p].sum()),
                }
                for p in ("ajuste", "validacion", "prueba")
            },
        }

        informe["principal"] = comparar(
            datos["y_val"],
            datos["monto_val"],
            datos["y"],
            datos["monto"],
            datos["p"],
            umbrales,
            config_reglas,
            ev,
        )
        informe["semillas"] = estabilidad(datos, config, config_reglas)
        informe["temporal"] = temporal(df, config, config_reglas)
        if informe["temporal"]["estado"] != "ok":
            informe["notas"].append(f"Particion temporal: {informe['temporal']['motivo']}")
        informe["sensibilidad"] = sensibilidad(datos["y_val"], datos["p_val"])
        informe["analisis_errores"] = analisis_errores(
            datos,
            bosque,
            umbrales,
            config,
            config_reglas,
            en_curso / "analisis_errores",
            muestra,
            meta.get("contribuciones", {}).get("metodo"),
        )
        informe["figuras"] = figuras.escribir(informe, datos, en_curso / "figuras", muestra)
        informe["estado"] = "ok"
        informe["duracion_s"] = round(time.monotonic() - inicio, 2)
        escribir_comparativa(informe, en_curso / "comparativa.md")
        return informe
    except Exception as error:
        informe["estado"] = "fallo"
        informe["error"] = str(error) or repr(error)
        raise
    finally:
        informe.setdefault("duracion_s", round(time.monotonic() - inicio, 2))
        _escribir_json(en_curso / "metricas.json", informe)
