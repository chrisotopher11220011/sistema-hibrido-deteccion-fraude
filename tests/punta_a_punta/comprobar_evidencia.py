"""Comprueba, en la CI, la carpeta de evidencia mas reciente (N2).

Uso: python tests/punta_a_punta/comprobar_evidencia.py [--con-anfitrion]
"""

import json
import os
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
RESULTADOS = RAIZ / "resultados"
DATOS = RAIZ / "datos"
ARCHIVOS = (
    "RESUMEN.md",
    "anfitrion.json",
    "entorno.json",
    "version.json",
    "errores.json",
    "OBSERVACIONES.md",
    "datos.json",
    "eda/resumen.json",
    "modelo.json",
    "metricas.json",
    "comparativa.md",
    "analisis_errores/resumen.json",
    "analisis_errores/fraudes_no_detectados.csv",
    "analisis_errores/falsas_alarmas.csv",
)
FIGURAS = {
    "comparativa_prueba.png",
    "curva_pr_prueba.png",
    "semillas.png",
    "umbral_validacion.png",
}


def main() -> int:
    con_anfitrion = "--con-anfitrion" in sys.argv
    carpetas = sorted(p for p in RESULTADOS.iterdir() if p.is_dir() and p.name != "en_curso")
    if not carpetas:
        print("No hay ninguna carpeta de evidencia")
        return 1
    carpeta = carpetas[-1]
    print(f"Evidencia: {carpeta.name}")
    fallos = []

    for nombre in ARCHIVOS:
        if not (carpeta / nombre).is_file():
            fallos.append(f"falta {nombre}")
    if not carpeta.with_suffix(".zip").is_file():
        fallos.append("falta el .zip")
    else:
        with zipfile.ZipFile(carpeta.with_suffix(".zip")) as z:
            if f"{carpeta.name}/RESUMEN.md" not in z.namelist():
                fallos.append("el .zip no contiene RESUMEN.md")

    if not fallos:
        errores = json.loads((carpeta / "errores.json").read_text())
        if errores["hay_errores"]:
            fallos.append(f"errores.json informa fallos: {errores['errores']}")
        version = json.loads((carpeta / "version.json").read_text())
        if version["commit"] in ("", "sin-commit"):
            fallos.append("version.json no trae el commit")
        datos = json.loads((carpeta / "datos.json").read_text())
        if datos.get("estado") != "ok":
            fallos.append(f"preparar no termino bien: {datos.get('error')}")
        elif datos.get("fuente") != "muestra" or datos.get("reportable") is not False:
            fallos.append("en la CI los datos deben ser la muestra, marcada no reportable")
        if not list((carpeta / "eda").glob("*.png")):
            fallos.append("eda/ no trae figuras")
        for nombre in ("modelo.json", "metricas.json"):
            informe = json.loads((carpeta / nombre).read_text())
            if informe.get("estado") != "ok":
                fallos.append(f"{nombre} no termino bien: {informe.get('error')}")
            elif informe.get("reportable") is not False:
                fallos.append(f"en la CI {nombre} debe venir de la muestra, marcada no reportable")
        metricas = json.loads((carpeta / "metricas.json").read_text())
        if metricas.get("estado") == "ok":
            principal = metricas["principal"]
            if len(principal["configuraciones"]) != 4 or len(principal["lineas_base"]) != 3:
                fallos.append("metricas.json no trae las cuatro configuraciones y tres lineas base")
            if len(metricas["semillas"]["por_semilla"]) != 10:
                fallos.append("metricas.json no trae las diez semillas")
            if metricas["analisis_errores"]["parte"] != "validacion":
                fallos.append("el analisis de errores no sale de validacion")
        if "no es un resultado" not in (carpeta / "comparativa.md").read_text().lower():
            fallos.append("comparativa.md no avisa de que la muestra no es un resultado")
        figuras = {p.name for p in (carpeta / "figuras").glob("*.png")}
        if figuras != FIGURAS:
            fallos.append(f"figuras/ trae {sorted(figuras)}")
        sinteticos = DATOS / "sinteticos" / "ubicacion.json"
        if not sinteticos.is_file():
            fallos.append("falta datos/sinteticos/ubicacion.json")
        elif {t["origen"] for t in json.loads(sinteticos.read_text())} != {"sintetico"}:
            fallos.append("los datos sinteticos traen transacciones que no son sinteticas")
        if con_anfitrion:
            anfitrion = json.loads((carpeta / "anfitrion.json").read_text())
            if "uso_sudo" not in anfitrion:
                fallos.append("anfitrion.json no viene del guion ./fraude")
            for registro in ("api.log", "n8n.log"):
                if not (carpeta / "registros" / registro).is_file():
                    fallos.append(f"falta registros/{registro}")

    # Supuesto S7: nada de resultados/ ni de datos/ queda a nombre de root.
    for base in (RESULTADOS, DATOS):
        for ruta in [base, *base.rglob("*")]:
            if ruta.name == ".gitkeep":
                continue
            if ruta.stat().st_uid != os.getuid():
                fallos.append(f"{ruta} pertenece al uid {ruta.stat().st_uid}, no al usuario")
                break

    for fallo in fallos:
        print(f"FALLO: {fallo}")
    if not fallos:
        print((carpeta / "RESUMEN.md").read_text())
        print("Evidencia correcta")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
