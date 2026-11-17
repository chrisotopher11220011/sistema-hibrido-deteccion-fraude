# Supuestos y su estado

Quien desarrolla no ejecuta el sistema completo. Esta lista dice qué se da por cierto sin haberlo visto en el computador de ejecución y cómo se comprobará. Estados: **pendiente**, **confirmado** o **refutado**. Solo la evidencia de una ejecución N3 confirma o refuta, salvo S10, que es un supuesto sobre N2.

- **Última actualización:** 2026-11-17 (UTC), al cerrar la fase 3.
- **Evidencia N3 recibida hasta hoy:** ninguna.

| N.º | Supuesto | Cómo se comprueba | Estado | Notas |
|---|---|---|---|---|
| S1 | Docker y Docker Compose están instalados y en marcha en Omarchy 4 | `anfitrion.json` | Pendiente | El manual de Omarchy lo afirma (leído el 2026-11-16) |
| S2 | Los puertos 5678 y 8000 están libres | Arranque; `anfitrion.json` anota los que ya estaban en escucha antes de arrancar | Pendiente | Se cambian con `FRAUDE_PUERTO_API` y `FRAUDE_PUERTO_N8N` |
| S3 | OpenML responde y entrega el mismo conjunto que Kaggle | `datos.json`: 284.807 filas y 492 fraudes | Pendiente | Desde la fase 2, `preparar` lo comprueba. `huellas.sha256_contenido` no depende del formato ni de `Time`: si alguien prepara también con el CSV de Kaggle y sale la misma huella, el supuesto queda confirmado del todo |
| S4 | La versión fijada de n8n importa y activa los flujos sin pasos manuales | N2 y, en N3, `RESUMEN.md` y `registros/n8n.log` | Pendiente | **Comprobado en N2** con n8n 2.47.7, también en un segundo arranque con el volumen ya creado. Falta N3 |
| S5 | El entrenamiento termina en minutos | `modelo.json` (`tiempo_entrenamiento_s`) y `metricas.json` (`duracion_s`) | Pendiente | Ensayo N1 con un conjunto inventado del tamaño real (284.807 filas, 2 núcleos): `entrenar` cerca de 1 s y `evaluar` (mil remuestreos, diez semillas y partición temporal) unos 30 s, con menos de 1 GB de memoria. Son tiempos, no métricas: N3 lo confirma |
| S6 | El flujo responde cada transacción en pocos segundos | `flujo.json` | Pendiente | Fase 5 |
| S7 | Con `sudo`, los archivos de `resultados/` y `datos/` quedan a nombre del usuario | Punto de prueba A | Pendiente | En N2 se comprobó sin `sudo` y con `sudo ./fraude`. El caso de Omarchy (usuario normal y `sudo` solo para Docker) está probado en N1 con Docker simulado |
| S8 | La página funciona en el Chrome de Omarchy | `simulacion.json` y `capturas/` | Pendiente | Fase 6 |
| S9 | Tras instalar el paquete de NVIDIA para contenedores, Docker usa la gráfica; si no, se usa el procesador | `anfitrion.json` y `explicaciones.json` | Pendiente | Fase 7. `anfitrion.json` ya anota si Docker tiene el runtime de NVIDIA |
| S10 | GitHub Actions puede levantar n8n con Compose y probar el flujo | N2 desde la fase 1 | **Confirmado** | Es un supuesto sobre N2 y N2 lo demostró: CI en verde con el ping a n8n |
| S11 | El cortafuegos de Omarchy no impide llegar a los puertos publicados en `127.0.0.1` ni la comunicación entre contenedores | Punto de prueba A: `errores.json` | Pendiente | `tareas` llama a `api` y a `n8n` por la red de Compose, y `./fraude estado` por `127.0.0.1` |
| S12 | Los contenedores resuelven nombres y salen a internet para descargar datos e imágenes | Punto de prueba A y `datos.json` | Pendiente | Desde la versión 0.2.0, `./fraude todo` descarga el conjunto desde el contenedor `tareas`: `datos.json` con `fuente: openml` y `estado: ok` lo confirma |

## Supuestos nuevos de la fase 1

| N.º | Supuesto | Cómo se comprueba | Estado |
|---|---|---|---|
| S13 | La versión de Omarchy puede leerse con `omarchy-version` o del archivo `version` de su carpeta de instalación | `anfitrion.json`: campo `omarchy` | Pendiente. Si queda «desconocida», se corrige con la evidencia |
| S14 | `xdg-open` abre el navegador por defecto en Omarchy | Punto de prueba A: `OBSERVACIONES.md` | Pendiente. Si falla, el guion muestra la dirección para abrirla a mano |

## Supuestos nuevos de la fase 2

| N.º | Supuesto | Cómo se comprueba | Estado |
|---|---|---|---|
| S15 | El ARFF de OpenML 1597 se lee con el lector del proyecto: 31 atributos, `Class` nominal con `0` y `1`, valores numéricos separados por comas. El lector acepta comillas o su ausencia y la falta de `Time` | `datos.json`: `estado: ok`, `columnas` y `tiene_time` | Pendiente. Metadatos de OpenML leídos el 2026-11-17; el archivo en sí no pudo verse desde el entorno de desarrollo |
| S16 | El archivo que sirve OpenML coincide con la suma MD5 que publica (`178bcf9b…`) | `datos.json`: `huellas.md5_coincide` | Pendiente. Si no coincide, `preparar` prueba la otra dirección y, si tampoco, falla sin dejar archivos a medias |
| S17 | `preparar` con el conjunto real tarda segundos y cabe con holgura en 16 GB | `datos.json`: `duracion_s` | Pendiente. Ensayo N1 con un archivo inventado del mismo tamaño (168 MB): unos 2 s por ejecución, sin contar la descarga, y menos de 1 GB de memoria |

## Supuestos nuevos de la fase 3

| N.º | Supuesto | Cómo se comprueba | Estado |
|---|---|---|---|
| S18 | Con las versiones fijadas en `uv.lock`, SHAP explica exactamente la puntuación de Isolation Forest (la suma de contribuciones reconstruye `score_samples`) | Prueba `test_aditividad_con_la_version_instalada` en N1 y N2 | **Comprobado en N1 y N2** con scikit-learn 1.9.1 y SHAP 0.54.1. La imagen usa el mismo `uv.lock` |
| S19 | Con los datos reales, la validación tiene fraudes suficientes para elegir los umbrales (se esperan unos 69) y la partición temporal tiene fraudes en sus tres tramos | `modelo.json` (`datos.fraudes_validacion`) y `metricas.json` (`temporal.partes`) | Pendiente. Si un tramo temporal no tiene fraudes, la partición temporal queda como `fallo` con su motivo y el resto sigue |
| S20 | `k = 100` es un cupo razonable de casos para un revisor | `metricas.json` (`protocolo.k_revision`) | Pendiente. Valor del manual de la ULB (por día y por tarjetas); aquí se aplica a transacciones. Se revisa con el equipo antes de la ponencia |


## Supuestos nuevos de la fase 4

| N.º | Supuesto | Cómo se comprueba | Estado |
|---|---|---|---|
| S21 | La API, que arranca antes que `entrenar`, ve por el volumen `datos/` el modelo que deja `tareas` y lo carga sin reiniciarse | N2: `tests/punta_a_punta/comprobar_api.py` tras `todo --muestra`. N3: `/salud` con `"cargado": true` y `casos.csv` con `version_modelo` | **Comprobado en N2** ([ejecución](https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/actions/runs/44110435779)) y en N1. Falta verlo en Omarchy 4 (N3), aunque el mecanismo es el mismo volumen de Compose |
| S22 | SQLite funciona en el volumen `datos/` de Omarchy 4 con el usuario de quien ejecuta (bloqueos de archivo incluidos) | N2 en Linux de GitHub; N3: `casos.csv` y `revisiones.csv` en la evidencia del punto C | Comprobado en N2 (Linux de GitHub, [ejecución](https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/actions/runs/44110435779)). Pendiente en Omarchy 4 (N3) |
| S23 | Evaluar una transacción con el modelo, incluidas las contribuciones SHAP de una anomalía, tarda mucho menos que el tiempo límite de n8n | N3: latencias de `flujo.json` (fase 5) | **Comprobado en N2 con la muestra** ([ejecución](https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/actions/runs/44131224953)): ninguna transacción del lote superó el tiempo límite de 10 s; la más lenta fue la primera tras arrancar (unos 5 s, al crear el explicador SHAP). Pendiente con el modelo real en Omarchy 4 (N3) |


## Supuestos nuevos de la fase 5

| N.º | Supuesto | Cómo se comprueba | Estado |
|---|---|---|---|
| S24 | n8n 2.47.7 ejecuta las expresiones y los nodos de los flujos como el simulador de N1 (Switch con la primera regla, salida de error, reintentos, expresiones con funciones flecha) | N2: `demostrar` con paridad total y `comprobar_flujos.py` en sus ramas de error | **Comprobado en N2** ([ejecución](https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/actions/runs/44131224953)): paridad 124/124 en las tres ejecuciones de `todo`, y las ramas sin modelo, entrada inválida, revisión y API detenida respondieron lo esperado. En N3 se repite con el lote real |
| S25 | Con la API detenida, n8n agota los reintentos y responde en menos de un minuto, sin dejar al cliente colgado | N2: `comprobar_flujos.py --api-detenida` | **Comprobado en N2**: 502 con el caso en unos 22 s (el nombre `api` deja de resolverse). En Omarchy 4 puede variar con su DNS |
| S26 | El lote de la muestra recorre los niveles que importan para la paridad (sin alerta, revisión, prioritaria y error) | N2: `flujo.json` (`niveles_n8n`) | **Comprobado en N2**. Con el lote real (N3) los niveles dependerán del modelo; la paridad exhaustiva sobre todas las combinaciones está en N1 |
