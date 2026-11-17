import json

import pytest

from fraude import cli


@pytest.fixture
def raiz(tmp_path, monkeypatch):
    monkeypatch.setenv("FRAUDE_RAIZ", str(tmp_path))
    monkeypatch.setenv("FRAUDE_COMMIT", "abc1234")
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
    assert {p["estado"] for p in pasos} == {"no_disponible"}
    assert carpetas(raiz) == []


def test_evidencia_lee_los_pasos_guardados(raiz, monkeypatch):
    monkeypatch.setattr(cli, "comprobar_servicios", servicios())
    cli.main(["todo", "--sin-evidencia"])

    assert cli.main(["evidencia"]) == 0
    resumen = (carpetas(raiz)[0] / "RESUMEN.md").read_text()
    assert "preparar" in resumen and "fase 2" in resumen


@pytest.mark.parametrize(
    ("comando", "fase"),
    [
        ("preparar", "fase 2"),
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
