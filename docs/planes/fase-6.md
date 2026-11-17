# Fase 6 — Página de simulación: plan de implementación

> **Para quien ejecute el plan:** se trabaja tarea por tarea con `superpowers:executing-plans`, prueba primero. Cada paso lleva casilla (`- [x]`).

**Meta:** la página de la sección 13 de `docs/spec.md`, con su nivel de calidad, servida por `api`: simulación del lote de demostración, comparación con la etiqueta real después del veredicto, transacción manual, bandeja de revisión, gráficas en vivo, temas claro y oscuro, modo presentación, uso completo con teclado y registro de la sesión en `simulacion.json`. Capturas automáticas en la CI en tres anchos y dos temas.

**Arquitectura:** `web/` contiene la página (HTML, CSS y JavaScript sin compilación) y su sistema de diseño. La API la sirve en `GET /` y sus recursos en `/recursos/`. Las rutas `/simulacion/*` (sección 8.6) viven en `src/fraude/simulacion.py`: sirven el lote, reenvían a los webhooks de n8n (ADR 0007) y anotan cada intercambio en `resultados/en_curso/simulacion.jsonl`; `tareas evidencia` lo convierte en `simulacion.json`, uniendo cada transacción con su etiqueta del lote **fuera** del camino de evaluación.

**Tecnología:** FastAPI (`StaticFiles`), `urllib` para el reenvío, JavaScript de módulo único sin dependencias, Atkinson Hyperlegible Next (OFL, incluida en `web/fuentes/`), Playwright para las capturas y axe-core para la comprobación automática de accesibilidad (solo en pruebas, se instala en la CI con npm).

**Especificación:** `docs/spec.md`, secciones 8.6, 13, 16 y 21; ADR 0007; ADR 0015 (nuevo).

## Restricciones globales

- Contratos de la sección 8 sin cambios: las rutas de 8.6 se implementan tal cual. Lo que 8.6 no fija (cuerpos, errores, registro) va al ADR 0015.
- La etiqueta real se muestra **después** del veredicto y nunca viaja al flujo: la página envía solo `elemento.transaccion`; la API rechaza con 422 un cuerpo que traiga `etiqueta_real`.
- Lenguaje: «señala para revisión», nunca «confirma fraude». Una prueba busca frases prohibidas en `web/`.
- Sin recursos externos ni paso de compilación. Una prueba falla si `web/` referencia `http://` o `https://` fuera de comentarios de licencia.
- Ningún umbral en el código: los umbrales que dibuja la página llegan en cada caso (`senales.modelo`).
- Sin cifras de desempeño: los contadores de la página son del lote mostrado y la página lo dice. Con la muestra, avisa de que no es reportable.

## Dirección visual (skill `frontend-design`)

**Asunto, público y tarea.** Mesa de verificación de un banco, vista por el público de un congreso en un proyector. La tarea principal: ver cómo cada transacción llega, recibe un nivel con sus razones y, después, se compara con la etiqueta real.

**Concepto: «mesa de verificación».** La transacción actual es una boleta sobre la mesa, con el borde perforado de los comprobantes bancarios; el nivel cae sobre ella como un sello de tinta. Es lo único llamativo de la página. Todo lo demás (contadores, gráficas, bandeja) es sobrio y queda sobre el papel.

| Token | Claro | Oscuro | Uso |
|---|---|---|---|
| `papel` | `#e9eeea` | `#0e1715` | Fondo de la página: papel de seguridad verde grisáceo |
| `hoja` | `#f7f9f6` | `#15211e` | Superficie de paneles y gráficas |
| `tinta` | `#13302c` | `#e3ece7` | Texto principal: tinta de billete |
| `tinta-2` | `#48605b` | `#a9bab3` | Texto secundario |
| `filete` | `#c6d2cc` | `#2a3a36` | Líneas finas y bordes |
| `sello` | `#4b2e83` | `#b7a3f0` | Acciones e interacción: tinta violeta de sello |

Niveles (validados con `dataviz/scripts/validate_palette.js`, todos los pares): sin alerta `#2a78d6` / `#3987e5`, revisión recomendada `#c98300` / `#c98500`, alerta prioritaria `#c7305f` / `#e85682`. Error de evaluación no usa color: marca hueca con `tinta-2` y borde discontinuo. Cada nivel lleva además **forma e icono** (círculo, rombo, triángulo, aspa) y su nombre en texto. El ámbar claro queda bajo 3:1 frente a la hoja: el texto de los niveles usa variantes oscuras y la tabla del historial da el alivio que pide la regla.

**Tipografía.** Una sola familia: Atkinson Hyperlegible Next (variable, 200–800), diseñada por el Braille Institute para distinguir caracteres parecidos (`0/O`, `1/l/I`): justo lo que pide un proyector y una sala con distintas capacidades visuales. Escala de tercera mayor sobre 16 px (13, 16, 20, 25, 31, 39, 49). Cifras tabulares en tablas y ejes. Sin versalitas ni mayúsculas en etiquetas, sin monoespaciada.

**Disposición.** Alineada a la izquierda.

```
ancho (≥ 1100 px)
+--------------------------------------------------------------------------+
| Simulador de verificación de transacciones          [Tema] [Presentación] |
| Aviso fijo: simulación académica · el sistema señala para revisión        |
| [Iniciar simulación] [Pausar] Velocidad [1 por segundo] [Paso] [Reiniciar]|
| Progreso 34 de 126                                                        |
+-------------------------------------+------------------------------------+
| Boleta del caso actual (héroe)      | Contadores                         |
|  id, monto, origen                  | Matriz de confusión (lote mostrado)|
|  SELLO DEL NIVEL                    | Qué cuenta como «señalada»         |
|  Razones · explicación              |                                    |
|  Puntuación frente a umbrales       |                                    |
|  Variables que más pesaron          |                                    |
|  Etiqueta real (tras el veredicto)  |                                    |
+-------------------------------------+------------------------------------+
| Puntuación de cada transacción frente a sus umbrales (ancho completo)    |
| Línea de tiempo de alertas (misma escala horizontal)                     |
+-------------------------------------+------------------------------------+
| Bandeja de revisión                 | Transacción manual                 |
+-------------------------------------+------------------------------------+
| Historial (tabla: también es la vista accesible de las gráficas)         |
+--------------------------------------------------------------------------+
estrecho (≈ 640 px): una columna en el mismo orden.
```

**Principios.**

1. La boleta y su sello son el momento memorable; el resto, silencioso.
2. Cada señal se dice tres veces: color, forma y palabra.
3. Primero el veredicto, después la verdad: la etiqueta aparece tras una pausa breve y siempre separada del veredicto.
4. Las palabras dicen lo que el sistema hace: «señala para revisión», «puntuación de anomalía», «fraude no señalado».

**Revisión frente a los valores por defecto.** El primer borrador usaba fondo crema y acento terracota, el valor por defecto más común: se cambió a papel de seguridad verde grisáceo y tinta violeta de sello, que salen del mundo bancario. También se descartó la monoespaciada para cifras (marca de plantilla) en favor de cifras tabulares de la misma familia, y las etiquetas en mayúsculas en favor de texto normal en peso 600.

## Gráficas (skill `dataviz`)

| Gráfica | Forma | Por qué |
|---|---|---|
| Puntuación frente a umbrales | Puntos en orden de llegada (eje x) y puntuación (eje y), con las dos líneas de umbral rotuladas directamente | Muestra cada decisión del modelo frente a su corte; un solo eje |
| Línea de tiempo de alertas | Banda de marcas, una por transacción, en la misma escala x | Dónde aparecen las alertas a lo largo de la sesión |
| Matriz de confusión | Tabla 2×2 con conteos | Cuatro números: una tabla es más clara que un gráfico |
| Puntuación del caso actual | Pista horizontal con los dos umbrales y la marca de la puntuación | Una sola cifra frente a dos cortes |
| Variables que más pesaron | Barras horizontales finas de un solo color | Magnitud, una serie, sin leyenda |

Leyenda siempre presente en la gráfica de puntos (varias series). Información emergente con ratón y con foco, área de toque de 24 px; la tabla del historial es la vista sin gráfica. El lienzo se dibuja en `<canvas>` para seguir fluido con miles de puntos; el historial pinta solo las últimas 200 filas.

## Decisiones de esta fase (ADR 0015)

1. `GET /` sirve `web/index.html`; `/recursos/` sirve `web/`. La imagen copia `web/` en `/app/web` (`FRAUDE_WEB`).
2. `GET /simulacion/lote`: el lote de la fuente del modelo que usa la API (`FRAUDE_MODELO`: `auto` toma el real si existe). 404 `lote_no_disponible` si aún no se generó.
3. `POST /simulacion/transacciones`: el cuerpo es la transacción tal cual. Rechaza con 422 `etiqueta_en_transaccion` un objeto con `etiqueta_real`. Reenvía a `FRAUDE_URL_N8N/webhook/transaccion` y devuelve su código y su cuerpo. Si n8n no responde, 502 `n8n_no_disponible` (sin `caso`, para distinguirlo del 502 de n8n con `caso`).
4. `POST /simulacion/revisiones`: igual, hacia `/webhook/revision`.
5. Cada intercambio se anota en `resultados/en_curso/simulacion.jsonl` (sesión, número de elemento, enviado, código, nivel, estado, latencia). La sesión y el número llegan por la consulta (`?sesion=…&n=…`), nunca dentro de la transacción.
6. `tareas evidencia` escribe `simulacion.json`: sesiones, intercambios y la comparación con la etiqueta, unida desde el lote por `id_transaccion` al reunir la evidencia.
7. Capturas: Playwright (Chromium) en la CI, tres anchos (640, 1280 y 1920 px) por dos temas, más el modo presentación y los estados vacío y de error; axe-core para WCAG 2.2 A y AA. En N1 se usa el Chrome del entorno y un n8n de pruebas que ejecuta los flujos reales con el simulador de la fase 5.
8. Atajos de una tecla (espacio, `S`, `T`, `P`, `?`) con interruptor para desactivarlos (WCAG 2.1.4).

## Tareas

### Tarea 1: rutas de simulación en la API

- [ ] Pruebas (`tests/unitarias/test_simulacion.py`): `GET /` devuelve HTML con el aviso; `/recursos/estilos.css` existe; lote 404 sin lote, 200 con el real o la muestra según el modo; reenvío con n8n simulado (200, 502 con caso, n8n caído → 502 `n8n_no_disponible`); 422 con `etiqueta_real`; revisión reenviada con su código; cada intercambio queda en `simulacion.jsonl`.
- [ ] Implementar `src/fraude/simulacion.py` y montarlo en `api.py`.
- [ ] `compose.yaml`: `FRAUDE_URL_N8N` en `api`. `Dockerfile`: copiar `web/`.

### Tarea 2: `simulacion.json` en la evidencia

- [ ] Pruebas en `test_evidencia.py`: sin registro → nota; con registro → sesiones, intercambios, comparación con la etiqueta del lote; tokens enmascarados.
- [ ] Implementar en `evidencia.py`.

### Tarea 3: la página

- [ ] Pruebas estáticas (`tests/unitarias/test_web.py`): sin direcciones externas, sin frases prohibidas, aviso fijo presente, la página no envía `etiqueta_real` (el código solo envía `elemento.transaccion`), fuentes con su licencia.
- [ ] `web/index.html`, `web/estilos.css` (sistema de diseño con tokens), `web/app.js`, `web/fuentes/`, `web/DISENO.md`.

### Tarea 4: capturas y accesibilidad

- [ ] `tests/punta_a_punta/n8n_de_pruebas.py` (solo N1).
- [ ] `tests/punta_a_punta/comprobar_pagina.py`: recorre la página con Playwright, solo con teclado; axe-core; capturas en `resultados/en_curso/capturas_ci/`.
- [ ] CI: paso nuevo tras `todo --muestra`; las capturas se suben como artefacto.
- [ ] Mirar las capturas y corregir.

### Tarea 5: documentos y cierre

- [ ] `docs/interfaz-evaluacion.md` (Amershi et al., 2019), ADR 0015, `EJECUTAR.md`, `README.md`, `CHANGELOG.md`, `docs/ESTADO.md`, `docs/supuestos.md`, versión 0.6.0.
- [ ] Revisión con subagente de contexto limpio, Pull Request sobre `fase-5-flujos-n8n`, CI en verde.

## Revisión dirigida

1. Ninguna petición de la página lleva la etiqueta real; la etiqueta solo aparece después de mostrar el nivel.
2. Ningún texto dice que el sistema confirma o detecta fraude con certeza.
3. API caída, n8n caído, caso no registrado y entrada inválida tienen cada uno un estado que dice qué pasa y qué hacer.
4. Todo se puede hacer con el teclado y el foco siempre se ve.
5. Con «reducir movimiento» no hay animaciones.
