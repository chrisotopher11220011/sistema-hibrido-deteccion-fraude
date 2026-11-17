"""Transacciones sinteticas de ubicacion (docs/spec.md, secciones 9 y 10; ADR 0006).

El conjunto original no trae ubicacion. Para comprobar la regla de la ponencia que combina
monto alto y ubicacion inusual, se generan transacciones marcadas `origen: "sintetico"`,
sin `variables` y sin etiqueta real. Nunca se mezclan con los datos originales y con ellas
no se mide desempeno: solo se comprueba que la regla se activa cuando debe y deja su razon.
"""

import numpy as np

from fraude.reglas import evaluar_reglas

REGLA = "MONTO_ALTO_UBICACION_INUSUAL"
NOTA = (
    "Prueba funcional con datos sinteticos: comprueba que la regla se activa cuando debe y "
    "deja su razon. No mide desempeno frente a fraude real; estas etiquetas no existen."
)


def generar(
    cantidad: int, semilla: int, paises: list[str], monto_maximo: float, umbral_monto: float
) -> list[dict]:
    """Genera transacciones que recorren, por turnos, las cuatro combinaciones de monto alto
    o bajo y pais igual o distinto del habitual."""
    if len(paises) < 2:
        raise ValueError("hacen falta al menos dos paises")
    if not 0 < umbral_monto < monto_maximo:
        raise ValueError("el umbral debe estar entre 0 y el monto maximo")
    rng = np.random.default_rng(semilla)
    transacciones = []
    for i in range(cantidad):
        alto, distinto = (i % 4) in (0, 1), (i % 4) in (0, 2)
        if alto:
            monto = rng.uniform(umbral_monto + 0.01, monto_maximo)
        else:
            monto = rng.uniform(1.0, umbral_monto)
        habitual = str(rng.choice(paises))
        otros = [p for p in paises if p != habitual]
        actual = str(rng.choice(otros)) if distinto else habitual
        transacciones.append(
            {
                "id_transaccion": f"s-{i + 1:05d}",
                "origen": "sintetico",
                "monto": round(float(monto), 2),
                "ubicacion": {"pais_habitual": habitual, "pais_transaccion": actual},
            }
        )
    return transacciones


def comprobacion_funcional(
    transacciones: list[dict], config_reglas: dict, umbral_monto: float | None = None
) -> dict:
    """Compara la activacion de la regla con la esperada por su definicion (seccion 10)."""
    if umbral_monto is None:
        umbral_monto = float(config_reglas["reglas"][REGLA]["umbral_monto"])
    esperadas = activadas = coinciden = con_razon = 0
    discrepancias = []
    for t in transacciones:
        u = t["ubicacion"]
        esperada = t["monto"] > umbral_monto and u["pais_habitual"] != u["pais_transaccion"]
        regla = next(r for r in evaluar_reglas(t, config_reglas) if r["id"] == REGLA)
        esperadas += esperada
        activadas += regla["activada"]
        con_razon += bool(regla["razon"])
        if regla["activada"] == esperada and regla["evaluable"]:
            coinciden += 1
        else:
            discrepancias.append(
                {"id_transaccion": t["id_transaccion"], "esperada": esperada, "regla": regla}
            )
    return {
        "regla": REGLA,
        "total": len(transacciones),
        "esperadas_activas": esperadas,
        "activadas": activadas,
        "coinciden": coinciden,
        "con_razon": con_razon,
        "discrepancias": discrepancias,
        "correcta": not discrepancias and con_razon == len(transacciones),
        "nota": NOTA,
    }
