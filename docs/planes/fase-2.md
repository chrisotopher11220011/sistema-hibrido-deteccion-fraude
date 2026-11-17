# Fase 2 — Datos y reglas: plan de implementación

> **Para quien ejecute el plan:** se trabaja tarea por tarea con `superpowers:executing-plans`, prueba primero. Cada paso lleva casilla (`- [ ]`).

**Meta:** que `tareas preparar` obtenga y verifique el conjunto, guarde la partición, deje el análisis exploratorio de la parte de ajuste y genere los datos sintéticos de ubicación; y que exista el motor de reglas deterministas con sus razones.

**Arquitectura:** módulos pequeños en `src/fraude/` (uno por responsabilidad) y un orquestador, `preparar.py`, que la línea de comandos llama. Los datos reales, la muestra para pruebas y los sintéticos viven en carpetas distintas de `datos/` y nunca comparten archivo. Lo que debe volver al chat (`datos.json` y `eda/`) se escribe en `resultados/en_curso/` y `evidencia` lo copia.

**Tecnología:** Python 3.12, pandas, NumPy, scikit-learn (partición estratificada), Matplotlib (figuras), Pydantic (forma de la transacción), PyYAML.

**Especificación:** `docs/spec.md`, secciones 8.2, 8.3, 8.8, 8.9, 9, 10, 16 y 21; ADR 0002, 0003 y 0006.

## Restricciones globales

- Conjunto real: 284.807 transacciones y 492 fraudes; columnas `Time`, `V1` a `V28`, `Amount` y `Class`.
- `preparar` funciona aunque falte `Time`: lo registra y continúa.
- Partición estratificada con semilla fija: 70 % desarrollo y 30 % prueba; el desarrollo, 80 % ajuste y 20 % validación. Los índices se guardan antes de cualquier ajuste.
- El análisis exploratorio usa solo la parte de ajuste.
- Sintéticos: `origen: "sintetico"`, con `monto` y `ubicacion`, sin `variables`. Nunca se mezclan con los originales.
- La muestra para pruebas no representa el fraude real y no produce métricas reportables.
- Ningún umbral ni parámetro dentro del código: van en `config/`. No se añaden archivos de configuración nuevos (contrato 8.9).
- No se inventan ni anticipan cifras de desempeño. Lo que no pasó por N3 es un supuesto.
- Nombres del dominio en español y sin tildes en el código. Fechas en UTC.

## Lo que se verificó antes de escribir código (2026-11-17, UTC)

| Tema | Hallazgo | Fuente |
|---|---|---|
| Entorno de este chat | Llega a GitHub y a PyPI. No llega a OpenML ni a Kaggle. Sin servicio de Docker | Comprobación directa |
| Conjunto 1597 en OpenML | Activo, formato ARFF, 31 atributos: `Time` (identificador de fila), `V1`…`V28`, `Amount` (numéricos) y `Class` (nominal, valores `0` y `1`, atributo objetivo). Archivo: `https://openml.org/data/v1/download/1673544/creditcard.arff`; también `https://www.openml.org/data/download/1673544/phpKo8OWT`. Suma MD5 publicada: `178bcf9bb1f31a3dfe12d0e577884add` | API JSON de OpenML, `data/1597` y `data/features/1597`, leída el 2026-11-17 |
| Parquet de OpenML | Existe (`data.openml.org/datasets/0000/1597/dataset_1597.pq`) pero exige `pyarrow`; no se usa | Ídem |
| Contenido exacto del ARFF | No pudo verse desde aquí. El lector acepta valores nominales con comillas o sin ellas y no supone que `Time` esté presente (supuesto S15) | — |

## Decisiones de esta fase

1. **Descarga directa del ARFF** con la biblioteca estándar, probando las dos direcciones en orden. No se usa `fetch_openml`, que omite `Time` por ser identificador de fila. El lector acepta también el CSV de Kaggle.
2. **Parámetros de datos en `config/modelo.yaml`** (bloques `datos`, `particion`, `muestra` y `sinteticos`), para no ampliar el contrato 8.9.
3. **Carpetas separadas:** `datos/crudos/` y `datos/preparados/` (reales), `datos/muestra/` (muestra) y `datos/sinteticos/` (ubicación).
4. **Huella:** al descargar de OpenML se comprueba la MD5 publicada (en `config/modelo.yaml`). Además se calcula la SHA-256 del archivo y del contenido normalizado (sin `Time`). La primera ejecución las fija en `datos/crudos/huella.json`; las siguientes las verifican. `config/modelo.yaml` admite una lista de huellas SHA-256 conocidas, vacía hasta N3.
5. **Partición determinista:** se recalcula siempre con la misma semilla y se compara con la guardada; `datos.json` dice si se creó, coincidió o cambió.
6. **Regla de ubicación fuera de sus datos:** con `origen: "original"` queda «no evaluable», aunque la transacción traiga `ubicacion`.
7. **Muestra:** `tareas preparar --muestra` y `tareas todo --muestra`; `./fraude` acepta la misma opción. `datos.json` marca `reportable: false`.

## Revisión dirigida

1. OpenML no responde o el contenedor no tiene internet → el paso falla con un mensaje que dice cómo dejar el archivo de Kaggle a mano; `todo` sigue y deja evidencia.
2. El archivo llega sin `Time` → se continúa y queda anotado.
3. Descarga cortada o archivo distinto → los conteos o la huella no coinciden y el paso falla sin guardar partición.
4. Se ejecuta `preparar` dos veces → misma partición, sin descargar de nuevo.
5. Una transacción sintética con `variables`, o una etiqueta `Class` dentro de la transacción → se rechaza.

Cada una tiene su prueba en la tarea que le corresponde.

---

### Tarea 1: configuración y forma de la transacción

**Archivos:** `config/modelo.yaml`, `config/reglas.yaml`, `src/fraude/configuracion.py`, `src/fraude/transaccion.py`, `tests/unitarias/test_transaccion.py`.

**Produce:** `configuracion.cargar(raiz: Path, nombre: str) -> dict`; `transaccion.VARIABLES` (`V1`…`V28`); `transaccion.Transaccion` (Pydantic, campos de 8.2, sin campos extra) y `transaccion.Ubicacion`.

- [ ] Pruebas: acepta el ejemplo de 8.2; rechaza `Class`, monto negativo o no finito, `origen` desconocido, sintético con `variables`, y `variables` con claves que no sean exactamente `V1`…`V28`.

### Tarea 2: motor de reglas

**Archivos:** `src/fraude/reglas.py`, `tests/unitarias/test_reglas.py`.

**Produce:** `reglas.evaluar_reglas(transaccion: Transaccion | dict, config: dict) -> list[dict]`, cada elemento con `id`, `evaluable`, `activada`, `alto_riesgo` y `razon` (8.3); `reglas.version(config) -> str`.

- [ ] Pruebas: `MONTO_ALTO` con 1250 se activa y su razón es «El monto 1250.00 supera el umbral 1000.00»; 1000 exacto no se activa; la de ubicación se activa con monto alto y países distintos, es de alto riesgo y nombra los países; sin `ubicacion` u `origen: original` queda no evaluable y no activada; el umbral sale de la configuración.

### Tarea 3: muestra para pruebas

**Archivos:** `src/fraude/muestra.py`, `tests/unitarias/test_muestra.py`.

**Produce:** `muestra.generar(filas: int, fraudes: int, semilla: int, con_time: bool = True) -> pd.DataFrame` con las columnas del conjunto real.

- [ ] Pruebas: columnas y tipos, número exacto de fraudes, misma semilla → mismos datos, `con_time=False` omite `Time`.

### Tarea 4: lectura, descarga e integridad

**Archivos:** `src/fraude/datos.py`, `tests/unitarias/test_datos.py`.

**Produce:** `datos.ErrorDatos`; `leer_conjunto(ruta: Path) -> pd.DataFrame`; `descargar(urls: list[str], destino: Path, tiempo_limite: float, abrir=...) -> str`; `huella_archivo(ruta) -> str`; `huella_contenido(df) -> str`; `comprobar_conteos(df, filas: int, fraudes: int) -> list[str]`.

- [ ] Pruebas: lee CSV y ARFF (con comillas y sin ellas, con `Time` y sin `Time`); falla si falta una columna obligatoria o hay valores vacíos; `Class` queda entera; la descarga prueba la segunda dirección si la primera falla, no deja archivos a medias y su error nombra la alternativa manual; la huella de contenido es igual con y sin `Time`.

### Tarea 5: partición

**Archivos:** `src/fraude/particion.py`, `tests/unitarias/test_particion.py`.

**Produce:** `particion.crear(clase: np.ndarray, semilla: int, prueba: float, validacion: float) -> np.ndarray` (valores `ajuste`, `validacion`, `prueba`); `particion.guardar(partes, carpeta, meta) -> dict`; `particion.cargar(carpeta) -> np.ndarray`.

- [ ] Pruebas: proporciones 56/14/30, cada fila en una sola parte, fraudes repartidos en proporción, misma semilla → misma partición, otra semilla → distinta.

### Tarea 6: generador sintético

**Archivos:** `src/fraude/sinteticos.py`, `tests/unitarias/test_sinteticos.py`.

**Produce:** `sinteticos.generar(cantidad: int, semilla: int, paises: list[str], monto_maximo: float, umbral_monto: float) -> list[dict]`; `sinteticos.comprobacion_funcional(transacciones: list[dict], config_reglas: dict) -> dict`.

- [ ] Pruebas: todas válidas como `Transaccion`, con `origen: sintetico` y sin `variables`; cubren las cuatro combinaciones de monto y país; reproducibles; la comprobación funcional no devuelve precisión ni exhaustividad.

### Tarea 7: análisis exploratorio

**Archivos:** `src/fraude/eda.py`, `tests/unitarias/test_eda.py`.

**Produce:** `eda.resumir(ajuste: pd.DataFrame, umbral_monto: float) -> dict`; `eda.escribir(ajuste, umbral_monto, carpeta: Path) -> list[str]` (nombres de archivo: `resumen.json`, `resumen.md` y figuras PNG, hechas con la skill `dataviz`).

- [ ] Pruebas: el resumen trae conteos, montos por clase, montos sobre el umbral por clase y separación por variable; funciona sin `Time` y lo anota; las figuras se crean.

### Tarea 8: `preparar` y línea de comandos

**Archivos:** `src/fraude/preparar.py`, `src/fraude/cli.py`, `tests/unitarias/test_preparar.py`, `tests/unitarias/test_cli.py`.

**Produce:** `preparar.preparar(raiz: Path, muestra: bool = False, abrir=...) -> dict` (contenido de `datos.json`, que también escribe en `resultados/en_curso/`); `preparar.cargar_preparados(raiz, muestra) -> tuple[pd.DataFrame, np.ndarray]` para la fase 3; comando `preparar [--muestra]` y `todo [--muestra]`.

- [ ] Pruebas: con la muestra deja partición, `datos.json`, `eda/` y sintéticos; el análisis usa solo ajuste; sin `Time` termina bien y lo dice; segunda ejecución no cambia la partición; conteos que no coinciden fallan sin dejar partición; archivo cambiado → la huella lo detecta; ningún archivo mezcla sintéticos con originales; `todo` sigue hasta `evidencia` aunque `preparar` falle.

### Tarea 9: evidencia, guion, CI y documentos

**Archivos:** `src/fraude/evidencia.py`, `fraude`, `compose.yaml`, `Dockerfile`, `.github/workflows/ci.yml`, `tests/punta_a_punta/comprobar_evidencia.py`, `EJECUTAR.md`, `README.md`, `CHANGELOG.md`, `docs/ESTADO.md`, `docs/supuestos.md`, `docs/architecture.md`.

- [ ] Pruebas: la evidencia copia `datos.json` y `eda/`; `./fraude todo --muestra` pasa la opción a `tareas`; una sesión nueva no arrastra `datos.json` ni `eda/` anteriores.
- [ ] La CI ejecuta `todo --muestra` y exige `datos.json` con `fuente: muestra` y `eda/resumen.json`.
- [ ] Versión 0.2.0, revisión con subagente, Pull Request, CI en verde.
