"""Comprobaciones estaticas de la pagina de simulacion (docs/spec.md, seccion 13)."""

import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "web"
TEXTO = [p for p in WEB.rglob("*") if p.suffix in {".html", ".css", ".js", ".md"}]
# Direcciones permitidas: el espacio de nombres de SVG (no se descarga nada).
PERMITIDAS = {"http://www.w3.org/2000/svg"}
PROHIBIDAS = (
    r"fraude confirmado",
    r"(?<!no )confirm(?:a|o|ó|ado) (?:el )?fraude",
    r"\bes fraude\b",
    r"fraude detectado",
    r"transacci[oó]n fraudulenta",
)


def test_hay_pagina_estilos_codigo_y_diseno():
    for nombre in ("index.html", "estilos.css", "app.js", "DISENO.md"):
        assert (WEB / nombre).is_file(), nombre


@pytest.mark.parametrize("archivo", TEXTO, ids=lambda p: p.name)
def test_sin_recursos_externos(archivo):
    direcciones = set(re.findall(r"https?://[^\s'\")]+", archivo.read_text(encoding="utf-8")))
    if archivo.name == "DISENO.md":
        return  # documentacion: puede citar fuentes
    assert direcciones <= PERMITIDAS, direcciones - PERMITIDAS


def test_sin_paso_de_compilacion():
    assert not (WEB / "package.json").exists()
    assert '<script type="module" src="/recursos/app.js">' in (WEB / "index.html").read_text()


@pytest.mark.parametrize("archivo", TEXTO, ids=lambda p: p.name)
def test_el_sistema_solo_senala(archivo):
    texto = archivo.read_text(encoding="utf-8").lower()
    for frase in PROHIBIDAS:
        assert not re.search(frase, texto), f"{archivo.name}: {frase}"


def test_aviso_fijo_de_simulacion():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert '<html lang="es">' in html
    assert "Simulación académica con datos públicos y sintéticos" in html
    assert "señala transacciones para revisión humana; no confirma fraude" in html


def test_la_pagina_solo_envia_la_transaccion():
    codigo = (WEB / "app.js").read_text(encoding="utf-8")
    # La etiqueta solo se lee del elemento del lote, nunca se escribe en lo que se envia.
    usos = re.findall(r"[\w.]*etiqueta_real", codigo)
    assert usos and set(usos) == {"elemento.etiqueta_real"}, usos
    assert "enviarTransaccion(elemento.transaccion, elemento.n)" in codigo
    envios = re.findall(r"pedir\('POST', `/simulacion/transacciones[^\n]*", codigo)
    assert envios == ["pedir('POST', `/simulacion/transacciones?${consulta(n)}`, transaccion);"]


def test_fuente_incluida_con_su_licencia():
    assert (WEB / "fuentes" / "atkinson-hyperlegible-next.woff2").is_file()
    assert "SIL Open Font License" in (WEB / "fuentes" / "OFL.txt").read_text(encoding="utf-8")


def test_tokens_de_los_temas_y_movimiento_reducido():
    css = (WEB / "estilos.css").read_text(encoding="utf-8")
    assert "prefers-color-scheme: dark" in css
    assert ':root[data-tema="oscuro"]' in css
    assert ":root[data-presentacion]" in css
    assert "prefers-reduced-motion: reduce" in css
    assert ":focus-visible" in css


def _node():
    import os
    import shutil

    node = shutil.which("node")
    if node is None:
        if os.environ.get("FRAUDE_EXIGIR_NODE") == "1":
            pytest.fail("Hace falta Node.js (FRAUDE_EXIGIR_NODE=1)")
        pytest.skip("Sin Node.js")
    return node


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("1250", 1250.0),
        ("1.500", 1500.0),  # punto de miles, como muestra la pagina
        ("1.250,50", 1250.5),
        ("1250,5", 1250.5),
        ("12.5", 12.5),
        ("1,250.50", 1250.5),
        ("1.250.000", 1250000.0),
        (" 2 500 ", 2500.0),
        ("0", 0.0),
        ("", None),
        ("-5", None),
        ("abc", None),
        ("1,2,3", None),
        ("1.2.3", None),
        ("1500,", None),
        ("12.34,5", None),
    ],
)
def test_lectura_del_monto_manual(texto, esperado):
    import json
    import subprocess

    codigo = (
        "import { leerMonto } from './web/formato.js';"
        f"const v = leerMonto({json.dumps(texto)});"
        "process.stdout.write(JSON.stringify(Number.isNaN(v) ? null : v));"
    )
    salida = subprocess.run(
        [_node(), "--input-type=module", "-e", codigo],
        cwd=WEB.parent,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert json.loads(salida) == esperado
