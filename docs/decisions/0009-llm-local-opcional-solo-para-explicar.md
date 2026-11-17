# ADR 0009: LLM local opcional, solo para explicar

- **Estado:** Aceptada
- **Fecha:** 2026-11-16
- **Fase en la que se aplica:** 7

## Contexto

El proyecto debe usar aprendizaje automático y admite un LLM. El computador de ejecución tiene una gráfica de 8 GB. Un LLM que decidiera si hay fraude sería opaco, no reproducible y contrario a la ponencia, que no considera infalibles las decisiones de la IA. Omarchy ofrece modelos locales propios, pero corren fuera de Compose y sus descargas son de decenas de GB.

## Decisión

El detector es Isolation Forest. El LLM es opcional: redacta en dos o tres frases, para el revisor, por qué se generó una alerta, a partir de señales ya calculadas. No decide, no cambia el nivel y no ve datos que el sistema no haya calculado. Corre en el servicio `llm` del perfil `llm` de Compose y se le habla por una API compatible con OpenAI. Si no está activo, falla o tarda demasiado, se usa la explicación por plantilla. Servidor y modelo se eligen y fijan en la fase 7 tras verificar el catálogo vigente.

## Consecuencias

- El sistema funciona igual sin LLM y el nivel de alerta es idéntico con él y sin él.
- Usar la gráfica en contenedores pide una preparación única con permisos de administrador; es el supuesto S9.
- Cada explicación guarda su origen, el modelo y el tiempo, y se comprueba de forma automática que no menciona reglas que no se activaron.
