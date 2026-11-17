"""`comparativa.md`: las tablas de la seccion 15 en lenguaje llano, a partir de `metricas.json`.

No calcula nada: solo da forma a lo que ya calculo `evaluar.py`.
"""

from pathlib import Path

CONFIGURACIONES = ("solo_reglas", "solo_modelo", "hibrido_cualquier", "hibrido_prioritaria")
LINEAS_BASE = ("nunca", "azar", "monto")
NOMBRES_METRICA = {
    "precision": "Precisión",
    "exhaustividad": "Exhaustividad",
    "f1": "F1",
    "precision_media": "Precisión media",
}
NOMBRES_PUNTUACION = {
    "modelo": "Puntuación de Isolation Forest",
    "monto": "Monto (línea base)",
    "azar": "Azar (línea base)",
}
NOMBRES = {
    "solo_reglas": "Solo reglas",
    "solo_modelo": "Solo Isolation Forest",
    "hibrido_cualquier": "Híbrido, cualquier alerta",
    "hibrido_prioritaria": "Híbrido, solo prioritarias",
    "nunca": "No alertar nunca",
    "azar": "Alertar al azar (misma cantidad de alertas)",
    "monto": "Ordenar por monto",
    "modelo": "Isolation Forest",
}


def numero(valor, decimales: int = 3) -> str:
    if valor is None:
        return "indefinida"
    return f"{valor:.{decimales}f}".replace(".", ",")


def con_ic(entrada: dict) -> str:
    ic = entrada["ic95"]
    if entrada["valor"] is None:
        return "indefinida"
    if ic["inferior"] is None:
        return numero(entrada["valor"])
    texto = f"{numero(entrada['valor'])} [{numero(ic['inferior'])}; {numero(ic['superior'])}]"
    if ic["indefinidos"]:
        texto += f" ({ic['indefinidos']} remuestreos indefinidos)"
    return texto


def _tabla_binarias(seccion: dict) -> list[str]:
    lineas = [
        "| Configuración | Alertas | VP | FP | FN | VN | Precisión [IC 95 %] "
        "| Exhaustividad [IC 95 %] | F1 [IC 95 %] |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for grupo, nombres in (("configuraciones", CONFIGURACIONES), ("lineas_base", LINEAS_BASE)):
        for nombre in nombres:
            e = seccion[grupo][nombre]
            m = e["matriz"]
            etiqueta = NOMBRES[nombre] + (" *(línea base)*" if grupo == "lineas_base" else "")
            lineas.append(
                f"| {etiqueta} | {e['alertas']} | {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} "
                f"| {con_ic(e['precision'])} | {con_ic(e['exhaustividad'])} | {con_ic(e['f1'])} |"
            )
    return lineas


def _tabla_puntuaciones(seccion: dict) -> list[str]:
    k = seccion["puntuaciones"]["modelo"]["precision_k"]["k"]
    lineas = [
        f"| Puntuación | Precisión media [IC 95 %] | Precisión en los {k} primeros [IC 95 %] "
        "| AUC ROC, complementaria [IC 95 %] |",
        "|---|---|---|---|",
    ]
    for nombre, entrada in seccion["puntuaciones"].items():
        lineas.append(
            f"| {NOMBRES_PUNTUACION[nombre]} | {con_ic(entrada['precision_media'])} "
            f"| {con_ic(entrada['precision_k'])} | {con_ic(entrada['auc_roc'])} |"
        )
    return lineas


def _tabla_diferencias(seccion: dict) -> list[str]:
    lineas = [
        "| A | B | Métrica | A − B [IC 95 %] |",
        "|---|---|---|---|",
    ]
    for d in seccion["diferencias"]:
        a = NOMBRES.get(d["a"], d["a"])
        b = NOMBRES.get(d["b"], d["b"])
        lineas.append(f"| {a} | {b} | {NOMBRES_METRICA[d['metrica']]} | {con_ic(d)} |")
    return lineas


def _resumen_semilla(r: dict, decimales: int = 3) -> str:
    if r["media"] is None:
        return "indefinida"
    d = decimales
    desviacion = "—" if r["desviacion"] is None else numero(r["desviacion"], d)
    extremos = f"mín. {numero(r['minimo'], d)}, máx. {numero(r['maximo'], d)}"
    return f"{numero(r['media'], d)} ± {desviacion} ({extremos})"


def _tabla_semillas(semillas: dict) -> list[str]:
    resumen = semillas["resumen"]
    lineas = [
        "| Configuración | Precisión | Exhaustividad | F1 | Alertas |",
        "|---|---|---|---|---|",
    ]
    for nombre in ("solo_modelo", "hibrido_cualquier", "hibrido_prioritaria"):
        r = resumen[nombre]
        lineas.append(
            f"| {NOMBRES[nombre]} | {_resumen_semilla(r['precision'])} "
            f"| {_resumen_semilla(r['exhaustividad'])} | {_resumen_semilla(r['f1'])} "
            f"| {_resumen_semilla(r['alertas'], 1)} |"
        )
    lineas += [
        "",
        f"- Precisión media del modelo: {_resumen_semilla(resumen['precision_media'])}",
        f"- `umbral_revision`: {_resumen_semilla(resumen['umbral_revision'], 4)}",
        f"- `umbral_prioritaria`: {_resumen_semilla(resumen['umbral_prioritaria'], 4)}",
    ]
    return lineas


def _temporal(t: dict) -> list[str]:
    if t["estado"] != "ok":
        return [f"**Omitida.** {t['motivo']}", ""]
    partes = t["partes"]
    lineas = [
        t["descripcion"],
        "",
        "| Parte | Filas | Fraudes | Time desde | Time hasta |",
        "|---|---|---|---|---|",
    ]
    for nombre in ("ajuste", "validacion", "prueba"):
        p = partes[nombre]
        lineas.append(
            f"| {nombre} | {p['filas']} | {p['fraudes']} | {numero(p['time_desde'], 0)} "
            f"| {numero(p['time_hasta'], 0)} |"
        )
    lineas += [
        "",
        f"Umbrales elegidos en la validación cronológica: revisión "
        f"{numero(t['umbrales']['umbral_revision'], 4)}, prioritaria "
        f"{numero(t['umbrales']['umbral_prioritaria'], 4)}.",
        "",
        *_tabla_binarias(t),
        "",
        *_tabla_puntuaciones(t),
        "",
    ]
    return lineas


def texto(m: dict) -> str:
    p = m["principal"]
    datos = m["datos"]["partes"]
    protocolo = m["protocolo"]
    lineas = ["# Comparativa de configuraciones", ""]
    if not m.get("reportable", False):
        lineas += [f"> **{m['aviso']}**", ""]
    lineas += [
        f"- Fecha (UTC): {m['fecha']}",
        f"- Versión del modelo: `{m['version_modelo']}`",
        f"- Datos: {m['fuente']}. Huella del contenido `{m['datos']['sha256_contenido'][:16]}…`, "
        f"huella de la partición `{m['datos']['huella_particion'][:16]}…`",
        "- Partes: "
        + ", ".join(f"{n} {d['filas']} filas y {d['fraudes']} fraudes" for n, d in datos.items()),
        f"- Umbrales, elegidos en validación (ADR 0008): revisión "
        f"{numero(m['umbrales']['umbral_revision'], 4)}, prioritaria "
        f"{numero(m['umbrales']['umbral_prioritaria'], 4)}. Corte de la línea base por monto: "
        f"{numero(p['umbral_monto']['valor'], 2)}.",
        f"- Intervalos: {protocolo['intervalo']}, {protocolo['remuestreos']} remuestreos, "
        f"confianza {numero(protocolo['confianza'], 2)}.",
        "",
        "La parte de prueba se usa solo para estas métricas agregadas, una vez por versión. "
        "La regla de ubicación no aparece: el conjunto original no trae ubicación y esa regla "
        "se comprueba de forma funcional con datos sintéticos (`datos.json`). Una precisión "
        "«indefinida» significa que no hubo alertas.",
        "",
        "## Configuraciones",
        "",
        *[
            f"- **{NOMBRES[n]}**: {protocolo['definiciones'][n]}."
            for n in protocolo["definiciones"]
        ],
        "",
        "## Parte de prueba",
        "",
        *_tabla_binarias(p),
        "",
        "## Puntuaciones continuas",
        "",
        *_tabla_puntuaciones(p),
        "",
        "## Diferencias pareadas",
        "",
        "Mismos remuestreos para A y B. Un intervalo que no contiene el 0 indica una "
        "diferencia que no se explica solo por el azar del muestreo.",
        "",
        *_tabla_diferencias(p),
        "",
        f"## Estabilidad con {len(m['semillas']['por_semilla'])} semillas",
        "",
        "Media ± desviación estándar sobre la parte de prueba. Cada semilla elige sus umbrales "
        "en validación. " + m["semillas"]["nota"],
        "",
        *_tabla_semillas(m["semillas"]),
        "",
        "## Partición temporal (análisis secundario)",
        "",
        *_temporal(m["temporal"]),
        "## Figuras",
        "",
        *[f"- `figuras/{nombre}`" for nombre in m["figuras"]],
        "",
        "## Análisis de errores",
        "",
        f"En `analisis_errores/`, de la parte de **validación**: "
        f"{m['analisis_errores']['fraudes_no_detectados']} fraudes no detectados y "
        f"{m['analisis_errores']['falsas_alarmas']} falsas alarmas de la configuración híbrida "
        "con cualquier alerta, con monto, puntuación, reglas y variables que más pesaron.",
        "",
    ]
    return "\n".join(lineas)


def escribir(metricas: dict, ruta: Path) -> None:
    Path(ruta).write_text(texto(metricas), encoding="utf-8")
