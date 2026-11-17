"""Reglas deterministas (docs/spec.md, seccion 10).

Cada regla devuelve si pudo evaluarse, si se activo, si es de alto riesgo y una razon en texto.
Los umbrales y el alto riesgo salen de `config/reglas.yaml`. Una regla que no puede evaluarse
cuenta como no activada y lo dice en su razon (seccion 8.4).
"""

from fraude.transaccion import Transaccion


def _parametros(config: dict, id_regla: str) -> dict:
    try:
        return config["reglas"][id_regla]
    except KeyError as error:
        raise KeyError(f"config/reglas.yaml no define la regla {id_regla}") from error


def _resultado(id_regla: str, params: dict, evaluable: bool, activada: bool, razon: str) -> dict:
    return {
        "id": id_regla,
        "evaluable": evaluable,
        "activada": evaluable and activada,
        "alto_riesgo": bool(params["alto_riesgo"]),
        "razon": razon,
    }


def _admite_origen(params: dict, origen: str) -> bool:
    return origen in params.get("datos", ["original", "sintetico"])


def _monto_alto(t: Transaccion, config: dict) -> dict:
    id_regla = "MONTO_ALTO"
    params = _parametros(config, id_regla)
    umbral = float(params["umbral_monto"])
    if not _admite_origen(params, t.origen):
        razon = f"No evaluable: la regla no se aplica a datos de origen {t.origen}"
        return _resultado(id_regla, params, False, False, razon)
    if t.monto > umbral:
        razon = f"El monto {t.monto:.2f} supera el umbral {umbral:.2f}"
        return _resultado(id_regla, params, True, True, razon)
    razon = f"El monto {t.monto:.2f} no supera el umbral {umbral:.2f}"
    return _resultado(id_regla, params, True, False, razon)


def _monto_alto_ubicacion_inusual(t: Transaccion, config: dict) -> dict:
    id_regla = "MONTO_ALTO_UBICACION_INUSUAL"
    params = _parametros(config, id_regla)
    umbral = float(params["umbral_monto"])
    if not _admite_origen(params, t.origen):
        razon = (
            f"No evaluable: los datos de origen {t.origen} no traen ubicacion real; "
            "la regla solo se comprueba con datos sinteticos"
        )
        return _resultado(id_regla, params, False, False, razon)
    if t.ubicacion is None:
        razon = "No evaluable: la transaccion no trae ubicacion"
        return _resultado(id_regla, params, False, False, razon)
    habitual, actual = t.ubicacion.pais_habitual, t.ubicacion.pais_transaccion
    inusual = habitual != actual
    alto = t.monto > umbral
    if alto and inusual:
        razon = (
            f"El monto {t.monto:.2f} supera el umbral {umbral:.2f} y el pais de la "
            f"transaccion ({actual}) es distinto del habitual ({habitual})"
        )
        return _resultado(id_regla, params, True, True, razon)
    partes = []
    if not alto:
        partes.append(f"el monto {t.monto:.2f} no supera el umbral {umbral:.2f}")
    if not inusual:
        partes.append(f"el pais de la transaccion coincide con el habitual ({habitual})")
    razon = "No se activa: " + " y ".join(partes)
    return _resultado(id_regla, params, True, False, razon)


REGLAS = (_monto_alto, _monto_alto_ubicacion_inusual)


def evaluar_reglas(transaccion: Transaccion | dict, config: dict) -> list[dict]:
    """Evalua todas las reglas, en orden fijo, sobre una transaccion valida."""
    t = (
        transaccion
        if isinstance(transaccion, Transaccion)
        else Transaccion.model_validate(transaccion)
    )
    return [regla(t, config) for regla in REGLAS]


def version(config: dict) -> str:
    """Version de las reglas, la que viaja en `versiones.reglas` (seccion 8.3)."""
    return str(config["version"])
