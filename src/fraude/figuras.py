"""Figuras de la evaluacion (docs/spec.md, secciones 15 y 16), con la skill `dataviz`.

- Un eje de medida por panel; comparaciones en paneles pequenos, nunca dos escalas.
- Colores categoricos en orden fijo (azul, naranja, aqua) con un segundo codigo (trazo y
  etiqueta directa): la identidad nunca depende solo del color. Gris para lineas base.
- Cada figura dice en el subtitulo de que parte salen los datos; con la muestra, el aviso
  de que no es un resultado.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import precision_recall_curve

from fraude.graficas import (
    NEUTRO,
    REJILLA,
    SERIE_1,
    SERIE_2,
    SERIE_3,
    SUPERFICIE,
    TEXTO,
    TEXTO_SECUNDARIO,
    ejes,
    guardar,
    titulo,
)

FILAS_COMPARATIVA = (
    ("configuraciones", "solo_reglas"),
    ("configuraciones", "solo_modelo"),
    ("configuraciones", "hibrido_cualquier"),
    ("configuraciones", "hibrido_prioritaria"),
    ("lineas_base", "monto"),
    ("lineas_base", "azar"),
)


def _subtitulo(texto: str, aviso: str | None) -> str:
    return texto + ("\n" + aviso if aviso else "")


def _f1(precision: np.ndarray, exhaustividad: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.nan_to_num(2 * precision * exhaustividad / (precision + exhaustividad))


def _separar(posiciones: list[float], minimo: float) -> list[float]:
    """Separa etiquetas directas para que no se pisen, conservando su orden vertical."""
    orden = sorted(range(len(posiciones)), key=lambda i: posiciones[i])
    resultado = list(posiciones)
    for anterior, actual in zip(orden, orden[1:], strict=False):
        resultado[actual] = max(resultado[actual], resultado[anterior] + minimo)
    return resultado


def umbral_validacion(datos: dict, umbrales: dict, ruta: Path, aviso: str | None) -> None:
    figura, eje = ejes(8.6, 4.8)
    precision, exhaustividad, cortes = precision_recall_curve(datos["y_val"], datos["p_val"])
    precision, exhaustividad = precision[:-1], exhaustividad[:-1]
    series = (
        ("Precisión", precision, SERIE_1, "-"),
        ("Exhaustividad", exhaustividad, SERIE_2, "--"),
        ("F1", _f1(precision, exhaustividad), SERIE_3, ":"),
    )
    for nombre, valores, color, trazo in series:
        eje.plot(cortes, valores, color=color, linewidth=2, linestyle=trazo, label=nombre)
    finales = _separar([float(valores[-1]) for _, valores, _, _ in series], 0.06)
    for (nombre, valores, _, _), y in zip(series, finales, strict=True):
        eje.annotate(
            nombre,
            xy=(cortes[-1], valores[-1]),
            xytext=(cortes[-1] + 0.01 * (cortes[-1] - cortes[0]), y),
            textcoords="data",
            xycoords="data",
            ha="left",
            va="center",
            fontsize=8,
            color=TEXTO,
        )
    # Revision a la izquierda de su linea y prioritaria a la derecha: no se pisan aunque
    # los dos umbrales coincidan.
    for clave, nombre, desplazamiento, alineacion in (
        ("umbral_revision", "revisión (máx. F1)", -4, "right"),
        ("umbral_prioritaria", "prioritaria (máx. F0,5)", 4, "left"),
    ):
        eje.axvline(umbrales[clave], color=NEUTRO, linewidth=1, linestyle="--")
        eje.annotate(
            f"{nombre}: {umbrales[clave]:.3f}".replace(".", ","),
            xy=(umbrales[clave], 0.5),
            xycoords=("data", "axes fraction"),
            xytext=(desplazamiento, 0),
            textcoords="offset points",
            ha=alineacion,
            va="center",
            fontsize=8,
            color=TEXTO_SECUNDARIO,
            backgroundcolor=SUPERFICIE,
        )
    eje.set_ylim(0, 1.05)
    eje.set_xlabel("Umbral sobre la puntuación de Isolation Forest", color=TEXTO_SECUNDARIO)
    eje.set_ylabel("Valor de la métrica", color=TEXTO_SECUNDARIO)
    eje.legend(frameon=False, fontsize=9, labelcolor=TEXTO, loc="lower left")
    titulo(
        figura,
        eje,
        "Precisión, exhaustividad y F1 según el umbral",
        _subtitulo("Parte de validación: aquí se eligen los umbrales.", aviso),
    )
    guardar(figura, ruta)


def curva_pr_prueba(datos: dict, principal: dict, ruta: Path, aviso: str | None) -> None:
    figura, eje = ejes(7, 5.6)
    pm = principal["puntuaciones"]
    for nombre, puntuacion, clave, color, trazo in (
        ("Isolation Forest", datos["p"], "modelo", SERIE_1, "-"),
        ("Monto (línea base)", datos["monto"], "monto", SERIE_2, "--"),
    ):
        precision, exhaustividad, _ = precision_recall_curve(datos["y"], puntuacion)
        valor = pm[clave]["precision_media"]["valor"]
        eje.step(
            exhaustividad,
            precision,
            where="post",
            color=color,
            linewidth=2,
            linestyle=trazo,
            label=f"{nombre}: precisión media {valor:.3f}".replace(".", ","),
        )
    prevalencia = float(np.mean(datos["y"]))
    eje.axhline(prevalencia, color=NEUTRO, linewidth=1, linestyle=":")
    eje.annotate(
        "tasa de fraude (azar)",
        xy=(1.0, prevalencia),
        xytext=(-4, 4),
        textcoords="offset points",
        ha="right",
        fontsize=8,
        color=TEXTO_SECUNDARIO,
    )
    eje.set_xlim(0, 1.02)
    eje.set_ylim(0, 1.05)
    eje.set_xlabel("Exhaustividad", color=TEXTO_SECUNDARIO)
    eje.set_ylabel("Precisión", color=TEXTO_SECUNDARIO)
    eje.legend(
        frameon=False,
        fontsize=9,
        labelcolor=TEXTO,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
        ncol=1,
    )
    titulo(
        figura,
        eje,
        "Curva de precisión y exhaustividad",
        _subtitulo("Parte de prueba, métricas agregadas.", aviso),
    )
    guardar(figura, ruta)


def comparativa_prueba(principal: dict, ruta: Path, aviso: str | None) -> None:
    figura, paneles = plt.subplots(1, 3, figsize=(11, 4.6), dpi=110, sharey=True)
    figura.patch.set_facecolor(SUPERFICIE)
    filas = list(reversed(FILAS_COMPARATIVA))
    etiquetas = [principal[g][n]["nombre"] for g, n in filas]
    for eje, (metrica, nombre_metrica) in zip(
        paneles,
        (("precision", "Precisión"), ("exhaustividad", "Exhaustividad"), ("f1", "F1")),
        strict=True,
    ):
        eje.set_facecolor(SUPERFICIE)
        for lado in ("top", "right", "left"):
            eje.spines[lado].set_visible(False)
        eje.spines["bottom"].set_color(REJILLA)
        eje.tick_params(colors=TEXTO_SECUNDARIO, labelsize=9, length=0)
        eje.grid(axis="x", color=REJILLA, linewidth=0.8)
        eje.set_axisbelow(True)
        for y, (grupo, nombre) in enumerate(filas):
            entrada = principal[grupo][nombre][metrica]
            color = SERIE_1 if grupo == "configuraciones" else NEUTRO
            if entrada["valor"] is None:
                eje.annotate("indefinida", (0.02, y), va="center", fontsize=8, color=NEUTRO)
                continue
            ic = entrada["ic95"]
            if ic["inferior"] is not None:
                eje.plot([ic["inferior"], ic["superior"]], [y, y], color=color, linewidth=2)
            eje.plot(entrada["valor"], y, "o", color=color, markersize=7, zorder=3)
        eje.set_xlim(-0.03, 1.03)
        eje.set_title(nombre_metrica, loc="left", fontsize=10, color=TEXTO)
    paneles[0].set_yticks(range(len(filas)), etiquetas)
    figura.suptitle(
        "Configuraciones y líneas base: valor e intervalo del 95 %",
        x=0.02,
        ha="left",
        fontsize=12,
        color=TEXTO,
        fontweight="bold",
    )
    figura.text(
        0.02,
        0.90,
        _subtitulo(
            "Parte de prueba. Azul: sistema; gris: líneas base. Bootstrap estratificado. "
            "«No alertar nunca» se omite: no tiene alertas.",
            aviso,
        ),
        fontsize=9,
        color=TEXTO_SECUNDARIO,
        va="top",
    )
    figura.tight_layout(rect=(0, 0, 1, 0.84 if aviso else 0.88))
    figura.savefig(ruta, facecolor=SUPERFICIE)
    plt.close(figura)


def semillas(estabilidad: dict, ruta: Path, aviso: str | None) -> None:
    figura, eje = ejes(8, 3.8)
    eje.grid(axis="y", visible=False)
    eje.grid(axis="x", color=REJILLA, linewidth=0.8)
    configuraciones = (
        ("hibrido_prioritaria", "Híbrido, solo prioritarias"),
        ("hibrido_cualquier", "Híbrido, cualquier alerta"),
        ("solo_modelo", "Solo Isolation Forest"),
    )
    rng = np.random.default_rng(0)  # solo para separar puntos superpuestos
    for y, (clave, _) in enumerate(configuraciones):
        valores = [f[clave]["f1"] for f in estabilidad["por_semilla"] if f[clave]["f1"] is not None]
        if not valores:
            continue
        desplazamiento = rng.uniform(-0.12, 0.12, size=len(valores))
        eje.plot(valores, y + desplazamiento, "o", color=SERIE_1, markersize=6, alpha=0.75)
        media = float(np.mean(valores))
        eje.plot([media, media], [y - 0.25, y + 0.25], color=TEXTO, linewidth=2)
    eje.set_yticks(range(len(configuraciones)), [n for _, n in configuraciones])
    eje.set_xlabel("F1 en la parte de prueba (raya: media)", color=TEXTO_SECUNDARIO)
    n = len(estabilidad["por_semilla"])
    titulo(
        figura,
        eje,
        f"Estabilidad del F1 con {n} semillas",
        _subtitulo("Cada punto: un entrenamiento con sus umbrales elegidos en validación.", aviso),
    )
    guardar(figura, ruta)


AVISO_CORTO = "Muestra para pruebas: no es un resultado."


def escribir(informe: dict, datos: dict, carpeta: Path, muestra: bool) -> list[str]:
    """Escribe las cuatro figuras y devuelve sus nombres."""
    aviso = AVISO_CORTO if muestra else None
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    umbral_validacion(datos, informe["umbrales"], carpeta / "umbral_validacion.png", aviso)
    curva_pr_prueba(datos, informe["principal"], carpeta / "curva_pr_prueba.png", aviso)
    comparativa_prueba(informe["principal"], carpeta / "comparativa_prueba.png", aviso)
    semillas(informe["semillas"], carpeta / "semillas.png", aviso)
    return sorted(p.name for p in carpeta.glob("*.png"))
