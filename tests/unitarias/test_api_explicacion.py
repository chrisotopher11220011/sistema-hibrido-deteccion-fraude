"""Ruta `POST /explicacion` (docs/spec.md, seccion 14; ADR 0016).

Se prueba contra un servidor compatible con OpenAI de pruebas, con HTTP real: asi se cubren
la peticion, el tiempo limite y los errores de red tal como los vera la API en Compose.
"""

import time

import pytest
import yaml
from fastapi.testclient import TestClient

from apoyo import TEXTO_LLM as TEXTO
from apoyo import ServidorLlm
from fraude.api import crear_app


@pytest.fixture
def servidor():
    s = ServidorLlm()
    yield s
    s.cerrar()


def _configurar(raiz, url, **cambios):
    ruta = raiz / "config" / "llm.yaml"
    config = yaml.safe_load(ruta.read_text())
    config["servidor"]["url"] = url
    config.update(cambios)
    ruta.write_text(yaml.safe_dump(config, allow_unicode=True))


def _senales(**modelo):
    return {
        "id_transaccion": "t-1",
        "reglas": [
            {"id": "MONTO_ALTO", "evaluable": True, "activada": True, "alto_riesgo": False,
             "razon": "El monto 1250.00 supera el umbral 1000.00"},
            {"id": "MONTO_ALTO_UBICACION_INUSUAL", "evaluable": False, "activada": False,
             "alto_riesgo": True, "razon": "No evaluable: la transaccion no trae ubicacion"},
        ],
        "modelo": {"evaluable": True, "puntuacion": 0.8, "umbral_revision": 0.62,
                   "umbral_prioritaria": 0.74, "anomalia": True, "anomalia_alta": True,
                   "contribuciones": [{"variable": "V14", "peso": 0.2}], **modelo},
        "versiones": {"reglas": "0.2.0", "modelo": "m"},
    }  # fmt: skip


def _pedido(nivel="alerta_prioritaria", **cambios):
    return {"id_transaccion": "t-1", "nivel": nivel, "senales": _senales(), **cambios}


def _cliente(raiz, activo=True):
    return TestClient(crear_app(raiz, llm_activo=activo), raise_server_exceptions=False)


def test_con_llm_activo_devuelve_la_redaccion_comprobada(raiz_api, servidor):
    _configurar(raiz_api, servidor.url)
    respuesta = _cliente(raiz_api).post("/explicacion", json=_pedido())
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["origen"] == "llm"
    assert cuerpo["texto"] == TEXTO
    assert cuerpo["modelo"] == "modelo-de-prueba"
    assert cuerpo["comprobacion"] == {"valida": True, "fallos": []}
    recibido = servidor.recibidos[0]
    assert recibido["ruta"] == "/v1/chat/completions"
    usuario = recibido["cuerpo"]["messages"][1]["content"]
    assert "MONTO_ALTO:" in usuario and "UBICACION" not in usuario


def test_sin_llm_activo_no_llama_al_servidor(raiz_api, servidor):
    _configurar(raiz_api, servidor.url)
    cuerpo = _cliente(raiz_api, activo=False).post("/explicacion", json=_pedido()).json()
    assert cuerpo["origen"] == "plantilla"
    assert cuerpo["respaldo"]["motivo"] == "llm_desactivado"
    assert servidor.recibidos == []


def test_el_estado_del_llm_sale_de_la_variable_de_entorno(raiz_api, servidor, monkeypatch):
    _configurar(raiz_api, servidor.url)
    monkeypatch.setenv("FRAUDE_LLM", "activo")
    cuerpo = TestClient(crear_app(raiz_api)).post("/explicacion", json=_pedido()).json()
    assert cuerpo["origen"] == "llm"
    monkeypatch.setenv("FRAUDE_LLM", "desactivado")
    cuerpo = TestClient(crear_app(raiz_api)).post("/explicacion", json=_pedido()).json()
    assert cuerpo["origen"] == "plantilla"


def test_llm_lento_usa_la_plantilla_por_tiempo_agotado(raiz_api, servidor):
    _configurar(raiz_api, servidor.url, tiempo_limite_s=0.3)
    servidor.espera_s = 1.5
    inicio = time.monotonic()
    cuerpo = _cliente(raiz_api).post("/explicacion", json=_pedido()).json()
    assert time.monotonic() - inicio < 1.4
    assert cuerpo["origen"] == "plantilla"
    assert cuerpo["respaldo"]["motivo"] == "tiempo_agotado"


def test_llm_apagado_usa_la_plantilla_por_error(raiz_api):
    _configurar(raiz_api, "http://127.0.0.1:9")
    cuerpo = _cliente(raiz_api).post("/explicacion", json=_pedido()).json()
    assert cuerpo["origen"] == "plantilla"
    assert cuerpo["respaldo"]["motivo"] == "error_llm"


def test_llm_que_responde_un_error_http_usa_la_plantilla(raiz_api, servidor):
    _configurar(raiz_api, servidor.url)
    servidor.codigo = 404
    cuerpo = _cliente(raiz_api).post("/explicacion", json=_pedido()).json()
    assert cuerpo["respaldo"]["motivo"] == "error_llm"
    assert "404" in cuerpo["respaldo"]["detalle"]


def test_texto_que_afirma_fraude_se_descarta(raiz_api, servidor):
    _configurar(raiz_api, servidor.url)
    servidor.texto = TEXTO + " Es fraude confirmado."
    cuerpo = _cliente(raiz_api).post("/explicacion", json=_pedido()).json()
    assert cuerpo["origen"] == "plantilla"
    assert cuerpo["respaldo"]["motivo"] == "comprobacion_fallida"
    assert cuerpo["respaldo"]["texto_descartado"] == servidor.texto


def test_sin_alerta_no_se_redacta(raiz_api, servidor):
    _configurar(raiz_api, servidor.url)
    cuerpo = _cliente(raiz_api).post("/explicacion", json=_pedido("sin_alerta")).json()
    assert cuerpo["respaldo"]["motivo"] == "nivel_sin_redaccion"
    assert servidor.recibidos == []


@pytest.mark.parametrize(
    "cambio",
    [
        {"nivel": "fraude"},
        {"senales": None},
        {"Class": 1},
        {"senales": {**_senales(), "reglas": "no"}},
    ],
)
def test_pedido_invalido_es_422(raiz_api, cambio):
    respuesta = _cliente(raiz_api, activo=False).post("/explicacion", json=_pedido(**cambio))
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["tipo"] == "entrada_invalida"
