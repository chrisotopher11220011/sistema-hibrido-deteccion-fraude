# Estado del proyecto

Documento vivo. Cada chat lo lee al empezar y lo actualiza al cerrar.

- **Última actualización:** 2026-11-17 (UTC)
- **Versión integrada en `main`:** 0.4.0 (Pull Request #7).
- **Etiquetas `v0.1.0`, `v0.2.0`, `v0.3.0` y `v0.4.0`:** **pendientes**. El entorno de Claude no puede crear etiquetas; las crea Christopher desde GitHub (*Releases > Draft a new release*): `v0.1.0` sobre el commit `54c0be4`, `v0.2.0` sobre el commit `0a20cd8` `v0.3.0` sobre el commit `2ff2987` y `v0.4.0` sobre el commit de integración del Pull Request #7.
- **Fase en curso:** ninguna. La fase 4 está terminada; sigue la fase 5.
- **Punto de prueba pendiente:** **B** (Omarchy 4): datos reales, entrenamiento y primeras métricas. Incluye lo que comprobaba el punto A.

## Fases

| Fase | Versión | Estado | Pull Request |
|---|---|---|---|
| 1. Cimientos | v0.1.0 | Terminada (N1 y N2). Espera el punto de prueba A | #1 |
| 2. Datos y reglas | v0.2.0 | Terminada (N1 y N2 con la muestra). Los datos reales esperan N3 | #3 |
| 3. Aprendizaje automático | v0.3.0 | Terminada (N1 y N2 con la muestra). Las métricas reales esperan el punto B (N3) | #5 |
| 4. API y casos | v0.4.0 | Terminada (N1 y N2 con la muestra). Sin punto de prueba propio | #7 |
| 5. Flujos de n8n | v0.5.0 | Sin empezar | |
| 6. Página de simulación | v0.6.0 | Sin empezar | |
| 7. LLM local (opcional) | v0.7.0 | Sin empezar | |
| 8. Mejora con evidencia | v0.8.x | Sin empezar | |
| 9. Cierre | v1.0.0 | Sin empezar | |

## Qué existe hoy

- `api` con `GET /salud` (estado del modelo), `POST /evaluar` (contrato 8.3), `POST /casos`, `GET /casos` y `POST /casos/{id}/revision` (SQLite en `datos/casos/casos.sqlite`). Carga el modelo de `datos/modelo/` o `datos/muestra/modelo/` (`FRAUDE_MODELO`) y lo recarga cuando `entrenar` deja uno nuevo (ADR 0013). Faltan las rutas `/`, `/simulacion/*` (fases 5 y 6).
- Contratos como esquemas JSON en `docs/contratos/`, con pruebas en `tests/contrato/`.
- `n8n` 2.47.7 con el flujo `ping` (`GET /webhook/ping`), importado y publicado en cada arranque por `n8n/arranque.sh`.
- `tareas` con `todo`, `evidencia`, `preparar`, `entrenar` y `evaluar` (todos con `--muestra`). `demostrar` avisa de su fase: dentro de `todo` no cuenta como fallo; llamado suelto devuelve código 2.
- `entrenar`: Isolation Forest (100 árboles, 256 muestras por árbol) con la parte de ajuste; umbrales por F1 y F0,5 en validación; artefacto en `datos/modelo/modelo.joblib` con `modelo.json`, y copia en `resultados/en_curso/modelo.json`.
- `evaluar`: protocolo completo de la sección 15 en `metricas.json`, `comparativa.md`, `figuras/` (cuatro) y `analisis_errores/` (validación).
- Contribución por variable con SHAP (`src/fraude/contribuciones.py`, ADR 0012) y tabla de decisión en Python (`src/fraude/decision.py`).
- `preparar`: OpenML 1597 (ARFF con MD5 publicada) o CSV de Kaggle a mano en `datos/crudos/creditcard.csv`; conteos, huella SHA-256 del contenido, partición 56/14/30 en `datos/preparados/particion/`, `eda/` de la parte de ajuste, sintéticos en `datos/sinteticos/ubicacion.json` y `datos.json`. Funciona sin `Time`.
- Motor de reglas (`src/fraude/reglas.py`) con la forma del contrato 8.3 y forma de la transacción del 8.2 (`src/fraude/transaccion.py`, con tipos estrictos).
- Evidencia: los archivos «para diagnosticar» de la sección 16, más `datos.json`, `eda/`, `modelo.json`, `metricas.json`, `comparativa.md`, `figuras/`, `analisis_errores/`, `casos.csv`, `revisiones.csv`, `OBSERVACIONES.md` y `capturas/`.
- Guion `./fraude` con `todo [--muestra]`, `evidencia`, `abrir`, `estado`, `apagar` y los pasos sueltos.
- CI: estilo, pruebas unitarias y de contrato, `shellcheck` y punta a punta con Compose usando `todo --muestra`, más la API en marcha (`tests/punta_a_punta/comprobar_api.py`) y la exportación de casos.

## Decisiones tomadas al construir (fase 1)

Las que la especificación dejaba «para quien construya»:

| Tema | Decisión | Dónde |
|---|---|---|
| Versión de n8n | `n8nio/n8n:2.47.7`, la estable al 2026-11-16. No se usa la 3.0, en beta | ADR 0004 |
| Importación y activación de flujos | `n8n/arranque.sh`: importar, publicar por `id` fijo y arrancar | ADR 0004 |
| Archivos a nombre del usuario | Contenedores con el UID y GID del usuario; `sudo` solo delante de `docker` | ADR 0010 |
| Imagen de Python | `python:3.12.12-slim-bookworm`, una sola para `api` y `tareas` | `Dockerfile` |
| Formato de la carpeta de evidencia | `resultados/<AAAAMMDDTHHMMSSZ>_<commit>/`; si ya existe, sufijo `-2`, `-3`… | `src/fraude/evidencia.py` |

## Decisiones tomadas al construir (fase 2)

| Tema | Decisión | Dónde |
|---|---|---|
| Descarga | ARFF directo con la biblioteca estándar, dos direcciones de OpenML y su MD5 publicada; sin `fetch_openml`, que omite `Time` | `src/fraude/datos.py`, `config/modelo.yaml` |
| Parámetros de datos | En `config/modelo.yaml` (`datos`, `particion`, `muestra`, `sinteticos`), sin archivos de configuración nuevos | `config/modelo.yaml` |
| Huella | SHA-256 del contenido sin `Time`, igual para ARFF y CSV; la fija la primera ejecución real en `datos/crudos/huella.json`. La muestra no fija huella | `src/fraude/preparar.py` |
| Partición repetida | Se recalcula y se compara con la guardada; si cambió la configuración se recrea y queda anotado | `src/fraude/preparar.py` |
| Carga para la fase 3 | `preparar.cargar_preparados(raiz, muestra)` devuelve los datos y la parte de cada fila, verificando la huella | `src/fraude/preparar.py` |
| Datos en la CI | La muestra; la descarga real queda para N3 | `.github/workflows/ci.yml` |

## Decisiones tomadas al construir (fase 3)

| Tema | Decisión | Dónde |
|---|---|---|
| Método de contribución por variable | SHAP para árboles 0.54.1, verificado en su código y con prueba de aditividad. DIFFI no tiene paquete | ADR 0012 |
| Parámetros iniciales del modelo | Los del artículo original y de scikit-learn, sin transformar variables | `config/modelo.yaml` |
| Puntuación | `-score_samples`, en (0, 1] | `src/fraude/modelo.py` |
| Empates de umbral | Se toma el mayor (menos alertas) | ADR 0008, `modelo.py` |
| Línea base al azar | Misma cantidad de alertas que el híbrido con cualquier alerta | `src/fraude/evaluar.py` |
| Línea base por monto | Corte por F1 en validación | `evaluar.py` |
| Cupo `k` | 100 (supuesto S20) | `config/modelo.yaml` |
| Intervalos | Percentiles del *bootstrap* estratificado, con pesos por fila | `src/fraude/metricas.py` |
| Partición temporal | Orden estable por `Time`, mismas proporciones | `evaluar.py` |
| Dónde vive el modelo | `datos/modelo/` (real) y `datos/muestra/modelo/` (muestra). La API lo cargará de ahí en la fase 4 | `src/fraude/entrenar.py` |

## Decisiones tomadas al construir (fase 4)

| Tema | Decisión | Dónde |
|---|---|---|
| Cómo comparte `tareas` el modelo con `api` y cómo lo recarga | Volumen `datos/`; la API compara la firma de los archivos en cada consulta y recarga | ADR 0013, `src/fraude/servicio_modelo.py` |
| Qué modelo usa la API | `FRAUDE_MODELO=auto` (real si existe, si no la muestra), `real` o `muestra` | ADR 0013, `compose.yaml` |
| Evaluación imposible | 503 `modelo_no_disponible` si trae `variables` y no hay modelo; 422 `entrada_invalida`; cuerpo de error común | ADR 0013, `src/fraude/errores.py` |
| Cuerpo de `POST /casos` y `GET /casos` | Esquemas `caso_nuevo` y `lista_casos` | `docs/contratos/` |
| Contribuciones en `/evaluar` | Solo con `anomalia`; explicador SHAP reutilizado por modelo cargado | ADR 0013 |

## Límites del entorno de Claude (comprobados el 2026-11-17, fase 4)

- Llega a GitHub (repositorio y API REST; no GraphQL) y a PyPI.
- Puede subir ramas, abrir Pull Requests e integrarlos; **no** puede crear etiquetas ni publicaciones.
- No llega a Docker Hub, Kaggle ni OpenML desde la consola. La lectura de páginas web sí llega a la API de OpenML (metadatos), no a los archivos.
- Tiene el cliente de Docker pero no el servicio en marcha: Compose y n8n solo se prueban en N2.
- La consola trabaja como `root`: las pruebas del guion deben ejecutarse también con un usuario normal (ver `CLAUDE.md`).

Cada chat lo vuelve a comprobar al empezar.

## Pendiente de Christopher

- Usuario de GitHub del compañero, para darle acceso al repositorio privado.
- Si quiere Telegram.
- Si quiere una ejecución completa bajo demanda en GitHub Actions con datos reales.

## Notas para el siguiente chat (fase 5)

- n8n llama a `POST http://api:8000/evaluar` con la transacción tal cual (esquema `docs/contratos/transaccion.schema.json`). **Si la respuesta no es 200, o no llega, el caso es `error_evaluacion`** y la razón sale de `error.mensaje` (ADR 0013). Nunca `sin_alerta`.
- El nodo «Clasificar nivel» aplica la tabla 8.4 sobre `reglas` y `modelo` de la respuesta 200. La copia en Python es `decision.clasificar(reglas, modelo)`; con `reglas=None` da `error_evaluacion`. La paridad compara ambos caminos.
- Registrar con `POST http://api:8000/casos` (esquema `caso_nuevo`): sin `id_caso`, `estado`, `decision_final` ni `revision`; `senales` es la respuesta de `/evaluar` tal cual. Toda alerta lleva al menos una razón. En `error_evaluacion` pueden ir en `null` `id_transaccion`, `origen`, `monto` y `senales`. Responde 201 con el caso completo, que es lo que el webhook debe devolver.
- Revisión humana: `POST /casos/{id}/revision` con `decision`, `revisor` y `comentario`; 404 si no existe, 409 si no está pendiente.
- `versiones.flujo` del caso queda para la versión del flujo de n8n.
- Con la API en marcha, `/salud` dice si el modelo está cargado; en la CI es el de la muestra.
- Pendiente de la fase 3 que sigue en pie: si llega evidencia del punto B, revisar `datos.json`, `modelo.json` y `metricas.json` y actualizar S3, S5, S12, S15–S17, S19 y S20. Las cifras de `comparativa.md` serán las primeras reportables: citarlas con su carpeta de evidencia.
- `MONTO_ALTO` puede detectar pocos fraudes: si pasa, se reporta tal cual (sección 10).
