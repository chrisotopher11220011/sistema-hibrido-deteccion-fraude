"""Lote de demostracion (docs/spec.md, seccion 12; ADR 0014).

Archivo fijo que envian `tareas demostrar` y la pagina (fase 6): una muestra con semilla de
la parte de **prueba** con fraudes y no fraudes, las transacciones sinteticas de ubicacion y
unas entradas invalidas fijas. La etiqueta real va en cada elemento, aparte de la transaccion:
nunca viaja hacia la API ni hacia n8n. Con la muestra para pruebas no es reportable.
"""

import json
from pathlib import Path

import numpy as np

from fraude.configuracion import cargar
from fraude.datos import ErrorDatos
from fraude.preparar import cargar_preparados
from fraude.transaccion import VARIABLES

# Entradas que la API rechaza (422). La ultima pasa la validacion minima de n8n y la rechaza
# la API: asi el lote recorre las dos ramas de «entrada invalida».
INVALIDAS = (
    ("sin id_transaccion", {"origen": "original", "monto": 120.0}),
    ("monto como texto", {"id_transaccion": "inv-0002", "origen": "original", "monto": "1500"}),
    ("origen desconocido", {"id_transaccion": "inv-0003", "origen": "tarjeta", "monto": 80.0}),
    ("monto negativo", {"id_transaccion": "inv-0004", "origen": "sintetico", "monto": -5.0}),
    (
        "trae la etiqueta real (Class)",
        {"id_transaccion": "inv-0005", "origen": "original", "monto": 30.0, "Class": 1},
    ),
    (
        "variables incompletas (solo V1)",
        {
            "id_transaccion": "inv-0006",
            "origen": "original",
            "monto": 45.0,
            "variables": {"V1": 0.5},
        },
    ),
)


def ruta(raiz: Path, muestra: bool = False) -> Path:
    base = Path(raiz) / "datos" / ("muestra" if muestra else "")
    return base / "demostracion" / "lote.json"


def _originales(raiz: Path, muestra: bool, params: dict, rng) -> list[dict]:
    df, partes = cargar_preparados(raiz, muestra)
    prueba = np.flatnonzero(partes == "prueba")
    clase = df["Class"].to_numpy()[prueba]
    fraudes, legitimas = prueba[clase == 1], prueba[clase == 0]
    n_fraudes = min(int(params["fraudes"]), len(fraudes))
    n_legitimas = int(params["legitimas"])
    if n_legitimas > len(legitimas):
        raise ErrorDatos(f"La parte de prueba tiene solo {len(legitimas)} no fraudes")
    filas = np.concatenate(
        [
            rng.choice(fraudes, size=n_fraudes, replace=False),
            rng.choice(legitimas, size=n_legitimas, replace=False),
        ]
    )
    elementos = []
    for fila in filas.tolist():
        registro = df.iloc[fila]
        transaccion = {
            "id_transaccion": f"t-{fila:06d}",
            "origen": "original",
            "monto": float(registro["Amount"]),
            "variables": {v: float(registro[v]) for v in VARIABLES},
        }
        elementos.append(
            {
                "tipo": "original",
                "fila": fila,
                "etiqueta_real": int(registro["Class"]),
                "descripcion": None,
                "transaccion": transaccion,
            }
        )
    return elementos


def _sinteticas(raiz: Path, cantidad: int) -> list[dict]:
    archivo = Path(raiz) / "datos" / "sinteticos" / "ubicacion.json"
    if not archivo.is_file():
        raise ErrorDatos("No hay transacciones sinteticas. Ejecuta antes: preparar")
    sinteticas = json.loads(archivo.read_text(encoding="utf-8"))[:cantidad]
    return [
        {
            "tipo": "sintetico",
            "fila": None,
            "etiqueta_real": None,
            "descripcion": None,
            "transaccion": t,
        }
        for t in sinteticas
    ]


def generar(raiz: Path, muestra: bool = False) -> dict:
    """Genera el lote, lo guarda en `ruta(raiz, muestra)` y lo devuelve. Es determinista."""
    raiz = Path(raiz)
    params = cargar(raiz, "modelo")["demostracion"]
    rng = np.random.default_rng(int(params["semilla"]))
    elementos = _originales(raiz, muestra, params, rng)
    elementos += _sinteticas(raiz, int(params["sinteticas"]))
    elementos = [elementos[i] for i in rng.permutation(len(elementos))]
    # Las invalidas, repartidas a lo largo del lote en posiciones fijas.
    paso = max(1, len(elementos) // (len(INVALIDAS) + 1))
    for k, (descripcion, cuerpo) in enumerate(INVALIDAS, start=1):
        invalida = {
            "tipo": "invalida",
            "fila": None,
            "etiqueta_real": None,
            "descripcion": descripcion,
            "transaccion": cuerpo,
        }
        elementos.insert(min(len(elementos), k * paso + k - 1), invalida)
    for n, elemento in enumerate(elementos, start=1):
        elemento["n"] = n
    tipos = [e["tipo"] for e in elementos]
    lote = {
        "version": 1,
        "fuente": "muestra" if muestra else "real",
        "reportable": not muestra,
        "semilla": int(params["semilla"]),
        "parte": "prueba",
        "nota": (
            "Lote de demostracion. Las originales salen de la parte de prueba; la etiqueta "
            "real solo sirve para mostrarla en la pagina y nunca viaja en la transaccion."
        ),
        "conteos": {
            "total": len(tipos),
            "original": tipos.count("original"),
            "sintetico": tipos.count("sintetico"),
            "invalida": tipos.count("invalida"),
            "fraudes": sum(1 for e in elementos if e["etiqueta_real"] == 1),
        },
        "elementos": elementos,
    }
    destino = ruta(raiz, muestra)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(lote, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return lote
