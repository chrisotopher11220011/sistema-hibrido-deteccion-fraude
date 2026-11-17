"""Comprueba, en la CI, los flujos de n8n en marcha dentro de Compose (N2, fase 5).

Modos:

- `--sin-modelo` (recien arrancado, antes de `todo`): la API aun no tiene modelo. Una
  transaccion con `variables` no puede evaluarse (503) y n8n la registra en
  `error_evaluacion`; una entrada invalida tambien; las sinteticas se evaluan solo con reglas.
  Tambien recorre el flujo de revision: 200, 409, 404 y 422.
- `--api-detenida` (con `docker compose stop api`): el webhook responde 502 con el caso
  calculado en `error_evaluacion` y no se queda colgado.

Solo usa la biblioteca estandar: el trabajo de la CI no instala dependencias del proyecto.

Uso: python tests/punta_a_punta/comprobar_flujos.py --sin-modelo|--api-detenida [url_n8n] [url_api]
"""

import json
import sys
import time
import urllib.error
import urllib.request

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
URL_N8N = ARGS[0] if ARGS else "http://127.0.0.1:5678"
URL_API = ARGS[1] if len(ARGS) > 1 else "http://127.0.0.1:8000"
VERSION_FLUJO_PREFIJO = "transaccion-"


def pedir(metodo: str, url: str, cuerpo=None, timeout: float = 90) -> tuple[int, object, float]:
    if isinstance(cuerpo, bytes):
        datos = cuerpo  # cuerpo crudo, sin serializar
    else:
        datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    peticion = urllib.request.Request(
        url, data=datos, method=metodo, headers={"content-type": "application/json"}
    )
    inicio = time.monotonic()
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            codigo, texto = respuesta.status, respuesta.read()
    except urllib.error.HTTPError as error:
        codigo, texto = error.code, error.read()
    duracion = time.monotonic() - inicio
    try:
        return codigo, json.loads(texto), duracion
    except ValueError:
        return codigo, texto.decode(errors="replace"), duracion


def transaccion(cuerpo) -> tuple[int, object, float]:
    codigo, respuesta, duracion = pedir("POST", f"{URL_N8N}/webhook/transaccion", cuerpo)
    print(f"webhook/transaccion {codigo} en {duracion:.2f} s: {json.dumps(respuesta)[:600]}")
    return codigo, respuesta, duracion


def revision(cuerpo) -> tuple[int, object]:
    codigo, respuesta, _ = pedir("POST", f"{URL_N8N}/webhook/revision", cuerpo)
    print(f"webhook/revision {codigo}: {json.dumps(respuesta)[:400]}")
    return codigo, respuesta


def sin_modelo(exigir) -> None:
    _, salud, _ = pedir("GET", f"{URL_API}/salud")
    exigir(salud["modelo"]["cargado"] is False, "se esperaba la API sin modelo antes de entrenar")

    # Evaluacion fallida: variables sin modelo -> /evaluar 503 -> error_evaluacion.
    original = {
        "id_transaccion": "ci-flujo-sin-modelo",
        "origen": "original",
        "monto": 50.0,
        "variables": {f"V{i}": 0.0 for i in range(1, 29)},
    }
    pendiente = None
    codigo, caso, _ = transaccion(original)
    exigir(codigo == 200, f"sin modelo: el webhook respondio {codigo}")
    if codigo == 200:
        exigir(caso["nivel"] == "error_evaluacion", f"sin modelo: nivel {caso['nivel']}")
        exigir(caso["estado"] == "pendiente_revision", "error_evaluacion debe quedar pendiente")
        exigir(caso["id_caso"].startswith("c-"), "el caso no se registro")
        exigir("503" in caso["razones"][0], f"razon sin el 503: {caso['razones']}")
        exigir(
            caso["versiones"]["flujo"].startswith(VERSION_FLUJO_PREFIJO),
            "el caso no lleva la version del flujo",
        )
        exigir(caso["explicacion"]["origen"] == "plantilla", "explicacion sin origen plantilla")
        pendiente = caso["id_caso"]

    # Entrada invalida que n8n detecta y una que solo detecta la API (422).
    for nombre, cuerpo, codigo_razon in [
        ("monto texto", {"id_transaccion": "ci-inv-1", "origen": "original", "monto": "9"}, None),
        (
            "variables incompletas",
            {"id_transaccion": "ci-inv-2", "origen": "original", "monto": 9.0, "variables": {}},
            "422",
        ),
    ]:
        codigo, caso, _ = transaccion(cuerpo)
        exigir(codigo == 200, f"{nombre}: el webhook respondio {codigo}")
        if codigo == 200:
            exigir(caso["nivel"] == "error_evaluacion", f"{nombre}: nivel {caso['nivel']}")
            exigir(caso["estado"] == "pendiente_revision", f"{nombre}: no quedo pendiente")
            if codigo_razon:
                exigir(codigo_razon in caso["razones"][0], f"{nombre}: {caso['razones']}")
            else:
                exigir(caso["razones"][0].startswith("Entrada inválida"), f"{nombre}: razon")

    # JSON mal formado: n8n lo rechaza (422) antes de ejecutar el flujo, asi que no hay caso
    # (ADR 0014). Se comprueba que responde un error y que no aparece ningun caso nuevo.
    _, antes, _ = pedir("GET", f"{URL_API}/casos?limite=1")
    codigo, respuesta, _ = pedir("POST", f"{URL_N8N}/webhook/transaccion", b'{"monto": 12,')
    print(f"webhook/transaccion con JSON mal formado: {codigo} {str(respuesta)[:200]}")
    exigir(400 <= codigo < 500, f"JSON mal formado: n8n respondio {codigo}")
    _, despues, _ = pedir("GET", f"{URL_API}/casos?limite=1")
    exigir(despues["total"] == antes["total"], "el JSON mal formado registro un caso")

    # Sinteticas: solo reglas, el modelo no hace falta.
    inusual = {
        "id_transaccion": "ci-sint-1",
        "origen": "sintetico",
        "monto": 2500.0,
        "ubicacion": {"pais_habitual": "EC", "pais_transaccion": "US"},
    }
    codigo, caso, _ = transaccion(inusual)
    exigir(codigo == 200 and caso["nivel"] == "alerta_prioritaria", "ubicacion inusual")
    if codigo == 200:
        exigir(caso["notificacion"]["estado"] == "simulada_enviada", "sin notificacion simulada")
        exigir("señala" in caso["explicacion"]["texto"], "la explicacion no señala para revision")
    habitual = {**inusual, "id_transaccion": "ci-sint-2", "monto": 20.0}
    habitual["ubicacion"] = {"pais_habitual": "EC", "pais_transaccion": "EC"}
    codigo, caso, _ = transaccion(habitual)
    exigir(codigo == 200 and caso["nivel"] == "sin_alerta", "sintetica sin alerta")
    if codigo == 200:
        exigir(caso["estado"] == "cerrado", "sin_alerta debe cerrarse sola")

    # Revision humana.
    if pendiente is None:
        exigir(False, "no hay caso pendiente con el que probar la revision")
        return
    decision = {"decision": "sospecha_descartada", "revisor": "ci", "comentario": "prueba"}
    codigo, revisado = revision({"id_caso": pendiente, **decision})
    exigir(codigo == 200, f"revision: {codigo}")
    if codigo == 200:
        exigir(revisado["estado"] == "revisado", "el caso no quedo revisado")
        exigir(revisado["decision_final"] == "sospecha_descartada", "decision final distinta")
    codigo, repetida = revision({"id_caso": pendiente, **decision})
    exigir(codigo == 409, f"revision repetida: {codigo}")
    codigo, _ = revision({"id_caso": "c-000000000000", **decision})
    exigir(codigo == 404, f"revision de un caso inexistente: {codigo}")
    codigo, invalida = revision({"id_caso": "../salud", **decision})
    exigir(codigo == 422, f"revision con id_caso invalido: {codigo}")

    _, lista, _ = pedir("GET", f"{URL_API}/casos?limite=20")
    ids = {c["id_transaccion"] for c in lista["casos"]}
    exigir({"ci-flujo-sin-modelo", "ci-sint-1", "ci-sint-2"} <= ids, "faltan casos en GET /casos")


def api_detenida(exigir) -> None:
    sintetica = {
        "id_transaccion": "ci-api-caida",
        "origen": "sintetico",
        "monto": 10.0,
        "ubicacion": {"pais_habitual": "EC", "pais_transaccion": "EC"},
    }
    codigo, respuesta, duracion = transaccion(sintetica)
    exigir(codigo == 502, f"con la API detenida el webhook respondio {codigo}")
    exigir(duracion < 75, f"el webhook tardo {duracion:.1f} s")
    if codigo == 502:
        exigir(respuesta["error"]["tipo"] == "caso_no_registrado", "tipo de error inesperado")
        exigir(respuesta["caso"]["nivel"] == "error_evaluacion", "el caso no es error_evaluacion")
        exigir(respuesta["caso"]["id_transaccion"] == "ci-api-caida", "el caso perdio su id")
    decision = {"decision": "sospecha_confirmada", "revisor": "ci"}
    codigo, _ = revision({"id_caso": "c-000000000001", **decision})
    exigir(codigo == 502, f"revision con la API detenida: {codigo}")


def main() -> int:
    fallos: list[str] = []

    def exigir(condicion: bool, mensaje: str) -> None:
        if not condicion:
            fallos.append(mensaje)

    if "--sin-modelo" in sys.argv:
        sin_modelo(exigir)
    elif "--api-detenida" in sys.argv:
        api_detenida(exigir)
    else:
        print(__doc__)
        return 2
    for fallo in fallos:
        print(f"FALLO: {fallo}")
    print("Flujos de n8n: bien." if not fallos else f"{len(fallos)} fallo(s).")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
