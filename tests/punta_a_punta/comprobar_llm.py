"""Comprueba, en la CI, una ejecucion con el LLM local real (N2; ADR 0016).

Uso: python tests/punta_a_punta/comprobar_llm.py

Se ejecuta tras `./fraude todo --muestra --llm` con Ollama real en el procesador y un modelo
diminuto (no el fijado: en la CI no hay grafica ni tiempo para el de 4B). Exige:

- `llm.json`: servidor y modelo listos. `anfitrion.json`: arrancado en el procesador.
- `flujo.json`: paridad total con el LLM activo. El nivel de cada transaccion del lote sale
  igual por n8n (que pidio la redaccion) que por la tabla en Python: el LLM no lo cambio.
- `explicaciones.json`: todas las alertas llegaron al LLM (ningun respaldo por LLM
  desactivado ni por error de la API), al menos una explicacion con origen `llm`, y la
  comprobacion repetida sobre lo guardado no encuentra discrepancias.

Imprime la muestra de textos para leerlos en el registro. La calidad de un modelo de 0,8B no
dice nada de la del fijado: eso lo mide el punto de prueba C con LLM (N3).
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
RESULTADOS = RAIZ / "resultados"


def main() -> int:
    carpetas = sorted(p for p in RESULTADOS.iterdir() if p.is_dir() and p.name != "en_curso")
    if not carpetas:
        print("No hay ninguna carpeta de evidencia")
        return 1
    carpeta = carpetas[-1]
    print(f"Evidencia: {carpeta.name}")
    fallos = []

    def exigir(condicion: bool, mensaje: str) -> None:
        if not condicion:
            fallos.append(mensaje)

    llm = json.loads((carpeta / "llm.json").read_text(encoding="utf-8"))
    print("llm.json:", json.dumps(llm, ensure_ascii=False))
    exigir(llm["estado"] == "ok", f"el LLM no quedo listo: {llm.get('error')}")
    # `ejecucion` de llm.json es lo que informa Ollama (size_vram): en un ejecutor sin grafica
    # llego a decir «mixta». Lo que manda es como lo arranco ./fraude (anfitrion.json).
    print(f"Segun Ollama: {llm.get('ejecucion')} ({llm.get('memoria')})")

    anfitrion = json.loads((carpeta / "anfitrion.json").read_text(encoding="utf-8"))
    exigir(anfitrion["llm"]["solicitado"] is True, "anfitrion.json no anota el LLM")
    exigir(anfitrion["llm"]["ejecucion"] == "procesador", "anfitrion.json: no es el procesador")

    flujo = json.loads((carpeta / "flujo.json").read_text(encoding="utf-8"))
    paridad = flujo["paridad"]
    print(f"Paridad con LLM: {paridad['coinciden']}/{paridad['total']}")
    exigir(flujo["estado"] == "ok" and paridad["completa"], "paridad incompleta con el LLM")

    expl = json.loads((carpeta / "explicaciones.json").read_text(encoding="utf-8"))
    resumen = {k: expl[k] for k in ("total", "por_origen", "respaldos", "intentos_llm")}
    print("explicaciones.json:", json.dumps(resumen, ensure_ascii=False))
    print("comprobacion:", json.dumps(expl["comprobacion"], ensure_ascii=False))
    print("tiempos_ms:", json.dumps(expl["tiempos_ms"], ensure_ascii=False))
    for e in expl["muestra"]:
        print(f"--- {e['nivel']} · {e['origen']} · {e['modelo']} · {e['duracion_ms']} ms")
        print(f"    {e['texto']}")
        if e.get("texto_descartado"):
            print(f"    descartado ({', '.join(e['fallos'])}): {e['texto_descartado']}")
    respaldos = expl["respaldos"]
    exigir("llm_desactivado" not in respaldos, "alertas sin LLM aunque se activo")
    exigir("error_api" not in respaldos, "n8n no obtuvo respuesta de /explicacion")
    exigir("error_llm" not in respaldos, "el LLM respondio con error")
    exigir(expl["por_origen"]["llm"] >= 1, "ninguna explicacion con origen llm")
    recomprobacion = expl["comprobacion"]["recomprobacion"]
    exigir(recomprobacion.get("discrepan") == [], f"discrepancias: {recomprobacion}")

    for fallo in fallos:
        print(f"FALLO: {fallo}")
    print("Correcto." if not fallos else f"{len(fallos)} fallo(s).")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
