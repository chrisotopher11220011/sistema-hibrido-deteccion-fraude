# Fugas de información: dónde podrían estar y por qué no aplican

Sección 15 de `docs/spec.md` y ADR 0003. Una fuga es cualquier camino por el que información de la parte de prueba (o de las etiquetas) entra en algo que se ajusta. Con 492 fraudes, una fuga pequeña basta para inflar los resultados.

- **Última revisión:** 2026-11-17 (UTC), fase 3.

| Fuente habitual | Dónde podría ocurrir aquí | Por qué no aplica | Cómo se comprueba |
|---|---|---|---|
| Partición hecha después de transformar o seleccionar | `preparar` | La partición se calcula y se guarda antes de cualquier ajuste, a partir solo de la clase y una semilla | `datos.json` (`particion.estado`); `particion.json` con huella de los índices |
| Transformaciones ajustadas con todos los datos (escalado, PCA) | Variables | El proyecto no ajusta ninguna transformación: `V1`–`V28` vienen ya transformadas en el conjunto público y `Amount` se usa tal cual (Isolation Forest no necesita escalado) | Código de `modelo.py` |
| PCA del conjunto original | `V1`–`V28` | Los autores del conjunto la aplicaron a todas las filas antes de publicarlo. Es una fuga posible y ajena al proyecto: se declara como amenaza a la validez | `docs/resultados.md` (fase 9) |
| Entrenar con etiquetas | `entrenar` | Isolation Forest es no supervisado: se ajusta solo con las variables de la parte de ajuste | `test_solo_ajusta_con_la_parte_de_ajuste` |
| Umbrales elegidos mirando la prueba | `entrenar` | Se eligen con validación (F1 y F0,5) y quedan en `modelo.json`; `evaluar` los lee de ahí y no los recalcula | `test_umbrales_salen_de_validacion`, `test_umbrales_vienen_de_entrenar_no_de_la_prueba` |
| Corte de una línea base elegido con la prueba | Línea base por monto | Su corte se elige en validación con el mismo criterio que el modelo | `metricas.json`: `umbral_monto.parte = validacion` |
| Línea base al azar con información de etiquetas | Línea base al azar | Usa la cantidad de alertas del híbrido en la prueba, que no depende de las etiquetas, y una semilla fija | `metricas.json`: `protocolo.semilla_azar` |
| Hiperparámetros ajustados con la prueba | `config/modelo.yaml` | Son los del artículo original y de scikit-learn; no se buscaron. Si en la fase de mejora se ajustan, será con validación | Historial de `config/modelo.yaml` |
| Reglas diseñadas mirando la prueba | `config/reglas.yaml` | `MONTO_ALTO` viene de la ponencia. Las candidatas saldrán del análisis exploratorio de ajuste y del análisis de errores de validación | `eda/` y `analisis_errores/` |
| Mejorar con archivos que vienen de la prueba | Evidencia | `analisis_errores/` sale de validación; la prueba solo deja métricas agregadas | `test_analisis_de_errores_solo_con_filas_de_validacion` |
| Mirar la prueba muchas veces | Iteraciones de la fase 8 | Cada versión mide la prueba una vez. Las decisiones de mejora se toman con validación | Regla de trabajo; `CHANGELOG.md` |
| Duplicados entre partes | Conjunto original | El conjunto trae transacciones idénticas; pueden caer en partes distintas. Se trata como amenaza a la validez y se cuantifica con N3 | Pendiente de N3 |
| Orden temporal | Partición aleatoria | La partición principal ignora el orden; por eso existe la partición temporal secundaria, que desarrolla con el pasado y prueba con lo último | `metricas.json`: `temporal` |
| Datos sintéticos mezclados con los reales | Regla de ubicación | Viven en `datos/sinteticos/`, solo sirven para la prueba funcional y no producen métricas | ADR 0006 |
| Muestra para pruebas reportada como resultado | N1 y N2 | Todo lo calculado con ella lleva `reportable: false` y un aviso visible | `comparativa.md`, `metricas.json` |
