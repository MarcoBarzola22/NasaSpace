# Tareas 001 — Backend MVP de AgroDSS

| Campo | Valor |
|---|---|
| Especificación | [spec.md](spec.md) (rev. 3, incluye CA-6.10) |
| Plan | [plan.md](plan.md) (aprobado el 2026-11-15) |
| Fecha | 2026-11-15 |
| Total | 52 tareas, de 20 a 30 minutos cada una, en orden de dependencia estricta |

## Reglas de ejecución

1. **Una tarea por vez y en orden.** Una tarea solo empieza cuando todas las de su línea «Depende de» están marcadas como hechas.
2. **REGLA 0 de AGENTS:** durante estas tareas no se lee `docs/Documentacion.md`. Las fuentes son el spec, el plan y `research.md`, que generan T001–T003, junto con la documentación oficial externa (NASA POWER y FAO).
3. **Constitución:**
   - sin base de datos, sin caché y sin escritura de series climáticas (C5);
   - solo NASA POWER, FAO-56, FAO-33 y margen bruto (C2);
   - ningún cálculo en el frontend (C3);
   - ninguna dependencia fuera de fastapi, uvicorn, httpx, pytest y ruff (C1).
4. **Definición de hecho común a toda tarea de código (desde T005).** Ejecutados desde `backend/`, estos tres comandos deben terminar con código 0, además de cumplir el «Hecho cuando» propio de cada tarea:
   - `pytest`
   - `ruff check .`
   - `ruff format --check .`
5. **Trazabilidad:** cada archivo de prueba lleva en su docstring los identificadores CA-x.y que verifica. Lo comprueba T051.
6. **Supuestos nuevos:** si al implementar aparece un supuesto que no está en el spec ni en el plan §11, la tarea se detiene y se consulta al equipo.

**Leyenda:** **RF** son los requisitos del spec que cubre la tarea; **Archivos** son las rutas que crea o modifica (bajo `backend/` salvo que se indique otra cosa).

## Resumen por fases

| Fase | Tareas | Resultado |
|---|---|---|
| 0. Verificaciones previas | T001–T003 | `research.md` con los datos verificados de NASA POWER, el catálogo FAO y los ejemplos FAO-56 |
| 1. Esqueleto | T004–T009 | Proyecto instalable, configuración, constantes, endpoint de salud y regla de arquitectura |
| 2. Dominio científico | T010–T028 | ET₀, calendario, balance hídrico, FAO-33, economía, viento, rangos y faltantes, todo probado sin red |
| 3. Textos y supuestos | T029–T030 | Mensajes en español y registro de supuestos |
| 4. Catálogo y entrada | T031–T037 | `GET /catalog`, modelos de entrada, validación y resolución de parámetros |
| 5. NASA POWER | T038–T041 | Cliente en vivo, parser, procedencia y errores HTTP |
| 6. Orquestación y salida | T042–T048 | `POST /simulations` completo y contrato versionado |
| 7. Cierre | T049–T052 | Pruebas no funcionales, prueba en vivo, trazabilidad y PR |

---

## Fase 0 — Verificaciones previas (sin código)

- [x] **T001 · V-1 — Verificar la API diaria de NASA POWER**
  - **Depende de:** —
  - **RF:** RF-5, RF-6, RF-13 (CA-4.5, CA-5.1, CA-5.5, CA-6.1, CA-13.1)
  - **Qué:** consultar la documentación oficial (power.larc.nasa.gov/docs) y, si hace falta, hacer una consulta manual de prueba para un punto de San Luis. **No se guarda ninguna serie**: solo claves y metadatos.
  - **Archivos:** `specs/001-agrodss-backend/research.md` (sección «V-1 NASA POWER»).
  - **Hecho cuando:** la sección V-1 contiene una tabla con estas 9 filas, sin celdas vacías ni con «pendiente» o «?», y cada fila con al menos un enlace a power.larc.nasa.gov:
    1. URL del endpoint diario de punto;
    2. para cada una de las 7 variables (PRECTOTCORR, T2M_MAX, T2M_MIN, T2MDEW, WS2M, WS2M_MAX, ALLSKY_SFC_SW_DWN): disponible en la comunidad AG (sí/no), nombre largo y unidad exacta tal como la devuelve la API;
    3. ruta JSON y valor del dato de relleno;
    4. ruta JSON de la versión de la API;
    5. ruta JSON de la elevación;
    6. fecha de inicio de cobertura de cada variable;
    7. soporte y valor por defecto de `time-standard` en datos diarios;
    8. límite de parámetros y de rango de fechas por consulta;
    9. esqueleto de la respuesta (solo claves, sin valores de la serie).

    Las 7 variables deben figurar como «disponible: sí». Si alguna figura «no», la tarea queda **bloqueada** y se escala al equipo antes de seguir.

- [x] **T002 · V-2 — Verificar y cargar los valores de referencia FAO del catálogo**
  - **Depende de:** —
  - **RF:** RF-2, RF-3 (CA-2.1, CA-2.3, CA-2.4, CA-2.5, CA-3.3), D-1, D-14
  - **Qué:** transcribir de FAO-56 (tablas 11, 12 y 22, y el capítulo 8 para la Zr inicial) y de FAO-33 (Ky) los valores de los 5 cultivos de D-1: `maize`, `soybean_first`, `soybean_second`, `wheat` y `rye_cover`.
  - **Archivos:** `specs/001-agrodss-backend/research.md` (sección «V-2 Catálogo FAO»).
  - **Hecho cuando:** la sección V-2 contiene una tabla de 5 cultivos × 8 parámetros (Kc inicial, Kc medio, Kc final, duración de las 4 etapas, Zr inicial, Zr máxima, p y Ky), es decir, 40 celdas, y:
    - ninguna celda está vacía;
    - cada celda es un valor con cita (documento, tabla y página o URL) o exactamente «sin referencia» o «no aplica»;
    - las duraciones indican qué región o fila de la tabla 11 se eligió;
    - hay una línea «Revisado por: ‹nombre del agrónomo›, ‹fecha›».

- [x] **T003 · V-3 — Transcribir los ejemplos de FAO-56 para las pruebas**
  - **Depende de:** —
  - **RF:** RF-7 (CA-7.3), RF-6 (CA-6.4)
  - **Archivos:** `specs/001-agrodss-backend/research.md` (sección «V-3 Ejemplos FAO-56»).
  - **Hecho cuando:** la sección V-3 transcribe, con unidad y número de página o URL:
    - todos los datos de entrada y todos los resultados publicados de los ejemplos 2, 8 y 18 de FAO-56. Para el 18, como mínimo: Δ, γ, es, ea, Ra, Rso, Rs, Rns, Rnl, Rn y ET₀;
    - e° y Δ a 20 °C del anexo 2;
    - el número y los valores del ejemplo de FAO-56 que estima Rs a partir de la temperatura (Hargreaves), o la frase «no existe».

---

## Fase 1 — Esqueleto

- [x] **T004 — Crear el esqueleto del backend y fijar dependencias**
  - **Depende de:** T001, T002, T003 (puerta del plan §12: las verificaciones se cierran antes del código)
  - **RF:** RNF-8, RNF-10 (C1)
  - **Archivos:**
    - `requirements.txt`, `pyproject.toml`;
    - paquetes vacíos con `__init__.py` en `app/`, `app/routers/`, `app/core/`, `app/models/`, `app/services/`, `app/domain/` y `app/data/`;
    - carpetas `tests/unit`, `tests/integration`, `tests/api`, `tests/invariants`, `tests/nonfunctional`, `tests/builders`, `tests/live` y `tests/snapshots`.
  - **Hecho cuando:** desde `backend/`, en un entorno virtual nuevo:
    - `pip install -r requirements.txt` termina con código 0;
    - `requirements.txt` tiene exactamente 5 líneas (fastapi, uvicorn, httpx, pytest y ruff), todas con versión fija `==`;
    - `python -c "import app.routers, app.core, app.models, app.services, app.domain"` termina con código 0;
    - `ruff check .` y `ruff format --check .` terminan con código 0;
    - `pyproject.toml` declara Python ≥ 3.11, `addopts` con `-m "not live"` y los marcadores `live` y `slow`.

- [x] **T005 — Configuración desde variables de entorno**
  - **Depende de:** T004, T001
  - **RF:** RF-5 (CA-5.6), RF-4 (CA-4.5)
  - **Archivos:** `app/core/config.py`, `tests/unit/test_config.py`
  - **Hecho cuando:** `pytest tests/unit/test_config.py` pasa con dos pruebas:
    - `test_settings_defaults`: URL base de POWER, timeout de conexión 10 s, timeout de lectura 60 s, CORS `http://localhost:5173` y fechas de inicio de cobertura de las 7 variables iguales a las de `research.md` §V-1;
    - `test_settings_env_override`: las variables `AGRODSS_POWER_BASE_URL`, `AGRODSS_POWER_CONNECT_TIMEOUT_S`, `AGRODSS_POWER_READ_TIMEOUT_S` y `AGRODSS_CORS_ORIGINS` cambian los valores.

- [x] **T006 — Constantes del modelo y jerarquía de excepciones**
  - **Depende de:** T004
  - **RF:** RF-6, RF-8, RF-11, RF-16 (CA-1.9, CA-8.10, CA-8.16, CA-11.1, CA-16.4)
  - **Archivos:** `app/core/constants.py`, `app/core/exceptions.py`, `tests/unit/test_constants.py`
  - **Hecho cuando:** `pytest tests/unit/test_constants.py` pasa con dos pruebas:
    - `test_constants_match_approved_decisions`, que verifica uno a uno estos valores:
      - umbral de viento 8,0 m/s; Kc base de barbecho 0,20; Ze 0,15 m; reducción por rastrojo 0,05 por cada 10 %;
      - tolerancia de cierre 0,01 mm; ε diario 1e-9 mm;
      - kRs 0,16; corrección de Tdew 2,0 °C; viento por defecto 2,0 m/s; albedo 0,23; σ 4,903e-9;
      - límites: 3 rotaciones, 10 años, 3,0 m de profundidad, Kc ≤ 2,0, Ky ≤ 2,0, Ym ≤ 30 t/ha, etapas ≤ 365 días, Kc de barbecho ≤ 1,0;
      - inicio de ventana por defecto (1, 7) y caja aproximada de San Luis (latitud −36,0 a −31,8; longitud −67,6 a −64,8);
    - `test_exception_hierarchy`: existen `InputValidationError`, `PowerUnreachableError`, `PowerTimeoutError`, `PowerRateLimitedError`, `PowerBadResponseError` y `CalculationIntegrityError`, y las 4 de NASA heredan de `PowerError`.

- [ ] **T007 — Aplicación FastAPI, endpoint de salud, CORS e identificador de solicitud**
  - **Depende de:** T005, T006
  - **RF:** RNF-13, RF-16 (CA-16.4: `request_id`)
  - **Archivos:** `app/main.py`, `app/routers/health.py`, `tests/api/test_health.py`
  - **Hecho cuando:**
    - `pytest tests/api/test_health.py` pasa verificando:
      - `GET /api/v1/health` → 200 con `status == "ok"`, `model_version` no vacío y `contract_version == "1.0"`;
      - la cabecera `X-Request-ID` es un UUID válido;
      - una consulta CORS de verificación previa desde `http://localhost:5173` devuelve ese origen en `access-control-allow-origin`;
      - `GET /docs` → 200;
    - `uvicorn app.main:app` arranca y `curl http://localhost:8000/api/v1/health` responde 200 (verificación manual anotada en el PR).

- [x] **T008 — Tipos del dominio (dataclasses inmutables)**
  - **Depende de:** T004
  - **RF:** RF-3, RF-4, RF-8
  - **Archivos:** `app/domain/types.py`, `tests/unit/test_types.py`
  - **Hecho cuando:** `pytest tests/unit/test_types.py` pasa verificando:
    - que existen `Stages`, `SowingSpec`, `CropSpec`, `RotationSpec`, `ParcelSpec`, `Window`, `DailyClimate`, `Weather`, `CropSegment`, `FallowSegment` y `Timeline`;
    - que asignar un atributo de cualquiera de ellas lanza `FrozenInstanceError`;
    - que `Stages.total_days` es la suma de las 4 etapas;
    - que `DailyClimate` acepta `None` en cada una de las 7 variables.

- [x] **T009 — Prueba de la regla de arquitectura del dominio**
  - **Depende de:** T006, T008
  - **RF:** RNF-7 (plan §3, decisión T-5)
  - **Archivos:** `tests/nonfunctional/test_architecture.py`
  - **Hecho cuando:** `pytest tests/nonfunctional/test_architecture.py` pasa con dos pruebas:
    - `test_domain_imports_allowed_only`: analiza con `ast` todos los `.py` de `app/domain/` y solo admite la biblioteca estándar, `app.domain.*`, `app.core.constants` y `app.core.exceptions`;
    - `test_checker_rejects_forbidden_import`: el mismo verificador rechaza un fragmento de código con `import fastapi`.

---

## Fase 2 — Dominio científico (sin red)

- [x] **T010 — ET₀: funciones psicrométricas (FAO-56, ec. 7, 8, 11–14)**
  - **Depende de:** T003, T006, T009
  - **RF:** RF-7
  - **Archivos:** `app/domain/et0.py`, `tests/unit/test_et0.py`
  - **Hecho cuando:** `pytest tests/unit/test_et0.py -k psychrometric` pasa verificando:
    - P y γ del ejemplo 2 con la tolerancia del redondeo publicado (según `research.md` §V-3);
    - e°(20 °C) y Δ(20 °C) iguales a los del anexo 2 transcritos en V-3, con ±0,001;
    - `ea(Tdew) == e°(Tdew)`.

- [x] **T011 — ET₀: radiación (FAO-56, ec. 21–25 y 37–40)**
  - **Depende de:** T010
  - **RF:** RF-7
  - **Archivos:** `app/domain/et0.py`, `tests/unit/test_et0.py`
  - **Hecho cuando:** `pytest tests/unit/test_et0.py -k radiation` pasa con dos pruebas:
    - `test_radiation_fao56_example_8`: Ra igual al valor de V-3, con ±0,1 MJ/m²/día;
    - `test_radiation_polar_latitude_no_error`: con latitud 70° S en junio devuelve Ra ≥ 0 sin excepción.

- [x] **T012 — ET₀ Penman–Monteith, radiación de Hargreaves y ET₀ negativa**
  - **Depende de:** T011
  - **RF:** RF-7 (CA-7.1, CA-7.2, CA-7.3), RF-6 (CA-6.4)
  - **Archivos:** `app/domain/et0.py`, `tests/unit/test_et0.py`
  - **Hecho cuando:** `pytest tests/unit/test_et0.py -k "et0 or hargreaves"` pasa con:
    - `test_et0_fao56_example_18`: ET₀ dentro de ±0,1 mm/día del valor de V-3, y cada intermedio dentro de la tolerancia de su redondeo publicado;
    - `test_hargreaves_capped_by_rso`: Rs estimada ≤ Rso;
    - `test_clamp_negative_et0`: −0,2 da (0,0; True) y 1,5 da (1,5; False);
    - el ejemplo de Hargreaves de V-3, si existe.

- [x] **T013 — Calendario: ventanas, fechas de siembra y fin de ciclo**
  - **Depende de:** T008
  - **RF:** RF-3 (CA-3.5, CA-3.8), RF-4 (CA-4.2, CA-4.3)
  - **Archivos:** `app/domain/calendar.py`, `tests/unit/test_calendar.py`
  - **Hecho cuando:** `pytest tests/unit/test_calendar.py -k "window or sowing or cycle"` pasa verificando:
    - ventana 2008 = 730 días (2008-07-01 a 2010-06-30) y ventana 2011 = 731 días;
    - con inicio el 1-jul-2008: (año 1, 1-abr) → 2009-04-01 y (año 2, 15-nov) → 2009-11-15;
    - siembra 2008-10-15 con 150 días → fin 2009-03-13;
    - `is_feb_29` detecta el 29 de febrero.

- [x] **T014 — Calendario: línea de tiempo y problemas de calendario por escenario**
  - **Depende de:** T013
  - **RF:** RF-3 (CA-3.6, CA-3.7, CA-3.11), RF-8 (CA-8.2)
  - **Archivos:** `app/domain/calendar.py`, `tests/unit/test_calendar.py`
  - **Hecho cuando:** `pytest tests/unit/test_calendar.py -k "timeline or calendar_issues"` pasa verificando:
    - la suma de días de los segmentos es `n_days` y cada fecha aparece exactamente una vez;
    - el rastrojo del barbecho inicial es el de la rotación, y el de cada barbecho posterior es el del cultivo anterior;
    - no hay barbecho entre un trigo que termina el 2009-12-02 y una soja de segunda sembrada el 2009-12-03 (CL-17);
    - una superposición que solo ocurre en escenarios sin 29 de febrero se informa solo para esos años (CL-4);
    - un ciclo que solo excede la ventana en un escenario se informa solo para ese año (CL-5).

- [x] **T015 — Curva de Kc por etapas y crecimiento radicular**
  - **Depende de:** T006, T008
  - **RF:** RF-8 (CA-8.4, CA-8.8), RF-3 (CA-3.10)
  - **Archivos:** `app/domain/kc_curve.py`, `app/domain/root_growth.py`, `tests/unit/test_kc_curve.py`, `tests/unit/test_root_growth.py`
  - **Hecho cuando:** `pytest tests/unit/test_kc_curve.py tests/unit/test_root_growth.py` pasa verificando:
    - con etapas 30/40/50/30 y Kc 0,30/1,20/0,35, el Kc de los días 1, 30, 31, 70, 120, 121 y 150 coincide con la fórmula del plan §7.4 (±1e-12); en particular, el día 70 vale 1,20 y el día 150 vale 0,35;
    - Zr el día 1 es la Zr inicial; el día L_ini + L_dev es la Zr máxima; después se mantiene constante;
    - Zr nunca supera D cuando la Zr máxima es mayor que D.

- [x] **T016 — Redistribución entre compartimentos y factor de rastrojo**
  - **Depende de:** T006
  - **RF:** RF-8 (CA-8.7, CA-8.10)
  - **Archivos:** `app/domain/water_balance.py` (funciones auxiliares), `tests/unit/test_redistribution.py`
  - **Hecho cuando:** `pytest tests/unit/test_redistribution.py` pasa verificando:
    - en ≥ 20 combinaciones parametrizadas, `W_act + W_low` se conserva con |Δ| ≤ 1e-12;
    - el caso del plan (31,2 mm; de 1,2 a 0,15 m de profundidad) da W_act = 3,9 y W_low = 27,3 (±1e-9);
    - con `z_old == D`, profundizar no mueve agua;
    - `residue_factor` de 0, 50 y 100 % vale 1,0; 0,75 y 0,5.

- [x] **T017 — Balance diario (1/4): estado inicial, lluvia en cascada y barbecho**
  - **Depende de:** T014, T015, T016
  - **RF:** RF-8 (CA-8.1, CA-8.3, CA-8.10, CA-8.12, CA-8.13, CA-8.14)
  - **Archivos:** `app/domain/water_balance.py`, `tests/unit/test_water_balance.py`
  - **Hecho cuando:** `pytest tests/unit/test_water_balance.py -k fallow` pasa verificando, con D = 1,2 m y AWC = 0,16 (capacidad 192 mm):
    - CL-13: 300 mm de lluvia con el perfil al 50 % dejan el almacenamiento en 192,0 y un excedente de 300 − 96 = 204 mm;
    - CL-14: con 0 % y sin lluvia, la evaporación es 0 todos los días;
    - CL-15: con 100 %, toda la lluvia del día 1 es excedente;
    - con 120 días secos, W_low no cambia y la evaporación total no supera 24 mm (la capacidad de la capa de 0,15 m);
    - `0 ≤ almacenamiento ≤ 192` todos los días.

- [x] **T018 — Balance diario (2/4): días con cultivo (Kc, Ks, ETc, ETa)**
  - **Depende de:** T017
  - **RF:** RF-8 (CA-8.8, CA-8.9, CA-8.15), RF-9 (CA-9.6: días con estrés)
  - **Archivos:** `app/domain/water_balance.py`, `tests/unit/test_water_balance.py`
  - **Hecho cuando:** `pytest tests/unit/test_water_balance.py -k crop_day` pasa verificando:
    - un caso de 5 días calculado a mano (con el cálculo en el docstring) reproduce ETc, Ks, ETa y almacenamiento con |error| ≤ 1e-9 mm;
    - con la zona radicular en PMP, Ks = 0 y ETa = 0;
    - `ETa ≤ ETc` todos los días;
    - `stress_days` es exactamente la cantidad de días con Ks < 1.

- [x] **T019 — Balance diario (3/4): transferencia entre segmentos y crecimiento radicular**
  - **Depende de:** T018
  - **RF:** RF-8 (CA-8.4, CA-8.5, CA-8.6, CA-8.7), RF-9 (CA-9.6: almacenamiento al sembrar y al terminar)
  - **Archivos:** `app/domain/water_balance.py`, `tests/unit/test_water_balance.py`
  - **Hecho cuando:** `pytest tests/unit/test_water_balance.py -k transfer` pasa verificando:
    - en una rotación de 3 cultivos y 3 barbechos, `storage_at_end_mm` de cada segmento es **igual** al `storage_at_start_mm` del siguiente;
    - el caso del plan §7.4: maíz cosechado con 31,2 mm, y al día siguiente de barbecho W_act = 3,9 y W_low = 27,3;
    - CL-16: con la capa superficial en PMP y agua debajo, el cultivo tiene Ks < 1 los primeros días y W_low baja a medida que crece Zr;
    - CL-17: un barbecho de 0 días también cumple la igualdad.

- [x] **T020 — Balance diario (4/4): cierre de masa y error de integridad**
  - **Depende de:** T019
  - **RF:** RF-8 (CA-8.16, CA-8.17), RF-16 (CA-16.5)
  - **Archivos:** `app/domain/water_balance.py`, `tests/unit/test_water_balance.py`
  - **Hecho cuando:** `pytest tests/unit/test_water_balance.py -k closure` pasa con:
    - una corrida sintética de 731 días que cierra con |error| ≤ 0,01 mm, donde `BalanceRun` expone `initial_storage_mm`, `final_storage_mm`, lluvia, ETa de cultivos, evaporación de barbecho, excedente y `closure_mm`;
    - `test_integrity_error_on_forced_violation`: una perturbación inyectada con `monkeypatch` lanza `CalculationIntegrityError`.

- [x] **T021 — Generador de clima sintético y pruebas de invariantes**
  - **Nota de ejecución:** `pyproject.toml` pasó a `addopts = "-m 'not live and not slow'"`, de modo que `pytest` a secas excluye la matriz completa de 50 semillas y `pytest -m slow` la ejecuta (6,5 s). Antes solo excluía `live`.
  - **Depende de:** T020
  - **RF:** RF-8 (CA-8.2, CA-8.6, CA-8.14, CA-8.15, CA-8.16), C4
  - **Archivos:** `tests/builders/weather.py`, `tests/invariants/test_balance_invariants.py`
  - **Hecho cuando:**
    - `pytest tests/invariants` (matriz reducida: 5 semillas × 3 suelos × 3 humedades iniciales × 4 rotaciones = 180 corridas) termina con código 0;
    - `pytest tests/invariants -m slow` (50 semillas) termina con código 0;
    - el docstring enumera y el código verifica en cada corrida las condiciones del plan §9.3: límites de los dos compartimentos, `ETa ≤ ETc`, `ETa ≤ disponible`, `E ≤ E_dem`, cierre diario ≤ 1e-9 mm, cierre total ≤ 0,01 mm, días consecutivos sin huecos y transferencia exacta entre segmentos.

- [ ] **T022 — Rendimiento bajo déficit (FAO-33)**
  - **Depende de:** T006, T008
  - **RF:** RF-9 (CA-9.1–CA-9.7)
  - **Archivos:** `app/domain/yield_response.py`, `tests/unit/test_yield_response.py`
  - **Hecho cuando:** `pytest tests/unit/test_yield_response.py` pasa verificando:
    - ETa 418,9 mm, ETm 642,5 mm, Ky 1,25 e Ym 9 dan Ya = 5,0848 (±1e-4);
    - Ky 1,5 con ETa/ETm = 0,2 da Ya = 0 y la bandera de recorte en True;
    - ETm = 0 da Ya `None` con motivo;
    - un cultivo de cobertura da Ya `None` con la nota «No aplica (cultivo de cobertura).»;
    - `0 ≤ Ya ≤ Ym` en 100 combinaciones parametrizadas.

- [ ] **T023 — Ingreso y margen bruto**
  - **Depende de:** T022
  - **RF:** RF-10 (CA-10.1–CA-10.4, CA-10.7)
  - **Archivos:** `app/domain/economics.py`, `tests/unit/test_economics.py`
  - **Hecho cuando:** `pytest tests/unit/test_economics.py` pasa verificando:
    - grano con Ya 5,0848, precio 180 y costos 620: ingreso 915,264 y margen 295,264 (±1e-6);
    - cobertura con costos 95: ingreso 0 y margen −95, con el rótulo «Margen bruto negativo»;
    - una rotación con un cultivo sin precio queda con `status == "not_computed"` y ese cultivo en `crops_missing_economics`;
    - ningún texto producido contiene «pérdida».

- [ ] **T024 — Proxy de viento fuerte (WS2M_MAX > 8 m/s sin cultivo vivo)**
  - **Depende de:** T014
  - **RF:** RF-11 (CA-11.1–CA-11.4, CA-11.6)
  - **Archivos:** `app/domain/wind_proxy.py`, `tests/unit/test_wind_proxy.py`
  - **Hecho cuando:** `pytest tests/unit/test_wind_proxy.py` pasa verificando:
    - 8,0 sin cultivo no cuenta; 8,1 sin cultivo cuenta; 8,1 con cultivo no cuenta;
    - `None` sin cultivo cuenta como «sin dato»;
    - `live_crop_days + no_live_crop_days == window_days`;
    - la función solo recibe la serie cruda de WS2M_MAX (en su firma no hay parámetro para WS2M).

- [ ] **T025 — Rangos descriptivos y diferencias de margen entre rotaciones**
  - **Depende de:** T008
  - **RF:** RF-12 (CA-12.1–CA-12.3), RF-15 (CA-15.4), D-15
  - **Archivos:** `app/domain/stats.py`, `tests/unit/test_stats.py`
  - **Hecho cuando:** `pytest tests/unit/test_stats.py` pasa verificando:
    - [1, 5, 3] da mínimo 1, mediana 3 y máximo 5;
    - [5,08; 7,54] da mediana 6,31;
    - con n = 1 devuelve el valor único y la bandera «sin rango»;
    - las diferencias de margen B−A, C−A y C−B solo se generan cuando ambos márgenes existen (si uno es `None`, el par se excluye).

- [ ] **T026 — Clasificación de datos faltantes e inconsistentes**
  - **Depende de:** T006, T008
  - **RF:** RF-6 (CA-6.1, CA-6.3, CA-6.10), RF-11 (CA-11.4)
  - **Archivos:** `app/domain/missing_data.py`, `tests/unit/test_missing_data.py`
  - **Hecho cuando:** `pytest tests/unit/test_missing_data.py -k classify` pasa verificando:
    - `None` en PRECTOTCORR, T2M_MAX o T2M_MIN → bloqueo con variable y fechas;
    - Tmáx < Tmín → bloqueo «dato inconsistente de la fuente» con la fecha;
    - `None` en ALLSKY_SFC_SW_DWN, T2MDEW o WS2M → aparece en la lista de sustituciones, sin bloqueo;
    - `None` en WS2M_MAX → ni bloqueo ni sustitución.

- [ ] **T027 — Sustituciones FAO-56 para la ET₀**
  - **Depende de:** T026, T012
  - **RF:** RF-6 (CA-6.2, CA-6.4–CA-6.8)
  - **Archivos:** `app/domain/missing_data.py`, `tests/unit/test_missing_data.py`
  - **Hecho cuando:** `pytest tests/unit/test_missing_data.py -k substitution` pasa verificando:
    - Rs faltante = `min(0,16·√(Tmáx−Tmín)·Ra, Rso)` (±1e-9);
    - Tdew faltante = Tmín − 2,0;
    - u2 faltante = 2,0;
    - cada sustitución queda registrada con variable, método y fecha;
    - `test_no_interpolation`: con días vecinos de valores distintos, el valor sustituido es idéntico al de la fórmula y no cambia si se modifican los vecinos.

- [ ] **T028 — Cobertura de la fuente y bloqueo por datos no publicados**
  - **Depende de:** T026, T005
  - **RF:** RF-4 (CA-4.5), plan §6.3 (`UNPUBLISHED_DATA_BLOCK`)
  - **Archivos:** `app/domain/missing_data.py`, `tests/unit/test_missing_data.py`
  - **Hecho cuando:** `pytest tests/unit/test_missing_data.py -k coverage` pasa verificando:
    - una racha final de `None` en la radiación bloquea las ventanas que la incluyen, con el código `UNPUBLISHED_DATA_BLOCK`;
    - un `None` interior no bloquea por cobertura;
    - una ventana que empieza antes del inicio configurado de una variable queda bloqueada;
    - una ventana completamente cubierta no se bloquea.

---

## Fase 3 — Textos y supuestos

- [ ] **T029 — Mensajes en español y prueba de lenguaje**
  - **Depende de:** T006
  - **RF:** RF-17 (CA-17.1–CA-17.5), RF-16 (CA-16.6), RF-14 (CA-14.1), RF-10 (CA-10.7), CA-1.11
  - **Archivos:** `app/core/messages.py`, `tests/unit/test_messages.py`, `tests/nonfunctional/test_language.py`
  - **Hecho cuando:** `pytest tests/unit/test_messages.py tests/nonfunctional/test_language.py` pasa verificando:
    - ningún texto de `messages.py` contiene, sin distinguir mayúsculas, «pérdida neta», «probabilidad», «precisión», «recomendada», «óptima» ni «mejor»;
    - existen los 7 códigos de advertencia: `HISTORICAL_DESCRIPTIVE`, `UNCALIBRATED_PARAMETERS`, `CELL_SCALE_DATA`, `NOT_A_RECOMMENDATION`, `SUBSTITUTIONS_PRESENT`, `SCENARIOS_BLOCKED` y `OUTSIDE_SAN_LUIS`;
    - existe una descripción para cada código de supuesto de CA-14.2, CA-14.3 y el plan §11.

- [ ] **T030 — Registro de supuestos**
  - **Depende de:** T029
  - **RF:** RF-14 (CA-14.1–CA-14.4), RNF-1
  - **Archivos:** `app/services/assumptions.py`, `tests/unit/test_assumptions.py`
  - **Hecho cuando:** `pytest tests/unit/test_assumptions.py` pasa verificando:
    - `add_always_on()` produce exactamente los códigos de la lista «siempre» (CA-14.2 más el plan §11) escrita en el test;
    - 3 registros diarios con el mismo código y alcance dan 1 entrada con `count == 3` y las fechas ordenadas;
    - dos ejecuciones con la misma secuencia producen listas idénticas.

---

## Fase 4 — Catálogo y contrato de entrada

- [x] **T031 — Catálogo FAO en JSON y su carga validada**
  - **Depende de:** T002, T029
  - **RF:** RF-2 (CA-2.1–CA-2.5)
  - **Archivos:** `app/data/crop_catalog.json`, `app/services/catalog_service.py`, `tests/unit/test_catalog.py`, `specs/001-agrodss-backend/research.md`
  - **Nota de ejecución:** se hizo antes que T029 por pedido del equipo. `CatalogError` y sus mensajes en español viven en `catalog_service.py`; al hacer T029 hay que moverlos a `core/messages.py` y `core/exceptions.py`.
  - **Hecho cuando:**
    - `pytest tests/unit/test_catalog.py` pasa verificando que:
      - hay 5 cultivos con los códigos de D-1;
      - cada valor numérico tiene un `source` no vacío;
      - los valores sin número tienen `status` igual a «sin referencia» o «no aplica»;
      - no existen campos de Ym, precio ni costo;
      - un catálogo con un valor sin `source` hace fallar la carga con un error explícito;
    - `research.md` §V-2 incluye la línea «Catálogo cargado y cotejado: ‹nombre›, ‹fecha›».

- [ ] **T032 — Endpoint `GET /api/v1/catalog`**
  - **Depende de:** T031, T007
  - **RF:** RF-2 (CA-2.1, CA-2.6), RF-11 (CA-11.5)
  - **Archivos:** `app/models/catalog.py`, `app/routers/catalog.py`, `tests/api/test_catalog_endpoint.py`
  - **Hecho cuando:** `pytest tests/api/test_catalog_endpoint.py` pasa verificando:
    - la respuesta es 200;
    - `fallow.kc_base_default == 0.2` y `fallow.evaporation_layer_m == 0.15`;
    - `wind_proxy.variable == "WS2M_MAX"` y `wind_proxy.threshold_ms == 8.0`;
    - `limits.max_rotations == 3` y `limits.max_start_years == 10`;
    - cada cultivo tiene `label`.

- [ ] **T033 — Modelos Pydantic de la solicitud (validación estructural)**
  - **Depende de:** T006
  - **RF:** RF-1 (CA-1.1–CA-1.5), RF-3 (CA-3.1, CA-3.2, CA-3.9), RF-4 (CA-4.1), RF-10 (CA-10.5)
  - **Archivos:** `app/models/common.py`, `app/models/request.py`, `tests/unit/test_request_model.py`
  - **Hecho cuando:** `pytest tests/unit/test_request_model.py` pasa verificando:
    - el ejemplo de solicitud del plan §5.2 valida;
    - ≥ 15 casos parametrizados fuera de rango (uno por cada fila con límite de la tabla del plan §5.2) fallan con la ruta de campo esperada;
    - un campo desconocido falla;
    - `stage_lengths_days` con 3 de sus 4 claves falla.

- [ ] **T034 — Errores 422 en español y regla de riego**
  - **Depende de:** T033, T029
  - **RF:** RF-16 (CA-16.1, CA-16.6), RF-1 (CA-1.8)
  - **Archivos:** `app/models/errors.py`, `app/core/error_handlers.py`, `tests/api/test_validation_errors.py`
  - **Hecho cuando:** `pytest tests/api/test_validation_errors.py` pasa, sobre una app de prueba con el manejador, verificando:
    - un cuerpo inválido devuelve 422 con `error.category == "input"`, `error.code == "invalid_input"`, `retryable == false` y `request_id` presente;
    - `details[].field` tiene el formato `rotations[0].crops[1].ym_t_ha`;
    - ningún `details[].message` contiene «Field required», «Input should» ni «Extra inputs»;
    - una clave `irrigation_mm` devuelve `code == "irrigation_not_supported"` con el mensaje de CA-1.8.

- [ ] **T035 — Validación semántica (1/2): parcela, catálogo y reglas de cultivo**
  - **Depende de:** T033, T031
  - **RF:** RF-1 (CA-1.3, CA-1.10), RF-2 (CA-2.3), RF-3 (CA-3.2, CA-3.9, CA-3.13), RF-10 (CA-10.6), RF-16 (CA-16.1)
  - **Archivos:** `app/services/validation.py`, `tests/unit/test_validation.py`
  - **Hecho cuando:** `pytest tests/unit/test_validation.py -k "parcel or crop"` pasa verificando:
    - una solicitud con θPMP ≥ θCC, Ym ausente en un cultivo de grano y precio en uno de cobertura devuelve **exactamente 3** errores en una sola llamada;
    - también se detectan, con un error cada uno: `crop_code` inexistente, `rye_cover` sin Kc («sin referencia» omitido), Zr inicial > Zr máxima y datos económicos sin `currency`.

- [ ] **T036 — Validación semántica (2/2): años, fechas y calendario por escenario**
  - **Depende de:** T035, T014
  - **RF:** RF-1 (CA-1.12), RF-3 (CA-3.6–CA-3.8), RF-4 (CA-4.3, CA-4.4), CA-5.3
  - **Archivos:** `app/services/validation.py`, `tests/unit/test_validation.py`; agrega `MAX_ABS_LATITUDE_DEG = 60.0` a `app/core/constants.py` y su aserción a `tests/unit/test_constants.py`
  - **Hecho cuando:** `pytest tests/unit/test_validation.py -k "window or calendar or latitude"` pasa, con el reloj fijado en 2026-11-15, verificando que dan error:
    - una latitud fuera de [−60, 60] (por ejemplo −61 y 75), mientras que −33,68 y los extremos −60 y 60 son válidos (CA-1.12; decisión del equipo del 2026-11-15);
    - el año 2025 (su ventana termina el 2027-06-30);
    - años repetidos;
    - una fecha de inicio o de siembra el 29 de febrero;
    - una superposición presente solo en algunos escenarios (el error nombra esos años);
    - un ciclo fuera de la ventana (el error nombra cultivo y año);

    y que la solicitud del plan §5.2 da 0 errores.

- [ ] **T037 — Resolución de parámetros efectivos y su origen**
  - **Depende de:** T035, T030, T031
  - **RF:** RF-1 (CA-1.6, CA-1.9), RF-3 (CA-3.3, CA-3.4, CA-3.10, CA-3.12), RF-4 (D-6), RF-14 (CA-14.3)
  - **Archivos:** `app/services/parameter_resolver.py`, `tests/unit/test_parameter_resolver.py`
  - **Hecho cuando:** `pytest tests/unit/test_parameter_resolver.py` pasa verificando, con la solicitud del plan §5.2:
    - `ky` del maíz en A tiene origen `fao_reference`, su `source` coincide con el catálogo y existe el supuesto `FAO_REFERENCE_VALUE` con ese alcance;
    - `kc_mid` del maíz en A tiene origen `user`;
    - `root_depth_max_m` vale 1,2, tiene nota y genera el supuesto `ROOT_DEPTH_LIMITED`;
    - la rotación B tiene `initial_residue_cover_pct` 0 y el supuesto `NO_RESIDUE_DECLARED`;
    - `fallow_kc_base` vale 0,20 con origen `team_default`;
    - `profile_capacity_mm == 192.0` e `initial_storage_mm == 96.0`;
    - sin fecha de inicio, se usa el 1 de julio con el supuesto `WINDOW_START_DEFAULT`.

---

## Fase 5 — NASA POWER

- [ ] **T038 — Generador de respuestas sintéticas de NASA POWER**
  - **Depende de:** T001
  - **RF:** RF-5, RF-6 (soporte de pruebas, plan §9.4, decisión T-22)
  - **Archivos:** `tests/builders/power_payload.py`, `tests/unit/test_power_payload_builder.py`
  - **Hecho cuando:** `pytest tests/unit/test_power_payload_builder.py` pasa verificando:
    - el payload por defecto tiene las 7 variables con las unidades y rutas JSON de `research.md` §V-1, y fechas contiguas;
    - las opciones `fill_dates`, `drop_parameter`, `units_override`, `without_elevation` y `trailing_fill` producen cada una su efecto;
    - el generador no abre ningún archivo (`open` bloqueado con `monkeypatch` durante la prueba).

- [ ] **T039 — Cliente de NASA POWER con httpx**
  - **Depende de:** T005, T006, T038
  - **RF:** RF-5 (CA-5.1, CA-5.4, CA-5.6, CA-5.7), RNF-11, RNF-12
  - **Archivos:** `app/services/power_client.py`, `app/core/dependencies.py`, `tests/integration/test_power_client.py`
  - **Hecho cuando:** `pytest tests/integration/test_power_client.py` pasa con `httpx.MockTransport` verificando:
    - la consulta lleva exactamente los parámetros `parameters`, `community`, `latitude`, `longitude`, `start`, `end` y `format`, más `time-standard` si V-1 lo confirmó;
    - el User-Agent no contiene correo ni nombre de usuario;
    - se hace 1 sola llamada y sin reintentos;
    - `ConnectError` → `PowerUnreachableError`;
    - `ReadTimeout` y `ConnectTimeout` → `PowerTimeoutError`;
    - 429 → `PowerRateLimitedError`;
    - 500 y 404 → `PowerBadResponseError`;
    - los timeouts usados son los de `Settings`.

- [ ] **T040 — Parser de la respuesta y procedencia**
  - **Depende de:** T039, T008
  - **RF:** RF-5 (CA-5.2, CA-5.5), RF-6 (CA-6.1), RF-13 (CA-13.1, CA-13.2)
  - **Archivos:** `app/services/climate_parser.py`, `tests/integration/test_climate_parser.py`
  - **Hecho cuando:** `pytest tests/integration/test_climate_parser.py` pasa verificando:
    - −999 → `None` y fecha ausente → `None`;
    - dan `PowerBadResponseError` un cuerpo que no es JSON, la falta de `properties.parameter`, la falta de WS2M_MAX, una unidad distinta y la falta de elevación;
    - la procedencia contiene los campos de CA-13.1 y el rótulo exacto de CA-13.2;
    - con `open` en modo escritura bloqueado mediante `monkeypatch`, el parseo termina sin error.

- [ ] **T041 — Manejadores HTTP de errores de NASA, integridad e inesperados**
  - **Depende de:** T007, T029, T006
  - **RF:** RF-16 (CA-16.4, CA-16.5), RF-5 (CA-5.4)
  - **Archivos:** `app/core/error_handlers.py`, `tests/api/test_error_handlers.py`
  - **Hecho cuando:** `pytest tests/api/test_error_handlers.py` pasa, sobre una app de prueba que lanza cada excepción, verificando:
    - `PowerUnreachableError` → 503 `power_unreachable` con `retryable == true`;
    - `PowerTimeoutError` → 504 `power_timeout`, con un mensaje que incluye el timeout configurado en segundos;
    - `PowerRateLimitedError` → 503 `power_rate_limited`;
    - `PowerBadResponseError` → 502 `power_bad_response`;
    - `CalculationIntegrityError` → 500 `calculation_integrity` con `retryable == false`;
    - una excepción genérica → 500 `unexpected_error`;
    - ningún cuerpo contiene «Traceback» ni la cadena «app.»;
    - todos llevan un `request_id` igual a la cabecera `X-Request-ID`.

---

## Fase 6 — Orquestación y salida

- [ ] **T042 — Modelos Pydantic de la respuesta**
  - **Depende de:** T033, T029
  - **RF:** RF-15 (CA-15.1, CA-15.3, CA-15.5)
  - **Archivos:** `app/models/response.py`, `tests/unit/test_response_model.py`
  - **Hecho cuando:** `pytest tests/unit/test_response_model.py` pasa verificando:
    - el ejemplo de respuesta del plan §5.3 valida contra `SimulationResponse`;
    - todo campo numérico tiene un sufijo de unidad de la lista del plan §9.5 o figura en la lista `ALLOWED_DIMENSIONLESS` escrita en el test;
    - el modelo no tiene campos de serie diaria (CA-15.5).

- [ ] **T043 — Servicio de simulación (1/2): escenarios, faltantes y ET₀**
  - **Depende de:** T037, T040, T027, T028, T012, T013
  - **RF:** RF-4 (CA-4.5), RF-5 (CA-5.1), RF-6 (CA-6.3, CA-6.7), RF-7
  - **Archivos:** `app/services/simulation_service.py`, `tests/integration/test_simulation_service.py`
  - **Hecho cuando:** `pytest tests/integration/test_simulation_service.py -k scenarios` pasa con `MockTransport`, años [2008, 2011, 2017] y −999 en la lluvia del 2018-03-04 y en la radiación del 2009-01-17, verificando:
    - 2017 queda `blocked` con `MISSING_PRECIPITATION` y la fecha;
    - 2008 queda `computed` con 1 sustitución de radiación registrada;
    - 2011 queda `computed` con 731 días;
    - el transporte se llama 1 vez;
    - la ET₀ se calcula una vez por escenario aunque haya 2 rotaciones (contador con `monkeypatch`).

- [ ] **T044 — Servicio de simulación (2/2): corridas, resultados, rangos y comparaciones**
  - **Depende de:** T043, T021, T022, T023, T024, T025
  - **RF:** RF-8, RF-9, RF-10, RF-11, RF-12 (CA-12.4), RF-15 (CA-15.4), RF-16 (CA-16.2, CA-16.3)
  - **Archivos:** `app/services/simulation_service.py`, `tests/integration/test_simulation_service.py`
  - **Hecho cuando:** `pytest tests/integration/test_simulation_service.py -k runs` pasa verificando:
    - con 2 rotaciones y 2 escenarios calculados hay 4 resultados, cada uno con |cierre| ≤ 0,01 mm;
    - los rangos usan n = 2 y listan el escenario bloqueado como excluido;
    - existe la comparación B−A de cada escenario;
    - con todos los escenarios bloqueados hay 0 resultados y ninguna excepción;
    - una falla de integridad inyectada en una corrida propaga `CalculationIntegrityError`, sin resultados parciales.

- [ ] **T045 — Constructor de la respuesta: redondeo, advertencias y procedencia**
  - **Depende de:** T042, T044, T030
  - **RF:** RF-13, RF-14, RF-15 (CA-15.1–CA-15.4), RF-17 (CA-17.2, CA-17.3, CA-17.5), RF-1 (CA-1.11)
  - **Archivos:** `app/services/response_builder.py`, `tests/unit/test_response_builder.py`
  - **Hecho cuando:** `pytest tests/unit/test_response_builder.py` pasa verificando:
    - el redondeo del plan §5.1: mm con 1 decimal, cocientes con 3, t/ha con 2 y moneda con 2;
    - un `NaN` o infinito en cualquier valor lanza `CalculationIntegrityError`;
    - las 4 advertencias fijas están siempre presentes;
    - `SUBSTITUTIONS_PRESENT` y `SCENARIOS_BLOCKED` aparecen solo cuando corresponde;
    - `OUTSIDE_SAN_LUIS` aparece para (−31,42; −64,18) y no para (−33,68; −65,47);
    - `mass_balance_error_mm` se calcula con valores sin redondear.

- [ ] **T046 — Endpoint `POST /api/v1/simulations` (caso exitoso)**
  - **Depende de:** T045, T041, T034, T039
  - **RF:** RF-1 a RF-17 (flujo completo), CA-15.1
  - **Archivos:** `app/routers/simulations.py`, `app/main.py`, `tests/api/test_simulations_endpoint.py`
  - **Hecho cuando:** `pytest tests/api/test_simulations_endpoint.py -k success` pasa verificando:
    - un POST con la solicitud del plan §5.2 y un payload simulado devuelve 200;
    - la respuesta contiene exactamente las 13 claves de primer nivel del plan §5.3;
    - la respuesta valida contra `response_model`;
    - todo `mass_balance_error_mm` cumple |valor| ≤ 0,01.

- [ ] **T047 — Pruebas de errores de punta a punta del endpoint**
  - **Depende de:** T046
  - **RF:** RF-16 (CA-16.1–CA-16.5), RF-5 (CA-5.3–CA-5.5)
  - **Archivos:** `tests/api/test_simulations_endpoint.py`
  - **Hecho cuando:** `pytest tests/api/test_simulations_endpoint.py -k error` pasa verificando:
    - una solicitud con 3 errores semánticos da 422 con 3 `details` y **0** llamadas al transporte;
    - `ConnectError` da 503;
    - `ReadTimeout` da 504 con «60 s» en el mensaje;
    - un payload sin WS2M_MAX da 502;
    - una falla de integridad forzada da 500 sin la clave `results`;
    - con todos los escenarios bloqueados da 200 con `results == []` y la advertencia `SCENARIOS_BLOCKED`.

- [ ] **T048 — Ejemplos en OpenAPI e instantánea del contrato**
  - **Depende de:** T046
  - **RF:** RF-15 (CA-15.6), RNF-13
  - **Archivos:** `app/models/request.py`, `app/models/response.py` (ejemplos), `tests/api/test_contract.py`, `tests/snapshots/openapi_v1.json`
  - **Hecho cuando:** `pytest tests/api/test_contract.py` pasa verificando:
    - `/openapi.json` incluye los ejemplos de solicitud y respuesta del plan §5.2 y §5.3 en `POST /api/v1/simulations`;
    - el esquema coincide con `tests/snapshots/openapi_v1.json`;
    - `test_snapshot_detects_removed_field`: la función de comparación informa la diferencia cuando a una copia en memoria del esquema le falta un campo.

---

## Fase 7 — Cierre

- [ ] **T049 — Pruebas no funcionales: persistencia, reproducibilidad, lenguaje y rendimiento**
  - **Depende de:** T046
  - **RF:** RNF-1, RNF-3, RNF-8, RF-5 (CA-5.2), RF-17 (CA-17.1), C5
  - **Archivos:** `tests/nonfunctional/test_no_persistence.py`, `test_reproducibility.py`, `test_language.py` (ampliado), `test_performance.py`
  - **Hecho cuando:** `pytest tests/nonfunctional` y `pytest tests/nonfunctional -m slow` terminan con código 0 y verifican:
    - **persistencia:** durante una simulación completa, una llamada a `open` en modo escritura, agregado o creación, o a `Path.write_*`, hace fallar la prueba, y el directorio temporal de trabajo sigue sin archivos nuevos;
    - **reproducibilidad:** dos POST idénticos con el mismo payload y el mismo reloj devuelven JSON idénticos salvo `request_id`;
    - **lenguaje:** ningún texto de la respuesta completa contiene los términos prohibidos de T029;
    - **rendimiento:** 3 rotaciones × 10 escenarios se procesan en ≤ 5 s, excluida la espera de red.

- [ ] **T050 — Prueba manual contra NASA POWER real**
  - **Depende de:** T046
  - **RF:** RF-5 (CA-5.1), RF-8 (CA-8.16), plan §12 (riesgos R-1 y R-5)
  - **Archivos:** `tests/live/test_power_live.py`, `specs/001-agrodss-backend/research.md` (sección «Prueba en vivo»)
  - **Hecho cuando:**
    - `pytest -m live` termina con código 0 con conexión a internet (3 rotaciones × 3 escenarios en un punto de San Luis);
    - `research.md` tiene la sección «Prueba en vivo» con fecha, coordenadas, años, código HTTP, duración total, máximo |cierre| y cantidad de días sin cultivo vivo con WS2M_MAX > 8 m/s por escenario y rotación;
    - la sección no contiene valores de las series diarias.

- [ ] **T051 — Prueba de trazabilidad de criterios de aceptación**
  - **Depende de:** T047, T048, T049, T050
  - **RF:** todos (verifica la cobertura de CA-1.1 a CA-17.5)
  - **Archivos:** `tests/nonfunctional/test_traceability.py`
  - **Hecho cuando:** `pytest tests/nonfunctional/test_traceability.py` pasa verificando:
    - extrae de `specs/001-agrodss-backend/spec.md` todos los identificadores `CA-x.y`;
    - cada uno aparece en al menos un docstring de `tests/` o en la lista `NOT_AUTOMATABLE` del propio test, con su justificación escrita;
    - `NOT_AUTOMATABLE` tiene como máximo 3 entradas (se prevé solo CA-6.9, inactivo por D-12).

- [ ] **T052 — Verificación final y preparación del PR**
  - **Depende de:** T051
  - **RF:** criterios de finalización del spec §8, checklist de AGENTS
  - **Archivos:** `specs/001-agrodss-backend/spec.md` (§8 marcado), descripción del PR
  - **Hecho cuando:** desde `backend/`:
    - `pytest` y `pytest -m slow` terminan con código 0;
    - `ruff check .` y `ruff format --check .` terminan con código 0;
    - `uvicorn app.main:app` arranca y `GET /api/v1/health` responde 200;
    - todas las casillas del spec §8 están marcadas, cada una con el nombre de la prueba que la cubre;
    - la descripción del PR incluye: la aprobación de httpx del 2026-11-15, el commit de la enmienda del principio 5 de la constitución, la lista de supuestos del plan §11, la salida resumida de `pytest` y el resultado de T050.
