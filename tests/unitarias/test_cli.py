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


@pytest.fixture
def raiz(tmp_path, monkeypatch):
    monkeypatch.setenv("FRAUDE_RAIZ", str(tmp_path))
    monkeypatch.setenv("FRAUDE_COMMIT", "abc1234")
    monkeypatch.setattr(cli, "preparar", PrepararFalso())
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
    assert pasos[0]["estado"] == "ok"
    assert {p["estado"] for p in pasos[1:]} == {"no_disponible"}
    assert carpetas(raiz) == []


def test_evidencia_lee_los_pasos_guardados(raiz, monkeypatch):
    monkeypatch.setattr(cli, "comprobar_servicios", servicios())
    cli.main(["todo", "--sin-evidencia"])

    assert cli.main(["evidencia"]) == 0
    resumen = (carpetas(raiz)[0] / "RESUMEN.md").read_text()
    assert "preparar" in resumen and "fase 3" in resumen


@pytest.mark.parametrize(
    ("comando", "fase"),
    [
        ("entrenar", "fase 3"),
        ("evaluar", "fase 3"),
        ("demostrar", "fase 5"),
    ],
)
def test_comando_suelto_que_aun_no_existe_devuelve_dos(raiz, capsys, comando, fase):
    assert cli.main([comando]) == 2
    assert fase in capsys.readouterr().out


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


def test_todo_con_muestra_la_pasa_a_preparar(raiz, monkeypatch):
    monkeypatch.setattr(cli, "comprobar_servicios", servicios())
    assert cli.main(["todo", "--muestra", "--sin-evidencia"]) == 0
    assert cli.preparar.llamadas[0]["muestra"] is True


def test_preparar_de_verdad_con_la_muestra(tmp_path, monkeypatch):
    """Sin simular nada: el camino que sigue la CI (N2) con `tareas preparar --muestra`."""
    monkeypatch.setenv("FRAUDE_RAIZ", str(tmp_path))
    shutil.copytree(RAIZ_REPO / "config", tmp_path / "config")
    assert cli.main(["preparar", "--muestra"]) == 0
    informe = json.loads((tmp_path / "resultados" / "en_curso" / "datos.json").read_text())
    assert informe["estado"] == "ok" and informe["fuente"] == "muestra"
