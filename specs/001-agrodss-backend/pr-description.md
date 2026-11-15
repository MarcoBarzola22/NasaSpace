# PR — Backend MVP de AgroDSS (spec 001)

Borrador de la descripción del PR (T052). Escrito para quien revisa el PR del equipo.

## Qué cambió

Backend completo del MVP en `backend/` (FastAPI + Python): balance hídrico diario FAO-56, rendimiento FAO-33, margen bruto, proxy de viento fuerte, rangos entre escenarios y consulta en vivo a NASA POWER. 53 tareas en `specs/001-agrodss-backend/tasks.md`.

- `domain/`: Python puro (ET₀, calendario, balance, FAO-33, economía, viento, faltantes, rangos); una prueba de arquitectura impide importar FastAPI, httpx, Pydantic, red o archivos.
- `services/`: ventanas, validación semántica, resolución de parámetros, cliente NASA POWER, parser, orquestador, constructor de la respuesta y registro de supuestos.
- API: `GET /api/v1/health`, `GET /api/v1/catalog`, `POST /api/v1/simulations`, con errores en español y contrato OpenAPI con instantánea.

## Gobierno

- **Aprobación de `httpx`** (única dependencia nueva respecto de FastAPI/uvicorn/pytest/ruff): 2026-11-15. `requirements.txt` tiene exactamente 5 líneas con versión fija.
- **Enmienda del principio 5 de la constitución** (consulta en vivo a NASA POWER, sin base de datos ni caché, la demo requiere internet): commiteada por el equipo en `docs/constitution.md` (último commit que la modifica: `df619e3`; confirmar). Pendiente su aprobación en este PR.
- Decisiones del equipo del 2026-11-15 incorporadas al spec: CA-1.12 (latitud en [−60°, 60°]), CA-6.10 (Tmáx < Tmín bloquea) y CA-10.9 (rendimiento no calculado ⇒ margen «no calculado», nunca ingreso 0).

## Supuestos del plan §11 y agregados al implementar

Siempre presentes: `RAINFED_NO_IRRIGATION`, `TOP_DOWN_INFILTRATION`, `EXCESS_LOST`, `NO_CAPILLARY_RISE`, `INITIAL_MOISTURE_UNIFORM`, `INITIAL_MOISTURE_EACH_SCENARIO`, `FIXED_DEPTH_PROFILE`, `CONSTANT_PRICES_COSTS`, `PARAMETERS_NOT_CALIBRATED`, `CELL_SCALE_CLIMATE`, `UNIFORM_REDISTRIBUTION`, `LINEAR_ROOT_GROWTH`, `AVAILABLE_WATER_LIMITS`, `HUMIDITY_FROM_DEW_POINT`, `NO_KC_CLIMATE_ADJUSTMENT`.

Cuando ocurren: `FALLOW_EVAPORATION_LAYER`, `INITIAL_ROOT_DEPTH_TEAM`, `SUBST_HUMIDITY_TMIN`, `SUBST_RADIATION_HARGREAVES`, `WINDOW_START_DEFAULT`, `UNPUBLISHED_DATA_BLOCK`, `FAO_REFERENCE_VALUE`, `ROOT_DEPTH_LIMITED`, `NO_RESIDUE_DECLARED`, `FALLOW_KC_BASE_DEFAULT`, `RESIDUE_NO_DECOMPOSITION`, `ET0_NEGATIVE_CLAMPED`, `YIELD_CLIPPED_TO_ZERO`.

**Nuevos al implementar (a confirmar):** `SUBST_WIND_FAO56_DEFAULT` (viento medio faltante ⇒ 2 m/s, CA-6.6), `TEAM_REFERENCE_VALUE` (valores del catálogo con estado «decisión del equipo» distintos de la Zr inicial) y `USER_VALUE` (definido, aún sin uso).

## Pruebas

Desde `backend/`, el 2026-11-15:

| Comando | Resultado |
|---|---|
| `pytest` | 1447 pruebas aprobadas |
| `pytest -m slow` | 39 aprobadas (matriz de invariantes de 1 800 corridas y rendimiento) |
| `pytest -m live -s` | 1 aprobada (NASA POWER real) |
| `ruff check .` / `ruff format --check .` | sin errores |
| `uvicorn app.main:app` + `GET /api/v1/health` | 200 |

Trazabilidad: `tests/nonfunctional/test_traceability.py` comprueba que cada CA del spec aparece en un docstring de prueba; la única excepción justificada es CA-6.9 (inactivo por D-12).

## Prueba en vivo (T050)

Punto −33,68; −65,47, años de inicio 2010, 2015 y 2020, rotaciones A, B y C: HTTP 200 en 2,9 s, los 3 escenarios calculados, error de cierre de masa 0,000000 mm, sin datos faltantes. Días sin cultivo vivo con `WS2M_MAX` > 8 m/s entre 4 y 17 por escenario (el riesgo R-5 no se materializó en este punto). Detalle en `research.md`.

## Para revisar

- Condición humana de T040: contrastar con una consulta propia las unidades y rutas JSON de V-1 (el contraste automático del 2026-11-15 no mostró diferencias).
- Las dudas D-1 a D-16 del spec §9.1 se resolvieron con las propuestas por defecto del plan §2; faltan su confirmación o aplazamiento explícitos.
- Quedan fuera de la API los modos «últimos N años» y «todo el registro» (el servicio existe, T053; exponerlos requiere un campo nuevo del contrato).
