# ADR 0003: Partición y prevención de fugas de información

- **Estado:** Aceptada
- **Fecha:** 2026-11-16
- **Fase en la que se aplica:** 2 y 3

## Contexto

Con 492 fraudes entre 284.807 transacciones, cualquier decisión tomada mirando la parte de prueba infla los resultados. Además, el equipo mejora el sistema con archivos que devuelve cada ejecución, y esos archivos no deben contaminar la evaluación.

## Decisión

Partición estratificada con semilla fija: 70 % desarrollo y 30 % prueba; el desarrollo se divide en 80 % ajuste y 20 % validación. Los índices se guardan antes de cualquier ajuste. Ajuste entrena el modelo y alimenta el análisis exploratorio; validación elige umbrales y produce los archivos de análisis de errores; prueba solo da métricas agregadas, una vez por versión. Toda transformación, umbral o regla se ajusta únicamente con desarrollo. `docs/fugas.md` recorrerá las fuentes de fuga habituales.

## Consecuencias

- Los archivos para mejorar salen de validación, así que pueden usarse sin tocar la prueba.
- La parte de prueba queda con unos 148 fraudes: los intervalos de confianza serán anchos y hay que reportarlos (ADR 0011).
- Una partición aleatoria ignora el orden temporal; por eso existe el análisis secundario con partición cronológica.
