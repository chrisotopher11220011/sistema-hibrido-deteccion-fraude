# ADR 0010: Guion `./fraude` y permisos de Docker en Omarchy 4

- **Estado:** Aceptada
- **Fecha:** 2026-11-16
- **Fase en la que se aplica:** 1

## Contexto

Quien ejecuta no es quien desarrolla y debe poder hacerlo con un comando. Verificado en el manual oficial de Omarchy el 2026-11-16: Docker y Docker Compose vienen instalados; el usuario **no** está en el grupo `docker` (ese grupo equivale a administrador sin contraseña), así que los comandos se ejecutan con `sudo`; puede cambiarse en *Setup > Security > Sudoless Docker*. El cortafuegos bloquea el tráfico entrante y protege Docker con ufw-docker. Las capturas (`Print Screen`) se guardan en `~/Pictures/Screenshots`, carpeta que cambia con `OMASNAP_SCREENSHOT_DIR`.

Con `sudo`, los archivos que escribe un contenedor suelen quedar a nombre de `root`, y la persona no podría editarlos ni borrarlos. Además, solo el anfitrión puede leer los registros de Docker y los datos del sistema.

## Decisión

Un guion bash, `./fraude`, es la única pieza que habla con Docker en el computador de ejecución.

- **Permisos:** prueba `docker info`; si falla, usa `sudo` solo delante de `docker` y lo avisa. No pide cambiar la seguridad del sistema. El guion en sí corre como el usuario.
- **Propiedad de archivos:** crea `datos/` y `resultados/` antes de arrancar y pasa a Compose el UID y el GID del usuario (`FRAUDE_UID`, `FRAUDE_GID`), con los que corren `api` y `tareas`. Si alguien lanza `sudo ./fraude`, toma la identidad de `SUDO_UID` y al terminar devuelve la propiedad de ambas carpetas.
- **Evidencia del anfitrión:** escribe `anfitrion.json`, guarda los registros de cada servicio y copia las capturas de la sesión en `resultados/en_curso/`; `tareas evidencia` los incorpora.
- **Orden en `todo`:** `./fraude todo` llama a `tareas todo --sin-evidencia`, recoge registros y capturas y después llama a `tareas evidencia`, para que los registros sean posteriores a los pasos. Llamado directamente, `tareas todo` termina siempre con `evidencia`.
- **Fallos:** si los servicios no arrancan, guarda los registros y reúne la evidencia igualmente, con `--no-deps`.
- **Puertos:** se publican solo en `127.0.0.1`.

## Consecuencias

- Para el núcleo no se instala ni se configura nada en Omarchy.
- `sudo` puede volver a pedir la contraseña en ejecuciones largas.
- La opción `--sin-evidencia` de `tareas todo` es un añadido a la sección 8.8 de la especificación que no cambia el comportamiento por defecto.
- Que los archivos queden a nombre del usuario con el `sudo` real de Omarchy (S7) y que el cortafuegos no estorbe (S11) solo se confirman en el punto de prueba A. En la CI se comprueba sin `sudo` y con `sudo ./fraude`.
- La detección de la versión de Omarchy prueba varios caminos y anota cuál usó; si ninguno sirve, queda «desconocida» y se corrige con la evidencia.
