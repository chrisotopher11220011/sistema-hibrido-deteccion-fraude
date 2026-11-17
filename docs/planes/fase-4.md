# Fase 4 — API y casos: plan de implementación

> **Para quien ejecute el plan:** se trabaja tarea por tarea con `superpowers:executing-plans`, prueba primero. Cada paso lleva casilla (`- [ ]`).

**Meta:** que la API sirva `POST /evaluar` con el contrato 8.3, cargue (y recargue) el modelo que deja `entrenar`, registre casos en SQLite con `POST /casos`, `GET /casos` y `POST /casos/{id}/revision`, y que los contratos de la sección 8 queden como esquemas JSON en `docs/contratos/` con pruebas de contrato.

**Arquitectura:** `api.py` pasa a ser una fábrica (`crear_app(raiz)`) que compone tres piezas pequeñas: `servicio_modelo.py` (carga y recarga del artefacto, puntuación y contribuciones), `evaluacion.py` (transacción → respuesta 8.3, sin HTTP) y `registro.py` (casos en SQLite). Los esquemas de `docs/contratos/` son la referencia; las pruebas de `tests/contrato/` comprueban que los ejemplos de `docs/spec.md` y las respuestas reales de la API los cumplen.

**Tecnología:** FastAPI, Pydantic 2, `sqlite3` de la biblioteca estándar, JSON Schema 2020-12 y `jsonschema` (solo para pruebas).

**Especificación:** `docs/spec.md`, secciones 8.2, 8.3, 8.4, 8.5, 8.6, 8.9, 11, 12, 16 y 21; ADR 0004, 0005 y 0012.

## Restricciones globales

- Los contratos de la sección 8 no cambian. Lo que la sección 8 no fija (respuesta de error, cuerpo de `POST /casos`, forma de `GET /casos`) se decide aquí y queda en el ADR 0013 y en `docs/contratos/README.md`.
- La respuesta 200 de `/evaluar` tiene exactamente `id_transaccion`, `reglas`, `modelo` y `versiones`; `modelo` puede añadir `contribuciones` y nada más.
- `anomalia = puntuacion >= umbral_revision`; `anomalia_alta = puntuacion >= umbral_prioritaria`. Una señal no evaluable cuenta como no activada.
- Entrada inválida o evaluación imposible → respuesta no 200 con cuerpo `error`, para que n8n marque `error_evaluacion` (sección 12). Nunca un 200 que parezca `sin_alerta`.
- Casos `sin_alerta` → `cerrado`, `decision_final: sin_alerta`. Los demás → `pendiente_revision`, `decision_final: pendiente`.
- Ningún umbral en el código: reglas en `config/reglas.yaml`, umbrales del modelo en `modelo.json`, `k` de contribuciones en `config/modelo.yaml`.
- Fechas en UTC con sufijo `Z`. Nombres en español sin tildes en el código.
- Lenguaje: el sistema «señala para revisión»; nunca «confirma fraude» (`sospecha_confirmada`, no «fraude confirmado»).

## Lo que se verificó antes de escribir código (2026-11-17, UTC)

| Tema | Hallazgo | Fuente |
|---|---|---|
| Entorno de este chat | Llega a GitHub y PyPI; no a OpenML; Docker sin servicio; consola como `root` | Comprobación directa |
| Línea base | 210 pruebas en verde, 6 omitidas | `uv run pytest` |
| `jsonschema` | Disponible en PyPI; implementa el borrador 2020-12 | PyPI |

## Decisiones de esta fase (ADR 0013)

1. **Qué modelo carga la API.** `FRAUDE_MODELO=auto` (por defecto): el real (`datos/modelo/`) si existe, si no el de la muestra (`datos/muestra/modelo/`). También `real` o `muestra`. `/salud` dice cuál y si es reportable.
2. **Recarga.** La API arranca antes que `entrenar`. En cada petición compara la firma (ruta, `mtime_ns` y tamaño) de `modelo.json` y `modelo.joblib`; si cambió, recarga con `modelo.cargar_artefacto`, que comprueba la huella. Un modelo con `estado` distinto de `ok` o con variables distintas de `config/modelo.yaml` no se carga y `/salud` da el motivo.
3. **Cuándo falta el modelo.** Si la transacción trae `variables` y no hay modelo cargado → 503 `modelo_no_disponible`: la evaluación no pudo hacerse y n8n marca `error_evaluacion`. Si no trae `variables` (sintéticas u originales sin ellas), el modelo no hacía falta: 200 con `modelo.evaluable: false`, como dice el contrato 8.2.
4. **Modelo no evaluable en la respuesta.** `puntuacion: null`, `anomalia` y `anomalia_alta: false`; los umbrales del modelo cargado o `null` si no hay. `versiones.modelo` es `null` sin modelo cargado.
5. **Contribuciones.** Solo cuando `anomalia` es verdadera (sección 11: «para cada alerta»), con `k` de `config/modelo.yaml`. El explicador SHAP se crea una vez por modelo cargado.
6. **Respuesta de error, igual en todas las rutas:** `{"id_transaccion": str|null, "error": {"tipo", "mensaje", "detalles"}}`. Tipos: `entrada_invalida` (422), `modelo_no_disponible` (503), `error_interno` (500), `caso_no_encontrado` (404), `caso_ya_revisado` (409). `id_transaccion` se recupera del cuerpo si venía, para la trazabilidad.
7. **Casos.** `POST /casos` recibe lo que calcula n8n (sin `id_caso`, `estado`, `decision_final` ni `revision`) y la API completa esos cuatro campos y, si falta, `fecha_procesamiento`. En un caso `error_evaluacion` pueden faltar `id_transaccion`, `origen`, `monto` y `senales`, porque la entrada pudo ser inválida. `id_caso` es `c-` más 12 cifras hexadecimales aleatorias.
8. **Revisión.** Solo sobre casos `pendiente_revision`; decisiones `sospecha_confirmada` o `sospecha_descartada`; revisor obligatorio, comentario opcional (cadena vacía). Repetir sobre un caso revisado → 409.
9. **`GET /casos`.** `{"total": n, "casos": [...]}`, del más reciente al más antiguo, con filtros opcionales `estado` y `limite` (por defecto 100, máximo 1.000).
10. **Base de datos.** `datos/casos/casos.sqlite`, una tabla `casos` con los campos de la sección 8.5 (los objetos como JSON). Una conexión por operación. La ruta se cambia con `FRAUDE_BD_CASOS`.
11. **Evidencia.** `evidencia` exporta `casos.csv` y `revisiones.csv` desde la base si existe (sección 16); si no existe, lo dice en el resumen.

## Revisión dirigida

1. La API arrancó sin modelo y después `entrenar` lo crea → la siguiente petición lo usa sin reiniciar el servicio.
2. Cuerpo que no es JSON, JSON que no es objeto, campo extra como `Class`, `monto` negativo o `NaN` → 422 con `error.tipo = entrada_invalida`, nunca 200.
3. `modelo.joblib` reemplazado sin actualizar `modelo.json` → no se carga, `/salud` lo dice y `/evaluar` con variables da 503.
4. Revisión de un caso inexistente o ya revisado → 404 o 409 con cuerpo de error, y el caso no cambia.
5. Caso `error_evaluacion` sin `id_transaccion` ni `monto` → se registra y queda `pendiente_revision`.

---

### Tarea 1: esquemas de contrato y pruebas sobre los ejemplos de la especificación

**Archivos:**
- Crear: `docs/contratos/{transaccion,evaluacion,error,caso_nuevo,caso,lista_casos,revision,salud}.schema.json`, `docs/contratos/README.md`
- Crear: `tests/contrato/conftest.py`, `tests/contrato/test_esquemas.py`
- Modificar: `pyproject.toml` (`jsonschema` en `dev`; `testpaths` con `tests/contrato`)

**Interfaces:**
- Produce: fixture `validar(nombre: str, instancia) -> None` (lanza `jsonschema.ValidationError`), y `ejemplos_spec() -> dict[str, dict]` que extrae de `docs/spec.md` los bloques JSON de 8.2 y 8.3.

- [ ] Prueba: los ejemplos 8.2 y 8.3 de `docs/spec.md` cumplen `transaccion` y `evaluacion`; cada esquema es válido en 2020-12; los enumerados de `nivel` coinciden con `config/decision.yaml`; `transaccion` rechaza `Class`, `origen` desconocido y `variables` incompletas; `evaluacion` rechaza campos extra en la raíz y en `modelo` salvo `contribuciones`.
- [ ] Ver fallar, escribir los esquemas, ver pasar, commit `test(contratos): ...` / `docs(contratos): ...`.

### Tarea 2: servicio del modelo

**Archivos:** Crear `src/fraude/servicio_modelo.py`, `tests/unitarias/test_servicio_modelo.py`; modificar `src/fraude/contribuciones.py` (explicador reutilizable).

**Interfaces:**
- Produce: `class ServicioModelo(raiz: Path, modo: str = "auto")` con `estado() -> dict` (`cargado`, `fuente`, `version`, `reportable`, `umbrales`, `motivo`), `disponible() -> bool`, `evaluar(fila: dict[str, float]) -> dict` (la parte `modelo` del 8.3, con `contribuciones` si hay anomalía) y `version() -> str | None`.
- Produce: `contribuciones.Explicador(bosque)` con `.contribuciones(X, variables, k)`; la función `contribuciones(...)` existente lo usa.

- [ ] Pruebas: sin artefacto → `cargado: False` con motivo que menciona `entrenar`; con artefacto de muestra → `fuente: muestra`, `reportable: False`; `auto` prefiere el real; reentrenar cambia la versión sin crear un servicio nuevo; huella alterada o variables distintas de la configuración → no cargado con motivo; `anomalia` y `anomalia_alta` siguen exactamente los umbrales de `modelo.json`; contribuciones solo con anomalía y con `k` de la configuración.

### Tarea 3: `/evaluar` y `/salud`

**Archivos:** Crear `src/fraude/evaluacion.py`, `src/fraude/errores.py`; reescribir `src/fraude/api.py` como `crear_app(raiz: Path | None = None, modo_modelo: str | None = None) -> FastAPI` y `app = crear_app()`; pruebas en `tests/unitarias/test_api.py` y `tests/contrato/test_api_contrato.py`.

**Interfaces:**
- Produce: `evaluacion.evaluar_transaccion(t: Transaccion, config_reglas: dict, servicio: ServicioModelo) -> dict` (lanza `ModeloNoDisponible`); `errores.cuerpo_error(tipo, mensaje, detalles, id_transaccion) -> dict`.

- [ ] Pruebas: ejemplo 8.2 → 200 que cumple `evaluacion`; regla de ubicación sintética activada con razón; original sin `variables` → modelo no evaluable; con `variables` y sin modelo → 503 `modelo_no_disponible` que cumple `error`; entradas de la revisión dirigida 2 → 422 `entrada_invalida` con `id_transaccion` recuperado; `/salud` cumple `salud` con y sin modelo; recarga tras entrenar (revisión dirigida 1).

### Tarea 4: registro de casos

**Archivos:** Crear `src/fraude/registro.py` (`RegistroCasos(ruta)` con `crear(dict) -> dict`, `listar(estado, limite) -> dict`, `revisar(id_caso, dict) -> dict`), `src/fraude/casos.py` (modelos Pydantic `CasoNuevo`, `Revision`); rutas en `api.py`; pruebas unitarias y de contrato.

- [ ] Pruebas: `sin_alerta` → `cerrado`; otros niveles → `pendiente_revision`/`pendiente`; caso `error_evaluacion` sin datos de la transacción se registra (revisión dirigida 5); un nivel distinto de `error_evaluacion` sin `senales` → 422; revisión → `revisado` con fecha UTC; 404 y 409 sin cambiar el caso (revisión dirigida 4); `GET /casos` filtra y ordena; todo cumple `caso` y `lista_casos`; los datos sobreviven a una app nueva sobre la misma base.

### Tarea 5: exportación a la evidencia, CI y documentos

**Archivos:** `src/fraude/evidencia.py` (`casos.csv`, `revisiones.csv`), `tests/punta_a_punta/comprobar_api.py` (biblioteca estándar), `.github/workflows/ci.yml`, ADR 0013, `docs/architecture.md`, versión 0.4.0 en `pyproject.toml`, `__init__.py`, `compose.yaml`, `README.md`, `EJECUTAR.md`, `CHANGELOG.md`, `docs/ESTADO.md`, `docs/supuestos.md`.

- [ ] Pruebas: `evidencia` con base → los dos CSV con cabeceras fijas; sin base → anotado en el resumen.
- [ ] CI: tras `todo --muestra`, `comprobar_api.py` comprueba que la API cargó el modelo recién entrenado, evalúa, registra y revisa un caso y recibe 422 con una entrada inválida; luego `evidencia` y comprobación de `casos.csv`.
