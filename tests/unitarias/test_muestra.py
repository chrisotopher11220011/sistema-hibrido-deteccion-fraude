"""Muestra para pruebas (docs/spec.md, seccion 9). No representa el fraude real."""

import pandas as pd

from fraude.muestra import COLUMNAS, generar


def test_columnas_del_conjunto_real():
    assert ("Time", *[f"V{i}" for i in range(1, 29)], "Amount", "Class") == COLUMNAS
    df = generar(500, 10, semilla=1)
    assert tuple(df.columns) == COLUMNAS


def test_filas_y_fraudes_exactos():
    df = generar(500, 10, semilla=1)
    assert len(df) == 500
    assert int(df["Class"].sum()) == 10
    assert set(df["Class"].unique()) == {0, 1}
    assert df["Class"].dtype.kind == "i"


def test_montos_no_negativos_y_tiempo_creciente():
    df = generar(500, 10, semilla=1)
    assert (df["Amount"] >= 0).all()
    assert df["Time"].is_monotonic_increasing


def test_hay_montos_sobre_el_umbral_de_la_regla():
    """Para que la regla MONTO_ALTO tenga algo que hacer en N1 y N2."""
    df = generar(6000, 60, semilla=7)
    assert (df["Amount"] > 1000).sum() > 0


def test_misma_semilla_mismos_datos():
    pd.testing.assert_frame_equal(generar(300, 5, semilla=3), generar(300, 5, semilla=3))


def test_otra_semilla_otros_datos():
    assert not generar(300, 5, semilla=3).equals(generar(300, 5, semilla=4))


def test_sin_time():
    df = generar(300, 5, semilla=3, con_time=False)
    assert "Time" not in df.columns
    assert len(df.columns) == len(COLUMNAS) - 1
