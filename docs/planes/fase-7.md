# Fase 7 — LLM local (opcional): plan de implementación

> **Para quien ejecute el plan:** se trabaja tarea por tarea con `superpowers:executing-plans`, prueba primero. Cada paso lleva casilla (`- [ ]`).

**Meta:** la sección 14 de `docs/spec.md` completa. Un LLM local redacta, para el revisor, la explicación de cada alerta a partir de las señales ya calculadas. No decide ni cambia el nivel. Si no está activo, falla, tarda más del tiempo límite o su texto no pasa la comprobación automática, se usa la plantilla. El sistema pasa las pruebas con y sin LLM.

**Arquitectura:** servicio `llm` (Ollama, perfil `llm` de Compose, sin puerto publicado). En n8n, después de «Preparar explicación» (la plantilla de siempre), las alertas pasan por el nodo HTTP «Redactar explicación», que llama a `POST /explicacion` de la API. La API (`src/fraude/explicacion.py`) construye el mensaje solo con las señales, llama al LLM por la API compatible con OpenAI, comprueba el texto y devuelve la redacción o el motivo del respaldo. Si la API no responde, n8n se queda con su plantilla. Dos capas de respaldo; el nivel ya estaba decidido antes de llegar aquí.

**Tecnología:** Ollama 0.40.16 (`ollama/ollama:0.40.16`), modelo `qwen3.5:4b-q4_K_M`, `urllib` de la biblioteca estándar (sin dependencias nuevas), NVIDIA Container Toolkit en el anfitrión solo si se quiere la gráfica.

**Especificación:** `docs/spec.md`, secciones 2, 7, 8.5, 8.6, 8.8, 14, 15, 16 y 23.9; ADR 0009; ADR 0016 (nuevo).

## Verificación de versiones (2026-11-17)

| Tema | Comprobado | Fuente |
|---|---|---|
| Servidor | Ollama 0.40.16 es la última estable (9 de noviembre); 0.40.17 sigue en candidata | Página de publicaciones de `ollama/ollama` en GitHub |
| Imagen | `ollama/ollama:0.40.16` existe; 3.397.600.037 bytes comprimidos para linux/amd64 (unos 3,4 GB) | API de etiquetas de Docker Hub |
| API compatible con OpenAI | `/v1/chat/completions` admite `model`, `messages`, `temperature`, `seed`, `max_tokens`, `stream` y `reasoning_effort` (`"none"` desactiva el pensamiento en los modelos que lo permiten) | docs.ollama.com/api/openai-compatibility |
| Descarga y estado | `POST /api/pull` (progreso con `status`, `total`, `completed`; termina en `success`); `GET /api/ps` da `size_vram` y `digest` | docs.ollama.com/api/pull y /api/ps |
| Memoria | `OLLAMA_KEEP_ALIVE` negativo mantiene el modelo cargado (por defecto, 5 minutos) | docs.ollama.com/faq |
| Gráfica | RTX 5060: capacidad de cómputo 12.0, admitida; controlador 550 o posterior | docs.ollama.com/gpu |
| Modelo | `qwen3.5:4b-q4_K_M`, resumen `d8b0f5e9760c`, 3,3 GB; Apache 2.0; 201 idiomas; piensa por defecto | ollama.com/library/qwen3.5/tags; huggingface.co/Qwen/Qwen3.5-4B |
| Gráfica en Docker (Arch) | Paquete `nvidia-container-toolkit` 1.20.1 en *extra*; `nvidia-ctk runtime configure --runtime=docker` y reiniciar Docker | archlinux.org; guía de instalación de NVIDIA |
| Omarchy 4 | Docker sin grupo `docker` (se usa `sudo`); `omarchy pkg add` instala paquetes; los modelos propios (`omarchy agent local`) usan Podman y descargas de decenas de GB | omarchy.org/manual (Development Tools, Other Packages, AI) |

## Restricciones globales

- El LLM **no decide**: el nivel sale del nodo «Clasificar nivel» antes de redactar. Una prueba ejecuta el flujo con y sin redacción y exige el mismo nivel en todas las combinaciones.
- El LLM **no ve** datos que el sistema no calculó: el mensaje se construye solo con nivel, reglas activadas con su razón, puntuación y umbrales, y contribuciones. Nunca `variables` crudas ni la etiqueta.
- Comprobación automática (sección 15) antes de aceptar un texto: menciona el nivel correcto, no menciona otro nivel, no nombra reglas que no se activaron (ni inventadas), no cita variables que no estén en las contribuciones, no afirma fraude, no deja razonamiento visible y no excede la longitud. Si falla, plantilla, y el fallo queda anotado para la tasa de `explicaciones.json`.
- Parámetros en `config/llm.yaml` (dirección, modelo, tiempo límite, muestreo, etiquetas y palabras de la comprobación). Ninguno en el código.
- Sin LLM (`./fraude todo`), todo sigue igual que en la 0.6.0 salvo la nota de respaldo en la explicación.
- Lo que no pasó por N3 (gráfica, tiempos, calidad de los textos con el modelo de 4B) es un supuesto.

## Tareas

### Tarea 1: configuración y módulo `explicacion`

- [ ] Prueba: `config/llm.yaml` existe con servidor, modelo fijado, tiempo límite y comprobación.
- [ ] Prueba: el mensaje contiene el nivel, las reglas activadas con su razón, la puntuación, los umbrales y las contribuciones; no contiene reglas no activadas ni `variables`.
- [ ] Prueba: `comprobar` detecta cada tipo de fallo.
- [ ] Prueba: `redactar` devuelve plantilla con motivo `llm_desactivado`, `nivel_sin_redaccion`, `tiempo_agotado`, `error_llm` o `comprobacion_fallida`, y `llm` con modelo, duración y comprobación válida.
- [ ] Implementación en `src/fraude/explicacion.py`.

### Tarea 2: ruta `POST /explicacion` y contratos

- [ ] Prueba con un servidor compatible con OpenAI de pruebas (HTTP real, incluido el tiempo límite).
- [ ] Esquemas `redaccion_pedida` y `redaccion`; `explicacion` de los casos admite `respaldo` y `comprobacion` (ampliación, ADR 0016).

### Tarea 3: flujo de n8n

- [ ] Prueba en el simulador: solo las alertas piden redacción; con `llm` el caso guarda el texto del modelo; con plantilla, error de la API o sin respuesta, guarda la plantilla con su respaldo; el nivel no cambia en ninguna de las 45 combinaciones.
- [ ] Nodos If «¿Pedir redacción?», HTTP «Redactar explicación» (sin reintento, tiempo límite mayor que el de `config/llm.yaml`), If «¿Redacción del modelo?» y Set de cada salida.

### Tarea 4: `tareas llm`, `todo --llm` y evidencia

- [ ] `tareas llm`: descarga el modelo con progreso, lo precarga y deja `resultados/en_curso/llm.json` (modelo, resumen, tamaño, memoria de la gráfica usada).
- [ ] `tareas todo --llm` ejecuta `llm` antes de los demás pasos.
- [ ] `explicaciones.json`: origen, motivos de respaldo, tiempos (mediana y p95), comprobación repetida sobre cada caso guardado y su tasa de fallos, muestra de textos; `llm.json` en la evidencia; columnas nuevas en `casos.csv`.

### Tarea 5: Compose y guion

- [ ] Servicio `llm` con perfil `llm`, imagen exacta, volumen `ollama_modelos`, sin puertos, `OLLAMA_KEEP_ALIVE=-1`; `compose.gpu.yaml` con la reserva de la gráfica.
- [ ] `./fraude todo --llm`: perfil `llm`, `FRAUDE_LLM=activo`, `compose.gpu.yaml` solo si Docker tiene el entorno de NVIDIA y `nvidia-smi` responde; si el arranque con gráfica falla, reintenta con el procesador. Sin `--llm`, `FRAUDE_LLM=desactivado`. `apagar` también detiene `llm`.
- [ ] `anfitrion.json` anota si se pidió el LLM y con qué se ejecuta.

### Tarea 6: CI (N2)

- [ ] Trabajo nuevo «LLM local»: Ollama real con un modelo diminuto en el procesador (`qwen3.5:0.8b`), lote de la muestra, paridad total y explicaciones con origen `llm`; el trabajo de siempre comprueba el respaldo sin LLM.

### Tarea 7: documentos

- [ ] ADR 0016; `docs/spec.md` (secciones 7, 8.5, 8.6, 8.8, 14 y 16); `EJECUTAR.md` con la preparación de la gráfica; supuestos S9 y nuevos; `CHANGELOG.md`; `README.md`; `docs/ESTADO.md`.
