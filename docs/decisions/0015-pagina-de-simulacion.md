# ADR 0015: Página de simulación: rutas, registro de la sesión, etiqueta y capturas

- **Estado:** Aceptada
- **Fecha:** 2026-11-17
- **Fase en la que se aplica:** 6

## Contexto

La sección 13 describe la página y la sección 8.6 fija sus rutas (`GET /`, `GET /simulacion/lote`, `POST /simulacion/transacciones`, `POST /simulacion/revisiones`); el ADR 0007 decide que la página habla con n8n a través de la API. Quedaban abiertos: los cuerpos y errores de esas rutas, cómo se registra la sesión en `simulacion.json`, cómo se impide que la etiqueta real viaje al flujo, la herramienta de capturas automáticas (sección 22, «para quien construya») y cómo probar la página sin Docker en el entorno de desarrollo.

## Decisión

**Servir la página.** `GET /` devuelve `web/index.html` sin caché; `/recursos/` sirve el resto de `web/`. La imagen copia `web/` en `/app/web` (`FRAUDE_WEB`). Sin recursos externos: la fuente (Atkinson Hyperlegible Next, SIL OFL 1.1) va en `web/fuentes/`.

**Lote.** `GET /simulacion/lote` devuelve el archivo de `lote.py` de la fuente del modelo cargado; sin modelo, según `FRAUDE_MODELO` (`auto` prefiere el real). Si no existe: 404 `lote_no_disponible`, con «Ejecuta antes: ./fraude todo». Esquema `lote` en `docs/contratos/`.

**Etiqueta real.** La etiqueta va en cada elemento del lote, aparte de la transacción. La página solo envía `elemento.transaccion` y muestra la etiqueta después del veredicto. Como defensa añadida, `POST /simulacion/transacciones` rechaza con 422 `etiqueta_en_transaccion` un cuerpo con el campo `etiqueta_real`, sin reenviarlo, y el registro de la sesión no lo guarda.

**Reenvío.** El cuerpo de `POST /simulacion/transacciones` es la transacción tal cual, válida o no: una entrada inválida también va a n8n para que la página muestre la rama `error_evaluacion`. Un cuerpo que no es JSON recibe 422 `entrada_invalida` sin reenviarse. La API repite el código y el cuerpo de n8n (200 con el caso, 502 con el caso calculado). Si n8n no responde, o responde algo que no es JSON, la API devuelve 502 `n8n_no_disponible` sin `caso`. `POST /simulacion/revisiones` hace lo mismo con el webhook de revisión.

El reenvío corre en un hilo aparte (`run_in_threadpool`): n8n llama a `/evaluar` y `/casos` de la misma API mientras esta espera su respuesta, y bloquear el bucle de eventos sería un interbloqueo. Una prueba con un servidor real lo comprueba.

**Registro de la sesión.** La API anota cada intercambio en `resultados/en_curso/simulacion.jsonl`: fecha, sesión, número del elemento del lote, ruta, lo enviado (sin etiqueta), código, respuesta y latencia desde la API. La sesión y el número llegan en la consulta (`?sesion=…&n=…`), nunca dentro de la transacción. `tareas evidencia` escribe `simulacion.json`: sesiones con niveles, códigos, latencia y la comparación con la etiqueta (matrices con «cualquier alerta» y «solo prioritarias»), unida desde el lote por `id_transaccion` al reunir la evidencia, fuera del camino de evaluación. Siempre `reportable: false`: describe el lote mostrado, no sustituye a `comparativa.md`.

**Errores nuevos.** Tres tipos en el cuerpo de error del ADR 0013: `lote_no_disponible` (404), `etiqueta_en_transaccion` (422) y `n8n_no_disponible` (502).

**Capturas y accesibilidad.** Playwright con Chromium (`tests/punta_a_punta/comprobar_pagina.py`), en la CI tras `todo --muestra`: tres anchos (640, 1280 y 1920 px) por dos temas, más el modo presentación y los estados vacío y de error; recorrido solo con teclado; axe-core 4.14.1 con las etiquetas de WCAG 2.0, 2.1 y 2.2 A y AA. Las capturas se suben como artefacto `capturas-pagina`. Playwright y axe-core solo se instalan en la CI, no son dependencias del proyecto.

**N1 sin Docker.** `tests/punta_a_punta/n8n_de_pruebas.py` sirve los webhooks ejecutando los flujos reales con el simulador de la fase 5 y haciendo de verdad las peticiones a la API. Solo para el entorno de desarrollo; en N2 se usa n8n 2.47.7.

## Consecuencias

- La página puede probarse de punta a punta en N1 y en N2, y cada ejecución de la CI deja capturas para mirarlas.
- La etiqueta real tiene dos barreras: la página no la envía y la API la rechaza.
- `simulacion.json` permite reconstruir cada sesión de la demostración y su comparación con la etiqueta.
- La latencia de la página incluye el salto por la API (ADR 0007); la del flujo sigue en `flujo.json`.
- La CI tarda unos minutos más y necesita descargar Chromium y axe-core en cada ejecución.
