# Arquitectura

Resumen de una página. El detalle y los contratos están en `docs/spec.md` (secciones 7 y 8); los motivos, en `docs/decisions/`.

## Destino (versión 1.0)

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

## Hoy (versión 0.2.0)

```
Computador de ejecución (Omarchy 4)
│
├─ ./fraude ............ guion bash; único que habla con Docker (con sudo si hace falta)
│     ├─ escribe resultados/en_curso/: anfitrion.json, registros/, capturas/
│     └─ llama a Compose
│
└─ Docker Compose (proyecto «fraude»)
      ├─ api ............ FastAPI · 127.0.0.1:8000 · GET /salud
      ├─ n8n ............ n8n 2.47.7 · 127.0.0.1:5678 · GET /webhook/ping
      │                   arranque.sh: importar flujos → publicar → n8n start
      └─ tareas ......... línea de comandos (perfil «tareas», sin puerto)
                          preparar: datos, partición, análisis exploratorio, sintéticos
                          comprueba api y n8n por la red interna y reúne la evidencia
```

### Datos (fase 2)

```
OpenML 1597 (ARFF, MD5 publicada)  ─┐
datos/crudos/creditcard.csv (Kaggle, a mano) ─┴─> leer y verificar (conteos, MD5, huella SHA-256)
                                                     │
                     partición estratificada 56/14/30, índices guardados
                       ├─ ajuste ──────> análisis exploratorio (resultados/en_curso/eda/)
                       ├─ validación     (umbrales y análisis de errores: fase 3)
                       └─ prueba         (solo métricas agregadas: fase 3)

generador sintético ──> datos/sinteticos/ubicacion.json ──> comprobación funcional de la regla
                        (origen «sintetico», sin variables; nunca junto a los originales)
```

| Carpeta | Contenido |
|---|---|
| `datos/crudos/`, `datos/preparados/` | Conjunto real, su huella, la partición y `origen.json` |
| `datos/muestra/` | Muestra para pruebas (N1 y N2), con la misma estructura |
| `datos/sinteticos/` | Transacciones sintéticas de ubicación |

| Módulo de `src/fraude/` | Responsabilidad |
|---|---|
| `transaccion.py` | Forma de la transacción (sección 8.2) |
| `reglas.py` | Reglas deterministas y sus razones (sección 10) |
| `datos.py` | Lectura de ARFF y CSV, descarga, huellas y conteos |
| `particion.py` | Partición estratificada |
| `muestra.py`, `sinteticos.py` | Muestra para pruebas y transacciones sintéticas |
| `eda.py` | Análisis exploratorio y figuras de la parte de ajuste |
| `preparar.py` | Orquesta el paso y escribe `datos.json` |

| Pieza | Archivos |
|---|---|
| Imagen de `api` y `tareas` | `Dockerfile`, `pyproject.toml`, `uv.lock`, `src/fraude/` |
| Servicios | `compose.yaml` |
| n8n | `n8n/arranque.sh`, `n8n/flujos/*.json` |
| Guion de ejecución | `fraude` |
| Configuración | `config/*.yaml` (`modelo.yaml` también guarda los parámetros de datos, partición, muestra y sintéticos) |
| Comprobación automática | `.github/workflows/ci.yml`, `tests/` |

## Reglas de diseño

- Los puertos se publican solo en `127.0.0.1`.
- `api` y `tareas` corren con el usuario de quien ejecuta, para que `datos/` y `resultados/` queden a su nombre.
- La página nunca llama a n8n directamente: lo hace la API.
- La tabla de decisión vive en n8n, con copia en Python y prueba de paridad.
- Lo que solo el anfitrión puede ver (sistema, registros de Docker, capturas) lo recoge `./fraude`; los contenedores no acceden a Docker.
