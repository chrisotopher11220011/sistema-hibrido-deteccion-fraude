# ADR 0006: Datos sintéticos de ubicación solo para prueba funcional

- **Estado:** Aceptada
- **Fecha:** 2026-11-16
- **Fase en la que se aplica:** 2

## Contexto

La ponencia propone una regla que combina un monto superior a 1.000 con una ubicación inusual. El conjunto original no trae ubicación geográfica: sus variables son componentes anonimizados.

## Decisión

Un generador con semilla produce transacciones con `monto` y `ubicacion`, marcadas `origen: "sintetico"` y sin `variables`. Nunca se mezclan con los datos originales. La regla `MONTO_ALTO_UBICACION_INUSUAL` se comprueba de forma funcional: que se active cuando debe y deje su razón. No se reportan precisión ni exhaustividad sobre datos sintéticos.

## Consecuencias

- La regla de la ponencia queda demostrada sin fabricar evidencia de desempeño.
- Las transacciones sintéticas aparecen en la página como «sin etiqueta real».
- Presentar estos datos como desempeño frente a fraude real sería un fracaso del proyecto, aunque el sistema funcione.
