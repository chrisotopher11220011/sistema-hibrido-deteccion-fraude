# Sistema híbrido de detección de fraude

Prototipo académico que simula la verificación de transacciones bancarias combinando **reglas deterministas**, **aprendizaje automático** (Isolation Forest) y **automatización con n8n**. Acompaña a la ponencia «Diseño de un sistema híbrido para la detección de fraude en transacciones financieras mediante reglas deterministas, aprendizaje automático y automatización con n8n».

No bloquea operaciones reales ni está pensado para producción. El sistema señala transacciones para revisión humana; no confirma fraudes.

## Estado

**Versión 0.5.0 — Fase 5, flujos de n8n.** Además de los cimientos (fase 1), los datos y las reglas (fase 2), el aprendizaje automático (fase 3) y la API con registro de casos (fase 4), n8n evalúa cada transacción por `POST /webhook/transaccion`: valida la entrada, consulta `/evaluar` con reintento y tiempo límite, aplica la tabla de decisión en el nodo «Clasificar nivel», explica el nivel con una plantilla, deja una notificación simulada, registra el caso y lo devuelve. `POST /webhook/revision` recibe la decisión de la persona que revisa. `./fraude demostrar` envía el lote de demostración por n8n y por la copia de la tabla en Python, exige el mismo nivel en todas las transacciones y mide la latencia (`flujo.json`). Todavía **no hay** página de simulación (fase 6). Las cifras de desempeño solo existirán cuando se ejecute con los datos reales en el computador de ejecución (N3): lo calculado en la CI usa la muestra para pruebas y no es un resultado.

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
| `./fraude entrenar` | Entrena Isolation Forest con la parte de ajuste y elige los umbrales en validación |
| `./fraude evaluar` | Métricas sobre la parte de prueba, comparativa, figuras y análisis de errores de validación |
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
