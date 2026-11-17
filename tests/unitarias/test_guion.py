"""Pruebas del guion `./fraude` con `docker` y `sudo` simulados (N1)."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
ES_ROOT = os.getuid() == 0
sin_root = pytest.mark.skipif(ES_ROOT, reason="Describe el uso normal, sin ser administrador")
solo_root = pytest.mark.skipif(not ES_ROOT, reason="Describe el caso `sudo ./fraude`")

DOCKER_FALSO = r"""#!/bin/bash
echo "docker[sudo=${FALSO_ES_SUDO:-0}] $*" >> "$FALSO_REGISTRO"
if [ "$1" = "info" ]; then
    if [ -n "${FALSO_DOCKER_PIDE_SUDO:-}" ] && [ -z "${FALSO_ES_SUDO:-}" ]; then exit 1; fi
    echo "informacion"; exit 0
fi
if [ "$1" = "version" ]; then echo "29.0.0"; exit 0; fi
if [ "$1" = "compose" ]; then
    case " $* " in
        *" version "*) echo "5.0.0"; exit 0 ;;
        *" up "*) [ -n "${FALSO_UP_FALLA:-}" ] && exit 1; exit 0 ;;
        *" logs "*) echo "registro de ${!#} TELEGRAM_TOKEN=abc"; exit 0 ;;
        *" tareas evidencia"*)
            mkdir -p "$FALSO_RAIZ/resultados/20260101T000000Z_falso"
            echo "uid=${FRAUDE_UID:-} gid=${FRAUDE_GID:-}" \
                > "$FALSO_RAIZ/resultados/entorno_visto.txt"
            exit 0 ;;
    esac
fi
exit 0
"""

SUDO_FALSO = r"""#!/bin/bash
echo "sudo $*" >> "$FALSO_REGISTRO"
[ "$1" = "-v" ] && exit 0
[ "$1" = "-n" ] && shift
FALSO_ES_SUDO=1 exec "$@"
"""

ABRIR_FALSO = r"""#!/bin/bash
echo "xdg-open $*" >> "$FALSO_REGISTRO"
"""


class Guion:
    def __init__(self, raiz: Path):
        self.raiz = raiz
        self.registro = raiz / "llamadas.log"
        self.casa = raiz / "casa"
        self.capturas = self.casa / "Pictures" / "Screenshots"
        self.capturas.mkdir(parents=True)
        simulados = raiz / "simulados"
        simulados.mkdir()
        for nombre, texto in (
            ("docker", DOCKER_FALSO),
            ("sudo", SUDO_FALSO),
            ("xdg-open", ABRIR_FALSO),
        ):
            (simulados / nombre).write_text(texto)
            (simulados / nombre).chmod(0o755)
        self.proyecto = raiz / "proyecto"
        self.proyecto.mkdir()
        shutil.copy(RAIZ / "fraude", self.proyecto / "fraude")
        self.entorno = {
            "PATH": f"{simulados}:/usr/bin:/bin",
            "HOME": str(self.casa),
            "FALSO_REGISTRO": str(self.registro),
            "FALSO_RAIZ": str(self.proyecto),
        }

    def ejecutar(self, *argumentos, **extra):
        return subprocess.run(
            ["bash", str(self.proyecto / "fraude"), *argumentos],
            env={**self.entorno, **extra},
            capture_output=True,
            text=True,
            timeout=60,
        )

    def llamadas(self) -> list[str]:
        return self.registro.read_text().splitlines() if self.registro.exists() else []

    def en_curso(self) -> Path:
        return self.proyecto / "resultados" / "en_curso"


@pytest.fixture
def guion(tmp_path):
    return Guion(tmp_path)


def test_sin_argumentos_muestra_la_ayuda_en_espanol(guion):
    resultado = guion.ejecutar()

    assert resultado.returncode == 0
    for palabra in ("todo", "evidencia", "abrir", "estado", "apagar"):
        assert palabra in resultado.stdout
    assert guion.llamadas() == []


def test_comando_desconocido_lo_dice_y_falla(guion):
    resultado = guion.ejecutar("bailar")

    assert resultado.returncode == 2
    assert "No conozco el comando" in resultado.stderr


@sin_root
def test_sin_sudo_cuando_docker_responde(guion):
    resultado = guion.ejecutar("todo")

    assert resultado.returncode == 0, resultado.stderr
    assert not any(linea.startswith("sudo") for linea in guion.llamadas())
    anfitrion = json.loads((guion.en_curso() / "anfitrion.json").read_text())
    assert anfitrion["uso_sudo"] is False
    assert anfitrion["modo_docker"] == "directo"


@sin_root
def test_usa_sudo_cuando_docker_lo_pide_y_lo_avisa(guion):
    resultado = guion.ejecutar("todo", FALSO_DOCKER_PIDE_SUDO="1")

    assert resultado.returncode == 0, resultado.stderr
    assert "sudo" in resultado.stdout
    llamadas = guion.llamadas()
    assert any("docker[sudo=1] compose" in linea and " up " in f"{linea} " for linea in llamadas)
    assert not any("docker[sudo=0] compose" in linea for linea in llamadas)
    anfitrion = json.loads((guion.en_curso() / "anfitrion.json").read_text())
    assert anfitrion["uso_sudo"] is True
    assert anfitrion["modo_docker"] == "sudo"


@sin_root
def test_los_contenedores_reciben_el_usuario_real_tambien_con_sudo(guion):
    guion.ejecutar("todo", FALSO_DOCKER_PIDE_SUDO="1")

    visto = (guion.proyecto / "resultados" / "entorno_visto.txt").read_text().strip()
    assert visto == f"uid={os.getuid()} gid={os.getgid()}"


def test_todo_arranca_ejecuta_pasos_y_termina_con_evidencia(guion):
    resultado = guion.ejecutar("todo")

    texto = "\n".join(guion.llamadas())
    arranque = texto.index(" up ")
    pasos = texto.index("tareas todo --sin-evidencia")
    registros = texto.index(" logs ")
    evidencia = texto.index("tareas evidencia")
    assert arranque < pasos < registros < evidencia
    assert "--wait" in texto
    assert "20260101T000000Z_falso" in resultado.stdout
    assert "./fraude abrir" in resultado.stdout


def test_si_el_arranque_falla_guarda_registros_y_evidencia_y_devuelve_error(guion):
    resultado = guion.ejecutar("todo", FALSO_UP_FALLA="1")

    assert resultado.returncode != 0
    assert "no arrancaron" in resultado.stderr
    assert (guion.en_curso() / "registros" / "n8n.log").is_file()
    assert (guion.en_curso() / "registros" / "api.log").is_file()
    assert any("tareas evidencia" in linea for linea in guion.llamadas())


def test_anfitrion_es_json_valido_con_los_datos_del_sistema(guion):
    guion.ejecutar("evidencia")

    anfitrion = json.loads((guion.en_curso() / "anfitrion.json").read_text())
    for campo in ("fecha", "omarchy", "nucleo", "docker", "grafica", "uso_sudo", "usuario"):
        assert campo in anfitrion, campo
    assert anfitrion["fecha"].endswith("Z")
    assert anfitrion["docker"]["motor"] == "29.0.0"
    assert anfitrion["usuario"]["uid"] == int(os.environ.get("SUDO_UID", os.getuid()))


def test_evidencia_copia_solo_las_capturas_de_la_sesion(guion):
    vieja = guion.capturas / "screenshot-vieja.png"
    vieja.write_bytes(b"vieja")
    os.utime(vieja, (1_000_000_000, 1_000_000_000))
    guion.ejecutar("todo")
    (guion.capturas / "screenshot-nueva.png").write_bytes(b"nueva")

    resultado = guion.ejecutar("evidencia")

    assert resultado.returncode == 0, resultado.stderr
    copiadas = {p.name for p in (guion.en_curso() / "capturas").iterdir()}
    assert copiadas == {"screenshot-nueva.png"}


def test_evidencia_respeta_la_carpeta_de_capturas_configurada(guion, tmp_path):
    otra = tmp_path / "otras"
    otra.mkdir()
    guion.ejecutar("todo")
    (otra / "screenshot-x.png").write_bytes(b"x")

    guion.ejecutar("evidencia", OMASNAP_SCREENSHOT_DIR=str(otra))

    assert (guion.en_curso() / "capturas" / "screenshot-x.png").is_file()


def test_carpetas_de_trabajo_creadas_por_el_usuario(guion):
    guion.ejecutar("todo")

    for carpeta in ("datos", "resultados", "resultados/en_curso"):
        ruta = guion.proyecto / carpeta
        assert ruta.is_dir()
        assert ruta.stat().st_uid == os.getuid()
    assert (guion.en_curso() / "registros").is_dir()


def test_apagar_detiene_los_servicios(guion):
    resultado = guion.ejecutar("apagar")

    assert resultado.returncode == 0
    assert any(linea.endswith("compose down") for linea in guion.llamadas())


@sin_root
def test_abrir_abre_la_pagina_local(guion):
    resultado = guion.ejecutar("abrir")

    assert resultado.returncode == 0
    assert "xdg-open http://localhost:8000" in guion.llamadas()


@sin_root
def test_abrir_respeta_el_puerto_configurado(guion):
    guion.ejecutar("abrir", FRAUDE_PUERTO_API="8123")

    assert "xdg-open http://localhost:8123" in guion.llamadas()


def test_sin_docker_explica_que_falta(guion):
    resultado = guion.ejecutar("todo", PATH="/usr/bin:/bin")

    if shutil.which("docker", path="/usr/bin:/bin"):
        pytest.skip("Este equipo tiene Docker en /usr/bin")
    assert resultado.returncode != 0
    assert "No encuentro Docker" in resultado.stderr


def test_paso_suelto_se_delega_en_tareas(guion):
    guion.ejecutar("preparar")

    assert any("tareas preparar" in linea for linea in guion.llamadas())


@solo_root
def test_lanzado_con_sudo_devuelve_los_archivos_a_la_persona(guion):
    resultado = guion.ejecutar("todo", SUDO_UID="1234", SUDO_GID="1234")

    assert resultado.returncode == 0, resultado.stderr
    assert "administrador" in resultado.stderr
    visto = (guion.proyecto / "resultados" / "entorno_visto.txt").read_text().strip()
    assert visto == "uid=1234 gid=1234"
    for ruta in (guion.proyecto / "resultados").rglob("*"):
        assert ruta.stat().st_uid == 1234, ruta
    assert (guion.proyecto / "datos").stat().st_uid == 1234
    anfitrion = json.loads((guion.en_curso() / "anfitrion.json").read_text())
    assert anfitrion["modo_docker"] == "root"
    assert anfitrion["usuario"] == {"uid": 1234, "gid": 1234}
