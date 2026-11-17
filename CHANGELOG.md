# Registro de cambios

Formato de [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y versiones [SemVer](https://semver.org/lang/es/) `0.y.z` hasta la ponencia.

Cada entrada indica su nivel de verificación: N1 (entorno de desarrollo), N2 (GitHub Actions) o N3 (computador de ejecución).

## [Sin publicar]

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

[Sin publicar]: https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/compare/54c0be4...HEAD
[0.1.0]: https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/pull/1
