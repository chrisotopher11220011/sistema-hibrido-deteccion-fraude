# Arquitectura

Resumen de una página. El detalle y los contratos están en `docs/spec.md` (secciones 7 y 8); los motivos, en `docs/decisions/`.

## Destino (versión 1.0)

```
Página de simulación (navegador)
        |  envía transacción / decisión del revisor
        v
+---------- API (Python) -----------+        +---------------- n8n ----------------+
| Página y rutas de simulación  ----------->  | 1. Webhook de entrada               |
| Validación de variables           |        | 2. Consultar evaluación             |
| Reglas deterministas       <--------------- |                                     |
| Isolation Forest (puntuación) ----------->  | 3. Clasificar nivel de alerta       |
| Registro de casos (SQLite) <--------------- | 4. Registrar caso                   |
| Redacción de la explicación <-------------- | 5. Explicación (plantilla o LLM)    |
+-----------------------------------+        | 6. Notificación de prueba           |
        |                                    | 7. Revisión humana (otro webhook)   |
        v                                    +-------------------------------------+
LLM local (opcional, servicio llm)
```

## Hoy (versión 0.7.0)

```
Computador de ejecución (Omarchy 4)
│
├─ ./fraude ............ guion bash; único que habla con Docker (con sudo si hace falta)
│     ├─ escribe resultados/en_curso/: anfitrion.json, registros/, capturas/, .llm
│     └─ llama a Compose (con --llm: perfil «llm» y, si Docker ve la gráfica, compose.gpu.yaml)
│
└─ Docker Compose (proyecto «fraude»)
      ├─ api ............ FastAPI · 127.0.0.1:8000 · /salud, /evaluar, /explicacion,
      │                   /casos, /casos/{id}/revision, página en / y /simulacion/*
      │                   carga y recarga el modelo de datos/modelo/; casos en SQLite
      ├─ n8n ............ n8n 2.47.7 · 127.0.0.1:5678 · ping, transaccion, revision
      │                   arranque.sh: importar flujos → publicar → n8n start
      ├─ llm ............ Ollama 0.40.16 (perfil «llm», sin puerto) · qwen3.5:4b-q4_K_M
      └─ tareas ......... línea de comandos (perfil «tareas», sin puerto)
                          preparar, entrenar, evaluar, demostrar, llm y evidencia

n8n ──> POST /evaluar ──> «Clasificar nivel» ──> (alertas) POST /explicacion ──> llm
    ──> POST /casos ──> datos/casos/casos.sqlite ──> casos.csv, revisiones.csv, explicaciones.json
página ──> /simulacion/* ──> webhooks de n8n
```

Cualquier respuesta de `/evaluar` que no sea 200 hace que n8n marque el caso `error_evaluacion`. Los contratos están en `docs/contratos/`.

| Pieza | Archivos |
|---|---|
| Imagen de `api` y `tareas` | `Dockerfile`, `pyproject.toml`, `uv.lock`, `src/fraude/` |
| Servicios | `compose.yaml` |
| n8n | `n8n/arranque.sh`, `n8n/flujos/*.json` |
| Guion de ejecución | `fraude` |
| Configuración | `config/*.yaml` (`modelo.yaml` también guarda los parámetros de datos, partición, muestra y sintéticos) |
| Comprobación automática | `.github/workflows/ci.yml`, `tests/` |

## Reglas de diseño

- Los puertos se publican solo en `127.0.0.1`.
- `api` y `tareas` corren con el usuario de quien ejecuta, para que `datos/` y `resultados/` queden a su nombre.
- La página nunca llama a n8n directamente: lo hace la API.
- El LLM solo redacta, después de clasificar, y siempre con respaldo por plantilla (ADR 0016).
- La tabla de decisión vive en n8n, con copia en Python y prueba de paridad.
- Lo que solo el anfitrión puede ver (sistema, registros de Docker, capturas) lo recoge `./fraude`; los contenedores no acceden a Docker.
