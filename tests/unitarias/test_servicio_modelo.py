import pytest

from apoyo import fila
from fraude.entrenar import carpeta_modelo
from fraude.servicio_modelo import ModeloNoDisponible, ServicioModelo


def test_sin_modelo_no_esta_cargado_y_dice_que_hacer(raiz_api):
    servicio = ServicioModelo(raiz_api)

    estado = servicio.estado()
    assert estado["cargado"] is False
    assert "entrenar" in estado["motivo"]
    assert estado["fuente"] is None and estado["version"] is None
    assert servicio.disponible() is False
    assert servicio.version() is None


def test_evaluar_sin_modelo_falla(raiz_api):
    with pytest.raises(ModeloNoDisponible, match="entrenar"):
        ServicioModelo(raiz_api).evaluar(fila())


def test_carga_el_modelo_de_la_muestra(raiz_api, entrenar_modelo):
    meta = entrenar_modelo(raiz_api, muestra=True, version="v-muestra")

    estado = ServicioModelo(raiz_api).estado()
    assert estado["cargado"] is True
    assert estado["fuente"] == "muestra"
    assert estado["reportable"] is False
    assert estado["version"] == "v-muestra"
    assert estado["umbral_revision"] == meta["umbrales"]["umbral_revision"]
    assert estado["umbral_prioritaria"] == meta["umbrales"]["umbral_prioritaria"]
    assert estado["motivo"] is None


def test_auto_prefiere_el_modelo_real(raiz_api, entrenar_modelo):
    entrenar_modelo(raiz_api, muestra=True, version="v-muestra")
    entrenar_modelo(raiz_api, muestra=False, version="v-real")

    assert ServicioModelo(raiz_api).estado()["fuente"] == "real"
    assert ServicioModelo(raiz_api).version() == "v-real"
    assert ServicioModelo(raiz_api, modo="muestra").version() == "v-muestra"


def test_modo_real_no_usa_la_muestra(raiz_api, entrenar_modelo):
    entrenar_modelo(raiz_api, muestra=True)

    assert ServicioModelo(raiz_api, modo="real").disponible() is False


def test_modo_desconocido(raiz_api):
    with pytest.raises(ValueError, match="FRAUDE_MODELO"):
        ServicioModelo(raiz_api, modo="otro")


def test_recarga_cuando_entrenar_deja_un_modelo_nuevo(raiz_api, entrenar_modelo):
    servicio = ServicioModelo(raiz_api)
    assert servicio.disponible() is False

    entrenar_modelo(raiz_api, version="v1")
    assert servicio.version() == "v1"

    entrenar_modelo(raiz_api, version="v2", semilla=1)
    assert servicio.version() == "v2"


def test_artefacto_alterado_no_se_carga(raiz_api, entrenar_modelo):
    entrenar_modelo(raiz_api)
    ruta = carpeta_modelo(raiz_api, True) / "modelo.joblib"
    ruta.write_bytes(ruta.read_bytes() + b"x")

    estado = ServicioModelo(raiz_api).estado()
    assert estado["cargado"] is False
    assert "entrenar" in estado["motivo"]


def test_entrenamiento_fallido_no_se_carga(raiz_api, entrenar_modelo):
    entrenar_modelo(raiz_api, estado="fallo")

    estado = ServicioModelo(raiz_api).estado()
    assert estado["cargado"] is False
    assert "entrenar" in estado["motivo"]


def test_variables_distintas_de_la_configuracion_no_se_carga(raiz_api, entrenar_modelo):
    entrenar_modelo(raiz_api, variables=["V1", "Amount"])

    estado = ServicioModelo(raiz_api).estado()
    assert estado["cargado"] is False
    assert "variables" in estado["motivo"]


def test_evaluar_sigue_los_umbrales_de_modelo_json(raiz_api, entrenar_modelo):
    meta = entrenar_modelo(raiz_api)
    servicio = ServicioModelo(raiz_api)
    revision = meta["umbrales"]["umbral_revision"]
    prioritaria = meta["umbrales"]["umbral_prioritaria"]

    for valor in (0.0, 1.5, 3.0, 50.0):
        resultado = servicio.evaluar(fila(valor))
        p = resultado["puntuacion"]
        assert resultado["evaluable"] is True
        assert 0 < p <= 1
        assert resultado["umbral_revision"] == revision
        assert resultado["umbral_prioritaria"] == prioritaria
        assert resultado["anomalia"] is (p >= revision)
        assert resultado["anomalia_alta"] is (p >= prioritaria)


def test_contribuciones_solo_con_anomalia(raiz_api, entrenar_modelo):
    entrenar_modelo(raiz_api)
    servicio = ServicioModelo(raiz_api)

    normal = servicio.evaluar(fila(0.0))
    extrema = servicio.evaluar(fila(50.0))

    assert normal["anomalia"] is False
    assert "contribuciones" not in normal
    assert extrema["anomalia"] is True
    k = 5  # config/modelo.yaml, contribuciones.k
    assert len(extrema["contribuciones"]) == k
    assert all(set(c) == {"variable", "peso"} for c in extrema["contribuciones"])


def test_evaluar_exige_todas_las_variables(raiz_api, entrenar_modelo):
    entrenar_modelo(raiz_api)
    incompleta = fila()
    del incompleta["V3"]

    with pytest.raises(KeyError, match="V3"):
        ServicioModelo(raiz_api).evaluar(incompleta)
