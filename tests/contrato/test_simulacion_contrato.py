"""Las rutas de la pagina cumplen los esquemas de docs/contratos/ (ADR 0015)."""

import shutil
import urllib.error

import pytest
from contratos import RAIZ, validar
from fastapi.testclient import TestClient

from fraude import lote
from fraude.api import crear_app
from fraude.preparar import preparar


@pytest.fixture(scope="module")
def raiz_con_lote(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("lote_contrato")
    shutil.copytree(RAIZ / "config", raiz / "config")
    preparar(raiz, muestra=True)
    lote.generar(raiz, muestra=True)
    return raiz


def _caido(*_):
    raise urllib.error.URLError("Connection refused")


def test_el_lote_generado_cumple_el_esquema(raiz_con_lote):
    cliente = TestClient(crear_app(raiz_con_lote), raise_server_exceptions=False)

    respuesta = cliente.get("/simulacion/lote")

    assert respuesta.status_code == 200
    validar("lote", respuesta.json())


def test_el_esquema_rechaza_la_etiqueta_dentro_de_la_transaccion(raiz_con_lote):
    import jsonschema

    datos = lote.generar(raiz_con_lote, muestra=True)
    original = next(e for e in datos["elementos"] if e["tipo"] == "original")
    original["transaccion"]["etiqueta_real"] = original["etiqueta_real"]

    with pytest.raises(jsonschema.ValidationError):
        validar("lote", datos)


@pytest.mark.parametrize(
    ("ruta", "cuerpo"),
    [
        ("/simulacion/transacciones", {"id_transaccion": "t", "etiqueta_real": 1}),
        ("/simulacion/transacciones", {"id_transaccion": "t", "origen": "original", "monto": 1}),
        ("/simulacion/revisiones", {"id_caso": "c-0123456789ab"}),
    ],
)
def test_errores_de_las_rutas_de_simulacion_cumplen_error(tmp_path, ruta, cuerpo):
    shutil.copytree(RAIZ / "config", tmp_path / "config")
    cliente = TestClient(crear_app(tmp_path, pedir_n8n=_caido), raise_server_exceptions=False)

    respuesta = cliente.post(ruta, json=cuerpo)

    assert respuesta.status_code in (422, 502)
    validar("error", respuesta.json())


def test_lote_no_disponible_cumple_error(tmp_path):
    shutil.copytree(RAIZ / "config", tmp_path / "config")
    respuesta = TestClient(crear_app(tmp_path)).get("/simulacion/lote")

    assert respuesta.status_code == 404
    validar("error", respuesta.json())
