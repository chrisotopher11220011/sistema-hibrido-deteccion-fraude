import json
import shutil
from pathlib import Path

import pytest

from fraude import cli
from fraude.datos import ErrorDatos

RAIZ_REPO = Path(__file__).resolve().parents[2]


class PrepararFalso:
    def __init__(self, error=None):
        self.error = error
        self.llamadas = []

    def __call__(self, raiz, muestra=False):
        self.llamadas.append({"raiz": raiz, "muestra": muestra})
        if self.error:
            raise self.error
        return {
            "fuente": "muestra" if muestra else "openml",
            "filas": 10,
            "fraudes": 1,
            "particion": {"estado": "creada"},
        }


class PasoFalso:
    """Sustituye a `entrenar` o `evaluar`: registra las llamadas y puede fallar."""

    def __init__(self, respuesta, error=None):
        self.respuesta = respuesta
        self.error = error
        self.llamadas = []

    def __call__(self, raiz, muestra=False):
        self.llamadas.append({"raiz": raiz, "muestra": muestra})
        if self.error:
            raise self.error
        return self.respuesta


def entrenar_falso(error=None):
    return PasoFalso({"version": "2026-11-17T00:00Z-abc123", "reportable": False}, error)


def evaluar_falso(error=None):
    return PasoFalso({"duracion_s": 1.0, "reportable": False}, error)


def demostrar_falso(error=None):
    respuesta = {
        "reportable": False,
        "lote": {"total": 12},
        "paridad": {"total": 12, "coinciden": 12, "completa": True},
        "latencia_ms": {"mediana": 40.0, "p95": 90.0},
    }
    return PasoFalso(respuesta, error)


def llm_falso(error=None):
    respuesta = {
        "estado": "ok",
        "servidor": {"url": "http://llm:11434", "version": "0.40.16"},
        "modelo": {"nombre": "qwen3.5:4b-q4_K_M"},
        "ejecucion": "grafica",
    }
    return PasoFalso(respuesta, error)


@pytest.fixture
def raiz(tmp_path, monkeypatch):
    monkeypatch.setenv("FRAUDE_RAIZ", str(tmp_path))
    monkeypatch.setenv("FRAUDE_COMMIT", "abc1234")
    monkeypatch.setattr(cli, "preparar", PrepararFalso())
    monkeypatch.setattr(cli, "entrenar", entrenar_falso())
    monkeypatch.setattr(cli, "evaluar", evaluar_falso())
    monkeypatch.setattr(cli, "demostrar", demostrar_falso())
    monkeypatch.setattr(cli, "preparar_llm", llm_falso())
    return tmp_path


def servicios(n8n_ok=True):
    def comprobar(url_api, url_n8n):
        return [
            {"servicio": "api", "url": url_api, "ok": True, "detalle": "200"},
            {"servicio": "n8n", "url": url_n8n, "ok": n8n_ok, "detalle": "200" if n8n_ok else "x"},
        ]

    return comprobar


def carpetas(raiz):
    resultados = raiz / "resultados"
    return [p for p in resultados.iterdir() if p.is_dir() and p.name != "en_curso"]


def test_todo_con_servicios_bien_devuelve_cero_y_deja_evidencia(raiz, monkeypatch, capsys):
    monkeypatch.setattr(cli, "comprobar_servicios", servicios())

    assert cli.main(["todo"]) == 0
    assert len(carpetas(raiz)) == 1
    assert "abc1234" in carpetas(raiz)[0].name
    assert "Evidencia" in capsys.readouterr().out


def test_todo_con_n8n_caido_devuelve_uno_y_aun_asi_deja_evidencia(raiz, monkeypatch):
    monkeypatch.setattr(cli, "comprobar_servicios", servicios(n8n_ok=False))

    assert cli.main(["todo"]) == 1
    assert len(carpetas(raiz)) == 1


def test_todo_sin_evidencia_solo_deja_pasos(raiz, monkeypatch):
    monkeypatch.setattr(cli, "comprobar_servicios", servicios())

    assert cli.main(["todo", "--sin-evidencia"]) == 0
    pasos = json.loads((raiz / "resultados" / "en_curso" / "pasos.json").read_text())
    assert [p["paso"] for p in pasos] == ["preparar", "entrenar", "evaluar", "demostrar"]
    assert [p["estado"] for p in pasos] == ["ok", "ok", "ok", "ok"]
    assert carpetas(raiz) == []


def test_evidencia_lee_los_pasos_guardados(raiz, monkeypatch):
    monkeypatch.setattr(cli, "comprobar_servicios", servicios())
    cli.main(["todo", "--sin-evidencia"])

    assert cli.main(["evidencia"]) == 0
    resumen = (carpetas(raiz)[0] / "RESUMEN.md").read_text()
    assert "entrenar" in resumen and "paridad 12/12" in resumen


def test_demostrar_suelto_informa_paridad_y_latencia(raiz, capsys):
    assert cli.main(["demostrar", "--muestra"]) == 0
    assert cli.demostrar.llamadas == [{"raiz": raiz, "muestra": True}]
    salida = capsys.readouterr().out
    assert "paridad 12/12" in salida and "mediana 40.0 ms" in salida and "p95 90.0 ms" in salida


def test_demostrar_que_falla_devuelve_uno(raiz, monkeypatch, capsys):
    monkeypatch.setattr(cli, "demostrar", demostrar_falso(RuntimeError("paridad incompleta")))
    assert cli.main(["demostrar"]) == 1
    assert "paridad incompleta" in capsys.readouterr().out


def test_todo_sigue_y_reune_evidencia_aunque_demostrar_falle(raiz, monkeypatch):
    monkeypatch.setattr(cli, "comprobar_servicios", servicios())
    monkeypatch.setattr(cli, "demostrar", demostrar_falso(RuntimeError("n8n no responde")))
    assert cli.main(["todo"]) == 1
    assert len(carpetas(raiz)) == 1


def test_sin_comando_muestra_ayuda_y_devuelve_dos(raiz, capsys):
    assert cli.main([]) == 2
    assert "evidencia" in capsys.readouterr().out


def test_preparar_suelto_bien_devuelve_cero(raiz, capsys):
    assert cli.main(["preparar"]) == 0
    assert cli.preparar.llamadas == [{"raiz": raiz, "muestra": False}]
    assert "10 transacciones" in capsys.readouterr().out


def test_preparar_con_muestra(raiz):
    assert cli.main(["preparar", "--muestra"]) == 0
    assert cli.preparar.llamadas[0]["muestra"] is True


def test_preparar_suelto_que_falla_devuelve_uno_y_explica(raiz, monkeypatch, capsys):
    monkeypatch.setattr(cli, "preparar", PrepararFalso(ErrorDatos("sin red; alternativa manual")))
    assert cli.main(["preparar"]) == 1
    salida = capsys.readouterr().out
    assert "ERROR" in salida and "alternativa manual" in salida


def test_todo_sigue_hasta_la_evidencia_aunque_preparar_falle(raiz, monkeypatch):
    monkeypatch.setattr(cli, "comprobar_servicios", servicios())
    monkeypatch.setattr(cli, "preparar", PrepararFalso(RuntimeError("inesperado")))
    assert cli.main(["todo"]) == 1
    assert len(carpetas(raiz)) == 1
    errores = json.loads((carpetas(raiz)[0] / "errores.json").read_text())
    assert errores["errores"][0]["origen"] == "preparar"
    assert "inesperado" in errores["errores"][0]["mensaje"]


def test_todo_con_muestra_la_pasa_a_todos_los_pasos(raiz, monkeypatch):
    monkeypatch.setattr(cli, "comprobar_servicios", servicios())
    assert cli.main(["todo", "--muestra", "--sin-evidencia"]) == 0
    assert cli.preparar.llamadas[0]["muestra"] is True
    assert cli.entrenar.llamadas == [{"raiz": raiz, "muestra": True}]
    assert cli.evaluar.llamadas == [{"raiz": raiz, "muestra": True}]


@pytest.mark.parametrize("paso", ["entrenar", "evaluar"])
def test_entrenar_y_evaluar_sueltos(raiz, capsys, paso):
    assert cli.main([paso, "--muestra"]) == 0
    assert getattr(cli, paso).llamadas == [{"raiz": raiz, "muestra": True}]
    salida = capsys.readouterr().out
    assert f"[{paso}] Listo" in salida and "no reportable" in salida


def test_entrenar_que_falla_devuelve_uno_y_todo_sigue(raiz, monkeypatch, capsys):
    monkeypatch.setattr(cli, "comprobar_servicios", servicios())
    monkeypatch.setattr(cli, "entrenar", entrenar_falso(ErrorDatos("No hay datos preparados")))
    assert cli.main(["entrenar"]) == 1
    assert "No hay datos preparados" in capsys.readouterr().out
    assert cli.main(["todo"]) == 1
    errores = json.loads((carpetas(raiz)[0] / "errores.json").read_text())
    assert [e["origen"] for e in errores["errores"]] == ["entrenar"]
    assert len(cli.evaluar.llamadas) == 1  # evaluar se intenta igual y dice su motivo


def test_preparar_de_verdad_con_la_muestra(tmp_path, monkeypatch):
    """Sin simular nada: el camino que sigue la CI (N2) con `tareas preparar --muestra`."""
    monkeypatch.setenv("FRAUDE_RAIZ", str(tmp_path))
    shutil.copytree(RAIZ_REPO / "config", tmp_path / "config")
    assert cli.main(["preparar", "--muestra"]) == 0
    informe = json.loads((tmp_path / "resultados" / "en_curso" / "datos.json").read_text())
    assert informe["estado"] == "ok" and informe["fuente"] == "muestra"


def test_preparar_entrenar_y_evaluar_de_verdad_con_la_muestra(tmp_path, monkeypatch):
    """Sin simular nada: el camino de la CI (N2) con `tareas todo --muestra`, sin servicios.

    Sin n8n ni API, `demostrar` falla (y lo dice en flujo.json) pero los demas pasos terminan.
    """
    monkeypatch.setenv("FRAUDE_RAIZ", str(tmp_path))
    monkeypatch.setenv("FRAUDE_URL_N8N", "http://127.0.0.1:9")
    monkeypatch.setenv("FRAUDE_URL_API", "http://127.0.0.1:9")
    shutil.copytree(RAIZ_REPO / "config", tmp_path / "config")
    ruta = tmp_path / "config" / "modelo.yaml"
    ruta.write_text(ruta.read_text().replace("remuestreos: 1000", "remuestreos: 50"))
    assert cli.main(["todo", "--muestra", "--sin-evidencia"]) == 1
    en_curso = tmp_path / "resultados" / "en_curso"
    pasos = json.loads((en_curso / "pasos.json").read_text())
    assert [p["estado"] for p in pasos] == ["ok", "ok", "ok", "fallo"]
    flujo = json.loads((en_curso / "flujo.json").read_text())
    assert flujo["estado"] == "fallo" and "n8n" in flujo["error"]
    assert flujo["lote"]["total"] > 0
    for nombre in ("modelo.json", "metricas.json", "comparativa.md"):
        assert (en_curso / nombre).is_file()
    assert json.loads((en_curso / "metricas.json").read_text())["reportable"] is False


# --- LLM local (fase 7) ---------------------------------------------------------------------


def test_llm_suelto_prepara_el_modelo(raiz, capsys):
    assert cli.main(["llm"]) == 0
    salida = capsys.readouterr().out
    assert "qwen3.5:4b-q4_K_M" in salida and "grafica" in salida


def test_llm_suelto_que_falla_devuelve_uno(raiz, monkeypatch, capsys):
    monkeypatch.setattr(cli, "preparar_llm", llm_falso(RuntimeError("sin red")))
    assert cli.main(["llm"]) == 1
    assert "sin red" in capsys.readouterr().out


def test_todo_con_llm_lo_prepara_primero(raiz, monkeypatch):
    monkeypatch.setattr(cli, "comprobar_servicios", servicios())
    assert cli.main(["todo", "--llm", "--sin-evidencia"]) == 0
    pasos = json.loads((raiz / "resultados" / "en_curso" / "pasos.json").read_text())
    assert [p["paso"] for p in pasos] == ["llm", "preparar", "entrenar", "evaluar", "demostrar"]


def test_todo_sin_llm_no_lo_toca(raiz, monkeypatch):
    llamado = llm_falso()
    monkeypatch.setattr(cli, "preparar_llm", llamado)
    assert cli.main(["todo", "--sin-evidencia"]) == 0
    assert llamado.llamadas == []
    pasos = json.loads((raiz / "resultados" / "en_curso" / "pasos.json").read_text())
    assert "llm" not in [p["paso"] for p in pasos]


def test_si_el_llm_falla_todo_sigue_con_la_plantilla(raiz, monkeypatch):
    monkeypatch.setattr(cli, "preparar_llm", llm_falso(RuntimeError("sin red")))
    assert cli.main(["todo", "--llm", "--sin-evidencia"]) == 1
    pasos = json.loads((raiz / "resultados" / "en_curso" / "pasos.json").read_text())
    assert [p["estado"] for p in pasos] == ["fallo", "ok", "ok", "ok", "ok"]
    assert "plantilla" in pasos[0]["detalle"]
