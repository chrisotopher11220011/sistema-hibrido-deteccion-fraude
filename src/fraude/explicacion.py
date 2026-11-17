"""Explicacion de una alerta con el LLM local (docs/spec.md, secciones 14 y 15; ADR 0016).

El LLM solo redacta, para el revisor, por que se genero una alerta. No decide ni cambia el
nivel: cuando n8n pide la redaccion, el nivel ya salio del nodo «Clasificar nivel».

- El mensaje se construye solo con lo que el sistema calculo: nivel, reglas activadas con su
  razon, puntuacion y umbrales del modelo, y contribuciones. Nunca `variables` crudas, el
  identificador de la transaccion ni la etiqueta real.
- Cada texto pasa una comprobacion automatica (seccion 15) antes de aceptarse.
- Si el LLM no esta activo, falla, tarda mas del tiempo limite o su texto no pasa la
  comprobacion, la respuesta dice «plantilla» y por que. n8n conserva entonces su plantilla.

Parametros en `config/llm.yaml`. La llamada usa la API compatible con OpenAI de Ollama.
"""

import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request

# Identificadores con forma de regla: MAYUSCULAS_CON_GUIONES (al menos un guion bajo).
_FORMA_DE_REGLA = re.compile(r"(?<![A-Za-z0-9_])[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+(?![A-Za-z0-9_])")
_VARIABLE = re.compile(r"(?<![A-Za-z0-9_])V([1-9]|1[0-9]|2[0-8])(?![A-Za-z0-9_])")


def llm_activo() -> bool:
    """El LLM se usa solo si `./fraude todo --llm` lo activo (`FRAUDE_LLM=activo`)."""
    return os.environ.get("FRAUDE_LLM", "desactivado").strip().lower() == "activo"


def normalizar(texto: str) -> str:
    """Minusculas y sin tildes, para comparar sin depender de la ortografia del modelo."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).lower()


def _etiqueta(nivel: str, config: dict) -> str:
    return config["comprobacion"]["etiquetas_nivel"][nivel]


def _cifra(valor) -> str:
    return f"{valor:.3f}" if isinstance(valor, int | float) else "desconocida"


def _linea_modelo(modelo: dict) -> str:
    if not modelo.get("evaluable"):
        return "Modelo Isolation Forest: no evaluable (la transacción no trae variables)."
    if modelo.get("anomalia_alta"):
        situacion = "supera el umbral prioritario"
    elif modelo.get("anomalia"):
        situacion = "supera el umbral de revisión"
    else:
        situacion = "no supera el umbral de revisión"
    return (
        f"Modelo Isolation Forest: puntuación {_cifra(modelo.get('puntuacion'))}; "
        f"umbral de revisión {_cifra(modelo.get('umbral_revision'))}; "
        f"umbral prioritario {_cifra(modelo.get('umbral_prioritaria'))}; {situacion}."
    )


def _activadas(senales: dict) -> list[dict]:
    return [r for r in senales.get("reglas", []) if r.get("evaluable") and r.get("activada")]


def mensajes(nivel: str, senales: dict, config: dict) -> list[dict]:
    """Mensajes para el LLM: instrucciones y solo las senales calculadas."""
    etiqueta = _etiqueta(nivel, config)
    sistema = (
        "Redactas, para la persona que revisa, la explicación de una alerta de un prototipo "
        "académico de detección de fraude con datos públicos. Escribe en español, en dos o "
        "tres frases, sin listas ni títulos. Usa solo los datos que se te dan: no inventes "
        "cifras, causas ni datos de personas. El nivel ya está decidido: no lo cambies ni lo "
        f"discutas, y escríbelo exactamente así: «{etiqueta}». Nombra solo las reglas de la "
        "lista, por su identificador; si la lista dice «ninguna», no nombres reglas. Las "
        "variables que más pesaron son componentes anónimos: di cuáles pesaron, no qué "
        "significan. El sistema señala para revisión: no digas que la transacción es fraude "
        "ni que el fraude está confirmado; la decisión es de la persona que revisa."
    )
    lineas = [f"Nivel: {etiqueta}"]
    activadas = _activadas(senales)
    if activadas:
        lineas.append("Reglas activadas:")
        for r in activadas:
            marca = " (alto riesgo)" if r.get("alto_riesgo") else ""
            lineas.append(f"- {r['id']}{marca}: {r['razon']}")
    else:
        lineas.append("Reglas activadas: ninguna")
    modelo = senales.get("modelo") or {}
    lineas.append(_linea_modelo(modelo))
    contribuciones = modelo.get("contribuciones") or []
    if modelo.get("evaluable") and contribuciones:
        partes = [f"{c['variable']} ({_cifra(c['peso'])})" for c in contribuciones]
        lineas.append("Variables que más pesaron en la puntuación: " + ", ".join(partes) + ".")
    lineas.append("Redacta la explicación.")
    return [
        {"role": "system", "content": sistema},
        {"role": "user", "content": "\n".join(lineas)},
    ]


def _contiene_palabra(texto_normalizado: str, palabra: str) -> bool:
    patron = r"(?<!\w)" + re.escape(normalizar(palabra)) + r"(?!\w)"
    return re.search(patron, texto_normalizado) is not None


def comprobar(texto: str, nivel: str, senales: dict, config: dict) -> dict:
    """Comprobacion automatica de una explicacion (docs/spec.md, seccion 15).

    Devuelve `{"valida", "fallos"}`. Fallos posibles: `vacio`, `razonamiento_visible`,
    `demasiado_largo`, `nivel_no_mencionado`, `nivel_ajeno:<nivel>`,
    `regla_no_activada:<id>`, `regla_inexistente:<id>`, `variable_no_calculada:<Vn>` y
    `afirmacion_prohibida:<patron>`.
    """
    reglas_config = config["comprobacion"]
    fallos: list[str] = []
    if not isinstance(texto, str) or not texto.strip():
        return {"valida": False, "fallos": ["vacio"]}
    normal = normalizar(texto)
    if "<think" in normal or "</think" in normal:
        fallos.append("razonamiento_visible")
    if len(texto) > reglas_config["max_caracteres"]:
        fallos.append("demasiado_largo")

    etiquetas = reglas_config["etiquetas_nivel"]
    if not _contiene_palabra(normal, etiquetas[nivel]):
        fallos.append("nivel_no_mencionado")
    for otro, etiqueta in etiquetas.items():
        if otro != nivel and _contiene_palabra(normal, etiqueta):
            fallos.append(f"nivel_ajeno:{otro}")

    reglas = senales.get("reglas", [])
    activadas = {r["id"] for r in _activadas(senales)}
    conocidas = {r["id"] for r in reglas}
    citadas = {m.group(0).upper() for m in _FORMA_DE_REGLA.finditer(texto.upper())}
    for id_regla in sorted(conocidas - activadas):
        palabras = reglas_config.get("palabras_de_regla", {}).get(id_regla, [])
        if id_regla in citadas or any(_contiene_palabra(normal, p) for p in palabras):
            fallos.append(f"regla_no_activada:{id_regla}")
    for id_citado in sorted(citadas - conocidas):
        fallos.append(f"regla_inexistente:{id_citado}")

    modelo = senales.get("modelo") or {}
    calculadas = {c["variable"] for c in (modelo.get("contribuciones") or [])}
    for variable in sorted({f"V{m.group(1)}" for m in _VARIABLE.finditer(texto)} - calculadas):
        fallos.append(f"variable_no_calculada:{variable}")

    for patron in reglas_config.get("afirmaciones_prohibidas", []):
        if re.search(patron, normal):
            fallos.append(f"afirmacion_prohibida:{patron}")
    return {"valida": not fallos, "fallos": fallos}


# --- Llamada al servidor --------------------------------------------------------------------


def pedir_http(url: str, cuerpo: dict, tiempo_limite: float) -> dict:
    """POST con JSON y respuesta JSON. Lanza `TimeoutError`, `OSError` o `ValueError`."""
    datos = json.dumps(cuerpo).encode("utf-8")
    peticion = urllib.request.Request(
        url, data=datos, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(peticion, timeout=tiempo_limite) as respuesta:
            contenido = respuesta.read()
    except urllib.error.HTTPError as error:
        detalle = error.read()[:300].decode("utf-8", "replace")
        raise OSError(f"HTTP {error.code}: {detalle}") from error
    except urllib.error.URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise TimeoutError(str(error.reason)) from error
        raise OSError(str(error.reason)) from error
    return json.loads(contenido)


def _respaldo(motivo: str, detalle: str, modelo=None, duracion_ms=None, descartado=None) -> dict:
    return {
        "motivo": motivo,
        "detalle": detalle,
        "modelo": modelo,
        "duracion_ms": duracion_ms,
        "texto_descartado": descartado,
    }


def _plantilla(respaldo: dict, comprobacion: dict | None = None) -> dict:
    return {
        "origen": "plantilla",
        "texto": None,
        "modelo": None,
        "duracion_ms": None,
        "respaldo": respaldo,
        "comprobacion": comprobacion,
    }


def _texto_de(respuesta) -> str:
    try:
        contenido = respuesta["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("la respuesta no trae choices[0].message.content") from error
    if not isinstance(contenido, str):
        raise ValueError("el contenido de la respuesta no es texto")
    return contenido.strip()


def redactar(
    nivel: str,
    senales: dict | None,
    config: dict,
    *,
    activo: bool,
    pedir=pedir_http,
    reloj=time.monotonic,
) -> dict:
    """Redaccion de la explicacion o motivo del respaldo (esquema `redaccion`).

    `origen` es `llm` con `texto`, `modelo` y `duracion_ms`, o `plantilla` con `respaldo`
    (y `texto` nulo: n8n conserva la suya).
    """
    if nivel not in config["redactar_niveles"]:
        return _plantilla(_respaldo("nivel_sin_redaccion", f"El nivel {nivel} no lleva redacción."))
    if not activo:
        return _plantilla(
            _respaldo("llm_desactivado", "El LLM local no está activo (./fraude todo sin --llm).")
        )
    modelo_config = config["modelo"]
    limite = float(config["tiempo_limite_s"])
    generacion = config.get("generacion", {})
    cuerpo = {
        "model": modelo_config,
        "messages": mensajes(nivel, senales or {}, config),
        "stream": False,
        "temperature": generacion.get("temperatura", 0.2),
        "seed": generacion.get("semilla", 0),
        "max_tokens": generacion.get("max_tokens", 220),
        "reasoning_effort": generacion.get("razonamiento", "none"),
    }
    url = config["servidor"]["url"].rstrip("/") + "/v1/chat/completions"
    inicio = reloj()
    try:
        respuesta = pedir(url, cuerpo, limite)
        texto = _texto_de(respuesta)
    except TimeoutError as error:
        duracion = round((reloj() - inicio) * 1000, 1)
        detalle = f"El LLM no respondió en {limite:g} s ({error})."
        return _plantilla(_respaldo("tiempo_agotado", detalle, modelo_config, duracion))
    except (OSError, ValueError) as error:
        duracion = round((reloj() - inicio) * 1000, 1)
        detalle = f"{type(error).__name__}: {error}"
        return _plantilla(_respaldo("error_llm", detalle, modelo_config, duracion))
    duracion = round((reloj() - inicio) * 1000, 1)
    modelo = respuesta.get("model") or modelo_config
    if duracion > limite * 1000:
        detalle = f"El LLM tardó {duracion:g} ms, más que el límite de {limite:g} s."
        return _plantilla(_respaldo("tiempo_agotado", detalle, modelo, duracion, texto))
    comprobacion = comprobar(texto, nivel, senales or {}, config)
    if not comprobacion["valida"]:
        detalle = "El texto no pasó la comprobación: " + ", ".join(comprobacion["fallos"])
        respaldo = _respaldo("comprobacion_fallida", detalle, modelo, duracion, texto)
        return _plantilla(respaldo, comprobacion)
    return {
        "origen": "llm",
        "texto": texto,
        "modelo": modelo,
        "duracion_ms": duracion,
        "respaldo": None,
        "comprobacion": comprobacion,
    }
