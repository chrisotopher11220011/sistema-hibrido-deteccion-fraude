# Estado del proyecto

Documento vivo. Cada chat lo lee al empezar y lo actualiza al cerrar.

- **Última actualización:** 2026-11-17 (UTC), cierre de la fase 6
- **Versión integrada en `main`:** 0.3.0. La 0.4.0 está en el Pull Request #7, la 0.5.0 en el #8 y la 0.6.0 en el #9, los tres **abiertos** con la CI en verde y apilados: el #8 apunta a `fase-4-api-casos` y el #9 a `fase-5-flujos-n8n`. Orden: Christopher integra **#7**, luego **#8** y luego **#9**; GitHub reapunta cada uno a `main` al integrar el anterior.
- **Etiquetas `v0.1.0` a `v0.6.0`:** **pendientes**. El entorno de Claude no puede crear etiquetas; las crea Christopher desde GitHub (*Releases > Draft a new release*): `v0.1.0` sobre el commit `54c0be4`, `v0.2.0` sobre el commit `0a20cd8`, `v0.3.0` sobre el commit `2ff2987`, y `v0.4.0`, `v0.5.0` y `v0.6.0` sobre los commits de integración de los Pull Requests #7, #8 y #9.
- **Fase en curso:** ninguna. La fase 6 está terminada; sigue la fase 7 (LLM local, opcional) o directamente el punto de prueba C.
- **Punto de prueba pendiente:** **C** (Omarchy 4): sistema completo con la página. Incluye lo que comprobaban los puntos A y B.

## Fases

| Fase | Versión | Estado | Pull Request |
|---|---|---|---|
| 1. Cimientos | v0.1.0 | Terminada (N1 y N2). Espera el punto de prueba A | #1 |
| 2. Datos y reglas | v0.2.0 | Terminada (N1 y N2 con la muestra). Los datos reales esperan N3 | #3 |
| 3. Aprendizaje automático | v0.3.0 | Terminada (N1 y N2 con la muestra). Las métricas reales esperan el punto B (N3) | #5 |
| 4. API y casos | v0.4.0 | Terminada (N1 y N2 con la muestra), pendiente de integrar. Sin punto de prueba propio | #7 (abierto) |
| 5. Flujos de n8n | v0.5.0 | Terminada: paridad 124/124 en N2 con la muestra. Sin punto de prueba propio | #8 (abierto, sobre #7) |
| 6. Página de simulación | v0.6.0 | Terminada ([CI](https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/actions/runs/44144074191)): capturas revisadas en N2, axe-core sin violaciones y pruebas en verde con la muestra. Espera el punto C | #9 (abierto, sobre #8) |
| 7. LLM local (opcional) | v0.7.0 | Sin empezar | |
| 8. Mejora con evidencia | v0.8.x | Sin empezar | |
| 9. Cierre | v1.0.0 | Sin empezar | |

## Qué existe hoy

- `api` con `GET /salud` (estado del modelo), `POST /evaluar` (contrato 8.3), `POST /casos`, `GET /casos` y `POST /casos/{id}/revision` (SQLite en `datos/casos/casos.sqlite`). Carga el modelo de `datos/modelo/` o `datos/muestra/modelo/` (`FRAUDE_MODELO`) y lo recarga cuando `entrenar` deja uno nuevo (ADR 0013). Sirve la página en `/` y las rutas `/simulacion/*` (fase 6).
- Página de simulación en `web/` (HTML, CSS y JavaScript sin compilación, sistema de diseño en `web/DISENO.md`): lote por n8n a través de la API, nivel y razones, etiqueta real después del veredicto, contadores y matriz del lote, gráficas en lienzo, bandeja de revisión, transacción manual, historial, temas, modo presentación y teclado. `src/fraude/simulacion.py`: rutas `/simulacion/*` y registro en `resultados/en_curso/simulacion.jsonl` (ADR 0015).
- Contratos como esquemas JSON en `docs/contratos/`, con pruebas en `tests/contrato/`.
- `n8n` 2.47.7 con tres flujos importados y publicados en cada arranque por `n8n/arranque.sh`: `ping` (`GET /webhook/ping`), `evaluacion` (`POST /webhook/transaccion`: validar, `/evaluar` con reintento, «Clasificar nivel», explicación por plantilla, notificación simulada, registrar caso y responder con él) y `revision` (`POST /webhook/revision`). ADR 0014.
- Simulador de flujos para N1 (`tests/n8n/simulador.mjs`, Node.js) y paridad exhaustiva con `decision.clasificar`.
- `tareas` con `todo`, `evidencia`, `preparar`, `entrenar`, `evaluar` y `demostrar` (todos con `--muestra`). `demostrar` envía el lote (`datos/[muestra/]demostracion/lote.json`) por n8n y por Python y deja `flujo.json` con paridad y latencia.
- `entrenar`: Isolation Forest (100 árboles, 256 muestras por árbol) con la parte de ajuste; umbrales por F1 y F0,5 en validación; artefacto en `datos/modelo/modelo.joblib` con `modelo.json`, y copia en `resultados/en_curso/modelo.json`.
- `evaluar`: protocolo completo de la sección 15 en `metricas.json`, `comparativa.md`, `figuras/` (cuatro) y `analisis_errores/` (validación).
- Contribución por variable con SHAP (`src/fraude/contribuciones.py`, ADR 0012) y tabla de decisión en Python (`src/fraude/decision.py`).
- `preparar`: OpenML 1597 (ARFF con MD5 publicada) o CSV de Kaggle a mano en `datos/crudos/creditcard.csv`; conteos, huella SHA-256 del contenido, partición 56/14/30 en `datos/preparados/particion/`, `eda/` de la parte de ajuste, sintéticos en `datos/sinteticos/ubicacion.json` y `datos.json`. Funciona sin `Time`.
- Motor de reglas (`src/fraude/reglas.py`) con la forma del contrato 8.3 y forma de la transacción del 8.2 (`src/fraude/transaccion.py`, con tipos estrictos).
- Evidencia: los archivos «para diagnosticar» de la sección 16, más `datos.json`, `eda/`, `modelo.json`, `metricas.json`, `comparativa.md`, `figuras/`, `analisis_errores/`, `casos.csv`, `revisiones.csv`, `flujo.json`, `simulacion.json`, `OBSERVACIONES.md` y `capturas/`.
- Guion `./fraude` con `todo [--muestra]`, `evidencia`, `abrir`, `estado`, `apagar` y los pasos sueltos.
- CI: estilo, pruebas unitarias y de contrato, `shellcheck` y punta a punta con Compose usando `todo --muestra`, más la API en marcha (`tests/punta_a_punta/comprobar_api.py`), la exportación de casos, los flujos de n8n reales sin modelo, con revisión y con la API detenida (`comprobar_flujos.py`), y la paridad total de `demostrar` en `flujo.json`. Desde la fase 6, la página en Chromium con Playwright (`comprobar_pagina.py`): teclado, etiqueta, estados de error, axe-core, fluidez y capturas (artefacto `capturas-pagina` y hoja de contactos en el registro).

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

## Decisiones tomadas al construir (fase 5)

| Tema | Decisión | Dónde |
|---|---|---|
| Nodos de los flujos | Webhook 2, Set 3.4, If 2.2, Switch 3.2, HTTP Request 4.2 y Respond to Webhook 1.1; sin nodos Code. Verificado en el código de `n8n@2.47.7` | ADR 0014, `docs/planes/fase-5.md` |
| Cómo se prueban los flujos en N1 | Simulador del subconjunto de nodos (Node.js); en la CI, `FRAUDE_EXIGIR_NODE=1` | `tests/n8n/` |
| Validación en n8n | Subconjunto de la de la API, para no romper la paridad | ADR 0014 |
| Reintentos | `/evaluar`: 10 s y 3 intentos, solo ante errores de red; `/casos` y la revisión sin reintento | `n8n/flujos/*.json` |
| Caso no registrado | 502 con el caso calculado (`error_flujo`) | `docs/contratos/` |
| Notificación | Simulada, escrita en el caso. Telegram no se construyó | ADR 0014 |
| Lote de demostración | Parte de prueba (20 fraudes como máximo y 80 no fraudes), 20 sintéticas y 6 inválidas, con semilla | `config/modelo.yaml`, `src/fraude/lote.py` |
| Latencia | Transacciones válidas, desde `tareas` hasta la respuesta del webhook; mediana y p95 con interpolación lineal. `demostrar` falla si una válida termina en `error_evaluacion` (paridad sin cobertura) | `src/fraude/demostrar.py` |

## Decisiones tomadas al construir (fase 6)

| Tema | Decisión | Dónde |
|---|---|---|
| Dirección visual | Mesa de verificación: papel de seguridad, tinta de billete, sello violeta; boleta perforada con sello del nivel | `web/DISENO.md`, `docs/planes/fase-6.md` |
| Tipografía | Atkinson Hyperlegible Next (OFL), incluida en `web/fuentes/` | `web/DISENO.md` |
| Lote que sirve la página | El de la fuente del modelo cargado; sin modelo, según `FRAUDE_MODELO` | ADR 0015 |
| Etiqueta real | La página solo envía `transaccion`; la API rechaza `etiqueta_real` (422) | ADR 0015 |
| Registro de la sesión | `simulacion.jsonl` por la API; `simulacion.json` con la comparación al reunir la evidencia | ADR 0015, `src/fraude/evidencia.py` |
| Herramienta de capturas | Playwright con Chromium en la CI; axe-core 4.14.1 para WCAG | ADR 0015, `.github/workflows/ci.yml` |
| Página en N1 sin Docker | n8n de pruebas con los flujos reales y el simulador | `tests/punta_a_punta/n8n_de_pruebas.py` |
| Reenvío a n8n | En un hilo aparte: evita el interbloqueo con las llamadas de n8n a la API | ADR 0015 |

## Límites del entorno de Claude (comprobados el 2026-11-17, fase 6)

- Llega a GitHub (repositorio y API REST; no GraphQL) y a PyPI.
- Puede subir ramas y abrir Pull Requests (con la API REST: `gh pr create` usa GraphQL y falla). En las fases 4 y 5 no integró: el #8 depende del #7, que integra Christopher. No puede crear etiquetas ni publicaciones.
- No llega a Docker Hub, Kaggle ni OpenML desde la consola. La lectura de páginas web sí llega a la API de OpenML (metadatos), no a los archivos.
- Tiene el cliente de Docker pero no el servicio en marcha: Compose y n8n solo se prueban en N2. n8n 2.47.7 pide Node.js 24 y aquí hay 22; instalar otro Node fue denegado. El simulador de flujos sí corre con Node 22.
- Llega al código de n8n en GitHub (etiqueta `n8n@2.47.7`), que sirve para verificar el formato de los nodos.
- La consola trabaja como `root`: las pruebas del guion deben ejecutarse también con un usuario normal (ver `CLAUDE.md`).
- Hay Google Chrome y Playwright para Python 1.63 en el sistema, y npm llega al registro: la página se prueba en N1 con `n8n_de_pruebas.py`, `uvicorn` y `comprobar_pagina.py --chrome /usr/bin/google-chrome` (axe-core con `npm pack axe-core@4.14.1`).
- Lee los registros de GitHub Actions, pero **no** descarga artefactos (el almacenamiento de artefactos no está permitido): por eso la CI imprime una hoja de contactos de las capturas en base64 (`hoja_capturas.py`).
- No tiene `shellcheck`: lo comprueba la CI.

Cada chat lo vuelve a comprobar al empezar.

## Pendiente de Christopher

- Usuario de GitHub del compañero, para darle acceso al repositorio privado.
- Si quiere Telegram.
- Si quiere una ejecución completa bajo demanda en GitHub Actions con datos reales.

## Notas para el siguiente chat (fase 7 o mejora tras el punto C)

- Antes de empezar: comprobar si Christopher integró los Pull Requests #7, #8 y #9. Si no, crear la rama siguiente desde `fase-6-pagina-simulacion` y apuntar su Pull Request a esa rama.
- La explicación del caso llega en `explicacion` (`texto`, `origen`, `modelo`, `duracion_ms`). La página ya muestra «explicación por modelo de lenguaje» cuando `origen` es `llm`: la fase 7 no necesita tocar la página para eso.
- Para ver la página en N1: preparar y entrenar con la muestra en una raíz temporal (`FRAUDE_RAIZ`), generar el lote (`lote.generar`), arrancar `uvicorn fraude.api:app` con `FRAUDE_URL_N8N` apuntando a `n8n_de_pruebas.py`, y ejecutar `comprobar_pagina.py`.
- Para mirar las capturas de N2: el registro del paso «Hoja de contactos de las capturas» trae tres JPEG en base64 entre `=== HOJA <nombre> INICIO ===` y `FIN`.
- Si llega evidencia del punto C: `simulacion.json` (sesiones, latencias, comparación), `revisiones.csv`, `capturas/` y el SUS de `OBSERVACIONES.md`. Actualizar S8, S25 a S27 y la tabla SUS de `docs/interfaz-evaluacion.md`. Lo de los puntos A y B sigue en pie: `datos.json`, `modelo.json`, `metricas.json` y `flujo.json` (S3, S5, S12, S15–S17, S19, S20, S23, S24). Las cifras de `comparativa.md` serán las primeras reportables: citarlas siempre con su carpeta de evidencia.
- `MONTO_ALTO` puede detectar pocos fraudes: si pasa, se reporta tal cual (sección 10).
