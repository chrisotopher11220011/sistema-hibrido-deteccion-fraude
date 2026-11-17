"""Analisis exploratorio de la parte de ajuste (docs/spec.md, secciones 9 y 16)."""

import json

import pytest

from fraude.eda import escribir, resumir
from fraude.muestra import generar


@pytest.fixture
def ajuste():
    return generar(2000, 40, semilla=5)


def test_resumen_conteos(ajuste):
    r = resumir(ajuste, umbral_monto=1000)
    assert r["filas"] == 2000 and r["fraudes"] == 40
    assert r["tasa_fraude"] == pytest.approx(0.02)
    assert r["parte"] == "ajuste"
    assert r["tiene_time"] is True


def test_resumen_montos_por_clase(ajuste):
    r = resumir(ajuste, umbral_monto=1000)
    legitimas = ajuste.loc[ajuste["Class"] == 0, "Amount"]
    assert r["monto"]["legitima"]["mediana"] == pytest.approx(legitimas.median())
    assert set(r["monto"]["fraude"]) == {"n", "media", "mediana", "p95", "minimo", "maximo"}


def test_resumen_montos_sobre_el_umbral(ajuste):
    r = resumir(ajuste, umbral_monto=1000)
    s = r["sobre_umbral"]
    assert s["umbral"] == 1000
    assert s["legitimas"] == int(((ajuste["Amount"] > 1000) & (ajuste["Class"] == 0)).sum())
    assert s["fraudes"] == int(((ajuste["Amount"] > 1000) & (ajuste["Class"] == 1)).sum())


def test_resumen_separacion_ordenada_por_variable(ajuste):
    sep = resumir(ajuste, umbral_monto=1000)["separacion"]
    assert len(sep) == 29
    assert {s["variable"] for s in sep} == {*(f"V{i}" for i in range(1, 29)), "Amount"}
    valores = [abs(s["diferencia_estandarizada"]) for s in sep]
    assert valores == sorted(valores, reverse=True)


def test_resumen_sin_time_lo_anota(ajuste):
    r = resumir(ajuste.drop(columns="Time"), umbral_monto=1000)
    assert r["tiene_time"] is False
    assert any("Time" in nota for nota in r["notas"])


def test_escribir_deja_resumen_y_figuras(tmp_path, ajuste):
    archivos = escribir(ajuste, 1000, tmp_path / "eda")
    assert {"resumen.json", "resumen.md"} <= set(archivos)
    figuras = [a for a in archivos if a.endswith(".png")]
    assert len(figuras) >= 3
    for nombre in archivos:
        assert (tmp_path / "eda" / nombre).stat().st_size > 0
    resumen = json.loads((tmp_path / "eda" / "resumen.json").read_text())
    assert resumen["figuras"] == figuras
    assert "ajuste" in (tmp_path / "eda" / "resumen.md").read_text()


def test_escribir_sin_time_omite_la_figura_temporal(tmp_path, ajuste):
    con = escribir(ajuste, 1000, tmp_path / "con")
    sin = escribir(ajuste.drop(columns="Time"), 1000, tmp_path / "sin")
    assert any("hora" in a for a in con)
    assert not any("hora" in a for a in sin)
