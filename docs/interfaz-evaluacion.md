# Evaluación de la interfaz de la página de simulación

- **Versión revisada:** 0.6.0 (fase 6).
- **Qué se revisa:** la página de `web/`, servida por `api` en `http://localhost:8000`.
- **Con qué:** las pautas de interacción humano-IA de Amershi et al. (2019), la accesibilidad WCAG 2.2 nivel AA y el cuestionario SUS.
- **Nivel de verificación:** N1 y N2 con la muestra para pruebas. La experiencia de una persona real (SUS, observaciones, Chrome de Omarchy) espera el punto de prueba C (N3).

## 1. Pautas de interacción humano-IA

Fuente: Amershi, S. et al. (2019). *Guidelines for Human-AI Interaction*. CHI 2019. https://doi.org/10.1145/3290605.3300233. La numeración G1 a G18 se comprobó el 2026-11-17 en el artículo de los autores que presenta las 18 pautas (Microsoft Design, 2019). Antes de citarla en la ponencia hay que contrastarla con el artículo de CHI.

La sección 13 de la especificación pide revisar siete pautas (G1, G2, G4, G9, G11, G15 y G16). Para cada una: qué dice, cómo la cumple la página, cómo se comprueba y qué falta.

| Pauta | Qué hace la página | Comprobación | Valoración |
|---|---|---|---|
| **G1.** Dejar claro qué puede hacer el sistema | Aviso fijo bajo el título: simulación académica, «el sistema señala transacciones para revisión humana; no confirma fraude ni bloquea operaciones». Panel «Qué hace este sistema y cuánto fiarse», con tres columnas: qué hace, cuánto fiarse y qué no hace. Los niveles se llaman por lo que significan (*Revisión recomendada*, *Alerta prioritaria*) | `test_web.py`: aviso presente y frases prohibidas ausentes; `comprobar_pagina.py`: el texto de la página no afirma fraude en ningún ancho ni tema | Cumple |
| **G2.** Dejar claro con qué fiabilidad lo hace | El panel muestra el modelo cargado, si es real o la muestra (no reportable) y sus umbrales; dice que una puntuación alta prioriza la revisión pero no prueba el fraude, y que las métricas con intervalos están en `comparativa.md`. La matriz del lote lleva la nota «es una ilustración con el lote mostrado, no una métrica del sistema». La boleta muestra la puntuación frente a los dos umbrales | Prueba de la API (`/salud`) y capturas | Cumple en parte: la página no muestra cifras de precisión ni exhaustividad, a propósito, porque en N1 y N2 no existen cifras reportables. Tras el punto C puede añadirse un enlace o un resumen de `comparativa.md` con su carpeta de evidencia |
| **G4.** Mostrar la información pertinente | La boleta reúne lo que necesita quien revisa: identificador, monto, origen de los datos, nivel, razones de las reglas, explicación, puntuación frente a umbrales y variables que más pesaron. La bandeja muestra solo los pendientes con sus razones | Capturas en tres anchos | Cumple. Las razones vienen del flujo con el identificador de la regla (`MONTO_ALTO: …`); son exactas pero técnicas para el público general |
| **G9.** Permitir corregir con facilidad | Cada caso señalado se confirma o se descarta desde la boleta o desde la bandeja, con un comentario opcional, en un clic o una tecla. La decisión humana prevalece y queda en el caso (`decision_final`) | `comprobar_pagina.py`: revisión con teclado, respuesta 200 y mensaje de confirmación; pruebas de la API (200, 404, 409, 422) | Cumple. Una decisión no puede deshacerse desde la página (la API responde 409 a una segunda revisión, ADR 0013); la página lo explica si ocurre |
| **G11.** Explicar por qué hizo lo que hizo | Razones de cada regla activada y de la señal del modelo; explicación en texto (por plantilla); pista con la puntuación y los dos umbrales; contribución por variable (SHAP, ADR 0012) con la advertencia de que son componentes anónimos | Capturas; prueba de la transacción manual (dos razones) | Cumple, con el límite propio del conjunto: las variables V1–V28 son anónimas y la explicación dice cuáles pesaron, no por qué |
| **G15.** Recoger retroalimentación detallada | Por caso: decisión (confirmar o descartar), nombre de quien revisa y comentario libre. Queda en `revisiones.csv` y en `simulacion.json` | `comprobar_evidencia.py --con-casos --con-simulacion` en N2 | Cumple. La retroalimentación no reentrena el modelo (fuera de alcance; G13 no aplica) |
| **G16.** Mostrar las consecuencias de las acciones | Al revisar: «Guardado: caso … revisado, sospecha descartada, por …; sale de la bandeja y quedará en `revisiones.csv`». Al cambiar «Cuenta como señalada», los contadores, la matriz y el historial se recalculan al momento. Al pausar o al fallar un servicio, el estado dice dónde quedó la simulación y cómo seguir | `comprobar_pagina.py`: mensaje tras la revisión, pausa ante n8n caído | Cumple |

### Otras pautas, sin obligación de la especificación

| Pauta | Situación |
|---|---|
| G3, G5, G7, G13 | No aplican: la IA no actúa por iniciativa propia ni aprende del usuario |
| G6. Mitigar sesgos sociales | El conjunto no trae datos personales; no se evalúa aquí |
| G8. Descartar con facilidad | «Descartar sospecha» en cada caso; pausar en cualquier momento |
| G10. Acotar el servicio ante la duda | Una evaluación fallida nunca es «sin alerta»: queda como *Error de evaluación* pendiente de revisión |
| G12. Recordar interacciones recientes | Historial de la sesión; preferencias de tema, presentación, atajos y revisor recordadas en el navegador |
| G14. Actualizar con cautela | El modelo se recarga solo al reentrenar (ADR 0013); la página muestra su versión |
| G17. Controles globales | Velocidad, criterio de «señalada», tema, modo presentación y atajos |
| G18. Avisar de los cambios | La versión del modelo y la de la página aparecen en el panel y en el pie |

## 2. Accesibilidad (WCAG 2.2, nivel AA)

| Requisito de la sección 13 | Cómo se cumple | Comprobación |
|---|---|---|
| Contraste | Tokens de texto con contraste AA en los dos temas; el ámbar de las marcas (2,95:1) nunca se usa para texto | axe-core 4.14.1 con `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa` y `wcag22aa`, sin violaciones con el lote completo en tema claro, oscuro y modo presentación |
| Uso completo con teclado | Todo es un control nativo; enlace «Saltar al caso actual»; atajos `Espacio`, `S`, `T`, `P` y `?` con interruptor para desactivarlos (criterio 2.1.4); la gráfica se recorre con las flechas | `comprobar_pagina.py`: llegar con `Tab`, enviar con `S`, iniciar y pausar con `Espacio`, revisar desde la bandeja, transacción manual, `T`, `P` y `?` |
| Foco visible | Contorno de 3 px (4 px en presentación) del color del sello | `comprobar_pagina.py` comprueba el contorno en cada parada de `Tab` |
| Reducir movimiento | Sin animaciones con `prefers-reduced-motion: reduce` | `comprobar_pagina.py`: `animation-name: none` |
| Niveles con icono y texto | Círculo, rombo, triángulo y aspa, siempre con el nombre del nivel | Capturas; leyenda |
| Gráficas accesibles | Nombre y descripción en el lienzo, resumen en texto, globo también con teclado, historial como tabla | Capturas |
| Avisos | Región `aria-live` para el veredicto y la etiqueta; a velocidad alta solo se anuncian las alertas | Revisión del código |
| Ventana estrecha | Una columna desde unos 640 px, sin desbordamiento horizontal | `comprobar_pagina.py` en 640, 1280 y 1920 px |

**Límites.** axe-core encuentra una parte de los problemas posibles, no todos. Falta probar con un lector de pantalla real (Orca en Omarchy) y con usuarios. Eso queda para la fase de mejora (fase 8) con las observaciones del punto C.

## 3. Usabilidad (SUS)

`OBSERVACIONES.md` incluye el cuestionario SUS de diez preguntas (Brooke, 1996; referencia sin revisar hoy, ver `docs/spec.md`, sección 24). En el punto C lo llena el compañero. Con tan pocas personas el resultado es descriptivo, no una prueba estadística.

| Fuente | Puntuación SUS | Notas |
|---|---|---|
| Punto de prueba C | Pendiente | |

## 4. Capturas

La CI deja el artefacto `capturas-pagina` en cada ejecución: `pagina_<ancho>_<tema>.png` (página completa), `pantalla_<ancho>_<tema>.png` (lo que se ve sin desplazarse), `vacio_1280_<tema>.png`, `presentacion_<tema>.png` y los estados de error. `informe.json` resume cada comprobación.

Revisión de las capturas de la fase 6, en N1 y N2, y lo que se corrigió:

| Hallazgo | Corrección |
|---|---|
| El texto del estado vacío seguía visible al mostrar un caso (una regla `display: grid` anulaba el atributo `hidden`) | Regla global `[hidden] { display: none !important; }` |
| Las etiquetas de los umbrales se cortaban a la derecha y se tapaban cuando los dos umbrales coinciden (pasa con la muestra) | Margen derecho mayor, etiquetas en una línea y apiladas sin taparse |
| En modo presentación la letra de las gráficas no crecía | Las gráficas escalan su letra y sus márgenes con la de la página |
| La comprobación de lenguaje marcaba el propio aviso («no confirma fraude») | La comprobación admite la negación |
