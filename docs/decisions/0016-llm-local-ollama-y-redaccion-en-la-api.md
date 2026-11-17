# ADR 0016: LLM local con Ollama, redacción en la API y doble respaldo por plantilla

- **Estado:** Aceptada
- **Fecha:** 2026-11-17
- **Fase en la que se aplica:** 7
- **Desarrolla:** ADR 0009

## Contexto

El ADR 0009 dejó para la fase 7 el servidor y el modelo del LLM, que solo redacta la explicación de una alerta. La sección 14 pide: servicio `llm` en el perfil `llm` de Compose, API compatible con OpenAI con dirección y modelo configurables, gráfica si está disponible y procesador si no, un modelo que quepa en 8 GB de VRAM, respaldo por plantilla si el LLM no está, falla o tarda, y trazabilidad de origen, modelo y tiempo. La sección 15 pide comprobar de forma automática que cada explicación menciona el nivel correcto y ninguna regla que no se activó, con su tasa de fallos.

El computador de ejecución tiene una RTX 5060 de 8 GB y Omarchy 4. Docker no viene preparado para la gráfica, y los modelos propios de Omarchy (`omarchy agent local`) quedan fuera (sección 14): usan Podman, descargas de decenas de GB y hoy solo modelos para equipos de 128 GB.

Todo lo que depende de versiones se comprobó el 2026-11-17 (detalle y fuentes en `docs/planes/fase-7.md`).

## Decisión

**Servidor: Ollama 0.40.16** (`ollama/ollama:0.40.16`, la última estable; 0.40.17 seguía en candidata). Gestiona la descarga de modelos con un comando, mantiene el modelo en memoria, usa CUDA si el contenedor ve la gráfica y el procesador si no, y ofrece `/v1/chat/completions` compatible con OpenAI. Su documentación lista la RTX 5060 (capacidad de cómputo 12.0). Alternativas descartadas: el servidor de llama.cpp (no gestiona descargas: habría que bajar a mano el GGUF y su resumen), vLLM (pensado para servir a muchos usuarios a la vez; para un solo revisor añade complejidad sin ventaja), LM Studio (aplicación de escritorio, fuera de Compose) y los modelos de Omarchy.

**Modelo: `qwen3.5:4b-q4_K_M`** (resumen `d8b0f5e9760c`, 3,3 GB, Apache 2.0, 201 idiomas). Deja unos 4 GB de la gráfica libres para el escritorio de Hyprland y el contexto. El pensamiento, activo por defecto, se desactiva con `reasoning_effort: "none"`. Descartados: `qwen3.5:9b` (6,6 GB: justo en 8 GB con el escritorio usando la gráfica), `gemma4:e2b` (4,6 a 7,5 GB para su tamaño efectivo) y modelos de 2024 como Llama 3.2 3B. El nombre y el resumen quedan en `config/llm.yaml`; `tareas llm` anota en `llm.json` el resumen real y si coincide.

**Quién llama al LLM: la API, a petición de n8n.** Después de «Preparar explicación» (la plantilla de siempre), n8n pide la redacción de las alertas a `POST /explicacion` con el nivel ya decidido y las señales tal como las devolvió `/evaluar`. La API construye el mensaje, llama al LLM y comprueba el texto. Motivos: los parámetros viven en `config/llm.yaml` (ningún umbral en el código, y los nodos de n8n no leen el entorno, ADR 0014); la comprobación de la sección 15 es Python probado en N1 y no expresiones de n8n; y hay dos capas de respaldo con tiempos límite separados. El paso sigue siendo del flujo, como sitúa la sección 7, y el LLM sigue detrás de la API como n8n detrás de la API para la página (ADR 0007). La sección 7 se actualiza en este mismo Pull Request.

**Qué ve el LLM.** Solo el nivel, las reglas activadas con su razón (y si son de alto riesgo), la puntuación y los umbrales del modelo y las contribuciones. Nunca las `variables`, el identificador de la transacción ni la etiqueta.

**Comprobación automática** (`explicacion.comprobar`, sin tildes y sin distinguir mayúsculas). Se rechaza el texto vacío, con razonamiento visible (`<think>`), de más de 700 caracteres, que no menciona la etiqueta de su nivel o menciona la de otro, que nombra una regla no activada (por su identificador o por palabras como «país» para la de ubicación), que inventa una regla con forma de identificador, que cita una variable que no está en las contribuciones o que afirma fraude («es fraude», «fraude confirmado», «se confirma el fraude»…). Etiquetas, palabras y expresiones están en `config/llm.yaml`.

**Respaldo, en dos capas.**

| Dónde | Cuándo | `respaldo.motivo` |
|---|---|---|
| API | `./fraude todo` sin `--llm` (`FRAUDE_LLM=desactivado`) | `llm_desactivado` |
| API | Nivel `sin_alerta` o `error_evaluacion` | `nivel_sin_redaccion` (n8n ni siquiera lo pide) |
| API | El LLM no responde en `tiempo_limite_s` (20 s) | `tiempo_agotado` |
| API | Error de red, HTTP o respuesta sin texto | `error_llm` |
| API | El texto no pasa la comprobación | `comprobacion_fallida`, con el texto descartado |
| n8n | `/explicacion` no responde en 30 s, responde otro código o algo que no es una redacción | `error_api` |

En todos, el caso guarda el texto de la plantilla de n8n con `origen: plantilla` y el motivo. `/explicacion` no se reintenta. El nivel ya estaba decidido: ninguna rama lo toca.

**Contrato.** Ampliaciones sin cambiar nada de lo existente: ruta `POST /explicacion` (8.6), esquemas `redaccion_pedida` y `redaccion`, y campos opcionales `respaldo` y `comprobacion` en `explicacion` del caso (8.5). Comando `tareas llm` y opción `todo --llm` (8.8).

**Gráfica.** `compose.gpu.yaml` reserva la gráfica para `llm`. `./fraude todo --llm` lo añade solo si `nvidia-smi` responde y Docker tiene el entorno `nvidia`; si no, avisa y sigue en el procesador. Si el arranque con gráfica falla, reintenta en el procesador. El estado (`grafica` o `procesador`) se guarda en `resultados/en_curso/.llm` para que los pasos sueltos usen el mismo Compose y no recreen la API sin LLM; `./fraude apagar` lo borra y detiene también `llm`.

**Preparación única en Omarchy 4**, con permisos de administrador: `sudo pacman -S nvidia-container-toolkit` (o `omarchy pkg add nvidia-container-toolkit`; paquete 1.20.1 de *extra*), `sudo nvidia-ctk runtime configure --runtime=docker` y `sudo systemctl restart docker`. Está en `EJECUTAR.md`.

**Trazabilidad.** Cada explicación guarda origen, modelo, tiempo, respaldo y comprobación. `tareas llm` deja `llm.json` (servidor, modelo, resumen, tiempos de descarga y carga, memoria de la gráfica usada y si corre en la gráfica, en el procesador o mixto). `tareas evidencia` deja `explicaciones.json` con origen, motivos, tiempos (mediana, p95 y máximo), tasa de fallos de la comprobación por tipo, la comprobación repetida sobre lo guardado y una muestra de textos sin secretos.

**N2.** Un trabajo de la CI ejecuta `./fraude todo --muestra --llm` con Ollama real en el procesador y `qwen3.5:0.8b`, de la misma familia: comprueba el camino entero, no la calidad del texto del modelo fijado.

## Consecuencias

- El sistema funciona igual sin LLM y el nivel es idéntico con él y sin él: lo prueba el simulador en las 45 combinaciones de señales y la paridad de `demostrar` en N2 con el LLM activo.
- La primera vez con `--llm` se descargan unos 6,7 GB: la imagen de Ollama (3,4 GB comprimida) y el modelo (3,3 GB). El modelo queda en el volumen `ollama_modelos` y sobrevive a `./fraude apagar`.
- Con el LLM en el procesador, cada explicación tarda más; si pasa de 20 s, queda la plantilla. El tiempo real en la gráfica y en el procesador del Alienware es un supuesto hasta el punto C con LLM.
- La comprobación puede rechazar textos aceptables (por ejemplo, una negación como «no es fraude»): es conservadora a propósito. La tasa queda en `explicaciones.json` para decidir en la fase 8.
- Cambiar de servidor, versión o modelo exige repetir la verificación, actualizar `config/llm.yaml` y `compose.yaml`, y este ADR.
