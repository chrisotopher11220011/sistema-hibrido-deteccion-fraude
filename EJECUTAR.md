# Cómo ejecutar el prototipo en Omarchy 4

Esta guía es para quien ejecuta el sistema en su computador. No hace falta saber programar ni instalar nada: Omarchy 4 ya trae Docker, Docker Compose, Git y el navegador.

**Versión 0.1.0 (punto de prueba A).** Esta versión solo comprueba que el sistema arranca en tu equipo. Toma unos cinco minutos, más la descarga de la primera vez. Aún no hay página de simulación ni detección de fraude.

## Antes de empezar

- Conexión a internet: la primera vez se descargan imágenes de Docker.
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
4. `Paso 2 de 3: ejecutar los pasos del proyecto.` En esta versión cada paso solo avisa de que llega en una fase posterior.
5. `Paso 3 de 3: evidencia.` y una línea como `Evidencia lista: resultados/20261117T153000Z_ab12cd3/ y resultados/20261117T153000Z_ab12cd3.zip`.
6. `Todo termino bien.`

Si en lugar de eso aparece `ERROR`, **no intentes arreglarlo**: el guion ya guardó lo necesario. Sigue con el paso 4 y devuelve la carpeta tal cual.

## 3. Mirar que responde

```
./fraude estado
./fraude abrir
```

**Deberías ver:** con `estado`, dos líneas: `api responde en …` y `n8n responde en …`. Con `abrir`, el navegador en `http://localhost:8000`. En esta versión la página aún no existe, así que mostrará un mensaje corto de «no encontrado»; para ver algo, entra en `http://localhost:8000/salud`, que debe mostrar `"estado":"ok"`.

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

## Si algo va mal

| Qué ves | Qué hacer |
|---|---|
| `No pude obtener permisos con sudo` | Vuelve a ejecutar `./fraude todo` y escribe tu contraseña de usuario |
| `Docker no responde ni con sudo` | `sudo systemctl start docker` y repite |
| Un mensaje de que el puerto 8000 o 5678 ya está en uso | Usa otros puertos. Escribe una vez `export FRAUDE_PUERTO_API=8010 FRAUDE_PUERTO_N8N=5690` y, en esa misma terminal, repite `./fraude todo`. Las demás órdenes (`estado`, `abrir`, `evidencia`, `apagar`) deben ejecutarse en esa misma terminal |
| Se queda mucho tiempo en el paso 1 | La primera descarga depende de tu conexión. Si n8n no responde pasados entre cuatro y siete minutos, el guion lo da por fallido y guarda los registros |
| Cualquier otro `ERROR` | Ejecuta `./fraude evidencia` y envía el `.zip`. Con eso basta para diagnosticarlo |

Ejecutar `./fraude todo` varias veces no rompe nada. Para volver a empezar de cero: `./fraude apagar` y de nuevo `./fraude todo`.

## Qué deja en tu equipo

- Imágenes y un volumen de Docker del proyecto `fraude`.
- Las carpetas `datos/` y `resultados/` dentro del repositorio, a tu nombre.
- Nada queda visible en la red: los puertos se publican solo en `127.0.0.1`.

Para borrar todo al terminar el proyecto: `./fraude apagar`, luego `sudo docker compose down --volumes --rmi local` dentro de la carpeta, y borra la carpeta.

## Más adelante

- **Página de simulación:** llega en la fase 6. Podrás abrirla en ventana propia con *Install > Web App* del menú de Omarchy.
- **Grabar la pantalla:** `Alt + Print Screen` inicia y detiene la grabación; el video queda en `~/Videos`.
- **Explicación con LLM local (fase 7, opcional):** pedirá una preparación única de la gráfica para Docker (`nvidia-container-toolkit`). Se documentará aquí cuando esa fase la verifique.
