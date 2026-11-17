"""Comprueba, en la CI, la API en marcha dentro de Compose (N2, fase 4).

Se ejecuta despues de `tareas todo --muestra`. La API arranco antes de que `entrenar` dejara el
modelo, asi que esto comprueba tambien que lo cargo sola. Solo usa la biblioteca estandar: el
trabajo de la CI no instala dependencias del proyecto.

Uso: python tests/punta_a_punta/comprobar_api.py [url_api]
"""

import json
import sys
import urllib.error
import urllib.request

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
CAMPOS_EVALUACION = {"id_transaccion", "reglas", "modelo", "versiones"}
CAMPOS_MODELO = {
    "evaluable",
    "puntuacion",
    "umbral_revision",
    "umbral_prioritaria",
    "anomalia",
    "anomalia_alta",
}


def pedir(metodo: str, ruta: str, cuerpo=None) -> tuple[int, dict]:
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    peticion = urllib.request.Request(
        URL + ruta, data=datos, method=metodo, headers={"content-type": "application/json"}
    )
    try:
        with urllib.request.urlopen(peticion, timeout=30) as respuesta:
            return respuesta.status, json.loads(respuesta.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def main() -> int:
    fallos: list[str] = []

    def exigir(condicion: bool, mensaje: str) -> None:
        if not condicion:
            fallos.append(mensaje)

    _, salud = pedir("GET", "/salud")
    modelo = salud["modelo"]
    print(f"/salud: modelo {json.dumps(modelo, ensure_ascii=False)}")
    exigir(modelo["cargado"] is True, f"la API no cargo el modelo: {modelo.get('motivo')}")
    exigir(modelo.get("reportable") is False, "en la CI el modelo debe ser el de la muestra")

    original = {
        "id_transaccion": "ci-original",
        "origen": "original",
        "monto": 2000.0,
        "variables": {f"V{i}": 0.0 for i in range(1, 29)},
    }
    codigo, ev = pedir("POST", "/evaluar", original)
    print(f"/evaluar original: {codigo} {json.dumps(ev, ensure_ascii=False)}")
    exigir(codigo == 200, f"/evaluar original respondio {codigo}")
    if codigo == 200:
        exigir(set(ev) == CAMPOS_EVALUACION, f"campos de /evaluar: {sorted(ev)}")
        exigir(set(ev["modelo"]) - {"contribuciones"} == CAMPOS_MODELO, "campos de modelo")
        exigir(ev["modelo"]["evaluable"] is True, "el modelo no evaluo la transaccion original")
        exigir(ev["versiones"]["modelo"] == modelo["version"], "version del modelo distinta")
        activadas = {r["id"] for r in ev["reglas"] if r["activada"]}
        exigir(activadas == {"MONTO_ALTO"}, f"reglas activadas: {activadas}")

    sintetica = {
        "id_transaccion": "ci-sintetica",
        "origen": "sintetico",
        "monto": 1500.0,
        "ubicacion": {"pais_habitual": "EC", "pais_transaccion": "US"},
    }
    codigo, senales = pedir("POST", "/evaluar", sintetica)
    exigir(codigo == 200, f"/evaluar sintetica respondio {codigo}")
    activadas = {r["id"] for r in senales.get("reglas", []) if r["activada"]}
    exigir("MONTO_ALTO_UBICACION_INUSUAL" in activadas, f"reglas activadas: {activadas}")

    codigo, error = pedir("POST", "/evaluar", {**sintetica, "monto": -1})
    print(f"/evaluar invalida: {codigo} {json.dumps(error, ensure_ascii=False)}")
    exigir(codigo == 422, f"una entrada invalida respondio {codigo}, no 422")
    exigir(error.get("error", {}).get("tipo") == "entrada_invalida", "tipo de error")
    exigir(error.get("id_transaccion") == "ci-sintetica", "el error no trae id_transaccion")

    caso = {
        "id_transaccion": "ci-sintetica",
        "origen": "sintetico",
        "monto": 1500.0,
        "senales": senales,
        "puntuacion": None,
        "nivel": "alerta_prioritaria",
        "razones": [r["razon"] for r in senales.get("reglas", []) if r["activada"]],
        "explicacion": {"texto": "Prueba de la CI.", "origen": "plantilla"},
        "notificacion": {"canal": "simulada", "estado": "registrada"},
        "versiones": {"reglas": senales.get("versiones", {}).get("reglas"), "modelo": None,
                      "flujo": None},
    }  # fmt: skip
    codigo, registrado = pedir("POST", "/casos", caso)
    print(f"/casos: {codigo} {registrado.get('id_caso')} {registrado.get('estado')}")
    exigir(codigo == 201, f"/casos respondio {codigo}: {registrado}")
    if codigo == 201:
        exigir(registrado["estado"] == "pendiente_revision", "el caso no quedo pendiente")
        ruta = f"/casos/{registrado['id_caso']}/revision"
        revision = {"decision": "sospecha_descartada", "revisor": "ci", "comentario": "prueba"}
        codigo, revisado = pedir("POST", ruta, revision)
        exigir(codigo == 200 and revisado.get("estado") == "revisado", f"revision: {codigo}")
        codigo, _ = pedir("POST", ruta, revision)
        exigir(codigo == 409, f"una segunda revision respondio {codigo}, no 409")

    codigo, lista = pedir("GET", "/casos?estado=revisado")
    exigir(codigo == 200 and lista.get("total", 0) >= 1, f"/casos?estado=revisado: {codigo}")

    for fallo in fallos:
        print(f"FALLO: {fallo}")
    if not fallos:
        print("API correcta: modelo cargado, /evaluar, errores, casos y revision")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
