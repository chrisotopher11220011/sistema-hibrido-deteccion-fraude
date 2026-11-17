# ADR 0007: La página habla con n8n a través de la API

- **Estado:** Aceptada
- **Fecha:** 2026-11-16
- **Fase en la que se aplica:** 6

## Contexto

La página de simulación debe enviar transacciones al webhook de n8n y decisiones al webhook de revisión. Si el navegador llamara a n8n directamente, cruzaría orígenes (puerto 8000 hacia puerto 5678) y dependería de la configuración de CORS de n8n.

## Decisión

La página solo llama a la API, que la sirve. Las rutas `POST /simulacion/transacciones` y `POST /simulacion/revisiones` reenvían a los webhooks de n8n por la red interna de Compose.

## Consecuencias

- Sin problemas entre orígenes y sin configurar CORS en n8n.
- Un solo punto donde registrar lo enviado y lo respondido (`simulacion.json`).
- La latencia que ve la página incluye el salto por la API; la del flujo se mide aparte en `flujo.json`.
