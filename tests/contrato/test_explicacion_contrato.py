"""Las respuestas reales de `POST /explicacion` cumplen el esquema `redaccion` (ADR 0016)."""

import yaml
from contratos import validar
from fastapi.testclient import TestClient

from apoyo import TEXTO_LLM, ServidorLlm
from fraude.api import crear_app


def test_redacciones_reales_cumplen_el_contrato(raiz_api, ejemplos):
    servidor = ServidorLlm()
    try:
        ruta = raiz_api / "config" / "llm.yaml"
        config = yaml.safe_load(ruta.read_text())
        config["servidor"]["url"] = servidor.url
        ruta.write_text(yaml.safe_dump(config, allow_unicode=True))
        senales = ejemplos["evaluacion"]
        pedido = {"id_transaccion": "t-000457", "nivel": "alerta_prioritaria", "senales": senales}
        validar("redaccion_pedida", pedido)
        activo = TestClient(crear_app(raiz_api, llm_activo=True))
        inactivo = TestClient(crear_app(raiz_api, llm_activo=False))
        respuestas = [
            activo.post("/explicacion", json=pedido),
            inactivo.post("/explicacion", json=pedido),
            activo.post("/explicacion", json={**pedido, "nivel": "sin_alerta"}),
        ]
        servidor.texto = TEXTO_LLM + " Es fraude."
        respuestas.append(activo.post("/explicacion", json=pedido))
        origenes = []
        for respuesta in respuestas:
            assert respuesta.status_code == 200, respuesta.text
            validar("redaccion", respuesta.json())
            origenes.append(respuesta.json()["origen"])
        assert origenes == ["llm", "plantilla", "plantilla", "plantilla"]
        invalido = activo.post("/explicacion", json={**pedido, "senales": None})
        assert invalido.status_code == 422
        validar("error", invalido.json())
    finally:
        servidor.cerrar()
