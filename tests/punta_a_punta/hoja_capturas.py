"""Hoja de contactos de las capturas de la pagina, impresa en el registro de la CI.

El entorno de desarrollo lee los registros de GitHub Actions pero no puede descargar los
artefactos. Para que quien desarrolla mire las capturas de N2 antes de cerrar una fase, este
guion reduce las capturas, las junta en hojas JPEG y las imprime en base64 entre marcas. Las
capturas completas siguen en el artefacto `capturas-pagina`.

Uso: python tests/punta_a_punta/hoja_capturas.py capturas_ci
"""

import base64
import io
import sys
from pathlib import Path

from PIL import Image

HOJAS = {
    "pantallas": [
        f"pantalla_{ancho}_{tema}" for tema in ("claro", "oscuro") for ancho in (640, 1280, 1920)
    ],
    "paginas": [f"pagina_{ancho}_{tema}" for tema in ("claro", "oscuro") for ancho in (640, 1280)],
    "estados": [
        "vacio_1280_claro",
        "vacio_1280_oscuro",
        "presentacion_claro",
        "presentacion_oscuro",
        "estado-error-api_claro",
        "estado-error-n8n_claro",
    ],
}
ANCHO_CELDA = 900
ALTO_MAXIMO = 2400


def hoja(carpeta: Path, nombres: list[str]) -> bytes:
    imagenes = []
    for nombre in nombres:
        ruta = carpeta / f"{nombre}.png"
        if not ruta.is_file():
            continue
        imagen = Image.open(ruta).convert("RGB")
        escala = ANCHO_CELDA / imagen.width if imagen.width > ANCHO_CELDA else 1
        imagen = imagen.resize((int(imagen.width * escala), int(imagen.height * escala)))
        imagenes.append(imagen.crop((0, 0, imagen.width, min(imagen.height, ALTO_MAXIMO))))
    columnas = 3
    filas = (len(imagenes) + columnas - 1) // columnas
    alto_fila = [
        max((im.height for im in imagenes[f * columnas : (f + 1) * columnas]), default=0)
        for f in range(filas)
    ]
    lienzo = Image.new("RGB", (ANCHO_CELDA * columnas, sum(alto_fila) or 1), "white")
    y = 0
    for f in range(filas):
        for c, im in enumerate(imagenes[f * columnas : (f + 1) * columnas]):
            lienzo.paste(im, (c * ANCHO_CELDA, y))
        y += alto_fila[f]
    salida = io.BytesIO()
    lienzo.save(salida, "JPEG", quality=70, optimize=True)
    return salida.getvalue()


def main() -> int:
    carpeta = Path(sys.argv[1])
    for nombre, capturas in HOJAS.items():
        datos = base64.b64encode(hoja(carpeta, capturas)).decode()
        print(f"=== HOJA {nombre} INICIO ===")
        for i in range(0, len(datos), 4000):
            print(datos[i : i + 4000])
        print(f"=== HOJA {nombre} FIN ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
