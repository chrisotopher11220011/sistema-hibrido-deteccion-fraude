import json
import zipfile
from datetime import UTC, datetime

from fraude import evidencia

AHORA = datetime(2026, 11, 16, 20, 30, 0, tzinfo=UTC)
SERVICIOS_BIEN = [
    {"servicio": "api", "url": "http://api:8000/salud", "ok": True, "detalle": "200"},
    {"servicio": "n8n", "url": "http://n8n:5678/webhook/ping", "ok": True, "detalle": "200"},
]
ESPERADOS = {
    "RESUMEN.md",
    "anfitrion.json",
    "entorno.json",
    "version.json",
    "errores.json",
    "OBSERVACIONES.md",
}


def reunir(raiz, servicios=SERVICIOS_BIEN, pasos=(), ahora=AHORA):
    return evidencia.reunir_evidencia(
        raiz,
        commit="abc1234",
        etiqueta="v0.1.0",
        servicios=list(servicios),
        pasos=list(pasos),
        ahora=ahora,
    )


def test_crea_carpeta_con_fecha_commit_y_archivos(tmp_path):
    carpeta = reunir(tmp_path)

    assert carpeta == tmp_path / "resultados" / "20261116T203000Z_abc1234"
    nombres = {p.name for p in carpeta.iterdir()}
    assert nombres >= ESPERADOS
    assert (carpeta / "registros").is_dir()
    assert (carpeta / "capturas").is_dir()


def test_crea_zip_con_lo_mismo(tmp_path):
    carpeta = reunir(tmp_path)

    archivo = carpeta.with_suffix(".zip")
    assert archivo.is_file()
    with zipfile.ZipFile(archivo) as z:
        nombres = set(z.namelist())
    assert {f"{carpeta.name}/{n}" for n in ESPERADOS} <= nombres


def test_servicio_caido_queda_en_errores_y_en_resumen(tmp_path):
    servicios = [
        SERVICIOS_BIEN[0],
        {
            "servicio": "n8n",
            "url": "http://n8n:5678/webhook/ping",
            "ok": False,
            "detalle": "Connection refused",
        },
    ]

    carpeta = reunir(tmp_path, servicios=servicios)

    errores = json.loads((carpeta / "errores.json").read_text())
    assert errores["hay_errores"] is True
    assert errores["errores"][0]["origen"] == "n8n"
    assert "Connection refused" in errores["errores"][0]["mensaje"]
    resumen = (carpeta / "RESUMEN.md").read_text()
    assert "n8n" in resumen and "FALLO" in resumen


def test_paso_fallido_queda_en_errores(tmp_path):
    pasos = [{"paso": "preparar", "estado": "fallo", "detalle": "sin red"}]

    carpeta = reunir(tmp_path, pasos=pasos)

    errores = json.loads((carpeta / "errores.json").read_text())
    assert {"origen": "preparar", "mensaje": "sin red"} in errores["errores"]


def test_sin_errores_lo_dice(tmp_path):
    carpeta = reunir(tmp_path)

    errores = json.loads((carpeta / "errores.json").read_text())
    assert errores == {"hay_errores": False, "errores": []}


def test_sin_anfitrion_anota_la_ausencia(tmp_path):
    carpeta = reunir(tmp_path)

    anfitrion = json.loads((carpeta / "anfitrion.json").read_text())
    assert anfitrion["disponible"] is False
    assert "./fraude" in anfitrion["motivo"]


def test_copia_lo_que_dejo_el_guion(tmp_path):
    en_curso = tmp_path / "resultados" / "en_curso"
    (en_curso / "registros").mkdir(parents=True)
    (en_curso / "capturas").mkdir()
    (en_curso / "anfitrion.json").write_text('{"uso_sudo": true}')
    (en_curso / "registros" / "n8n.log").write_text("n8n listo\n")
    (en_curso / "capturas" / "screenshot-1.png").write_bytes(b"png")
    (en_curso / "OBSERVACIONES.md").write_text("Vi la pagina.\n")

    carpeta = reunir(tmp_path)

    assert json.loads((carpeta / "anfitrion.json").read_text()) == {"uso_sudo": True}
    assert (carpeta / "registros" / "n8n.log").read_text() == "n8n listo\n"
    assert (carpeta / "capturas" / "screenshot-1.png").read_bytes() == b"png"
    assert (carpeta / "OBSERVACIONES.md").read_text() == "Vi la pagina.\n"


def test_dos_veces_en_el_mismo_segundo_no_se_pisan(tmp_path):
    primera = reunir(tmp_path)
    segunda = reunir(tmp_path)

    assert primera != segunda
    assert primera.is_dir() and segunda.is_dir()
    assert segunda.with_suffix(".zip").is_file()


def test_registros_salen_sin_secretos(tmp_path):
    registros = tmp_path / "resultados" / "en_curso" / "registros"
    registros.mkdir(parents=True)
    (registros / "n8n.log").write_text("TELEGRAM_TOKEN=12345:ABCdef\nlisto\n")

    carpeta = reunir(tmp_path)

    texto = (carpeta / "registros" / "n8n.log").read_text()
    assert "12345:ABCdef" not in texto
    assert "TELEGRAM_TOKEN=***" in texto
    assert "listo" in texto


def test_observaciones_trae_el_cuestionario_sus(tmp_path):
    carpeta = reunir(tmp_path)

    texto = (carpeta / "OBSERVACIONES.md").read_text()
    assert texto.count("/5") >= 10
    assert "SUS" in texto
    assert (tmp_path / "resultados" / "en_curso" / "OBSERVACIONES.md").is_file()


def test_version_y_entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("N8N_VERSION_FIJADA", "2.47.7")

    carpeta = reunir(tmp_path)

    version = json.loads((carpeta / "version.json").read_text())
    assert version["commit"] == "abc1234"
    assert version["etiqueta"] == "v0.1.0"
    assert version["n8n"] == "2.47.7"
    assert "fastapi" in version["dependencias"]
    for nombre in ("pandas", "numpy", "scikit-learn", "matplotlib"):
        assert version["dependencias"][nombre] != "no instalada", nombre
    entorno = json.loads((carpeta / "entorno.json").read_text())
    assert entorno["arquitectura"]
    assert entorno["fecha"] == "2026-11-16T20:30:00Z"


def test_comprobar_servicios_usa_salud_y_ping():
    vistas = []

    def obtener(url):
        vistas.append(url)
        if "n8n" in url:
            raise OSError("Connection refused")
        return 200, '{"estado": "ok"}'

    resultado = evidencia.comprobar_servicios("http://api:8000", "http://n8n:5678", obtener)

    assert vistas == ["http://api:8000/salud", "http://n8n:5678/webhook/ping"]
    assert resultado[0]["ok"] is True
    assert resultado[1]["ok"] is False
    assert "Connection refused" in resultado[1]["detalle"]


def test_comprobar_servicios_no_acepta_codigos_de_error():
    resultado = evidencia.comprobar_servicios("http://a", "http://n", lambda url: (404, "no"))

    assert [r["ok"] for r in resultado] == [False, False]
    assert "404" in resultado[1]["detalle"]


def _dejar_preparar(raiz, fuente="muestra", reportable=False):
    en_curso = raiz / "resultados" / "en_curso"
    (en_curso / "eda").mkdir(parents=True)
    informe = {"estado": "ok", "fuente": fuente, "reportable": reportable, "filas": 10}
    (en_curso / "datos.json").write_text(json.dumps(informe))
    (en_curso / "eda" / "resumen.json").write_text("{}")
    (en_curso / "eda" / "montos_por_clase.png").write_bytes(b"\x89PNG")


def test_copia_datos_y_analisis_exploratorio(tmp_path):
    _dejar_preparar(tmp_path)
    carpeta = reunir(tmp_path)
    assert json.loads((carpeta / "datos.json").read_text())["fuente"] == "muestra"
    assert (carpeta / "eda" / "resumen.json").is_file()
    assert (carpeta / "eda" / "montos_por_clase.png").read_bytes() == b"\x89PNG"
    with zipfile.ZipFile(carpeta.with_suffix(".zip")) as z:
        assert f"{carpeta.name}/eda/resumen.json" in z.namelist()


def test_resumen_avisa_cuando_los_datos_son_la_muestra(tmp_path):
    _dejar_preparar(tmp_path)
    resumen = (reunir(tmp_path) / "RESUMEN.md").read_text()
    assert "muestra" in resumen.lower() and "no reportable" in resumen.lower()


def test_resumen_con_datos_reales_no_trae_el_aviso_de_muestra(tmp_path):
    _dejar_preparar(tmp_path, fuente="openml", reportable=True)
    resumen = (reunir(tmp_path) / "RESUMEN.md").read_text()
    assert "no reportable" not in resumen.lower()
    assert "openml" in resumen


def test_sin_preparar_lo_anota(tmp_path):
    resumen = (reunir(tmp_path) / "RESUMEN.md").read_text()
    assert "datos.json" in resumen


def _dejar_modelo_y_evaluacion(raiz, reportable=False):
    en_curso = raiz / "resultados" / "en_curso"
    (en_curso / "figuras").mkdir(parents=True, exist_ok=True)
    (en_curso / "analisis_errores").mkdir(parents=True, exist_ok=True)
    modelo = {"estado": "ok", "version": "2026-11-17T00:00Z-abc123", "reportable": reportable}
    (en_curso / "modelo.json").write_text(json.dumps(modelo))
    metricas = {"estado": "ok", "reportable": reportable, "version_modelo": modelo["version"]}
    (en_curso / "metricas.json").write_text(json.dumps(metricas))
    (en_curso / "comparativa.md").write_text("# Comparativa\n")
    (en_curso / "figuras" / "curva_pr_prueba.png").write_bytes(b"\x89PNG")
    (en_curso / "analisis_errores" / "falsas_alarmas.csv").write_text("fila\n1\n")
    (en_curso / "analisis_errores" / "resumen.json").write_text("{}")


def test_copia_modelo_metricas_figuras_y_analisis_de_errores(tmp_path):
    _dejar_modelo_y_evaluacion(tmp_path)
    carpeta = reunir(tmp_path)
    for nombre in (
        "modelo.json",
        "metricas.json",
        "comparativa.md",
        "figuras/curva_pr_prueba.png",
        "analisis_errores/falsas_alarmas.csv",
        "analisis_errores/resumen.json",
    ):
        assert (carpeta / nombre).is_file(), nombre
    with zipfile.ZipFile(carpeta.with_suffix(".zip")) as z:
        assert f"{carpeta.name}/metricas.json" in z.namelist()
    resumen = (carpeta / "RESUMEN.md").read_text()
    assert "2026-11-17T00:00Z-abc123" in resumen
    assert "no reportable" in resumen.lower()


def test_sin_entrenar_ni_evaluar_lo_anota(tmp_path):
    resumen = (reunir(tmp_path) / "RESUMEN.md").read_text()
    assert "modelo.json" in resumen and "metricas.json" in resumen


def test_evaluacion_fallida_queda_en_el_resumen(tmp_path):
    en_curso = tmp_path / "resultados" / "en_curso"
    en_curso.mkdir(parents=True)
    fallo = {"estado": "fallo", "error": "Repite el paso entrenar."}
    (en_curso / "metricas.json").write_text(json.dumps(fallo))
    resumen = (reunir(tmp_path) / "RESUMEN.md").read_text()
    assert "Repite el paso entrenar." in resumen
