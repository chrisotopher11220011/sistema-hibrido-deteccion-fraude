# Estado del proyecto

Documento vivo. Cada chat lo lee al empezar y lo actualiza al cerrar.

- **Última actualización:** 2026-11-17 (UTC)
- **Versión integrada en `main`:** 0.2.0 (Pull Request #3, commit `0a20cd8`).
- **Etiquetas `v0.1.0` y `v0.2.0`:** **pendientes**. El entorno de Claude no puede crear etiquetas; las crea Christopher desde GitHub (*Releases > Draft a new release*): `v0.1.0` sobre el commit `54c0be4` y `v0.2.0` sobre el commit `0a20cd8`.
- **Fase en curso:** ninguna. La fase 2 está terminada; sigue la fase 3.
- **Punto de prueba pendiente:** **A** (Omarchy 4). Con la versión 0.2.0 además descarga y prepara los datos reales, así que adelanta parte del punto B. Puede saltarse.

## Fases

| Fase | Versión | Estado | Pull Request |
|---|---|---|---|
| 1. Cimientos | v0.1.0 | Terminada (N1 y N2). Espera el punto de prueba A | #1 |
| 2. Datos y reglas | v0.2.0 | Terminada (N1 y N2 con la muestra). Los datos reales esperan N3 | #3 |
| 3. Aprendizaje automático | v0.3.0 | Sin empezar | |
| 4. API y casos | v0.4.0 | Sin empezar | |
| 5. Flujos de n8n | v0.5.0 | Sin empezar | |
| 6. Página de simulación | v0.6.0 | Sin empezar | |
| 7. LLM local (opcional) | v0.7.0 | Sin empezar | |
| 8. Mejora con evidencia | v0.8.x | Sin empezar | |
| 9. Cierre | v1.0.0 | Sin empezar | |

## Qué existe hoy

- `api` con `GET /salud`. Nada más de la sección 8.6.
- `n8n` 2.47.7 con el flujo `ping` (`GET /webhook/ping`), importado y publicado en cada arranque por `n8n/arranque.sh`.
- `tareas` con `todo`, `evidencia` y `preparar` (con `--muestra` en `preparar` y `todo`). `entrenar`, `evaluar` y `demostrar` avisan de su fase: dentro de `todo` no cuentan como fallo; llamados sueltos devuelven código 2.
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

## Notas para el siguiente chat (fase 3)

- Los datos se cargan con `cargar_preparados(raiz, muestra)`; la parte de cada fila viene como texto (`ajuste`, `validacion`, `prueba`). Entrenar solo con `ajuste`, elegir umbrales con `validacion` y usar `prueba` solo para métricas agregadas (ADR 0003).
- `config/modelo.yaml` ya tiene `semilla` y `variables`; añadir ahí los parámetros de Isolation Forest.
- La muestra tiene 60 fraudes (18 en prueba): basta para probar el código, no para conclusiones. Si se cambia su configuración, `preparar --muestra` recrea la partición sin problema.
- Al añadir `entrenar` y `evaluar`, sacarlos de `PASOS_FUTUROS` en `src/fraude/cli.py` y conservar la regla: `todo` termina siempre con `evidencia`.
- `datos.json` informa `tiene_time`: la partición temporal secundaria (sección 15) debe omitirse y anotarse cuando sea `false`.
- Si llega evidencia de N3, revisar primero `datos.json` (conteos, `md5_coincide`, `tiene_time`, `duracion_s`) y actualizar S3, S12, S15, S16 y S17 en `docs/supuestos.md`. Si la huella del contenido queda fijada, copiarla a `huellas_sha256_conocidas` en `config/modelo.yaml`.
