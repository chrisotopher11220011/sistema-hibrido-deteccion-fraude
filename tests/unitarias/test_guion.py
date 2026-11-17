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
if [ "$1" = "compose" ]; then
    echo "perfiles=${COMPOSE_PROFILES:-} archivos=${COMPOSE_FILE:-} llm=${FRAUDE_LLM:-} $*" \
        >> "$FALSO_REGISTRO.entorno"
fi
if [ "$1" = "info" ]; then
    if [ -n "${FALSO_DOCKER_PIDE_SUDO:-}" ] && [ -z "${FALSO_ES_SUDO:-}" ]; then exit 1; fi
    if [ -n "${FALSO_RUNTIME_NVIDIA:-}" ]; then echo '{"nvidia":{},"runc":{}}'; exit 0; fi
    echo "informacion"; exit 0
fi
if [ "$1" = "version" ]; then echo "29.0.0"; exit 0; fi
if [ "$1" = "compose" ]; then
    case " $* " in
        *" version "*) echo "5.0.0"; exit 0 ;;
        *" up "*)
            [ -n "${FALSO_UP_FALLA:-}" ] && exit 1
            [ -n "${FALSO_UP_FALLA_CON_GRAFICA:-}" ] && [ -n "${COMPOSE_FILE:-}" ] && exit 1
            [ -n "${FALSO_UP_FALLA_CON_LLM:-}" ] && [ -n "${COMPOSE_PROFILES:-}" ] && exit 1
            exit 0 ;;
        *" logs "*) echo "registro de ${!#} TELEGRAM_TOKEN=abc"; exit 0 ;;
        *" tareas todo"*)
            stat -c %u "$FALSO_RAIZ/resultados/en_curso" > "$FALSO_RAIZ/dueno_al_ejecutar.txt"
            exit 0 ;;
        *" tareas evidencia"*)
            [ -n "${FALSO_EVIDENCIA_FALLA:-}" ] && exit 1
            carpeta="$FALSO_RAIZ/resultados/20260101T000000Z_falso"
            [ -d "$carpeta" ] && carpeta="$FALSO_RAIZ/resultados/20260101T$(date +%H%M%S%N)Z_falso"
            mkdir -p "$carpeta"
            echo "uid=${FRAUDE_UID:-} gid=${FRAUDE_GID:-}" \
                > "$FALSO_RAIZ/resultados/entorno_visto.txt"
            : > "$carpeta.zip"
            exit 0 ;;
    esac
fi
exit 0
"""

SS_FALSO = r"""#!/bin/bash
[ -n "${FALSO_PUERTO_OCUPADO:-}" ] && echo "LISTEN 0 4096 127.0.0.1:8000 0.0.0.0:*"
exit 0
"""

OMARCHY_FALSO = "#!/bin/bash\nprintf '\\033[32m4.0.3\\033[0m\\n'\n"

SUDO_FALSO = r"""#!/bin/bash
echo "sudo $*" >> "$FALSO_REGISTRO"
[ "$1" = "-v" ] && exit 0
[ "$1" = "-n" ] && shift
FALSO_ES_SUDO=1 exec "$@"
"""

NVIDIA_SMI_FALSO = r"""#!/bin/bash
[ -z "${FALSO_NVIDIA:-}" ] && exit 9
if [ "$1" = "-L" ]; then echo "GPU 0: NVIDIA GeForce RTX 5060 Laptop GPU"; exit 0; fi
if [ "$1" = "--query-gpu=memory.used" ]; then echo "3312"; exit 0; fi
echo "NVIDIA GeForce RTX 5060 Laptop GPU, 8151 MiB, 580.95"
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
            ("ss", SS_FALSO),
            ("omarchy-version", OMARCHY_FALSO),
            ("nvidia-smi", NVIDIA_SMI_FALSO),
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

    def entorno_compose(self) -> list[str]:
        ruta = Path(f"{self.registro}.entorno")
        return ruta.read_text().splitlines() if ruta.exists() else []

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


@solo_root
def test_lanzado_con_sudo_las_carpetas_ya_son_de_la_persona_al_llamar_a_los_contenedores(guion):
    guion.ejecutar("todo", SUDO_UID="1234", SUDO_GID="1234")

    assert (guion.proyecto / "dueno_al_ejecutar.txt").read_text().strip() == "1234"


def test_si_la_evidencia_falla_no_anuncia_una_carpeta_anterior(guion):
    guion.ejecutar("todo")

    resultado = guion.ejecutar("evidencia", FALSO_EVIDENCIA_FALLA="1")

    assert resultado.returncode != 0
    assert "Evidencia lista" not in resultado.stdout
    assert "resultados/en_curso" in resultado.stderr


def test_anfitrion_conserva_los_puertos_ocupados_antes_de_arrancar(guion):
    guion.ejecutar("todo", FALSO_PUERTO_OCUPADO="1")
    guion.ejecutar("evidencia")

    puertos = json.loads((guion.en_curso() / "anfitrion.json").read_text())["puertos"]
    assert "8000" in puertos["en_escucha_antes_de_arrancar"]
    assert puertos["en_escucha_ahora"] == ""


def test_anfitrion_sigue_siendo_json_si_una_orden_devuelve_colores(guion):
    guion.ejecutar("evidencia")

    anfitrion = json.loads((guion.en_curso() / "anfitrion.json").read_text())
    assert anfitrion["omarchy"] == {"version": "4.0.3", "obtenida_de": "omarchy-version"}


def test_todo_con_muestra_la_pasa_a_tareas(guion):
    resultado = guion.ejecutar("todo", "--muestra")

    assert resultado.returncode == 0, resultado.stderr
    assert any("tareas todo --sin-evidencia --muestra" in linea for linea in guion.llamadas())
    assert "muestra" in resultado.stdout


def test_todo_sin_muestra_no_la_pasa(guion):
    guion.ejecutar("todo")

    assert not any("--muestra" in linea for linea in guion.llamadas())


def test_preparar_suelto_con_muestra(guion):
    guion.ejecutar("preparar", "--muestra")

    assert any("tareas preparar --muestra" in linea for linea in guion.llamadas())


def test_una_sesion_nueva_no_arrastra_datos_de_la_anterior(guion):
    en_curso = guion.en_curso()
    (en_curso / "eda").mkdir(parents=True)
    (en_curso / "eda" / "vieja.png").write_bytes(b"x")
    (en_curso / "datos.json").write_text("{}")
    for nombre in ("modelo.json", "metricas.json", "comparativa.md"):
        (en_curso / nombre).write_text("{}")
    for nombre in ("figuras", "analisis_errores"):
        (en_curso / nombre).mkdir()
        (en_curso / nombre / "viejo").write_text("x")

    guion.ejecutar("todo")

    assert not (en_curso / "datos.json").exists()
    assert not (en_curso / "eda").exists()
    for nombre in ("modelo.json", "metricas.json", "comparativa.md", "figuras", "analisis_errores"):
        assert not (en_curso / nombre).exists(), nombre


def test_entrenar_y_evaluar_sueltos_con_muestra(guion):
    guion.ejecutar("entrenar", "--muestra")
    guion.ejecutar("evaluar", "--muestra")

    llamadas = guion.llamadas()
    assert any("tareas entrenar --muestra" in linea for linea in llamadas)
    assert any("tareas evaluar --muestra" in linea for linea in llamadas)


def test_la_ayuda_explica_la_muestra(guion):
    assert "--muestra" in guion.ejecutar("ayuda").stdout


# --- LLM local (fase 7, ADR 0016) -----------------------------------------------------------


def _linea(lineas: list[str], fragmento: str) -> str:
    coincidencias = [linea for linea in lineas if fragmento in linea]
    assert coincidencias, f"Ninguna llamada con «{fragmento}»: {lineas}"
    return coincidencias[-1]


def test_todo_sin_llm_no_activa_el_perfil(guion):
    resultado = guion.ejecutar("todo")

    assert resultado.returncode == 0, resultado.stderr
    arranque = _linea(guion.entorno_compose(), " up ")
    assert "perfiles= " in arranque and "archivos= " in arranque
    assert "llm=desactivado" in arranque
    assert "tareas todo --sin-evidencia" in _linea(guion.llamadas(), "tareas todo")
    assert "--llm" not in _linea(guion.llamadas(), "tareas todo")
    anfitrion = json.loads((guion.en_curso() / "anfitrion.json").read_text())
    assert anfitrion["llm"]["solicitado"] is False


def test_todo_con_llm_y_grafica_preparada_usa_la_grafica(guion):
    resultado = guion.ejecutar("todo", "--llm", FALSO_RUNTIME_NVIDIA="1", FALSO_NVIDIA="1")

    assert resultado.returncode == 0, resultado.stderr
    arranque = _linea(guion.entorno_compose(), " up ")
    assert "perfiles=llm" in arranque
    assert "archivos=compose.yaml:compose.gpu.yaml" in arranque
    assert "llm=activo" in arranque
    assert "tareas todo --sin-evidencia --llm" in _linea(guion.llamadas(), "tareas todo")
    assert "grafica" in resultado.stdout and "3,3 GB" in resultado.stdout
    anfitrion = json.loads((guion.en_curso() / "anfitrion.json").read_text())
    assert anfitrion["llm"] == {
        "solicitado": True,
        "ejecucion": "grafica",
        "nvidia_smi": True,
        "runtime_nvidia": True,
        "grafica_memoria_usada_mib": 3312,
    }


def test_todo_con_llm_sin_preparar_la_grafica_usa_el_procesador_y_lo_explica(guion):
    resultado = guion.ejecutar("todo", "--llm", FALSO_NVIDIA="1")

    assert resultado.returncode == 0, resultado.stderr
    arranque = _linea(guion.entorno_compose(), " up ")
    assert "perfiles=llm" in arranque and "archivos= " in arranque
    assert "procesador" in resultado.stdout
    assert "EJECUTAR.md" in resultado.stdout
    assert "nvidia-container-toolkit" in resultado.stdout
    anfitrion = json.loads((guion.en_curso() / "anfitrion.json").read_text())
    assert anfitrion["llm"]["ejecucion"] == "procesador"
    assert anfitrion["llm"]["runtime_nvidia"] is False


def test_si_la_grafica_no_arranca_reintenta_con_el_procesador(guion):
    resultado = guion.ejecutar(
        "todo", "--llm", FALSO_RUNTIME_NVIDIA="1", FALSO_NVIDIA="1", FALSO_UP_FALLA_CON_GRAFICA="1"
    )

    assert resultado.returncode == 0, resultado.stderr
    arranques = [linea for linea in guion.entorno_compose() if " up " in linea]
    assert len(arranques) == 2
    assert "compose.gpu.yaml" in arranques[0] and "archivos= " in arranques[1]
    assert "procesador" in resultado.stderr + resultado.stdout
    anfitrion = json.loads((guion.en_curso() / "anfitrion.json").read_text())
    assert anfitrion["llm"]["ejecucion"] == "procesador"


def test_los_pasos_sueltos_tras_todo_con_llm_no_lo_apagan(guion):
    guion.ejecutar("todo", "--llm", FALSO_RUNTIME_NVIDIA="1", FALSO_NVIDIA="1")
    guion.ejecutar("demostrar")

    # Mismo entorno de Compose: la API no se recrea sin LLM al lanzar un paso suelto.
    paso = _linea(guion.entorno_compose(), "tareas demostrar")
    assert "perfiles=llm" in paso and "llm=activo" in paso and "compose.gpu.yaml" in paso


def test_todo_sin_llm_tras_uno_con_llm_lo_desactiva(guion):
    guion.ejecutar("todo", "--llm")
    guion.ejecutar("todo")

    arranque = _linea(guion.entorno_compose(), " up ")
    assert "llm=desactivado" in arranque and "perfiles= " in arranque


def test_evidencia_guarda_el_registro_del_llm(guion):
    guion.ejecutar("todo", "--llm")

    assert (guion.en_curso() / "registros" / "llm.log").is_file()


def test_apagar_detiene_tambien_el_llm(guion):
    guion.ejecutar("todo", "--llm")
    resultado = guion.ejecutar("apagar")

    assert resultado.returncode == 0
    assert "perfiles=llm" in _linea(guion.entorno_compose(), "compose down")


def test_la_ayuda_explica_el_llm(guion):
    salida = guion.ejecutar("ayuda").stdout

    assert "--llm" in salida and "plantilla" in salida


def test_opcion_desconocida_sigue_fallando(guion):
    resultado = guion.ejecutar("todo", "--gpu")

    assert resultado.returncode == 2
    assert "No conozco la opcion" in resultado.stderr


def test_si_el_llm_no_arranca_sigue_sin_el(guion):
    resultado = guion.ejecutar("todo", "--llm", FALSO_UP_FALLA_CON_LLM="1")

    assert resultado.returncode == 0, resultado.stderr
    arranques = [linea for linea in guion.entorno_compose() if " up " in linea]
    assert "perfiles=llm" in arranques[0]
    assert "perfiles= " in arranques[-1] and "llm=desactivado" in arranques[-1]
    assert "plantilla" in resultado.stderr + resultado.stdout
    tareas = _linea(guion.llamadas(), "tareas todo")
    assert "--llm" not in tareas
    anfitrion = json.loads((guion.en_curso() / "anfitrion.json").read_text())
    assert anfitrion["llm"]["solicitado"] is False
    llm = json.loads((guion.en_curso() / "llm.json").read_text())
    assert llm["estado"] == "fallo" and "sin LLM" in llm["error"]


def test_todo_sin_llm_detiene_el_llm_de_antes(guion):
    guion.ejecutar("todo", "--llm")
    guion.ejecutar("todo")

    retirada = _linea(guion.entorno_compose(), "rm -s -f llm")
    assert "perfiles=llm" in retirada
