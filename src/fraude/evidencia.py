"""Archivos de evidencia que deja cada ejecucion (seccion 16 de docs/spec.md).

Fase 1: lo minimo para diagnosticar a distancia. Lo que solo puede verse desde el
anfitrion (datos del sistema, registros de Docker y capturas) lo deja el guion
`./fraude` en `resultados/en_curso/`; aqui se copia a la carpeta de evidencia.
"""

import csv
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
from fraude.registro import RegistroCasos, ruta_bd_casos

DEPENDENCIAS = (
    "fastapi",
    "uvicorn",
    "pydantic",
    "starlette",
    "pandas",
    "numpy",
    "scikit-learn",
    "matplotlib",
    "pyyaml",
)
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


def _copiar_datos(en_curso: Path, carpeta: Path) -> list[str]:
    """Copia lo que deja `preparar` (`datos.json` y `eda/`) y resume su estado."""
    origen = en_curso / "datos.json"
    if not origen.is_file():
        return ["Sin datos.json: el paso preparar no se ejecuto en esta sesion."]
    shutil.copyfile(origen, carpeta / "datos.json")
    if (en_curso / "eda").is_dir():
        _copiar_carpeta(en_curso / "eda", carpeta / "eda", texto=False)
    try:
        informe = json.loads(origen.read_text(encoding="utf-8"))
    except ValueError:
        return ["datos.json no se pudo leer."]
    if informe.get("estado") != "ok":
        return [f"Datos: preparar no termino bien ({informe.get('error', 'sin detalle')})."]
    nota = (
        f"Datos: fuente {informe.get('fuente')}, {informe.get('filas')} transacciones, "
        f"{informe.get('fraudes')} fraudes."
    )
    if not informe.get("reportable", False):
        nota += " Es la muestra para pruebas: no reportable, no representa el fraude real."
    return [nota]


def _leer(ruta: Path) -> dict | None:
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _copiar_modelo_y_evaluacion(en_curso: Path, carpeta: Path) -> list[str]:
    """Copia lo que dejan `entrenar` y `evaluar` y resume su estado."""
    notas = []
    for nombre in ("modelo.json", "metricas.json", "comparativa.md"):
        if (en_curso / nombre).is_file():
            shutil.copyfile(en_curso / nombre, carpeta / nombre)
    for nombre in ("figuras", "analisis_errores"):
        if (en_curso / nombre).is_dir():
            _copiar_carpeta(en_curso / nombre, carpeta / nombre, texto=False)

    modelo = _leer(en_curso / "modelo.json")
    if modelo is None:
        notas.append("Sin modelo.json: el paso entrenar no se ejecuto en esta sesion.")
    elif modelo.get("estado") != "ok":
        notas.append(f"Modelo: entrenar no termino bien ({modelo.get('error', 'sin detalle')}).")
    else:
        nota = f"Modelo: version {modelo.get('version')}, umbrales elegidos en validacion."
        if not modelo.get("reportable", False):
            nota += " Entrenado con la muestra para pruebas: no reportable."
        notas.append(nota)

    metricas = _leer(en_curso / "metricas.json")
    if metricas is None:
        notas.append("Sin metricas.json: el paso evaluar no se ejecuto en esta sesion.")
    elif metricas.get("estado") != "ok":
        notas.append(
            f"Evaluacion: evaluar no termino bien ({metricas.get('error', 'sin detalle')})."
        )
    else:
        nota = (
            "Evaluacion: metricas.json, comparativa.md y figuras/ con la parte de prueba; "
            "analisis_errores/ con la de validacion."
        )
        if not metricas.get("reportable", False):
            nota += " Calculado con la muestra para pruebas: no reportable, no es un resultado."
        notas.append(nota)
    return notas


COLUMNAS_CASOS = (
    "id_caso",
    "fecha_procesamiento",
    "id_transaccion",
    "origen",
    "monto",
    "nivel",
    "puntuacion",
    "reglas_activadas",
    "anomalia",
    "razones",
    "estado",
    "decision_final",
    "explicacion_origen",
    "explicacion",
    "notificacion_canal",
    "notificacion_estado",
    "version_reglas",
    "version_modelo",
    "version_flujo",
)
COLUMNAS_REVISIONES = (
    "id_caso",
    "id_transaccion",
    "nivel",
    "decision_final",
    "revisor",
    "comentario",
    "fecha_revision",
    "fecha_procesamiento",
    "version_modelo",
)


def _fila_caso(caso: dict) -> dict:
    senales = caso.get("senales") or {}
    activadas = [r["id"] for r in senales.get("reglas", []) if r.get("activada")]
    modelo = senales.get("modelo") or {}
    versiones = caso.get("versiones") or {}
    explicacion = caso.get("explicacion") or {}
    notificacion = caso.get("notificacion") or {}
    return {
        "id_caso": caso["id_caso"],
        "fecha_procesamiento": caso["fecha_procesamiento"],
        "id_transaccion": caso.get("id_transaccion"),
        "origen": caso.get("origen"),
        "monto": caso.get("monto"),
        "nivel": caso["nivel"],
        "puntuacion": caso.get("puntuacion"),
        "reglas_activadas": " | ".join(activadas),
        "anomalia": modelo.get("anomalia") if modelo.get("evaluable") else "no_evaluable",
        "razones": " | ".join(caso.get("razones") or []),
        "estado": caso["estado"],
        "decision_final": caso["decision_final"],
        "explicacion_origen": explicacion.get("origen"),
        "explicacion": enmascarar(explicacion.get("texto") or ""),
        "notificacion_canal": notificacion.get("canal"),
        "notificacion_estado": notificacion.get("estado"),
        "version_reglas": versiones.get("reglas"),
        "version_modelo": versiones.get("modelo"),
        "version_flujo": versiones.get("flujo"),
    }


def _fila_revision(caso: dict) -> dict:
    revision = caso["revision"]
    return {
        "id_caso": caso["id_caso"],
        "id_transaccion": caso.get("id_transaccion"),
        "nivel": caso["nivel"],
        "decision_final": caso["decision_final"],
        "revisor": enmascarar(revision["revisor"]),
        "comentario": enmascarar(revision.get("comentario") or ""),
        "fecha_revision": revision["fecha"],
        "fecha_procesamiento": caso["fecha_procesamiento"],
        "version_modelo": (caso.get("versiones") or {}).get("modelo"),
    }


def _escribir_csv(ruta: Path, columnas: tuple, filas: list[dict]) -> None:
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)


def _exportar_casos(raiz: Path, carpeta: Path) -> list[str]:
    """`casos.csv` y `revisiones.csv` desde la base de la API (seccion 16; ADR 0005)."""
    ruta = ruta_bd_casos(raiz)
    casos = RegistroCasos(ruta).todos() if ruta.is_file() else []
    revisados = [c for c in casos if c.get("revision")]
    _escribir_csv(carpeta / "casos.csv", COLUMNAS_CASOS, [_fila_caso(c) for c in casos])
    _escribir_csv(
        carpeta / "revisiones.csv", COLUMNAS_REVISIONES, [_fila_revision(c) for c in revisados]
    )
    if not casos:
        return ["Sin casos registrados: casos.csv y revisiones.csv solo traen las cabeceras."]
    pendientes = sum(c["estado"] == "pendiente_revision" for c in casos)
    return [
        f"Casos: {len(casos)} casos registrados en total, {pendientes} pendientes de revision "
        f"y {len(revisados)} revisado(s) (casos.csv y revisiones.csv)."
    ]


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
        "Esta version prepara los datos, entrena Isolation Forest con la parte de ajuste,",
        "elige los umbrales en validacion y evalua en la parte de prueba con el protocolo",
        "de la seccion 15. La API evalua transacciones (POST /evaluar) con el modelo",
        "entrenado y registra casos y revisiones; el flujo de n8n que los usa llega en la",
        "fase 5. Solo las cifras calculadas con el conjunto real en el computador de",
        "ejecucion (N3) son resultados; las de la muestra para pruebas no lo son.",
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
    notas += _copiar_datos(en_curso, carpeta)
    notas += _copiar_modelo_y_evaluacion(en_curso, carpeta)
    notas += _exportar_casos(Path(raiz), carpeta)
    notas.append(f"Capturas de pantalla copiadas: {capturas}.")

    observaciones = en_curso / "OBSERVACIONES.md"
    if not observaciones.is_file():
        observaciones.write_text(plantilla_observaciones(), encoding="utf-8")
    shutil.copyfile(observaciones, carpeta / "OBSERVACIONES.md")

    resumen = _resumen(momento, commit, etiqueta, servicios, pasos, errores, notas)
    (carpeta / "RESUMEN.md").write_text(resumen, encoding="utf-8")

    shutil.make_archive(str(carpeta), "zip", root_dir=resultados, base_dir=carpeta.name)
    return carpeta
