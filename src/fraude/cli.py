"""Linea de comandos del proyecto (servicio `tareas`). Seccion 8.8 de docs/spec.md."""

import argparse
import json
import os
import sys
from pathlib import Path

from fraude.demostrar import demostrar
from fraude.entrenar import entrenar
from fraude.evaluar import evaluar
from fraude.evidencia import comprobar_servicios, reunir_evidencia
from fraude.llm import preparar_llm
from fraude.preparar import preparar

PASOS = ("preparar", "entrenar", "evaluar", "demostrar")
# Paso -> fase en la que empieza a existir (vacio: todos los pasos existen).
PASOS_FUTUROS: dict[str, int] = {}
NO_REPORTABLE = " Muestra para pruebas: no reportable."


def _raiz() -> Path:
    return Path(os.environ.get("FRAUDE_RAIZ", "/trabajo"))


def _archivo_pasos() -> Path:
    return _raiz() / "resultados" / "en_curso" / "pasos.json"


def _mensaje_futuro(paso: str) -> str:
    return f"El paso «{paso}» llega en la fase {PASOS_FUTUROS[paso]}; en esta version no hace nada."


def _detalle_preparar(informe: dict) -> str:
    return (
        f"Fuente {informe['fuente']}: {informe['filas']} transacciones, "
        f"{informe['fraudes']} fraudes; particion {informe['particion']['estado']}."
    )


def _detalle_entrenar(informe: dict) -> str:
    detalle = f"Modelo {informe['version']}; umbrales elegidos en validacion (modelo.json)."
    return detalle + (NO_REPORTABLE if not informe.get("reportable", True) else "")


def _detalle_evaluar(informe: dict) -> str:
    detalle = (
        f"Protocolo de la seccion 15 en {informe['duracion_s']} s: metricas.json, "
        "comparativa.md, figuras/ y analisis_errores/ (validacion)."
    )
    return detalle + (NO_REPORTABLE if not informe.get("reportable", True) else "")


def _detalle_demostrar(informe: dict) -> str:
    paridad, latencia = informe["paridad"], informe["latencia_ms"]
    detalle = (
        f"Lote de {informe['lote']['total']} por n8n y por Python: paridad "
        f"{paridad['coinciden']}/{paridad['total']}; latencia mediana {latencia['mediana']} ms, "
        f"p95 {latencia['p95']} ms (flujo.json)."
    )
    return detalle + (NO_REPORTABLE if not informe.get("reportable", True) else "")


def _detalle_llm(informe: dict) -> str:
    version = informe["servidor"]["version"]
    lugar = {
        "grafica": "la grafica",
        "procesador": "el procesador",
        "mixta": "grafica y procesador",
    }
    donde = lugar.get(informe.get("ejecucion"), "lugar desconocido")
    return (
        f"Modelo {informe['modelo']['nombre']} listo en Ollama {version}, en {donde} "
        f"({informe.get('ejecucion')}; llm.json)."
    )


AVISOS = {
    "llm": "Preparando el LLM local (la primera vez descarga el modelo, unos 3,3 GB)",
    "preparar": "Obteniendo y verificando los datos",
    "entrenar": "Entrenando Isolation Forest con la parte de ajuste y eligiendo umbrales",
    "evaluar": "Evaluando: configuraciones, lineas base, bootstrap, semillas y temporal",
    "demostrar": "Enviando el lote de demostracion por n8n; paridad y latencia",
}


def _paso(nombre: str, muestra: bool) -> dict:
    """Ejecuta un paso. Cualquier fallo se registra y no detiene `todo`."""
    funcion, detallar = {
        "llm": (preparar_llm, _detalle_llm),
        "preparar": (preparar, _detalle_preparar),
        "entrenar": (entrenar, _detalle_entrenar),
        "evaluar": (evaluar, _detalle_evaluar),
        "demostrar": (demostrar, _detalle_demostrar),
    }[nombre]
    print(f"[{nombre}] {AVISOS[nombre]}" + (" (muestra)..." if muestra else "..."))
    try:
        informe = funcion(_raiz(), muestra=muestra)
    except Exception as error:  # noqa: BLE001 - todo debe terminar siempre con evidencia
        detalle = f"{type(error).__name__}: {error}"
        if nombre == "llm":
            detalle += ". Las explicaciones usaran la plantilla."
        print(f"[{nombre}] ERROR: {detalle}")
        return {"paso": nombre, "estado": "fallo", "detalle": detalle}
    detalle = detallar(informe)
    print(f"[{nombre}] Listo. {detalle}")
    return {"paso": nombre, "estado": "ok", "detalle": detalle}


def _ejecutar_pasos(muestra: bool = False, llm: bool = False) -> list[dict]:
    """Ejecuta, en orden, los pasos que ya existen y anota los que llegan despues.

    Con `llm`, primero deja listo el LLM local: si falla, los demas pasos siguen y las
    explicaciones usan la plantilla.
    """
    pasos = [_paso("llm", muestra)] if llm else []
    for paso in PASOS:
        if paso not in PASOS_FUTUROS:
            pasos.append(_paso(paso, muestra))
            continue
        print(f"[{paso}] {_mensaje_futuro(paso)}")
        pasos.append({"paso": paso, "estado": "no_disponible", "detalle": _mensaje_futuro(paso)})
    archivo = _archivo_pasos()
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps(pasos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return pasos


def _pasos_guardados() -> list[dict]:
    try:
        return json.loads(_archivo_pasos().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _evidencia(pasos: list[dict]) -> int:
    url_api = os.environ.get("FRAUDE_URL_API", "http://api:8000")
    url_n8n = os.environ.get("FRAUDE_URL_N8N", "http://n8n:5678")
    print("[evidencia] Comprobando la API y n8n...")
    servicios = comprobar_servicios(url_api, url_n8n)
    for servicio in servicios:
        marca = "responde" if servicio["ok"] else "NO responde"
        print(f"[evidencia] {servicio['servicio']} {marca}: {servicio['detalle']}")
    carpeta = reunir_evidencia(
        _raiz(),
        commit=os.environ.get("FRAUDE_COMMIT") or "sin-commit",
        etiqueta=os.environ.get("FRAUDE_ETIQUETA") or "sin-etiqueta",
        servicios=servicios,
        pasos=pasos,
    )
    print(f"[evidencia] Evidencia reunida en resultados/{carpeta.name} (y su .zip).")
    hay_fallos = any(not s["ok"] for s in servicios) or any(p["estado"] == "fallo" for p in pasos)
    return 1 if hay_fallos else 0


def _analizador() -> argparse.ArgumentParser:
    analizador = argparse.ArgumentParser(
        prog="fraude", description="Tareas del prototipo de deteccion hibrida de fraude."
    )
    comandos = analizador.add_subparsers(dest="comando", metavar="comando")
    ayuda_muestra = "Usa la muestra para pruebas en lugar del conjunto real (no reportable)"
    ayudas = {
        "preparar": "Descarga y verifica los datos y los parte",
        "entrenar": "Entrena Isolation Forest y elige los umbrales en validacion",
        "evaluar": "Metricas de la seccion 15, figuras y analisis de errores",
        "demostrar": "Envia el lote de demostracion por n8n: paridad con Python y latencia",
    }
    for paso, ayuda in ayudas.items():
        comandos.add_parser(paso, help=ayuda).add_argument(
            "--muestra", action="store_true", help=ayuda_muestra
        )
    for paso, fase in PASOS_FUTUROS.items():
        comandos.add_parser(paso, help=f"Disponible desde la fase {fase}")
    comandos.add_parser(
        "llm", help="Descarga y precarga el modelo del LLM local (perfil llm de Compose)"
    )
    comandos.add_parser("evidencia", help="Reune los archivos de evidencia")
    todo = comandos.add_parser("todo", help="Ejecuta todos los pasos y termina con evidencia")
    todo.add_argument(
        "--sin-evidencia",
        action="store_true",
        help="No reunir evidencia al final (lo usa ./fraude, que la reune despues)",
    )
    todo.add_argument("--muestra", action="store_true", help=ayuda_muestra)
    todo.add_argument(
        "--llm", action="store_true", help="Prepara antes el LLM local para las explicaciones"
    )
    return analizador


def main(argv: list[str] | None = None) -> int:
    analizador = _analizador()
    opciones = analizador.parse_args(argv)
    if opciones.comando is None:
        analizador.print_help()
        return 2
    if opciones.comando in PASOS_FUTUROS:
        print(_mensaje_futuro(opciones.comando))
        return 2
    if opciones.comando in PASOS:
        return 0 if _paso(opciones.comando, opciones.muestra)["estado"] == "ok" else 1
    if opciones.comando == "llm":
        return 0 if _paso("llm", False)["estado"] == "ok" else 1
    if opciones.comando == "evidencia":
        return _evidencia(_pasos_guardados())
    pasos = _ejecutar_pasos(opciones.muestra, opciones.llm)
    if opciones.sin_evidencia:
        return 1 if any(p["estado"] == "fallo" for p in pasos) else 0
    return _evidencia(pasos)


if __name__ == "__main__":
    sys.exit(main())
