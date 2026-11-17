"""Datos sinteticos de ubicacion (docs/spec.md, secciones 9 y 10; ADR 0006)."""

from pathlib import Path

from fraude.configuracion import cargar
from fraude.sinteticos import comprobacion_funcional, generar
from fraude.transaccion import Transaccion

RAIZ = Path(__file__).resolve().parents[2]
REGLAS = cargar(RAIZ, "reglas")
PAISES = ["EC", "CO", "US"]


def lote(cantidad=40, semilla=2026):
    return generar(cantidad, semilla, PAISES, monto_maximo=5000, umbral_monto=1000)


def test_todas_son_transacciones_sinteticas_validas_sin_variables():
    for t in lote():
        Transaccion.model_validate(t)
        assert t["origen"] == "sintetico"
        assert "variables" not in t
        assert "Class" not in t
        assert t["id_transaccion"].startswith("s-")


def test_identificadores_unicos():
    ids = [t["id_transaccion"] for t in lote()]
    assert len(ids) == len(set(ids))


def test_cubre_las_cuatro_combinaciones():
    combinaciones = {
        (t["monto"] > 1000, t["ubicacion"]["pais_habitual"] != t["ubicacion"]["pais_transaccion"])
        for t in lote(8)
    }
    assert combinaciones == {(True, True), (True, False), (False, True), (False, False)}


def test_montos_dentro_del_rango():
    assert all(0 < t["monto"] <= 5000 for t in lote())


def test_reproducible():
    assert lote(semilla=1) == lote(semilla=1)
    assert lote(semilla=1) != lote(semilla=2)


def test_comprobacion_funcional_sin_metricas_de_desempeno():
    resultado = comprobacion_funcional(lote(), REGLAS)
    assert resultado["total"] == 40
    assert resultado["coinciden"] == 40
    assert resultado["discrepancias"] == []
    assert resultado["activadas"] == resultado["esperadas_activas"] == 10
    assert resultado["con_razon"] == 40
    assert resultado["correcta"] is True
    claves = " ".join(resultado).lower()
    for prohibida in ("precision", "exhaustividad", "recall", "f1"):
        assert prohibida not in claves
    assert "no mide desempeno" in resultado["nota"].lower()


def test_comprobacion_funcional_detecta_una_discrepancia():
    config = {**REGLAS, "reglas": {**REGLAS["reglas"]}}
    config["reglas"]["MONTO_ALTO_UBICACION_INUSUAL"] = {
        **REGLAS["reglas"]["MONTO_ALTO_UBICACION_INUSUAL"],
        "umbral_monto": 999999,
    }
    resultado = comprobacion_funcional(lote(), config, umbral_monto=1000)
    assert resultado["correcta"] is False
    assert resultado["discrepancias"]
