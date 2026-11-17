"""Linea de comandos del proyecto (servicio `tareas`). Seccion 8.8 de docs/spec.md."""

import argparse
import json
import os
import sys
from pathlib import Path

from fraude.evidencia import comprobar_servicios, reunir_evidencia
from fraude.preparar import preparar

PASOS = ("preparar", "entrenar", "evaluar", "demostrar")
# Paso -> fase en la que empieza a existir.
PASOS_FUTUROS = {"entrenar": 3, "evaluar": 3, "demostrar": 5}


def _raiz() -> Path:
    return Path(os.environ.get("FRAUDE_RAIZ", "/trabajo"))


def _archivo_pasos() -> Path:
    return _raiz() / "resultados" / "en_curso" / "pasos.json"


def _mensaje_futuro(paso: str) -> str:
    return f"El paso «{paso}» llega en la fase {PASOS_FUTUROS[paso]}; en esta version no hace nada."


def _paso_preparar(muestra: bool) -> dict:
    """Ejecuta `preparar`. Cualquier fallo se registra y no detiene `todo`."""
    print("[preparar] Obteniendo y verificando los datos" + (" (muestra)..." if muestra else "..."))
    try:
        informe = preparar(_raiz(), muestra=muestra)
    except Exception as error:  # noqa: BLE001 - todo debe terminar siempre con evidencia
        detalle = f"{type(error).__name__}: {error}"
        print(f"[preparar] ERROR: {detalle}")
        return {"paso": "preparar", "estado": "fallo", "detalle": detalle}
    detalle = (
        f"Fuente {informe['fuente']}: {informe['filas']} transacciones, "
        f"{informe['fraudes']} fraudes; particion {informe['particion']['estado']}."
    )
    print(f"[preparar] Listo. {detalle}")
    return {"paso": "preparar", "estado": "ok", "detalle": detalle}


def _ejecutar_pasos(muestra: bool = False) -> list[dict]:
    """Ejecuta, en orden, los pasos que ya existen y anota los que llegan despues."""
    pasos = []
    for paso in PASOS:
        if paso == "preparar":
            pasos.append(_paso_preparar(muestra))
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
    preparar_ = comandos.add_parser("preparar", help="Descarga y verifica los datos y los parte")
    preparar_.add_argument("--muestra", action="store_true", help=ayuda_muestra)
    for paso, fase in PASOS_FUTUROS.items():
        comandos.add_parser(paso, help=f"Disponible desde la fase {fase}")
    comandos.add_parser("evidencia", help="Reune los archivos de evidencia")
    todo = comandos.add_parser("todo", help="Ejecuta todos los pasos y termina con evidencia")
    todo.add_argument(
        "--sin-evidencia",
        action="store_true",
        help="No reunir evidencia al final (lo usa ./fraude, que la reune despues)",
    )
    todo.add_argument("--muestra", action="store_true", help=ayuda_muestra)
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
    if opciones.comando == "preparar":
        return 0 if _paso_preparar(opciones.muestra)["estado"] == "ok" else 1
    if opciones.comando == "evidencia":
        return _evidencia(_pasos_guardados())
    pasos = _ejecutar_pasos(opciones.muestra)
    if opciones.sin_evidencia:
        return 1 if any(p["estado"] == "fallo" for p in pasos) else 0
    return _evidencia(pasos)


if __name__ == "__main__":
    sys.exit(main())
