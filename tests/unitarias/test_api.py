from fastapi.testclient import TestClient

from fraude import __version__
from fraude.api import app


def test_salud_responde_ok():
    respuesta = TestClient(app).get("/salud")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "ok"
    assert cuerpo["servicio"] == "api"
    assert cuerpo["version"] == __version__
    assert cuerpo["fecha"].endswith("Z")


def test_salud_informa_que_el_modelo_aun_no_esta():
    cuerpo = TestClient(app).get("/salud").json()

    assert cuerpo["modelo"]["cargado"] is False
    assert "fase 3" in cuerpo["modelo"]["motivo"].lower()
