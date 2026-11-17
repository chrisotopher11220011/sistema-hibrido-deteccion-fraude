# Fase 5 — Flujos de n8n: plan de implementación

> **Para quien ejecute el plan:** se trabaja tarea por tarea con `superpowers:executing-plans`, prueba primero. Cada paso lleva casilla (`- [x]`).

**Meta:** que n8n evalúe cada transacción (webhook, validar, consultar `/evaluar` con reintento y tiempo límite, clasificar nivel, explicar por plantilla, notificación de prueba, registrar caso, responder con el caso), que reciba la revisión humana, que `tareas demostrar` envíe el lote de demostración midiendo paridad y latencia en `flujo.json`, y que la CI exija paridad total.

**Arquitectura:** dos flujos nuevos en `n8n/flujos/` (`evaluacion.json`, `revision.json`) escritos como JSON, solo con nodos Webhook, Edit Fields (Set), If, Switch, HTTP Request y Respond to Webhook: sin nodos Code, para no depender de los ejecutores de código. La tabla de la sección 8.4 vive en el nodo Switch «Clasificar nivel», precedido por un Set que calcula `R_alto`, `R`, `A`, `A_alta` y `R_y_A`. Un **simulador** de ese subconjunto de nodos (`tests/n8n/simulador.mjs`, Node.js) ejecuta los flujos en N1 con respuestas de la API simuladas: así la paridad con `decision.clasificar` se prueba en todas las combinaciones en N1, y con n8n real en N2.

**Tecnología:** n8n 2.47.7, Node.js (solo para el simulador en pruebas), Python con `urllib` para `demostrar`.

**Especificación:** `docs/spec.md`, secciones 8.4, 8.5, 8.7, 8.8, 12, 15 (latencia y paridad), 16 (`flujo.json`) y 21; ADR 0004, 0005, 0007 y 0013.

## Restricciones globales

- Los contratos de la sección 8 no cambian. Lo que la sección 8 no fija (respuesta de los webhooks cuando el caso no se pudo registrar, forma del lote) se decide aquí y queda en el ADR 0014.
- La tabla del nodo «Clasificar nivel» y `decision.clasificar` deben dar el mismo nivel siempre. Una entrada inválida o una evaluación fallida terminan en `error_evaluacion` y pendientes de revisión; nunca en `sin_alerta`.
- La validación de n8n es un subconjunto de la de la API (nunca más estricta): si n8n rechazara algo que la API acepta, los dos caminos darían niveles distintos.
- Los umbrales llegan en la respuesta de `/evaluar`; el flujo no lee variables de entorno.
- Lenguaje: «señala para revisión»; nunca «confirma fraude».
- Sin cifras de desempeño: el lote de la CI sale de la muestra y no es reportable.

## Lo que se verificó antes de escribir los flujos (2026-11-17, UTC)

Fuente: código de n8n en la etiqueta `n8n@2.47.7` (commit `d4dcb1b`), repositorio oficial `n8n-io/n8n`.

| Tema | Hallazgo | Archivo |
|---|---|---|
| Versiones de nodo disponibles | Webhook 1–2.2, Respond to Webhook 1–1.5, HTTP Request 3–4.5, If 2–2.4, Switch 3–3.5, Set 3–3.5. Se usan Webhook 2 y Respond 1.1 (como el ping ya probado en N2), If 2.2, Switch 3.2, Set 3.4 y HTTP Request 4.2 | `*/*.node.ts` |
| Switch 3.x | `rules.values[]` con `conditions` (`combinator`, `conditions`, `options`), `renameOutput` y `outputKey`; `options.fallbackOutput: "extra"` añade una salida al final; por defecto solo la **primera** regla que se cumple (`allMatchingOutputs: false`) | `Switch/V3/SwitchV3.node.ts` |
| Condición booleana | Operador `{"type": "boolean", "operation": "true", "singleValue": true}`; con `typeValidation: "strict"` el valor debe ser booleano | `workflow/src/node-parameters/filter-parameter.ts` |
| Set 3.4 | `assignments.assignments[]` con `id`, `name`, `type` (`string`, `number`, `boolean`, `array`, `object`) y `value`; `includeOtherFields` (falso por defecto); desde 3.2 un valor `null` se acepta | `Set/v2/SetV2.node.ts`, `Set/v2/helpers/utils.ts` |
| HTTP Request 4.2 | `sendBody`, `specifyBody: "json"`, `jsonBody` (si la expresión devuelve un objeto se envía tal cual); `options.timeout` en ms; `options.response.response.{fullResponse, neverError}` devuelve `{body, headers, statusCode, statusMessage}` sin fallar en códigos no 2xx | `HttpRequest/V3/*.ts` |
| Reintentos | `retryOnFail`, `maxTries` (acotado a 2–5) y `waitBetweenTries` (0–5000 ms) del nodo. Se reintenta cuando la salida trae `json.error`: errores de red o tiempo límite, no respuestas 4xx/5xx con `neverError` | `core/src/execution-engine/workflow-execute.ts` |
| Salida de error | `onError: "continueErrorOutput"` añade una segunda salida; su elemento es la entrada del nodo más `error` | `workflow-execute.ts` (`handleNodeErrorOutput`) |
| Respond to Webhook | `respondWith: "json"`, `responseBody` (objeto o texto JSON), `options.responseCode` (100–599) | `RespondToWebhook/RespondToWebhook.node.ts` |
| Expresiones | `{{ … }}` termina en el **primer** `}}`; están disponibles `Number`, `JSON`, `Array`, `Object` (seguro), `encodeURIComponent`, `isFinite` (= `Number.isFinite`) | `workflow/src/extensions/expression-parser.ts`, `workflow/src/expression.ts` |
| Entorno de este chat | Docker sin servicio; n8n 2.47.7 pide Node.js ≥ 24 y aquí hay 22 (instalar otro Node fue denegado): n8n solo se ejecuta en N2 | Comprobación directa |

## Decisiones de esta fase (ADR 0014)

1. **Sin nodos Code.** Todo con Set, If y Switch: se ve en el lienzo y no depende de los ejecutores de tareas de n8n 2.x.
2. **Validación en n8n** (subconjunto de la API): cuerpo objeto, `id_transaccion` texto de 1 a 100, `origen` `original` o `sintetico`, `monto` número finito ≥ 0, sin `Class`. Lo demás lo valida la API (422).
3. **`/evaluar`:** tiempo límite 10 s, 3 intentos con 1 s entre ellos, solo ante errores de red o tiempo límite. Una respuesta distinta de 200 no se reintenta: es `error_evaluacion` con el tipo y el mensaje de la API como razón.
4. **Notificación de prueba:** simulada, escrita en el caso (`canal: simulada`). Telegram queda para cuando Christopher lo pida.
5. **Registro del caso:** `POST /casos` sin reintento, para no duplicar casos. Si no se registra, el webhook responde 502 con `{"error", "caso"}`: el caso calculado viaja en la respuesta y queda en el historial de n8n (ADR 0005).
6. **Respuesta del webhook de transacción:** 200 con el caso registrado (esquema `caso`).
7. **Revisión:** `id_caso` debe cumplir `^c-[0-9a-f]{12}$` (si no, 422 sin llamar a la API); el webhook responde el código y el cuerpo de la API.
8. **Versión del flujo:** `transaccion-<versión del paquete>` y `revision-<versión>`; una prueba lo comprueba.
9. **Lote de demostración:** `datos/demostracion/lote.json` (real) o `datos/muestra/demostracion/lote.json`, con semilla, desde la parte de **prueba**: fraudes y no fraudes, las sintéticas de ubicación y entradas inválidas fijas. Cada elemento lleva su etiqueta real aparte de la transacción.
10. **Paridad en `demostrar`:** cada elemento va por n8n (webhook) y por Python (`/evaluar` + `decision.clasificar`). Se exige el mismo nivel en todos; si no, el paso falla.
11. **Latencia:** desde `tareas` hasta la respuesta del webhook (incluye `/evaluar` y `/casos`): mediana y percentil 95 (interpolación lineal).

## Revisión dirigida

1. `/evaluar` responde 422, 503 o 500, no responde o tarda más del límite → `error_evaluacion`, `pendiente_revision`, con razón.
2. Entrada que no es objeto, sin `id_transaccion`, `monto` como texto o con `Class` → `error_evaluacion` sin llamar a la API.
3. Las 16 combinaciones de `R_alto`, `R`, `A`, `A_alta`, más reglas y modelo no evaluables → mismo nivel que `decision.clasificar`.
4. La API cae al registrar → 502 con el caso calculado, nunca un 200.
5. Revisión con `id_caso` raro (`../salud`) → 422 sin tocar la API.

---

### Tarea 1: simulador de flujos y pruebas de estructura

**Archivos:** crear `tests/n8n/simulador.mjs`, `tests/n8n/conftest.py`, `tests/n8n/test_simulador.py`; modificar `pyproject.toml` (`testpaths`).

- [x] Prueba: el simulador ejecuta un flujo mínimo (Webhook → Set → If → Respond) y uno con Switch, HTTP simulado, reintentos y salida de error; rechaza expresiones con `}}` interno, tipos de nodo o versiones fuera del subconjunto y nombres con punto.
- [x] Ver fallar, escribir el simulador, ver pasar, commit.

### Tarea 2: flujo de evaluación

**Archivos:** crear `n8n/flujos/evaluacion.json`, `tests/n8n/test_flujo_evaluacion.py`.

- [x] Prueba de paridad exhaustiva con `decision.clasificar`; ramas de error (entrada inválida, 422, 503, 500, sin respuesta tras 3 intentos); caso enviado a `/casos` válido según `CasoNuevo` y `docs/contratos/caso_nuevo.schema.json`; razones y explicación; 502 si el registro falla; ids y `webhookId` fijos.
- [x] Ver fallar, escribir el flujo, ver pasar, commit.

### Tarea 3: flujo de revisión

**Archivos:** crear `n8n/flujos/revision.json`, `tests/n8n/test_flujo_revision.py`.

- [x] Prueba: reenvía decisión, revisor y comentario a `/casos/{id}/revision` y devuelve su código y cuerpo; 422 local con `id_caso` inválido; 502 si la API no responde.

### Tarea 4: lote y `demostrar`

**Archivos:** crear `src/fraude/lote.py`, `src/fraude/demostrar.py` y sus pruebas; modificar `cli.py`, `evidencia.py`, `config/modelo.yaml`, `fraude`.

- [x] Pruebas: lote determinista con fraudes, no fraudes, sintéticas e inválidas, sin `Class` en las transacciones; `demostrar` con servicios simulados escribe `flujo.json` con paridad, latencias y errores, y falla si hay una discrepancia o n8n no responde; `todo` incluye `demostrar`; la evidencia copia `flujo.json`.

### Tarea 5: CI

**Archivos:** crear `tests/punta_a_punta/comprobar_flujos.py`; modificar `.github/workflows/ci.yml` y `comprobar_evidencia.py`.

- [x] Antes de entrenar: evaluación con variables sin modelo → `error_evaluacion`; entrada inválida → `error_evaluacion`; revisión 200, 409, 404 y 422.
- [x] Después de `todo --muestra`: `flujo.json` con paridad total y entradas inválidas en `error_evaluacion`.
- [x] Con la API detenida: el webhook responde 502 con el caso en `error_evaluacion`.

### Tarea 6: cierre

- [x] Revisión de código con subagente; ADR 0014; `CHANGELOG.md`, `docs/ESTADO.md`, `docs/supuestos.md`, `README.md`, `EJECUTAR.md`; Pull Request.
