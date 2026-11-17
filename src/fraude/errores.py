"""Respuesta de error de la API (ADR 0013; docs/contratos/error.schema.json).

Toda respuesta que no es 2xx lleva el mismo cuerpo. En `POST /evaluar`, cualquier respuesta que
no sea 200 significa que la evaluacion fallo: n8n marca el caso `error_evaluacion` y lo deja
pendiente de revision, nunca `sin_alerta` (docs/spec.md, seccion 12).
"""

from fastapi.responses import JSONResponse

CODIGOS = {
    "entrada_invalida": 422,
    "modelo_no_disponible": 503,
    "error_interno": 500,
    "caso_no_encontrado": 404,
    "caso_ya_revisado": 409,
}


class ErrorApi(Exception):
    """Error con tipo del contrato; el manejador de la API lo convierte en respuesta."""

    def __init__(
        self,
        tipo: str,
        mensaje: str,
        detalles: list[dict] | None = None,
        id_transaccion: str | None = None,
    ):
        if tipo not in CODIGOS:
            raise ValueError(f"Tipo de error desconocido: {tipo}")
        super().__init__(mensaje)
        self.tipo = tipo
        self.mensaje = mensaje
        self.detalles = detalles or []
        self.id_transaccion = id_transaccion


def id_del_cuerpo(cuerpo) -> str | None:
    """`id_transaccion` del cuerpo recibido, si venia como texto: sirve para la trazabilidad."""
    if isinstance(cuerpo, dict):
        valor = cuerpo.get("id_transaccion")
        if isinstance(valor, str) and valor:
            return valor[:100]
    return None


def cuerpo_error(
    tipo: str, mensaje: str, detalles: list[dict] | None = None, id_transaccion: str | None = None
) -> dict:
    return {
        "id_transaccion": id_transaccion,
        "error": {"tipo": tipo, "mensaje": mensaje, "detalles": list(detalles or [])},
    }


def respuesta_error(
    tipo: str, mensaje: str, detalles: list[dict] | None = None, id_transaccion: str | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=CODIGOS[tipo],
        content=cuerpo_error(tipo, mensaje, detalles, id_transaccion),
    )


def detalles_validacion(errores: list[dict]) -> list[dict]:
    """Errores de Pydantic en una forma que siempre puede pasarse a JSON."""
    return [
        {
            "campo": ".".join(str(parte) for parte in e.get("loc", ()) if parte != "body")
            or "(cuerpo)",
            "mensaje": str(e.get("msg", "valor no valido")),
            "tipo": str(e.get("type", "")),
        }
        for e in errores
    ]
