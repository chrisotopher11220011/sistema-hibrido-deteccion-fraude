# Cómo ejecutar el prototipo en Omarchy 4

Esta guía es para quien ejecuta el sistema en su computador. No hace falta saber programar ni instalar nada: Omarchy 4 ya trae Docker, Docker Compose, Git y el navegador.

**Versión 0.6.0 — punto de prueba C: el sistema completo con la página.** Además de lo que comprobaba el punto B (arranque, datos reales, entrenamiento y métricas), ahora usarás la **página de simulación**, que es lo que verá el público del congreso. Toma unos quince minutos de ejecución, más las descargas de la primera vez (imágenes de Docker y unos 150 MB de datos), y unos veinte minutos usando la página.

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
4. `Paso 2 de 3: ejecutar los pasos del proyecto.` Primero `[preparar] Descargando el conjunto de OpenML (unos 150 MB)...` y, al terminar, una línea como `[preparar] Listo. Fuente openml: 284807 transacciones, 492 fraudes; particion creada.` Si la columna `Time` no llega, verás un `AVISO` sobre ella: es esperable y el paso sigue. Después `[entrenar] Listo. Modelo ...; umbrales elegidos en validacion (modelo.json).` (unos segundos) y `[evaluar] Listo. Protocolo de la seccion 15 en ... s: ...` (uno o dos minutos: repite el entrenamiento con diez semillas y hace mil remuestreos). Por último `[demostrar] Listo. Lote de ... por n8n y por Python: paridad N/N; latencia mediana ... ms, p95 ... ms (flujo.json).` (uno o dos minutos): envía el lote de demostración por n8n y comprueba que n8n y Python clasifican igual cada transacción. Si las dos cifras de `paridad` no coinciden, el paso marca `ERROR`: no pasa nada, la evidencia lo recoge.
5. `Paso 3 de 3: evidencia.` y una línea como `Evidencia lista: resultados/20261117T153000Z_ab12cd3/ y resultados/20261117T153000Z_ab12cd3.zip`.
6. `Todo termino bien.`

Si en lugar de eso aparece `ERROR`, **no intentes arreglarlo**: el guion ya guardó lo necesario. Sigue con el paso 4 y devuelve la carpeta tal cual.

## 3. Usar la página de simulación

```
./fraude estado
./fraude abrir
```

**Deberías ver:** con `estado`, dos líneas: `api responde en …` y `n8n responde en …`. Con `abrir`, Chrome con la página **Simulador de verificación de transacciones** en `http://localhost:8000`. Si no se abre sola, escribe esa dirección en el navegador.

Haz lo siguiente, sin prisa, y fíjate en qué entiendes y qué no. Haz una captura con `Print Screen` en los pasos marcados con 📷: se guardan solas en `~/Pictures/Screenshots` y la evidencia las recoge.

1. **Antes de empezar.** Debajo de los botones verás «Listo para empezar» y cuántas transacciones tiene el lote (unas 126: originales con etiqueta, sintéticas de ubicación y algunas entradas inválidas a propósito). 📷
2. **Iniciar.** Pulsa **Iniciar simulación**. Cada segundo llega una transacción: la boleta muestra el monto, un sello con el nivel (*Sin alerta*, *Revisión recomendada*, *Alerta prioritaria* o *Error de evaluación*) y las razones. Un instante después aparece la **etiqueta real** del conjunto y si coincide. Los contadores, la matriz y las gráficas cambian solos. 📷 a mitad del lote.
3. **Pausar y revisar.** Pulsa **Pausar**. En la **Bandeja de revisión**, escribe un comentario en dos o tres casos y pulsa **Confirmar sospecha** o **Descartar sospecha**. Debe aparecer «Guardado: caso … revisado» y el caso sale de la bandeja.
4. **Continuar hasta el final.** Pulsa **Continuar simulación** (puedes subir la velocidad). Al terminar debe decir **Lote completo**. 📷
5. **Transacción manual.** En **Transacción manual** deja monto `1250`, país habitual `EC` y país `US`, y pulsa **Evaluar transacción**. El sello debe decir **Alerta prioritaria** con dos razones: monto alto, y monto alto con país distinto. Prueba también un monto pequeño o el mismo país.
6. **Modo presentación.** Pulsa **Modo presentación** (o la tecla `P`): todo se ve más grande, pensado para el proyector. 📷 Vuelve a pulsarlo para salir.
7. **Tema.** Pulsa **Tema** (o la tecla `T`) para pasar a claro y a oscuro. 📷 en el tema que no sea el tuyo.
8. **Ventana estrecha.** Pon la ventana en mosaico al lado de la terminal (como hace Hyprland al abrir otra ventana). La página debe verse en una columna, sin cortarse. 📷
9. **Solo con el teclado.** Recarga la página y, sin tocar el ratón, usa `Tab` para moverte, `Intro` para pulsar y `Espacio` para iniciar o pausar. Pulsa `?` para ver los atajos. Anota si en algún momento no sabías dónde estaba el foco.

Si algo no responde, la página dice qué pasa y qué hacer (por ejemplo, «n8n no responde. La simulación quedó en pausa.»). Anótalo y sigue.

Para la exposición, la página puede abrirse en ventana propia con *Install > Web App* del menú de Omarchy (`Super + Space`), con la dirección `http://localhost:8000`.

## 4. Anotar y reunir la evidencia

1. Abre `resultados/en_curso/OBSERVACIONES.md` con cualquier editor y escribe con tus palabras qué hiciste, qué viste, cuánto tardó y qué te confundió. **Esta vez llena también el cuestionario del final** (diez frases, de 1 a 5), pensando en la página.
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
| ¿n8n clasifica igual que Python cada transacción del lote y cuánto tarda? | `flujo.json`: `paridad` y `latencia_ms` |
| ¿Se registran los casos y quedan pendientes los que deben? | `casos.csv` |
| ¿Qué envió la página, qué respondió el sistema y cómo se compara con la etiqueta? | `simulacion.json` |
| ¿Se guardaron las revisiones que hiciste en la página? | `revisiones.csv` |
| ¿La página se ve bien en tu Chrome, en pantalla completa, en ventana estrecha y en modo presentación? | `capturas/` y `OBSERVACIONES.md` |
| ¿Es fácil de usar? | Cuestionario SUS en `OBSERVACIONES.md` |

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
| La página dice «Aún no hay lote de demostración» | El paso `demostrar` no llegó a generarlo. Ejecuta `./fraude todo` otra vez y recarga la página |
| La página dice «La API no responde» o «n8n no responde» | `./fraude estado`. Si algo está detenido, `./fraude todo` y recarga la página |
| Cualquier otro `ERROR` | Ejecuta `./fraude evidencia` y envía el `.zip`. Con eso basta para diagnosticarlo |

Ejecutar `./fraude todo` varias veces no rompe nada. Para volver a empezar de cero: `./fraude apagar` y de nuevo `./fraude todo`.

## Qué deja en tu equipo

- Imágenes y un volumen de Docker del proyecto `fraude`.
- Las carpetas `datos/` (unos 150 MB con el conjunto descargado) y `resultados/` dentro del repositorio, a tu nombre.
- Nada queda visible en la red: los puertos se publican solo en `127.0.0.1`.

Para borrar todo al terminar el proyecto: `./fraude apagar`, luego `sudo docker compose down --volumes --rmi local` dentro de la carpeta, y borra la carpeta.

## Más adelante

- **Grabar la pantalla:** `Alt + Print Screen` inicia y detiene la grabación; el video queda en `~/Videos`.
- **Explicación con LLM local (fase 7, opcional):** pedirá una preparación única de la gráfica para Docker (`nvidia-container-toolkit`). Se documentará aquí cuando esa fase la verifique.
