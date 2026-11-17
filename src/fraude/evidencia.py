"""Archivos de evidencia que deja cada ejecucion (seccion 16 de docs/spec.md).

Fase 1: lo minimo para diagnosticar a distancia. Lo que solo puede verse desde el
anfitrion (datos del sistema, registros de Docker y capturas) lo deja el guion
`./fraude` en `resultados/en_curso/`; aqui se copia a la carpeta de evidencia.
"""

import json
import os
import platform
import re
import shutil
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

from fraude import __version__

DEPENDENCIAS = ("fastapi", "uvicorn", "pydantic", "starlette")
PATRON_SECRETO = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|CLAVE|API_KEY)[A-Z0-9_]*)(\s*[=:]\s*)(\S+)"
)
SUS = (
    "Creo que usaria este sistema con frecuencia.",
    "Encontre el sistema innecesariamente complejo.",
    "Pense que el sistema era facil de usar.",
    "Creo que necesitaria ayuda de una persona tecnica para usarlo.",
    "Las funciones del sistema estan bien integradas.",
    "Pense que habia demasiada inconsistencia en el sistema.",
    "Imagino que la mayoria aprenderia a usarlo muy rapido.",
    "Encontre el sistema muy engorroso de usar.",
    "Me senti con confianza al usar el sistema.",
    "Necesite aprender muchas cosas antes de poder usarlo.",
)


def enmascarar(texto: str) -> str:
    """Oculta el valor de cualquier variable con nombre de secreto."""
    return PATRON_SECRETO.sub(lambda m: f"{m.group(1)}{m.group(2)}***", texto)


def _obtener(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=10) as respuesta:  # noqa: S310
            return respuesta.status, respuesta.read(2000).decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read(2000).decode("utf-8", "replace")


def comprobar_servicios(
    url_api: str,
    url_n8n: str,
    obtener: Callable[[str], tuple[int, str]] = _obtener,
) -> list[dict]:
    """Comprueba la API (`/salud`) y n8n (`/webhook/ping`)."""
    resultado = []
    for servicio, url in (
        ("api", f"{url_api.rstrip('/')}/salud"),
        ("n8n", f"{url_n8n.rstrip('/')}/webhook/ping"),
    ):
        try:
            codigo, cuerpo = obtener(url)
            ok = 200 <= codigo < 300
            detalle = f"HTTP {codigo}: {cuerpo.strip()[:200]}"
        except Exception as error:  # noqa: BLE001 - se registra cualquier fallo de red
            ok, detalle = False, f"{type(error).__name__}: {error}"
        resultado.append({"servicio": servicio, "url": url, "ok": ok, "detalle": detalle})
    return resultado


def _fecha(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _escribir_json(ruta: Path, contenido: dict) -> None:
    ruta.write_text(json.dumps(contenido, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _carpeta_nueva(resultados: Path, momento: datetime, commit: str) -> Path:
    base = f"{momento.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}_{commit}"
    carpeta = resultados / base
    numero = 2
    while carpeta.exists() or carpeta.with_suffix(".zip").exists():
        carpeta = resultados / f"{base}-{numero}"
        numero += 1
    carpeta.mkdir(parents=True)
    return carpeta


def _memoria_mb() -> int | None:
    try:
        for linea in Path("/proc/meminfo").read_text().splitlines():
            if linea.startswith("MemTotal:"):
                return int(linea.split()[1]) // 1024
    except OSError:
        pass
    return None


def _entorno(momento: datetime) -> dict:
    return {
        "fecha": _fecha(momento),
        "arquitectura": platform.machine(),
        "sistema": platform.platform(),
        "python": platform.python_version(),
        "procesadores": os.cpu_count(),
        "memoria_mb": _memoria_mb(),
        "usuario": {"uid": os.getuid(), "gid": os.getgid()},
        "imagenes": {
            "n8n": os.environ.get("N8N_VERSION_FIJADA", "desconocida"),
            "python": os.environ.get("PYTHON_IMAGEN", "desconocida"),
        },
    }


def _version(commit: str, etiqueta: str) -> dict:
    dependencias = {}
    for nombre in DEPENDENCIAS:
        try:
            dependencias[nombre] = metadata.version(nombre)
        except metadata.PackageNotFoundError:
            dependencias[nombre] = "no instalada"
    return {
        "commit": commit,
        "etiqueta": etiqueta,
        "paquete": __version__,
        "python": sys.version.split()[0],
        "n8n": os.environ.get("N8N_VERSION_FIJADA", "desconocida"),
        "dependencias": dependencias,
    }


def _errores(servicios: list[dict], pasos: list[dict]) -> dict:
    errores = [
        {"origen": p["paso"], "mensaje": p.get("detalle", "")}
        for p in pasos
        if p.get("estado") == "fallo"
    ]
    errores += [
        {"origen": s["servicio"], "mensaje": f"{s['url']}: {s['detalle']}"}
        for s in servicios
        if not s["ok"]
    ]
    return {"hay_errores": bool(errores), "errores": errores}


def plantilla_observaciones() -> str:
    preguntas = "\n".join(f"{n}. {texto} ___/5" for n, texto in enumerate(SUS, start=1))
    return f"""# Observaciones de la ejecucion

Escribe con tus palabras. No hace falta que quede bonito: sirve para mejorar el sistema.

- **Quien ejecuto:**
- **Fecha:**

## Que hice


## Que vi


## Que me confundio o no funciono


## Cuanto tardo cada cosa (aproximado)


## Cuestionario SUS

Puntua cada frase de 1 (muy en desacuerdo) a 5 (muy de acuerdo). Llenalo cuando hayas
usado la pagina de simulacion (desde la fase 6); antes, dejalo en blanco.

{preguntas}
"""


def _copiar_carpeta(origen: Path, destino: Path, texto: bool) -> int:
    destino.mkdir(exist_ok=True)
    copiados = 0
    if not origen.is_dir():
        return copiados
    for archivo in sorted(origen.iterdir()):
        if not archivo.is_file():
            continue
        if texto:
            contenido = archivo.read_text(encoding="utf-8", errors="replace")
            (destino / archivo.name).write_text(enmascarar(contenido), encoding="utf-8")
        else:
            shutil.copyfile(archivo, destino / archivo.name)
        copiados += 1
    return copiados


def _resumen(
    momento: datetime,
    commit: str,
    etiqueta: str,
    servicios: list[dict],
    pasos: list[dict],
    errores: dict,
    notas: list[str],
) -> str:
    estado = {"ok": "bien", "fallo": "FALLO", "no_disponible": "aun no existe"}
    lineas = [
        "# Resumen de la ejecucion",
        "",
        f"- Fecha (UTC): {_fecha(momento)}",
        f"- Version: {etiqueta} (commit {commit})",
        f"- Resultado general: {'CON FALLOS' if errores['hay_errores'] else 'sin fallos'}",
        "",
        "## Servicios",
        "",
    ]
    for s in servicios:
        marca = "bien" if s["ok"] else "FALLO"
        lineas.append(f"- {s['servicio']}: {marca} ({s['url']} -> {s['detalle']})")
    if not servicios:
        lineas.append("- No se comprobaron.")
    lineas += ["", "## Pasos", ""]
    for p in pasos:
        marca = estado.get(p["estado"], p["estado"])
        lineas.append(f"- {p['paso']}: {marca}. {p.get('detalle', '')}".rstrip())
    if not pasos:
        lineas.append("- No se ejecuto ningun paso; solo se reunio la evidencia.")
    lineas += ["", "## Notas", ""]
    lineas += [f"- {nota}" for nota in notas] or ["- Ninguna."]
    lineas += [
        "",
        "## Alcance",
        "",
        "Esta version comprueba el arranque. No contiene metricas de deteccion de fraude.",
        "",
    ]
    return "\n".join(lineas)


def reunir_evidencia(
    raiz: Path,
    *,
    commit: str,
    etiqueta: str,
    servicios: list[dict],
    pasos: list[dict],
    ahora: datetime | None = None,
) -> Path:
    """Crea `resultados/<fecha>_<commit>/` y un `.zip` con lo mismo. Devuelve la carpeta."""
    momento = ahora or datetime.now(UTC)
    resultados = Path(raiz) / "resultados"
    en_curso = resultados / "en_curso"
    en_curso.mkdir(parents=True, exist_ok=True)
    carpeta = _carpeta_nueva(resultados, momento, commit)
    notas = []

    anfitrion = en_curso / "anfitrion.json"
    if anfitrion.is_file():
        shutil.copyfile(anfitrion, carpeta / "anfitrion.json")
    else:
        motivo = "No se uso el guion ./fraude, que es quien recoge los datos del sistema."
        _escribir_json(carpeta / "anfitrion.json", {"disponible": False, "motivo": motivo})
        notas.append(f"Sin datos del anfitrion. {motivo}")

    _escribir_json(carpeta / "entorno.json", _entorno(momento))
    _escribir_json(carpeta / "version.json", _version(commit, etiqueta))
    errores = _errores(servicios, pasos)
    _escribir_json(carpeta / "errores.json", errores)

    if _copiar_carpeta(en_curso / "registros", carpeta / "registros", texto=True) == 0:
        notas.append("Sin registros de los servicios: los guarda ./fraude desde el anfitrion.")
    capturas = _copiar_carpeta(en_curso / "capturas", carpeta / "capturas", texto=False)
    notas.append(f"Capturas de pantalla copiadas: {capturas}.")

    observaciones = en_curso / "OBSERVACIONES.md"
    if not observaciones.is_file():
        observaciones.write_text(plantilla_observaciones(), encoding="utf-8")
    shutil.copyfile(observaciones, carpeta / "OBSERVACIONES.md")

    resumen = _resumen(momento, commit, etiqueta, servicios, pasos, errores, notas)
    (carpeta / "RESUMEN.md").write_text(resumen, encoding="utf-8")

    shutil.make_archive(str(carpeta), "zip", root_dir=resultados, base_dir=carpeta.name)
    return carpeta
