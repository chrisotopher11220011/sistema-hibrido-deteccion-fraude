# Registro de cambios

Formato de [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y versiones [SemVer](https://semver.org/lang/es/) `0.y.z` hasta la ponencia.

Cada entrada indica su nivel de verificación: N1 (entorno de desarrollo), N2 (GitHub Actions) o N3 (computador de ejecución).

## [Sin publicar]

## [0.3.0] - 2026-11-17

Fase 3, aprendizaje automático. Todo lo comprobado aquí usa la muestra para pruebas: confirma que el procedimiento funciona, no mide la detección de fraude. Las cifras reales salen solo de N3 (punto de prueba B).

### Añadido

- Paso `entrenar` (`./fraude entrenar`, y dentro de `todo`): Isolation Forest con la parte de ajuste y sin etiquetas; `umbral_revision` por F1 y `umbral_prioritaria` por F0,5 en validación; artefacto con huella en `datos/modelo/` y `modelo.json` con parámetros, umbrales, huellas de datos y partición, versiones y tiempos (N1; N2 con la muestra).
- Paso `evaluar`: cuatro configuraciones y tres líneas base sobre la parte de prueba, con matriz de confusión, precisión, exhaustividad y F1; precisión media, precisión en los 100 primeros y AUC ROC complementaria; intervalos del 95 % por *bootstrap* estratificado con 1.000 remuestreos; diferencias pareadas; diez semillas; partición temporal secundaria (omitida y anotada si falta `Time`) (N1; N2 con la muestra).
- `metricas.json`, `comparativa.md`, cuatro figuras siguiendo la skill `dataviz` y `analisis_errores/` de la parte de validación con las variables que más pesaron (N1; N2 con la muestra).
- Contribución por variable con SHAP para árboles, con prueba de aditividad (ADR 0012) (N1; N2).
- Copia en Python de la tabla de decisión de la sección 8.4 (N1).
- `docs/fugas.md`: fuentes de fuga habituales y por qué no aplican.
- La evidencia copia `modelo.json`, `metricas.json`, `comparativa.md`, `figuras/` y `analisis_errores/`, y el resumen dice si son de la muestra (N1; N2).

### Cambiado

- Dependencia nueva: `shap` 0.54.1.
- `config/modelo.yaml` añade `isolation_forest`, `contribuciones` y `evaluacion`.
- `entrenar` y `evaluar` dejan de avisar de su fase; `demostrar` sigue llegando en la fase 5.
- Una sesión nueva de `./fraude todo` no arrastra los archivos de modelo y evaluación de la anterior.
- El estilo común de las figuras pasa a `src/fraude/graficas.py`.

## [0.2.0] - 2026-11-17

Fase 2, datos y reglas. Sin modelo ni métricas todavía: todo lo comprobado aquí usa la muestra para pruebas o datos sintéticos, que no representan el fraude real.

### Añadido

- Paso `preparar` (`./fraude preparar`, y dentro de `todo`): descarga el ARFF de OpenML 1597 con su suma MD5 publicada, o usa el CSV de Kaggle dejado a mano; comprueba filas, fraudes y columnas; fija y verifica la huella SHA-256 del contenido; guarda la partición estratificada 56/14/30 antes de cualquier ajuste; deja `datos.json` (N1; N2 con la muestra; los datos reales esperan N3).
- `preparar` funciona sin la columna `Time`: lo anota y sigue (N1).
- Análisis exploratorio de la parte de ajuste en `eda/`: resumen y tres figuras (N1; N2 con la muestra).
- Motor de reglas deterministas `MONTO_ALTO` y `MONTO_ALTO_UBICACION_INUSUAL`, con razón en texto y «no evaluable» cuando faltan datos; la de ubicación solo se aplica a datos sintéticos (N1).
- Generador sintético de ubicación en `datos/sinteticos/`, separado de los originales, con comprobación funcional de la regla y sin métricas de desempeño (N1; N2).
- Muestra para pruebas y opción `--muestra` en `preparar`, `todo` y `./fraude todo` (N1; N2).
- Forma de la transacción del contrato 8.2 validada con Pydantic (N1).
- La evidencia incluye `datos.json`, `eda/` y las versiones de las bibliotecas de datos (N1; N2).

### Cambiado

- `config/reglas.yaml` pasa a la versión 0.2.0. `config/modelo.yaml` guarda también los parámetros de datos, partición, muestra y sintéticos.
- La CI ejecuta `todo --muestra` y comprueba `datos.json`, `eda/` y los datos sintéticos.
- Una sesión nueva de `./fraude todo` no arrastra `datos.json` ni `eda/` de la anterior.

## [0.1.0] - 2026-11-17

Fase 1, cimientos. Sin datos, reglas, modelo ni página todavía: esta versión solo comprueba que el sistema arranca.

### Añadido

- Estructura del repositorio, `CLAUDE.md`, `README.md`, `EJECUTAR.md`, `docs/ESTADO.md`, `docs/supuestos.md`, `docs/architecture.md` y los ADR 0001 a 0011.
- API con `GET /salud` (N1 y N2).
- n8n fijado en la versión 2.47.7, con el flujo `ping` importado y publicado al arrancar; responde en `GET /webhook/ping` (N2).
- Línea de comandos `tareas` con `todo` y `evidencia`. Los pasos `preparar`, `entrenar`, `evaluar` y `demostrar` existen pero avisan de la fase en que llegan (N1 y N2).
- Evidencia mínima: `RESUMEN.md`, `anfitrion.json`, `entorno.json`, `version.json`, `errores.json`, `registros/`, `OBSERVACIONES.md`, `capturas/` y el `.zip` (N1 y N2).
- Guion `./fraude` para Omarchy 4: detecta si Docker pide `sudo`, deja los archivos a nombre del usuario, recoge los datos del sistema y guarda los registros si algo falla (N1 con Docker simulado; N2 sin `sudo` y con `sudo ./fraude`; el caso real de Omarchy espera N3).
- Integración continua en GitHub Actions: estilo, pruebas unitarias, `shellcheck`, construcción de imágenes y flujo `ping` de punta a punta.
- Archivos de configuración `config/reglas.yaml`, `config/modelo.yaml` y `config/decision.yaml`.

[Sin publicar]: https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/compare/main...HEAD
[0.2.0]: https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/pull/3
[0.1.0]: https://github.com/chrisotopher11220011/sistema-hibrido-deteccion-fraude/pull/1
