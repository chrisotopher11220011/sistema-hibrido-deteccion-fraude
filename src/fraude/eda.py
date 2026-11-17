"""Analisis exploratorio de la parte de ajuste (docs/spec.md, secciones 9 y 16).

Solo describe la parte de ajuste: nunca mira validacion ni prueba (ADR 0003). Sirve para
conocer el conjunto y proponer reglas candidatas en la fase de mejora. Ninguna cifra de
aqui es una metrica de deteccion.

Las figuras siguen la skill `dataviz`: un eje por grafica, marcas finas, rejilla tenue,
leyenda cuando hay dos series, colores categoricos en orden fijo (azul para legitimas,
naranja para fraudes; el rojo queda reservado para estados).
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from fraude.graficas import (
    COLOR_FRAUDE,
    COLOR_LEGITIMA,
    REJILLA,
    TEXTO,
    TEXTO_SECUNDARIO,
)
from fraude.graficas import ejes as _ejes
from fraude.graficas import guardar as _guardar
from fraude.graficas import titulo as _titulo
from fraude.transaccion import VARIABLES

AVISO = "Parte de ajuste. Descriptivo: no es una metrica de deteccion."
AVISO_FIGURA = "Parte de ajuste. Descriptivo, no es una métrica de detección."


def _describir(montos: pd.Series) -> dict:
    if montos.empty:
        return {"n": 0, "media": None, "mediana": None, "p95": None, "minimo": None, "maximo": None}
    return {
        "n": int(len(montos)),
        "media": float(montos.mean()),
        "mediana": float(montos.median()),
        "p95": float(montos.quantile(0.95)),
        "minimo": float(montos.min()),
        "maximo": float(montos.max()),
    }


def _separacion(ajuste: pd.DataFrame) -> list[dict]:
    """Diferencia de medias entre clases dividida por la desviacion combinada (d de Cohen)."""
    fraude, legitima = ajuste[ajuste["Class"] == 1], ajuste[ajuste["Class"] == 0]
    filas = []
    for variable in (*VARIABLES, "Amount"):
        a, b = fraude[variable], legitima[variable]
        combinada = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2) if len(a) > 1 else np.nan
        d = float((a.mean() - b.mean()) / combinada) if combinada and combinada > 0 else 0.0
        filas.append(
            {
                "variable": variable,
                "media_fraude": float(a.mean()) if len(a) else None,
                "media_legitima": float(b.mean()),
                "diferencia_estandarizada": d,
            }
        )
    return sorted(filas, key=lambda f: abs(f["diferencia_estandarizada"]), reverse=True)


def resumir(ajuste: pd.DataFrame, umbral_monto: float) -> dict:
    """Resumen estadistico de la parte de ajuste."""
    clase = ajuste["Class"]
    sobre = ajuste["Amount"] > umbral_monto
    notas = [AVISO]
    tiene_time = "Time" in ajuste.columns
    if not tiene_time:
        notas.append("Falta la columna Time: se omite la distribucion por hora.")
    return {
        "parte": "ajuste",
        "filas": int(len(ajuste)),
        "fraudes": int(clase.sum()),
        "tasa_fraude": float(clase.mean()),
        "tiene_time": tiene_time,
        "monto": {
            "legitima": _describir(ajuste.loc[clase == 0, "Amount"]),
            "fraude": _describir(ajuste.loc[clase == 1, "Amount"]),
        },
        "sobre_umbral": {
            "umbral": umbral_monto,
            "legitimas": int((sobre & (clase == 0)).sum()),
            "fraudes": int((sobre & (clase == 1)).sum()),
        },
        "separacion": _separacion(ajuste),
        "notas": notas,
    }


def _figura_montos(ajuste: pd.DataFrame, umbral: float, ruta: Path) -> None:
    figura, ejes = _ejes()
    bordes = np.linspace(0, np.log10(max(ajuste["Amount"].max(), umbral) + 1) + 0.1, 50)
    for valor, nombre, color in ((0, "Legítimas", COLOR_LEGITIMA), (1, "Fraudes", COLOR_FRAUDE)):
        montos = np.log10(ajuste.loc[ajuste["Class"] == valor, "Amount"] + 1)
        if len(montos):
            ejes.hist(
                montos,
                bins=bordes,
                density=True,
                histtype="step",
                linewidth=2,
                color=color,
                label=f"{nombre} ({len(montos)})",
            )
    ejes.axvline(np.log10(umbral + 1), color=TEXTO_SECUNDARIO, linewidth=1, linestyle="--")
    ejes.annotate(
        f"umbral de la regla: {umbral:,.0f}",
        xy=(np.log10(umbral + 1), 0.98),
        xycoords=("data", "axes fraction"),
        xytext=(4, 0),
        textcoords="offset points",
        va="top",
        fontsize=8,
        color=TEXTO_SECUNDARIO,
    )
    marcas = [0, 1, 10, 100, 1000, 10000]
    ejes.set_xticks([np.log10(m + 1) for m in marcas], [f"{m:,}" for m in marcas])
    ejes.set_xlabel("Monto (escala logarítmica, unidades de Amount)", color=TEXTO_SECUNDARIO)
    ejes.set_ylabel("Densidad", color=TEXTO_SECUNDARIO)
    ejes.legend(frameon=False, fontsize=9, labelcolor=TEXTO)
    _titulo(
        figura,
        ejes,
        "Distribución del monto por clase",
        "Cada clase normalizada por separado. " + AVISO_FIGURA,
    )
    _guardar(figura, ruta)


def _figura_separacion(separacion: list[dict], ruta: Path) -> None:
    figura, ejes = _ejes(8, 7)
    ejes.grid(axis="y", visible=False)
    ejes.grid(axis="x", color=REJILLA, linewidth=0.8)
    filas = list(reversed(separacion))
    valores = [abs(f["diferencia_estandarizada"]) for f in filas]
    ejes.barh([f["variable"] for f in filas], valores, height=0.7, color=COLOR_LEGITIMA)
    for posicion, fila in enumerate(filas[-5:], start=len(filas) - 5):
        ejes.annotate(
            f"{fila['diferencia_estandarizada']:+.2f}",
            xy=(abs(fila["diferencia_estandarizada"]), posicion),
            xytext=(4, 0),
            textcoords="offset points",
            va="center",
            fontsize=8,
            color=TEXTO,
        )
    ejes.set_xlabel(
        "|diferencia de medias| / desviación combinada (d de Cohen)", color=TEXTO_SECUNDARIO
    )
    _titulo(
        figura,
        ejes,
        "Separación entre fraudes y legítimas por variable",
        "Signo en las cinco mayores. " + AVISO_FIGURA,
    )
    _guardar(figura, ruta)


def _figura_hora(ajuste: pd.DataFrame, ruta: Path) -> None:
    figura, ejes = _ejes()
    hora = (ajuste["Time"] // 3600 % 24).astype(int)
    tasa = ajuste.groupby(hora)["Class"].mean().reindex(range(24), fill_value=0) * 100
    ejes.plot(tasa.index, tasa.values, color=COLOR_FRAUDE, linewidth=2, marker="o", markersize=4)
    ejes.set_xticks(range(0, 24, 3))
    ejes.set_xlabel(
        "Hora relativa al inicio del registro (Time // 3600 mod 24)", color=TEXTO_SECUNDARIO
    )
    ejes.set_ylabel("Fraudes por cada 100 transacciones", color=TEXTO_SECUNDARIO)
    _titulo(
        figura,
        ejes,
        "Proporción de fraudes por hora",
        "Time cuenta segundos desde la primera transacción.\n" + AVISO_FIGURA,
    )
    _guardar(figura, ruta)


def _markdown(resumen: dict) -> str:
    m = resumen["monto"]

    def fila(nombre: str, d: dict) -> str:
        if not d["n"]:
            return f"| {nombre} | 0 | - | - | - | - |"
        return (
            f"| {nombre} | {d['n']} | {d['media']:.2f} | {d['mediana']:.2f} | "
            f"{d['p95']:.2f} | {d['maximo']:.2f} |"
        )

    s = resumen["sobre_umbral"]
    lineas = [
        "# Análisis exploratorio (parte de ajuste)",
        "",
        *[f"> {nota}" for nota in resumen["notas"]],
        "",
        f"- Transacciones: {resumen['filas']}",
        f"- Fraudes: {resumen['fraudes']} ({resumen['tasa_fraude']:.4%})",
        f"- Columna Time: {'presente' if resumen['tiene_time'] else 'ausente'}",
        "",
        "## Monto por clase",
        "",
        "| Clase | n | Media | Mediana | P95 | Máximo |",
        "|---|---|---|---|---|---|",
        fila("Legítima", m["legitima"]),
        fila("Fraude", m["fraude"]),
        "",
        f"Montos mayores que {s['umbral']:g}: {s['legitimas']} legítimas y {s['fraudes']} fraudes.",
        "",
        "## Variables con mayor separación entre clases",
        "",
        "| Variable | d de Cohen |",
        "|---|---|",
        *[
            f"| {f['variable']} | {f['diferencia_estandarizada']:+.3f} |"
            for f in resumen["separacion"][:10]
        ],
        "",
        "## Figuras",
        "",
        *[f"- `{nombre}`" for nombre in resumen["figuras"]],
        "",
    ]
    return "\n".join(lineas)


def escribir(ajuste: pd.DataFrame, umbral_monto: float, carpeta: Path) -> list[str]:
    """Escribe `resumen.json`, `resumen.md` y las figuras. Devuelve los nombres creados."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    resumen = resumir(ajuste, umbral_monto)
    figuras = ["montos_por_clase.png", "separacion_por_variable.png"]
    _figura_montos(ajuste, umbral_monto, carpeta / figuras[0])
    _figura_separacion(resumen["separacion"], carpeta / figuras[1])
    if resumen["tiene_time"]:
        figuras.append("fraudes_por_hora.png")
        _figura_hora(ajuste, carpeta / figuras[-1])
    resumen["figuras"] = figuras
    (carpeta / "resumen.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (carpeta / "resumen.md").write_text(_markdown(resumen), encoding="utf-8")
    return ["resumen.json", "resumen.md", *figuras]
