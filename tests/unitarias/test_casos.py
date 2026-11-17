import re

import pytest
from fastapi.testclient import TestClient

from fraude.api import crear_app

SINTETICA = {
    "id_transaccion": "s-1",
    "origen": "sintetico",
    "monto": 1250.0,
    "ubicacion": {"pais_habitual": "EC", "pais_transaccion": "US"},
}
FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@pytest.fixture
def cliente(raiz_api):
    return TestClient(crear_app(raiz_api), raise_server_exceptions=False)


def caso_nuevo(cliente: TestClient, nivel: str = "alerta_prioritaria", **cambios) -> dict:
    senales = cliente.post("/evaluar", json=SINTETICA).json()
    caso = {
        "id_transaccion": "s-1",
        "origen": "sintetico",
        "monto": 1250.0,
        "senales": senales,
        "puntuacion": None,
        "nivel": nivel,
        "razones": [r["razon"] for r in senales["reglas"] if r["activada"]],
        "explicacion": {"texto": "Señalada para revisión por dos reglas.", "origen": "plantilla"},
        "notificacion": {"canal": "simulada", "estado": "registrada"},
        "versiones": {"reglas": "0.2.0", "modelo": None, "flujo": "evaluacion-0.5.0"},
    }
    return {**caso, **cambios}


def registrar(cliente: TestClient, **cambios) -> dict:
    respuesta = cliente.post("/casos", json=caso_nuevo(cliente, **cambios))
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_alerta_queda_pendiente_de_revision(cliente):
    caso = registrar(cliente)

    assert re.fullmatch(r"c-[0-9a-f]{12}", caso["id_caso"])
    assert caso["estado"] == "pendiente_revision"
    assert caso["decision_final"] == "pendiente"
    assert caso["revision"] is None
    assert FECHA.match(caso["fecha_procesamiento"])
    assert caso["senales"]["id_transaccion"] == "s-1"


def test_sin_alerta_se_cierra_sola(cliente):
    caso = registrar(cliente, nivel="sin_alerta", razones=[])

    assert caso["estado"] == "cerrado"
    assert caso["decision_final"] == "sin_alerta"


@pytest.mark.parametrize("nivel", ["revision_recomendada", "error_evaluacion"])
def test_otros_niveles_quedan_pendientes(cliente, nivel):
    assert registrar(cliente, nivel=nivel)["estado"] == "pendiente_revision"


def test_respeta_la_fecha_de_procesamiento_de_n8n(cliente):
    caso = registrar(cliente, fecha_procesamiento="2026-11-17T10:00:00Z")

    assert caso["fecha_procesamiento"] == "2026-11-17T10:00:00Z"


def test_caso_de_error_sin_datos_de_la_transaccion(cliente):
    caso = registrar(
        cliente,
        nivel="error_evaluacion",
        id_transaccion=None,
        origen=None,
        monto=None,
        senales=None,
        razones=["Entrada invalida: monto debe ser mayor o igual que 0"],
    )

    assert caso["estado"] == "pendiente_revision"
    assert caso["id_transaccion"] is None and caso["senales"] is None


@pytest.mark.parametrize(
    "cambios",
    [
        {"senales": None},
        {"monto": None},
        {"razones": []},
        {"nivel": "fraude_confirmado"},
        {"estado": "cerrado"},
        {"id_caso": "c-000000000000"},
        {"explicacion": {"texto": "x", "origen": "otro"}},
        {"fecha_procesamiento": "17/11/2026"},
    ],
)
def test_caso_invalido(cliente, cambios):
    respuesta = cliente.post("/casos", json=caso_nuevo(cliente, **cambios))

    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["tipo"] == "entrada_invalida"
    assert cliente.get("/casos").json()["total"] == 0


def test_revision_confirma_la_sospecha(cliente):
    caso = registrar(cliente)

    respuesta = cliente.post(
        f"/casos/{caso['id_caso']}/revision",
        json={"decision": "sospecha_confirmada", "revisor": "ana", "comentario": "Patrón raro"},
    )

    assert respuesta.status_code == 200
    revisado = respuesta.json()
    assert revisado["estado"] == "revisado"
    assert revisado["decision_final"] == "sospecha_confirmada"
    assert revisado["revision"]["revisor"] == "ana"
    assert revisado["revision"]["comentario"] == "Patrón raro"
    assert FECHA.match(revisado["revision"]["fecha"])


def test_revision_sin_comentario(cliente):
    caso = registrar(cliente)

    revisado = cliente.post(
        f"/casos/{caso['id_caso']}/revision",
        json={"decision": "sospecha_descartada", "revisor": "luis"},
    ).json()

    assert revisado["decision_final"] == "sospecha_descartada"
    assert revisado["revision"]["comentario"] == ""


def test_revision_de_caso_inexistente(cliente):
    respuesta = cliente.post(
        "/casos/c-000000000000/revision", json={"decision": "sospecha_confirmada", "revisor": "a"}
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["tipo"] == "caso_no_encontrado"


def test_no_se_revisa_dos_veces(cliente):
    caso = registrar(cliente)
    ruta = f"/casos/{caso['id_caso']}/revision"
    cliente.post(ruta, json={"decision": "sospecha_confirmada", "revisor": "ana"})

    respuesta = cliente.post(ruta, json={"decision": "sospecha_descartada", "revisor": "luis"})

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["tipo"] == "caso_ya_revisado"
    guardado = cliente.get("/casos").json()["casos"][0]
    assert guardado["decision_final"] == "sospecha_confirmada"
    assert guardado["revision"]["revisor"] == "ana"


def test_no_se_revisa_un_caso_cerrado(cliente):
    caso = registrar(cliente, nivel="sin_alerta", razones=[])

    revision = {"decision": "sospecha_confirmada", "revisor": "a"}

    respuesta = cliente.post(f"/casos/{caso['id_caso']}/revision", json=revision)

    assert respuesta.status_code == 409


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"decision": "fraude_confirmado", "revisor": "a"},
        {"decision": "sospecha_confirmada", "revisor": ""},
        {"decision": "sospecha_confirmada"},
    ],
)
def test_revision_invalida_no_cambia_el_caso(cliente, cuerpo):
    caso = registrar(cliente)

    respuesta = cliente.post(f"/casos/{caso['id_caso']}/revision", json=cuerpo)

    assert respuesta.status_code == 422
    assert cliente.get("/casos").json()["casos"][0]["estado"] == "pendiente_revision"


def test_listar_del_mas_reciente_al_mas_antiguo_y_filtrar(cliente):
    primero = registrar(cliente)
    registrar(cliente, nivel="sin_alerta", razones=[])
    tercero = registrar(cliente, nivel="revision_recomendada")

    todos = cliente.get("/casos").json()
    pendientes = cliente.get("/casos", params={"estado": "pendiente_revision"}).json()
    uno = cliente.get("/casos", params={"limite": 1}).json()

    assert todos["total"] == 3
    assert todos["casos"][0]["id_caso"] == tercero["id_caso"]
    assert todos["casos"][-1]["id_caso"] == primero["id_caso"]
    assert pendientes["total"] == 2
    assert {c["estado"] for c in pendientes["casos"]} == {"pendiente_revision"}
    assert uno["total"] == 3 and len(uno["casos"]) == 1


@pytest.mark.parametrize("params", [{"estado": "otro"}, {"limite": 0}, {"limite": 1001}])
def test_filtros_invalidos(cliente, params):
    respuesta = cliente.get("/casos", params=params)

    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["tipo"] == "entrada_invalida"


def test_los_casos_persisten_en_sqlite(raiz_api):
    registrar(TestClient(crear_app(raiz_api)))

    otra = TestClient(crear_app(raiz_api))

    assert otra.get("/casos").json()["total"] == 1
    assert (raiz_api / "datos" / "casos" / "casos.sqlite").is_file()


def test_ruta_de_la_base_configurable(raiz_api, tmp_path, monkeypatch):
    ruta = tmp_path / "otra" / "casos.sqlite"
    monkeypatch.setenv("FRAUDE_BD_CASOS", str(ruta))

    registrar(TestClient(crear_app(raiz_api)))

    assert ruta.is_file()


def test_las_senales_se_guardan_tal_como_las_devolvio_evaluar(cliente):
    nuevo = caso_nuevo(cliente)

    caso = cliente.post("/casos", json=nuevo).json()

    assert caso["senales"] == nuevo["senales"]
    assert cliente.get("/casos").json()["casos"][0]["senales"] == nuevo["senales"]


@pytest.mark.parametrize(
    ("ruta", "valor"),
    [
        (("senales", "modelo", "puntuacion"), "NaN"),
        (("senales", "modelo", "umbral_revision"), "Infinity"),
        (("monto",), True),
        (("monto",), "1250"),
        (("senales", "reglas", 0, "activada"), "si"),
    ],
)
def test_caso_con_numeros_no_validos_se_rechaza(cliente, ruta, valor):
    import json

    nuevo = caso_nuevo(cliente)
    nuevo["senales"]["modelo"].update(
        {"evaluable": True, "puntuacion": 0.5, "umbral_revision": 0.4, "umbral_prioritaria": 0.6}
    )
    destino = nuevo
    for clave in ruta[:-1]:
        destino = destino[clave]
    destino[ruta[-1]] = "__VALOR__"
    cuerpo = json.dumps(nuevo).replace(
        '"__VALOR__"', json.dumps(valor) if valor not in ("NaN", "Infinity") else valor
    )

    respuesta = cliente.post("/casos", content=cuerpo, headers={"content-type": "application/json"})

    assert respuesta.status_code == 422, respuesta.text
    assert cliente.get("/casos").json()["total"] == 0
