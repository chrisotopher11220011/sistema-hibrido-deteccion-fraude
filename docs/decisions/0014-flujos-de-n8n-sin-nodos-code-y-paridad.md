# ADR 0014: Flujos de n8n sin nodos Code, simulador en N1 y respuestas de los webhooks

- **Estado:** Aceptada
- **Fecha:** 2026-11-17
- **Fase en la que se aplica:** 5

## Contexto

La sección 12 fija los pasos de los flujos de evaluación y revisión, y el ADR 0004 sitúa la tabla de decisión en el nodo «Clasificar nivel» con una copia en Python y una prueba de paridad. Quedaban abiertas varias cosas: cómo escribir los flujos sin editor visual de forma comprobable, qué responden los webhooks cuando la API no guarda el resultado, qué valida n8n por su cuenta, qué se reintenta y cómo se forma el lote de demostración.

Dos hechos condicionan la decisión. n8n 2.47.7 necesita Node.js 24 y Docker, que el entorno de desarrollo no tiene: el flujo real solo corre en N2. Y en n8n 2.x los nodos Code se ejecutan en «task runners» aparte, una pieza más que puede fallar.

Todo lo que depende de la versión se verificó en el código de n8n en la etiqueta `n8n@2.47.7` (commit `d4dcb1b`); el detalle está en `docs/planes/fase-5.md`.

## Decisión

**Nodos.** Los flujos usan solo Webhook 2, Edit Fields (Set) 3.4, If 2.2, Switch 3.2, HTTP Request 4.2 y Respond to Webhook 1.1. Sin nodos Code ni variables de entorno: todo se ve en el lienzo.

**Tabla de decisión.** El Set «Señales para la tabla» calcula `R_alto`, `R`, `A`, `A_alta` y `R_y_A` (una señal no evaluable cuenta como no activada). El Switch «Clasificar nivel» aplica la tabla 8.4 en orden: `fallo` → `error_evaluacion`; `R_alto` o `R_y_A` o `A_alta` → `alerta_prioritaria`; `R` o `A` → `revision_recomendada`; salida de respaldo → `sin_alerta`. Validación de tipos estricta.

**Simulador en N1.** `tests/n8n/simulador.mjs` ejecuta ese subconjunto de nodos con la semántica comprobada en el código de n8n (primera regla del Switch, salida de error con la entrada más `error`, reintentos acotados, expresiones que cierran en el primer `}}`). Con él, las pruebas recorren todas las combinaciones de señales contra `decision.clasificar` y todas las ramas de error con respuestas de la API simuladas. Es más estricto que n8n (tipos exactos, nada fuera del subconjunto). La prueba definitiva es N2.

**Validación en n8n.** Cuerpo objeto, `id_transaccion` texto de 1 a 100 caracteres, `origen` conocido, `monto` número finito ≥ 0 y sin `Class`. Es un subconjunto de la validación de la API: si n8n rechazara algo que la API acepta, los dos caminos de la paridad darían niveles distintos. Lo demás lo rechaza la API con 422.

**Reintentos.** `/evaluar`: tiempo límite de 10 s y 3 intentos con 1 s entre ellos, solo ante errores de red o de tiempo; una respuesta distinta de 200 ya es la respuesta y lleva a `error_evaluacion` con su tipo y mensaje como razón. `/casos` y `/casos/{id}/revision` no se reintentan, para no duplicar casos ni revisiones.

**Respuestas.** `/webhook/transaccion` responde 200 con el caso registrado. Si la API no lo guarda, 502 con `{"error": {"tipo": "caso_no_registrado", …}, "caso": <calculado>}`: el caso queda en la respuesta y en el historial de n8n (ADR 0005). `/webhook/revision` repite el código y el cuerpo de la API; 422 sin llamarla si `id_caso` no tiene la forma `c-` y 12 cifras hexadecimales; 502 si no responde. Esquema `docs/contratos/error_flujo.schema.json`.

**Explicación y notificación.** Plantilla en el Set «Preparar explicación»: menciona solo lo que se activó, «señala para revisión» y nunca confirma fraude. La notificación de prueba es simulada (`canal: simulada`) y queda escrita en el caso; Telegram queda para cuando se pida.

**Versión del flujo.** `versiones.flujo` del caso es `transaccion-<versión del paquete>`.

**Lote de demostración.** `datos/demostracion/lote.json` (o `datos/muestra/demostracion/lote.json`), con semilla y parámetros en `config/modelo.yaml` (`demostracion`): fraudes y no fraudes de la parte de **prueba**, las primeras sintéticas de ubicación y seis entradas inválidas fijas, una de ellas solo detectable por la API. La etiqueta real va en cada elemento, fuera de la transacción.

**`demostrar`.** Cada elemento va por n8n (webhook) y por Python (`/evaluar` + `decision.clasificar`). Exige el mismo nivel en todos, que cada caso quede registrado y que su estado corresponda a su nivel. La latencia se mide desde `tareas` hasta la respuesta del webhook (incluye `/evaluar` y `/casos`): mediana y percentil 95 con interpolación lineal. Todo queda en `flujo.json`, también si falla.

## Consecuencias

- La combinación de señales se ve en el lienzo de n8n y no depende de los ejecutores de código.
- La paridad tiene dos capas: exhaustiva en N1 (simulador) y sobre el lote real en N2 y N3 (`demostrar`). Un fallo de paridad hace fallar `demostrar` y, con él, la CI.
- El simulador puede divergir de n8n en algo no cubierto: por eso la CI ejecuta además los flujos reales, incluidas las ramas de error (sin modelo, entrada inválida, API detenida).
- Las expresiones de los Set son largas; a cambio, cada una es una sola expresión JS comprobable.
- Cambiar de versión de n8n o de nodo exige repetir la verificación y ampliar el simulador.
- Es una ampliación de lo que la sección 8 dejaba abierto, no un cambio de contrato.
