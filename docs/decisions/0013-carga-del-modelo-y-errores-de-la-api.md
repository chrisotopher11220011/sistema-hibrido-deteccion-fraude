# ADR 0013: Carga del modelo en la API, respuestas de error y forma de los casos

- **Estado:** Aceptada
- **Fecha:** 2026-11-17
- **Fase en la que se aplica:** 4

## Contexto

La sección 8 fija la transacción, la respuesta de `POST /evaluar`, los niveles y los campos del caso, y deja para quien construya «cómo comparte `tareas` el modelo con `api` y cómo lo recarga la API» (sección 22). Tampoco fija qué responde la API cuando no puede evaluar, ni el cuerpo exacto de `POST /casos` y `GET /casos`. La sección 12 sí exige que una evaluación fallida o una entrada inválida terminen en `error_evaluacion` y pendientes de revisión, nunca en `sin_alerta`.

Dos hechos de la ejecución condicionan la carga del modelo: el servicio `api` arranca antes de que `tareas entrenar` deje el modelo, y comparten la carpeta `datos/` por un volumen.

## Decisión

**Modelo.** La API lee el artefacto que deja `entrenar` en `datos/modelo/` (conjunto real) o `datos/muestra/modelo/` (muestra). `FRAUDE_MODELO` elige cuál: `auto` (por defecto) usa el real si existe y si no el de la muestra; `real` y `muestra` fuerzan uno. En cada consulta compara la firma de los archivos (contenido de `modelo.json`, fecha y tamaño de `modelo.joblib`) y, si cambió, vuelve a cargar con la comprobación de huella de `modelo.cargar_artefacto`. No se carga un modelo cuyo entrenamiento no terminó bien o cuyas variables no son las de `config/modelo.yaml`. `GET /salud` informa si hay modelo, cuál (fuente y versión), si es reportable y, si no hay, por qué.

**Cuándo falta el modelo.** Si la transacción trae `variables` y no hay modelo, la evaluación no puede hacerse: la API responde 503 `modelo_no_disponible`. Si no las trae, el modelo no hacía falta (sección 8.2): responde 200 con `modelo.evaluable: false`, `puntuacion: null`, `anomalia` y `anomalia_alta` en falso, los umbrales del modelo cargado o `null`, y `versiones.modelo` con la versión cargada o `null`.

**Errores.** Toda respuesta que no es 2xx lleva `{"id_transaccion", "error": {"tipo", "mensaje", "detalles"}}`, con `entrada_invalida` (422), `modelo_no_disponible` (503), `error_interno` (500), `caso_no_encontrado` (404) y `caso_ya_revisado` (409). `id_transaccion` se recupera del cuerpo cuando venía como texto. Para n8n la regla es simple: si `POST /evaluar` no responde 200, el caso es `error_evaluacion`.

**Contribuciones.** Solo cuando `anomalia` es verdadera (sección 11, «para cada alerta»), con el explicador SHAP creado una vez por modelo cargado.

**Casos.** n8n envía a `POST /casos` lo que calculó (esquema `caso_nuevo`); la API añade `id_caso` (`c-` y 12 cifras hexadecimales), `estado`, `decision_final`, `revision` y, si falta, `fecha_procesamiento`, y responde 201 con el caso completo. En un caso `error_evaluacion` pueden faltar `id_transaccion`, `origen`, `monto` y `senales`; en los demás son obligatorios. Toda alerta lleva al menos una razón. Las señales se guardan tal como las devolvió `/evaluar`. `POST /casos/{id}/revision` acepta `sospecha_confirmada` o `sospecha_descartada` una sola vez y solo sobre casos `pendiente_revision`. `GET /casos` devuelve `{"total", "casos"}` del más reciente al más antiguo, con filtros `estado` y `limite` (1 a 1.000, 100 por defecto). La base es `datos/casos/casos.sqlite` (`FRAUDE_BD_CASOS` la cambia).

**Contratos.** Todo lo anterior y la sección 8 quedan como esquemas JSON 2020-12 en `docs/contratos/`, con pruebas que comprueban los ejemplos de `docs/spec.md` y las respuestas reales de la API.

## Consecuencias

- `./fraude todo` funciona sin reiniciar la API después de entrenar.
- n8n no necesita conocer los motivos del fallo para clasificar: le basta el código; el cuerpo queda como razón del caso.
- Una transacción sintética sigue evaluándose aunque no haya modelo; una original con variables no, y queda pendiente de revisión.
- Si existen los dos modelos, `auto` usa el real aunque la última sesión haya sido con `--muestra`. `/salud` lo dice; `FRAUDE_MODELO=muestra` lo evita.
- La base de casos acumula todas las sesiones; `casos.csv` y `revisiones.csv` llevan la versión del modelo y del flujo de cada caso para separarlas.
- Es una ampliación de lo que la sección 8 dejaba abierto, no un cambio de contrato: los campos fijados en la sección 8 no cambian.
