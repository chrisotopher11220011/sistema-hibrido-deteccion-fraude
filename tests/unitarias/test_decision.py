import itertools

import numpy as np
import pytest

from fraude import decision


def esperado(r_alto, r, a, a_alta):
    """La tabla de la seccion 8.4, escrita tal cual."""
    if r_alto or (r and a) or a_alta:
        return "alerta_prioritaria"
    if r or a:
        return "revision_recomendada"
    return "sin_alerta"


def regla(activada, alto_riesgo=False, evaluable=True):
    return {
        "id": "X",
        "evaluable": evaluable,
        "activada": activada,
        "alto_riesgo": alto_riesgo,
        "razon": "",
    }


def modelo(a, a_alta, evaluable=True):
    return {"evaluable": evaluable, "anomalia": a, "anomalia_alta": a_alta}


COMBINACIONES = list(itertools.product([False, True], repeat=4))


@pytest.mark.parametrize("r_alto,r,a,a_alta", COMBINACIONES)
def test_cada_combinacion_da_el_nivel_de_la_tabla(r_alto, r, a, a_alta):
    reglas = [regla(r, False), regla(r_alto, True)]
    assert decision.clasificar(reglas, modelo(a, a_alta)) == esperado(
        r_alto or False, r or r_alto, a, a_alta
    )


def test_vector_coincide_con_la_version_por_caso():
    c = np.array(COMBINACIONES)
    niveles = decision.clasificar_vector(c[:, 0], c[:, 1] | c[:, 0], c[:, 2], c[:, 3])
    for fila, nivel in zip(c, niveles, strict=True):
        r_alto, r, a, a_alta = (bool(v) for v in fila)
        assert nivel == esperado(r_alto, r or r_alto, a, a_alta)


def test_senal_no_evaluable_cuenta_como_no_activada():
    reglas = [regla(True, True, evaluable=False)]
    assert decision.clasificar(reglas, modelo(True, True, evaluable=False)) == "sin_alerta"


def test_sin_modelo_ni_reglas_es_sin_alerta_y_none_es_error():
    assert decision.clasificar([], None) == "sin_alerta"
    assert decision.clasificar(None, None) == "error_evaluacion"
