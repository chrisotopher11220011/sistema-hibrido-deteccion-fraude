# Estado del proyecto

Documento vivo. Cada chat lo lee al empezar y lo actualiza al cerrar.

- **Última actualización:** 2026-11-17 (UTC)
- **Versión publicada:** v0.1.0
- **Fase en curso:** ninguna. La fase 1 está terminada; sigue la fase 2.
- **Punto de prueba pendiente:** **A** (Omarchy 4, cinco minutos). Puede saltarse, pero es barato.

## Fases

| Fase | Versión | Estado | Pull Request |
|---|---|---|---|
| 1. Cimientos | v0.1.0 | Terminada (N1 y N2). Espera el punto de prueba A | #1 |
| 2. Datos y reglas | v0.2.0 | Sin empezar | |
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
- `tareas` con `todo` y `evidencia`. `preparar`, `entrenar`, `evaluar` y `demostrar` avisan de su fase: dentro de `todo` no cuentan como fallo; llamados sueltos devuelven código 2.
- Evidencia mínima (los archivos «para diagnosticar» de la sección 16, más `OBSERVACIONES.md` y `capturas/`).
- Guion `./fraude` con `todo`, `evidencia`, `abrir`, `estado`, `apagar` y los pasos sueltos.
- CI: estilo, pruebas unitarias, `shellcheck` y punta a punta con Compose.

## Decisiones tomadas al construir (fase 1)

Las que la especificación dejaba «para quien construya»:

| Tema | Decisión | Dónde |
|---|---|---|
| Versión de n8n | `n8nio/n8n:2.47.7`, la estable al 2026-11-16. No se usa la 3.0, en beta | ADR 0004 |
| Importación y activación de flujos | `n8n/arranque.sh`: importar, publicar por `id` fijo y arrancar | ADR 0004 |
| Archivos a nombre del usuario | Contenedores con el UID y GID del usuario; `sudo` solo delante de `docker` | ADR 0010 |
| Imagen de Python | `python:3.12.12-slim-bookworm`, una sola para `api` y `tareas` | `Dockerfile` |
| Formato de la carpeta de evidencia | `resultados/<AAAAMMDDTHHMMSSZ>_<commit>/`; si ya existe, sufijo `-2`, `-3`… | `src/fraude/evidencia.py` |

## Límites del entorno de Claude (comprobados el 2026-11-16)

- Llega a GitHub (repositorio y API REST; no GraphQL) y a PyPI.
- No llega a Docker Hub, Kaggle ni OpenML desde la consola. La búsqueda y lectura de páginas web sí funcionan.
- Tiene el cliente de Docker pero no el servicio en marcha: Compose y n8n solo se prueban en N2.
- La consola trabaja como `root`: las pruebas del guion deben ejecutarse también con un usuario normal (ver `CLAUDE.md`).

Cada chat lo vuelve a comprobar al empezar.

## Pendiente de Christopher

- Usuario de GitHub del compañero, para darle acceso al repositorio privado.
- Si quiere Telegram.
- Si quiere una ejecución completa bajo demanda en GitHub Actions con datos reales.

## Notas para el siguiente chat (fase 2)

- `config/reglas.yaml` ya fija los umbrales de las dos reglas; el motor aún no existe.
- La sesión de trabajo del guion vive en `resultados/en_curso/` (ignorada por Git). Lo que `tareas` necesite del anfitrión debe pasar por ahí.
- Al añadir un paso real, sustituir su entrada en `PASOS_FUTUROS` de `src/fraude/cli.py` y conservar la regla: `todo` termina siempre con `evidencia`.
- Si llega evidencia del punto de prueba A, revisar primero `anfitrion.json` (versión de Omarchy detectada y modo de Docker) y actualizar `docs/supuestos.md`.
