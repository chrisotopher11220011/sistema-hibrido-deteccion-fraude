# Contratos

Esquemas JSON (borrador 2020-12) de la sección 8 de `docs/spec.md`. Son el acuerdo entre la API, n8n y la página. Cambiar uno exige un ADR y actualizar la especificación en el mismo Pull Request.

| Esquema | Qué describe | Origen |
|---|---|---|
| `transaccion.schema.json` | Transacción que entra por `POST /evaluar` y por `/webhook/transaccion` | Sección 8.2 |
| `evaluacion.schema.json` | Respuesta 200 de `POST /evaluar` | Sección 8.3 |
| `caso_nuevo.schema.json` | Cuerpo de `POST /casos`: lo que calcula n8n | Sección 8.5; ADR 0013 |
| `caso.schema.json` | Caso registrado, tal como lo devuelve la API | Sección 8.5 |
| `lista_casos.schema.json` | Respuesta de `GET /casos` | ADR 0013 |
| `revision.schema.json` | Cuerpo de `POST /casos/{id}/revision` | Sección 8.5; ADR 0013 |
| `error.schema.json` | Cuerpo de toda respuesta que no es 2xx | ADR 0013 |
| `salud.schema.json` | Respuesta de `GET /salud` | Sección 8.6 |
| `error_flujo.schema.json` | Respuesta 502 de los webhooks de n8n cuando la API no guardó el resultado | Sección 8.7; ADR 0014 |

Cada esquema tiene un `$id` de la forma `urn:fraude:contratos:<nombre>`; `caso` y `caso_nuevo` usan `evaluacion` por referencia.

## Lo que fija la sección 8 y lo que fija el ADR 0013

La sección 8 fija la transacción, la respuesta de `/evaluar`, los niveles y los campos del caso. Lo que dejaba abierto se decidió en la fase 4 (ADR 0013):

- **Errores.** `{"id_transaccion": …, "error": {"tipo", "mensaje", "detalles"}}`. Tipos y códigos: `entrada_invalida` (422), `modelo_no_disponible` (503), `error_interno` (500), `caso_no_encontrado` (404), `caso_ya_revisado` (409) y `ruta_no_disponible` (404 o 405). En `POST /evaluar`, **cualquier** respuesta que no sea 200 (o la falta de respuesta) significa que la evaluación falló: n8n marca el caso `error_evaluacion` y lo deja pendiente de revisión, nunca `sin_alerta`.
- **Tipos.** Los números deben ser números JSON finitos: `"1500"` o `true` en `monto` son entrada inválida, igual que en el esquema.
- **Modelo no disponible.** Si la transacción trae `variables` y la API no tiene modelo cargado, responde 503. Si no las trae, el modelo no hacía falta: responde 200 con `modelo.evaluable: false`, `puntuacion: null` y `versiones.modelo: null` si no hay modelo.
- **Casos.** n8n envía el caso sin `id_caso`, `estado`, `decision_final` ni `revision`: los pone la API. Un caso `sin_alerta` queda `cerrado`; los demás, `pendiente_revision` con `decision_final: pendiente`. Toda alerta lleva al menos una razón.

## Respuestas de los webhooks de n8n (ADR 0014)

- **`POST /webhook/transaccion`** recibe una transacción (sección 8.2) y responde **200 con el caso registrado** (esquema `caso`), también cuando el nivel es `error_evaluacion`. Si la API no guarda el caso, responde **502** con `error_flujo`: `error.tipo = caso_no_registrado` y el caso calculado en `caso`.
- **`POST /webhook/revision`** recibe `{"id_caso", "decision", "revisor", "comentario"}`. Si `id_caso` no tiene la forma `c-` y 12 cifras hexadecimales, responde **422** (esquema `error`) sin llamar a la API. Si no, repite el código y el cuerpo de `POST /casos/{id}/revision` (200, 404, 409, 422). Si la API no responde, **502** con `error_flujo` (`revision_no_registrada`).

## Pruebas

`tests/contrato/` comprueba que los ejemplos de la sección 8 de `docs/spec.md` cumplen los esquemas y que las respuestas reales de la API también. El ejemplo de la sección 8.2 abrevia `variables` (V1, V2 y V28): la prueba lo completa, porque el contrato exige V1 a V28.

```
uv run pytest tests/contrato
```
