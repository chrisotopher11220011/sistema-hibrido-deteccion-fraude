import pytest
from fastapi.testclient import TestClient

from apoyo import variables_transaccion
from fraude import __version__
from fraude.api import crear_app


def _cliente(raiz, **opciones) -> TestClient:
    return TestClient(crear_app(raiz, **opciones), raise_server_exceptions=False)


def _original(valor: float = 0.0, monto: float = 10.0, **cambios) -> dict:
    return {
        "id_transaccion": "t-1",
        "origen": "original",
        "monto": monto,
        "variables": variables_transaccion(valor),
        **cambios,
    }


SINTETICA = {
    "id_transaccion": "s-1",
    "origen": "sintetico",
    "monto": 1250.0,
    "ubicacion": {"pais_habitual": "EC", "pais_transaccion": "US"},
}


# --- /salud ---------------------------------------------------------------------------


def test_salud_responde_ok(raiz_api):
    cuerpo = _cliente(raiz_api).get("/salud").json()

    assert cuerpo["estado"] == "ok"
    assert cuerpo["servicio"] == "api"
    assert cuerpo["version"] == __version__
    assert cuerpo["fecha"].endswith("Z")


def test_salud_sin_modelo_dice_que_hacer(raiz_api):
    modelo = _cliente(raiz_api).get("/salud").json()["modelo"]

    assert modelo["cargado"] is False
    assert "entrenar" in modelo["motivo"]


def test_salud_con_modelo(raiz_api, entrenar_modelo):
    entrenar_modelo(raiz_api, version="v-salud")

    modelo = _cliente(raiz_api).get("/salud").json()["modelo"]

    assert modelo["cargado"] is True
    assert modelo["fuente"] == "muestra"
    assert modelo["reportable"] is False
    assert modelo["version"] == "v-salud"


# --- /evaluar -------------------------------------------------------------------------


def test_sintetica_de_monto_alto_y_pais_distinto(raiz_api):
    respuesta = _cliente(raiz_api).post("/evaluar", json=SINTETICA)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["id_transaccion"] == "s-1"
    reglas = {r["id"]: r for r in cuerpo["reglas"]}
    assert reglas["MONTO_ALTO"]["activada"] is True
    ubicacion = reglas["MONTO_ALTO_UBICACION_INUSUAL"]
    assert ubicacion["activada"] is True and ubicacion["alto_riesgo"] is True
    assert "US" in ubicacion["razon"] and "EC" in ubicacion["razon"]
    assert cuerpo["modelo"]["evaluable"] is False
    assert cuerpo["modelo"]["puntuacion"] is None
    assert cuerpo["versiones"] == {"reglas": "0.2.0", "modelo": None}


def test_original_sin_variables_no_necesita_el_modelo(raiz_api):
    t = {"id_transaccion": "t-2", "origen": "original", "monto": 5.0}

    respuesta = _cliente(raiz_api).post("/evaluar", json=t)

    assert respuesta.status_code == 200
    modelo = respuesta.json()["modelo"]
    assert modelo["evaluable"] is False
    assert modelo["anomalia"] is False and modelo["anomalia_alta"] is False


def test_sin_variables_y_con_modelo_informa_sus_umbrales(raiz_api, entrenar_modelo):
    meta = entrenar_modelo(raiz_api, version="v-u")

    cuerpo = _cliente(raiz_api).post("/evaluar", json=SINTETICA).json()

    assert cuerpo["modelo"]["evaluable"] is False
    assert cuerpo["modelo"]["umbral_revision"] == meta["umbrales"]["umbral_revision"]
    assert cuerpo["versiones"]["modelo"] == "v-u"


def test_con_variables_y_sin_modelo_es_evaluacion_fallida(raiz_api):
    respuesta = _cliente(raiz_api).post("/evaluar", json=_original())

    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["id_transaccion"] == "t-1"
    assert cuerpo["error"]["tipo"] == "modelo_no_disponible"
    assert "entrenar" in cuerpo["error"]["mensaje"]


def test_con_modelo_puntua_y_explica_la_anomalia(raiz_api, entrenar_modelo):
    entrenar_modelo(raiz_api, version="v-m")

    cuerpo = _cliente(raiz_api).post("/evaluar", json=_original(valor=50.0)).json()

    modelo = cuerpo["modelo"]
    assert modelo["evaluable"] is True
    assert modelo["anomalia"] is (modelo["puntuacion"] >= modelo["umbral_revision"])
    assert modelo["anomalia"] is True
    assert len(modelo["contribuciones"]) == 5
    assert cuerpo["versiones"]["modelo"] == "v-m"


def test_el_monto_entra_al_modelo_como_amount(raiz_api, entrenar_modelo):
    entrenar_modelo(raiz_api)
    cliente = _cliente(raiz_api)

    bajo = cliente.post("/evaluar", json=_original(monto=0.0)).json()
    alto = cliente.post("/evaluar", json=_original(monto=1e6)).json()

    assert alto["modelo"]["puntuacion"] > bajo["modelo"]["puntuacion"]


def test_carga_el_modelo_que_entrenar_deja_despues_de_arrancar(raiz_api, entrenar_modelo):
    cliente = _cliente(raiz_api)
    assert cliente.post("/evaluar", json=_original()).status_code == 503

    entrenar_modelo(raiz_api, version="v-tarde")

    respuesta = cliente.post("/evaluar", json=_original())
    assert respuesta.status_code == 200
    assert respuesta.json()["versiones"]["modelo"] == "v-tarde"
    assert cliente.get("/salud").json()["modelo"]["cargado"] is True


@pytest.mark.parametrize(
    ("cuerpo", "id_esperado"),
    [
        ("{", None),
        ("[]", None),
        ('"hola"', None),
        ('{"id_transaccion": "t-9", "origen": "original", "monto": NaN}', "t-9"),
        ('{"id_transaccion": "t-9", "origen": "original", "monto": -1}', "t-9"),
        ('{"id_transaccion": "t-9", "origen": "real", "monto": 1}', "t-9"),
        ('{"id_transaccion": "t-9", "origen": "original", "monto": 1, "Class": 1}', "t-9"),
        ('{"origen": "original", "monto": 1}', None),
        ('{"id_transaccion": 7, "origen": "original", "monto": 1}', None),
    ],
)
def test_entrada_invalida(raiz_api, cuerpo, id_esperado):
    respuesta = _cliente(raiz_api).post(
        "/evaluar", content=cuerpo, headers={"content-type": "application/json"}
    )

    assert respuesta.status_code == 422
    error = respuesta.json()
    assert error["id_transaccion"] == id_esperado
    assert error["error"]["tipo"] == "entrada_invalida"
    assert error["error"]["detalles"]
    assert all(isinstance(d, dict) for d in error["error"]["detalles"])


def test_variables_incompletas_son_entrada_invalida(raiz_api, entrenar_modelo):
    entrenar_modelo(raiz_api)
    t = _original()
    del t["variables"]["V5"]

    respuesta = _cliente(raiz_api).post("/evaluar", json=t)

    assert respuesta.status_code == 422
    assert respuesta.json()["id_transaccion"] == "t-1"


def test_fallo_interno_tiene_cuerpo_de_error(raiz_api):
    (raiz_api / "config" / "reglas.yaml").unlink()

    respuesta = _cliente(raiz_api).post("/evaluar", json=SINTETICA)

    assert respuesta.status_code == 500
    assert respuesta.json()["id_transaccion"] == "s-1"
    assert respuesta.json()["error"]["tipo"] == "error_interno"
