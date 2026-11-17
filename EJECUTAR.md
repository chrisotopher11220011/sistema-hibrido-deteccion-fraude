# Cómo ejecutar el prototipo en Omarchy 4

Esta guía es para quien ejecuta el sistema en su computador. No hace falta saber programar ni instalar nada: Omarchy 4 ya trae Docker, Docker Compose, Git y el navegador.

**Versión 0.4.0 — punto de prueba B.** Comprueba que el sistema arranca en tu equipo, descarga los datos reales, entrena el modelo de detección de anomalías (Isolation Forest) y calcula las primeras métricas. Toma unos diez minutos, más las descargas de la primera vez (imágenes de Docker y unos 150 MB de datos). Aún no hay página de simulación. Desde la versión 0.4.0, la dirección `http://localhost:8000/salud` también dice si la API cargó el modelo entrenado.

## Antes de empezar

- Conexión a internet: la primera vez se descargan imágenes de Docker y el conjunto de datos (unos 150 MB, desde OpenML; no hace falta cuenta).
- Espacio en disco: con 1 GB libre sobra para los datos.
- Tu contraseña de usuario: Docker la pedirá a través de `sudo`. Es lo normal en Omarchy 4, donde tu usuario no pertenece al grupo `docker`. **No hace falta** activar *Setup > Security > Sudoless Docker* ni cambiar nada de la seguridad del sistema.
- El repositorio es privado. Si `git clone` pide credenciales, ejecuta antes `gh auth login` y sigue sus pasos con tu cuenta de GitHub.

## 1. Descargar

Abre una terminal y escribe:

```
git clone https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude
cd sistema-hibrido-deteccion-fraude
```

**Deberías ver:** una carpeta nueva con archivos como `fraude`, `compose.yaml` y `EJECUTAR.md`.

## 2. Ejecutar

```
./fraude todo
```

**Deberías ver**, en este orden (todas las líneas del guion empiezan por `[fraude]`):

1. `Docker pide permisos de administrador (es lo normal en Omarchy 4).` y después la petición de tu contraseña. Al escribirla no se ve nada en pantalla; es normal.
2. `Paso 1 de 3: construir y arrancar los servicios (api y n8n).` Aquí se descargan las imágenes. La primera vez puede tardar varios minutos; las siguientes, menos de uno.
3. `Servicios en marcha: la API y n8n responden.`
4. `Paso 2 de 3: ejecutar los pasos del proyecto.` Primero `[preparar] Descargando el conjunto de OpenML (unos 150 MB)...` y, al terminar, una línea como `[preparar] Listo. Fuente openml: 284807 transacciones, 492 fraudes; particion creada.` Si la columna `Time` no llega, verás un `AVISO` sobre ella: es esperable y el paso sigue. Después `[entrenar] Listo. Modelo ...; umbrales elegidos en validacion (modelo.json).` (unos segundos) y `[evaluar] Listo. Protocolo de la seccion 15 en ... s: ...` (uno o dos minutos: repite el entrenamiento con diez semillas y hace mil remuestreos). El paso `demostrar` solo avisa de que llega en la fase 5.
5. `Paso 3 de 3: evidencia.` y una línea como `Evidencia lista: resultados/20261117T153000Z_ab12cd3/ y resultados/20261117T153000Z_ab12cd3.zip`.
6. `Todo termino bien.`

Si en lugar de eso aparece `ERROR`, **no intentes arreglarlo**: el guion ya guardó lo necesario. Sigue con el paso 4 y devuelve la carpeta tal cual.

## 3. Mirar que responde

```
./fraude estado
./fraude abrir
```

**Deberías ver:** con `estado`, dos líneas: `api responde en …` y `n8n responde en …`. Con `abrir`, el navegador en `http://localhost:8000`. En esta versión la página aún no existe, así que mostrará un mensaje corto de «no encontrado»; para ver algo, entra en `http://localhost:8000/salud`, que debe mostrar `"estado":"ok"` y, después de entrenar, `"cargado":true` dentro de `"modelo"`.

Si quieres, haz una captura con `Print Screen`. Se guarda sola en `~/Pictures/Screenshots` y el siguiente paso la recoge.

## 4. Anotar y reunir la evidencia

1. Abre `resultados/en_curso/OBSERVACIONES.md` con cualquier editor y escribe con tus palabras qué hiciste, qué viste, cuánto tardó y qué te confundió. El cuestionario del final déjalo en blanco por ahora.
2. Ejecuta:

```
./fraude evidencia
```

**Deberías ver:** `Evidencia lista: resultados/<fecha>_<código>/ y resultados/<fecha>_<código>.zip`.

## 5. Devolver y apagar

1. Envía a Christopher el archivo `.zip` más reciente de la carpeta `resultados/`. Contiene texto e imágenes pequeñas, sin contraseñas.
2. Detén todo:

```
./fraude apagar
```

**Deberías ver:** `Todo detenido. Los resultados siguen en resultados/.`

## Qué comprueba esta prueba

| Pregunta | Dónde queda la respuesta |
|---|---|
| ¿Docker funciona con `sudo` en tu Omarchy? | `anfitrion.json` |
| ¿Los archivos quedan a tu nombre y no de `root`? | Puedes abrir y editar `OBSERVACIONES.md` sin `sudo` |
| ¿El cortafuegos deja llegar a los puertos locales y deja hablar a los contenedores? | `RESUMEN.md` y `errores.json` |
| ¿n8n arranca y publica sus flujos sin pasos manuales? | `RESUMEN.md` y `registros/n8n.log` |
| ¿Los puertos 8000 y 5678 estaban libres? | `anfitrion.json` y `errores.json` |
| ¿Los contenedores salen a internet y OpenML entrega el conjunto esperado? | `datos.json`: 284.807 transacciones y 492 fraudes |
| ¿Cómo es el conjunto en la parte de ajuste? | `eda/` (resumen y figuras) |
| ¿El entrenamiento termina en minutos y cabe en tu equipo? | `modelo.json`: `tiempo_entrenamiento_s`; `metricas.json`: `duracion_s` |
| ¿Qué tal detectan las reglas, el modelo y el híbrido? | `comparativa.md`, `metricas.json` y `figuras/` (parte de prueba) |
| ¿Qué fraudes se escapan y qué falsas alarmas hay? | `analisis_errores/` (parte de validación) |

## Si algo va mal

| Qué ves | Qué hacer |
|---|---|
| `No pude obtener permisos con sudo` | Vuelve a ejecutar `./fraude todo` y escribe tu contraseña de usuario |
| `Docker no responde ni con sudo` | `sudo systemctl start docker` y repite |
| `[preparar] ERROR: ... No pude descargar el conjunto de OpenML` | El resto sigue igual. Si OpenML no responde, descarga `creditcard.csv` desde https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud (necesita cuenta de Kaggle), déjalo en `datos/crudos/creditcard.csv` dentro de la carpeta del proyecto y repite `./fraude todo` |
| `[preparar] ERROR` por conteos, suma MD5 o huella | No borres nada. Ejecuta `./fraude evidencia` y envía el `.zip`: `datos.json` dice qué no coincidió |
| Un mensaje de que el puerto 8000 o 5678 ya está en uso | Usa otros puertos. Escribe una vez `export FRAUDE_PUERTO_API=8010 FRAUDE_PUERTO_N8N=5690` y, en esa misma terminal, repite `./fraude todo`. Las demás órdenes (`estado`, `abrir`, `evidencia`, `apagar`) deben ejecutarse en esa misma terminal |
| Se queda mucho tiempo en el paso 1 | La primera descarga depende de tu conexión. Si n8n no responde pasados entre cuatro y siete minutos, el guion lo da por fallido y guarda los registros |
| `[entrenar] ERROR` o `[evaluar] ERROR` | Casi siempre es consecuencia de un `[preparar] ERROR` anterior: arréglalo primero. Si `preparar` terminó bien, ejecuta `./fraude evidencia` y envía el `.zip`: `modelo.json` y `metricas.json` dicen qué pasó |
| Cualquier otro `ERROR` | Ejecuta `./fraude evidencia` y envía el `.zip`. Con eso basta para diagnosticarlo |

Ejecutar `./fraude todo` varias veces no rompe nada. Para volver a empezar de cero: `./fraude apagar` y de nuevo `./fraude todo`.

## Qué deja en tu equipo

- Imágenes y un volumen de Docker del proyecto `fraude`.
- Las carpetas `datos/` (unos 150 MB con el conjunto descargado) y `resultados/` dentro del repositorio, a tu nombre.
- Nada queda visible en la red: los puertos se publican solo en `127.0.0.1`.

Para borrar todo al terminar el proyecto: `./fraude apagar`, luego `sudo docker compose down --volumes --rmi local` dentro de la carpeta, y borra la carpeta.

## Más adelante

- **Página de simulación:** llega en la fase 6. Podrás abrirla en ventana propia con *Install > Web App* del menú de Omarchy.
- **Grabar la pantalla:** `Alt + Print Screen` inicia y detiene la grabación; el video queda en `~/Videos`.
- **Explicación con LLM local (fase 7, opcional):** pedirá una preparación única de la gráfica para Docker (`nvidia-container-toolkit`). Se documentará aquí cuando esa fase la verifique.
