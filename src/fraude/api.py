"""API del prototipo (docs/spec.md, secciones 8.3, 8.5 y 8.6; ADR 0005 y 0013).

`crear_app` compone la API sobre una raiz de trabajo (por defecto `FRAUDE_RAIZ`, `/trabajo` en
el contenedor). La API usa el modelo que deja `entrenar` y lo recarga cuando cambia, sin
reiniciar el servicio. Toda respuesta que no es 2xx lleva el cuerpo de `errores.py`.
"""

import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from fraude import __version__
from fraude.configuracion import cargar
from fraude.errores import ErrorApi, detalles_validacion, id_del_cuerpo, respuesta_error
from fraude.evaluacion import ModeloNoDisponible, evaluar_transaccion
from fraude.servicio_modelo import ServicioModelo
from fraude.transaccion import Transaccion

registro_api = logging.getLogger("fraude.api")


def fecha_utc(momento: datetime | None = None) -> str:
    """Fecha en UTC, ISO 8601, con sufijo Z."""
    momento = momento or datetime.now(UTC)
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _raiz_por_defecto() -> Path:
    return Path(os.environ.get("FRAUDE_RAIZ", "/trabajo"))


def crear_app(raiz: Path | None = None, modo_modelo: str | None = None) -> FastAPI:
    """API sobre `raiz`. `modo_modelo`: `auto`, `real` o `muestra` (`FRAUDE_MODELO`)."""
    raiz = Path(raiz) if raiz is not None else _raiz_por_defecto()
    servicio = ServicioModelo(raiz, modo_modelo or os.environ.get("FRAUDE_MODELO", "auto"))

    app = FastAPI(
        title="Deteccion hibrida de fraude (prototipo academico)",
        version=__version__,
        docs_url="/documentacion",
        redoc_url=None,
    )
    app.state.raiz = raiz
    app.state.servicio_modelo = servicio

    @app.exception_handler(RequestValidationError)
    async def _entrada_invalida(_: Request, error: RequestValidationError):
        return respuesta_error(
            "entrada_invalida",
            "La entrada no cumple el contrato (docs/contratos/).",
            detalles_validacion(error.errors()),
            id_del_cuerpo(error.body),
        )

    @app.exception_handler(ErrorApi)
    async def _error_api(_: Request, error: ErrorApi):
        return respuesta_error(error.tipo, error.mensaje, error.detalles, error.id_transaccion)

    @app.exception_handler(Exception)
    async def _error_interno(_: Request, error: Exception):
        registro_api.exception("Fallo no previsto en la API")
        return respuesta_error("error_interno", f"Fallo interno de la API: {error}")

    @app.get("/salud")
    def salud() -> dict:
        """Estado del servicio y del modelo."""
        return {
            "estado": "ok",
            "servicio": "api",
            "version": __version__,
            "fecha": fecha_utc(),
            "modelo": servicio.estado(),
        }

    @app.post("/evaluar")
    def evaluar(transaccion: Transaccion) -> dict:
        """Senales de una transaccion: reglas y modelo (contrato 8.3)."""
        id_t = transaccion.id_transaccion
        try:
            return evaluar_transaccion(transaccion, cargar(raiz, "reglas"), servicio)
        except ModeloNoDisponible as error:
            raise ErrorApi("modelo_no_disponible", str(error), id_transaccion=id_t) from error
        except Exception as error:  # noqa: BLE001 - n8n debe recibir un cuerpo de error
            registro_api.exception("Fallo al evaluar %s", id_t)
            mensaje = f"No se pudo evaluar la transaccion: {error}"
            raise ErrorApi("error_interno", mensaje, id_transaccion=id_t) from error

    return app


app = crear_app()
