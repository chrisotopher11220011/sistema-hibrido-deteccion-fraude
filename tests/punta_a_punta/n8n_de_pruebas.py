"""n8n de pruebas para N1: sirve los webhooks ejecutando los flujos REALES con el simulador.

Solo para el entorno de Claude, donde no hay Docker (docs/ESTADO.md). Ejecuta
`n8n/flujos/evaluacion.json` y `revision.json` con `tests/n8n/simulador.mjs` (fase 5) y hace de
verdad las peticiones HTTP que el flujo pide a la API, para que la pagina pueda probarse y
fotografiarse en N1 contra una API en marcha. En N2 se usa n8n 2.47.7 real.

Uso: python tests/punta_a_punta/n8n_de_pruebas.py --puerto 5678 --api http://127.0.0.1:8000
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "n8n"))
from simulacion import simular  # noqa: E402

API_INTERNA = "http://api:8000"


def _http(metodo: str, url: str, cuerpo=None) -> dict:
    """Respuesta en el formato del simulador: `{statusCode, body}` o `{error}`."""
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    peticion = urllib.request.Request(
        url, data=datos, method=metodo, headers={"content-type": "application/json"}
    )
    try:
        with urllib.request.urlopen(peticion, timeout=30) as r:
            codigo, texto = r.status, r.read()
    except urllib.error.HTTPError as error:
        codigo, texto = error.code, error.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        return {"error": {"message": f"{type(error).__name__}: {error}"}}
    try:
        return {"statusCode": codigo, "body": json.loads(texto)}
    except ValueError:
        return {"statusCode": codigo, "body": texto.decode(errors="replace")}


def _reales(api: str, pedidas: list[dict], nodo: str) -> list[dict]:
    respuestas = []
    for p in pedidas:
        if p["nodo"] == nodo:
            respuesta = _http(p["metodo"], p["url"].replace(API_INTERNA, api), p.get("cuerpo"))
            respuestas.append(respuesta)
            if "error" not in respuesta:
                break
    return respuestas


def evaluar(api: str, cuerpo) -> dict:
    evaluacion = _http("POST", f"{api}/evaluar", cuerpo)
    # Ante un fallo de red el flujo reintenta: cada intento recibe el mismo fallo.
    evaluacion_cola = [evaluacion] * 5 if "error" in evaluacion else [evaluacion]
    marcador = [{"statusCode": 201, "body": {}}]
    primero = simular(
        "evaluacion.json",
        cuerpo,
        {"Consultar evaluación": list(evaluacion_cola), "Registrar caso": marcador},
    )
    registro = _reales(api, primero["peticiones"], "Registrar caso")
    if not registro:
        return primero["respuesta"]
    segundo = simular(
        "evaluacion.json",
        cuerpo,
        {"Consultar evaluación": list(evaluacion_cola), "Registrar caso": registro},
    )
    return segundo["respuesta"]


def revisar(api: str, cuerpo) -> dict:
    marcador = [{"statusCode": 200, "body": {}}]
    primero = simular("revision.json", cuerpo, {"Guardar revisión": marcador})
    reales = _reales(api, primero["peticiones"], "Guardar revisión")
    if not reales:
        return primero["respuesta"]
    return simular("revision.json", cuerpo, {"Guardar revisión": reales})["respuesta"]


def crear_manejador(api: str):
    class Manejador(BaseHTTPRequestHandler):
        def _responder(self, codigo: int, cuerpo) -> None:
            datos = json.dumps(cuerpo).encode()
            self.send_response(codigo)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def do_GET(self):  # noqa: N802
            if self.path == "/webhook/ping":
                self._responder(200, {"estado": "ok", "servicio": "n8n de pruebas (N1)"})
            else:
                self._responder(404, {"message": "no existe"})

        def do_POST(self):  # noqa: N802
            longitud = int(self.headers.get("content-length", 0))
            try:
                cuerpo = json.loads(self.rfile.read(longitud) or b"null")
            except ValueError:
                self._responder(422, {"message": "JSON mal formado"})
                return
            if self.path == "/webhook/transaccion":
                respuesta = evaluar(api, cuerpo)
            elif self.path == "/webhook/revision":
                respuesta = revisar(api, cuerpo)
            else:
                self._responder(404, {"message": "no existe"})
                return
            if respuesta is None:
                self._responder(500, {"message": "El flujo no respondio"})
            else:
                self._responder(respuesta["codigo"], respuesta["cuerpo"])

        def log_message(self, formato, *args):  # silencio
            return

    return Manejador


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--puerto", type=int, default=5678)
    argumentos.add_argument("--api", default="http://127.0.0.1:8000")
    a = argumentos.parse_args()
    servidor = ThreadingHTTPServer(("127.0.0.1", a.puerto), crear_manejador(a.api.rstrip("/")))
    print(f"n8n de pruebas en http://127.0.0.1:{a.puerto} (flujos reales con el simulador)")
    servidor.serve_forever()


if __name__ == "__main__":
    main()
