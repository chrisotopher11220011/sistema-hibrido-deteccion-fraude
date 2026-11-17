"""Lote de demostracion (docs/spec.md, seccion 12; ADR 0014)."""

import json
import shutil
from pathlib import Path

import pytest

from fraude import lote
from fraude.preparar import cargar_preparados, preparar
from fraude.transaccion import Transaccion

RAIZ_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def raiz(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("lote")
    shutil.copytree(RAIZ_REPO / "config", raiz / "config")
    preparar(raiz, muestra=True)
    return raiz


@pytest.fixture(scope="module")
def generado(raiz):
    return lote.generar(raiz, muestra=True)


def test_es_determinista_y_queda_en_un_archivo_fijo(raiz, generado):
    assert lote.generar(raiz, muestra=True) == generado
    ruta = raiz / "datos" / "muestra" / "demostracion" / "lote.json"
    assert lote.ruta(raiz, muestra=True) == ruta
    assert json.loads(ruta.read_text(encoding="utf-8")) == generado
    assert lote.ruta(raiz, muestra=False) == raiz / "datos" / "demostracion" / "lote.json"


def test_la_muestra_no_es_reportable(generado):
    assert generado["fuente"] == "muestra" and generado["reportable"] is False


def test_trae_fraudes_y_no_fraudes_de_la_parte_de_prueba(raiz, generado):
    df, partes = cargar_preparados(raiz, muestra=True)
    originales = [e for e in generado["elementos"] if e["tipo"] == "original"]
    etiquetas = [e["etiqueta_real"] for e in originales]
    assert 0 in etiquetas and 1 in etiquetas
    for e in originales:
        fila = int(e["fila"])
        assert partes[fila] == "prueba"
        assert e["etiqueta_real"] == int(df["Class"].iloc[fila])
        t = e["transaccion"]
        assert t["monto"] == float(df["Amount"].iloc[fila])
        assert t["variables"]["V14"] == float(df["V14"].iloc[fila])


def test_las_transacciones_nunca_llevan_la_etiqueta(generado):
    for e in generado["elementos"]:
        if e["tipo"] != "invalida":
            assert "Class" not in e["transaccion"]
            Transaccion.model_validate(e["transaccion"])


def test_incluye_sinteticas_de_ubicacion_sin_etiqueta(generado):
    sinteticas = [e for e in generado["elementos"] if e["tipo"] == "sintetico"]
    assert sinteticas
    for e in sinteticas:
        assert e["etiqueta_real"] is None
        assert e["transaccion"]["origen"] == "sintetico"
        assert "ubicacion" in e["transaccion"] and "variables" not in e["transaccion"]


def test_incluye_entradas_invalidas_que_la_api_rechaza(generado):
    invalidas = [e for e in generado["elementos"] if e["tipo"] == "invalida"]
    assert len(invalidas) >= 4
    for e in invalidas:
        assert e["etiqueta_real"] is None and e["descripcion"]
        with pytest.raises(ValueError):
            Transaccion.model_validate(e["transaccion"])
    # Al menos una pasa la validacion de n8n y la rechaza la API (rama 422).
    assert any(e["descripcion"].startswith("variables incompletas") for e in invalidas)


def test_ids_unicos_y_conteos(generado):
    ids = [
        e["transaccion"]["id_transaccion"]
        for e in generado["elementos"]
        if isinstance(e["transaccion"], dict) and "id_transaccion" in e["transaccion"]
    ]
    assert len(ids) == len(set(ids))
    tipos = [e["tipo"] for e in generado["elementos"]]
    assert generado["conteos"] == {
        "total": len(tipos),
        "original": tipos.count("original"),
        "sintetico": tipos.count("sintetico"),
        "invalida": tipos.count("invalida"),
        "fraudes": sum(1 for e in generado["elementos"] if e["etiqueta_real"] == 1),
    }


def test_respeta_la_configuracion(raiz, generado):
    import yaml

    config = yaml.safe_load((raiz / "config" / "modelo.yaml").read_text())["demostracion"]
    conteos = generado["conteos"]
    assert conteos["fraudes"] <= config["fraudes"]
    assert conteos["original"] - conteos["fraudes"] == config["legitimas"]
    assert conteos["sintetico"] == config["sinteticas"]
    assert generado["semilla"] == config["semilla"]


def test_sin_datos_preparados_falla_con_un_mensaje_claro(tmp_path):
    shutil.copytree(RAIZ_REPO / "config", tmp_path / "config")
    with pytest.raises(Exception, match="preparar"):
        lote.generar(tmp_path, muestra=True)
