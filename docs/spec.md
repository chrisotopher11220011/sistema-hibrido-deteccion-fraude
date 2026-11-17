# Archivo maestro: detección híbrida de fraude con reglas, aprendizaje automático y n8n

- **Versión del documento:** 1.1 (2026-11-16). Añade Omarchy 4 como sistema de ejecución, el protocolo de rigor científico y el nivel de calidad de la interfaz.
- **Para quién:** cualquier chat de desarrollo de este proyecto. Con este archivo y el repositorio debe bastar para trabajar sin preguntar.
- **Base:** la ponencia «Diseño de un sistema híbrido para la detección de fraude en transacciones financieras…» y la guía «Ingeniería de software asistida por IA», ambas en este proyecto.
- **Copia que manda:** este archivo, `docs/spec.md` del repositorio.
- **Prompts:** están en `claude/PROMPTS.md`, uno por fase.

## 0. Datos del proyecto

| Dato | Valor |
|---|---|
| Repositorio | `chrisotopher11220011/sistema-hibrido-deteccion-fraude` |
| Quién dirige | Christopher Muzo, desde tablet y navegador |
| Quién ejecuta | Un compañero, en su computador |
| Computador de ejecución | Alienware Aurora 16X: Intel Core Ultra 9 275HX, 16 GB de RAM, NVIDIA RTX 5060 de 8 GB, 500 GB libres en SSD |
| Sistema de ejecución | Omarchy 4 (Arch Linux con Hyprland). Trae Docker y Docker Compose instalados |

## 1. Qué se construye

Un prototipo académico que simula la verificación de transacciones bancarias:

1. Una transacción de prueba entra por un webhook de n8n.
2. Una API en Python la evalúa con **reglas deterministas** y con un modelo de **aprendizaje automático** (Isolation Forest).
3. n8n combina las señales, clasifica el nivel de alerta, registra las razones y deriva el caso a revisión humana.
4. Una **página de simulación** muestra el proceso en vivo: transacciones que llegan, veredicto del sistema, razones y comparación con la etiqueta real del conjunto.
5. Cada ejecución deja **archivos de evidencia** con los que se corrige y se mejora la versión siguiente.

No bloquea operaciones reales ni está pensado para producción.

Segundo propósito, propio del equipo: comprobar hasta dónde se llega desarrollando desde la tablet con un agente de IA, sin usar el computador de quien dirige.

### Trazabilidad con la ponencia

| Objetivo específico de la ponencia | Dónde se cumple |
|---|---|
| Analizar el conjunto de datos, sus variables y limitaciones | Secciones 9 y 15; Fase 2 |
| Definir reglas deterministas documentadas | Sección 10; Fase 2 |
| Proponer un modelo de detección de anomalías con evaluación reproducible | Secciones 11 y 15; Fase 3 |
| Diseñar un flujo en n8n que reciba la evaluación, registre razones y derive a revisión humana | Sección 12; Fase 5 |
| Evaluar con métricas para datos desbalanceados y documentar limitaciones | Sección 15; Fases 3 y 9 |

La revisión bibliográfica es trabajo de redacción y queda fuera de este repositorio.

## 2. Dónde está la inteligencia artificial

| Componente | Tipo | Papel | Estado |
|---|---|---|---|
| Isolation Forest | Aprendizaje automático no supervisado | Puntúa cada transacción por lo atípica que es. Es una de las dos señales que deciden el nivel de alerta | Obligatorio; núcleo del sistema |
| Elección de umbrales | Ajuste con datos etiquetados de validación | Convierte la puntuación en señal de anomalía | Obligatorio |
| LLM local | Modelo de lenguaje ejecutado en el computador del compañero | Redacta en lenguaje natural la explicación de una alerta para el revisor. No decide ni cambia el nivel | Opcional; Fase 7 |

Isolation Forest trabaja en el procesador. La gráfica solo se usa si se activa el LLM local.

Ninguna decisión de la IA se considera infalible: la puntuación prioriza la revisión humana, no prueba el fraude.

## 3. Forma de trabajo: desarrollo en la nube, ejecución delegada

Quien desarrolla no ejecuta el sistema completo. Se construye con supuestos explícitos y un compañero lo ejecuta.

1. Un chat de Claude desarrolla una fase y la sube a GitHub.
2. GitHub Actions comprueba cada cambio.
3. En los puntos de prueba, el compañero descarga la versión y ejecuta un comando.
4. Ese comando deja archivos de evidencia (sección 16) que vuelven al chat o al repositorio.
5. Con esa evidencia se corrige y se mejora.

### Tres niveles de verificación

Toda afirmación sobre el proyecto (README, CHANGELOG, Pull Requests, mensajes de Claude) dice en qué nivel está comprobada.

| Nivel | Dónde | Qué cubre |
|---|---|---|
| N1 | Entorno de Claude | Pruebas unitarias con muestras pequeñas y datos sintéticos |
| N2 | GitHub Actions | Lo anterior en limpio, la construcción de las imágenes y el flujo de n8n de punta a punta con un modelo pequeño |
| N3 | Computador del compañero | Datos reales completos, entrenamiento, métricas, tiempos, página y demostración |

Lo que no pasó por N3 es un **supuesto**, no un resultado. Las cifras de la ponencia salen solo de N3.

Límites del entorno de Claude comprobados el 2026-11-16: llega a GitHub y a PyPI, no llega a Kaggle ni a OpenML, y no tiene Docker en marcha. Cada chat lo vuelve a comprobar al empezar, porque puede cambiar.

## 4. Objetivos, fuera de alcance y qué lo haría fracasar

**Objetivos**

- Reglas deterministas que registran qué regla se activó y por qué.
- Isolation Forest entrenado y evaluado con un procedimiento reproducible.
- Flujo de n8n que recibe, consulta la evaluación, combina señales, clasifica, registra y deriva a revisión humana.
- Página de simulación de la verificación de transacciones, con calidad de producto.
- Evaluación comparativa de solo reglas, solo modelo e híbrido, con el rigor de un congreso científico: incertidumbre medida, líneas base y reporte con una lista reconocida.
- Ejecución por un tercero en Omarchy 4 con un comando.
- Archivos de evidencia que permiten diagnosticar y mejorar a distancia.
- Historial ordenado: especificación, ADR, Conventional Commits, CHANGELOG y versiones SemVer.

**Fuera de alcance**

- Bloqueo real de operaciones o conexión con sistemas bancarios.
- Datos personales, números de tarjeta o credenciales.
- Modelos supervisados o de aprendizaje profundo como detectores.
- Un LLM que decida si hay fraude.
- Despliegue permanente en la nube.

**Qué lo haría fracasar aunque funcione**

- Reportar cifras que nadie midió.
- Ajustar umbrales o reglas mirando la parte de prueba.
- Presentar resultados de datos sintéticos como desempeño frente a fraude real.
- Alertas sin razón registrada.
- Una página que afirme «fraude confirmado» cuando el sistema solo señala sospechas.
- Pasos manuales no documentados para quien ejecuta.
- Secretos o datos dentro del repositorio.

## 5. Restricciones

- Sin computador local de quien dirige y sin GitHub Codespaces.
- El conjunto de datos pesa unos 150 MB: no va al repositorio, se descarga al ejecutar.
- El sistema de ejecución es Omarchy 4. Para el núcleo no se le pide instalar nada: Docker, Docker Compose y el navegador ya vienen con el sistema (sección 17).
- El flujo de n8n se escribe como JSON, sin editor visual. La versión de n8n queda fijada y el flujo se valida importándolo en un n8n real dentro de GitHub Actions.
- Nadie del lado del desarrollo ve la página en vivo: se valida con capturas automáticas en N2 y con las del compañero en N3.

## 6. Enfoques considerados

| Enfoque | Resultado | Motivo |
|---|---|---|
| A. Todo en el repositorio con Docker Compose y ejecución delegada | **Elegido** | Gratis y reproducible. A cambio, el ciclo de corrección es más lento |
| B. GitHub Codespaces | Descartado por Christopher | Se prefiere que lo ejecute el compañero |
| C. n8n Cloud y API publicada aparte | Descartado | No tiene plan gratuito (solo una prueba de 14 días) y deja configuración fuera del repositorio |

## 7. Arquitectura

```
Página de simulación (navegador)
        |  envía transacción / decisión del revisor
        v
+---------- API (Python) -----------+        +---------------- n8n ----------------+
| Página y rutas de simulación  ----------->  | 1. Webhook de entrada               |
| Validación de variables           |        | 2. Consultar evaluación             |
| Reglas deterministas       <--------------- |                                     |
| Isolation Forest (puntuación) ----------->  | 3. Clasificar nivel de alerta       |
| Registro de casos (SQLite) <--------------- | 4. Registrar caso                   |
+-----------------------------------+        | 5. Explicación (plantilla o LLM)    |
                                             | 6. Notificación de prueba           |
        LLM local (opcional) <--------------- | 7. Revisión humana (otro webhook)   |
                                             +-------------------------------------+
```

La página nunca llama a n8n directamente: lo hace la API, para evitar problemas entre orígenes del navegador.

## 8. Contratos

Estos nombres son el acuerdo entre chats. Cambiar uno exige un ADR y actualizar `docs/spec.md` en el mismo Pull Request.

### 8.1 Servicios y puertos

| Servicio | Puerto | Qué hace |
|---|---|---|
| `api` | 8000 | FastAPI: página, validación, reglas, modelo y registro de casos |
| `n8n` | 5678 | n8n Community con los flujos importados y activos al arrancar |
| `tareas` | sin puerto | Línea de comandos del proyecto |
| `llm` | interno | Servidor de modelos local; solo con el perfil `llm` de Compose |

Los puertos se publican solo en `127.0.0.1` y se cambian con variables de entorno. Todo tiene valores por defecto: no hace falta crear un archivo `.env` para ejecutar.

### 8.2 Transacción

```json
{
  "id_transaccion": "t-000457",
  "origen": "original",
  "monto": 1250.0,
  "variables": {"V1": -1.36, "V2": 0.07, "V28": -0.02},
  "ubicacion": {"pais_habitual": "EC", "pais_transaccion": "US"}
}
```

- `origen` es `original` o `sintetico`.
- `variables` lleva `V1` a `V28`; es opcional. Sin ella, el modelo queda «no evaluable».
- `ubicacion` es opcional. Sin ella, la regla de ubicación queda «no evaluable».
- La etiqueta real (`Class`) nunca viaja en la transacción.

### 8.3 Respuesta de `POST /evaluar`

```json
{
  "id_transaccion": "t-000457",
  "reglas": [
    {"id": "MONTO_ALTO", "evaluable": true, "activada": true,
     "alto_riesgo": false, "razon": "El monto 1250.00 supera el umbral 1000.00"}
  ],
  "modelo": {"evaluable": true, "puntuacion": 0.81,
             "umbral_revision": 0.62, "umbral_prioritaria": 0.74,
             "anomalia": true, "anomalia_alta": true},
  "versiones": {"reglas": "0.2.0", "modelo": "2026-11-20T15:04Z-a1b2c3"}
}
```

Los números son de ejemplo. Una puntuación mayor significa más anómalo. `anomalia` es `puntuacion >= umbral_revision`; `anomalia_alta` es `puntuacion >= umbral_prioritaria`.

`modelo` puede incluir además `contribuciones`: las variables que más pesaron en la puntuación, con su peso (sección 11).

### 8.4 Niveles y tabla de decisión

```
R_alto = alguna regla de alto riesgo activada
R      = alguna regla activada
A      = modelo.anomalia
A_alta = modelo.anomalia_alta

entrada inválida o evaluación fallida  -> error_evaluacion
R_alto, o (R y A), o A_alta            -> alerta_prioritaria
R o A                                  -> revision_recomendada
en otro caso                           -> sin_alerta
```

Una señal «no evaluable» cuenta como no activada y queda anotada en el caso.

La tabla se aplica en n8n, en el nodo «Clasificar nivel», porque la ponencia sitúa ahí la combinación de señales. Hay una copia en Python para evaluar fuera de línea. La **prueba de paridad** envía el mismo lote por los dos caminos y exige el mismo nivel en todos los casos.

### 8.5 Caso

| Campo | Contenido |
|---|---|
| `id_caso`, `id_transaccion`, `origen`, `monto` | Identificación |
| `fecha_procesamiento` | UTC, ISO 8601 |
| `senales` | Reglas y modelo tal como los devolvió `/evaluar` |
| `puntuacion`, `nivel`, `razones` | Resultado y sus motivos en texto |
| `explicacion` | Texto y `origen`: `plantilla` o `llm` |
| `notificacion` | Canal y estado |
| `estado` | `cerrado`, `pendiente_revision` o `revisado` |
| `decision_final` | `sin_alerta`, `pendiente`, `sospecha_confirmada` o `sospecha_descartada` |
| `revision` | Revisor, comentario y fecha |
| `versiones` | Reglas, modelo y flujo |

Los casos `sin_alerta` se cierran solos. Los demás niveles quedan en `pendiente_revision` hasta que alguien revisa.

### 8.6 Rutas de la API

| Ruta | Uso |
|---|---|
| `GET /salud` | Estado del servicio y del modelo |
| `POST /evaluar` | Señales de una transacción |
| `POST /casos`, `GET /casos`, `POST /casos/{id}/revision` | Registro de casos |
| `GET /` | Página de simulación |
| `GET /simulacion/lote` | Lote de demostración con etiqueta real, solo para mostrarla en la página |
| `POST /simulacion/transacciones` | Reenvía una transacción al webhook de n8n y devuelve el caso |
| `POST /simulacion/revisiones` | Reenvía la decisión del revisor al webhook de revisión |

### 8.7 Webhooks de n8n

| Webhook | Flujo |
|---|---|
| `POST /webhook/transaccion` | Evaluación de transacción |
| `POST /webhook/revision` | Revisión humana |
| `GET /webhook/ping` | Comprobación de arranque (Fase 1) |

### 8.8 Comandos

Quien ejecuta usa el guion `./fraude <comando>`, que por dentro llama a `docker compose run --rm tareas <comando>`. La CI llama a Compose directamente.

| Comando | Qué hace |
|---|---|
| `preparar` | Descarga y verifica los datos, crea la partición y el análisis exploratorio |
| `entrenar` | Entrena el modelo y elige los umbrales |
| `evaluar` | Calcula las métricas y los archivos de análisis de errores |
| `demostrar` | Envía el lote de demostración por n8n; mide paridad y latencia |
| `evidencia` | Reúne los archivos de la sección 16. Puede ejecutarse varias veces; cada vez deja una carpeta completa |
| `todo` | Ejecuta todo lo anterior, en orden, y termina siempre con `evidencia`, aunque un paso falle |

En cada fase, `todo` ejecuta los pasos que ya existen. Al terminar, `api` y `n8n` siguen en marcha para usar la página.

El guion `./fraude` añade tres comandos propios: `abrir` (abre la página en el navegador), `estado` (qué servicios están en marcha) y `apagar` (detiene todo). Sus obligaciones están en la sección 17.

### 8.9 Configuración

`config/reglas.yaml`, `config/modelo.yaml` y `config/decision.yaml`. Ningún umbral queda escrito dentro del código.

## 9. Datos

- **Conjunto:** Credit Card Fraud Detection (ULB y Worldline). 284.807 transacciones, 492 fraudes (0,172 %). Columnas `Time`, `V1` a `V28`, `Amount` y `Class`.
- **Descarga:** OpenML, conjunto 1597, sin credenciales. Alternativa manual: bajar el archivo de Kaggle y dejarlo en `datos/crudos/creditcard.csv`.
- **Integridad:** se comprueban filas, fraudes y columnas. La primera ejecución N3 fija la huella SHA-256, que las siguientes verifican.
- **Aviso sobre `Time`:** OpenML la marca como identificador de fila y algunas bibliotecas la omiten. El modelo no depende de `Time`; si falta, se registra y se continúa.
- **Partición:** estratificada y con semilla fija. 70 % desarrollo y 30 % prueba. El desarrollo se divide en 80 % ajuste y 20 % validación. Los índices se guardan antes de cualquier ajuste.
  - **Ajuste:** entrena el modelo y alimenta el análisis exploratorio.
  - **Validación:** elige umbrales y produce los archivos de análisis de errores.
  - **Prueba:** solo métricas agregadas, una vez por versión.
- **Moneda:** la descripción del conjunto no la indica (tarjetahabientes europeos, septiembre de 2013). El umbral «1.000» de la ponencia se aplica a `Amount` tal cual, es configurable y se documenta como limitación.
- **Datos sintéticos:** un generador con semilla produce transacciones con `monto` y `ubicacion`, marcadas `origen: "sintetico"`. No llevan `variables`. Nunca se mezclan con los datos originales.
- **Muestra para pruebas:** un generador crea datos con la misma forma que el conjunto real para N1 y N2. No representa el fraude real y no produce métricas reportables.

## 10. Reglas deterministas

Cada regla tiene identificador, condición, parámetros en `config/reglas.yaml` y un texto de razón.

| Regla | Condición | Alto riesgo | Datos |
|---|---|---|---|
| `MONTO_ALTO` | `monto > 1000` | No | Originales y sintéticos |
| `MONTO_ALTO_UBICACION_INUSUAL` | `monto > 1000` y `pais_transaccion` distinto de `pais_habitual` | Sí | Solo sintéticos |
| Candidatas | Salen del análisis exploratorio que devuelva N3 | Por definir | Se añaden en la fase de mejora, con justificación escrita |

La regla de ubicación se comprueba de forma **funcional**: que se active cuando debe y deje su razón. No se reportan precisión ni exhaustividad sobre datos sintéticos, porque esas etiquetas las habríamos fabricado nosotros.

Es probable que `MONTO_ALTO` detecte pocos fraudes en este conjunto. Si ocurre, se reporta tal cual.

## 11. Aprendizaje automático: Isolation Forest

- **Modelo:** `IsolationForest` de scikit-learn con semilla fija. Parámetros en `config/modelo.yaml`.
- **Variables:** `V1` a `V28` y `Amount`.
- **Entrenamiento:** con la parte de ajuste, sin usar etiquetas.
- **Puntuación:** transformada para que un valor mayor signifique más anómalo.
- **Umbrales, elegidos en validación:**
  - `umbral_revision`: el que maximiza F1.
  - `umbral_prioritaria`: el que maximiza F0,5, que da más peso a la precisión; nunca menor que `umbral_revision`.
- **Artefacto:** el modelo y `modelo.json` con parámetros, umbrales, huella de los datos, versiones y tiempo de entrenamiento. Se genera al ejecutar; no va al repositorio.
- **Contribución por variable:** para cada alerta se calculan las variables que más pesaron en la puntuación, con un método documentado y verificado para `IsolationForest` (por ejemplo SHAP para árboles o DIFFI). Es una explicación técnica: las variables son componentes anónimos, así que indica cuáles pesaron, no por qué.
- **Estabilidad:** el algoritmo es aleatorio. Además del modelo principal, la evaluación repite el entrenamiento con varias semillas (sección 15).
- **Interpretación:** la puntuación prioriza la revisión; no prueba el fraude.

## 12. Flujos de n8n

Versionados en `n8n/flujos/`.

1. **Evaluación de transacción:** webhook, validar entrada, consultar `/evaluar` con reintento y tiempo límite, clasificar nivel, preparar la explicación, registrar caso, notificación de prueba si hay alerta, y responder con el caso.
2. **Revisión humana:** webhook que recibe caso, decisión, revisor y comentario, y los guarda con `/casos/{id}/revision`.
3. **Ping:** responde «ok». Sirve para comprobar que n8n importó y publicó los flujos.

Comprobado en la documentación oficial de n8n 2.x el 2026-11-16; se vuelve a comprobar al fijar la versión:

- `n8n import:workflow` deja los flujos sin publicar. Se publican con `n8n publish:workflow --id=<ID>`; `update:workflow` está en desuso. Por eso cada flujo lleva un `id` fijo en su JSON.
- Las etiquetas de imagen ahora son `stable` y `beta`. Aquí se fija una versión exacta.
- Los nodos Code no leen variables de entorno por defecto. Los umbrales llegan en la respuesta de `/evaluar`, nunca por entorno.
- Para la tabla de decisión se prefieren nodos If y Switch si la expresan sin ambigüedad: se ve en el lienzo y no depende de los ejecutores de código.

Si la evaluación falla o la entrada es inválida, el caso queda como `error_evaluacion` y pendiente de revisión; nunca como `sin_alerta`.

La notificación es simulada por defecto: queda escrita en el caso. Telegram es opcional y se activa solo si quien ejecuta define el token en un archivo `.env`.

**Lote de demostración.** Archivo fijo que `tareas demostrar` y la página envían: una muestra de la parte de prueba con fraudes y no fraudes, transacciones sintéticas de ubicación y algunas entradas inválidas. En N2 se usa la muestra para pruebas.

## 13. Página de simulación

Es la cara visible del proyecto: simula que se verifica si las transacciones son legítimas o sospechosas de fraude.

```
+------------------------------------------------------------------+
| Simulador de verificación de transacciones   Simulación académica |
| [Iniciar simulación]  Velocidad [1 por segundo]  [Pausar]         |
+------------------------+-----------------------------------------+
| Analizadas        120  | t-000457 · Monto 1.250,00 · original     |
| Alertas             9  | ALERTA PRIORITARIA                       |
| Fraudes detectados  3  | · El monto supera el umbral 1.000        |
| Fraudes no detect.  1  | · Puntuación 0,81 sobre umbral 0,74      |
| Falsas alarmas      6  | Etiqueta real: fraude · Acierto          |
| Matriz de confusión    | [Confirmar sospecha]  [Descartar]        |
+------------------------+-----------------------------------------+
| Transacción manual:  Monto [   ]  País habitual [  ]  País [  ]   |
| Bandeja de revisión:  casos pendientes con sus razones            |
+------------------------------------------------------------------+
```

Las cifras del boceto son de ejemplo, no resultados.

- **Simulación:** envía el lote de demostración, una transacción cada cierto tiempo, y muestra cada caso al llegar: nivel, razones, puntuación frente al umbral y explicación.
- **Comparación con la etiqueta real:** como son datos etiquetados, después del veredicto se muestra la etiqueta y si el sistema acertó. Los contadores y la matriz de confusión se actualizan en vivo. Las transacciones sintéticas se muestran «sin etiqueta real».
- **Transacción manual:** formulario con monto y países para probar la regla de ubicación.
- **Bandeja de revisión:** casos pendientes con botones para confirmar o descartar la sospecha, con comentario.
- **Lenguaje:** el sistema «señala para revisión»; nunca «confirma fraude». Un aviso fijo indica que es una simulación con datos públicos y sintéticos.
- **Registro:** cada sesión queda en `simulacion.json` dentro de la evidencia.

### Nivel de calidad de la interfaz

La página es lo que verá el público del congreso. Se trata como un producto, no como una pantalla de pruebas.

- **Dirección visual:** se define con la skill `frontend-design` antes de escribir código y se guarda como sistema de diseño en `web/`: colores, tipografía, espaciado y componentes. Las gráficas siguen la skill `dataviz`.
- **Temas:** oscuro y claro, según la preferencia del sistema, y un **modo presentación** para proyector, con letra grande y alto contraste.
- **Tamaños:** se adapta desde una ventana estrecha en mosaico, habitual en Hyprland (unos 640 px), hasta pantalla completa.
- **Accesibilidad:** WCAG 2.2 nivel AA: contraste, uso completo con teclado, foco visible, respeto a «reducir movimiento» y niveles señalados con icono y texto además de color.
- **Estados:** vacío, cargando, en pausa, fin de lote y error (API o n8n sin responder). Cada uno dice qué pasa y qué hacer.
- **Gráficas:** matriz de confusión en vivo, puntuación de cada transacción frente a sus umbrales y línea de tiempo de alertas.
- **Interacción humano-IA:** se revisa contra las pautas de Amershi et al. (2019): dejar claro qué hace el sistema y con qué fiabilidad (G1, G2), mostrar la información pertinente (G4), permitir corregir con facilidad (G9), explicar por qué hizo lo que hizo (G11), recoger retroalimentación detallada (G15) y mostrar las consecuencias de las acciones del usuario (G16). El resultado queda en `docs/interfaz-evaluacion.md`.
- **Técnica:** HTML, CSS y JavaScript sin paso de compilación ni recursos externos, servidos por `api`. Debe seguir fluida con miles de transacciones.
- **Control visual:** la CI genera capturas en tres anchos y dos temas, y el chat las mira antes de cerrar la fase. En N3 se suman las capturas del compañero.
- **Usabilidad:** `OBSERVACIONES.md` incluye el cuestionario SUS de diez preguntas. Con tan pocas personas el resultado es descriptivo, no una prueba estadística.

## 14. Explicación con LLM local (opcional)

- **Qué hace:** redacta en dos o tres frases, para el revisor, por qué se generó la alerta, a partir de las señales ya calculadas.
- **Qué no hace:** no decide, no cambia el nivel y no ve datos que el sistema no haya calculado.
- **Dónde:** servicio `llm` del perfil `llm` de Compose, por ejemplo con Ollama, usando la gráfica si está disponible y el procesador si no. Se habla con él por una API compatible con OpenAI, con dirección y modelo configurables.
- **Gráfica en Omarchy:** pide una preparación única con permisos de administrador: `sudo pacman -S nvidia-container-toolkit`, `sudo nvidia-ctk runtime configure --runtime=docker` y `sudo systemctl restart docker`. Quien construya lo verifica y lo deja en `EJECUTAR.md`.
- **No se usan los modelos locales propios de Omarchy** (`omarchy agent local`): corren fuera de Compose y sus descargas son de decenas de GB.
- **Modelo:** uno pequeño que quepa en 8 GB de VRAM, elegido y fijado al construir tras verificar el catálogo vigente.
- **Respaldo:** si el LLM no está activo, falla o tarda más del tiempo límite, se usa la explicación por plantilla. El sistema funciona igual sin LLM.
- **Trazabilidad:** cada explicación guarda su origen, el modelo y el tiempo que tardó.
- **Activación:** `./fraude todo --llm`. La primera vez descarga el modelo, de varios GB.

## 15. Evaluación y rigor científico

Sobre la parte de prueba, cuatro configuraciones: solo reglas, solo Isolation Forest, híbrido con cualquier alerta e híbrido con solo alertas prioritarias.

**Métricas**

- Las que pide la ponencia: matriz de confusión, precisión, exhaustividad y F1, con número de alertas, falsos positivos y falsos negativos.
- Precisión media (área bajo la curva precisión-exhaustividad) para la puntuación del modelo. Es la medida que recomiendan los autores del conjunto, por su desbalance.
- Precisión en los *k* casos con mayor puntuación, con *k* igual al cupo de casos que un revisor puede atender. Adapta la medida «precision top-k» del manual de detección de fraude de la ULB; aquí se calcula sobre transacciones porque el conjunto no identifica tarjetas ni días.
- Área bajo la curva ROC solo como dato complementario para comparar con otros trabajos: ese mismo manual advierte que está poco adaptada a clases tan desbalanceadas.
- Del flujo: latencia por transacción (mediana y percentil 95) y paridad.

**Incertidumbre**

- Intervalos de confianza del 95 % por remuestreo *bootstrap* estratificado de la parte de prueba, con 1.000 remuestreos por defecto.
- Entrenamiento repetido con 10 semillas: media y desviación estándar de cada métrica.
- Diferencia entre configuraciones con intervalo de confianza por *bootstrap* pareado, sobre las mismas transacciones.

**Referencias de comparación**

Tres líneas base para dar contexto: no alertar nunca, alertar al azar con la misma tasa de alertas y ordenar solo por monto.

**Análisis de sensibilidad**

- Curvas de precisión y exhaustividad según el umbral, en validación.
- Partición temporal como análisis secundario: desarrollar con la primera parte cronológica y probar con la última. Si falta `Time` y no puede comprobarse el orden de las filas, se omite y se deja constancia.

**Fugas de información**

Toda transformación, umbral o regla se ajusta solo con la parte de desarrollo. `docs/fugas.md` recorre las fuentes de fuga habituales y explica por qué no aplican.

**Reproducibilidad**

Semillas fijas, dependencias bloqueadas (`uv.lock`), imágenes con versión exacta, huella de los datos y resultados ligados a un commit.

**Reporte**

- Lista REFORMS (32 puntos en 8 secciones) completada en `docs/reforms.md`.
- Ficha del modelo y ficha de los datos en `docs/`.
- Sección de amenazas a la validez en `docs/resultados.md`.
- Si se usa el LLM: comprobación automática de que cada explicación menciona el nivel correcto y ninguna regla que no se activó, con su tasa de fallos.

No se fijan metas numéricas. La ponencia no anticipa cifras y este archivo tampoco.

## 16. Archivos que deja cada ejecución

`tareas evidencia` crea `resultados/<fecha>_<commit>/` y un `.zip` con lo mismo. Sirven para dos cosas: diagnosticar lo que falló y decidir qué mejorar.

**Para diagnosticar**

| Archivo | Contenido |
|---|---|
| `RESUMEN.md` | Qué se ejecutó, qué terminó bien y qué falló, en lenguaje llano |
| `anfitrion.json` | Lo que recoge `./fraude` en el sistema: versión de Omarchy, núcleo, Docker, gráfica y si se usó `sudo` |
| `entorno.json` | Lo que se ve desde los contenedores: arquitectura, memoria y versiones de las imágenes |
| `version.json` | Commit, etiqueta y versiones de dependencias y de n8n |
| `datos.json` | Fuente, filas, fraudes, columnas y huella |
| `errores.json` | Errores de cada paso y de cada servicio |
| `registros/` | Últimas líneas de los registros de cada servicio |

**Para mejorar**

| Archivo | Contenido |
|---|---|
| `modelo.json` | Parámetros, umbrales y tiempo de entrenamiento |
| `metricas.json`, `comparativa.md` y figuras | Resultados de la sección 15 |
| `eda/` | Resumen estadístico y figuras de la parte de ajuste |
| `analisis_errores/` | Fraudes no detectados y falsas alarmas de la parte de **validación**, con monto, puntuación y reglas |
| `flujo.json` | Niveles obtenidos por n8n, paridad, latencias y errores |
| `casos.csv`, `revisiones.csv` | Casos registrados y decisiones de los revisores |
| `simulacion.json` | Lo enviado desde la página y lo que respondió el sistema |
| `explicaciones.json` | Muestra de explicaciones, su origen y sus tiempos |
| `OBSERVACIONES.md` | Plantilla que llena el compañero: qué hizo, qué vio, qué le confundió, y el cuestionario SUS |
| `capturas/` | Capturas de pantalla de la sesión |

El compañero escribe sus observaciones en `resultados/en_curso/OBSERVACIONES.md`. Las capturas que haga durante la sesión las copia `./fraude evidencia` desde `~/Pictures/Screenshots`.

Los archivos de análisis de errores salen de validación y no de prueba, para poder usarlos al mejorar sin contaminar la evaluación.

Sin secretos: cualquier token se enmascara. Todo es texto o imágenes pequeñas, así que puede subirse al repositorio en un Pull Request o adjuntarse al chat.

## 17. Ejecución en Omarchy 4

Comprobado en el manual oficial de Omarchy 4 el 2026-11-16:

| Tema | Cómo viene Omarchy 4 | Consecuencia para el proyecto |
|---|---|---|
| Docker | Docker y Docker Compose vienen instalados | No hay que instalar nada para el núcleo |
| Permisos de Docker | El usuario no está en el grupo `docker`: los comandos piden `sudo`. Puede cambiarse en *Setup > Security > Sudoless Docker* | `./fraude` usa `sudo` cuando hace falta. No se pide cambiar la seguridad del sistema |
| Cortafuegos | UFW bloquea el tráfico entrante y protege Docker con ufw-docker | Los puertos se publican solo en `127.0.0.1`. Nada del prototipo queda visible en la red |
| Navegador | Google Chrome, con `Super + Shift + Return` | `./fraude abrir` abre la página |
| Capturas | `Print Screen`; se guardan en `~/Pictures/Screenshots` | `./fraude evidencia` copia las de la sesión |
| Grabación | `Alt + Print Screen`; se guarda en `~/Videos` | Sirve para el video de respaldo de la demostración |
| Aplicación web | *Install > Web App* en el menú de Omarchy (`Super + Space`) | La página puede abrirse en ventana propia para la exposición |
| Gráfica en contenedores | No viene preparada para Docker | Solo hace falta para el LLM (sección 14) |

**Pasos de quien ejecuta**

Si el repositorio es privado, antes: `gh auth login`.

```
git clone <repositorio>
cd <repositorio>
./fraude todo
```

Después:

1. `./fraude abrir` y usar la página.
2. Escribir lo que vio en `resultados/en_curso/OBSERVACIONES.md`. Capturas con `Print Screen`.
3. `./fraude evidencia`.
4. Devolver la carpeta más reciente de `resultados/` o su `.zip`.
5. `./fraude apagar`.

**Obligaciones del guion `./fraude`**

- Funciona con `sudo` y sin él, y lo detecta solo.
- Los archivos de `resultados/` y `datos/` quedan a nombre del usuario y no de `root`, para que pueda editarlos y borrarlos.
- Recoge los datos del sistema en `anfitrion.json`.
- Si algo falla, guarda los registros de los servicios en `resultados/` sin que haya que pedirlo.
- Sus mensajes están en español y dicen qué está pasando y qué falta.

`EJECUTAR.md` lo explica paso a paso e indica qué debería verse en cada momento.

## 18. Supuestos y cómo se comprueban

| N.º | Supuesto | Cómo se comprueba |
|---|---|---|
| S1 | Docker y Docker Compose están instalados y en marcha, como indica el manual de Omarchy 4. Los recursos ya se conocen y sobran | `anfitrion.json` |
| S2 | Los puertos 5678 y 8000 están libres | Arranque; son configurables |
| S3 | OpenML responde y entrega el mismo conjunto que Kaggle | `datos.json`: 284.807 filas y 492 fraudes |
| S4 | La versión fijada de n8n importa y activa los flujos sin pasos manuales | N2 y `flujo.json` en N3 |
| S5 | El entrenamiento termina en minutos | `modelo.json` |
| S6 | El flujo responde cada transacción en pocos segundos | `flujo.json` |
| S7 | Con `sudo`, los archivos de `resultados/` y `datos/` quedan a nombre del usuario | Punto de prueba A |
| S8 | La página funciona en el Chrome de Omarchy | `simulacion.json` y `capturas/` |
| S9 | Tras instalar el paquete de NVIDIA para contenedores, Docker usa la gráfica; si no, se usa el procesador | `anfitrion.json` y `explicaciones.json` |
| S10 | GitHub Actions puede levantar n8n con Compose y probar el flujo | N2 desde la Fase 1 |
| S11 | El cortafuegos de Omarchy no impide llegar a los puertos publicados en `127.0.0.1` ni la comunicación entre contenedores | Punto de prueba A |
| S12 | Los contenedores resuelven nombres y salen a internet para descargar datos e imágenes | Punto de prueba A y `datos.json` |

`docs/supuestos.md` mantiene la lista con su estado: pendiente, confirmado o refutado.

## 19. Repositorio y convenciones

```
<repositorio>/
├── CLAUDE.md  README.md  CHANGELOG.md  EJECUTAR.md
├── fraude             guion para quien ejecuta (bash)
├── compose.yaml
├── config/            reglas.yaml, modelo.yaml, decision.yaml
├── docs/              spec.md, ESTADO.md, supuestos.md, architecture.md,
│                      resultados.md, reforms.md, fugas.md, fichas del modelo
│                      y de los datos, interfaz-evaluacion.md,
│                      decisions/, planes/, contratos/
├── src/fraude/        datos, reglas, modelo, decision, evaluacion, api,
│                      registro, simulacion, evidencia, cli
├── web/               página de simulación y su sistema de diseño
├── tests/             unitarias, contrato, punta_a_punta
├── n8n/flujos/        *.json
├── datos/             ignorado por Git
├── resultados/        archivos de evidencia
└── .github/           workflows/ci.yml, plantillas de issue y de Pull Request
```

- Python 3.12 o superior, `uv`, `ruff`, `pytest`, scikit-learn, pandas y FastAPI.
- Documentación, mensajes de commit y nombres del dominio en español; en el código, sin tildes.
- Fechas siempre en UTC.
- Conventional Commits, SemVer `0.y.z` hasta la ponencia y Keep a Changelog.
- ADR en `docs/decisions/`, con la plantilla de Nygard. Los primeros:
  - 0001 Ejecución delegada con Docker Compose
  - 0002 Fuente de datos y verificación de integridad
  - 0003 Partición y prevención de fugas de información
  - 0004 Tabla de decisión en n8n con copia en Python y prueba de paridad
  - 0005 Registro de casos en la API con SQLite
  - 0006 Datos sintéticos de ubicación solo para prueba funcional
  - 0007 La página habla con n8n a través de la API
  - 0008 Criterio de elección de umbrales
  - 0009 LLM local opcional, solo para explicar
  - 0010 Guion `./fraude` y permisos de Docker en Omarchy 4
  - 0011 Protocolo de evaluación e incertidumbre

## 20. Reglas de trabajo para cada chat

Christopher pidió que cada chat desarrolle solo hasta el punto de prueba. Estas reglas lo hacen posible sin perder el control.

**Al empezar**

1. Leer este archivo (o `docs/spec.md`), `docs/ESTADO.md` y `CLAUDE.md`.
2. Adjuntar el repositorio con permiso para subir cambios. Si no existe o no hay acceso, decirlo y parar.
3. Comprobar los límites del entorno: red, Docker, herramientas.
4. Si `docs/ESTADO.md` dice que la fase está a medias, continuar desde ahí.

**Mientras trabaja**

5. Escribir el plan de la fase con la skill de planes y guardarlo en `docs/planes/fase-N.md`. No esperar aprobación.
6. Prueba primero: cada cambio de comportamiento empieza por una prueba que falla.
7. Una rama por fase, `fase-N-nombre`, con commits pequeños.
8. Ante un fallo, depuración sistemática: causa antes que parche. Tras dos intentos fallidos sobre el mismo problema, replantear en vez de insistir.
9. No inventar ni anticipar cifras de desempeño.
10. Verificar contra la documentación oficial vigente todo lo que dependa de la versión de una herramienta, en especial n8n, Omarchy y el servidor del LLM.
11. Ningún secreto en el repositorio ni en el chat.

**Al cerrar**

12. Verificar con evidencia antes de afirmar: salida de pruebas y estado de la CI.
13. Revisión de código con un subagente de contexto limpio, comparando el cambio con este archivo. Atender solo fallos de corrección o de requisitos.
14. Abrir el Pull Request de la fase. Si la CI está en verde y la revisión no encuentra fallos, integrarlo y etiquetar la versión. Si no hay permiso para integrar, dejarlo abierto y decirlo.
15. Actualizar `CHANGELOG.md`, `docs/ESTADO.md` y `docs/supuestos.md`.
16. Entregar el informe de fase.

**Paradas obligatorias: preguntar a Christopher antes de seguir**

- Un cambio que contradiga este archivo o un contrato de la sección 8.
- Necesidad de una cuenta, un secreto o un pago.
- Una acción fuera del repositorio que no pueda deshacerse.
- La CI no queda en verde después de replantear una vez.

**Informe de fase**

```
Fase N — <nombre> · versión vX.Y.Z · Pull Request #N
Hecho: ...
Verificado en N1: ...            (con la salida de las pruebas)
Verificado en N2: ...            (con el enlace a la ejecución de la CI)
Supuestos que esperan N3: ...
Qué revisar si solo tienes cinco minutos: tres archivos
Siguiente prompt: Fase N+1
Mensaje para tu compañero: (solo si hay punto de prueba)
```

**Si el chat se queda sin espacio:** cerrar en un punto estable, subir los cambios, actualizar `docs/ESTADO.md` y pedir que se pegue el mismo prompt en un chat nuevo.

**Skills:** planes, desarrollo guiado por pruebas, depuración sistemática, verificación antes de dar algo por terminado, revisión de código y cierre de rama (superpowers); `frontend-design` y `dataviz` en la Fase 6; `dataviz` también para las figuras de la Fase 3.

## 21. Fases

| Fase | Versión | Contenido | Terminada cuando | Punto de prueba |
|---|---|---|---|---|
| 1. Cimientos | v0.1.0 | Estructura, documentos (incluidos los ADR 0001 a 0011), CI, guion `./fraude`, `api` con `/salud`, n8n con el flujo ping, `evidencia` mínima y `EJECUTAR.md` para Omarchy 4 | CI en verde, incluido el ping a n8n | **A** |
| 2. Datos y reglas | v0.2.0 | `preparar`, integridad, partición, análisis exploratorio, motor de reglas, generador sintético y muestra para pruebas | Pruebas en verde en N1 y N2 | |
| 3. Aprendizaje automático | v0.3.0 | `entrenar`, umbrales, contribución por variable, `evaluar` con todo el protocolo de la sección 15, comparativa, figuras y análisis de errores | Pruebas en verde con la muestra | **B** |
| 4. API y casos | v0.4.0 | `/evaluar`, registro en SQLite, carga del modelo y esquemas en `docs/contratos/` | Pruebas de contrato en verde | |
| 5. Flujos de n8n | v0.5.0 | Flujos de evaluación y revisión con explicación por plantilla, `demostrar`, paridad y latencia | Paridad total en N2 | |
| 6. Página de simulación | v0.6.0 | Sección 13 completa, con su nivel de calidad, y capturas automáticas en la CI | Capturas revisadas en N2, accesibilidad comprobada y pruebas en verde | **C** |
| 7. LLM local (opcional) | v0.7.0 | Sección 14 completa, con respaldo por plantilla | El sistema pasa las pruebas con y sin LLM | **C** con LLM |
| 8. Mejora con evidencia | v0.8.x | Analizar la evidencia, abrir un issue por hallazgo y corregir | Cada hallazgo tiene prueba y corrección | Se repite |
| 9. Cierre | v1.0.0 | `docs/resultados.md` con tablas y figuras de N3, amenazas a la validez, lista REFORMS, fichas del modelo y de los datos, evaluación de la interfaz, guía de demostración y video de respaldo | Se cumple la sección 23 | |

**Puntos de prueba**

- **A, tras la Fase 1:** cinco minutos. Comprueba en Omarchy 4 Docker con `sudo`, permisos de archivos, cortafuegos, puertos y arranque de n8n.
- **B, tras la Fase 3:** descarga de datos reales, entrenamiento y primeras métricas.
- **C, tras la Fase 6:** sistema completo con la página. Si se hace la Fase 7, se repite con el LLM activo.

A y B pueden saltarse para ir directo a C. A es barato y evita construir seis fases sobre un equipo que no arranca.

## 22. Quién decidió qué

**Decisiones de Christopher**

- Desarrollar solo la parte práctica de la ponencia.
- No usar el computador local ni GitHub Codespaces.
- Un compañero ejecuta; se trabaja con supuestos y se mejora con los archivos que él devuelva.
- Debe usarse aprendizaje automático; un LLM es admisible.
- Los chats desarrollan solos hasta el punto de prueba.
- La página final simula la verificación de transacciones.
- El sistema de ejecución es Omarchy 4.
- Todo debe estar a la altura de un congreso científico, interfaz incluida.
- Seguir la guía de ingeniería asistida por IA.

**Decisiones de Claude, para revisar**

1. GitHub Actions se mantiene como verificación automática (N2).
2. El LLM es opcional y solo explica; el detector es Isolation Forest.
3. La regla de ubicación se reporta como prueba funcional.
4. La tabla de decisión vive en n8n, con copia en Python y prueba de paridad.
5. El registro de casos lo guarda la API en SQLite. Si la API entera se cae, el caso no puede guardarse y solo queda el historial de n8n.
6. Notificación simulada por defecto; Telegram opcional.
7. Partición 70/30, con validación dentro del desarrollo; `Time` fuera del modelo.
8. Umbrales por F1 y F0,5 en validación.
9. Cada chat integra su propio Pull Request si la CI y la revisión pasan.
10. n8n entra desde la Fase 1 con un flujo mínimo, para comprobar pronto el supuesto más frágil.
11. Los archivos para mejorar salen de validación, no de prueba.
12. Nombres del dominio en español.
13. En Omarchy 4 se usa `sudo` con Docker, en lugar de pedir que se desactive una protección del sistema.
14. Protocolo de rigor de la sección 15: intervalos de confianza, varias semillas, líneas base, partición temporal secundaria y lista REFORMS.
15. Contribución por variable como explicación técnica de cada alerta.
16. El LLM corre dentro de Compose y no con los modelos locales de Omarchy.
17. La interfaz se evalúa con las pautas de interacción humano-IA y con el cuestionario SUS.

**Queda para quien construya**

- Versión exacta de n8n y mecanismo de importación y activación de flujos.
- Parámetros iniciales del modelo.
- Formato exacto de cada archivo JSON, salvo lo fijado en la sección 8.
- Cómo comparte `tareas` el modelo con `api` y cómo lo recarga la API.
- Método de contribución por variable, tras verificar que admite `IsolationForest`.
- Cómo consigue `./fraude` que los archivos queden a nombre del usuario.
- Herramienta de capturas automáticas.
- Servidor y modelo del LLM.

**Pendiente de Christopher**

- Nombre y visibilidad del repositorio, y GitHub conectado a Claude.
- Usuario de GitHub del compañero.
- Si quiere Telegram.
- Si quiere además una ejecución completa bajo demanda en GitHub Actions con datos reales, que adelanta evidencia sin esperar al compañero.

## 23. Verificación de punta a punta

En un Omarchy 4 que nunca vio el proyecto:

1. `./fraude todo` termina sin errores, con `sudo` o sin él, y deja los archivos a nombre del usuario.
2. `datos.json` informa 284.807 transacciones y 492 fraudes.
3. `comparativa.md` contiene las cuatro configuraciones y las tres líneas base, con sus matrices, métricas e intervalos de confianza, calculados sobre la parte de prueba.
4. `flujo.json` muestra paridad total entre n8n y Python, y latencias medidas.
5. En `http://localhost:8000`, «Iniciar simulación» muestra transacciones con nivel, razones y etiqueta real, y los contadores cambian.
6. Una transacción manual de monto alto y país distinto produce `alerta_prioritaria` con las razones de las dos reglas.
7. Un caso revisado desde la página queda con decisión, revisor y fecha en `revisiones.csv`.
8. Una transacción con datos inválidos queda como `error_evaluacion` y pendiente de revisión.
9. Si se hizo la Fase 7: con `--llm`, las explicaciones marcan origen `llm`; sin él, `plantilla`. En ambos casos el nivel es el mismo.
10. Tras usar la página, `./fraude evidencia` deja una carpeta con todos los archivos de la sección 16, incluidas las observaciones y las capturas.
11. La página se ve bien en ventana estrecha, en pantalla completa y en modo presentación, y puede usarse solo con el teclado.
12. `docs/reforms.md` está completa y cada cifra de `docs/resultados.md` indica de qué carpeta de evidencia sale.

## 24. Fuentes

**Consultadas el 2026-11-16**

- Manual oficial de Omarchy 4, secciones Development Tools, Security, Screenshots & Recording, Browsers, Web Apps y AI: https://omarchy.org/manual/
- Notas de versiones de Omarchy: https://github.com/omacom/omarchy/releases
- n8n, cambios de la versión 2.0: https://docs.n8n.io/2-0-breaking-changes/
- n8n, comandos de la línea de órdenes: https://docs.n8n.io/hosting/cli-commands/
- *Reproducible Machine Learning for Credit Card Fraud Detection – Practical Handbook*, Machine Learning Group de la ULB, capítulo de métricas: https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_4_PerformanceMetrics/Summary.html
- REFORMS, estándares de reporte para ciencia basada en aprendizaje automático (Kapoor, Narayanan y otros, *Science Advances*, 2024): https://reforms.cs.princeton.edu/
- Amershi et al. (2019), *Guidelines for Human-AI Interaction*, CHI 2019: https://www.microsoft.com/en-us/research/publication/guidelines-for-human-ai-interaction/
- Kartha, Gautrais y Vercruyssen, *Why Are You Weird? Infusing Interpretability in Isolation Forest for Anomaly Detection*: https://ar5iv.arxiv.org/html/2112.06858
- Recomendación de los autores del conjunto de medir con el área bajo la curva precisión-exhaustividad, citada en: https://machinelearningmastery.com/imbalanced-classification-with-the-fraudulent-credit-card-transactions-dataset/
- Gráfica NVIDIA en contenedores Docker sobre Arch Linux: https://dev.to/pakos/access-nvidia-gpu-inside-docker-container-in-arch-linux-4k6b
- Conjunto de datos en OpenML: https://api.openml.org/d/1597

**Referencias clásicas no revisadas hoy.** Antes de citarlas en la ponencia hay que leer el original:

- Cuestionario SUS (Brooke, 1996).
- Fichas de modelo (Mitchell et al., 2019) y fichas de datos (Gebru et al., 2021).
- WCAG 2.2 (W3C).
- Remuestreo *bootstrap* (Efron y Tibshirani).
- La numeración G1 a G18 de Amershi et al., tomada de memoria.
- Que SHAP para árboles o DIFFI admitan `IsolationForest` de scikit-learn: lo verifica la Fase 3.
