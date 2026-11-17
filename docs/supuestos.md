# Supuestos y su estado

Quien desarrolla no ejecuta el sistema completo. Esta lista dice qué se da por cierto sin haberlo visto en el computador de ejecución y cómo se comprobará. Estados: **pendiente**, **confirmado** o **refutado**. Solo la evidencia de una ejecución N3 confirma o refuta, salvo S10, que es un supuesto sobre N2.

- **Última actualización:** 2026-11-17 (UTC), al cerrar la fase 1.
- **Evidencia N3 recibida hasta hoy:** ninguna.

| N.º | Supuesto | Cómo se comprueba | Estado | Notas |
|---|---|---|---|---|
| S1 | Docker y Docker Compose están instalados y en marcha en Omarchy 4 | `anfitrion.json` | Pendiente | El manual de Omarchy lo afirma (leído el 2026-11-16) |
| S2 | Los puertos 5678 y 8000 están libres | Arranque; `anfitrion.json` anota los que ya estaban en escucha antes de arrancar | Pendiente | Se cambian con `FRAUDE_PUERTO_API` y `FRAUDE_PUERTO_N8N` |
| S3 | OpenML responde y entrega el mismo conjunto que Kaggle | `datos.json`: 284.807 filas y 492 fraudes | Pendiente | Fase 2 |
| S4 | La versión fijada de n8n importa y activa los flujos sin pasos manuales | N2 y, en N3, `RESUMEN.md` y `registros/n8n.log` | Pendiente | **Comprobado en N2** con n8n 2.47.7, también en un segundo arranque con el volumen ya creado. Falta N3 |
| S5 | El entrenamiento termina en minutos | `modelo.json` | Pendiente | Fase 3 |
| S6 | El flujo responde cada transacción en pocos segundos | `flujo.json` | Pendiente | Fase 5 |
| S7 | Con `sudo`, los archivos de `resultados/` y `datos/` quedan a nombre del usuario | Punto de prueba A | Pendiente | En N2 se comprobó sin `sudo` y con `sudo ./fraude`. El caso de Omarchy (usuario normal y `sudo` solo para Docker) está probado en N1 con Docker simulado |
| S8 | La página funciona en el Chrome de Omarchy | `simulacion.json` y `capturas/` | Pendiente | Fase 6 |
| S9 | Tras instalar el paquete de NVIDIA para contenedores, Docker usa la gráfica; si no, se usa el procesador | `anfitrion.json` y `explicaciones.json` | Pendiente | Fase 7. `anfitrion.json` ya anota si Docker tiene el runtime de NVIDIA |
| S10 | GitHub Actions puede levantar n8n con Compose y probar el flujo | N2 desde la fase 1 | **Confirmado** | Es un supuesto sobre N2 y N2 lo demostró: CI en verde con el ping a n8n |
| S11 | El cortafuegos de Omarchy no impide llegar a los puertos publicados en `127.0.0.1` ni la comunicación entre contenedores | Punto de prueba A: `errores.json` | Pendiente | `tareas` llama a `api` y a `n8n` por la red de Compose, y `./fraude estado` por `127.0.0.1` |
| S12 | Los contenedores resuelven nombres y salen a internet para descargar datos e imágenes | Punto de prueba A y `datos.json` | Pendiente | En A solo se prueba la descarga de imágenes y la resolución de nombres entre contenedores; la salida a internet desde un contenedor se prueba en la fase 2 |

## Supuestos nuevos de la fase 1

| N.º | Supuesto | Cómo se comprueba | Estado |
|---|---|---|---|
| S13 | La versión de Omarchy puede leerse con `omarchy-version` o del archivo `version` de su carpeta de instalación | `anfitrion.json`: campo `omarchy` | Pendiente. Si queda «desconocida», se corrige con la evidencia |
| S14 | `xdg-open` abre el navegador por defecto en Omarchy | Punto de prueba A: `OBSERVACIONES.md` | Pendiente. Si falla, el guion muestra la dirección para abrirla a mano |
