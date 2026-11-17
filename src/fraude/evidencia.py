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

from fraude import __version__, explicaciones
from fraude.configuracion import cargar
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


def _copiar_flujo(en_curso: Path, carpeta: Path) -> list[str]:
    """Copia `flujo.json` (paso demostrar) y resume paridad y latencia (seccion 16)."""
    flujo = _leer(en_curso / "flujo.json")
    if flujo is None:
        return ["Sin flujo.json: el paso demostrar no se ejecuto en esta sesion."]
    shutil.copyfile(en_curso / "flujo.json", carpeta / "flujo.json")
    if flujo.get("estado") != "ok":
        return [f"Flujo: demostrar no termino bien ({flujo.get('error', 'sin detalle')})."]
    paridad, latencia = flujo["paridad"], flujo["latencia_ms"]
    nota = (
        f"Flujo de n8n: paridad {paridad['coinciden']}/{paridad['total']}, latencia "
        f"mediana {latencia['mediana']} ms y p95 {latencia['p95']} ms (flujo.json)."
    )
    if not flujo.get("reportable", False):
        nota += " Lote de la muestra para pruebas: no reportable."
    return [nota]


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
    "explicacion_modelo",
    "explicacion_duracion_ms",
    "explicacion_respaldo",
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
        "explicacion_modelo": explicacion.get("modelo"),
        "explicacion_duracion_ms": explicacion.get("duracion_ms"),
        "explicacion_respaldo": (explicacion.get("respaldo") or {}).get("motivo"),
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


def _exportar_explicaciones(raiz: Path, en_curso: Path, carpeta: Path) -> list[str]:
    """`llm.json` (si se preparo el LLM) y `explicaciones.json` (seccion 16; ADR 0016)."""
    notas = []
    servidor = _leer(en_curso / "llm.json")
    if servidor is not None:
        shutil.copyfile(en_curso / "llm.json", carpeta / "llm.json")
        if servidor.get("estado") == "ok":
            fraccion = (servidor.get("memoria") or {}).get("fraccion_en_grafica")
            lugar = (
                "sin dato de la grafica"
                if fraccion is None
                else (f"segun Ollama, {fraccion:.0%} de su memoria en la grafica")
            )
            anfitrion = (_leer(en_curso / "anfitrion.json") or {}).get("llm") or {}
            if anfitrion.get("ejecucion"):
                lugar += f"; ./fraude lo arranco con {anfitrion['ejecucion']}"
            if anfitrion.get("grafica_memoria_usada_mib") is not None:
                lugar += f" y nvidia-smi marca {anfitrion['grafica_memoria_usada_mib']} MiB usados"
            coincide = (servidor.get("modelo") or {}).get("coincide_con_el_fijado")
            aviso = "" if coincide is not False else " AVISO: el resumen no es el fijado."
            notas.append(
                f"LLM local: {servidor['modelo']['nombre']} en Ollama "
                f"{servidor['servidor']['version']}, {lugar} (llm.json).{aviso}"
            )
        else:
            notas.append(
                f"LLM local: no quedo listo ({servidor.get('error')}); las explicaciones "
                "usaron la plantilla (llm.json)."
            )
    else:
        notas.append("Sin LLM local en esta ejecucion: las explicaciones son de plantilla.")
    ruta = ruta_bd_casos(raiz)
    casos = RegistroCasos(ruta).todos() if ruta.is_file() else []
    try:
        config = cargar(raiz, "llm")
    except FileNotFoundError:
        config = None
    contenido = explicaciones.resumir(casos, config, servidor, enmascarar)
    _escribir_json(carpeta / "explicaciones.json", contenido)
    if contenido["total"]:
        c = contenido["comprobacion"]
        motivos = ", ".join(f"{m} {n}" for m, n in contenido["respaldos"].items()) or "ninguno"
        notas.append(
            f"Explicaciones: {contenido['total']} casos, {contenido['por_origen']['llm']} por el "
            f"LLM y {contenido['por_origen']['plantilla']} por plantilla (respaldos: {motivos}); "
            f"comprobacion automatica: {c['fallidos']} de {c['textos_comprobados']} textos del "
            "LLM no la pasaron (explicaciones.json)."
        )
    return notas


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


ALERTAS = ("alerta_prioritaria", "revision_recomendada")
NOTA_SIMULACION = (
    "Lo enviado desde la pagina y lo que respondio el sistema. La comparacion con la etiqueta "
    "real se hace aqui, al reunir la evidencia: la etiqueta nunca viajo al flujo. Cubre solo "
    "las transacciones que se enviaron en la sesion; ilustra, no sustituye a comparativa.md."
)


def _enmascarar_valores(valor):
    if isinstance(valor, str):
        return enmascarar(valor)
    if isinstance(valor, dict):
        return {k: _enmascarar_valores(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_enmascarar_valores(v) for v in valor]
    return valor


def _etiquetas_del_lote(raiz: Path) -> dict[str, dict[str, int | None]]:
    """Por lote (`real`, `muestra`): `id_transaccion` -> etiqueta real."""
    etiquetas: dict[str, dict[str, int | None]] = {}
    for fuente, parte in (("muestra", "muestra"), ("real", "")):
        mapa: dict[str, int | None] = {}
        datos = _leer(Path(raiz) / "datos" / parte / "demostracion" / "lote.json")
        for elemento in (datos or {}).get("elementos", []):
            transaccion = elemento.get("transaccion")
            if isinstance(transaccion, dict) and isinstance(transaccion.get("id_transaccion"), str):
                mapa[transaccion["id_transaccion"]] = elemento.get("etiqueta_real")
        etiquetas[fuente] = mapa
    return etiquetas


def _nivel_de(intercambio: dict) -> str | None:
    respuesta = intercambio.get("respuesta")
    if not isinstance(respuesta, dict):
        return None
    caso = respuesta.get("caso") if isinstance(respuesta.get("caso"), dict) else respuesta
    nivel = caso.get("nivel")
    return nivel if isinstance(nivel, str) else None


def _matriz() -> dict:
    return {"vp": 0, "fp": 0, "fn": 0, "vn": 0}


def _resumir_sesion(nombre: str | None, intercambios: list[dict]) -> dict:
    enviadas = [i for i in intercambios if i.get("ruta") == "transacciones"]
    # Solo cuentan las que el flujo evaluo: un intento sin respuesta se reintenta despues.
    transacciones = [i for i in enviadas if _nivel_de(i)]
    comparacion = {
        "cualquier_alerta": _matriz(),
        "solo_prioritaria": _matriz(),
        "sin_etiqueta": 0,
        "sin_veredicto": 0,
    }
    niveles: dict[str, int] = {}
    for i in transacciones:
        nivel = _nivel_de(i)
        niveles[nivel] = niveles.get(nivel, 0) + 1
        etiqueta = i.get("etiqueta_real")
        if etiqueta not in (0, 1):
            comparacion["sin_etiqueta"] += 1
            continue
        if nivel not in ALERTAS and nivel != "sin_alerta":
            comparacion["sin_veredicto"] += 1
            continue
        for clave, positivos in (
            ("cualquier_alerta", ALERTAS),
            ("solo_prioritaria", ("alerta_prioritaria",)),
        ):
            senalada = nivel in positivos
            celda = ("vp" if senalada else "fn") if etiqueta == 1 else ("fp" if senalada else "vn")
            comparacion[clave][celda] += 1
    latencias = [i["latencia_ms"] for i in transacciones if i.get("latencia_ms") is not None]
    codigos: dict[str, int] = {}
    for i in intercambios:
        codigos[str(i.get("codigo"))] = codigos.get(str(i.get("codigo")), 0) + 1
    fechas = [i.get("fecha") for i in intercambios if i.get("fecha")]
    return {
        "sesion": nombre,
        "inicio": min(fechas) if fechas else None,
        "fin": max(fechas) if fechas else None,
        "transacciones": len(transacciones),
        "sin_respuesta_del_flujo": len(enviadas) - len(transacciones),
        "revisiones": sum(1 for i in intercambios if i.get("ruta") == "revisiones"),
        "niveles": niveles,
        "codigos": codigos,
        "latencia_ms": _latencias(latencias),
        "comparacion": comparacion,
    }


def _latencias(valores: list[float]) -> dict:
    if not valores:
        return {"n": 0, "mediana": None, "p95": None}
    ordenados = sorted(valores)

    def percentil(q: float) -> float:
        posicion = (len(ordenados) - 1) * q
        bajo = int(posicion)
        alto = min(bajo + 1, len(ordenados) - 1)
        return round(ordenados[bajo] + (ordenados[alto] - ordenados[bajo]) * (posicion - bajo), 1)

    return {
        "n": len(valores),
        "mediana": percentil(0.5),
        "p95": percentil(0.95),
        "medida": "desde la API hasta la respuesta de n8n (incluye el flujo); la pagina suma "
        "el salto del navegador a la API",
    }


def _exportar_simulacion(raiz: Path, en_curso: Path, carpeta: Path) -> list[str]:
    """`simulacion.json` desde el registro de la pagina (seccion 13; ADR 0015)."""
    origen = en_curso / "simulacion.jsonl"
    intercambios, ilegibles = [], 0
    if origen.is_file():
        for linea in origen.read_text(encoding="utf-8", errors="replace").splitlines():
            if not linea.strip():
                continue
            try:
                entrada = json.loads(linea)
            except ValueError:
                ilegibles += 1
                continue
            if isinstance(entrada, dict):
                intercambios.append(_enmascarar_valores(entrada))
            else:
                ilegibles += 1
    etiquetas = _etiquetas_del_lote(raiz)
    for i in intercambios:
        enviado = i.get("enviado")
        id_t = enviado.get("id_transaccion") if isinstance(enviado, dict) else None
        if i.get("ruta") == "transacciones":
            fuentes = [i["lote"]] if i.get("lote") in etiquetas else ["muestra", "real"]
            i["etiqueta_real"] = None
            for fuente in fuentes:
                if isinstance(id_t, str) and id_t in etiquetas[fuente]:
                    i["etiqueta_real"] = etiquetas[fuente][id_t]
    grupos: dict[str | None, list[dict]] = {}
    for i in intercambios:
        grupos.setdefault(i.get("sesion"), []).append(i)
    sesiones = [_resumir_sesion(nombre, grupo) for nombre, grupo in grupos.items()]
    contenido = {
        "estado": "ok" if intercambios else "sin_sesiones",
        "reportable": False,
        "nota": NOTA_SIMULACION,
        "intercambios_total": len(intercambios),
        "lineas_ilegibles": ilegibles,
        "sesiones": sesiones,
        "intercambios": intercambios,
    }
    _escribir_json(carpeta / "simulacion.json", contenido)
    if not intercambios:
        return ["Sin sesiones de la pagina de simulacion: simulacion.json va vacio."]
    enviadas = sum(s["transacciones"] for s in sesiones)
    revisiones = sum(s["revisiones"] for s in sesiones)
    return [
        f"Pagina de simulacion: {len(sesiones)} sesion(es), {enviadas} transacciones enviadas "
        f"y {revisiones} revision(es) (simulacion.json)."
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
        "de la seccion 15. n8n evalua cada transaccion del lote de demostracion con la API,",
        "clasifica el nivel, registra el caso y recibe la revision humana; demostrar mide la",
        "paridad con la tabla en Python y la latencia (flujo.json). La pagina de simulacion",
        "envia el lote por n8n a traves de la API y su sesion queda en simulacion.json.",
        "Solo las cifras calculadas con el conjunto real en el computador de ejecucion (N3)",
        "son resultados; las de la muestra para pruebas no lo son.",
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
    notas += _copiar_flujo(en_curso, carpeta)
    notas += _exportar_casos(Path(raiz), carpeta)
    notas += _exportar_explicaciones(Path(raiz), en_curso, carpeta)
    notas += _exportar_simulacion(Path(raiz), en_curso, carpeta)
    notas.append(f"Capturas de pantalla copiadas: {capturas}.")

    observaciones = en_curso / "OBSERVACIONES.md"
    if not observaciones.is_file():
        observaciones.write_text(plantilla_observaciones(), encoding="utf-8")
    shutil.copyfile(observaciones, carpeta / "OBSERVACIONES.md")

    resumen = _resumen(momento, commit, etiqueta, servicios, pasos, errores, notas)
    (carpeta / "RESUMEN.md").write_text(resumen, encoding="utf-8")

    shutil.make_archive(str(carpeta), "zip", root_dir=resultados, base_dir=carpeta.name)
    return carpeta
