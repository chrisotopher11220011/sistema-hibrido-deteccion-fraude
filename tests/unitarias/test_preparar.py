"""Paso `preparar` (docs/spec.md, secciones 8.8, 9 y 16)."""

import hashlib
import io
import json
import shutil
import urllib.error
from pathlib import Path

import pytest
import yaml

from fraude.datos import ErrorDatos
from fraude.muestra import generar
from fraude.preparar import cargar_preparados, preparar

RAIZ_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def raiz(tmp_path):
    shutil.copytree(RAIZ_REPO / "config", tmp_path / "config")
    return tmp_path


def configurar(raiz, **datos):
    ruta = raiz / "config" / "modelo.yaml"
    config = yaml.safe_load(ruta.read_text())
    config["datos"].update(datos)
    ruta.write_text(yaml.safe_dump(config))


def como_arff(df) -> bytes:
    lineas = ["@RELATION creditcard"]
    for columna in df.columns:
        tipo = "{'0','1'}" if columna == "Class" else "NUMERIC"
        lineas.append(f"@ATTRIBUTE '{columna}' {tipo}")
    lineas.append("@DATA")
    for fila in df.itertuples(index=False):
        valores = [repr(float(v)) for v in fila[:-1]] + [f"'{int(fila[-1])}'"]
        lineas.append(",".join(valores))
    return ("\n".join(lineas) + "\n").encode()


class Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class OpenMLFalso:
    def __init__(self, contenido: bytes):
        self.contenido = contenido
        self.llamadas = 0

    def __call__(self, url, timeout):
        self.llamadas += 1
        return Respuesta(self.contenido)


@pytest.fixture
def conjunto_real_pequeno(raiz):
    """Un 'conjunto real' en miniatura, servido por un OpenML simulado, sin Time."""
    df = generar(1500, 30, semilla=11, con_time=False)
    contenido = como_arff(df)
    configurar(
        raiz,
        filas_esperadas=1500,
        fraudes_esperados=30,
        md5_openml=hashlib.md5(contenido).hexdigest(),
    )
    return OpenMLFalso(contenido)


def leer(ruta):
    return json.loads(Path(ruta).read_text())


# --- Muestra -------------------------------------------------------------------


def test_muestra_deja_particion_informe_eda_y_sinteticos(raiz):
    informe = preparar(raiz, muestra=True)
    assert informe["estado"] == "ok"
    assert informe["fuente"] == "muestra"
    assert informe["reportable"] is False
    assert informe["filas"] == 6000 and informe["fraudes"] == 60
    assert (raiz / "datos" / "muestra" / "preparados" / "particion" / "particion.json").is_file()
    assert leer(raiz / "resultados" / "en_curso" / "datos.json") == informe
    assert (raiz / "resultados" / "en_curso" / "eda" / "resumen.json").is_file()
    assert (raiz / "datos" / "sinteticos" / "ubicacion.json").is_file()
    assert informe["sinteticos"]["comprobacion"]["correcta"] is True


def test_muestra_no_toca_las_carpetas_de_datos_reales(raiz):
    preparar(raiz, muestra=True)
    assert not (raiz / "datos" / "crudos").exists()
    assert not (raiz / "datos" / "preparados").exists()


def test_el_analisis_exploratorio_usa_solo_la_parte_de_ajuste(raiz):
    informe = preparar(raiz, muestra=True)
    resumen = leer(raiz / "resultados" / "en_curso" / "eda" / "resumen.json")
    assert resumen["filas"] == informe["particion"]["filas"]["ajuste"]
    assert resumen["filas"] < informe["filas"]


def test_informe_de_datos_trae_lo_que_pide_la_especificacion(raiz):
    informe = preparar(raiz, muestra=True)
    for clave in ("fuente", "filas", "fraudes", "columnas", "huellas", "particion", "fecha"):
        assert clave in informe
    assert informe["columnas"][-2:] == ["Amount", "Class"]
    assert informe["fecha"].endswith("Z")


# --- Conjunto real (OpenML simulado) ------------------------------------------


def test_real_sin_time_termina_bien_y_lo_dice(raiz, conjunto_real_pequeno):
    informe = preparar(raiz, abrir=conjunto_real_pequeno)
    assert informe["estado"] == "ok"
    assert informe["fuente"] == "openml"
    assert informe["reportable"] is True
    assert informe["tiene_time"] is False
    assert "Time" not in informe["columnas"]
    assert any("Time" in nota for nota in informe["notas"])
    assert informe["huellas"]["md5_coincide"] is True
    assert informe["huellas"]["estado"] == "fijada_ahora"
    assert (raiz / "datos" / "crudos" / "creditcard.arff").is_file()


def test_segunda_ejecucion_no_descarga_y_conserva_la_particion(raiz, conjunto_real_pequeno):
    primera = preparar(raiz, abrir=conjunto_real_pequeno)
    segunda = preparar(raiz, abrir=conjunto_real_pequeno)
    assert conjunto_real_pequeno.llamadas == 1
    assert segunda["particion"]["estado"] == "coincide"
    assert segunda["huellas"]["estado"] == "coincide"
    huella = primera["particion"]["huella_indices"]
    assert segunda["particion"]["huella_indices"] == huella


def test_conteos_distintos_fallan_sin_dejar_particion(raiz, conjunto_real_pequeno):
    configurar(raiz, filas_esperadas=284807, fraudes_esperados=492)
    with pytest.raises(ErrorDatos, match="284807"):
        preparar(raiz, abrir=conjunto_real_pequeno)
    assert not (raiz / "datos" / "preparados" / "particion").exists()
    informe = leer(raiz / "resultados" / "en_curso" / "datos.json")
    assert informe["estado"] == "fallo"
    assert "284807" in informe["error"]


def test_archivo_cambiado_lo_detecta_la_huella(raiz, conjunto_real_pequeno):
    preparar(raiz, abrir=conjunto_real_pequeno)
    df = generar(1500, 30, semilla=99, con_time=False)
    df.to_csv(raiz / "datos" / "crudos" / "creditcard.csv", index=False)
    with pytest.raises(ErrorDatos, match="huella"):
        preparar(raiz, abrir=conjunto_real_pequeno)


def test_huella_conocida_en_la_configuracion(raiz, conjunto_real_pequeno):
    configurar(raiz, huellas_sha256_conocidas=["0" * 64])
    with pytest.raises(ErrorDatos, match="huella"):
        preparar(raiz, abrir=conjunto_real_pequeno)


def test_arff_guardado_con_md5_distinto_falla(raiz, conjunto_real_pequeno):
    preparar(raiz, abrir=conjunto_real_pequeno)
    with (raiz / "datos" / "crudos" / "creditcard.arff").open("a") as archivo:
        archivo.write("% modificado\n")
    with pytest.raises(ErrorDatos, match="MD5"):
        preparar(raiz, abrir=conjunto_real_pequeno)


def test_archivo_de_kaggle_dejado_a_mano_no_descarga(raiz, conjunto_real_pequeno):
    df = generar(1500, 30, semilla=11)
    (raiz / "datos" / "crudos").mkdir(parents=True)
    df.to_csv(raiz / "datos" / "crudos" / "creditcard.csv", index=False)
    informe = preparar(raiz, abrir=conjunto_real_pequeno)
    assert conjunto_real_pequeno.llamadas == 0
    assert informe["fuente"] == "kaggle_manual"
    assert informe["tiene_time"] is True


def test_sin_red_falla_y_explica_la_alternativa(raiz):
    def sin_red(url, timeout):
        raise urllib.error.URLError("sin red")

    with pytest.raises(ErrorDatos, match="datos/crudos/creditcard.csv"):
        preparar(raiz, abrir=sin_red)
    informe = leer(raiz / "resultados" / "en_curso" / "datos.json")
    assert informe["estado"] == "fallo"


# --- Separacion de originales y sinteticos -----------------------------------


def test_sinteticos_nunca_se_mezclan_con_los_originales(raiz, conjunto_real_pequeno):
    preparar(raiz, abrir=conjunto_real_pequeno)
    preparar(raiz, muestra=True)
    sinteticos = leer(raiz / "datos" / "sinteticos" / "ubicacion.json")
    assert {t["origen"] for t in sinteticos} == {"sintetico"}
    assert all("variables" not in t for t in sinteticos)
    for carpeta in (raiz / "datos" / "crudos", raiz / "datos" / "preparados", raiz / "datos" / "muestra"):
        for archivo in carpeta.rglob("*"):
            if archivo.is_file():
                assert "s-00001" not in archivo.read_text(errors="replace"), archivo
    df, partes = cargar_preparados(raiz)
    assert len(df) == 1500 and len(partes) == 1500


def test_cargar_preparados_devuelve_datos_y_partes_alineados(raiz):
    informe = preparar(raiz, muestra=True)
    df, partes = cargar_preparados(raiz, muestra=True)
    assert len(df) == len(partes) == informe["filas"]
    assert int(df.loc[partes == "prueba", "Class"].sum()) == 18


def test_cargar_preparados_sin_preparar_dice_que_hacer(raiz):
    with pytest.raises(ErrorDatos, match="preparar"):
        cargar_preparados(raiz)
