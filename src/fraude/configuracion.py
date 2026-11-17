"""Lectura de `config/*.yaml` (docs/spec.md, seccion 8.9). Ningun umbral vive en el codigo."""

from pathlib import Path

import yaml


def cargar(raiz: Path, nombre: str) -> dict:
    """Devuelve el contenido de `config/<nombre>.yaml` bajo `raiz`."""
    ruta = Path(raiz) / "config" / f"{nombre}.yaml"
    if not ruta.is_file():
        raise FileNotFoundError(f"No encuentro la configuracion {ruta}")
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
