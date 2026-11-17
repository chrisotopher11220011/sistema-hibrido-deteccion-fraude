"""Paso `evaluar` (docs/spec.md, secciones 8.8, 15 y 16; ADR 0003 y 0011).

Todo usa la muestra para pruebas: comprueba el procedimiento, no produce resultados.
"""

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from fraude import evaluar as paso
from fraude.configuracion import cargar
from fraude.entrenar import entrenar
from fraude.modelo import ErrorModelo
from fraude.preparar import cargar_preparados, preparar
from fraude.reglas import evaluar_reglas

RAIZ_REPO = Path(__file__).resolve().parents[2]
CONFIGURACIONES = {"solo_reglas", "solo_modelo", "hibrido_cualquier", "hibrido_prioritaria"}
LINEAS_BASE = {"nunca", "azar", "monto"}


def raiz_lista(tmp_path, con_time=True, remuestreos=100):
    shutil.copytree(RAIZ_REPO / "config", tmp_path / "config")
    ruta = tmp_path / "config" / "modelo.yaml"
    config = yaml.safe_load(ruta.read_text())
    config["muestra"]["con_time"] = con_time
    config["evaluacion"]["remuestreos"] = remuestreos
    ruta.write_text(yaml.safe_dump(config))
    preparar(tmp_path, muestra=True)
    entrenar(tmp_path, muestra=True)
    return tmp_path


@pytest.fixture(scope="module")
def evaluado(tmp_path_factory):
    raiz = raiz_lista(tmp_path_factory.mktemp("evaluar"))
    return raiz, paso.evaluar(raiz, muestra=True)


def test_senales_de_reglas_iguales_al_motor():
    config = cargar(RAIZ_REPO, "reglas")
    montos = np.array([0.0, 999.99, 1000.0, 1000.01, 25000.0, 1000.0])
    r, r_alto = paso.senales_reglas(montos, config)
    for monto, activada, alta in zip(montos, r, r_alto, strict=True):
        reglas = evaluar_reglas(
            {"id_transaccion": "x", "origen": "original", "monto": float(monto)}, config
        )
        assert activada == any(x["activada"] for x in reglas)
        assert alta == any(x["activada"] and x["alto_riesgo"] for x in reglas)


def test_cuatro_configuraciones_y_tres_lineas_base_con_intervalos(evaluado):
    _, metricas = evaluado
    principal = metricas["principal"]
    assert set(principal["configuraciones"]) == CONFIGURACIONES
    assert set(principal["lineas_base"]) == LINEAS_BASE
    for grupo in ("configuraciones", "lineas_base"):
        for nombre, entrada in principal[grupo].items():
            assert set(entrada["matriz"]) == {"tp", "fp", "fn", "tn"}, nombre
            for metrica in ("precision", "exhaustividad", "f1"):
                assert set(entrada[metrica]) == {"valor", "ic95"}, (nombre, metrica)
                assert set(entrada[metrica]["ic95"]) == {"inferior", "superior", "indefinidos"}
    assert principal["parte"] == "prueba"
    assert principal["fraudes"] > 0
    nunca = principal["lineas_base"]["nunca"]
    assert nunca["alertas"] == 0 and nunca["precision"]["valor"] is None
    azar = principal["lineas_base"]["azar"]
    assert azar["alertas"] == principal["configuraciones"]["hibrido_cualquier"]["alertas"]


def test_puntuaciones_con_precision_media_y_k_primeros(evaluado):
    _, metricas = evaluado
    puntuaciones = metricas["principal"]["puntuaciones"]
    assert set(puntuaciones) == {"modelo", "monto", "azar"}
    for entrada in puntuaciones.values():
        assert set(entrada) == {"precision_media", "precision_k", "auc_roc"}
        assert entrada["precision_k"]["k"] == metricas["protocolo"]["k_revision"]


def test_umbrales_vienen_de_entrenar_no_de_la_prueba(evaluado):
    raiz, metricas = evaluado
    modelo_json = json.loads((raiz / "resultados" / "en_curso" / "modelo.json").read_text())
    for clave in ("umbral_revision", "umbral_prioritaria"):
        assert metricas["umbrales"][clave] == modelo_json["umbrales"][clave]
    assert metricas["umbrales"]["parte"] == "validacion"


def test_diferencias_pareadas_entre_las_seis_parejas(evaluado):
    _, metricas = evaluado
    diferencias = metricas["principal"]["diferencias"]
    parejas = {(d["a"], d["b"]) for d in diferencias if d["metrica"] == "f1"}
    assert len(parejas) == 6
    assert any(d["metrica"] == "precision_media" for d in diferencias)
    for d in diferencias:
        assert set(d["ic95"]) == {"inferior", "superior", "indefinidos"}


def test_diez_semillas_con_media_y_desviacion(evaluado):
    _, metricas = evaluado
    semillas = metricas["semillas"]
    assert len(semillas["por_semilla"]) == 10
    assert len({s["semilla"] for s in semillas["por_semilla"]}) == 10
    f1 = semillas["resumen"]["hibrido_cualquier"]["f1"]
    assert {"media", "desviacion", "minimo", "maximo", "n"} <= set(f1)
    assert "umbral_revision" in semillas["resumen"]
    for metrica in ("precision_media", "precision_k", "auc_roc"):
        assert {"media", "desviacion"} <= set(semillas["resumen"][metrica]), metrica


def test_particion_temporal_presente_con_time(evaluado):
    _, metricas = evaluado
    temporal = metricas["temporal"]
    assert temporal["estado"] == "ok"
    assert set(temporal["configuraciones"]) == CONFIGURACIONES
    assert temporal["partes"]["prueba"]["filas"] > 0
    assert temporal["partes"]["prueba"]["fraudes"] == temporal["fraudes"]


def test_analisis_de_errores_solo_con_filas_de_validacion(evaluado):
    raiz, _ = evaluado
    _, partes = cargar_preparados(raiz, muestra=True)
    carpeta = raiz / "resultados" / "en_curso" / "analisis_errores"
    total = 0
    for nombre in ("fraudes_no_detectados.csv", "falsas_alarmas.csv"):
        tabla = pd.read_csv(carpeta / nombre)
        assert {"fila", "monto", "puntuacion", "nivel", "reglas_activadas"} <= set(tabla.columns)
        assert {"contribuciones"} <= set(tabla.columns)
        assert set(partes[tabla["fila"].to_numpy(dtype=int)]) <= {"validacion"}
        total += len(tabla)
    resumen = json.loads((carpeta / "resumen.json").read_text())
    assert resumen["parte"] == "validacion" and resumen["reportable"] is False
    assert total == resumen["fraudes_no_detectados"] + resumen["falsas_alarmas"]


def test_archivos_y_avisos_de_la_muestra(evaluado):
    raiz, metricas = evaluado
    en_curso = raiz / "resultados" / "en_curso"
    assert metricas["reportable"] is False and "muestra" in metricas["aviso"].lower()
    comparativa = (en_curso / "comparativa.md").read_text()
    assert "no es un resultado" in comparativa.lower()
    for texto in ("Solo reglas", "Solo Isolation Forest", "Híbrido", "Alertar al azar"):
        assert texto in comparativa
    figuras = sorted(p.name for p in (en_curso / "figuras").glob("*.png"))
    assert figuras == [
        "comparativa_prueba.png",
        "curva_pr_prueba.png",
        "semillas.png",
        "umbral_validacion.png",
    ]
    assert json.loads((en_curso / "metricas.json").read_text())["estado"] == "ok"


def test_sin_time_omite_la_particion_temporal_y_lo_anota(tmp_path):
    raiz = raiz_lista(tmp_path, con_time=False, remuestreos=20)
    metricas = paso.evaluar(raiz, muestra=True)
    assert metricas["temporal"]["estado"] == "omitida"
    assert "Time" in metricas["temporal"]["motivo"]
    assert "Time" in (raiz / "resultados" / "en_curso" / "comparativa.md").read_text()


def test_modelo_de_otros_datos_pide_repetir_entrenar(tmp_path):
    raiz = raiz_lista(tmp_path, remuestreos=20)
    ruta = raiz / "config" / "modelo.yaml"
    config = yaml.safe_load(ruta.read_text())
    config["muestra"]["semilla"] = 99
    ruta.write_text(yaml.safe_dump(config))
    preparar(raiz, muestra=True)
    with pytest.raises(ErrorModelo, match="entrenar"):
        paso.evaluar(raiz, muestra=True)
    informe = json.loads((raiz / "resultados" / "en_curso" / "metricas.json").read_text())
    assert informe["estado"] == "fallo"
