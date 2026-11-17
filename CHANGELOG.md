# Registro de cambios

Formato de [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y versiones [SemVer](https://semver.org/lang/es/) `0.y.z` hasta la ponencia.

Cada entrada indica su nivel de verificación: N1 (entorno de desarrollo), N2 (GitHub Actions) o N3 (computador de ejecución).

## [Sin publicar]

## [0.2.0] - 2026-11-17

Fase 2, datos y reglas. Sin modelo ni métricas todavía: todo lo comprobado aquí usa la muestra para pruebas o datos sintéticos, que no representan el fraude real.

### Añadido

- Paso `preparar` (`./fraude preparar`, y dentro de `todo`): descarga el ARFF de OpenML 1597 con su suma MD5 publicada, o usa el CSV de Kaggle dejado a mano; comprueba filas, fraudes y columnas; fija y verifica la huella SHA-256 del contenido; guarda la partición estratificada 56/14/30 antes de cualquier ajuste; deja `datos.json` (N1; N2 con la muestra; los datos reales esperan N3).
- `preparar` funciona sin la columna `Time`: lo anota y sigue (N1).
- Análisis exploratorio de la parte de ajuste en `eda/`: resumen y tres figuras (N1; N2 con la muestra).
- Motor de reglas deterministas `MONTO_ALTO` y `MONTO_ALTO_UBICACION_INUSUAL`, con razón en texto y «no evaluable» cuando faltan datos; la de ubicación solo se aplica a datos sintéticos (N1).
- Generador sintético de ubicación en `datos/sinteticos/`, separado de los originales, con comprobación funcional de la regla y sin métricas de desempeño (N1; N2).
- Muestra para pruebas y opción `--muestra` en `preparar`, `todo` y `./fraude todo` (N1; N2).
- Forma de la transacción del contrato 8.2 validada con Pydantic (N1).
- La evidencia incluye `datos.json`, `eda/` y las versiones de las bibliotecas de datos (N1; N2).

### Cambiado

- `config/reglas.yaml` pasa a la versión 0.2.0. `config/modelo.yaml` guarda también los parámetros de datos, partición, muestra y sintéticos.
- La CI ejecuta `todo --muestra` y comprueba `datos.json`, `eda/` y los datos sintéticos.
- Una sesión nueva de `./fraude todo` no arrastra `datos.json` ni `eda/` de la anterior.

## [0.1.0] - 2026-11-17

Fase 1, cimientos. Sin datos, reglas, modelo ni página todavía: esta versión solo comprueba que el sistema arranca.

### Añadido

- Estructura del repositorio, `CLAUDE.md`, `README.md`, `EJECUTAR.md`, `docs/ESTADO.md`, `docs/supuestos.md`, `docs/architecture.md` y los ADR 0001 a 0011.
- API con `GET /salud` (N1 y N2).
- n8n fijado en la versión 2.47.7, con el flujo `ping` importado y publicado al arrancar; responde en `GET /webhook/ping` (N2).
- Línea de comandos `tareas` con `todo` y `evidencia`. Los pasos `preparar`, `entrenar`, `evaluar` y `demostrar` existen pero avisan de la fase en que llegan (N1 y N2).
- Evidencia mínima: `RESUMEN.md`, `anfitrion.json`, `entorno.json`, `version.json`, `errores.json`, `registros/`, `OBSERVACIONES.md`, `capturas/` y el `.zip` (N1 y N2).
- Guion `./fraude` para Omarchy 4: detecta si Docker pide `sudo`, deja los archivos a nombre del usuario, recoge los datos del sistema y guarda los registros si algo falla (N1 con Docker simulado; N2 sin `sudo` y con `sudo ./fraude`; el caso real de Omarchy espera N3).
- Integración continua en GitHub Actions: estilo, pruebas unitarias, `shellcheck`, construcción de imágenes y flujo `ping` de punta a punta.
- Archivos de configuración `config/reglas.yaml`, `config/modelo.yaml` y `config/decision.yaml`.

[Sin publicar]: https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/compare/main...HEAD
[0.2.0]: https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/pull/3
[0.1.0]: https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/pull/1
