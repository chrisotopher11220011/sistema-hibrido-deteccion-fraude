"""Rutas de la pagina de simulacion (docs/spec.md, secciones 8.6 y 13; ADR 0007 y 0015).

- `GET /` sirve `web/index.html` y `/recursos/` el resto de `web/`.
- `GET /simulacion/lote` sirve el lote de demostracion con la etiqueta real, solo para que la
  pagina la muestre **despues** del veredicto.
- `POST /simulacion/transacciones` y `POST /simulacion/revisiones` reenvian a los webhooks de
  n8n por la red interna de Compose: la pagina nunca llama a n8n (ADR 0007).

Cada intercambio queda en `resultados/en_curso/simulacion.jsonl`; `tareas evidencia` lo
convierte en `simulacion.json`. La etiqueta real nunca viaja hacia n8n: un cuerpo que la trae
se rechaza sin reenviarlo.
"""

import json
import os
import re
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from fraude import lote
from fraude.demostrar import pedir_http
from fraude.errores import cuerpo_error, id_del_cuerpo, respuesta_error

CAMPO_ETIQUETA = "etiqueta_real"
PATRON_SESION = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SIN_CACHE = {"cache-control": "no-cache"}


def carpeta_web() -> Path:
    """`web/` del repositorio, o `FRAUDE_WEB` (en la imagen, `/app/web`)."""
    variable = os.environ.get("FRAUDE_WEB")
    if variable:
        return Path(variable)
    return Path(__file__).resolve().parents[2] / "web"


def ruta_registro(raiz: Path) -> Path:
    return Path(raiz) / "resultados" / "en_curso" / "simulacion.jsonl"


def _fecha() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"


class Registro:
    """Anota cada intercambio de la pagina, una linea JSON por intercambio."""

    def __init__(self, raiz: Path):
        self.ruta = ruta_registro(raiz)
        self._candado = threading.Lock()

    def anotar(self, entrada: dict) -> None:
        linea = json.dumps(entrada, ensure_ascii=False) + "\n"
        with self._candado:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            with self.ruta.open("a", encoding="utf-8") as archivo:
                archivo.write(linea)


def _sesion(valor: str | None) -> str | None:
    return valor if valor and PATRON_SESION.match(valor) else None


def _numero(valor: str | None) -> int | None:
    if valor is None or not valor.isdigit() or len(valor) > 9:
        return None
    return int(valor)


def _sin_etiqueta(cuerpo):
    if isinstance(cuerpo, dict) and CAMPO_ETIQUETA in cuerpo:
        return {k: v for k, v in cuerpo.items() if k != CAMPO_ETIQUETA}
    return cuerpo


def elegir_lote(raiz: Path, servicio) -> Path | None:
    """El lote de la fuente del modelo cargado; sin modelo, segun `FRAUDE_MODELO`."""
    estado = servicio.estado()
    if estado.get("cargado"):
        opciones = (estado["fuente"],)
    else:
        opciones = {"auto": ("real", "muestra"), "real": ("real",), "muestra": ("muestra",)}[
            servicio.modo
        ]
    for fuente in opciones:
        archivo = lote.ruta(raiz, fuente == "muestra")
        if archivo.is_file():
            return archivo
    return None


def montar(
    app: FastAPI,
    raiz: Path,
    servicio,
    url_n8n: str | None = None,
    pedir: Callable | None = None,
    reloj: Callable[[], float] = time.perf_counter,
) -> None:
    """Anade la pagina y las rutas `/simulacion/*` a la API."""
    raiz = Path(raiz)
    web = carpeta_web()
    url_n8n = (url_n8n or os.environ.get("FRAUDE_URL_N8N", "http://n8n:5678")).rstrip("/")
    pedir = pedir or pedir_http
    registro = Registro(raiz)
    router = APIRouter()

    @router.get("/", include_in_schema=False)
    def pagina():
        return FileResponse(web / "index.html", media_type="text/html", headers=SIN_CACHE)

    @router.get("/simulacion/lote")
    def lote_demostracion():
        archivo = elegir_lote(raiz, servicio)
        if archivo is None:
            return respuesta_error(
                "lote_no_disponible",
                "Aun no hay lote de demostracion. Ejecuta antes: ./fraude todo",
            )
        return FileResponse(archivo, media_type="application/json", headers=SIN_CACHE)

    def _reenviar(webhook: str, ruta: str, request: Request, crudo: bytes) -> JSONResponse:
        sesion = _sesion(request.query_params.get("sesion"))
        numero = _numero(request.query_params.get("n"))
        entrada = {
            "fecha": _fecha(),
            "sesion": sesion,
            "n": numero,
            "ruta": ruta,
            "enviado": None,
            "codigo": None,
            "respuesta": None,
            "latencia_ms": None,
        }
        try:
            cuerpo = json.loads(crudo)
        except ValueError:
            entrada["enviado"] = crudo[:2000].decode("utf-8", "replace")
            codigo, salida = 422, cuerpo_error("entrada_invalida", "El cuerpo no es JSON.")
        else:
            entrada["enviado"] = _sin_etiqueta(cuerpo)
            id_t = id_del_cuerpo(cuerpo)
            if isinstance(cuerpo, dict) and CAMPO_ETIQUETA in cuerpo:
                codigo, salida = (
                    422,
                    cuerpo_error(
                        "etiqueta_en_transaccion",
                        "La etiqueta real no puede viajar al flujo de evaluacion: "
                        "envia solo la transaccion.",
                        id_transaccion=id_t,
                    ),
                )
            else:
                inicio = reloj()
                codigo, salida = _pedir_n8n(pedir, f"{url_n8n}{webhook}", cuerpo, id_t)
                entrada["latencia_ms"] = round((reloj() - inicio) * 1000, 1)
        entrada["codigo"], entrada["respuesta"] = codigo, salida
        registro.anotar(entrada)
        return JSONResponse(status_code=codigo, content=salida)

    @router.post("/simulacion/transacciones")
    async def transacciones(request: Request):
        """Reenvia la transaccion al webhook de evaluacion y devuelve el caso."""
        # En un hilo aparte: n8n llama a /evaluar y /casos de esta misma API mientras se
        # espera su respuesta; bloquear el bucle de eventos aqui seria un interbloqueo.
        crudo = await request.body()
        return await run_in_threadpool(
            _reenviar, "/webhook/transaccion", "transacciones", request, crudo
        )

    @router.post("/simulacion/revisiones")
    async def revisiones(request: Request):
        """Reenvia la decision del revisor al webhook de revision humana."""
        crudo = await request.body()
        return await run_in_threadpool(_reenviar, "/webhook/revision", "revisiones", request, crudo)

    app.include_router(router)
    app.mount("/recursos", StaticFiles(directory=web), name="recursos")


def _pedir_n8n(pedir: Callable, url: str, cuerpo, id_t: str | None) -> tuple[int, object]:
    mensaje = (
        "n8n no respondio. Comprueba los servicios con ./fraude estado; si n8n esta detenido, "
        "vuelve a ejecutar ./fraude todo."
    )
    try:
        codigo, salida = pedir("POST", url, cuerpo)
    except Exception as error:  # noqa: BLE001 - red, tiempo limite o n8n detenido
        detalle = [{"motivo": f"{type(error).__name__}: {error}"}]
        return 502, cuerpo_error("n8n_no_disponible", mensaje, detalle, id_t)
    if not isinstance(salida, dict):
        detalle = [{"codigo_n8n": codigo, "cuerpo": str(salida)[:500]}]
        return 502, cuerpo_error("n8n_no_disponible", mensaje, detalle, id_t)
    return codigo, salida
