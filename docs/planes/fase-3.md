# Fase 3 — Aprendizaje automático: plan de implementación

> **Para quien ejecute el plan:** se trabaja tarea por tarea con `superpowers:executing-plans`, prueba primero. Cada paso lleva casilla (`- [ ]`).

**Meta:** que `tareas entrenar` entrene Isolation Forest y elija los umbrales en validación, y que `tareas evaluar` aplique completo el protocolo de la sección 15 (cuatro configuraciones, tres líneas base, intervalos por *bootstrap*, diez semillas, precisión en los *k* primeros, partición temporal secundaria), con figuras, `comparativa.md` y análisis de errores de validación.

**Arquitectura:** módulos pequeños y puros en `src/fraude/` (`modelo`, `decision`, `contribuciones`, `metricas`, `graficas`, `figuras`) y dos orquestadores (`entrenar`, `evaluar`) que la línea de comandos llama. El artefacto del modelo vive en `datos/modelo/` (o `datos/muestra/modelo/`); lo que vuelve al equipo se escribe en `resultados/en_curso/` y `evidencia` lo copia.

**Tecnología:** Python 3.12, scikit-learn 1.9.1 (`IsolationForest`), NumPy, pandas, joblib, SHAP 0.54.1 (`TreeExplainer`), Matplotlib.

**Especificación:** `docs/spec.md`, secciones 8.3, 8.4, 8.8, 8.9, 9, 11, 15, 16 y 21; ADR 0003, 0008 y 0011.

## Restricciones globales

- Entrenar solo con `ajuste` y sin etiquetas. Umbrales solo con `validacion`. `prueba` solo para métricas agregadas.
- Los archivos de análisis de errores salen de `validacion`.
- `umbral_revision` maximiza F1 en validación; `umbral_prioritaria` maximiza F0,5 y nunca es menor que `umbral_revision`. Quedan en `modelo.json`, no en `config/`.
- Puntuación: mayor = más anómalo. `anomalia = puntuacion >= umbral_revision`.
- Tabla de decisión de la sección 8.4, copia en Python.
- *Bootstrap* estratificado con 1.000 remuestreos y 10 semillas por defecto, en `config/modelo.yaml`.
- Lo calculado con la muestra lleva `reportable: false` y un aviso: no es un resultado.
- Ningún parámetro dentro del código. No se añaden archivos de configuración (contrato 8.9).
- Sin metas numéricas ni cifras anticipadas.

## Lo que se verificó antes de escribir código (2026-11-17, UTC)

| Tema | Hallazgo | Fuente |
|---|---|---|
| Entorno de este chat | Llega a GitHub y a PyPI; no a OpenML ni a Kaggle; sin servicio de Docker | Comprobación directa |
| SHAP para `IsolationForest` | `shap.TreeExplainer` 0.54.1 reconoce `sklearn.ensemble.IsolationForest` (clase `IsoTree`, que recalcula los valores de las hojas como profundidad + c(n), igual que scikit-learn) y respeta `estimators_features_`. Con scikit-learn 1.9.1, `expected_value + suma(valores SHAP)` reconstruye la profundidad media y de ella `score_samples` con error máximo 3e-16. Unos 1 ms por fila | Código fuente de `shap/explainers/_tree.py` y ensayo directo |
| Dependencias de SHAP 0.54.1 | numpy ≥ 2, scipy, scikit-learn, pandas, tqdm, packaging, slicer, cloudpickle. Ya no exige numba. Licencia MIT, Python ≥ 3.12 | Metadatos de PyPI |
| DIFFI | No hay paquete en PyPI (`diffi` y `DIFFI` devuelven 404): solo código de un artículo, sin mantenimiento | PyPI |

## Decisiones de esta fase

1. **Contribución por variable con SHAP para árboles** (ADR 0012). Peso de una variable = −valor SHAP sobre la profundidad media: positivo empuja hacia «más anómalo». Una prueba comprueba la aditividad con la versión instalada, de modo que un cambio de scikit-learn o de SHAP que la rompa se ve en la CI.
2. **Puntuación** = `-score_samples`, la puntuación de anomalía original de Liu et al., en (0, 1].
3. **Parámetros iniciales**: los del artículo original y de scikit-learn (100 árboles, 256 muestras por árbol, todas las variables), sin transformar las variables.
4. **Empates en el umbral**: entre umbrales con el mismo F1 (o F0,5) se toma el mayor, que da menos alertas.
5. **Reglas en la evaluación**: se llama al motor de reglas de la fase 2 una vez por monto distinto y se reparte el resultado, para usar exactamente el mismo código que la API.
6. **Líneas base**: no alertar nunca; azar con la misma cantidad de alertas que el híbrido con cualquier alerta en la prueba (usa el conteo de alertas, no las etiquetas); ordenar por monto, con su corte elegido en validación por F1.
7. **Precisión en los *k* primeros**: `k` en `config/modelo.yaml` (100 por defecto, la del manual de la ULB) para las puntuaciones continuas: modelo, monto y azar.
8. **Intervalos**: percentiles 2,5 y 97,5 del *bootstrap* estratificado; las métricas se calculan con pesos (cuántas veces sale cada fila), lo que evita copiar los datos mil veces. Una prueba compara contra scikit-learn con las filas repetidas.
9. **Diferencias pareadas**: F1, precisión y exhaustividad entre los seis pares de configuraciones, y precisión media del modelo frente al monto, con los mismos remuestreos.
10. **Diez semillas**: cada una entrena, elige sus umbrales en validación y mide en prueba; se informa media y desviación estándar.
11. **Partición temporal**: orden estable por `Time`; primer 70 % desarrollo (80/20 ajuste/validación, también en orden) y último 30 % prueba. Si falta `Time`, se omite y se anota.
12. **Análisis de errores**: configuración híbrida con cualquier alerta, sobre validación; fraudes no detectados y falsas alarmas con monto, puntuación, umbrales, nivel, reglas activadas y las variables que más pesaron.

## Revisión dirigida

1. `evaluar` sin `entrenar` previo, o con un modelo entrenado sobre otros datos o partición → falla diciendo qué paso repetir.
2. Validación sin fraudes → `entrenar` falla con un mensaje claro en lugar de elegir un umbral cualquiera.
3. Una configuración sin alertas en un remuestreo → la precisión queda indefinida en ese remuestreo, se cuenta y el intervalo usa el resto.
4. Datos sin `Time` → la partición temporal queda omitida y anotada, y el resto termina.
5. `todo` con `preparar` fallido → `entrenar` y `evaluar` fallan con su motivo y `todo` sigue terminando con `evidencia`.

---

### Tarea 1: modelo y umbrales

**Archivos:** `config/modelo.yaml`, `src/fraude/modelo.py`, `tests/unitarias/test_modelo.py`.

**Produce:** `entrenar_bosque(X: np.ndarray, params: dict, semilla: int) -> IsolationForest`; `puntuar(modelo, X) -> np.ndarray`; `elegir_umbrales(y: np.ndarray, puntuacion: np.ndarray) -> dict` con `umbral_revision`, `umbral_prioritaria`, `f1_validacion`, `f05_validacion`; `umbral_por_fbeta(y, puntuacion, beta) -> tuple[float, float]`; `guardar_artefacto(carpeta, modelo, meta) -> dict` y `cargar_artefacto(carpeta) -> tuple[IsolationForest, dict]`; `ErrorModelo`.

- [ ] Pruebas: la puntuación es mayor para un punto atípico evidente; misma semilla, misma puntuación; `umbral_revision` coincide con el F1 máximo calculado a mano; `umbral_prioritaria >= umbral_revision` también cuando F0,5 prefiere un corte menor; empate → umbral mayor; validación sin fraudes → `ErrorModelo`; guardar y cargar devuelve las mismas puntuaciones.
- [ ] Implementar y pasar. Commit `feat(modelo): ...`.

### Tarea 2: tabla de decisión en Python

**Archivos:** `src/fraude/decision.py`, `tests/unitarias/test_decision.py`.

**Produce:** `clasificar(reglas: list[dict] | None, modelo: dict | None) -> str` (sección 8.4; `None` = evaluación fallida) y `clasificar_vector(r_alto, r, a, a_alta) -> np.ndarray`.

- [ ] Pruebas: las 16 combinaciones de las cuatro señales dan el nivel de la tabla, y el vector coincide con la versión por caso; señal no evaluable cuenta como no activada; `None` → `error_evaluacion`.
- [ ] Implementar y pasar. Commit.

### Tarea 3: contribución por variable

**Archivos:** `pyproject.toml`, `uv.lock` (`shap==0.54.1`), `src/fraude/contribuciones.py`, `tests/unitarias/test_contribuciones.py`.

**Produce:** `contribuciones(modelo, X, variables: list[str], k: int) -> list[list[dict]]` (cada dict `{"variable", "peso"}`, ordenado de mayor a menor peso); `METODO: str`; `error_aditividad(modelo, X) -> float`.

- [ ] Pruebas: aditividad < 1e-9 con la versión instalada; en un punto desplazado solo en `V3`, `V3` encabeza la lista; `k` limita la longitud.
- [ ] Implementar y pasar. Commit.

### Tarea 4: métricas e incertidumbre

**Archivos:** `src/fraude/metricas.py`, `tests/unitarias/test_metricas.py`.

**Produce:** `binarias(y, alerta, pesos=None) -> dict` (`tp`, `fp`, `fn`, `tn`, `alertas`, `precision`, `exhaustividad`, `f1`); `de_puntuacion(y, puntuacion, k, pesos=None) -> dict` (`precision_media`, `precision_k`, `auc_roc`); `remuestreos(y, n, semilla) -> Iterator[np.ndarray]` (pesos de cada fila, estratificado); `intervalo(valores) -> dict` (`inferior`, `superior`, `indefinidos`).

- [ ] Pruebas: con pesos enteros coincide con scikit-learn sobre las filas repetidas (precisión, exhaustividad, F1, precisión media, AUC); precisión en los *k* primeros a mano; los remuestreos conservan los fraudes y las legítimas de cada clase; sin alertas → precisión `None` e `indefinidos` lo cuenta.
- [ ] Implementar y pasar. Commit.

### Tarea 5: paso `entrenar`

**Archivos:** `src/fraude/entrenar.py`, `src/fraude/cli.py`, `tests/unitarias/test_entrenar.py`, `tests/unitarias/test_cli.py`.

**Produce:** `entrenar(raiz: Path, muestra: bool = False) -> dict` (contenido de `modelo.json`, que escribe en el artefacto y en `resultados/en_curso/`).

- [ ] Pruebas con la muestra: solo usa filas de `ajuste` para ajustar (se comprueba con un modelo espía), umbrales iguales a `elegir_umbrales` sobre validación, `modelo.json` trae parámetros, umbrales, huellas, versiones, tiempo y `reportable: false`; sin `preparar` falla con su mensaje; `todo` ejecuta `entrenar` y `evaluar` y sigue terminando con `evidencia`.
- [ ] Implementar y pasar. Commit.

### Tarea 6: paso `evaluar`, figuras y análisis de errores

**Archivos:** `src/fraude/evaluar.py`, `src/fraude/graficas.py` (estilo común, sacado de `eda.py`), `src/fraude/figuras.py`, `tests/unitarias/test_evaluar.py`.

**Produce:** `evaluar(raiz: Path, muestra: bool = False) -> dict` (contenido de `metricas.json`); escribe `comparativa.md`, `figuras/*.png` y `analisis_errores/`.

- [ ] Pruebas con la muestra: cuatro configuraciones y tres líneas base con matriz, métricas e intervalos; diez semillas; diferencias pareadas; la parte de prueba no aparece en `analisis_errores/` (se comprueba por los índices de fila); sin `Time` la partición temporal queda omitida y anotada; modelo de otros datos → error; `comparativa.md` y `metricas.json` avisan de que la muestra no es reportable.
- [ ] Implementar y pasar. Mirar las figuras. Commit.

### Tarea 7: evidencia, guion y CI

**Archivos:** `src/fraude/evidencia.py`, `fraude`, `tests/punta_a_punta/comprobar_evidencia.py`, `tests/unitarias/test_evidencia.py`.

- [ ] Pruebas: la evidencia copia `modelo.json`, `metricas.json`, `comparativa.md`, `figuras/` y `analisis_errores/`, y el resumen lo dice; la sesión nueva del guion los borra; la comprobación de la CI los exige.
- [ ] Implementar y pasar. Commit.

### Tarea 8: documentos y cierre

ADR 0012, `docs/fugas.md`, `CHANGELOG.md`, `docs/ESTADO.md`, `docs/supuestos.md`, `EJECUTAR.md`, versión 0.3.0. Ensayo N1 con un conjunto inventado del tamaño real para medir tiempos (S5). CI en verde, revisión con subagente, Pull Request.
