"""Tabla de decision (docs/spec.md, seccion 8.4; ADR 0004).

Copia en Python de la tabla que aplica n8n en el nodo «Clasificar nivel». Sirve para evaluar
fuera de linea y para la prueba de paridad. Una senal «no evaluable» cuenta como no activada.

    R_alto, o (R y A), o A_alta  -> alerta_prioritaria
    R o A                        -> revision_recomendada
    en otro caso                 -> sin_alerta
"""

import numpy as np

ERROR = "error_evaluacion"
PRIORITARIA = "alerta_prioritaria"
REVISION = "revision_recomendada"
SIN_ALERTA = "sin_alerta"


def _nivel(r_alto: bool, r: bool, a: bool, a_alta: bool) -> str:
    if r_alto or (r and a) or a_alta:
        return PRIORITARIA
    if r or a:
        return REVISION
    return SIN_ALERTA


def clasificar(reglas: list[dict] | None, modelo: dict | None) -> str:
    """Nivel de un caso. `reglas=None` significa entrada invalida o evaluacion fallida."""
    if reglas is None:
        return ERROR
    activadas = [r for r in reglas if r.get("evaluable") and r.get("activada")]
    r = bool(activadas)
    r_alto = any(x.get("alto_riesgo") for x in activadas)
    evaluable = bool(modelo) and bool(modelo.get("evaluable"))
    a = evaluable and bool(modelo.get("anomalia"))
    a_alta = evaluable and bool(modelo.get("anomalia_alta"))
    return _nivel(r_alto, r, a, a_alta)


def clasificar_vector(
    r_alto: np.ndarray, r: np.ndarray, a: np.ndarray, a_alta: np.ndarray
) -> np.ndarray:
    """La misma tabla sobre vectores booleanos (evaluacion fuera de linea)."""
    r_alto, r, a, a_alta = (np.asarray(v, dtype=bool) for v in (r_alto, r, a, a_alta))
    prioritaria = r_alto | (r & a) | a_alta
    revision = ~prioritaria & (r | a)
    niveles = np.full(len(r), SIN_ALERTA, dtype=object)
    niveles[revision] = REVISION
    niveles[prioritaria] = PRIORITARIA
    return niveles.astype(str)
