# ADR 0005: Registro de casos en la API con SQLite

- **Estado:** Aceptada
- **Fecha:** 2026-11-16
- **Fase en la que se aplica:** 4

## Contexto

Cada transacción evaluada produce un caso que debe poder consultarse, revisarse y exportarse a la evidencia. n8n guarda su propio historial de ejecuciones, pero no es cómodo de consultar ni de exportar, y la página habla solo con la API.

## Decisión

La API guarda los casos en una base SQLite dentro de `datos/`, con las rutas `POST /casos`, `GET /casos` y `POST /casos/{id}/revision`. n8n registra cada caso llamando a la API.

## Consecuencias

- Un solo archivo, sin servicio adicional, fácil de exportar a `casos.csv` y `revisiones.csv`.
- Si la API entera se cae, el caso no puede guardarse y solo queda el historial de n8n. Se acepta para un prototipo y se documenta como limitación.
- SQLite admite un solo escritor a la vez: suficiente para una simulación local.
