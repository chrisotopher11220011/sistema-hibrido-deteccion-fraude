# Fase 1 — Cimientos: plan de implementación

> **Para quien ejecute el plan:** se trabaja tarea por tarea con `superpowers:executing-plans`. Cada paso lleva casilla (`- [ ]`).

**Meta:** dejar un repositorio que arranca `api` y `n8n` con un comando en Omarchy 4, responde `GET /salud` y `GET /webhook/ping`, y deja una carpeta de evidencia mínima; todo comprobado en GitHub Actions.

**Arquitectura:** una sola imagen de Python sirve a `api` (FastAPI) y a `tareas` (línea de comandos). n8n usa la imagen oficial con versión exacta y un guion de arranque que importa y publica los flujos antes de `n8n start`. El guion `./fraude` (bash) es la única pieza que habla con Docker en el computador de quien ejecuta.

**Tecnología:** Python 3.12, uv, FastAPI, pytest, ruff, Docker Compose, n8n 2.47.7, bash.

**Especificación:** `docs/spec.md` (secciones 8, 12, 16, 17, 19, 20 y 21).

## Restricciones globales

- Puertos publicados solo en `127.0.0.1`; `api` en 8000 y `n8n` en 5678, cambiables por variables de entorno. Nada exige un archivo `.env`.
- Nombres del dominio en español; en el código, sin tildes. Fechas en UTC.
- Ningún umbral dentro del código: van en `config/`.
- Imágenes con versión exacta y dependencias bloqueadas en `uv.lock`.
- Los mensajes de `./fraude` van en español y dicen qué pasa y qué falta.
- Sin secretos ni datos en el repositorio.
- Toda afirmación indica su nivel de verificación (N1, N2 o N3).

## Lo que se verificó antes de escribir código (2026-11-16)

| Tema | Hallazgo | Fuente |
|---|---|---|
| Versión de n8n | La estable es 2.47.7 y la beta 2.48.4. n8n 3.0 está en beta desde el 27 de octubre y su versión estable se espera para diciembre: no se usa | Registro de cambios y notas de versión de n8n |
| Importar flujos | `n8n import:workflow` desactiva todo lo que importa. Un flujo con el mismo `id` se sobrescribe | Documentación de la línea de órdenes de n8n |
| Publicar flujos | `n8n publish:workflow --id=<ID>`, sin `--all`. Aplica las mismas comprobaciones que el editor. Si n8n no está en marcha, el cambio se aplica al arrancar | Ídem |
| Docker en Omarchy 4 | Docker y Compose vienen instalados. El usuario no está en el grupo `docker`: se usa `sudo docker …`. Opción *Setup > Security > Sudoless Docker* | Manual de Omarchy, *Development Tools* |
| Cortafuegos | Bloquea lo entrante salvo LocalSend, mDNS y las consultas DNS de los contenedores a `172.17.0.1`. Docker queda protegido con ufw-docker | Manual de Omarchy, *Security* y *Networking* |
| Capturas | `Print Screen`; se guardan en `~/Pictures/Screenshots` como `screenshot-<fecha>-<aplicación>.png`. La carpeta cambia con `OMASNAP_SCREENSHOT_DIR` | Manual de Omarchy, *Screenshots & Recording* y FAQ |
| Grabación | `Alt + Print Screen`; MP4 en `~/Videos` | Ídem |

Entorno de este chat: llega a GitHub y a PyPI; no llega a Docker Hub, Kaggle ni OpenML; no tiene el servicio de Docker en marcha. Por eso Compose y n8n se comprueban solo en N2.

## Decisiones de esta fase

1. **Activación de flujos:** el contenedor `n8n` arranca con `n8n/arranque.sh`, que importa `n8n/flujos/*.json`, publica cada flujo por su `id` fijo y luego ejecuta `n8n start`. Así no hace falta reiniciar ni tocar el editor.
2. **Propiedad de archivos:** `./fraude` corre como el usuario y solo antepone `sudo` a `docker`. Los contenedores `api` y `tareas` corren con el UID y GID del usuario (`FRAUDE_UID`, `FRAUDE_GID`). Si alguien lanza `sudo ./fraude`, el guion devuelve la propiedad de `resultados/` y `datos/` a `SUDO_UID`.
3. **Registros:** solo el anfitrión puede leer los registros de Docker. `./fraude` los guarda en `resultados/en_curso/registros/` y `tareas evidencia` los copia.
4. **`todo` en dos caminos:** `tareas todo` termina siempre con `evidencia`. `./fraude todo` llama a `tareas todo --sin-evidencia`, recoge registros, capturas y datos del sistema, y después llama a `tareas evidencia`, para que los registros sean posteriores a los pasos.
5. **Pasos que aún no existen:** `preparar`, `entrenar`, `evaluar` y `demostrar` responden «llega en la fase N» y salen con código 0 dentro de `todo`; llamados sueltos salen con código 2.

## Revisión dirigida

Condiciones que la especificación implica y que más pueden afectar a quien ejecuta:

1. `docker` responde solo con `sudo` → el guion lo detecta y lo dice.
2. Se ejecuta `sudo ./fraude todo` → los archivos no quedan a nombre de `root`.
3. Un servicio no arranca → quedan registros en `resultados/` sin pedirlos y el resumen dice qué falló.
4. `evidencia` se ejecuta dos veces en el mismo segundo → dos carpetas completas, ninguna pisada.
5. No hay capturas ni `anfitrion.json` → la evidencia se genera igual y lo anota.

Cada una tiene su prueba en la tarea que le corresponde.

---

### Tarea 1: paquete, API y `/salud`

**Archivos:** `pyproject.toml`, `uv.lock`, `src/fraude/__init__.py`, `src/fraude/api.py`, `tests/unitarias/test_api.py`.

**Produce:** `fraude.__version__ = "0.1.0"`; `fraude.api.app` (FastAPI); `GET /salud` → `{"estado": "ok", "servicio": "api", "version": str, "fecha": ISO 8601 UTC, "modelo": {"cargado": false, "motivo": str}}`.

- [ ] Prueba: `test_salud_responde_ok` (200, `estado == "ok"`, `modelo.cargado is False`, fecha termina en `Z`).
- [ ] Ver que falla, implementar, ver que pasa, commit.

### Tarea 2: evidencia mínima

**Archivos:** `src/fraude/evidencia.py`, `tests/unitarias/test_evidencia.py`.

**Produce:**
- `comprobar_servicios(url_api: str, url_n8n: str, obtener=...) -> list[dict]` con una entrada por servicio: `{"servicio", "url", "ok", "detalle"}`. Comprueba `<api>/salud` y `<n8n>/webhook/ping`.
- `reunir_evidencia(raiz: Path, *, commit: str, etiqueta: str, servicios: list[dict], pasos: list[dict], ahora: datetime | None = None) -> Path`. Crea `resultados/<AAAAMMDDTHHMMSSZ>_<commit>/` y el `.zip` hermano con `RESUMEN.md`, `anfitrion.json`, `entorno.json`, `version.json`, `errores.json`, `registros/`, `OBSERVACIONES.md` y `capturas/`. Lee lo que `./fraude` dejó en `resultados/en_curso/`.
- `enmascarar(texto: str) -> str`: oculta valores de variables cuyo nombre contiene `TOKEN`, `SECRET`, `PASSWORD`, `CLAVE` o `API_KEY`.

- [ ] Pruebas: carpeta y zip con los archivos esperados; servicio caído aparece en `errores.json` y en `RESUMEN.md`; sin `anfitrion.json` se anota la ausencia; dos llamadas con la misma hora dan carpetas distintas; un token en un registro sale enmascarado; `OBSERVACIONES.md` incluye las diez preguntas SUS.
- [ ] Ver que fallan, implementar, ver que pasan, commit.

### Tarea 3: línea de comandos `tareas`

**Archivos:** `src/fraude/cli.py`, `tests/unitarias/test_cli.py`.

**Produce:** `fraude.cli.main(argv: list[str] | None = None) -> int`, punto de entrada `fraude`. Comandos `preparar`, `entrenar`, `evaluar`, `demostrar`, `evidencia` y `todo [--sin-evidencia]`. Entorno: `FRAUDE_RAIZ` (por defecto `/trabajo`), `FRAUDE_URL_API`, `FRAUDE_URL_N8N`, `FRAUDE_COMMIT`, `FRAUDE_ETIQUETA`. `todo` escribe `resultados/en_curso/pasos.json`.

- [ ] Pruebas: `todo` con servicios en buen estado devuelve 0 y crea evidencia; con n8n caído devuelve 1 y aun así crea evidencia; `preparar` suelto devuelve 2 y nombra la fase 2; `todo --sin-evidencia` no crea carpeta pero sí `pasos.json`.
- [ ] Ver que fallan, implementar, ver que pasan, commit.

### Tarea 4: Compose, imagen y flujo ping

**Archivos:** `Dockerfile`, `.dockerignore`, `compose.yaml`, `n8n/arranque.sh`, `n8n/flujos/ping.json`, `config/*.yaml`, `tests/unitarias/test_estructura.py`.

- [ ] Pruebas de estructura (N1, sin Docker): los puertos publicados empiezan por `127.0.0.1:`; la imagen de n8n lleva versión exacta y coincide con `N8N_VERSION_FIJADA` de `tareas`; cada flujo tiene `id` fijo y único, y su nodo Webhook lleva `webhookId`; `ping.json` declara `GET` y ruta `ping`; `config/reglas.yaml` fija el umbral 1000.
- [ ] Implementar. `n8n` con `init: true`, comprobación de salud contra `/healthz` hecha con Node, volumen `n8n_datos`. `tareas` en el perfil `tareas`.
- [ ] Commit.

### Tarea 5: guion `./fraude`

**Archivos:** `fraude`, `tests/unitarias/test_guion.py` (ejecuta el guion con `docker`, `sudo` y `xdg-open` simulados en el `PATH`).

**Comandos:** `todo [--llm]`, `preparar`, `entrenar`, `evaluar`, `demostrar`, `evidencia`, `abrir`, `estado`, `apagar`, `ayuda`.

- [ ] Pruebas: sin argumentos muestra la ayuda en español; si `docker info` falla y `sudo` funciona, los comandos de Docker salen con `sudo` y `anfitrion.json` dice `"uso_sudo": true`; si `docker info` funciona, no se usa `sudo`; `evidencia` deja registros en `resultados/en_curso/registros/`; un fallo de `up` deja registros y termina con código distinto de 0; `evidencia` copia las capturas nuevas de la carpeta de capturas; `apagar` llama a `compose down`.
- [ ] Implementar, `bash -n`, ver que pasan, commit.

### Tarea 6: CI

**Archivos:** `.github/workflows/ci.yml`, `tests/punta_a_punta/comprobar_evidencia.py`, plantillas de issue y de Pull Request.

- [ ] Trabajo `pruebas`: `uv sync --frozen`, `ruff check`, `ruff format --check`, `pytest`, `shellcheck fraude n8n/arranque.sh`.
- [ ] Trabajo `punta-a-punta`: `docker compose up -d --build --wait`; `curl` a `/salud` y a `/webhook/ping` desde el anfitrión; `docker compose run --rm tareas todo`; después `./fraude todo`, `./fraude estado`, comprobación de que nada en `resultados/` pertenece a `root` y `./fraude apagar`. La evidencia se sube como artefacto, también si falla.

### Tarea 7: documentos

`CLAUDE.md`, `README.md`, `CHANGELOG.md`, `EJECUTAR.md`, `docs/ESTADO.md`, `docs/supuestos.md`, `docs/architecture.md` y los ADR 0001 a 0011 con la plantilla de Nygard.

### Tarea 8: cierre

Verificación con evidencia, revisión con subagente de contexto limpio, Pull Request, integración, etiqueta `v0.1.0`, actualización de `ESTADO`, `CHANGELOG` y `supuestos`, e informe de fase con el mensaje del punto de prueba A.
