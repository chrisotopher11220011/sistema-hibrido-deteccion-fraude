# Estado del proyecto

Documento vivo. Cada chat lo lee al empezar y lo actualiza al cerrar.

- **Última actualización:** 2026-11-17 (UTC)
- **Versión integrada en `main`:** 0.3.0 (Pull Request #5).
- **Etiquetas `v0.1.0`, `v0.2.0` y `v0.3.0`:** **pendientes**. El entorno de Claude no puede crear etiquetas; las crea Christopher desde GitHub (*Releases > Draft a new release*): `v0.1.0` sobre el commit `54c0be4`, `v0.2.0` sobre el commit `0a20cd8` y `v0.3.0` sobre el commit de integración del Pull Request #5.
- **Fase en curso:** ninguna. La fase 3 está terminada; sigue la fase 4.
- **Punto de prueba pendiente:** **B** (Omarchy 4): datos reales, entrenamiento y primeras métricas. Incluye lo que comprobaba el punto A.

## Fases

| Fase | Versión | Estado | Pull Request |
|---|---|---|---|
| 1. Cimientos | v0.1.0 | Terminada (N1 y N2). Espera el punto de prueba A | #1 |
| 2. Datos y reglas | v0.2.0 | Terminada (N1 y N2 con la muestra). Los datos reales esperan N3 | #3 |
| 3. Aprendizaje automático | v0.3.0 | Terminada (N1 y N2 con la muestra). Las métricas reales esperan el punto B (N3) | #5 |
| 4. API y casos | v0.4.0 | Sin empezar | |
| 5. Flujos de n8n | v0.5.0 | Sin empezar | |
| 6. Página de simulación | v0.6.0 | Sin empezar | |
| 7. LLM local (opcional) | v0.7.0 | Sin empezar | |
| 8. Mejora con evidencia | v0.8.x | Sin empezar | |
| 9. Cierre | v1.0.0 | Sin empezar | |

## Qué existe hoy

- `api` con `GET /salud`. Nada más de la sección 8.6: la carga del modelo en la API llega en la fase 4.
- `n8n` 2.47.7 con el flujo `ping` (`GET /webhook/ping`), importado y publicado en cada arranque por `n8n/arranque.sh`.
- `tareas` con `todo`, `evidencia`, `preparar`, `entrenar` y `evaluar` (todos con `--muestra`). `demostrar` avisa de su fase: dentro de `todo` no cuenta como fallo; llamado suelto devuelve código 2.
- `entrenar`: Isolation Forest (100 árboles, 256 muestras por árbol) con la parte de ajuste; umbrales por F1 y F0,5 en validación; artefacto en `datos/modelo/modelo.joblib` con `modelo.json`, y copia en `resultados/en_curso/modelo.json`.
- `evaluar`: protocolo completo de la sección 15 en `metricas.json`, `comparativa.md`, `figuras/` (cuatro) y `analisis_errores/` (validación).
- Contribución por variable con SHAP (`src/fraude/contribuciones.py`, ADR 0012) y tabla de decisión en Python (`src/fraude/decision.py`).
- `preparar`: OpenML 1597 (ARFF con MD5 publicada) o CSV de Kaggle a mano en `datos/crudos/creditcard.csv`; conteos, huella SHA-256 del contenido, partición 56/14/30 en `datos/preparados/particion/`, `eda/` de la parte de ajuste, sintéticos en `datos/sinteticos/ubicacion.json` y `datos.json`. Funciona sin `Time`.
- Motor de reglas (`src/fraude/reglas.py`) con la forma del contrato 8.3 y forma de la transacción del 8.2 (`src/fraude/transaccion.py`). Aún no hay ruta `/evaluar`: llega en la fase 4.
- Evidencia: los archivos «para diagnosticar» de la sección 16, más `datos.json`, `eda/`, `OBSERVACIONES.md` y `capturas/`.
- Guion `./fraude` con `todo [--muestra]`, `evidencia`, `abrir`, `estado`, `apagar` y los pasos sueltos.
- CI: estilo, pruebas unitarias, `shellcheck` y punta a punta con Compose usando `todo --muestra`.

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

## Límites del entorno de Claude (comprobados el 2026-11-17)

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

## Notas para el siguiente chat (fase 4)

- El modelo se carga con `modelo.cargar_artefacto(entrenar.carpeta_modelo(raiz, muestra))`, que devuelve el `IsolationForest` y `modelo.json` (umbrales en `umbrales`, versión en `version`). Comprobar las huellas como hace `evaluar._comprobar_modelo`.
- Para `/evaluar`: `modelo.puntuar` da la puntuación; `anomalia = puntuacion >= umbral_revision` y `anomalia_alta = puntuacion >= umbral_prioritaria`. `contribuciones.contribuciones(bosque, X, variables, k)` da la lista de la sección 8.3 (`{"variable", "peso"}`).
- La tabla de decisión en Python es `decision.clasificar(reglas, modelo)`; la fase 5 la usa para la paridad con n8n.
- Las variables del modelo son `V1`–`V28` y `Amount` (`config/modelo.yaml`): `/evaluar` debe construir `Amount` desde `monto`.
- Si llega evidencia del punto B, revisar primero `datos.json`, luego `modelo.json` (`datos.fraudes_validacion`, tiempos) y `metricas.json` (`estado`, `duracion_s`, `temporal.estado`). Actualizar S3, S5, S12, S15–S17, S19 y S20. Las cifras de `comparativa.md` serán las primeras reportables: citarlas siempre con la carpeta de evidencia de la que salen.
- `MONTO_ALTO` puede detectar pocos fraudes: si pasa, se reporta tal cual (sección 10).
