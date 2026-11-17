import numpy as np
import pytest
from sklearn.metrics import fbeta_score

from fraude import modelo
from fraude.modelo import ErrorModelo

PARAMS = {"n_estimators": 50, "max_samples": 128, "max_features": 1.0, "bootstrap": False}


def datos(semilla=0, filas=2000):
    rng = np.random.default_rng(semilla)
    return rng.normal(size=(filas, 5))


def test_un_punto_atipico_puntua_mas_alto():
    X = datos()
    bosque = modelo.entrenar_bosque(X, PARAMS, semilla=42)
    p = modelo.puntuar(bosque, np.vstack([np.zeros(5), np.full(5, 8.0)]))
    assert p[1] > p[0]
    assert np.all((p > 0) & (p <= 1))


def test_misma_semilla_misma_puntuacion():
    X = datos()
    a = modelo.puntuar(modelo.entrenar_bosque(X, PARAMS, 42), X[:50])
    b = modelo.puntuar(modelo.entrenar_bosque(X, PARAMS, 42), X[:50])
    assert np.array_equal(a, b)


def _f_a_mano(y, p, umbral, beta):
    return fbeta_score(y, (p >= umbral).astype(int), beta=beta)


def test_umbral_revision_maximiza_f1_y_prioritaria_f05():
    rng = np.random.default_rng(3)
    y = np.r_[np.zeros(500, int), np.ones(20, int)]
    p = np.r_[rng.uniform(0, 0.7, 500), rng.uniform(0.5, 1.0, 20)]
    u = modelo.elegir_umbrales(y, p)
    mejor_f1 = max(_f_a_mano(y, p, t, 1) for t in np.unique(p))
    assert _f_a_mano(y, p, u["umbral_revision"], 1) == pytest.approx(mejor_f1)
    assert u["f1_validacion"] == pytest.approx(mejor_f1)
    mejor_f05 = max(_f_a_mano(y, p, t, 0.5) for t in np.unique(p) if t >= u["umbral_revision"])
    assert _f_a_mano(y, p, u["umbral_prioritaria"], 0.5) == pytest.approx(mejor_f05)
    assert u["umbral_prioritaria"] >= u["umbral_revision"]


def test_prioritaria_nunca_menor_que_revision():
    # F1 prefiere un corte alto (0.9) y F0,5 uno menor si se le dejara: se respeta el minimo.
    y = np.array([1, 1, 0, 1, 0, 0, 0, 0])
    p = np.array([0.95, 0.9, 0.85, 0.8, 0.3, 0.2, 0.1, 0.05])
    u = modelo.elegir_umbrales(y, p)
    assert u["umbral_prioritaria"] >= u["umbral_revision"]


def test_empate_elige_el_umbral_mayor():
    # Cortar en 0.9 o en 0.4 da el mismo F1; se toma 0.9 (menos alertas).
    y = np.array([1, 0, 0, 1, 0])
    p = np.array([0.9, 0.8, 0.7, 0.4, 0.1])
    umbral, valor = modelo.umbral_por_fbeta(y, p, 1.0)
    assert valor == pytest.approx(2 / 3)
    assert umbral == pytest.approx(0.9)


def test_validacion_sin_fraudes_falla_con_mensaje():
    with pytest.raises(ErrorModelo, match="fraudes"):
        modelo.elegir_umbrales(np.zeros(10, int), np.linspace(0, 1, 10))


def test_guardar_y_cargar_da_las_mismas_puntuaciones(tmp_path):
    X = datos()
    bosque = modelo.entrenar_bosque(X, PARAMS, 42)
    meta = modelo.guardar_artefacto(tmp_path / "m", bosque, {"umbral_revision": 0.6})
    cargado, meta_cargada = modelo.cargar_artefacto(tmp_path / "m")
    assert np.array_equal(modelo.puntuar(cargado, X[:30]), modelo.puntuar(bosque, X[:30]))
    assert meta_cargada["umbral_revision"] == 0.6
    assert meta_cargada["huella_artefacto"] == meta["huella_artefacto"]


def test_sin_artefacto_dice_que_entrene(tmp_path):
    with pytest.raises(ErrorModelo, match="entrenar"):
        modelo.cargar_artefacto(tmp_path / "no")
