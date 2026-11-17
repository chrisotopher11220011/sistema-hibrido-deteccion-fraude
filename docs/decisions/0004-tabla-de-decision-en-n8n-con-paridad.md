# ADR 0004: Tabla de decisión en n8n con copia en Python y prueba de paridad

- **Estado:** Aceptada
- **Fecha:** 2026-11-16
- **Fase en la que se aplica:** 1 (versión y arranque) y 5 (tabla y paridad)

## Contexto

La ponencia sitúa en n8n la combinación de señales. Pero la evaluación fuera de línea de cientos de miles de transacciones no puede pasar una a una por n8n, y el flujo se escribe como JSON sin editor visual, de modo que su corrección debe comprobarse de forma automática. Las órdenes de n8n cambian entre versiones. Verificado en la documentación oficial el 2026-11-16: la versión estable es la 2.47.7 (la 3.0 está en beta desde el 27 de octubre y su estable se espera para diciembre); `n8n import:workflow` deja sin publicar lo que importa y sobrescribe el flujo con el mismo `id`; `n8n publish:workflow --id=<ID>` publica y no admite `--all`; `update:workflow` está en desuso; con n8n detenido, la publicación se aplica al arrancar.

## Decisión

La tabla de la sección 8.4 se aplica en n8n, en el nodo «Clasificar nivel», con nodos If y Switch si la expresan sin ambigüedad. Hay una copia en Python para evaluar fuera de línea. La prueba de paridad envía el mismo lote por los dos caminos y exige el mismo nivel en todos los casos.

Se fija la imagen `n8nio/n8n:2.47.7`. Cada flujo lleva un `id` fijo en su JSON y cada nodo Webhook un `webhookId` fijo. El contenedor arranca con `n8n/arranque.sh`, que importa los flujos, los publica uno por uno y solo entonces ejecuta `n8n start`. El contenedor se considera sano cuando `GET /webhook/ping` responde.

## Consecuencias

- La combinación de señales queda donde la ponencia dice, visible en el lienzo.
- Hay dos implementaciones de la misma tabla; la prueba de paridad es obligatoria y su fallo bloquea la versión.
- Sin pasos manuales en el editor: importar y publicar ocurre en cada arranque y es repetible.
- Pasar a n8n 3.x exigirá repetir la verificación de las órdenes y un cambio en este ADR.
- Los umbrales llegan en la respuesta de `/evaluar`, nunca por variables de entorno, porque los nodos Code no las leen por defecto.
