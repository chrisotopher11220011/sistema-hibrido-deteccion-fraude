"""Lectura, descarga e integridad del conjunto (docs/spec.md, seccion 9; ADR 0002)."""

import hashlib
import io
import urllib.error

import pandas as pd
import pytest

from fraude.datos import (
    ErrorDatos,
    comprobar_conteos,
    descargar,
    huella_archivo,
    huella_contenido,
    leer_conjunto,
)
from fraude.muestra import generar

VS = [f"V{i}" for i in range(1, 29)]


def arff(con_time=True, comillas=True, filas=((0.0, 0.5, 149.62, 0), (1.0, -1.2, 2.69, 1))):
    q = "'" if comillas else ""
    lineas = ["% comentario", "@RELATION creditcard", ""]
    if con_time:
        lineas.append(f"@ATTRIBUTE {q}Time{q} NUMERIC")
    lineas += [f"@ATTRIBUTE {q}{v}{q} NUMERIC" for v in VS]
    lineas += [f"@ATTRIBUTE {q}Amount{q} NUMERIC", f"@ATTRIBUTE {q}Class{q} {{{q}0{q},{q}1{q}}}"]
    lineas.append("@DATA")
    for tiempo, v, monto, clase in filas:
        valores = ([str(tiempo)] if con_time else []) + [str(v)] * 28
        lineas.append(",".join([*valores, str(monto), f"{q}{clase}{q}"]))
    return "\n".join(lineas) + "\n"


def escribir(tmp_path, nombre, texto):
    ruta = tmp_path / nombre
    ruta.write_text(texto)
    return ruta


@pytest.mark.parametrize("comillas", [True, False])
def test_lee_arff_con_y_sin_comillas(tmp_path, comillas):
    df = leer_conjunto(escribir(tmp_path, "c.arff", arff(comillas=comillas)))
    assert list(df.columns) == ["Time", *VS, "Amount", "Class"]
    assert df["Class"].tolist() == [0, 1]
    assert df["Class"].dtype.kind == "i"
    assert df["Amount"].tolist() == [149.62, 2.69]


def test_lee_arff_sin_time(tmp_path):
    df = leer_conjunto(escribir(tmp_path, "c.arff", arff(con_time=False)))
    assert "Time" not in df.columns
    assert list(df.columns) == [*VS, "Amount", "Class"]


def test_lee_csv_de_kaggle_con_comillas(tmp_path):
    cabecera = ",".join(f'"{c}"' for c in ["Time", *VS, "Amount", "Class"])
    fila = ",".join(["0", *["0.1"] * 28, "12.5", '"1"'])
    df = leer_conjunto(escribir(tmp_path, "creditcard.csv", f"{cabecera}\n{fila}\n"))
    assert df["Class"].tolist() == [1] and df["Amount"].tolist() == [12.5]


def test_falta_una_columna_obligatoria(tmp_path):
    df = generar(20, 2, semilla=1).drop(columns="V7")
    ruta = tmp_path / "c.csv"
    df.to_csv(ruta, index=False)
    with pytest.raises(ErrorDatos, match="V7"):
        leer_conjunto(ruta)


def test_valores_vacios(tmp_path):
    texto = arff().replace("149.62", "?")
    with pytest.raises(ErrorDatos, match="vac"):
        leer_conjunto(escribir(tmp_path, "c.arff", texto))


def test_clase_fuera_de_cero_y_uno(tmp_path):
    df = generar(20, 2, semilla=1)
    df.loc[0, "Class"] = 2
    ruta = tmp_path / "c.csv"
    df.to_csv(ruta, index=False)
    with pytest.raises(ErrorDatos, match="Class"):
        leer_conjunto(ruta)


def test_formato_desconocido(tmp_path):
    with pytest.raises(ErrorDatos, match="formato"):
        leer_conjunto(escribir(tmp_path, "c.txt", "hola"))


def test_huella_de_contenido_no_depende_de_time_ni_del_formato(tmp_path):
    con = leer_conjunto(escribir(tmp_path, "a.arff", arff(con_time=True)))
    sin = leer_conjunto(escribir(tmp_path, "b.arff", arff(con_time=False)))
    assert huella_contenido(con) == huella_contenido(sin)
    con.to_csv(tmp_path / "c.csv", index=False)
    assert huella_contenido(leer_conjunto(tmp_path / "c.csv")) == huella_contenido(con)


def test_huella_de_contenido_cambia_si_cambia_un_dato(tmp_path):
    df = generar(50, 2, semilla=1)
    otro = df.copy()
    otro.loc[3, "Amount"] += 0.01
    assert huella_contenido(df) != huella_contenido(otro)


def test_huella_archivo_es_sha256(tmp_path):
    ruta = escribir(tmp_path, "x", "abc")
    assert huella_archivo(ruta) == hashlib.sha256(b"abc").hexdigest()
    assert huella_archivo(ruta, "md5") == hashlib.md5(b"abc").hexdigest()


def test_conteos():
    df = generar(100, 3, semilla=1)
    assert comprobar_conteos(df, filas=100, fraudes=3) == []
    problemas = comprobar_conteos(df, filas=284807, fraudes=492)
    assert len(problemas) == 2
    assert "284807" in problemas[0] and "100" in problemas[0]


class Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_descarga_prueba_la_segunda_direccion(tmp_path):
    vistas = []

    def abrir(url, timeout):
        vistas.append((url, timeout))
        if "uno" in url:
            raise urllib.error.URLError("sin red")
        return Respuesta(b"contenido")

    destino = tmp_path / "crudos" / "creditcard.arff"
    usada = descargar(["http://uno", "http://dos"], destino, 30, abrir=abrir)
    assert usada == "http://dos"
    assert destino.read_bytes() == b"contenido"
    assert vistas == [("http://uno", 30), ("http://dos", 30)]
    assert list(destino.parent.iterdir()) == [destino]


def test_descarga_comprueba_la_suma_md5(tmp_path):
    def abrir(url, timeout):
        return Respuesta(b"cortado" if "uno" in url else b"completo")

    destino = tmp_path / "c.arff"
    md5 = hashlib.md5(b"completo").hexdigest()
    assert descargar(["http://uno", "http://dos"], destino, 5, abrir=abrir, md5=md5) == "http://dos"
    assert destino.read_bytes() == b"completo"


def test_descarga_fallida_no_deja_archivos_y_explica_la_alternativa(tmp_path):
    def abrir(url, timeout):
        raise urllib.error.URLError("sin red")

    destino = tmp_path / "crudos" / "creditcard.arff"
    with pytest.raises(ErrorDatos) as error:
        descargar(["http://uno"], destino, 5, abrir=abrir)
    assert "datos/crudos/creditcard.csv" in str(error.value)
    assert "sin red" in str(error.value)
    assert not destino.exists()
    assert not any(destino.parent.glob("*")) if destino.parent.exists() else True


def test_lee_lo_que_escribe_la_muestra(tmp_path):
    df = generar(100, 3, semilla=2)
    df.to_csv(tmp_path / "m.csv", index=False)
    pd.testing.assert_frame_equal(leer_conjunto(tmp_path / "m.csv"), df, check_dtype=False)
