"""Explicacion con LLM local (docs/spec.md, secciones 14 y 15; ADR 0009 y 0016).

El LLM solo redacta. Estas pruebas usan una funcion `pedir` simulada en lugar del servidor:
comprueban que el mensaje lleva solo senales calculadas, que la comprobacion automatica
rechaza lo que debe y que cualquier fallo termina en la plantilla con su motivo.
"""

import copy

import pytest

from apoyo import RAIZ_REPO as RAIZ
from fraude import explicacion
from fraude.configuracion import cargar

CONFIG = cargar(RAIZ, "llm")
UBICACION = "MONTO_ALTO_UBICACION_INUSUAL"


def _regla(id_regla, activada, alto_riesgo=False, evaluable=True, razon=None):
    return {
        "id": id_regla,
        "evaluable": evaluable,
        "activada": activada,
        "alto_riesgo": alto_riesgo,
        "razon": razon
        or ("El monto 1250.00 supera el umbral 1000.00" if activada else "No se activa"),
    }


def _senales(monto=True, ubicacion=False, anomalia=True, alta=True, contribuciones=True):
    modelo = {
        "evaluable": True,
        "puntuacion": 0.812 if anomalia else 0.4,
        "umbral_revision": 0.62,
        "umbral_prioritaria": 0.74,
        "anomalia": anomalia,
        "anomalia_alta": anomalia and alta,
    }
    if anomalia and contribuciones:
        modelo["contribuciones"] = [
            {"variable": "V14", "peso": 0.21},
            {"variable": "V4", "peso": 0.08},
        ]
    return {
        "id_transaccion": "t-000457",
        "reglas": [
            _regla("MONTO_ALTO", monto),
            _regla(
                "MONTO_ALTO_UBICACION_INUSUAL",
                ubicacion,
                alto_riesgo=True,
                razon=(
                    "El monto 1250.00 supera 1000.00 y el pais US difiere del habitual EC"
                    if ubicacion
                    else "No evaluable: la transaccion no trae ubicacion"
                ),
                evaluable=ubicacion,
            ),
        ],
        "modelo": modelo,
        "versiones": {"reglas": "0.2.0", "modelo": "2026-11-20T15:04Z-a1b2c3"},
    }


BUENO = (
    "El sistema señala esta transacción como alerta prioritaria. Se activó MONTO_ALTO porque "
    "el monto 1250.00 supera el umbral 1000.00, y la puntuación del modelo (0.812) supera el "
    "umbral prioritario 0.740; las variables que más pesaron fueron V14 y V4. Una persona debe "
    "revisarla y decidir."
)


def _respuesta(texto, modelo="qwen3.5:4b-q4_K_M"):
    return {"model": modelo, "choices": [{"message": {"role": "assistant", "content": texto}}]}


class Pedidos:
    """Sustituye la peticion HTTP al LLM y guarda lo que se le envio."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.enviados = []

    def __call__(self, url, cuerpo, tiempo_limite):
        self.enviados.append({"url": url, "cuerpo": cuerpo, "tiempo_limite": tiempo_limite})
        r = self.respuestas.pop(0)
        if isinstance(r, BaseException):
            raise r
        return r


def _redactar(pedir, nivel="alerta_prioritaria", senales=None, activo=True, config=CONFIG):
    return explicacion.redactar(
        nivel, senales if senales is not None else _senales(), config, activo=activo, pedir=pedir
    )


# --- Configuracion ------------------------------------------------------------------------


def test_configuracion_fija_servidor_modelo_y_tiempo_limite():
    assert CONFIG["servidor"]["url"] == "http://llm:11434"
    assert CONFIG["modelo"] == "qwen3.5:4b-q4_K_M"
    assert 0 < CONFIG["tiempo_limite_s"] <= 60
    assert set(CONFIG["redactar_niveles"]) == {"alerta_prioritaria", "revision_recomendada"}
    etiquetas = CONFIG["comprobacion"]["etiquetas_nivel"]
    assert set(etiquetas) == {
        "alerta_prioritaria",
        "revision_recomendada",
        "sin_alerta",
        "error_evaluacion",
    }


# --- Mensaje: solo senales calculadas -----------------------------------------------------


def test_mensaje_con_nivel_reglas_activadas_modelo_y_contribuciones():
    mensajes = explicacion.mensajes("alerta_prioritaria", _senales(), CONFIG)
    assert [m["role"] for m in mensajes] == ["system", "user"]
    sistema, usuario = mensajes[0]["content"], mensajes[1]["content"]
    assert "«alerta prioritaria»" in sistema
    assert "no digas que la transacción es fraude" in sistema
    assert "Nivel: alerta prioritaria" in usuario
    assert "MONTO_ALTO: El monto 1250.00 supera el umbral 1000.00" in usuario
    assert "0.812" in usuario and "0.620" in usuario and "0.740" in usuario
    assert "supera el umbral prioritario" in usuario
    assert "V14 (0.210)" in usuario and "V4 (0.080)" in usuario


def test_mensaje_sin_reglas_no_activadas_ni_datos_crudos():
    senales = _senales(monto=True, ubicacion=False)
    usuario = explicacion.mensajes("alerta_prioritaria", senales, CONFIG)[1]["content"]
    assert "MONTO_ALTO_UBICACION_INUSUAL" not in usuario
    assert "ubicacion" not in usuario.lower()
    assert "id_transaccion" not in usuario and "t-000457" not in usuario
    assert "Class" not in usuario and "etiqueta" not in usuario.lower()


def test_mensaje_sin_reglas_activadas_lo_dice():
    senales = _senales(monto=False, anomalia=True, alta=False)
    usuario = explicacion.mensajes("revision_recomendada", senales, CONFIG)[1]["content"]
    assert "Reglas activadas: ninguna" in usuario
    assert "supera el umbral de revisión" in usuario


def test_mensaje_con_modelo_no_evaluable():
    senales = _senales(monto=True, anomalia=False)
    senales["modelo"].update(evaluable=False, puntuacion=None)
    usuario = explicacion.mensajes("revision_recomendada", senales, CONFIG)[1]["content"]
    assert "no evaluable" in usuario
    assert "Variables que más pesaron" not in usuario


def test_regla_de_alto_riesgo_se_marca():
    senales = _senales(monto=True, ubicacion=True)
    usuario = explicacion.mensajes("alerta_prioritaria", senales, CONFIG)[1]["content"]
    assert "MONTO_ALTO_UBICACION_INUSUAL (alto riesgo):" in usuario


# --- Comprobacion automatica (seccion 15) --------------------------------------------------


def test_texto_correcto_pasa_la_comprobacion():
    resultado = explicacion.comprobar(BUENO, "alerta_prioritaria", _senales(), CONFIG)
    assert resultado == {"valida": True, "fallos": []}


def test_la_comprobacion_no_depende_de_tildes_ni_mayusculas():
    texto = BUENO.replace("alerta prioritaria", "ALERTA PRIORITÁRIA".replace("Á", "A"))
    assert explicacion.comprobar(texto, "alerta_prioritaria", _senales(), CONFIG)["valida"]
    texto = "Revision recomendada: se activo MONTO_ALTO. Una persona debe revisarla."
    senales = _senales(anomalia=False)
    assert explicacion.comprobar(texto, "revision_recomendada", senales, CONFIG)["valida"]


@pytest.mark.parametrize(
    ("texto", "fallo"),
    [
        ("", "vacio"),
        ("   ", "vacio"),
        ("<think>pienso</think> " + BUENO, "razonamiento_visible"),
        (BUENO.replace("alerta prioritaria", "alerta"), "nivel_no_mencionado"),
        (BUENO + " No es revisión recomendada.", "nivel_ajeno:revision_recomendada"),
        (
            BUENO + " También MONTO_ALTO_UBICACION_INUSUAL.",
            "regla_no_activada:MONTO_ALTO_UBICACION_INUSUAL",
        ),
        (BUENO + " El país es distinto.", "regla_no_activada:MONTO_ALTO_UBICACION_INUSUAL"),
        (BUENO + " Y la regla HORARIO_RARO.", "regla_inexistente:HORARIO_RARO"),
        (BUENO + " También pesó V3.", "variable_no_calculada:V3"),
        (BUENO + " La transacción es fraude.", "afirmacion_prohibida"),
        (BUENO + " Fraude confirmado.", "afirmacion_prohibida"),
        (BUENO + " Se confirma el fraude.", "afirmacion_prohibida"),
        (BUENO + " Es fraudulenta.", "afirmacion_prohibida"),
        (BUENO + " x" * 400, "demasiado_largo"),
        (BUENO + " Superó el umbral por 0.072 puntos.", "cifra_no_calculada:0.072"),
        (BUENO.replace("1250.00", "1350.00"), "cifra_no_calculada:1350.00"),
    ],
)
def test_la_comprobacion_rechaza(texto, fallo):
    resultado = explicacion.comprobar(texto, "alerta_prioritaria", _senales(), CONFIG)
    assert resultado["valida"] is False
    assert any(f == fallo or f.startswith(fallo + ":") for f in resultado["fallos"]), resultado


def test_regla_activada_puede_nombrarse_y_su_palabra_tambien():
    senales = _senales(monto=True, ubicacion=True)
    texto = (
        "Alerta prioritaria: se activaron MONTO_ALTO y MONTO_ALTO_UBICACION_INUSUAL, porque el "
        "país difiere del habitual. Una persona debe revisarla."
    )
    assert explicacion.comprobar(texto, "alerta_prioritaria", senales, CONFIG)["valida"]


def test_monto_alto_no_se_confunde_con_la_regla_de_ubicacion():
    # MONTO_ALTO es prefijo de MONTO_ALTO_UBICACION_INUSUAL: solo cuenta el identificador entero.
    senales = _senales(monto=False, ubicacion=True)
    senales["reglas"][1]["evaluable"] = True
    texto = "Alerta prioritaria: se activó MONTO_ALTO_UBICACION_INUSUAL. Debe revisarse."
    assert explicacion.comprobar(texto, "alerta_prioritaria", senales, CONFIG)["valida"]
    texto = "Alerta prioritaria: se activó MONTO_ALTO. Debe revisarse."
    resultado = explicacion.comprobar(texto, "alerta_prioritaria", senales, CONFIG)
    assert "regla_no_activada:MONTO_ALTO" in resultado["fallos"]


# --- Redaccion y respaldo -----------------------------------------------------------------


def test_sin_llm_activo_usa_la_plantilla_sin_llamar():
    pedir = Pedidos()
    redaccion = _redactar(pedir, activo=False)
    assert pedir.enviados == []
    assert redaccion["origen"] == "plantilla"
    assert redaccion["texto"] is None
    assert redaccion["respaldo"]["motivo"] == "llm_desactivado"
    assert redaccion["comprobacion"] is None


@pytest.mark.parametrize("nivel", ["sin_alerta", "error_evaluacion"])
def test_niveles_sin_alerta_no_se_redactan(nivel):
    pedir = Pedidos()
    redaccion = _redactar(pedir, nivel=nivel, senales={} if nivel == "error_evaluacion" else None)
    assert pedir.enviados == []
    assert redaccion["origen"] == "plantilla"
    assert redaccion["respaldo"]["motivo"] == "nivel_sin_redaccion"


def test_redaccion_del_modelo_con_trazabilidad():
    pedir = Pedidos(_respuesta("  " + BUENO + "\n"))
    redaccion = _redactar(pedir)
    assert redaccion["origen"] == "llm"
    assert redaccion["texto"] == BUENO
    assert redaccion["modelo"] == "qwen3.5:4b-q4_K_M"
    assert isinstance(redaccion["duracion_ms"], float) and redaccion["duracion_ms"] >= 0
    assert redaccion["respaldo"] is None
    assert redaccion["comprobacion"] == {"valida": True, "fallos": []}
    enviado = pedir.enviados[0]
    assert enviado["url"] == "http://llm:11434/v1/chat/completions"
    assert enviado["tiempo_limite"] == CONFIG["tiempo_limite_s"]
    cuerpo = enviado["cuerpo"]
    assert cuerpo["model"] == CONFIG["modelo"]
    assert cuerpo["stream"] is False
    assert cuerpo["temperature"] == CONFIG["generacion"]["temperatura"]
    assert cuerpo["seed"] == CONFIG["generacion"]["semilla"]
    assert cuerpo["max_tokens"] == CONFIG["generacion"]["max_tokens"]
    assert cuerpo["reasoning_effort"] == "none"


def test_texto_que_no_pasa_la_comprobacion_usa_la_plantilla_y_lo_anota():
    malo = BUENO + " La transacción es fraude."
    redaccion = _redactar(Pedidos(_respuesta(malo)))
    assert redaccion["origen"] == "plantilla"
    assert redaccion["texto"] is None
    respaldo = redaccion["respaldo"]
    assert respaldo["motivo"] == "comprobacion_fallida"
    assert respaldo["texto_descartado"] == malo
    assert respaldo["modelo"] == "qwen3.5:4b-q4_K_M"
    assert respaldo["duracion_ms"] >= 0
    assert redaccion["comprobacion"]["valida"] is False
    assert "afirmacion_prohibida" in " ".join(redaccion["comprobacion"]["fallos"])


def test_tiempo_agotado_usa_la_plantilla():
    redaccion = _redactar(Pedidos(TimeoutError("timed out")))
    assert redaccion["origen"] == "plantilla"
    assert redaccion["respaldo"]["motivo"] == "tiempo_agotado"


def test_respuesta_lenta_aunque_llegue_cuenta_como_tiempo_agotado():
    marcas = iter([0.0, CONFIG["tiempo_limite_s"] + 1.0])
    redaccion = explicacion.redactar(
        "alerta_prioritaria",
        _senales(),
        CONFIG,
        activo=True,
        pedir=Pedidos(_respuesta(BUENO)),
        reloj=lambda: next(marcas),
    )
    assert redaccion["origen"] == "plantilla"
    assert redaccion["respaldo"]["motivo"] == "tiempo_agotado"


@pytest.mark.parametrize(
    "fallo",
    [
        ConnectionRefusedError("Connection refused"),
        OSError("Name or service not known"),
        ValueError("respuesta que no es JSON"),
    ],
)
def test_error_del_llm_usa_la_plantilla(fallo):
    redaccion = _redactar(Pedidos(fallo))
    assert redaccion["origen"] == "plantilla"
    assert redaccion["respaldo"]["motivo"] == "error_llm"
    assert redaccion["respaldo"]["detalle"]


@pytest.mark.parametrize(
    "respuesta",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": 3}}]},
    ],
)
def test_respuesta_sin_texto_es_error_del_llm(respuesta):
    redaccion = _redactar(Pedidos(respuesta))
    assert redaccion["origen"] == "plantilla"
    assert redaccion["respaldo"]["motivo"] == "error_llm"


def test_redactar_no_modifica_las_senales():
    senales = _senales()
    copia = copy.deepcopy(senales)
    _redactar(Pedidos(_respuesta(BUENO)), senales=senales)
    assert senales == copia


def test_llm_activo_lo_decide_la_variable_de_entorno(monkeypatch):
    monkeypatch.delenv("FRAUDE_LLM", raising=False)
    assert explicacion.llm_activo() is False
    monkeypatch.setenv("FRAUDE_LLM", "desactivado")
    assert explicacion.llm_activo() is False
    monkeypatch.setenv("FRAUDE_LLM", "activo")
    assert explicacion.llm_activo() is True


def test_las_cifras_del_mensaje_pueden_citarse_con_otro_formato():
    texto = (
        "Alerta prioritaria: MONTO_ALTO porque el monto 1250 supera 1000; la puntuación 0,812 "
        "supera el umbral prioritario 0.74. Pesaron V14 (0.21) y V4. Una persona debe revisarla."
    )
    assert explicacion.comprobar(texto, "alerta_prioritaria", _senales(), CONFIG)["valida"]
