"""`explicaciones.json`: como se explicaron los casos (docs/spec.md, secciones 15 y 16).

Se calcula al reunir la evidencia, desde los casos guardados por la API:

- cuantas explicaciones redacto el LLM y cuantas la plantilla, y por que (motivo del respaldo);
- tiempos del LLM (mediana, p95 y maximo), de las aceptadas y de todos los intentos;
- la comprobacion automatica de la seccion 15: de los textos que devolvio el LLM, cuantos no
  la pasaron y por que tipo de fallo, y la misma comprobacion repetida ahora sobre las
  explicaciones aceptadas (deben seguir pasandola);
- una muestra de textos, sin secretos.

Con la muestra para pruebas o con un modelo distinto del fijado, las cifras describen esa
ejecucion: no miden la calidad del LLM elegido.
"""

from collections import Counter

import numpy as np

from fraude.explicacion import comprobar

NOTA = (
    "Explicaciones de los casos registrados en esta ejecucion. El LLM solo redacta: el nivel "
    "se decidio antes (seccion 14). La comprobacion automatica es la de la seccion 15; los "
    "tiempos son de esta maquina. Con la muestra para pruebas o la CI, las cifras no miden "
    "la calidad del modelo fijado."
)
TAMANO_MUESTRA = 20


def _tiempos(valores: list[float]) -> dict:
    if not valores:
        return {"n": 0, "mediana": None, "p95": None, "maximo": None}
    arreglo = np.asarray(valores, dtype=float)
    return {
        "n": len(valores),
        "mediana": round(float(np.percentile(arreglo, 50)), 1),
        "p95": round(float(np.percentile(arreglo, 95)), 1),
        "maximo": round(float(arreglo.max()), 1),
    }


def _tipo(fallo: str) -> str:
    return fallo.split(":", 1)[0]


def resumir(casos: list[dict], config_llm: dict | None, servidor: dict | None, enmascarar):
    """Contenido de `explicaciones.json`. `enmascarar` quita secretos de los textos."""
    explicados = [c for c in casos if c.get("explicacion")]
    contenido = {
        "estado": "ok" if explicados else "sin_casos",
        "nota": NOTA,
        "servidor": servidor,
        "total": len(explicados),
        "por_origen": {"llm": 0, "plantilla": 0},
        "por_nivel": {},
        "respaldos": {},
        "intentos_llm": 0,
        "comprobacion": None,
        "tiempos_ms": {"llm": _tiempos([]), "intentos": _tiempos([])},
        "muestra": [],
    }
    respaldos: Counter = Counter()
    por_fallo: Counter = Counter()
    duraciones_llm, duraciones_intentos = [], []
    comprobados = fallidos = 0
    aceptadas = siguen_validas = 0
    discrepan = []
    elegidos = []
    for caso in explicados:
        e = caso["explicacion"]
        origen = e.get("origen", "plantilla")
        contenido["por_origen"][origen] = contenido["por_origen"].get(origen, 0) + 1
        nivel = contenido["por_nivel"].setdefault(caso["nivel"], {"llm": 0, "plantilla": 0})
        nivel[origen] = nivel.get(origen, 0) + 1
        respaldo = e.get("respaldo") or None
        if origen == "plantilla":
            respaldos[respaldo["motivo"] if respaldo else "sin_respaldo"] += 1
        if origen == "llm":
            contenido["intentos_llm"] += 1
            comprobados += 1
            if isinstance(e.get("duracion_ms"), int | float):
                duraciones_llm.append(e["duracion_ms"])
                duraciones_intentos.append(e["duracion_ms"])
            if config_llm is not None:
                aceptadas += 1
                repetida = comprobar(
                    e["texto"], caso["nivel"], caso.get("senales") or {}, config_llm
                )
                if repetida["valida"]:
                    siguen_validas += 1
                else:
                    discrepan.append({"id_caso": caso["id_caso"], "fallos": repetida["fallos"]})
        elif respaldo and respaldo.get("modelo"):
            contenido["intentos_llm"] += 1
            if isinstance(respaldo.get("duracion_ms"), int | float):
                duraciones_intentos.append(respaldo["duracion_ms"])
            # Solo cuenta lo que paso por la comprobacion: un texto que llego tarde se
            # descarta sin comprobar.
            if respaldo["motivo"] == "comprobacion_fallida":
                comprobados += 1
                fallidos += 1
                for fallo in (e.get("comprobacion") or {}).get("fallos", []):
                    por_fallo[_tipo(fallo)] += 1
        if origen == "llm" or respaldo:
            elegidos.append(caso)

    contenido["respaldos"] = dict(sorted(respaldos.items()))
    contenido["tiempos_ms"] = {
        "llm": _tiempos(duraciones_llm),
        "intentos": _tiempos(duraciones_intentos),
    }
    contenido["comprobacion"] = {
        "textos_comprobados": comprobados,
        "fallidos": fallidos,
        "tasa_fallos": round(fallidos / comprobados, 4) if comprobados else None,
        "por_fallo": dict(sorted(por_fallo.items())),
        "recomprobacion": (
            {"aceptadas": aceptadas, "siguen_validas": siguen_validas, "discrepan": discrepan}
            if config_llm is not None
            else {"estado": "sin_configuracion"}
        ),
    }
    for caso in elegidos[:TAMANO_MUESTRA]:
        e = caso["explicacion"]
        respaldo = e.get("respaldo") or {}
        descartado = respaldo.get("texto_descartado")
        contenido["muestra"].append(
            {
                "id_caso": caso["id_caso"],
                "nivel": caso["nivel"],
                "origen": e.get("origen"),
                "modelo": e.get("modelo") or respaldo.get("modelo"),
                "duracion_ms": e.get("duracion_ms") or respaldo.get("duracion_ms"),
                "texto": enmascarar(e.get("texto") or ""),
                "respaldo": respaldo.get("motivo"),
                "texto_descartado": enmascarar(descartado) if descartado else None,
                "fallos": (e.get("comprobacion") or {}).get("fallos", []),
            }
        )
    return contenido
