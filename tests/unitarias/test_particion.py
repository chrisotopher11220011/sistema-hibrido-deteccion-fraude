"""Particion estratificada (docs/spec.md, seccion 9; ADR 0003)."""

import json

import numpy as np
import pytest

from fraude.particion import PARTES, cargar, crear, guardar


@pytest.fixture
def clase():
    c = np.zeros(10_000, dtype=np.int64)
    c[np.random.default_rng(0).choice(10_000, 200, replace=False)] = 1
    return c


def test_partes_y_proporciones(clase):
    partes = crear(clase, semilla=42, prueba=0.30, validacion=0.20)
    assert PARTES == ("ajuste", "validacion", "prueba")
    assert len(partes) == len(clase)
    assert set(partes) == set(PARTES)
    n = len(clase)
    assert (partes == "prueba").sum() == pytest.approx(0.30 * n, abs=2)
    assert (partes == "validacion").sum() == pytest.approx(0.14 * n, abs=2)
    assert (partes == "ajuste").sum() == pytest.approx(0.56 * n, abs=2)


def test_estratificada(clase):
    partes = crear(clase, semilla=42, prueba=0.30, validacion=0.20)
    assert clase[partes == "prueba"].sum() == 60
    assert clase[partes == "validacion"].sum() == 28
    assert clase[partes == "ajuste"].sum() == 112


def test_misma_semilla_misma_particion(clase):
    a = crear(clase, semilla=42, prueba=0.30, validacion=0.20)
    b = crear(clase, semilla=42, prueba=0.30, validacion=0.20)
    assert (a == b).all()


def test_otra_semilla_otra_particion(clase):
    a = crear(clase, semilla=42, prueba=0.30, validacion=0.20)
    b = crear(clase, semilla=43, prueba=0.30, validacion=0.20)
    assert (a != b).any()


def test_guardar_y_cargar(tmp_path, clase):
    partes = crear(clase, semilla=42, prueba=0.30, validacion=0.20)
    meta = guardar(partes, tmp_path / "particion", {"semilla": 42})
    assert (cargar(tmp_path / "particion") == partes).all()
    assert meta["filas"] == {"ajuste": 5600, "validacion": 1400, "prueba": 3000}
    leido = json.loads((tmp_path / "particion" / "particion.json").read_text())
    assert leido["semilla"] == 42 and leido["huella_indices"] == meta["huella_indices"]
    for parte in PARTES:
        indices = np.loadtxt(tmp_path / "particion" / f"{parte}.txt", dtype=np.int64)
        assert (partes[indices] == parte).all()


def test_cargar_sin_particion(tmp_path):
    with pytest.raises(FileNotFoundError):
        cargar(tmp_path / "nada")
