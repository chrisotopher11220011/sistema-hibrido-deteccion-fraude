"""`tareas llm`: deja listo el modelo del LLM local (docs/spec.md, seccion 14; ADR 0016).

1. Comprueba que el servidor responde (`GET /api/version`).
2. Descarga el modelo de `config/llm.yaml` (`POST /api/pull`), con progreso. La primera vez son
   unos 3,3 GB; despues, Ollama solo comprueba que esta.
3. Lo precarga y lo deja en memoria (`POST /api/generate` vacio con `keep_alive: -1`), para que
   la primera explicacion no pague la carga.
4. Anota en `resultados/en_curso/llm.json` el servidor, el modelo, su resumen y cuanta memoria
   de la grafica usa (`GET /api/ps`): eso dice si el LLM corre en la grafica o en el procesador.

Si algo falla, `llm.json` lo dice y el sistema sigue con la plantilla.
"""

import contextlib
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from fraude.configuracion import cargar


class ErrorLlm(RuntimeError):
    """El servidor del LLM no respondio o no pudo dejar listo el modelo."""


def _abrir(url: str, cuerpo: dict | None, tiempo_limite: float):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    peticion = urllib.request.Request(
        url,
        data=datos,
        headers={"Content-Type": "application/json"},
        method="GET" if cuerpo is None else "POST",
    )
    try:
        return urllib.request.urlopen(peticion, timeout=tiempo_limite)
    except urllib.error.HTTPError as error:
        texto = error.read()[:400].decode("utf-8", "replace")
        with contextlib.suppress(ValueError, AttributeError):
            texto = json.loads(texto).get("error", texto)
        raise ErrorLlm(f"{url} respondio {error.code}: {texto}") from error
    except (urllib.error.URLError, OSError) as error:
        motivo = getattr(error, "reason", error)
        raise ErrorLlm(f"El servidor del LLM no responde en {url}: {motivo}") from error


def _json(url: str, cuerpo: dict | None = None, tiempo_limite: float = 30) -> dict:
    with _abrir(url, cuerpo, tiempo_limite) as respuesta:
        return json.loads(respuesta.read())


def _gb(n: float) -> str:
    return f"{n / 1e9:.1f}".replace(".", ",")


def _descargar(base: str, modelo: str, tiempo_limite: float) -> None:
    """`POST /api/pull` con progreso cada 10 %. Termina en `success` o lanza `ErrorLlm`.

    Ollama descarga el modelo en varias capas: el progreso suma todas las vistas hasta ahora,
    para que no vuelva a 0 % en cada capa.
    """
    ultimo_decil = -1
    estado_final = None
    capas: dict[str, tuple[int, int]] = {}
    with _abrir(f"{base}/api/pull", {"model": modelo, "stream": True}, tiempo_limite) as r:
        for linea in r:
            if not linea.strip():
                continue
            evento = json.loads(linea)
            if "error" in evento:
                raise ErrorLlm(f"La descarga de {modelo} fallo: {evento['error']}")
            estado_final = evento.get("status")
            if evento.get("digest") and evento.get("total"):
                capas[evento["digest"]] = (int(evento["total"]), int(evento.get("completed") or 0))
            if capas and evento.get("digest"):
                total = sum(t for t, _ in capas.values())
                hecho = sum(min(h, t) for t, h in capas.values())
                decil = int(hecho * 10 // total)
                # Al aparecer una capa nueva el total crece: el progreso nunca retrocede.
                if decil > ultimo_decil:
                    ultimo_decil = decil
                    print(
                        f"[llm] Descargando {modelo}: {decil * 10} % "
                        f"({_gb(hecho)} de {_gb(total)} GB)",
                        flush=True,
                    )
    if estado_final != "success":
        raise ErrorLlm(f"La descarga de {modelo} no termino (ultimo estado: {estado_final}).")


def _buscar(modelos: list[dict], nombre: str) -> dict | None:
    for m in modelos or []:
        if nombre in (m.get("name"), m.get("model")):
            return m
    return None


def preparar_llm(raiz: Path, muestra: bool = False) -> dict:
    """Descarga y precarga el modelo; deja `llm.json`. `muestra` no cambia nada (mismo LLM)."""
    config = cargar(raiz, "llm")
    base = config["servidor"]["url"].rstrip("/")
    modelo = config["modelo"]
    en_curso = Path(raiz) / "resultados" / "en_curso"
    en_curso.mkdir(parents=True, exist_ok=True)
    informe: dict = {
        "estado": "fallo",
        "fecha": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "servidor": {"url": base, "version": None},
        "modelo": {
            "nombre": modelo,
            "resumen": None,
            "resumen_esperado": config.get("resumen_modelo"),
            "coincide_con_el_fijado": None,
            "tamano_bytes": None,
        },
        "descarga_s": None,
        "carga_s": None,
        "memoria": None,
        "ejecucion": None,
        "error": None,
    }
    try:
        informe["servidor"]["version"] = _json(f"{base}/api/version").get("version")
        print(f"[llm] Servidor Ollama {informe['servidor']['version']} en {base}.", flush=True)
        inicio = time.monotonic()
        _descargar(base, modelo, float(config.get("descarga", {}).get("tiempo_limite_s", 3600)))
        informe["descarga_s"] = round(time.monotonic() - inicio, 1)
        inicio = time.monotonic()
        _json(
            f"{base}/api/generate",
            {"model": modelo, "keep_alive": -1},
            tiempo_limite=max(120.0, float(config["tiempo_limite_s"])),
        )
        informe["carga_s"] = round(time.monotonic() - inicio, 1)
        etiqueta = _buscar(_json(f"{base}/api/tags").get("models"), modelo) or {}
        resumen = etiqueta.get("digest")
        informe["modelo"]["resumen"] = resumen
        informe["modelo"]["tamano_bytes"] = etiqueta.get("size")
        esperado = config.get("resumen_modelo")
        if resumen and esperado:
            informe["modelo"]["coincide_con_el_fijado"] = resumen.startswith(esperado)
        cargado = _buscar(_json(f"{base}/api/ps").get("models"), modelo)
        if cargado:
            total, vram = int(cargado.get("size") or 0), int(cargado.get("size_vram") or 0)
            fraccion = round(vram / total, 3) if total else 0.0
            informe["memoria"] = {
                "total_bytes": total,
                "grafica_bytes": vram,
                "fraccion_en_grafica": fraccion,
            }
            informe["ejecucion"] = (
                "grafica" if fraccion >= 0.999 else "procesador" if vram == 0 else "mixta"
            )
        informe["estado"] = "ok"
    except (ErrorLlm, ValueError) as error:
        informe["error"] = str(error)
        raise ErrorLlm(str(error)) from error
    finally:
        (en_curso / "llm.json").write_text(
            json.dumps(informe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return informe
