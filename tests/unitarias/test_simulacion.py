"""Rutas de la pagina de simulacion (docs/spec.md, secciones 8.6 y 13; ADR 0007 y 0015)."""

import json
import urllib.error

import pytest
from fastapi.testclient import TestClient

from fraude import simulacion
from fraude.api import crear_app

TRANSACCION = {
    "id_transaccion": "s-1",
    "origen": "sintetico",
    "monto": 1250.0,
    "ubicacion": {"pais_habitual": "EC", "pais_transaccion": "US"},
}
CASO = {
    "id_caso": "c-0123456789ab",
    "id_transaccion": "s-1",
    "nivel": "alerta_prioritaria",
    "estado": "pendiente_revision",
    "decision_final": "pendiente",
}


class N8nFalso:
    """Sustituye la peticion HTTP hacia n8n y anota lo que recibe."""

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.peticiones = []

    def __call__(self, metodo, url, cuerpo=None):
        self.peticiones.append({"metodo": metodo, "url": url, "cuerpo": cuerpo})
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


def _cliente(raiz, n8n=None, **opciones) -> TestClient:
    app = crear_app(raiz, url_n8n="http://n8n-falso:5678", pedir_n8n=n8n, **opciones)
    return TestClient(app, raise_server_exceptions=False)


def _registro(raiz) -> list[dict]:
    ruta = simulacion.ruta_registro(raiz)
    return [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines()]


def _lote(raiz, muestra: bool, fuente: str) -> dict:
    lote = {
        "version": 1,
        "fuente": fuente,
        "reportable": not muestra,
        "conteos": {"total": 1},
        "elementos": [
            {
                "n": 1,
                "tipo": "sintetico",
                "fila": None,
                "etiqueta_real": None,
                "descripcion": None,
                "transaccion": TRANSACCION,
            }
        ],
    }
    destino = raiz / "datos" / ("muestra" if muestra else "") / "demostracion" / "lote.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(lote), encoding="utf-8")
    return lote


# --- Pagina ---------------------------------------------------------------------------


def test_raiz_sirve_la_pagina_con_el_aviso(raiz_api):
    respuesta = _cliente(raiz_api).get("/")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    assert "Simulador de verificación de transacciones" in respuesta.text
    assert "señala" in respuesta.text


def test_recursos_de_la_pagina(raiz_api):
    cliente = _cliente(raiz_api)

    for recurso in ("estilos.css", "app.js"):
        assert cliente.get(f"/recursos/{recurso}").status_code == 200
    assert cliente.get("/recursos/no-existe.js").status_code == 404


def test_la_pagina_no_se_cachea_entre_versiones(raiz_api):
    respuesta = _cliente(raiz_api).get("/")

    assert "no-cache" in respuesta.headers.get("cache-control", "")


# --- Lote -----------------------------------------------------------------------------


def test_lote_sin_generar_responde_404_y_dice_que_hacer(raiz_api):
    respuesta = _cliente(raiz_api).get("/simulacion/lote")

    assert respuesta.status_code == 404
    error = respuesta.json()["error"]
    assert error["tipo"] == "lote_no_disponible"
    assert "./fraude todo" in error["mensaje"]


def test_lote_de_la_muestra(raiz_api):
    _lote(raiz_api, muestra=True, fuente="muestra")

    cuerpo = _cliente(raiz_api).get("/simulacion/lote").json()

    assert cuerpo["fuente"] == "muestra"
    assert cuerpo["elementos"][0]["transaccion"] == TRANSACCION


def test_lote_auto_prefiere_el_real(raiz_api):
    _lote(raiz_api, muestra=True, fuente="muestra")
    _lote(raiz_api, muestra=False, fuente="real")

    assert _cliente(raiz_api).get("/simulacion/lote").json()["fuente"] == "real"


def test_lote_sigue_al_modelo_cargado(raiz_api, entrenar_modelo):
    _lote(raiz_api, muestra=True, fuente="muestra")
    _lote(raiz_api, muestra=False, fuente="real")
    entrenar_modelo(raiz_api, muestra=True)

    cliente = _cliente(raiz_api, modo_modelo="muestra")

    assert cliente.get("/simulacion/lote").json()["fuente"] == "muestra"


# --- Transacciones --------------------------------------------------------------------


def test_reenvia_la_transaccion_a_n8n_y_devuelve_el_caso(raiz_api):
    n8n = N8nFalso([(200, CASO)])

    respuesta = _cliente(raiz_api, n8n).post("/simulacion/transacciones", json=TRANSACCION)

    assert respuesta.status_code == 200
    assert respuesta.json() == CASO
    assert n8n.peticiones == [
        {
            "metodo": "POST",
            "url": "http://n8n-falso:5678/webhook/transaccion",
            "cuerpo": TRANSACCION,
        }
    ]


def test_la_etiqueta_real_nunca_viaja_al_flujo(raiz_api):
    n8n = N8nFalso([])
    cuerpo = {**TRANSACCION, "etiqueta_real": 1}

    respuesta = _cliente(raiz_api, n8n).post("/simulacion/transacciones", json=cuerpo)

    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["tipo"] == "etiqueta_en_transaccion"
    assert n8n.peticiones == []


def test_entrada_invalida_tambien_va_a_n8n(raiz_api):
    # n8n la marca error_evaluacion: la pagina debe ver esa rama (seccion 12).
    invalida = {"origen": "original", "monto": 120.0}
    caso = {**CASO, "nivel": "error_evaluacion", "id_transaccion": None}
    n8n = N8nFalso([(200, caso)])

    respuesta = _cliente(raiz_api, n8n).post("/simulacion/transacciones", json=invalida)

    assert respuesta.status_code == 200
    assert n8n.peticiones[0]["cuerpo"] == invalida


def test_json_mal_formado_no_llega_a_n8n(raiz_api):
    n8n = N8nFalso([])

    respuesta = _cliente(raiz_api, n8n).post(
        "/simulacion/transacciones",
        content=b"{no es json",
        headers={"content-type": "application/json"},
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["tipo"] == "entrada_invalida"
    assert n8n.peticiones == []


def test_502_de_n8n_con_el_caso_calculado_se_repite(raiz_api):
    cuerpo = {"error": "La API no registro el caso", "caso": {"nivel": "sin_alerta"}}
    n8n = N8nFalso([(502, cuerpo)])

    respuesta = _cliente(raiz_api, n8n).post("/simulacion/transacciones", json=TRANSACCION)

    assert respuesta.status_code == 502
    assert respuesta.json() == cuerpo


@pytest.mark.parametrize(
    "fallo",
    [urllib.error.URLError("Connection refused"), TimeoutError("timed out")],
)
def test_n8n_que_no_responde_es_un_502_sin_caso(raiz_api, fallo):
    n8n = N8nFalso([fallo])

    respuesta = _cliente(raiz_api, n8n).post("/simulacion/transacciones", json=TRANSACCION)

    assert respuesta.status_code == 502
    cuerpo = respuesta.json()
    assert cuerpo["error"]["tipo"] == "n8n_no_disponible"
    assert cuerpo["id_transaccion"] == "s-1"
    assert "caso" not in cuerpo
    assert "./fraude estado" in cuerpo["error"]["mensaje"]


def test_respuesta_de_n8n_que_no_es_json(raiz_api):
    n8n = N8nFalso([(500, "Internal Server Error")])

    respuesta = _cliente(raiz_api, n8n).post("/simulacion/transacciones", json=TRANSACCION)

    assert respuesta.status_code == 502
    assert respuesta.json()["error"]["tipo"] == "n8n_no_disponible"


# --- Revisiones -----------------------------------------------------------------------

REVISION = {
    "id_caso": "c-0123456789ab",
    "decision": "sospecha_descartada",
    "revisor": "Ana",
    "comentario": "Compra habitual",
}


@pytest.mark.parametrize("codigo", [200, 404, 409, 422])
def test_reenvia_la_revision_y_repite_el_codigo(raiz_api, codigo):
    cuerpo = {**CASO, "estado": "revisado"} if codigo == 200 else {"error": {"tipo": "x"}}
    n8n = N8nFalso([(codigo, cuerpo)])

    respuesta = _cliente(raiz_api, n8n).post("/simulacion/revisiones", json=REVISION)

    assert respuesta.status_code == codigo
    assert respuesta.json() == cuerpo
    assert n8n.peticiones[0]["url"] == "http://n8n-falso:5678/webhook/revision"
    assert n8n.peticiones[0]["cuerpo"] == REVISION


def test_revision_con_n8n_caido(raiz_api):
    n8n = N8nFalso([urllib.error.URLError("Connection refused")])

    respuesta = _cliente(raiz_api, n8n).post("/simulacion/revisiones", json=REVISION)

    assert respuesta.status_code == 502
    assert respuesta.json()["error"]["tipo"] == "n8n_no_disponible"


# --- Registro de la sesion (simulacion.json) ----------------------------------------------


def test_cada_intercambio_queda_registrado(raiz_api):
    n8n = N8nFalso([(200, CASO), (200, {**CASO, "estado": "revisado"})])
    cliente = _cliente(raiz_api, n8n)

    cliente.post("/simulacion/transacciones?sesion=ses-1&n=7", json=TRANSACCION)
    cliente.post("/simulacion/revisiones?sesion=ses-1", json=REVISION)

    primero, segundo = _registro(raiz_api)
    assert primero["sesion"] == "ses-1"
    assert primero["n"] == 7
    assert primero["ruta"] == "transacciones"
    assert primero["enviado"] == TRANSACCION
    assert primero["codigo"] == 200
    assert primero["respuesta"] == CASO
    assert primero["latencia_ms"] >= 0
    assert primero["fecha"].endswith("Z")
    assert segundo["ruta"] == "revisiones"
    assert segundo["n"] is None


def test_el_registro_no_guarda_la_etiqueta_ni_parametros_raros(raiz_api):
    n8n = N8nFalso([(200, CASO)])
    cliente = _cliente(raiz_api, n8n)

    cliente.post("/simulacion/transacciones?sesion=../../x&n=uno", json=TRANSACCION)
    cliente.post("/simulacion/transacciones", json={**TRANSACCION, "etiqueta_real": 0})

    primero, segundo = _registro(raiz_api)
    assert primero["sesion"] is None and primero["n"] is None
    assert segundo["codigo"] == 422
    assert "etiqueta_real" not in segundo["enviado"]


def test_el_fallo_de_n8n_tambien_queda_registrado(raiz_api):
    n8n = N8nFalso([urllib.error.URLError("Connection refused")])

    _cliente(raiz_api, n8n).post("/simulacion/transacciones?sesion=s", json=TRANSACCION)

    (registro,) = _registro(raiz_api)
    assert registro["codigo"] == 502
    assert registro["respuesta"]["error"]["tipo"] == "n8n_no_disponible"


# --- Sin interbloqueo: n8n llama a la API mientras la API espera a n8n --------------------


def test_el_reenvio_no_bloquea_la_api(raiz_api):
    import socket
    import threading
    import time
    import urllib.request

    import uvicorn

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]

    def n8n_que_llama_a_la_api(metodo, url, cuerpo=None):
        # Como el flujo real: consulta la API antes de responder.
        with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/salud", timeout=5) as r:
            return 200, {**CASO, "salud": json.loads(r.read())["estado"]}

    app = crear_app(raiz_api, url_n8n="http://n8n", pedir_n8n=n8n_que_llama_a_la_api)
    servidor = uvicorn.Server(uvicorn.Config(app, port=puerto, log_level="warning"))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    try:
        for _ in range(100):
            if servidor.started:
                break
            time.sleep(0.05)
        peticion = urllib.request.Request(
            f"http://127.0.0.1:{puerto}/simulacion/transacciones",
            data=json.dumps(TRANSACCION).encode(),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(peticion, timeout=15) as r:
            cuerpo = json.loads(r.read())
        assert cuerpo["salud"] == "ok"
    finally:
        servidor.should_exit = True
        hilo.join(timeout=5)
