# ADR 0008: Criterio de elección de umbrales

- **Estado:** Aceptada
- **Fecha:** 2026-11-16
- **Fase en la que se aplica:** 3

## Contexto

Isolation Forest da una puntuación continua. El sistema necesita dos cortes: uno para recomendar revisión y otro, más exigente, para la alerta prioritaria. Elegirlos a mano o mirando la parte de prueba invalidaría la evaluación.

## Decisión

Los dos umbrales se eligen en la parte de validación. `umbral_revision` es el que maximiza F1. `umbral_prioritaria` es el que maximiza F0,5, que da más peso a la precisión, y nunca es menor que `umbral_revision`. Quedan escritos en `modelo.json`, no en el código ni a mano en `config/`.

## Consecuencias

- Criterio fijado antes de ver ningún resultado, reproducible con la semilla.
- F1 y F0,5 son elecciones razonables, no las únicas; las curvas de precisión y exhaustividad según el umbral permiten juzgarlas.
- Con pocos fraudes en validación (unos 69), el umbral elegido tendrá varianza; el entrenamiento con varias semillas la muestra.
