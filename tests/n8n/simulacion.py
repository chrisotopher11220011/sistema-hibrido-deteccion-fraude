"""Ejecuta flujos de n8n en el simulador de N1 (`simulador.mjs`, con Node.js).

n8n solo corre en N2 (Docker). El simulador reproduce el subconjunto de nodos que usan los
flujos del proyecto, con la semantica comprobada en el codigo de n8n 2.47.7 (ver
`docs/planes/fase-5.md`), y deja probar en N1 la tabla de decision y las ramas de error con
respuestas de la API simuladas.

Sin Node.js las pruebas se omiten, salvo con `FRAUDE_EXIGIR_NODE=1` (la CI), donde fallan.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SIMULADOR = Path(__file__).with_name("simulador.mjs")
FLUJOS = RAIZ / "n8n" / "flujos"


class ErrorSimulador(RuntimeError):
    """El simulador rechazo el flujo o fallo al ejecutarlo."""


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("FRAUDE_EXIGIR_NODE") == "1":
            pytest.fail("Hace falta Node.js para el simulador de flujos (FRAUDE_EXIGIR_NODE=1)")
        pytest.skip("Sin Node.js: el simulador de flujos no puede ejecutarse")
    return node


def simular(flujo: dict | str, cuerpo, respuestas: dict | None = None) -> dict:
    """Ejecuta `flujo` (objeto o nombre de archivo en `n8n/flujos/`) con `cuerpo` en el
    webhook. `respuestas`: nombre del nodo HTTP -> lista de respuestas simuladas, en orden de
    llamada: `{"statusCode": int, "body": ...}` o `{"error": {"message": str}}`."""
    if isinstance(flujo, str):
        flujo = json.loads((FLUJOS / flujo).read_text(encoding="utf-8"))
    entrada = {"flujo": flujo, "cuerpo": cuerpo, "respuestas": respuestas or {}}
    proceso = subprocess.run(
        [_node(), str(SIMULADOR)],
        input=json.dumps(entrada),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proceso.returncode != 0:
        raise ErrorSimulador(proceso.stderr.strip() or proceso.stdout.strip())
    return json.loads(proceso.stdout)


def validar_contrato(nombre: str, instancia) -> None:
    """Valida contra `docs/contratos/<nombre>.schema.json` (utilidades de tests/contrato)."""
    import importlib.util

    ruta = RAIZ / "tests" / "contrato" / "contratos.py"
    especificacion = importlib.util.spec_from_file_location("contratos_fraude", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    modulo.validar(nombre, instancia)
