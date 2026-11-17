"""Utilidades de las pruebas de contrato (docs/spec.md, seccion 8; docs/contratos/).

Los esquemas de `docs/contratos/` son la referencia. Estas pruebas comprueban que los ejemplos
de la especificacion y las respuestas reales de la API los cumplen.
"""

import json
import re
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

RAIZ = Path(__file__).resolve().parents[2]
CONTRATOS = RAIZ / "docs" / "contratos"
SPEC = RAIZ / "docs" / "spec.md"
URN = "urn:fraude:contratos:"


def esquemas() -> dict[str, dict]:
    """Nombre corto (`evaluacion`) -> esquema."""
    return {
        ruta.name.removesuffix(".schema.json"): json.loads(ruta.read_text(encoding="utf-8"))
        for ruta in sorted(CONTRATOS.glob("*.schema.json"))
    }


def _registro() -> Registry:
    recursos = [
        (e["$id"], Resource.from_contents(e, default_specification=DRAFT202012))
        for e in esquemas().values()
    ]
    return Registry().with_resources(recursos)


def validar(nombre: str, instancia) -> None:
    """Lanza `jsonschema.ValidationError` si `instancia` no cumple el esquema `nombre`."""
    esquema = esquemas()[nombre]
    validador = jsonschema.Draft202012Validator(esquema, registry=_registro())
    validador.validate(instancia)


def cumple(nombre: str, instancia) -> bool:
    try:
        validar(nombre, instancia)
    except jsonschema.ValidationError:
        return False
    return True


def ejemplos_spec() -> dict[str, dict]:
    """Bloques JSON de las secciones 8.2 (transaccion) y 8.3 (evaluacion) de la especificacion."""
    texto = SPEC.read_text(encoding="utf-8")
    ejemplos = {}
    for seccion, nombre in (("### 8.2", "transaccion"), ("### 8.3", "evaluacion")):
        trozo = texto.split(seccion, 1)[1]
        bloque = re.search(r"```json\n(.*?)```", trozo, re.S)
        ejemplos[nombre] = json.loads(bloque.group(1))
    return ejemplos


def completar_variables(transaccion: dict) -> dict:
    """El ejemplo 8.2 abrevia `variables` (V1, V2 y V28); el contrato exige V1 a V28."""
    variables = {f"V{i}": 0.0 for i in range(1, 29)}
    variables.update(transaccion.get("variables") or {})
    return {**transaccion, "variables": variables}


@pytest.fixture
def ejemplos() -> dict[str, dict]:
    return ejemplos_spec()
