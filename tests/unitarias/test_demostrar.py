"""Paso `demostrar`: lote por n8n y por Python, paridad y latencia (docs/spec.md, 8.8, 12, 15, 16).

Los servicios se simulan: n8n y la API de verdad se prueban en N2.
"""

import json
import shutil
from pathlib import Path

import pytest

from fraude import demostrar as paso
from fraude.configuracion import cargar
from fraude.decision import clasificar
from fraude.preparar import preparar
from fraude.reglas import evaluar_reglas
from fraude.transaccion import Transaccion

RAIZ_REPO = Path(__file__).resolve().parents[2]
API, N8N = "http://api:8000", "http://n8n:5678"


@pytest.fixture(scope="module")
def raiz_base(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("demostrar")
    shutil.copytree(RAIZ_REPO / "config", raiz / "config")
    preparar(raiz, muestra=True)
    return raiz


@pytest.fixture
def raiz(raiz_base, tmp_path):
    destino = tmp_path / "raiz"
    shutil.copytree(raiz_base, destino)
    return destino


class Servicios:
    """API y n8n falsos. n8n aplica la tabla de Python salvo en `alterar` (ids)."""

    def __init__(self, raiz, alterar=(), ping_ok=True, n8n_caido=False):
        self.config_reglas = cargar(raiz, "reglas")
        self.alterar = set(alterar)
        self.ping_ok = ping_ok
        self.n8n_caido = n8n_caido
        self.llamadas = []

    def _evaluar(self, cuerpo):
        try:
            t = Transaccion.model_validate(cuerpo)
        except Exception:  # noqa: BLE001
            return 422, {"id_transaccion": None, "error": {"tipo": "entrada_invalida"}}
        anomalo = t.variables is not None and t.variables["V14"] < -2
        modelo = {
            "evaluable": t.variables is not None,
            "puntuacion": 0.9 if anomalo else 0.3,
            "umbral_revision": 0.6,
            "umbral_prioritaria": 0.8,
            "anomalia": anomalo,
            "anomalia_alta": anomalo,
        }
        return 200, {
            "id_transaccion": t.id_transaccion,
            "reglas": evaluar_reglas(t, self.config_reglas),
            "modelo": modelo,
            "versiones": {"reglas": "0.2.0", "modelo": "m"},
        }

    def __call__(self, metodo, url, cuerpo=None):
        self.llamadas.append((metodo, url))
        if url == f"{N8N}/webhook/ping":
            if not self.ping_ok:
                raise ConnectionError("n8n no responde")
            return 200, {"estado": "ok"}
        if url == f"{API}/evaluar":
            return self._evaluar(cuerpo)
        if url == f"{N8N}/webhook/transaccion":
            if self.n8n_caido:
                raise ConnectionError("conexion rechazada")
            codigo, senales = self._evaluar(cuerpo)
            nivel = clasificar(senales["reglas"], senales["modelo"]) if codigo == 200 else None
            nivel = nivel or "error_evaluacion"
            id_t = cuerpo.get("id_transaccion") if isinstance(cuerpo, dict) else None
            if id_t in self.alterar:
                nivel = "sin_alerta"
            estado = "cerrado" if nivel == "sin_alerta" else "pendiente_revision"
            id_caso = f"c-{len(self.llamadas):012x}"
            return 200, {"id_caso": id_caso, "nivel": nivel, "estado": estado}
        raise AssertionError(f"llamada inesperada {metodo} {url}")


def _flujo(raiz) -> dict:
    return json.loads((raiz / "resultados" / "en_curso" / "flujo.json").read_text())


def test_paridad_total_y_flujo_json(raiz):
    servicios = Servicios(raiz)
    informe = paso.demostrar(raiz, muestra=True, url_api=API, url_n8n=N8N, pedir=servicios)
    flujo = _flujo(raiz)
    assert flujo == informe
    assert flujo["estado"] == "ok"
    assert flujo["reportable"] is False and flujo["fuente"] == "muestra"
    total = flujo["lote"]["total"]
    assert flujo["paridad"] == {
        "total": total,
        "coinciden": total,
        "discrepancias": [],
        "completa": True,
    }
    assert sum(flujo["niveles_n8n"].values()) == total
    assert flujo["niveles_n8n"] == flujo["niveles_python"]
    assert flujo["niveles_n8n"]["error_evaluacion"] == flujo["lote"]["por_tipo"]["invalida"]
    assert flujo["latencia_ms"]["n"] == total
    assert 0 <= flujo["latencia_ms"]["mediana"] <= flujo["latencia_ms"]["p95"]
    assert flujo["latencia_ms"]["p95"] <= flujo["latencia_ms"]["maxima"]
    assert flujo["errores"] == []
    assert flujo["coherencia"]["incoherentes"] == []
    caso = flujo["casos"][0]
    assert set(caso) >= {
        "n",
        "tipo",
        "id_transaccion",
        "etiqueta_real",
        "nivel_n8n",
        "nivel_python",
        "coincide",
        "id_caso",
        "estado",
        "codigo_http",
        "latencia_ms",
    }


def test_envia_por_n8n_y_por_python_el_mismo_lote(raiz):
    servicios = Servicios(raiz)
    paso.demostrar(raiz, muestra=True, url_api=API, url_n8n=N8N, pedir=servicios)
    total = _flujo(raiz)["lote"]["total"]
    urls = [u for _, u in servicios.llamadas]
    assert urls.count(f"{N8N}/webhook/transaccion") == total
    assert urls.count(f"{API}/evaluar") == total


def test_una_discrepancia_hace_fallar_el_paso_y_queda_anotada(raiz):
    from fraude import lote

    elementos = lote.generar(raiz, muestra=True)["elementos"]
    con_alerta = next(
        e["transaccion"]["id_transaccion"]
        for e in elementos
        if e["tipo"] == "sintetico" and e["transaccion"]["monto"] > 1000
    )
    servicios = Servicios(raiz, alterar=[con_alerta])
    with pytest.raises(paso.ErrorDemostracion, match="paridad"):
        paso.demostrar(raiz, muestra=True, url_api=API, url_n8n=N8N, pedir=servicios)
    flujo = _flujo(raiz)
    assert flujo["estado"] == "fallo"
    assert flujo["paridad"]["completa"] is False
    [discrepancia] = flujo["paridad"]["discrepancias"]
    assert discrepancia["id_transaccion"] == con_alerta
    assert discrepancia["nivel_n8n"] == "sin_alerta"


def test_n8n_sin_responder_al_ping_falla_y_deja_flujo_json(raiz):
    servicios = Servicios(raiz, ping_ok=False)
    with pytest.raises(paso.ErrorDemostracion, match="n8n"):
        paso.demostrar(raiz, muestra=True, url_api=API, url_n8n=N8N, pedir=servicios)
    flujo = _flujo(raiz)
    assert flujo["estado"] == "fallo" and "n8n" in flujo["error"]


def test_errores_de_red_por_transaccion_se_registran(raiz):
    servicios = Servicios(raiz, n8n_caido=True)
    with pytest.raises(paso.ErrorDemostracion):
        paso.demostrar(raiz, muestra=True, url_api=API, url_n8n=N8N, pedir=servicios)
    flujo = _flujo(raiz)
    assert flujo["errores"] and "conexion rechazada" in flujo["errores"][0]["detalle"]
    assert flujo["paridad"]["completa"] is False
    assert all(c["nivel_n8n"] is None for c in flujo["casos"])


def test_incoherencia_entre_nivel_y_estado_falla(raiz):
    class Incoherente(Servicios):
        def __call__(self, metodo, url, cuerpo=None):
            codigo, respuesta = super().__call__(metodo, url, cuerpo)
            if url.endswith("/webhook/transaccion"):
                respuesta = {**respuesta, "estado": "cerrado"}
            return codigo, respuesta

    with pytest.raises(paso.ErrorDemostracion, match="estado"):
        paso.demostrar(raiz, muestra=True, url_api=API, url_n8n=N8N, pedir=Incoherente(raiz))
    assert _flujo(raiz)["coherencia"]["incoherentes"]


def test_caso_no_registrado_502_toma_el_nivel_del_caso(raiz):
    class SinRegistro(Servicios):
        def __call__(self, metodo, url, cuerpo=None):
            codigo, respuesta = super().__call__(metodo, url, cuerpo)
            if url.endswith("/webhook/transaccion"):
                caso = {"nivel": respuesta["nivel"]}
                return 502, {"error": {"tipo": "caso_no_registrado"}, "caso": caso}
            return codigo, respuesta

    with pytest.raises(paso.ErrorDemostracion, match="registr"):
        paso.demostrar(raiz, muestra=True, url_api=API, url_n8n=N8N, pedir=SinRegistro(raiz))
    flujo = _flujo(raiz)
    # La paridad se mide igual: el nivel viene en el caso calculado.
    assert flujo["paridad"]["completa"] is True
    assert all(c["id_caso"] is None for c in flujo["casos"])


def test_urls_por_defecto_salen_del_entorno(raiz, monkeypatch):
    monkeypatch.setenv("FRAUDE_URL_API", API)
    monkeypatch.setenv("FRAUDE_URL_N8N", N8N)
    informe = paso.demostrar(raiz, muestra=True, pedir=Servicios(raiz))
    assert informe["servicios"] == {"api": API, "n8n": N8N}
