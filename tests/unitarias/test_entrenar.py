"""Paso `entrenar` (docs/spec.md, secciones 8.8 y 11; ADR 0003 y 0008)."""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import yaml

from fraude import entrenar as paso
from fraude import modelo
from fraude.datos import ErrorDatos
from fraude.preparar import cargar_preparados, preparar

RAIZ_REPO = Path(__file__).resolve().parents[2]


def raiz_con_muestra(tmp_path, **muestra):
    shutil.copytree(RAIZ_REPO / "config", tmp_path / "config")
    if muestra:
        ruta = tmp_path / "config" / "modelo.yaml"
        config = yaml.safe_load(ruta.read_text())
        config["muestra"].update(muestra)
        ruta.write_text(yaml.safe_dump(config))
    preparar(tmp_path, muestra=True)
    return tmp_path


@pytest.fixture(scope="module")
def entrenado(tmp_path_factory):
    raiz = raiz_con_muestra(tmp_path_factory.mktemp("entrenar"))
    return raiz, paso.entrenar(raiz, muestra=True)


def test_solo_ajusta_con_la_parte_de_ajuste(tmp_path, monkeypatch):
    raiz = raiz_con_muestra(tmp_path)
    vistos = []
    original = modelo.entrenar_bosque

    def espia(X, params, semilla):
        vistos.append(np.asarray(X))
        return original(X, params, semilla)

    monkeypatch.setattr(paso.modelo, "entrenar_bosque", espia)
    paso.entrenar(raiz, muestra=True)
    df, partes = cargar_preparados(raiz, muestra=True)
    variables = yaml.safe_load((raiz / "config" / "modelo.yaml").read_text())["variables"]
    assert len(vistos) == 1
    assert np.array_equal(vistos[0], df.loc[partes == "ajuste", variables].to_numpy())


def test_umbrales_salen_de_validacion(entrenado):
    raiz, informe = entrenado
    df, partes = cargar_preparados(raiz, muestra=True)
    bosque, _ = modelo.cargar_artefacto(raiz / "datos" / "muestra" / "modelo")
    validacion = df[partes == "validacion"]
    p = modelo.puntuar(bosque, validacion[informe["variables"]].to_numpy())
    esperados = modelo.elegir_umbrales(validacion["Class"].to_numpy(), p)
    assert informe["umbrales"]["umbral_revision"] == esperados["umbral_revision"]
    assert informe["umbrales"]["umbral_prioritaria"] == esperados["umbral_prioritaria"]
    assert informe["umbrales"]["parte"] == "validacion"


def test_modelo_json_completo_y_marcado_no_reportable(entrenado):
    raiz, informe = entrenado
    for clave in (
        "version",
        "parametros",
        "semilla",
        "umbrales",
        "datos",
        "versiones",
        "tiempo_entrenamiento_s",
        "contribuciones",
    ):
        assert clave in informe
    assert informe["estado"] == "ok"
    assert informe["reportable"] is False and "muestra" in informe["aviso"].lower()
    assert informe["datos"]["sha256_contenido"]
    assert informe["datos"]["huella_particion"]
    assert "shap" in informe["versiones"] and "scikit-learn" in informe["versiones"]
    en_curso = json.loads((raiz / "resultados" / "en_curso" / "modelo.json").read_text())
    assert en_curso["version"] == informe["version"]


def test_sin_preparar_falla_y_lo_deja_escrito(tmp_path):
    shutil.copytree(RAIZ_REPO / "config", tmp_path / "config")
    with pytest.raises(ErrorDatos, match="preparar"):
        paso.entrenar(tmp_path, muestra=True)
    informe = json.loads((tmp_path / "resultados" / "en_curso" / "modelo.json").read_text())
    assert informe["estado"] == "fallo"
