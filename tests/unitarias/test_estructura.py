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


# --- LLM local (fase 7, ADR 0016) -----------------------------------------------------------

CONFIG_LLM = yaml.safe_load((RAIZ / "config" / "llm.yaml").read_text())


def test_llm_solo_con_su_perfil_version_exacta_y_sin_puertos():
    llm = COMPOSE["services"]["llm"]
    assert llm["profiles"] == ["llm"]
    assert re.fullmatch(r"ollama/ollama:\d+\.\d+\.\d+", llm["image"]), llm["image"]
    assert "ports" not in llm
    assert "deploy" not in llm  # La grafica solo con compose.gpu.yaml.
    assert llm["environment"]["OLLAMA_KEEP_ALIVE"] == "-1"
    assert any(str(v).startswith("ollama_modelos:") for v in llm["volumes"])
    assert "ollama_modelos" in COMPOSE["volumes"]
    assert llm["healthcheck"]["test"][:2] == ["CMD", "ollama"]


def test_la_api_no_depende_del_llm_y_lo_usa_solo_si_se_activa():
    api = COMPOSE["services"]["api"]
    assert "llm" not in (api.get("depends_on") or {})
    assert api["environment"]["FRAUDE_LLM"] == "${FRAUDE_LLM:-desactivado}"
    assert "llm" not in (COMPOSE["services"]["tareas"].get("depends_on") or {})


def test_la_configuracion_apunta_al_servicio_llm():
    assert CONFIG_LLM["servidor"]["url"] == "http://llm:11434"


def test_la_grafica_se_reserva_en_un_archivo_aparte():
    gpu = yaml.safe_load((RAIZ / "compose.gpu.yaml").read_text())
    assert set(gpu["services"]) == {"llm"}
    dispositivos = gpu["services"]["llm"]["deploy"]["resources"]["reservations"]["devices"]
    assert dispositivos == [{"driver": "nvidia", "count": "all", "capabilities": ["gpu"]}]


def test_omarchy_no_usa_sus_modelos_propios():
    texto = (RAIZ / "fraude").read_text() + (RAIZ / "compose.yaml").read_text()
    assert "omarchy agent" not in texto and "11435" not in texto
