"""API del prototipo. En la fase 1 solo informa su estado."""

from datetime import UTC, datetime

from fastapi import FastAPI

from fraude import __version__

app = FastAPI(
    title="Deteccion hibrida de fraude (prototipo academico)",
    version=__version__,
    docs_url="/documentacion",
    redoc_url=None,
)


def fecha_utc(momento: datetime | None = None) -> str:
    """Fecha en UTC, ISO 8601, con sufijo Z."""
    momento = momento or datetime.now(UTC)
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@app.get("/salud")
def salud() -> dict:
    """Estado del servicio y del modelo."""
    return {
        "estado": "ok",
        "servicio": "api",
        "version": __version__,
        "fecha": fecha_utc(),
        "modelo": {
            "cargado": False,
            "motivo": "El modelo se entrena a partir de la fase 3; todavia no existe.",
        },
    }
