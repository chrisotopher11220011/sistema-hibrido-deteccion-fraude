# Sistema híbrido de detección de fraude

Prototipo académico que simula la verificación de transacciones bancarias combinando **reglas deterministas**, **aprendizaje automático** (Isolation Forest) y **automatización con n8n**. Acompaña a la ponencia «Diseño de un sistema híbrido para la detección de fraude en transacciones financieras mediante reglas deterministas, aprendizaje automático y automatización con n8n».

No bloquea operaciones reales ni está pensado para producción. El sistema señala transacciones para revisión humana; no confirma fraudes.

## Estado

**Versión 0.2.0 — Fase 2, datos y reglas.** Además de los cimientos de la fase 1 (arranque con un comando, API con `/salud`, n8n con el flujo `ping`, evidencia e integración continua), existen la preparación de los datos (descarga verificada, partición y análisis exploratorio), el motor de reglas deterministas y los datos sintéticos de ubicación. Todavía **no hay** modelo ni página de simulación, y por tanto no hay ninguna cifra de desempeño.

El avance detallado está en [`docs/ESTADO.md`](docs/ESTADO.md) y los cambios en [`CHANGELOG.md`](CHANGELOG.md).

## Ejecutarlo

Pensado para Omarchy 4, que ya trae Docker y Docker Compose:

```
git clone https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude
cd sistema-hibrido-deteccion-fraude
./fraude todo
```

La guía paso a paso, con lo que debería verse en cada momento, está en [`EJECUTAR.md`](EJECUTAR.md).

| Comando | Qué hace |
|---|---|
| `./fraude todo` | Arranca los servicios, ejecuta los pasos que existen y reúne la evidencia |
| `./fraude todo --muestra` | Lo mismo con datos de prueba generados, sin descargar el conjunto real (sus cifras no se reportan) |
| `./fraude preparar` | Solo el paso de datos: descarga, verificación, partición y análisis exploratorio |
| `./fraude evidencia` | Reúne de nuevo la evidencia |
| `./fraude abrir` | Abre la página en el navegador |
| `./fraude estado` | Dice qué servicios están en marcha |
| `./fraude apagar` | Detiene todo |

## Cómo se trabaja

Quien desarrolla no ejecuta el sistema completo: se construye con supuestos explícitos, un compañero lo ejecuta y los archivos de evidencia que devuelve guían la versión siguiente. Toda afirmación indica en qué nivel está comprobada:

| Nivel | Dónde | Qué cubre |
|---|---|---|
| N1 | Entorno de desarrollo | Pruebas unitarias |
| N2 | GitHub Actions | Lo anterior en limpio, las imágenes y n8n de punta a punta |
| N3 | Computador de ejecución | Datos reales, entrenamiento, métricas y demostración |

Lo que no pasó por N3 es un supuesto, no un resultado. La lista está en [`docs/supuestos.md`](docs/supuestos.md).

## Documentos

- [`docs/spec.md`](docs/spec.md): especificación vigente. Manda sobre todo lo demás.
- [`docs/architecture.md`](docs/architecture.md): arquitectura en una página.
- [`docs/decisions/`](docs/decisions/): decisiones de arquitectura (ADR).
- [`docs/planes/`](docs/planes/): plan de cada fase.

## Desarrollo

```
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Python 3.12 o superior. Dependencias bloqueadas en `uv.lock`.
