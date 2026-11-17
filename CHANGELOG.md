# Registro de cambios

Formato de [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y versiones [SemVer](https://semver.org/lang/es/) `0.y.z` hasta la ponencia.

Cada entrada indica su nivel de verificación: N1 (entorno de desarrollo), N2 (GitHub Actions) o N3 (computador de ejecución).

## [Sin publicar]

## [0.5.0] - 2026-11-17

Fase 5, flujos de n8n. Lo comprobado en la CI usa la muestra para pruebas: confirma que los flujos funcionan y que n8n y Python clasifican igual, no mide la detección de fraude.

### Añadido

- Flujo `evaluacion.json` (`POST /webhook/transaccion`): validar entrada, consultar `/evaluar` con tiempo límite de 10 s y 3 intentos ante errores de red, clasificar nivel con la tabla 8.4 en el Switch «Clasificar nivel», razones y explicación por plantilla, notificación simulada, registrar el caso y responder con él. Una entrada inválida o una evaluación fallida terminan en `error_evaluacion`, pendientes de revisión (N1 con simulador; N2 con n8n 2.47.7).
- Flujo `revision.json` (`POST /webhook/revision`): guarda la decisión con `POST /casos/{id}/revision` y devuelve la respuesta de la API; 422 sin llamarla si `id_caso` no tiene la forma esperada (N1; N2).
- Si la API no guarda el caso, el webhook responde 502 con el caso calculado (`docs/contratos/error_flujo.schema.json`) (N1; N2 con la API detenida).
- Simulador de flujos para N1 (`tests/n8n/simulador.mjs`) con la semántica de n8n 2.47.7 comprobada en su código, y prueba de paridad exhaustiva con `decision.clasificar` (N1; N2 en el trabajo de pruebas).
- Lote de demostración con semilla (`datos/[muestra/]demostracion/lote.json`): fraudes y no fraudes de la parte de prueba, sintéticas de ubicación y entradas inválidas fijas; la etiqueta real va aparte de la transacción (N1).
- Paso `demostrar`: lote por n8n y por Python, paridad exigida, coherencia nivel-estado, ninguna transacción válida en `error_evaluacion` (si no, la paridad no probaría la tabla), latencia mediana y percentil 95 de las transacciones válidas, todo en `flujo.json`; `todo` lo incluye y la evidencia lo copia (N1; N2: paridad 124/124 con la muestra, [ejecución](https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/actions/runs/44127587093)).
- CI: flujos reales sin modelo (503 → `error_evaluacion`), entrada inválida, revisión (200, 409, 404, 422) y API detenida (502); `flujo.json` con paridad total.
- ADR 0014: flujos sin nodos Code, simulador en N1 y respuestas de los webhooks. Un cuerpo que no es JSON válido lo rechaza n8n (422) antes del flujo y no deja caso: documentado y comprobado en la CI.
- Revisión de código con subagente: tres hallazgos corregidos con prueba (paridad trivial si todo falla, latencia contando entradas que no llaman a la API, JSON mal formado sin documentar).

### Cambiado

- `todo` ejecuta `demostrar` en lugar de anunciarlo. Sin n8n, `demostrar` falla, lo dice en `flujo.json` y los demás pasos siguen.
- `config/modelo.yaml` añade la sección `demostracion`.

## [0.4.0] - 2026-11-17

Fase 4, API y casos. Lo comprobado en la CI usa la muestra para pruebas: confirma que la API funciona y cumple los contratos, no mide la detección de fraude.

### Añadido

- `POST /evaluar` con el contrato 8.3: reglas, puntuación de Isolation Forest frente a los umbrales de `modelo.json`, `anomalia` y `anomalia_alta`, y las variables que más pesaron cuando hay anomalía (N1; N2 con la muestra).
- La API carga el modelo que deja `entrenar` y lo recarga cuando cambia, sin reiniciarse; `FRAUDE_MODELO` elige `auto`, `real` o `muestra`. `/salud` informa si hay modelo, cuál y por qué no (ADR 0013) (N1; N2 con la muestra).
- Respuesta de error común a todas las rutas. Una entrada inválida responde 422 y una transacción con variables sin modelo cargado responde 503, para que n8n marque `error_evaluacion` (ADR 0013) (N1; N2).
- Registro de casos en SQLite (`datos/casos/casos.sqlite`): `POST /casos`, `GET /casos` y `POST /casos/{id}/revision`. Los casos `sin_alerta` se cierran solos; los demás quedan pendientes hasta una única revisión (ADR 0005 y 0013) (N1; N2).
- Esquemas JSON de los contratos en `docs/contratos/`, con pruebas de contrato sobre los ejemplos de `docs/spec.md` y sobre las respuestas reales de la API (`tests/contrato/`) (N1; N2).
- La evidencia trae `casos.csv` y `revisiones.csv` (N1; N2).
- ADR 0013: carga del modelo en la API, respuestas de error y forma de los casos.

### Cambiado

- `GET /salud` informa el estado real del modelo en lugar de «aún no existe».
- `contribuciones.Explicador` permite reutilizar el explicador SHAP de un modelo cargado.
- Dependencia de desarrollo nueva: `jsonschema`.

### Corregido

- Hallazgos de la revisión de código, antes de integrar: la transacción y el caso ya no convierten booleanos ni textos en números (`"monto": true` daba 200 y podía acabar en `sin_alerta`); los NaN e infinitos dentro de las señales de un caso se rechazan en lugar de guardarse como `null`; las rutas y métodos inexistentes responden con el cuerpo de error (`ruta_no_disponible`); la API comprueba y carga el modelo desde una sola lectura del archivo (N1; N2).

## [0.3.0] - 2026-11-17

Fase 3, aprendizaje automático. Todo lo comprobado aquí usa la muestra para pruebas: confirma que el procedimiento funciona, no mide la detección de fraude. Las cifras reales salen solo de N3 (punto de prueba B).

### Añadido

- Paso `entrenar` (`./fraude entrenar`, y dentro de `todo`): Isolation Forest con la parte de ajuste y sin etiquetas; `umbral_revision` por F1 y `umbral_prioritaria` por F0,5 en validación; artefacto con huella en `datos/modelo/` y `modelo.json` con parámetros, umbrales, huellas de datos y partición, versiones y tiempos (N1; N2 con la muestra).
- Paso `evaluar`: cuatro configuraciones y tres líneas base sobre la parte de prueba, con matriz de confusión, precisión, exhaustividad y F1; precisión media, precisión en los 100 primeros y AUC ROC complementaria; intervalos del 95 % por *bootstrap* estratificado con 1.000 remuestreos; diferencias pareadas; diez semillas; partición temporal secundaria (omitida y anotada si falta `Time`) (N1; N2 con la muestra).
- `metricas.json`, `comparativa.md`, cuatro figuras siguiendo la skill `dataviz` y `analisis_errores/` de la parte de validación con las variables que más pesaron (N1; N2 con la muestra).
- Contribución por variable con SHAP para árboles, con prueba de aditividad (ADR 0012) (N1; N2).
- Copia en Python de la tabla de decisión de la sección 8.4 (N1).
- `docs/fugas.md`: fuentes de fuga habituales y por qué no aplican.
- La evidencia copia `modelo.json`, `metricas.json`, `comparativa.md`, `figuras/` y `analisis_errores/`, y el resumen dice si son de la muestra (N1; N2).

### Cambiado

- Dependencia nueva: `shap` 0.54.1.
- `config/modelo.yaml` añade `isolation_forest`, `contribuciones` y `evaluacion`.
- `entrenar` y `evaluar` dejan de avisar de su fase; `demostrar` sigue llegando en la fase 5.
- Una sesión nueva de `./fraude todo` no arrastra los archivos de modelo y evaluación de la anterior.
- El estilo común de las figuras pasa a `src/fraude/graficas.py`.

## [0.2.0] - 2026-11-17

Fase 2, datos y reglas. Sin modelo ni métricas todavía: todo lo comprobado aquí usa la muestra para pruebas o datos sintéticos, que no representan el fraude real.

### Añadido

- Paso `preparar` (`./fraude preparar`, y dentro de `todo`): descarga el ARFF de OpenML 1597 con su suma MD5 publicada, o usa el CSV de Kaggle dejado a mano; comprueba filas, fraudes y columnas; fija y verifica la huella SHA-256 del contenido; guarda la partición estratificada 56/14/30 antes de cualquier ajuste; deja `datos.json` (N1; N2 con la muestra; los datos reales esperan N3).
- `preparar` funciona sin la columna `Time`: lo anota y sigue (N1).
- Análisis exploratorio de la parte de ajuste en `eda/`: resumen y tres figuras (N1; N2 con la muestra).
- Motor de reglas deterministas `MONTO_ALTO` y `MONTO_ALTO_UBICACION_INUSUAL`, con razón en texto y «no evaluable» cuando faltan datos; la de ubicación solo se aplica a datos sintéticos (N1).
- Generador sintético de ubicación en `datos/sinteticos/`, separado de los originales, con comprobación funcional de la regla y sin métricas de desempeño (N1; N2).
- Muestra para pruebas y opción `--muestra` en `preparar`, `todo` y `./fraude todo` (N1; N2).
- Forma de la transacción del contrato 8.2 validada con Pydantic (N1).
- La evidencia incluye `datos.json`, `eda/` y las versiones de las bibliotecas de datos (N1; N2).

### Cambiado

- `config/reglas.yaml` pasa a la versión 0.2.0. `config/modelo.yaml` guarda también los parámetros de datos, partición, muestra y sintéticos.
- La CI ejecuta `todo --muestra` y comprueba `datos.json`, `eda/` y los datos sintéticos.
- Una sesión nueva de `./fraude todo` no arrastra `datos.json` ni `eda/` de la anterior.

## [0.1.0] - 2026-11-17

Fase 1, cimientos. Sin datos, reglas, modelo ni página todavía: esta versión solo comprueba que el sistema arranca.

### Añadido

- Estructura del repositorio, `CLAUDE.md`, `README.md`, `EJECUTAR.md`, `docs/ESTADO.md`, `docs/supuestos.md`, `docs/architecture.md` y los ADR 0001 a 0011.
- API con `GET /salud` (N1 y N2).
- n8n fijado en la versión 2.47.7, con el flujo `ping` importado y publicado al arrancar; responde en `GET /webhook/ping` (N2).
- Línea de comandos `tareas` con `todo` y `evidencia`. Los pasos `preparar`, `entrenar`, `evaluar` y `demostrar` existen pero avisan de la fase en que llegan (N1 y N2).
- Evidencia mínima: `RESUMEN.md`, `anfitrion.json`, `entorno.json`, `version.json`, `errores.json`, `registros/`, `OBSERVACIONES.md`, `capturas/` y el `.zip` (N1 y N2).
- Guion `./fraude` para Omarchy 4: detecta si Docker pide `sudo`, deja los archivos a nombre del usuario, recoge los datos del sistema y guarda los registros si algo falla (N1 con Docker simulado; N2 sin `sudo` y con `sudo ./fraude`; el caso real de Omarchy espera N3).
- Integración continua en GitHub Actions: estilo, pruebas unitarias, `shellcheck`, construcción de imágenes y flujo `ping` de punta a punta.
- Archivos de configuración `config/reglas.yaml`, `config/modelo.yaml` y `config/decision.yaml`.

[Sin publicar]: https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/compare/main...HEAD
[0.4.0]: https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/pull/7
[0.5.0]: https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/pull/8
[0.3.0]: https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/pull/5
[0.2.0]: https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/pull/3
[0.1.0]: https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/pull/1
