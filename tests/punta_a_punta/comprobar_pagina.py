"""Comprueba la pagina de simulacion en un navegador real y guarda capturas (N2; tambien N1).

Recorre la pagina con Playwright (Chromium) contra la API en marcha:

- Uso completo con teclado: atajos, foco visible, revision desde la bandeja y formulario.
- La etiqueta real nunca viaja en una peticion y aparece despues del veredicto.
- Accesibilidad automatica con axe-core (WCAG 2.0, 2.1 y 2.2, niveles A y AA).
- «Reducir movimiento» desactiva las animaciones.
- Sin desbordamiento horizontal en ventana estrecha.
- Capturas en tres anchos (640, 1280 y 1920 px) por dos temas, mas el modo presentacion y los
  estados vacio y de error.

Uso:
  python tests/punta_a_punta/comprobar_pagina.py http://127.0.0.1:8000 \
      --axe /ruta/axe.min.js --salida resultados/capturas_ci [--chrome /usr/bin/google-chrome]

Necesita `playwright` (pip) y su Chromium, o `--chrome` con un Chrome instalado.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ANCHOS = (640, 1280, 1920)
TEMAS = ("light", "dark")
NOMBRE_TEMA = {"light": "claro", "dark": "oscuro"}
ETIQUETAS_AXE = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
# El aviso dice «no confirma fraude»: la negacion esta permitida.
FRASES_PROHIBIDAS = (
    r"fraude confirmado",
    r"(?<!no )confirm(?:a|o|ó|ado) (?:el )?fraude",
    r"\bes fraude\b",
    r"fraude detectado",
)


class Comprobacion:
    def __init__(self, salida: Path, axe: str):
        self.salida = salida
        self.axe = axe
        self.fallos: list[str] = []
        self.informe: dict = {"capturas": [], "axe": [], "comprobaciones": []}

    def anotar(self, nombre: str, ok: bool, detalle: str = "") -> None:
        self.informe["comprobaciones"].append({"nombre": nombre, "ok": ok, "detalle": detalle})
        marca = "bien" if ok else "FALLO"
        print(f"[{marca}] {nombre}{': ' + detalle if detalle else ''}")
        if not ok:
            self.fallos.append(f"{nombre}: {detalle}")

    def capturar(self, pagina: Page, nombre: str, completa: bool = True) -> None:
        archivo = self.salida / f"{nombre}.png"
        pagina.screenshot(path=str(archivo), full_page=completa)
        self.informe["capturas"].append(archivo.name)

    def accesibilidad(self, pagina: Page, contexto: str) -> None:
        pagina.add_script_tag(content=self.axe)
        resultado = pagina.evaluate(
            """async (etiquetas) => {
                const r = await axe.run(document, { runOnly: { type: 'tag', values: etiquetas } });
                return r.violations.map(v => ({
                    id: v.id, impacto: v.impact, ayuda: v.help,
                    nodos: v.nodes.slice(0, 5)
                        .map(n => n.target.join(' ') + ' :: ' + n.failureSummary)
                }));
            }""",
            ETIQUETAS_AXE,
        )
        self.informe["axe"].append({"contexto": contexto, "violaciones": resultado})
        detalle = "; ".join(f"{v['id']} ({len(v['nodos'])}): {v['nodos'][:2]}" for v in resultado)
        self.anotar(f"axe-core sin violaciones ({contexto})", not resultado, detalle)


def esperar_listo(pagina: Page) -> None:
    pagina.wait_for_function(
        "() => ['listo', 'error'].includes(document.getElementById('estado').dataset.tipo)",
        timeout=30_000,
    )


def evaluadas(pagina: Page) -> int:
    return pagina.evaluate("() => window.__simulacion.estado.registros.length")


def correr_lote(pagina: Page, limite_s: int = 300) -> None:
    pagina.select_option("#velocidad", "0")
    pagina.click("#boton-iniciar")
    pagina.wait_for_function(
        "() => document.getElementById('estado').dataset.tipo === 'fin'", timeout=limite_s * 1000
    )


def foco_visible(pagina: Page) -> str | None:
    """Descripcion del foco si es visible; None si no se ve."""
    return pagina.evaluate(
        """() => {
            const e = document.activeElement;
            if (!e || e === document.body) return null;
            const s = getComputedStyle(e);
            const visible = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) >= 2;
            return visible ? (e.id || e.tagName) : null;
        }"""
    )


def prueba_teclado(c: Comprobacion, navegador, base: str) -> None:
    contexto = navegador.new_context(viewport={"width": 1280, "height": 900})
    pagina = contexto.new_page()
    enviados: list[str] = []
    pagina.on(
        "request",
        lambda p: enviados.append(p.post_data or "") if "/simulacion/" in p.url else None,
    )
    pagina.goto(base)
    esperar_listo(pagina)

    # Tab hasta «Iniciar simulación», con el foco visible en cada parada.
    sin_foco = []
    for _ in range(12):
        pagina.keyboard.press("Tab")
        if foco_visible(pagina) is None:
            sin_foco.append(pagina.evaluate("() => document.activeElement.outerHTML.slice(0, 80)"))
        if pagina.evaluate("() => document.activeElement.id") == "boton-iniciar":
            break
    llego = pagina.evaluate("() => document.activeElement.id") == "boton-iniciar"
    c.anotar("con Tab se llega a «Iniciar simulación»", llego)
    c.anotar("el foco se ve en cada control", not sin_foco, str(sin_foco))

    # «S» envia una; la etiqueta llega despues del veredicto.
    pagina.evaluate("() => document.activeElement.blur()")
    with pagina.expect_response("**/simulacion/transacciones**"):
        pagina.keyboard.press("s")
    pagina.wait_for_function("() => window.__simulacion.estado.registros.length === 1")
    antes = pagina.evaluate(
        "() => [document.getElementById('caso-sello').textContent,"
        " document.getElementById('caso-etiqueta').textContent]"
    )
    pagina.wait_for_function(
        "() => document.getElementById('caso-etiqueta').textContent.includes('Etiqueta real')",
        timeout=5000,
    )
    c.anotar(
        "la etiqueta real aparece despues del veredicto",
        bool(antes[0]) and antes[1] == "",
        f"sello={antes[0]!r} etiqueta_al_llegar={antes[1]!r}",
    )
    for _ in range(14):
        with pagina.expect_response("**/simulacion/transacciones**"):
            pagina.keyboard.press("s")
        pagina.wait_for_function("() => !window.__simulacion.estado.ocupado")
    c.anotar(
        "«S» envia transacciones de una en una", evaluadas(pagina) == 15, str(evaluadas(pagina))
    )

    # Espacio inicia y pausa.
    pagina.keyboard.press(" ")
    pagina.wait_for_function("() => window.__simulacion.estado.corriendo")
    pagina.keyboard.press(" ")
    pagina.wait_for_function("() => !window.__simulacion.estado.corriendo")
    c.anotar("Espacio inicia y pausa la simulacion", True)

    # Revision desde la bandeja, solo con teclado.
    pagina.wait_for_function(
        "() => document.querySelectorAll('#bandeja-lista button').length > 0", timeout=10_000
    )
    pagina.locator("#bandeja-lista input").first.focus()
    pagina.keyboard.type("Revisado con teclado")
    pagina.keyboard.press("Tab")
    with pagina.expect_response("**/simulacion/revisiones**") as respuesta:
        pagina.keyboard.press("Enter")
    ok = respuesta.value.status == 200
    pagina.wait_for_function(
        "() => document.getElementById('bandeja-resultado').textContent.startsWith('Guardado')"
    )
    c.anotar("revision desde la bandeja con teclado (consecuencia visible)", ok)

    # Transaccion manual con teclado: monto alto y pais distinto -> alerta prioritaria.
    pagina.locator("#manual-monto").focus()
    pagina.keyboard.press("Control+A")
    pagina.keyboard.type("1500,50")
    pagina.locator("#manual-pais").focus()
    pagina.keyboard.press("Tab")
    with pagina.expect_response("**/simulacion/transacciones**"):
        pagina.keyboard.press("Enter")
    pagina.wait_for_function(
        "() => document.getElementById('caso-sello').dataset.nivel === 'alerta_prioritaria'"
        " && document.getElementById('caso-id').textContent.startsWith('manual-')"
    )
    razones = pagina.inner_text("#caso-razones")
    c.anotar(
        "transaccion manual de monto alto y pais distinto: alerta prioritaria con las dos reglas",
        "MONTO_ALTO_UBICACION_INUSUAL" in razones and "MONTO_ALTO:" in razones,
        razones.replace("\n", " | "),
    )
    c.anotar(
        "tras evaluar, el foco va al caso",
        pagina.evaluate("() => document.activeElement.id") == "caso",
    )

    # T, P y ? desde el teclado.
    pagina.evaluate("() => document.activeElement.blur()")
    pagina.keyboard.press("t")
    tema = pagina.evaluate("() => document.documentElement.dataset.tema")
    pagina.keyboard.press("p")
    presentacion = pagina.evaluate(
        "() => document.documentElement.hasAttribute('data-presentacion')"
    )
    pagina.keyboard.press("p")
    pagina.keyboard.press("t")
    pagina.keyboard.press("t")
    pagina.keyboard.press("?")
    abierto = pagina.evaluate("() => document.getElementById('dialogo-atajos').open")
    pagina.keyboard.press("Escape")
    c.anotar(
        "atajos T, P y ? funcionan",
        tema == "claro" and presentacion and abierto,
        f"tema={tema} presentacion={presentacion} dialogo={abierto}",
    )

    # Ninguna peticion llevo la etiqueta real.
    con_etiqueta = [e for e in enviados if "etiqueta_real" in e]
    c.anotar(
        "ninguna peticion lleva la etiqueta real",
        not con_etiqueta and len(enviados) > 10,
        f"{len(enviados)} peticiones",
    )
    contexto.close()


def prueba_movimiento(c: Comprobacion, navegador, base: str) -> None:
    contexto = navegador.new_context(
        viewport={"width": 1280, "height": 900}, reduced_motion="reduce"
    )
    pagina = contexto.new_page()
    pagina.goto(base)
    esperar_listo(pagina)
    pagina.select_option("#velocidad", "2000")
    with pagina.expect_response("**/simulacion/transacciones**"):
        pagina.click("#boton-paso")
    pagina.wait_for_function("() => window.__simulacion.estado.registros.length === 1")
    animacion = pagina.evaluate(
        "() => getComputedStyle(document.getElementById('caso-sello')).animationName"
    )
    c.anotar("con «reducir movimiento» no hay animaciones", animacion == "none", animacion)
    contexto.close()


def prueba_errores(c: Comprobacion, navegador, base: str) -> None:
    for tema in TEMAS:
        contexto = navegador.new_context(viewport={"width": 1280, "height": 900}, color_scheme=tema)
        pagina = contexto.new_page()
        pagina.route("**/simulacion/lote", lambda ruta: ruta.abort())
        pagina.goto(base)
        esperar_listo(pagina)
        texto = pagina.inner_text("#estado")
        c.anotar(f"estado de error si la API no responde ({tema})", "./fraude" in texto, texto)
        c.capturar(pagina, f"estado-error-api_{NOMBRE_TEMA[tema]}", completa=False)
        contexto.close()

    contexto = navegador.new_context(viewport={"width": 1280, "height": 900})
    pagina = contexto.new_page()
    cuerpo = {
        "id_transaccion": None,
        "error": {
            "tipo": "n8n_no_disponible",
            "mensaje": "n8n no respondio. Comprueba los servicios con ./fraude estado.",
            "detalles": [],
        },
    }
    pagina.route(
        "**/simulacion/transacciones**",
        lambda ruta: ruta.fulfill(status=502, json=cuerpo),
    )
    pagina.goto(base)
    esperar_listo(pagina)
    pagina.click("#boton-iniciar")
    pagina.wait_for_function("() => document.getElementById('estado').dataset.tipo === 'error'")
    texto = pagina.inner_text("#estado")
    pausada = not pagina.evaluate("() => window.__simulacion.estado.corriendo")
    c.anotar("si n8n no responde, la simulacion se pausa y dice que hacer", pausada, texto)
    c.capturar(pagina, "estado-error-n8n_claro", completa=False)
    contexto.close()


def capturas_por_ancho(c: Comprobacion, navegador, base: str) -> None:
    for tema in TEMAS:
        for ancho in ANCHOS:
            contexto = navegador.new_context(
                viewport={"width": ancho, "height": 1000},
                color_scheme=tema,
                reduced_motion="reduce",
            )
            pagina = contexto.new_page()
            pagina.goto(base)
            esperar_listo(pagina)
            nombre = f"{ancho}_{NOMBRE_TEMA[tema]}"
            if ancho == 1280:
                c.capturar(pagina, f"vacio_{nombre}", completa=False)
            correr_lote(pagina)
            pagina.wait_for_timeout(800)
            desborde = pagina.evaluate(
                "() => document.scrollingElement.scrollWidth - window.innerWidth"
            )
            c.anotar(f"sin desbordamiento horizontal ({nombre})", desborde <= 0, f"{desborde}px")
            texto = pagina.inner_text("body").lower()
            prohibidas = [f for f in FRASES_PROHIBIDAS if re.search(f, texto)]
            c.anotar(
                f"lenguaje: el sistema solo señala ({nombre})", not prohibidas, str(prohibidas)
            )
            c.capturar(pagina, f"pagina_{nombre}")
            c.capturar(pagina, f"pantalla_{nombre}", completa=False)
            if ancho == 1280:
                c.accesibilidad(pagina, f"lote completo, tema {NOMBRE_TEMA[tema]}")
            if ancho == 1920:
                pagina.click("#boton-presentacion")
                pagina.wait_for_timeout(300)
                c.capturar(pagina, f"presentacion_{NOMBRE_TEMA[tema]}", completa=False)
                c.capturar(pagina, f"presentacion-completa_{NOMBRE_TEMA[tema]}")
                c.accesibilidad(pagina, f"modo presentacion, tema {NOMBRE_TEMA[tema]}")
                pagina.click("#boton-presentacion")
            contexto.close()


def main() -> int:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("base")
    argumentos.add_argument("--axe", required=True, help="ruta de axe.min.js")
    argumentos.add_argument("--salida", default="resultados/capturas_ci")
    argumentos.add_argument("--chrome", default=None, help="Chrome instalado (opcional)")
    a = argumentos.parse_args()
    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    c = Comprobacion(salida, Path(a.axe).read_text(encoding="utf-8"))
    inicio = time.monotonic()
    with sync_playwright() as p:
        opciones = {"executable_path": a.chrome} if a.chrome else {}
        navegador = p.chromium.launch(**opciones)
        try:
            prueba_teclado(c, navegador, a.base)
            prueba_movimiento(c, navegador, a.base)
            prueba_errores(c, navegador, a.base)
            capturas_por_ancho(c, navegador, a.base)
        except Exception as error:  # noqa: BLE001 - se anota y se guardan las capturas hechas
            c.anotar(
                "la comprobacion termino sin excepciones", False, f"{type(error).__name__}: {error}"
            )
        finally:
            navegador.close()
    c.informe["duracion_s"] = round(time.monotonic() - inicio, 1)
    c.informe["fallos"] = c.fallos
    (salida / "informe.json").write_text(
        json.dumps(c.informe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{len(c.informe['capturas'])} capturas en {salida}; {len(c.fallos)} fallos")
    return 1 if c.fallos else 0


if __name__ == "__main__":
    sys.exit(main())
