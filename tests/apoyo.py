"""Apoyo comun a las pruebas unitarias y de contrato de la API (fase 4).

`raiz_api` es una raiz de trabajo con la configuracion del repositorio. `entrenar_modelo` deja
un Isolation Forest pequeno, entrenado con datos inventados, donde lo deja el paso `entrenar`.
No representa el fraude real: solo sirve para probar la carga y la forma de las respuestas.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import yaml

from fraude import modelo
from fraude.entrenar import carpeta_modelo

RAIZ_REPO = Path(__file__).resolve().parents[1]
VARIABLES = yaml.safe_load((RAIZ_REPO / "config" / "modelo.yaml").read_text())["variables"]


def fila(valor: float = 0.0) -> dict[str, float]:
    """Una fila con todas las variables del modelo al mismo valor."""
    return {v: float(valor) for v in VARIABLES}


def variables_transaccion(valor: float = 0.0) -> dict[str, float]:
    """`variables` de una transaccion (V1 a V28) al mismo valor."""
    return {f"V{i}": float(valor) for i in range(1, 29)}


def entrenar(
    raiz: Path,
    muestra: bool = True,
    version: str = "v-prueba",
    semilla: int = 0,
    **cambios,
) -> dict:
    generador = np.random.default_rng(semilla)
    X = generador.normal(size=(400, len(VARIABLES)))
    params = {"n_estimators": 20, "max_samples": 64}
    bosque = modelo.entrenar_bosque(X, params, semilla)
    puntuaciones = modelo.puntuar(bosque, X)
    meta = {
        "estado": "ok",
        "fuente": "muestra" if muestra else "real",
        "reportable": not muestra,
        "variables": list(VARIABLES),
        "version": version,
        "umbrales": {
            "umbral_revision": float(np.quantile(puntuaciones, 0.95)),
            "umbral_prioritaria": float(np.quantile(puntuaciones, 0.995)),
        },
        **cambios,
    }
    return modelo.guardar_artefacto(carpeta_modelo(raiz, muestra), bosque, meta)


# --- LLM local de pruebas (fase 7) ----------------------------------------------------------

TEXTO_LLM = (
    "El sistema señala esta transacción como alerta prioritaria: se activó MONTO_ALTO porque "
    "el monto supera el umbral. Una persona debe revisarla."
)


class ServidorLlm:
    """Servidor de pruebas: responde lo que diga `self.texto`, o tarda `self.espera_s`."""

    def __init__(self):
        self.texto = TEXTO_LLM
        self.espera_s = 0.0
        self.codigo = 200
        self.recibidos: list[dict] = []
        servidor = self

        class Manejador(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silencio en las pruebas
                pass

            def do_POST(self):
                largo = int(self.headers.get("Content-Length", 0))
                servidor.recibidos.append(
                    {"ruta": self.path, "cuerpo": json.loads(self.rfile.read(largo))}
                )
                time.sleep(servidor.espera_s)
                cuerpo = json.dumps(
                    {
                        "model": "modelo-de-prueba",
                        "choices": [{"message": {"role": "assistant", "content": servidor.texto}}],
                    }
                ).encode()
                try:
                    self.send_response(servidor.codigo)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(cuerpo)))
                    self.end_headers()
                    self.wfile.write(cuerpo)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self.url = f"http://127.0.0.1:{self.http.server_address[1]}"
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def cerrar(self):
        self.http.shutdown()
        self.http.server_close()
