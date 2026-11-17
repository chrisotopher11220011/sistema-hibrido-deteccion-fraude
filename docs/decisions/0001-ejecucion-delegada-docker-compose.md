# ADR 0001: Ejecución delegada con Docker Compose

- **Estado:** Aceptada
- **Fecha:** 2026-11-16
- **Fase en la que se aplica:** 1 en adelante

## Contexto

Quien dirige el proyecto trabaja desde tablet y navegador, sin computador local y sin GitHub Codespaces. El sistema tiene tres piezas (API en Python, n8n y, de forma opcional, un LLM local) y un compañero lo ejecuta en su computador con Omarchy 4, que trae Docker y Docker Compose instalados. Se consideró n8n Cloud con la API publicada aparte, pero no tiene plan gratuito y deja configuración fuera del repositorio.

## Decisión

Todo vive en el repositorio y se ejecuta con Docker Compose en el computador del compañero. Los servicios son `api`, `n8n`, `tareas` y, con el perfil `llm`, `llm`. Las imágenes llevan versión exacta y las dependencias de Python van bloqueadas en `uv.lock`. GitHub Actions levanta lo mismo en cada cambio (nivel N2). Lo que solo puede saberse en el computador real se trata como supuesto (`docs/supuestos.md`) hasta que la evidencia de una ejecución lo confirme (nivel N3).

## Consecuencias

- Gratis y reproducible: la misma definición sirve para la CI y para la ejecución real.
- El ciclo de corrección es más lento: cada hallazgo de N3 pasa por una ejecución del compañero.
- Obliga a que cada ejecución deje evidencia suficiente para diagnosticar a distancia (sección 16 de la especificación).
- Ninguna cifra de la ponencia puede salir de N1 o N2.
