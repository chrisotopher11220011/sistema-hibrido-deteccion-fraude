"""Estilo comun de las figuras (skill `dataviz`).

Un eje por grafica, marcas finas, rejilla tenue y recesiva, texto en tintas de texto y nunca
en el color de la serie. Colores categoricos de la paleta de referencia en orden fijo
(azul, naranja, aqua); el rojo queda reservado para estados. Gris para lineas base.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

COLOR_LEGITIMA = "#2a78d6"  # categorico, posicion 1
COLOR_FRAUDE = "#eb6834"  # categorico, posicion 2
SERIE_1 = "#2a78d6"  # azul
SERIE_2 = "#eb6834"  # naranja
SERIE_3 = "#1baf7a"  # aqua: bajo 3:1 en fondo claro, lleva etiqueta directa
SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_SECUNDARIO = "#52514e"
NEUTRO = "#8a8984"  # lineas base y referencias
REJILLA = "#e4e3df"


def ejes(ancho: float = 8, alto: float = 4.5):
    figura, ejes = plt.subplots(figsize=(ancho, alto), dpi=110)
    figura.patch.set_facecolor(SUPERFICIE)
    ejes.set_facecolor(SUPERFICIE)
    for lado in ("top", "right"):
        ejes.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ejes.spines[lado].set_color(REJILLA)
    ejes.tick_params(colors=TEXTO_SECUNDARIO, labelsize=9)
    ejes.grid(axis="y", color=REJILLA, linewidth=0.8)
    ejes.set_axisbelow(True)
    return figura, ejes


def titulo(figura, ejes, titulo: str, subtitulo: str) -> None:
    ejes.set_title(subtitulo, loc="left", fontsize=9, color=TEXTO_SECUNDARIO, pad=8)
    figura.suptitle(titulo, x=0.02, ha="left", fontsize=12, color=TEXTO, fontweight="bold")


def guardar(figura, ruta: Path) -> None:
    figura.tight_layout()
    figura.savefig(ruta, facecolor=SUPERFICIE)
    plt.close(figura)
