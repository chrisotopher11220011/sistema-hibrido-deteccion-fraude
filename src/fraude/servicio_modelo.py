"""Modelo que usa la API (docs/spec.md, secciones 8.3 y 11; ADR 0013).

La API arranca antes de que `entrenar` deje el modelo, asi que no lo carga una sola vez: en
cada consulta compara la firma de los archivos del artefacto y, si cambio, lo vuelve a cargar.
Un artefacto que no supera las comprobaciones no se carga y `estado()` dice por que.

Que modelo se usa (`FRAUDE_MODELO`):

- `auto` (por defecto): el del conjunto real si existe; si no, el de la muestra.
- `real` o `muestra`: solo ese.

La puntuacion prioriza la revision humana; no prueba el fraude.
"""

import hashlib
import threading
from pathlib import Path

import numpy as np

from fraude import modelo
from fraude.configuracion import cargar
from fraude.contribuciones import Explicador
from fraude.entrenar import carpeta_modelo

MODOS = ("auto", "real", "muestra")
_SIN_CARGAR = object()  # Firma inicial: obliga a cargar en la primera consulta.
SIN_MODELO = (
    "No hay modelo entrenado. Ejecuta el paso entrenar (./fraude todo o ./fraude entrenar); "
    "la API lo cargara sola en la siguiente consulta."
)


class ModeloNoDisponible(Exception):
    """La transaccion necesita el modelo y no hay uno cargado."""


class _Cargado:
    def __init__(self, bosque, meta: dict, fuente: str, k: int):
        self.bosque = bosque
        self.meta = meta
        self.fuente = fuente
        self.variables = list(meta["variables"])
        self.umbral_revision = float(meta["umbrales"]["umbral_revision"])
        self.umbral_prioritaria = float(meta["umbrales"]["umbral_prioritaria"])
        self.k = k
        self._explicador: Explicador | None = None

    def explicador(self) -> Explicador:
        if self._explicador is None:
            self._explicador = Explicador(self.bosque)
        return self._explicador


def _firma_archivo(ruta: Path) -> tuple | None:
    try:
        datos = ruta.stat()
    except OSError:
        return None
    return (datos.st_mtime_ns, datos.st_size)


class ServicioModelo:
    """Carga, recarga y usa el Isolation Forest que deja `entrenar`."""

    def __init__(self, raiz: Path, modo: str = "auto"):
        if modo not in MODOS:
            raise ValueError(f"FRAUDE_MODELO debe ser uno de {', '.join(MODOS)}; llego {modo!r}")
        self.raiz = Path(raiz)
        self.modo = modo
        self._candado = threading.Lock()
        self._firma: object = _SIN_CARGAR
        self._cargado: _Cargado | None = None
        self._motivo: str = SIN_MODELO

    # --- Carga --------------------------------------------------------------------------

    def _elegir(self) -> tuple[str, Path] | None:
        opciones = {"auto": ("real", "muestra"), "real": ("real",), "muestra": ("muestra",)}
        for fuente in opciones[self.modo]:
            carpeta = carpeta_modelo(self.raiz, fuente == "muestra")
            if (carpeta / modelo.ARCHIVO_META).is_file():
                return fuente, carpeta
        return None

    def _firma_actual(self, eleccion: tuple[str, Path] | None) -> tuple | None:
        if eleccion is None:
            return None
        fuente, carpeta = eleccion
        meta = carpeta / modelo.ARCHIVO_META
        try:
            contenido = hashlib.sha256(meta.read_bytes()).hexdigest()
        except OSError:
            contenido = None
        return (fuente, str(carpeta), contenido, _firma_archivo(carpeta / modelo.ARCHIVO_MODELO))

    def _cargar(self, eleccion: tuple[str, Path] | None) -> None:
        self._cargado = None
        if eleccion is None:
            self._motivo = SIN_MODELO
            return
        fuente, carpeta = eleccion
        try:
            config = cargar(self.raiz, "modelo")
            bosque, meta = modelo.cargar_artefacto(carpeta)
            if meta.get("estado") != "ok":
                raise modelo.ErrorModelo(
                    "El ultimo entrenamiento no termino bien: repite el paso entrenar."
                )
            if list(meta.get("variables", [])) != list(config["variables"]):
                raise modelo.ErrorModelo(
                    "Las variables del modelo no son las de config/modelo.yaml: "
                    "repite el paso entrenar."
                )
            k = int(config["contribuciones"]["k"])
            self._cargado = _Cargado(bosque, meta, fuente, k)
            self._motivo = None
        except Exception as error:  # noqa: BLE001 - el motivo se informa en /salud
            self._motivo = f"Modelo de {carpeta} no cargado: {error}"

    def _actualizar(self) -> _Cargado | None:
        with self._candado:
            eleccion = self._elegir()
            firma = self._firma_actual(eleccion)
            if firma != self._firma:
                self._cargar(eleccion)
                self._firma = firma
            return self._cargado

    # --- Consulta -----------------------------------------------------------------------

    def disponible(self) -> bool:
        return self._actualizar() is not None

    def version(self) -> str | None:
        cargado = self._actualizar()
        return str(cargado.meta["version"]) if cargado else None

    def estado(self) -> dict:
        cargado = self._actualizar()
        if cargado is None:
            return {
                "cargado": False,
                "fuente": None,
                "version": None,
                "reportable": None,
                "umbral_revision": None,
                "umbral_prioritaria": None,
                "motivo": self._motivo,
            }
        return {
            "cargado": True,
            "fuente": cargado.fuente,
            "version": str(cargado.meta["version"]),
            "reportable": bool(cargado.meta.get("reportable", cargado.fuente == "real")),
            "umbral_revision": cargado.umbral_revision,
            "umbral_prioritaria": cargado.umbral_prioritaria,
            "motivo": None,
        }

    def umbrales(self) -> tuple[float | None, float | None]:
        cargado = self._actualizar()
        if cargado is None:
            return None, None
        return cargado.umbral_revision, cargado.umbral_prioritaria

    def evaluar(self, fila: dict[str, float]) -> dict:
        """Parte `modelo` de la respuesta 8.3 para una fila con todas las variables."""
        cargado = self._actualizar()
        if cargado is None:
            raise ModeloNoDisponible(self._motivo)
        faltan = [v for v in cargado.variables if v not in fila]
        if faltan:
            raise KeyError(f"Faltan variables del modelo: {', '.join(faltan)}")
        X = np.array([[float(fila[v]) for v in cargado.variables]], dtype=np.float64)
        puntuacion = float(modelo.puntuar(cargado.bosque, X)[0])
        resultado = {
            "evaluable": True,
            "puntuacion": puntuacion,
            "umbral_revision": cargado.umbral_revision,
            "umbral_prioritaria": cargado.umbral_prioritaria,
            "anomalia": puntuacion >= cargado.umbral_revision,
            "anomalia_alta": puntuacion >= cargado.umbral_prioritaria,
        }
        if resultado["anomalia"]:
            explicador = cargado.explicador()
            resultado["contribuciones"] = explicador.contribuciones(
                X, cargado.variables, cargado.k
            )[0]
        return resultado
