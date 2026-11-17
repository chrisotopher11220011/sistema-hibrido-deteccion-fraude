# ADR 0011: Protocolo de evaluación e incertidumbre

- **Estado:** Aceptada
- **Fecha:** 2026-11-16
- **Fase en la que se aplica:** 3 y 9

## Contexto

El proyecto debe estar a la altura de un congreso científico. Con tan pocos fraudes, una sola cifra de precisión o de exhaustividad dice poco: hay que mostrar cuánta incertidumbre tiene, contra qué se compara y cómo se evitó sesgarla. Isolation Forest es además un algoritmo aleatorio.

## Decisión

Sobre la parte de prueba se evalúan cuatro configuraciones: solo reglas, solo Isolation Forest, híbrido con cualquier alerta e híbrido con solo alertas prioritarias.

- **Métricas:** matriz de confusión, precisión, exhaustividad y F1; precisión media (área bajo la curva precisión-exhaustividad); precisión en los *k* casos con mayor puntuación; área bajo la curva ROC solo como dato complementario; latencia y paridad del flujo.
- **Incertidumbre:** intervalos de confianza del 95 % por *bootstrap* estratificado con 1.000 remuestreos; entrenamiento repetido con 10 semillas; diferencias entre configuraciones por *bootstrap* pareado.
- **Líneas base:** no alertar nunca, alertar al azar con la misma tasa y ordenar solo por monto.
- **Sensibilidad:** curvas según el umbral en validación y partición temporal como análisis secundario.
- **Reporte:** lista REFORMS, ficha del modelo, ficha de los datos y amenazas a la validez.

No se fijan metas numéricas.

## Consecuencias

- Los resultados podrán defenderse ante una revisión, sean buenos o malos.
- `evaluar` tarda más: mil remuestreos y diez entrenamientos. Que termine en minutos es parte del supuesto S5.
- Si `MONTO_ALTO` detecta pocos fraudes, se reporta tal cual.
- Varias referencias metodológicas (bootstrap, SUS, fichas, numeración de Amershi et al.) deben leerse en el original antes de citarlas en la ponencia.
