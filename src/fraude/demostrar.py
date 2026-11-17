"""Paso `demostrar` (docs/spec.md, secciones 8.8, 12, 15 y 16; ADR 0004 y 0014).

Envia el lote de demostracion por los dos caminos de la tabla de decision:

- **n8n:** `POST /webhook/transaccion`, que evalua, clasifica en el nodo «Clasificar nivel»,
  registra el caso y lo devuelve. Aqui se mide la latencia.
- **Python:** `POST /evaluar` en la API y `decision.clasificar`.

Exige el mismo nivel en todos los elementos (prueba de paridad) y que el estado del caso sea
coherente con su nivel. Deja `resultados/en_curso/flujo.json` aunque falle.
"""

import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from fraude import __version__, lote
from fraude.decision import ERROR, NIVELES, clasificar

TIEMPO_LIMITE_S = 60


class ErrorDemostracion(RuntimeError):
    """La demostracion no pudo hacerse o no cumplio la paridad."""


def pedir_http(metodo: str, url: str, cuerpo=None) -> tuple[int, object]:
    """Peticion JSON con la biblioteca estandar. Devuelve el codigo y el cuerpo."""
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    peticion = urllib.request.Request(
        url, data=datos, method=metodo, headers={"content-type": "application/json"}
    )
    try:
        with urllib.request.urlopen(peticion, timeout=TIEMPO_LIMITE_S) as respuesta:
            codigo, texto = respuesta.status, respuesta.read()
    except urllib.error.HTTPError as error:
        codigo, texto = error.code, error.read()
    try:
        return codigo, json.loads(texto)
    except ValueError:
        return codigo, texto.decode(errors="replace")


def _fecha() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _nivel_n8n(codigo: int, cuerpo) -> tuple[str | None, dict | None]:
    """Nivel y caso registrado. Con 502 el caso no se registro pero trae su nivel."""
    if not isinstance(cuerpo, dict):
        return None, None
    if codigo == 200 and cuerpo.get("nivel") in NIVELES:
        return cuerpo["nivel"], cuerpo
    caso = cuerpo.get("caso")
    if codigo == 502 and isinstance(caso, dict) and caso.get("nivel") in NIVELES:
        return caso["nivel"], None
    return None, None


def _nivel_python(codigo: int, evaluacion) -> str:
    if codigo != 200 or not isinstance(evaluacion, dict):
        return ERROR
    return clasificar(evaluacion["reglas"], evaluacion["modelo"])


def _latencias(valores: list[float]) -> dict:
    if not valores:
        return {"n": 0, "mediana": None, "p95": None, "maxima": None}
    arreglo = np.asarray(valores)
    return {
        "n": len(valores),
        "mediana": round(float(np.percentile(arreglo, 50)), 1),
        "p95": round(float(np.percentile(arreglo, 95)), 1),
        "maxima": round(float(arreglo.max()), 1),
        "metodo": "percentiles con interpolacion lineal (numpy)",
        "medida": "desde tareas hasta la respuesta del webhook; incluye /evaluar y /casos",
    }


def _procesar(elemento: dict, url_api: str, url_n8n: str, pedir: Callable, reloj) -> dict:
    t = elemento["transaccion"]
    caso = {
        "n": elemento["n"],
        "tipo": elemento["tipo"],
        "id_transaccion": t.get("id_transaccion") if isinstance(t, dict) else None,
        "etiqueta_real": elemento["etiqueta_real"],
        "nivel_n8n": None,
        "nivel_python": None,
        "coincide": False,
        "id_caso": None,
        "estado": None,
        "codigo_http": None,
        "latencia_ms": None,
        "error": None,
    }
    try:
        inicio = reloj()
        codigo, cuerpo = pedir("POST", f"{url_n8n}/webhook/transaccion", t)
        caso["latencia_ms"] = round((reloj() - inicio) * 1000, 1)
        caso["codigo_http"] = codigo
        caso["nivel_n8n"], registrado = _nivel_n8n(codigo, cuerpo)
        if registrado:
            caso["id_caso"], caso["estado"] = registrado.get("id_caso"), registrado.get("estado")
        if caso["nivel_n8n"] is None:
            caso["error"] = f"n8n respondio {codigo} sin un caso reconocible"
    except Exception as error:  # noqa: BLE001 - se anota y se sigue con el lote
        caso["error"] = f"n8n: {type(error).__name__}: {error}"
    try:
        codigo, evaluacion = pedir("POST", f"{url_api}/evaluar", t)
        caso["nivel_python"] = _nivel_python(codigo, evaluacion)
    except Exception as error:  # noqa: BLE001
        caso["error"] = (caso["error"] or "") + f" API: {type(error).__name__}: {error}"
    caso["coincide"] = caso["nivel_n8n"] is not None and caso["nivel_n8n"] == caso["nivel_python"]
    return caso


def _coherencia(casos: list[dict]) -> dict:
    """Casos registrados cuyo estado no corresponde a su nivel (seccion 8.5)."""
    incoherentes = []
    registrados = [c for c in casos if c["id_caso"]]
    for c in registrados:
        esperado = "cerrado" if c["nivel_n8n"] == "sin_alerta" else "pendiente_revision"
        if c["estado"] != esperado:
            incoherentes.append(
                {"n": c["n"], "nivel": c["nivel_n8n"], "estado": c["estado"], "esperado": esperado}
            )
    return {"registrados": len(registrados), "incoherentes": incoherentes}


def _escribir(raiz: Path, informe: dict) -> None:
    salida = Path(raiz) / "resultados" / "en_curso" / "flujo.json"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def demostrar(
    raiz: Path,
    muestra: bool = False,
    url_api: str | None = None,
    url_n8n: str | None = None,
    pedir: Callable = pedir_http,
    reloj: Callable[[], float] = time.perf_counter,
) -> dict:
    """Ejecuta el paso. Devuelve el contenido de `flujo.json`, que tambien escribe."""
    raiz = Path(raiz)
    url_api = (url_api or os.environ.get("FRAUDE_URL_API", "http://api:8000")).rstrip("/")
    url_n8n = (url_n8n or os.environ.get("FRAUDE_URL_N8N", "http://n8n:5678")).rstrip("/")
    informe: dict = {
        "fecha": _fecha(),
        "version": __version__,
        "estado": "en_curso",
        "fuente": "muestra" if muestra else "real",
        "reportable": not muestra,
        "servicios": {"api": url_api, "n8n": url_n8n},
    }
    inicio = time.monotonic()
    try:
        datos_lote = lote.generar(raiz, muestra)
        informe["lote"] = {
            "archivo": str(lote.ruta(raiz, muestra).relative_to(raiz)),
            "total": datos_lote["conteos"]["total"],
            "por_tipo": {
                k: datos_lote["conteos"][k] for k in ("original", "sintetico", "invalida")
            },
            "fraudes": datos_lote["conteos"]["fraudes"],
        }
        try:
            codigo, _ = pedir("GET", f"{url_n8n}/webhook/ping")
        except Exception as error:  # noqa: BLE001
            raise ErrorDemostracion(f"n8n no responde al ping: {error}") from error
        if codigo != 200:
            raise ErrorDemostracion(f"n8n respondio {codigo} al ping")

        total = informe["lote"]["total"]
        print(f"[demostrar] Enviando {total} transacciones por n8n y por Python...")
        casos = [_procesar(e, url_api, url_n8n, pedir, reloj) for e in datos_lote["elementos"]]
        discrepancias = [
            {k: c[k] for k in ("n", "tipo", "id_transaccion", "nivel_n8n", "nivel_python", "error")}
            for c in casos
            if not c["coincide"]
        ]
        informe.update(
            paridad={
                "total": len(casos),
                "coinciden": len(casos) - len(discrepancias),
                "discrepancias": discrepancias,
                "completa": not discrepancias,
            },
            niveles_n8n=dict(Counter(c["nivel_n8n"] for c in casos if c["nivel_n8n"])),
            niveles_python=dict(Counter(c["nivel_python"] for c in casos if c["nivel_python"])),
            latencia_ms=_latencias(
                [c["latencia_ms"] for c in casos if c["latencia_ms"] is not None]
            ),
            coherencia=_coherencia(casos),
            errores=[{"n": c["n"], "detalle": c["error"]} for c in casos if c["error"]],
            casos=casos,
        )
        problemas = []
        if discrepancias:
            problemas.append(f"paridad incompleta: {len(discrepancias)} de {len(casos)} distintos")
        if informe["coherencia"]["incoherentes"]:
            problemas.append("hay casos cuyo estado no corresponde a su nivel")
        sin_registro = [c["n"] for c in casos if c["nivel_n8n"] and not c["id_caso"]]
        if sin_registro:
            problemas.append(f"{len(sin_registro)} casos no se registraron en la API")
        if problemas:
            raise ErrorDemostracion("; ".join(problemas))
        informe["estado"] = "ok"
        return informe
    except Exception as error:
        informe["estado"] = "fallo"
        informe["error"] = str(error)
        raise
    finally:
        informe["duracion_s"] = round(time.monotonic() - inicio, 2)
        _escribir(raiz, informe)
