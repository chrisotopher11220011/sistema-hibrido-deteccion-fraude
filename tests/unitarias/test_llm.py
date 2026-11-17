"""`tareas llm`: descarga, precarga y estado del modelo local (ADR 0016).

Contra un Ollama falso por HTTP: comprueba la API nativa que se usa (`/api/version`,
`/api/pull`, `/api/generate`, `/api/ps` y `/api/tags`) y lo que queda en `llm.json`.
"""

import json
import shutil

import pytest
import yaml

from apoyo import RAIZ_REPO, OllamaFalso
from fraude import llm


@pytest.fixture
def raiz(tmp_path):
    shutil.copytree(RAIZ_REPO / "config", tmp_path / "config")
    return tmp_path


def _apuntar(raiz, url):
    ruta = raiz / "config" / "llm.yaml"
    config = yaml.safe_load(ruta.read_text())
    config["servidor"]["url"] = url
    ruta.write_text(yaml.safe_dump(config, allow_unicode=True))


def _llm_json(raiz):
    return json.loads((raiz / "resultados" / "en_curso" / "llm.json").read_text())


def test_descarga_precarga_y_anota_el_modelo_en_la_grafica(raiz, capsys):
    ollama = OllamaFalso(en_grafica=True)
    try:
        _apuntar(raiz, ollama.url)
        informe = llm.preparar_llm(raiz)
    finally:
        ollama.cerrar()
    rutas = [(m, r) for m, r, _ in ollama.recibidos]
    assert ("POST", "/api/pull") in rutas and ("POST", "/api/generate") in rutas
    pull = next(c for m, r, c in ollama.recibidos if r == "/api/pull")
    assert pull == {"model": "qwen3.5:4b-q4_K_M", "stream": True}
    generate = next(c for m, r, c in ollama.recibidos if r == "/api/generate")
    assert generate["model"] == "qwen3.5:4b-q4_K_M" and generate["keep_alive"] == -1
    assert informe["estado"] == "ok"
    assert informe["ejecucion"] == "grafica"
    contenido = _llm_json(raiz)
    assert contenido == informe
    assert contenido["servidor"]["version"] == "0.40.16"
    assert contenido["modelo"]["nombre"] == "qwen3.5:4b-q4_K_M"
    assert contenido["modelo"]["resumen"].startswith("d8b0f5e9760c")
    assert contenido["modelo"]["resumen_esperado"] == "d8b0f5e9760c"
    assert contenido["modelo"]["coincide_con_el_fijado"] is True
    assert contenido["memoria"] == {
        "total_bytes": 3_300_000_000,
        "grafica_bytes": 3_300_000_000,
        "fraccion_en_grafica": 1.0,
    }
    salida = capsys.readouterr().out
    assert "50 %" in salida and "100 %" in salida


def test_sin_grafica_lo_anota_como_procesador(raiz):
    ollama = OllamaFalso(en_grafica=False)
    try:
        _apuntar(raiz, ollama.url)
        informe = llm.preparar_llm(raiz)
    finally:
        ollama.cerrar()
    assert informe["ejecucion"] == "procesador"
    assert informe["memoria"]["fraccion_en_grafica"] == 0.0


def test_descarga_fallida_deja_llm_json_y_lanza_error(raiz):
    ollama = OllamaFalso(pull_falla=True)
    try:
        _apuntar(raiz, ollama.url)
        with pytest.raises(llm.ErrorLlm, match="file does not exist"):
            llm.preparar_llm(raiz)
    finally:
        ollama.cerrar()
    contenido = _llm_json(raiz)
    assert contenido["estado"] == "fallo"
    assert "file does not exist" in contenido["error"]


def test_servidor_apagado_lo_explica(raiz):
    _apuntar(raiz, "http://127.0.0.1:9")
    with pytest.raises(llm.ErrorLlm, match="no responde"):
        llm.preparar_llm(raiz)
    assert _llm_json(raiz)["estado"] == "fallo"
