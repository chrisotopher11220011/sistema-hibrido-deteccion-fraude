# Instrucciones para Claude en este repositorio

Prototipo académico: detección híbrida de fraude con reglas, Isolation Forest y n8n.

## Antes de tocar nada

1. Lee `docs/spec.md` (manda sobre todo lo demás), `docs/ESTADO.md` y el plan de la fase en `docs/planes/`.
2. Sigue las reglas de trabajo de la sección 20 de la especificación.
3. Comprueba los límites del entorno (red, Docker): pueden haber cambiado.

## Reglas que no se negocian

- Los contratos de la sección 8 de `docs/spec.md` no se cambian sin ADR y sin actualizar la especificación en el mismo Pull Request.
- No se inventan ni se anticipan cifras de desempeño. Lo que no pasó por N3 es un supuesto.
- Prueba primero. Una rama por fase (`fase-N-nombre`), Conventional Commits en español.
- Ningún umbral dentro del código: van en `config/`.
- Ningún secreto ni dato en el repositorio.
- El sistema «señala para revisión»; nunca «confirma fraude».
- Lo que dependa de la versión de una herramienta (n8n, Omarchy, servidor del LLM) se verifica en su documentación oficial vigente antes de escribirlo.

## Comandos

```
uv sync                      # dependencias
uv run pytest                # pruebas unitarias (N1)
uv run ruff check . && uv run ruff format --check .
shellcheck fraude n8n/arranque.sh
```

Las pruebas del guion `./fraude` simulan `docker` y `sudo`. Parte de ellas solo corre sin ser administrador y otra parte solo como administrador: en un entorno donde se trabaja como `root`, ejecútalas también con un usuario normal.

Compose y n8n no pueden probarse sin Docker: se comprueban en GitHub Actions (N2).

## Dónde está cada cosa

- `fraude`: guion para quien ejecuta (bash). `src/fraude/`: API y línea de comandos `tareas`.
- `compose.yaml`, `Dockerfile`, `n8n/arranque.sh`, `n8n/flujos/*.json`.
- `docs/decisions/`: ADR. `docs/supuestos.md`: supuestos S1 a S12 y su estado.
- Código y nombres del dominio en español, sin tildes en el código. Fechas en UTC.
