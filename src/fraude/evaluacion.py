"""Senales de una transaccion: la respuesta de `POST /evaluar` (docs/spec.md, seccion 8.3).

Sin HTTP: la API llama a `evaluar_transaccion` con una transaccion ya validada.

- Las reglas se evaluan siempre (las no evaluables lo dicen en su razon).
- El modelo se evalua si la transaccion trae `variables`. Si las trae y no hay modelo cargado,
  la evaluacion no puede hacerse: `ModeloNoDisponible` (la API responde 503 y n8n marca
  `error_evaluacion`). Si no las trae, el modelo no hacia falta y queda «no evaluable».
- `Amount`, la variable del modelo, es el `monto` de la transaccion.
"""

from fraude import reglas
from fraude.servicio_modelo import ModeloNoDisponible, ServicioModelo
from fraude.transaccion import Transaccion

__all__ = ["ModeloNoDisponible", "evaluar_transaccion"]


def _no_evaluable(estado_modelo: dict) -> dict:
    return {
        "evaluable": False,
        "puntuacion": None,
        "umbral_revision": estado_modelo["umbral_revision"],
        "umbral_prioritaria": estado_modelo["umbral_prioritaria"],
        "anomalia": False,
        "anomalia_alta": False,
    }


def evaluar_transaccion(t: Transaccion, config_reglas: dict, servicio: ServicioModelo) -> dict:
    """Respuesta 8.3 para una transaccion valida."""
    resultado_reglas = reglas.evaluar_reglas(t, config_reglas)
    if t.variables is None:
        estado = servicio.estado()
        resultado_modelo, version_modelo = _no_evaluable(estado), estado["version"]
    else:
        fila = {**t.variables, "Amount": t.monto}
        resultado_modelo, version_modelo = servicio.evaluar_con_version(fila)
    return {
        "id_transaccion": t.id_transaccion,
        "reglas": resultado_reglas,
        "modelo": resultado_modelo,
        "versiones": {"reglas": reglas.version(config_reglas), "modelo": version_modelo},
    }
