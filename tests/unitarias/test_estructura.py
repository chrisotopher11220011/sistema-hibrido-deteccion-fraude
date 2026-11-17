"""Comprobaciones de estructura que no necesitan Docker (N1)."""

import json
import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
COMPOSE = yaml.safe_load((RAIZ / "compose.yaml").read_text())
FLUJOS = sorted((RAIZ / "n8n" / "flujos").glob("*.json"))


def test_servicios_del_contrato():
    assert {"api", "n8n", "tareas"} <= set(COMPOSE["services"])


def test_puertos_solo_en_la_maquina_local():
    for nombre, servicio in COMPOSE["services"].items():
        for puerto in servicio.get("ports", []):
            assert str(puerto).startswith("127.0.0.1:"), f"{nombre} publica {puerto}"


def test_puertos_por_defecto_del_contrato():
    assert COMPOSE["services"]["api"]["ports"] == ["127.0.0.1:${FRAUDE_PUERTO_API:-8000}:8000"]
    assert COMPOSE["services"]["n8n"]["ports"] == ["127.0.0.1:${FRAUDE_PUERTO_N8N:-5678}:5678"]
    assert "ports" not in COMPOSE["services"]["tareas"]


def test_n8n_con_version_exacta_y_declarada_en_tareas():
    imagen = COMPOSE["services"]["n8n"]["image"]
    coincidencia = re.fullmatch(r"n8nio/n8n:(\d+\.\d+\.\d+)", imagen)
    assert coincidencia, f"La imagen de n8n no fija una version exacta: {imagen}"
    entorno = COMPOSE["services"]["tareas"]["environment"]
    assert entorno["N8N_VERSION_FIJADA"] == coincidencia.group(1)


def test_imagen_de_python_con_version_exacta():
    primera = (RAIZ / "Dockerfile").read_text().splitlines()[0]
    assert re.fullmatch(r"FROM python:\d+\.\d+\.\d+-slim-\w+", primera), primera


def test_tareas_no_arranca_sola():
    assert COMPOSE["services"]["tareas"]["profiles"] == ["tareas"]


def test_hay_flujo_ping():
    assert (RAIZ / "n8n" / "flujos" / "ping.json") in FLUJOS


def test_flujos_con_id_fijo_y_unico():
    ids = [json.loads(f.read_text())["id"] for f in FLUJOS]
    assert all(re.fullmatch(r"[A-Za-z0-9]{16}", i) for i in ids), ids
    assert len(ids) == len(set(ids))


def test_webhooks_con_identificador_propio():
    for flujo in FLUJOS:
        for nodo in json.loads(flujo.read_text())["nodes"]:
            if nodo["type"] == "n8n-nodes-base.webhook":
                assert nodo.get("webhookId"), f"{flujo.name}: {nodo['name']} sin webhookId"


def test_ping_es_get_en_la_ruta_del_contrato():
    flujo = json.loads((RAIZ / "n8n" / "flujos" / "ping.json").read_text())
    webhook = next(n for n in flujo["nodes"] if n["type"] == "n8n-nodes-base.webhook")
    assert webhook["parameters"]["httpMethod"] == "GET"
    assert webhook["parameters"]["path"] == "ping"
    destino = flujo["connections"][webhook["name"]]["main"][0][0]["node"]
    assert destino in {n["name"] for n in flujo["nodes"]}


def test_arranque_de_n8n_importa_publica_y_arranca():
    guion = (RAIZ / "n8n" / "arranque.sh").read_text()
    assert "import:workflow" in guion
    assert "publish:workflow --id=" in guion
    assert "update:workflow" not in guion
    assert guion.rstrip().endswith("exec n8n start")


def test_configuracion_sin_umbrales_en_el_codigo():
    reglas = yaml.safe_load((RAIZ / "config" / "reglas.yaml").read_text())["reglas"]
    assert reglas["MONTO_ALTO"]["umbral_monto"] == 1000
    assert reglas["MONTO_ALTO"]["alto_riesgo"] is False
    assert reglas["MONTO_ALTO_UBICACION_INUSUAL"]["alto_riesgo"] is True
    for nombre in ("modelo.yaml", "decision.yaml"):
        assert yaml.safe_load((RAIZ / "config" / nombre).read_text())
