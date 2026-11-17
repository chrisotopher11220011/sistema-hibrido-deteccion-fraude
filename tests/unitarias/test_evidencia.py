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
