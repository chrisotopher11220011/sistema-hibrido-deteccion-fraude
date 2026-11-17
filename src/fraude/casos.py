"""Forma de los casos (docs/spec.md, seccion 8.5; ADR 0013; docs/contratos/).

`CasoNuevo` es lo que n8n envia a `POST /casos`: lo que calculo para la transaccion. La API
completa `id_caso`, `estado`, `decision_final` y `revision` (y `fecha_procesamiento` si falta).
`Revision` es la decision de la persona que revisa. El sistema senala para revision; la persona
confirma o descarta la sospecha.
"""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NIVELES = ("error_evaluacion", "alerta_prioritaria", "revision_recomendada", "sin_alerta")
FECHA_UTC = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Respuesta de /evaluar (contrato 8.3), tal como la guarda el caso -----------------------


class Regla(_Estricto):
    id: str = Field(min_length=1)
    evaluable: bool
    activada: bool
    alto_riesgo: bool
    razon: str = Field(min_length=1)


class Contribucion(_Estricto):
    variable: str
    peso: float


class SenalModelo(_Estricto):
    evaluable: bool
    puntuacion: float | None
    umbral_revision: float | None
    umbral_prioritaria: float | None
    anomalia: bool
    anomalia_alta: bool
    contribuciones: list[Contribucion] | None = None


class VersionesEvaluacion(_Estricto):
    reglas: str
    modelo: str | None


class Senales(_Estricto):
    id_transaccion: str = Field(min_length=1)
    reglas: list[Regla]
    modelo: SenalModelo
    versiones: VersionesEvaluacion


# --- Caso -----------------------------------------------------------------------------


class Explicacion(_Estricto):
    texto: str
    origen: Literal["plantilla", "llm"]
    modelo: str | None = None
    duracion_ms: float | None = Field(default=None, ge=0)


class Notificacion(_Estricto):
    canal: str = Field(min_length=1)
    estado: str = Field(min_length=1)
    detalle: str | None = None


class VersionesCaso(_Estricto):
    reglas: str | None
    modelo: str | None
    flujo: str | None


class CasoNuevo(_Estricto):
    id_transaccion: str | None = Field(default=None, max_length=100)
    origen: Literal["original", "sintetico"] | None = None
    monto: float | None = None
    fecha_procesamiento: str | None = Field(default=None, pattern=FECHA_UTC)
    senales: Senales | None = None
    puntuacion: float | None = None
    nivel: Literal[NIVELES]
    razones: list[str]
    explicacion: Explicacion
    notificacion: Notificacion
    versiones: VersionesCaso

    @field_validator("monto", "puntuacion")
    @classmethod
    def _finito(cls, valor: float | None) -> float | None:
        if valor is not None and not math.isfinite(valor):
            raise ValueError("debe ser un numero finito")
        return valor

    @field_validator("razones")
    @classmethod
    def _razones_con_texto(cls, valor: list[str]) -> list[str]:
        if any(not r for r in valor):
            raise ValueError("cada razon debe tener texto")
        return valor

    @model_validator(mode="after")
    def _coherente(self) -> "CasoNuevo":
        if self.nivel != "sin_alerta" and not self.razones:
            raise ValueError("toda alerta lleva al menos una razon registrada")
        if self.nivel != "error_evaluacion":
            campos = ("id_transaccion", "origen", "monto", "senales")
            faltan = [c for c in campos if getattr(self, c) is None or getattr(self, c) == ""]
            if faltan:
                raise ValueError(
                    f"un caso {self.nivel} debe traer {', '.join(faltan)}; "
                    "solo error_evaluacion puede no traerlos"
                )
        return self


class Revision(_Estricto):
    decision: Literal["sospecha_confirmada", "sospecha_descartada"]
    revisor: str = Field(min_length=1, max_length=100)
    comentario: str = Field(default="", max_length=2000)
