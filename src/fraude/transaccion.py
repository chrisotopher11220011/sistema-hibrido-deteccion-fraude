"""Forma de una transaccion (docs/spec.md, seccion 8.2).

La etiqueta real (`Class`) nunca viaja en la transaccion: cualquier campo extra se rechaza.
"""

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VARIABLES = tuple(f"V{i}" for i in range(1, 29))


class Ubicacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pais_habitual: str = Field(pattern=r"^[A-Z]{2}$", strict=True)
    pais_transaccion: str = Field(pattern=r"^[A-Z]{2}$", strict=True)


class Transaccion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_transaccion: str = Field(min_length=1, max_length=100)
    origen: Literal["original", "sintetico"]
    # Estrictos: el contrato exige numeros JSON; un booleano o un texto no se convierten.
    monto: float = Field(ge=0, strict=True)
    variables: dict[str, Annotated[float, Field(strict=True)]] | None = None
    ubicacion: Ubicacion | None = None

    @field_validator("monto")
    @classmethod
    def _monto_finito(cls, valor: float) -> float:
        if not math.isfinite(valor):
            raise ValueError("el monto debe ser un numero finito")
        return valor

    @field_validator("variables")
    @classmethod
    def _variables_completas(cls, valor: dict[str, float] | None) -> dict[str, float] | None:
        if valor is None:
            return valor
        if set(valor) != set(VARIABLES):
            raise ValueError("variables debe traer exactamente V1 a V28")
        if not all(math.isfinite(v) for v in valor.values()):
            raise ValueError("las variables deben ser numeros finitos")
        return valor

    @model_validator(mode="after")
    def _sintetico_sin_variables(self) -> "Transaccion":
        if self.origen == "sintetico" and self.variables is not None:
            raise ValueError("una transaccion sintetica no lleva variables del conjunto original")
        return self
