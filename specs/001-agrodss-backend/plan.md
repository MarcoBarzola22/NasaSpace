# Plan técnico 001 — Backend MVP de AgroDSS

| Campo | Valor |
|---|---|
| Especificación | [spec.md](spec.md) (revisión 3) |
| Estado | Aprobado por el equipo el 2026-11-15: todas las decisiones de diseño, los supuestos de §11 y la dependencia httpx |
| Fecha | 2026-11-15 |
| Base | Constitución (principio 5 enmendado: consulta en vivo, sin base de datos ni caché), AGENTS, spec rev. 3 y fundamentos del documento de investigación (leído por orden humana explícita) |
| Alcance | Cómo se construye el backend: módulos, contrato JSON, algoritmo, decisiones y pruebas. Este documento no contiene código. |

**Convención de trazabilidad:** cada sección indica entre corchetes los requisitos que cubre, por ejemplo **[RF-8]**. La §10 reúne la matriz completa RF → módulos → pruebas.

---

## 0. Resumen

El backend es un servicio FastAPI **sin estado**. Un único endpoint `POST /api/v1/simulations` recibe la parcela, de 1 a 3 rotaciones y de 1 a 10 años de inicio, y procesa la solicitud en este orden:

1. valida todo **antes** de contactar a la NASA;
2. hace **una sola consulta en vivo** a la API diaria de NASA POWER;
3. calcula, con funciones puras, la ET₀ (FAO-56), el balance diario continuo sobre un perfil fijo de dos compartimentos, FAO-33, el margen bruto, el proxy de viento (WS2M_MAX > 8 m/s) y los rangos;
4. devuelve un JSON autosuficiente para el frontend, con procedencia, supuestos y advertencias.

No se escribe nada en disco ni se conserva nada entre solicitudes.

---

## 1. Verificación de la constitución y de AGENTS (puerta de entrada)

| Principio | Cómo lo cumple el plan | Estado |
|---|---|---|
| **C1 Stack simple** | FastAPI + Uvicorn. Única dependencia de ejecución adicional: **httpx**, que FastAPI ya exige para su `TestClient` y que aquí se usa también como cliente de NASA POWER. pytest y ruff ya figuran en AGENTS. Sin base de datos ni servicios externos fuera de NASA POWER. | ✅ httpx aprobada por el equipo el 2026-11-15; dejar constancia en el PR (§4) |
| **C2 Datos NASA + FAO, sin inventar** | Solo NASA POWER (7 variables, §6.3). Solo FAO-56, FAO-33 y margen bruto. El catálogo cita tabla y fuente de cada valor. Las sustituciones FAO-56 son visibles y no hay interpolación (§7.3). | ✅ |
| **C3 Lógica separada** | Todo cálculo vive en `backend/app/domain`. La respuesta incluye totales, cocientes, rangos y diferencias ya calculados (§5.3). | ✅ |
| **C4 Tests obligatorios** | §9: conservación de masa, unidades, límites y cronología para cada fórmula; invariantes con series sintéticas. | ✅ |
| **C5 Persistencia mínima (enmendado)** | Consulta en vivo por solicitud, sin base de datos, sin caché y sin escritura de series; hay una prueba que lo verifica (§9.6). El catálogo FAO es un archivo estático de referencia versionado con el código, no una serie NASA. La enmienda de la constitución aún no está commiteada. | ✅ (commitear la enmienda) |
| **C6 Política de tokens** | La documentación extensa se leyó por orden explícita. El plan se apoya en el spec y en la constitución. | ✅ |
| **AGENTS 2 (modelos aprobados)** | Sin AquaCrop, APSIM, DSSAT, RUSLE/RWEQ, Monte Carlo ni ML. El suelo se evalúa solo con el proxy de viento y días sin cultivo vivo. | ✅ |
| **AGENTS 3–5 (faltantes, calibración, procedencia)** | §7.3, §5.3 (`assumptions`, `warnings`, `provenance`). | ✅ |
| **AGENTS 7 (alcance mínimo)** | Sin dependencias extra para pruebas: se usan `httpx.MockTransport` y el módulo `random` con semilla, en lugar de respx, hypothesis o vcrpy. | ✅ |

**Fundamentos del documento de investigación que el plan convierte en reglas verificables:**

| Fundamento | Sección del documento | Regla en el plan |
|---|---|---|
| Separar el dato de celda de la medición de lote | §2, §3.1 | Rótulo de celda en la procedencia y en las advertencias |
| Controles imprescindibles del balance (masa, unidades, ETa ≤ disponible, almacenamiento en límites, cronología continua) | §6.1 | Controles diarios y de cierre (§7.4) y pruebas de invariantes (§9.3) |
| FAO-33 no valida predicciones | §6.2 | Advertencia «no calibrado» y sin métricas de precisión |
| Proxy de suelo sin toneladas de erosión | §6.5 | RF-11, sin conversión a erosión |
| Margen bruto ≠ resultado neto | §8 | Rótulo «margen bruto negativo» |
| Frecuencia histórica ≠ probabilidad | §9.1 | Rangos rotulados como descriptivos; prueba de lenguaje |

---

## 2. Decisiones adoptadas para las dudas abiertas del spec [§9.1 del spec]

El plan adopta las propuestas por defecto del spec. El equipo puede cambiarlas antes de implementar.

| Duda | Decisión del plan |
|---|---|
| D-1 | Catálogo: `maize` (maíz), `soybean_first` (soja de primera), `soybean_second` (soja de segunda), `wheat` (trigo) y `rye_cover` (centeno de cobertura). |
| D-6 | `window.start_day` y `window.start_month` son opcionales; si se omiten, se usa el 1 de julio y se registra el supuesto `WINDOW_START_DEFAULT`. |
| D-7 | Entrada del ciclo: fecha de siembra + 4 duraciones. La siembra es el día 1 del ciclo; fin = siembra + (L − 1) días. Para el centeno, el usuario acorta la etapa final. |
| D-8 | De 1 a 3 rotaciones, con identificadores únicos entre A, B y C. |
| D-9 | Se aceptan coordenadas fuera de San Luis con la advertencia `OUTSIDE_SAN_LUIS`, calculada con una caja aproximada (latitud −36,0 a −31,8; longitud −67,6 a −64,8; a verificar). |
| D-11 | Humedad: **T2MDEW** (punto de rocío, el método preferido por FAO-56, ecuación 14). Verificación previa V-1 (§12). |
| D-12 | Sin límite de días sustituidos. Si hubo alguno, se emite la advertencia `SUBSTITUTIONS_PRESENT` con el conteo. |
| D-13 | Sin ajuste climático de Kc medio ni de Kc final; se registra el supuesto `NO_KC_CLIMATE_ADJUSTMENT`. |
| D-14 | `rye_cover` no trae referencias FAO salvo que V-2 las encuentre: Kc, etapas, Zr y p son obligatorios del usuario. |
| D-15 | `currency` con 3 letras, sin conversión. La terminación del centeno se incluye en sus costos directos. El backend calcula **diferencias de margen entre pares de rotaciones** por escenario, sin orden de conveniencia. |
| D-16 | Suelo solo con θCC y θPMP (m³/m³). La entrada como agua útil (mm/m) queda diferida. |
| Zr inicial (decisión T-26) | **La profundidad radicular inicial de referencia es 0,25 m para los cinco cultivos del catálogo.** Es una decisión técnica del equipo AgroDSS (aprobada por Mauro el 2026-11-15; rango considerado 0,2–0,3 m, punto medio), no un valor de FAO-56: la Tabla 22 de FAO-56 no contiene guía sobre Zr inicial. El usuario puede sobrescribirla por cultivo. Al ser mayor que la capa de evaporación del barbecho (0,15 m), el límite entre zonas del balance se mueve el día de la siembra; la redistribución (§7.4) conserva la masa. En el catálogo figura con `origin: team_default`. |

---

## 3. Estructura de módulos y carpetas

```
backend/
├── requirements.txt              # fastapi, uvicorn, httpx, pytest, ruff (versiones exactas)
├── pyproject.toml                # configuración de ruff y pytest (marcadores live/slow)
├── app/
│   ├── main.py                   # crea la app, registra routers, CORS y manejadores de error
│   ├── routers/                  # capa HTTP: solo traduce HTTP ⇄ servicios
│   │   ├── health.py             # GET  /api/v1/health
│   │   ├── catalog.py            # GET  /api/v1/catalog
│   │   └── simulations.py        # POST /api/v1/simulations
│   ├── core/                     # transversal, sin lógica agronómica
│   │   ├── config.py             # ajustes desde variables de entorno (URL de POWER, timeouts, CORS, límites)
│   │   ├── constants.py          # constantes físicas y de modelo (umbral de viento, Kc de barbecho, Ze, tolerancias)
│   │   ├── exceptions.py         # errores de dominio: entrada, NASA POWER, integridad
│   │   ├── error_handlers.py     # excepciones → ErrorResponse con código HTTP
│   │   ├── messages.py           # todos los textos visibles en español (errores, supuestos, advertencias)
│   │   └── dependencies.py       # inyección del cliente POWER y del reloj (reemplazables en tests)
│   ├── models/                   # contrato Pydantic (entrada y salida de la API)
│   │   ├── common.py             # tipos reutilizables (ParameterValue, Range, Scope)
│   │   ├── request.py            # SimulationRequest, ParcelInput, RotationInput, CropInput…
│   │   ├── response.py           # SimulationResponse, ScenarioOutcome, RunResult…
│   │   ├── catalog.py            # CatalogResponse
│   │   └── errors.py             # ErrorResponse
│   ├── services/                 # orquestación y E/S
│   │   ├── power_client.py       # consulta HTTP a NASA POWER (una por solicitud)
│   │   ├── climate_parser.py     # JSON de POWER → serie diaria tipada + procedencia
│   │   ├── validation.py         # validación semántica completa, previa a la consulta
│   │   ├── parameter_resolver.py # aplica referencias FAO, límites de Zr y orígenes
│   │   ├── simulation_service.py # flujo principal (§7.1)
│   │   ├── assumptions.py        # registro y agregación de supuestos
│   │   ├── catalog_service.py    # carga y valida el catálogo al arrancar
│   │   └── response_builder.py   # dominio → modelos de respuesta, redondeo y advertencias
│   ├── domain/                   # funciones puras: solo biblioteca estándar
│   │   ├── types.py              # dataclasses inmutables del dominio
│   │   ├── calendar.py           # ventanas, fechas de siembra, línea de tiempo
│   │   ├── et0.py                # FAO-56 Penman–Monteith y Hargreaves (radiación)
│   │   ├── missing_data.py       # clasificación de faltantes y cobertura
│   │   ├── kc_curve.py           # curva de Kc por etapas
│   │   ├── root_growth.py        # Zr diaria
│   │   ├── water_balance.py      # loop diario continuo (§7.4)
│   │   ├── yield_response.py     # FAO-33
│   │   ├── economics.py          # ingreso y margen bruto
│   │   ├── wind_proxy.py         # días sin cultivo vivo con WS2M_MAX > 8 m/s
│   │   └── stats.py              # mínimo, mediana y máximo
│   └── data/
│       └── crop_catalog.json     # valores de referencia FAO con citas (estático, versionado)
└── tests/                        # ver §9.1
```

**Regla de dependencias** (la verifica una prueba que analiza los `import`):
- `routers` → `services` → `domain`.
- `domain` importa solo la biblioteca estándar, `domain.types` y `core.constants`. Nunca FastAPI, Pydantic ni httpx.
- `models` solo lo usan `routers` y `services`.

| Módulo | Responsabilidad | RF |
|---|---|---|
| `routers/catalog.py`, `services/catalog_service.py`, `data/crop_catalog.json` | Exponer el catálogo con citas | RF-2 |
| `routers/simulations.py`, `services/simulation_service.py` | Flujo completo de cálculo | RF-1…RF-17 |
| `models/request.py`, `services/validation.py` | Validación estructural y semántica | RF-1, RF-3, RF-4, RF-10, RF-16 |
| `services/parameter_resolver.py` | Valores efectivos y su origen | RF-1, RF-3, RF-14 |
| `services/power_client.py`, `services/climate_parser.py` | Consulta en vivo, parseo y procedencia | RF-5, RF-13 |
| `domain/calendar.py` | Ventanas y línea de tiempo | RF-3, RF-4 |
| `domain/missing_data.py`, `domain/et0.py` | Faltantes, sustituciones y ET₀ | RF-6, RF-7 |
| `domain/kc_curve.py`, `domain/root_growth.py`, `domain/water_balance.py` | Balance diario | RF-8 |
| `domain/yield_response.py` | FAO-33 | RF-9 |
| `domain/economics.py` | Ingreso y margen | RF-10 |
| `domain/wind_proxy.py` | Proxy de suelo | RF-11 |
| `domain/stats.py` | Rangos | RF-12 |
| `services/assumptions.py`, `core/messages.py` | Supuestos, advertencias y lenguaje | RF-14, RF-17 |
| `models/response.py`, `services/response_builder.py` | Contrato de salida | RF-15 |
| `core/exceptions.py`, `core/error_handlers.py`, `models/errors.py` | Errores | RF-16 |

---

## 4. Dependencias

| Paquete | Uso | Situación frente a C1 |
|---|---|---|
| fastapi (incluye pydantic v2 y starlette) | Framework, validación y OpenAPI | Stack constitucional |
| uvicorn | Servidor ASGI | Ya figura en los comandos de AGENTS |
| httpx | Cliente de NASA POWER; también lo requiere el `TestClient` de FastAPI | **Aprobada por el equipo el 2026-11-15**; dejar constancia en el PR |
| pytest | Pruebas | Ya figura en AGENTS |
| ruff | Linter y formato | Ya figura en AGENTS |

Python 3.11 o superior. Las versiones exactas se fijan en `requirements.txt` al implementar. Se usa un único archivo de requisitos, coherente con `pip install -r requirements.txt` de AGENTS.

---

## 5. Modelo de datos JSON

### 5.1 Convenciones [RF-15, RNF-5, RNF-6]

- **Claves en inglés y `snake_case`, con la unidad en el nombre**, por ejemplo `et0_mm`, `yield_t_ha`, `threshold_ms` o `gross_margin_per_ha`. Los campos monetarios usan la moneda declarada en `currency`.
- **Textos visibles en español**: `message`, `description`, `label` y `note`.
- **Parámetros resueltos** como objeto `{ "value", "origin", "source", "note" }`. `origin` toma uno de estos valores: `user`, `fao_reference`, `team_default`, `system_default`.
- **`null` explícito** cuando algo no aplica (por ejemplo, el rendimiento de un cultivo de cobertura), acompañado de una nota en español.
- **Redondeo solo al serializar:** mm con 1 decimal, cocientes con 3, t/ha con 2 y moneda con 2. Los controles se calculan sin redondear; por eso, sumar los valores redondeados puede diferir en ±0,1 mm.
- **Fechas** en formato ISO `YYYY-MM-DD`. **Instantes** en ISO UTC.
- La respuesta nunca contiene `NaN` ni infinitos; si aparecieran, se trata como error de integridad.

### 5.2 Solicitud `POST /api/v1/simulations` [RF-1, RF-3, RF-4, RF-10]

| Campo | Tipo | Unidad | Obligatorio | Por defecto | Validación | RF / CA |
|---|---|---|---|---|---|---|
| `parcel.name` | texto ≤ 100 | — | no | `null` | — | RF-1 |
| `parcel.latitude_deg` | número | grados | sí | — | [−90, 90] (estructural); [−60, 60] (semántica, T036) | CA-1.2, CA-1.12 |
| `parcel.longitude_deg` | número | grados | sí | — | [−180, 180] | CA-1.2 |
| `parcel.theta_fc_m3_m3` | número | m³/m³ | sí | — | (0, 1] y > θPMP | CA-1.3 |
| `parcel.theta_wp_m3_m3` | número | m³/m³ | sí | — | [0, 1) y < θCC | CA-1.3 |
| `parcel.effective_depth_m` | número | m | sí | — | (0, 3,0] | CA-1.4 |
| `parcel.initial_available_water_pct` | número | % del agua útil | sí | — | [0, 100] | CA-1.5 |
| `parcel.fallow_kc_base` | número | — | no | 0,20 | (0, 1,0] | CA-1.9, CA-1.10 |
| `window.start_day`, `window.start_month` | entero | — | no | 1 y 7 | fecha válida, distinta del 29 de febrero | CA-4.3, D-6 |
| `window.start_years` | lista de enteros | año | sí | — | 1 a 10, distintos; cada ventana termina antes de hoy (UTC) | CA-4.1–CA-4.4 |
| `currency` | texto | — | sí, si hay datos económicos | — | 3 letras mayúsculas | CA-10.6 |
| `rotations` | lista | — | sí | — | 1 a 3; `id` único entre A, B y C | CA-3.1 |
| `rotations[].name` | texto | — | no | `null` | ≤ 100 | RF-3 |
| `rotations[].initial_residue_cover_pct` | número | % | no | 0 | [0, 100] | CA-3.12 |
| `rotations[].crops` | lista | — | sí | — | ≥ 1, en orden de siembra | CA-3.1 |
| `crops[].crop_code` | enumerado | — | sí | — | existe en el catálogo | CA-3.2 |
| `crops[].sowing.window_year` / `.day` / `.month` | entero | — | sí | — | año 1 o 2; fecha válida, distinta del 29 de febrero | CA-3.8 |
| `crops[].stage_lengths_days.{initial, development, mid, late}` | entero | días | no* | catálogo | **las cuatro o ninguna**; cada una en [1, 365] | CA-3.3, CA-3.9 |
| `crops[].kc_initial`, `kc_mid`, `kc_end` | número | — | no* | catálogo | [0, 2,0] | CA-3.3, CA-3.9 |
| `crops[].root_depth_initial_m` | número | m | no* | catálogo | > 0 y ≤ Zr máxima | CA-3.9 |
| `crops[].root_depth_max_m` | número | m | no* | catálogo | > 0; se limita a la profundidad efectiva | CA-3.10 |
| `crops[].depletion_fraction_p` | número | — | no* | catálogo | (0, 1) | CA-3.9 |
| `crops[].ky` | número | — | no* (solo grano) | catálogo | [0, 2,0]; prohibido en cobertura | CA-3.13 |
| `crops[].ym_t_ha` | número | t/ha | sí en grano | — | (0, 30]; prohibido en cobertura | CA-3.2, CA-3.13 |
| `crops[].residue_cover_after_pct` | número | % | no | 0 | [0, 100] | CA-3.12 |
| `crops[].economics.price_per_t` | número | moneda/t | no | — | ≥ 0; prohibido en cobertura | CA-10.5 |
| `crops[].economics.direct_costs_per_ha` | número | moneda/ha | no | — | ≥ 0 | CA-10.5 |

\* Obligatorio cuando el catálogo marca el parámetro como «sin referencia» (D-14).

Todo campo desconocido produce un error 422. Un campo de riego (cualquier clave que contenga `irrig` o `riego`) produce el mensaje específico de CA-1.8.

**Ejemplo de solicitud.** Los valores numéricos solo ilustran el formato: no son valores validados ni recomendados. La rotación B omite parámetros a propósito, para mostrar el uso de las referencias del catálogo. La rotación C se omite porque se aceptan de 1 a 3 rotaciones.

```json
{
  "parcel": {
    "name": "Lote 7 — Villa Mercedes",
    "latitude_deg": -33.68,
    "longitude_deg": -65.47,
    "theta_fc_m3_m3": 0.28,
    "theta_wp_m3_m3": 0.12,
    "effective_depth_m": 1.2,
    "initial_available_water_pct": 50,
    "fallow_kc_base": null
  },
  "window": {
    "start_day": 1,
    "start_month": 7,
    "start_years": [2008, 2011, 2017]
  },
  "currency": "USD",
  "rotations": [
    {
      "id": "A",
      "name": "Maíz → centeno de cobertura → soja",
      "initial_residue_cover_pct": 30,
      "crops": [
        {
          "crop_code": "maize",
          "sowing": { "window_year": 1, "day": 15, "month": 10 },
          "stage_lengths_days": { "initial": 30, "development": 40, "mid": 50, "late": 30 },
          "kc_initial": 0.30,
          "kc_mid": 1.20,
          "kc_end": 0.35,
          "root_depth_initial_m": 0.15,
          "root_depth_max_m": 1.5,
          "depletion_fraction_p": null,
          "ky": null,
          "ym_t_ha": 9.0,
          "residue_cover_after_pct": 60,
          "economics": { "price_per_t": 180, "direct_costs_per_ha": 620 }
        },
        {
          "crop_code": "rye_cover",
          "sowing": { "window_year": 1, "day": 1, "month": 4 },
          "stage_lengths_days": { "initial": 20, "development": 40, "mid": 40, "late": 20 },
          "kc_initial": 0.30,
          "kc_mid": 1.00,
          "kc_end": 0.80,
          "root_depth_initial_m": 0.15,
          "root_depth_max_m": 0.8,
          "depletion_fraction_p": 0.55,
          "residue_cover_after_pct": 80,
          "economics": { "direct_costs_per_ha": 95 }
        },
        {
          "crop_code": "soybean_first",
          "sowing": { "window_year": 2, "day": 15, "month": 11 },
          "stage_lengths_days": { "initial": 20, "development": 30, "mid": 60, "late": 25 },
          "root_depth_initial_m": 0.15,
          "ym_t_ha": 3.2,
          "residue_cover_after_pct": 30,
          "economics": { "price_per_t": 300, "direct_costs_per_ha": 380 }
        }
      ]
    },
    {
      "id": "B",
      "name": "Maíz → trigo → soja de segunda",
      "crops": [
        {
          "crop_code": "maize",
          "sowing": { "window_year": 1, "day": 15, "month": 10 },
          "stage_lengths_days": { "initial": 30, "development": 40, "mid": 50, "late": 30 },
          "ym_t_ha": 9.0,
          "residue_cover_after_pct": 60,
          "economics": { "price_per_t": 180, "direct_costs_per_ha": 620 }
        },
        {
          "crop_code": "wheat",
          "sowing": { "window_year": 1, "day": 1, "month": 6 },
          "stage_lengths_days": { "initial": 25, "development": 55, "mid": 70, "late": 35 },
          "ym_t_ha": 3.5,
          "economics": { "price_per_t": 200, "direct_costs_per_ha": 420 }
        },
        {
          "crop_code": "soybean_second",
          "sowing": { "window_year": 2, "day": 3, "month": 12 },
          "stage_lengths_days": { "initial": 15, "development": 25, "mid": 50, "late": 20 },
          "ym_t_ha": 2.0,
          "economics": { "price_per_t": 300, "direct_costs_per_ha": 300 }
        }
      ]
    }
  ]
}
```

Calendario que resulta para el año de inicio 2008 en la rotación A:
- maíz: del 15-10-2008 al 13-03-2009 (150 días);
- barbecho;
- centeno: del 01-04-2009 al 29-07-2009 (120 días);
- barbecho;
- soja: del 15-11-2009 al 29-03-2010 (135 días);
- barbecho hasta el 30-06-2010.

En B, el trigo termina el 02-12-2009 y la soja de segunda se siembra el 03-12-2009, sin barbecho intermedio (CL-17).

### 5.3 Respuesta `200 OK` [RF-9…RF-15, RF-17]

| Bloque | Contenido | RF / CA |
|---|---|---|
| `contract_version`, `model_version`, `request_id`, `computed_at`, `currency` | Identificación y reproducibilidad | CA-13.3, CA-15.6, RNF-1 |
| `resolved_input` | Valor efectivo y origen de cada parámetro; capacidad del perfil; almacenamiento inicial | CA-15.1a, CA-1.6, CA-3.3, CA-3.4 |
| `provenance` | Fuente, consulta, versión, ubicación, elevación, variables, faltantes y rótulo de celda | RF-13 |
| `scenarios[]` | Ventana, días, estado, motivos de bloqueo, sustituciones, ET₀ y lluvia totales | CA-15.1c, CA-6.7 |
| `results[]` | Por rotación y escenario: `water_balance`, `crops[]`, `rotation_economics` y `soil_exposure` | CA-15.1d, CA-15.2, RF-9, RF-10, RF-11 |
| `ranges[]` | Por rotación: mínimo, mediana y máximo con n | RF-12 |
| `comparisons[]` | Diferencias de margen bruto entre pares de rotaciones por escenario | CA-15.4, D-15 |
| `assumptions[]` | Supuestos estructurados y agregados | RF-14 |
| `warnings[]` | Advertencias fijas y condicionales | RF-17, CA-1.11 |

**Ejemplo de respuesta** (recortado: solo la rotación A, el primer cultivo en `resolved_input` y un rango). Los números ilustran el formato y respetan el cierre de masa; no son resultados reales.

```json
{
  "contract_version": "1.0",
  "model_version": "0.1.0",
  "request_id": "3f2b8c1e-7d4a-4f6b-9a2e-5c8d1b0e7f43",
  "computed_at": "2026-11-15T14:03:22Z",
  "currency": "USD",
  "resolved_input": {
    "parcel": {
      "latitude_deg": -33.68,
      "longitude_deg": -65.47,
      "theta_fc_m3_m3": 0.28,
      "theta_wp_m3_m3": 0.12,
      "effective_depth_m": 1.2,
      "profile_capacity_mm": 192.0,
      "initial_available_water_pct": 50,
      "initial_storage_mm": 96.0,
      "fallow_kc_base": { "value": 0.20, "origin": "team_default", "source": "Decisión del equipo AgroDSS (rango 0,15–0,20); no es un valor tabulado único de FAO-56", "note": null },
      "fallow_evaporation_layer_m": { "value": 0.15, "origin": "system_default", "source": "FAO-56, cap. 7 (capa evaporable Ze 0,10–0,15 m)", "note": null }
    },
    "window": { "start_day": 1, "start_month": 7, "start_years": [2008, 2011, 2017] },
    "rotations": [
      {
        "id": "A",
        "name": "Maíz → centeno de cobertura → soja",
        "initial_residue_cover_pct": { "value": 30, "origin": "user", "source": null, "note": null },
        "crops": [
          {
            "position": 1,
            "crop_code": "maize",
            "crop_name": "Maíz",
            "crop_type": "grain",
            "calibrated": false,
            "parameters": {
              "kc_initial": { "value": 0.30, "origin": "user", "source": null, "note": null },
              "kc_mid": { "value": 1.20, "origin": "user", "source": null, "note": null },
              "kc_end": { "value": 0.35, "origin": "user", "source": null, "note": null },
              "stage_lengths_days": { "value": { "initial": 30, "development": 40, "mid": 50, "late": 30 }, "origin": "user", "source": null, "note": null },
              "root_depth_initial_m": { "value": 0.15, "origin": "user", "source": null, "note": null },
              "root_depth_max_m": { "value": 1.2, "origin": "user", "source": null, "note": "Limitada a la profundidad efectiva (valor ingresado: 1,5 m)." },
              "depletion_fraction_p": { "value": 0.55, "origin": "fao_reference", "source": "FAO-56, Tabla 22", "note": "Valor tabulado FAO, no calibrado para el lote." },
              "ky": { "value": 1.25, "origin": "fao_reference", "source": "FAO-33 (Ky del ciclo completo)", "note": "Valor tabulado FAO, no calibrado para el lote." },
              "ym_t_ha": { "value": 9.0, "origin": "user", "source": null, "note": null },
              "residue_cover_after_pct": { "value": 60, "origin": "user", "source": null, "note": null }
            }
          }
        ]
      }
    ]
  },
  "provenance": {
    "source": "NASA POWER",
    "service": "API diaria de punto, comunidad AG",
    "retrieval": "Consulta en vivo",
    "queried_at": "2026-11-15T14:03:19Z",
    "source_version": "v2.x.x",
    "requested_location": { "latitude_deg": -33.68, "longitude_deg": -65.47 },
    "source_location": { "latitude_deg": -33.68, "longitude_deg": -65.47, "elevation_m": 512.4 },
    "spatial_note": "El dato representa una celda de varios kilómetros (resolución nativa según la documentación de POWER), no el lote.",
    "date_range": { "start": "2008-07-01", "end": "2019-06-30" },
    "variables": [
      { "code": "PRECTOTCORR", "name": "Precipitación corregida", "unit": "mm/día", "use": "Balance hídrico", "missing_days": 1 },
      { "code": "T2M_MAX", "name": "Temperatura máxima a 2 m", "unit": "°C", "use": "ET₀", "missing_days": 0 },
      { "code": "T2M_MIN", "name": "Temperatura mínima a 2 m", "unit": "°C", "use": "ET₀", "missing_days": 0 },
      { "code": "T2MDEW", "name": "Punto de rocío a 2 m", "unit": "°C", "use": "ET₀", "missing_days": 0 },
      { "code": "WS2M", "name": "Velocidad media diaria del viento a 2 m", "unit": "m/s", "use": "ET₀", "missing_days": 0 },
      { "code": "WS2M_MAX", "name": "Velocidad máxima diaria del viento a 2 m", "unit": "m/s", "use": "Proxy de viento fuerte", "missing_days": 0 },
      { "code": "ALLSKY_SFC_SW_DWN", "name": "Radiación solar global en superficie", "unit": "MJ/m²/día", "use": "ET₀", "missing_days": 2 }
    ],
    "label": "Dato de modelo/reanálisis de NASA POWER a escala de celda; no es una medición del lote."
  },
  "scenarios": [
    {
      "start_year": 2008,
      "window_start": "2008-07-01",
      "window_end": "2010-06-30",
      "days": 730,
      "status": "computed",
      "blocked_reasons": [],
      "substituted_days": [
        { "variable": "ALLSKY_SFC_SW_DWN", "method": "Hargreaves (FAO-56, ec. 50), kRs = 0,16", "count": 2, "dates": ["2009-01-17", "2009-01-18"] }
      ],
      "precipitation_total_mm": 1185.4,
      "et0_total_mm": 2650.2
    },
    {
      "start_year": 2011,
      "window_start": "2011-07-01",
      "window_end": "2013-06-30",
      "days": 731,
      "status": "computed",
      "blocked_reasons": [],
      "substituted_days": [],
      "precipitation_total_mm": 1402.7,
      "et0_total_mm": 2588.9
    },
    {
      "start_year": 2017,
      "window_start": "2017-07-01",
      "window_end": "2019-06-30",
      "days": 730,
      "status": "blocked",
      "blocked_reasons": [
        { "code": "MISSING_PRECIPITATION", "variable": "PRECTOTCORR", "dates": ["2018-03-04"], "message": "Falta la precipitación de NASA POWER en 1 día (2018-03-04). La lluvia no se sustituye: el escenario no se calcula." }
      ],
      "substituted_days": [],
      "precipitation_total_mm": null,
      "et0_total_mm": null
    }
  ],
  "results": [
    {
      "rotation_id": "A",
      "start_year": 2008,
      "water_balance": {
        "initial_storage_mm": 96.0,
        "final_storage_mm": 75.4,
        "precipitation_mm": 1185.4,
        "et0_mm": 2650.2,
        "crop_eta_mm": 790.6,
        "fallow_evaporation_mm": 255.3,
        "excess_lost_mm": 160.1,
        "mass_balance_error_mm": 0.0
      },
      "crops": [
        {
          "position": 1,
          "crop_code": "maize",
          "crop_type": "grain",
          "sowing_date": "2008-10-15",
          "cycle_end_date": "2009-03-13",
          "storage_at_sowing_mm": 88.4,
          "storage_at_end_mm": 31.2,
          "etm_mm": 642.5,
          "eta_mm": 418.9,
          "eta_etm_ratio": 0.652,
          "stress_days": 71,
          "yield_t_ha": 5.08,
          "relative_yield": 0.565,
          "yield_note": null,
          "economics": { "income_per_ha": 915.26, "direct_costs_per_ha": 620.0, "gross_margin_per_ha": 295.26, "gross_margin_label": null }
        },
        {
          "position": 2,
          "crop_code": "rye_cover",
          "crop_type": "cover",
          "sowing_date": "2009-04-01",
          "cycle_end_date": "2009-07-29",
          "storage_at_sowing_mm": 70.5,
          "storage_at_end_mm": 41.0,
          "etm_mm": 160.2,
          "eta_mm": 121.7,
          "eta_etm_ratio": 0.760,
          "stress_days": 18,
          "yield_t_ha": null,
          "relative_yield": null,
          "yield_note": "No aplica (cultivo de cobertura).",
          "economics": { "income_per_ha": 0.0, "direct_costs_per_ha": 95.0, "gross_margin_per_ha": -95.0, "gross_margin_label": "Margen bruto negativo" }
        },
        {
          "position": 3,
          "crop_code": "soybean_first",
          "crop_type": "grain",
          "sowing_date": "2009-11-15",
          "cycle_end_date": "2010-03-29",
          "storage_at_sowing_mm": 95.6,
          "storage_at_end_mm": 52.3,
          "etm_mm": 571.0,
          "eta_mm": 250.0,
          "eta_etm_ratio": 0.438,
          "stress_days": 64,
          "yield_t_ha": 1.67,
          "relative_yield": 0.522,
          "yield_note": null,
          "economics": { "income_per_ha": 501.24, "direct_costs_per_ha": 380.0, "gross_margin_per_ha": 121.24, "gross_margin_label": null }
        }
      ],
      "rotation_economics": {
        "status": "computed",
        "income_per_ha": 1416.50,
        "direct_costs_per_ha": 1095.0,
        "gross_margin_per_ha": 321.50,
        "gross_margin_label": null,
        "crops_missing_economics": []
      },
      "soil_exposure": {
        "window_days": 730,
        "live_crop_days": 405,
        "no_live_crop_days": 325,
        "strong_wind_days_without_live_crop": 9,
        "no_wind_data_days_without_live_crop": 0,
        "wind_variable": "WS2M_MAX",
        "threshold_ms": 8.0,
        "rule": "Velocidad máxima diaria del viento a 2 m estrictamente mayor que 8,0 m/s, solo en días sin cultivo vivo.",
        "threshold_source": "Decisión del equipo AgroDSS (revisión 3); no calibrado para erosión local.",
        "note": "«Días sin cultivo vivo» no equivale a suelo desnudo."
      }
    }
  ],
  "ranges": [
    {
      "rotation_id": "A",
      "n_scenarios": 2,
      "scenarios_included": [2008, 2011],
      "scenarios_excluded": [2017],
      "crops": [
        {
          "position": 1,
          "crop_code": "maize",
          "yield_t_ha": { "min": 5.08, "median": 6.31, "max": 7.54 },
          "eta_etm_ratio": { "min": 0.652, "median": 0.761, "max": 0.870 }
        }
      ],
      "gross_margin_per_ha": { "min": 321.50, "median": 465.80, "max": 610.10 },
      "strong_wind_days_without_live_crop": { "min": 4, "median": 6.5, "max": 9 },
      "label": "Rango descriptivo de los años elegidos; no es una probabilidad ni un pronóstico."
    }
  ],
  "comparisons": [
    {
      "start_year": 2008,
      "minuend_rotation_id": "B",
      "subtrahend_rotation_id": "A",
      "gross_margin_difference_per_ha": 142.30,
      "label": "Diferencia descriptiva de margen bruto (B − A); no indica qué rotación conviene."
    }
  ],
  "assumptions": [
    { "code": "RAINFED_NO_IRRIGATION", "scope": { "level": "request" }, "description": "Secano: riego = 0 todos los días.", "value": 0, "unit": "mm/día", "origin": "system_default", "source": null, "count": null, "dates": null },
    { "code": "FAO_REFERENCE_VALUE", "scope": { "level": "crop", "rotation_id": "A", "position": 1, "parameter": "ky" }, "description": "Valor tabulado FAO, no calibrado para el lote.", "value": 1.25, "unit": "adimensional", "origin": "fao_reference", "source": "FAO-33", "count": null, "dates": null },
    { "code": "ROOT_DEPTH_LIMITED", "scope": { "level": "crop", "rotation_id": "A", "position": 1, "parameter": "root_depth_max_m" }, "description": "La profundidad radicular máxima se limitó a la profundidad efectiva del perfil.", "value": 1.2, "unit": "m", "origin": "system_default", "source": null, "count": null, "dates": null },
    { "code": "SUBST_RADIATION_HARGREAVES", "scope": { "level": "scenario", "start_year": 2008 }, "description": "Radiación solar faltante estimada con Hargreaves (FAO-56, ec. 50), kRs = 0,16; usada solo para la ET₀.", "value": null, "unit": null, "origin": "system_default", "source": "FAO-56, cap. 3", "count": 2, "dates": ["2009-01-17", "2009-01-18"] },
    { "code": "NO_RESIDUE_DECLARED", "scope": { "level": "fallow", "rotation_id": "B", "after_position": 3 }, "description": "Sin rastrojo declarado: suelo desnudo, sin reducción de la evaporación.", "value": 0, "unit": "%", "origin": "system_default", "source": null, "count": null, "dates": null }
  ],
  "warnings": [
    { "code": "HISTORICAL_DESCRIPTIVE", "message": "Escenarios históricos descriptivos: muestran cómo se habría comportado cada rotación con el clima de los años elegidos; no son pronósticos." },
    { "code": "UNCALIBRATED_PARAMETERS", "message": "Kc, Ky, Ym y los parámetros de suelo son entradas o referencias no calibradas para el lote." },
    { "code": "CELL_SCALE_DATA", "message": "Los datos climáticos de NASA POWER representan una celda, no el lote." },
    { "code": "NOT_A_RECOMMENDATION", "message": "AgroDSS compara rotaciones para apoyar la decisión del agrónomo; no recomienda ninguna." },
    { "code": "SUBSTITUTIONS_PRESENT", "message": "Se estimaron datos faltantes con métodos FAO-56 en 2 días del escenario 2008; ver supuestos." },
    { "code": "SCENARIOS_BLOCKED", "message": "1 escenario no se calculó (2017); ver motivos." }
  ]
}
```

### 5.4 Catálogo `GET /api/v1/catalog` [RF-2, CA-2.6, CA-11.5]

Los valores deben cargarse y verificarse contra las tablas citadas en la tarea V-2 (§12). Los de este ejemplo son orientativos.

```json
{
  "contract_version": "1.0",
  "crops": [
    {
      "crop_code": "maize",
      "name": "Maíz",
      "crop_type": "grain",
      "reference_values": {
        "kc_initial": { "value": 0.30, "source": "FAO-56, Tabla 12", "status": "referencia" },
        "kc_mid": { "value": 1.20, "source": "FAO-56, Tabla 12", "status": "referencia" },
        "kc_end": { "value": 0.35, "source": "FAO-56, Tabla 12 (grano secado en el campo)", "status": "referencia" },
        "stage_lengths_days": { "value": { "initial": 30, "development": 40, "mid": 50, "late": 30 }, "source": "FAO-56, Tabla 11", "status": "referencia" },
        "root_depth_initial_m": { "value": 0.25, "source": "Decisión técnica del equipo AgroDSS (rango 0,2–0,3 m); no es un valor de FAO-56", "status": "decisión del equipo" },
        "root_depth_max_m": { "value": 1.0, "source": "FAO-56, Tabla 22 (rango 1,0–1,7 m)", "status": "referencia" },
        "depletion_fraction_p": { "value": 0.55, "source": "FAO-56, Tabla 22", "status": "referencia" },
        "ky": { "value": 1.25, "source": "FAO-33", "status": "referencia" }
      },
      "label": "Valor tabulado FAO, no calibrado para el lote."
    },
    {
      "crop_code": "rye_cover",
      "name": "Centeno de cobertura",
      "crop_type": "cover",
      "reference_values": {
        "kc_initial": { "value": null, "source": null, "status": "sin referencia" },
        "kc_mid": { "value": null, "source": null, "status": "sin referencia" },
        "kc_end": { "value": null, "source": null, "status": "sin referencia" },
        "stage_lengths_days": { "value": null, "source": null, "status": "sin referencia" },
        "root_depth_initial_m": { "value": 0.25, "source": "Decisión técnica del equipo AgroDSS (rango 0,2–0,3 m); no es un valor de FAO-56", "status": "decisión del equipo" },
        "root_depth_max_m": { "value": null, "source": null, "status": "sin referencia" },
        "depletion_fraction_p": { "value": null, "source": null, "status": "sin referencia" },
        "ky": { "value": null, "source": null, "status": "no aplica" }
      },
      "label": "Los valores «sin referencia» deben ingresarse."
    }
  ],
  "fallow": {
    "kc_base_default": 0.20,
    "kc_base_source": "Decisión del equipo AgroDSS (rango 0,15–0,20); no es un valor tabulado único de FAO-56.",
    "residue_rule": "Factor de rastrojo = 1 − 0,05 × (cobertura % / 10); 0 % → 1,0; 100 % → 0,5.",
    "residue_rule_source": "FAO-56, cap. 11 (acolchados orgánicos)",
    "evaporation_layer_m": 0.15
  },
  "wind_proxy": {
    "variable": "WS2M_MAX",
    "threshold_ms": 8.0,
    "rule": "Día de viento fuerte: WS2M_MAX > 8,0 m/s, contado solo sin cultivo vivo.",
    "source": "Decisión del equipo AgroDSS (revisión 3); no calibrado para erosión local."
  },
  "window_defaults": { "start_day": 1, "start_month": 7 },
  "limits": { "max_rotations": 3, "max_start_years": 10, "max_effective_depth_m": 3.0 }
}
```

### 5.5 Error (formato único) [RF-16]

```json
{
  "error": {
    "category": "input",
    "code": "invalid_input",
    "message": "La solicitud tiene datos inválidos. Corrija los campos indicados; no se consultó a NASA POWER.",
    "retryable": false,
    "request_id": "9b1d4e2a-0c3f-4a7e-8d61-2f5e9a7b3c10",
    "details": [
      { "field": "parcel.theta_wp_m3_m3", "message": "El punto de marchitez debe ser menor que la capacidad de campo." },
      { "field": "rotations[1].crops[2].ym_t_ha", "message": "Ym es obligatorio y debe ser mayor que 0 en cultivos de grano." },
      { "field": "rotations[0].crops", "message": "En el escenario 2011, el centeno (posición 2) y la soja (posición 3) quedan activos el mismo día." }
    ]
  }
}
```

`category` toma uno de tres valores (CA-16.4): `input`, `nasa_power` o `internal`.

---

## 6. Contrato de la API

### 6.1 Endpoints [RF-2, RF-15, RNF-13]

| Método y ruta | Propósito | Respuestas | RF |
|---|---|---|---|
| `GET /api/v1/health` | Estado del servicio y versiones; **no** consulta a NASA | 200 `{status, model_version, contract_version}` | — |
| `GET /api/v1/catalog` | Catálogo de cultivos, reglas de barbecho y viento, valores por defecto y límites | 200 (§5.4) | RF-2, CA-11.5 |
| `POST /api/v1/simulations` | Comparación completa | 200 (§5.3), 422, 502, 503, 504, 500 (§6.4) | RF-1…RF-17 |
| `GET /docs`, `GET /openapi.json` | Documentación navegable del contrato (generada por FastAPI) con los ejemplos de §5 | 200 | RNF-13, CA-15.6 |

- La respuesta exitosa es `200 OK` y no `201`, porque no se crea ningún recurso persistente.
- Todas las respuestas llevan la cabecera `X-Request-ID`.
- CORS se configura con el middleware de Starlette; los orígenes permitidos vienen de configuración (por defecto `http://localhost:5173`).

### 6.2 Validación de la solicitud [RF-1, RF-3, RF-4, RF-16, CA-5.3]

La validación ocurre en dos capas. Ambas terminan antes de cualquier llamada a NASA POWER.

1. **Estructural (Pydantic):** tipos, campos obligatorios, rangos de cada campo (tabla de §5.2) y campos desconocidos prohibidos.
   - Los errores de Pydantic se traducen al español con un mapa por tipo de error (`missing`, `greater_than`, `less_than_equal`, `extra_forbidden`…) definido en `core/messages.py`.
   - Las rutas de campo se devuelven con la forma `rotations[0].crops[1].ym_t_ha`.
2. **Semántica (`services/validation.py`):** junta **todos** los errores en una lista (CA-16.1). Comprueba:
   - θPMP < θCC;
   - existencia de `crop_code` en el catálogo;
   - reglas grano/cobertura (Ym obligatorio en grano; Ym, Ky y precio prohibidos en cobertura);
   - parámetros «sin referencia» que faltan;
   - Zr inicial ≤ Zr máxima;
   - etapas «las cuatro o ninguna»;
   - años distintos;
   - ventanas que terminan antes de hoy (UTC);
   - fechas válidas y distintas del 29 de febrero;
   - por cada año de inicio: ciclo dentro de la ventana y sin superposición (usa las mismas funciones de `domain/calendar.py` que el cálculo, CL-4 y CL-5);
   - `currency` presente si hay datos económicos.

   Si la capa estructural falla, la semántica no se ejecuta, porque no puede razonar sobre una estructura inválida. Se informan los errores estructurales completos.

La salida se valida con `response_model` de FastAPI. Además, `response_builder` verifica antes de serializar que no haya `NaN` ni infinitos y que se cumplan `0 ≤ Ya ≤ Ym` y `0 ≤ almacenamiento ≤ capacidad`; si algo falla, es un error de integridad (500).

### 6.3 Consulta en vivo a NASA POWER [RF-5, RF-13, CA-6.1]

**Consulta (una por solicitud, CA-5.1):**

```
GET {POWER_BASE_URL}/api/temporal/daily/point
    ?parameters=PRECTOTCORR,T2M_MAX,T2M_MIN,T2MDEW,WS2M,WS2M_MAX,ALLSKY_SFC_SW_DWN
    &community=AG
    &latitude={lat}&longitude={lon}
    &start={YYYYMMDD primer día de la ventana más temprana}
    &end={YYYYMMDD último día de la ventana más tardía}
    &format=JSON
    &time-standard=LST          (a confirmar en V-1)
User-Agent: AgroDSS/0.1 (NASA Space Apps)     # genérico, sin datos personales
```

- Solo se envían coordenadas, fechas y nombres de variables (CA-5.7).
- Timeout configurable: conexión 10 s y lectura 60 s (`AGRODSS_POWER_CONNECT_TIMEOUT_S`, `AGRODSS_POWER_READ_TIMEOUT_S`) (CA-5.6).
- **Sin reintentos automáticos**, para cumplir RNF-12 (una sola consulta); el usuario reintenta.

**Parseo (`climate_parser.py`):**
1. Cuerpo JSON válido con `properties.parameter`; cada una de las 7 variables presente. Si no, `PowerBadResponseError` (CA-5.5).
2. Unidades de `parameters[CODE].units` comparadas con las esperadas (°C, m/s, mm/día, MJ/m²/día). Una discrepancia es `PowerBadResponseError`; nunca se convierte en silencio.
3. Valor de relleno en `header.fill_value` (−999 si no viene declarado). Todo valor igual al de relleno pasa a `None`.
4. Fechas `YYYYMMDD` → `date`. Toda fecha del rango que no aparezca también es `None` (CA-6.1).
5. Elevación desde `geometry.coordinates[2]`; si falta, `PowerBadResponseError`, porque es imprescindible para la presión atmosférica.
6. Procedencia con versión (`header.api.version`, si existe), ubicación devuelta, instante de la consulta, rango, conteo de faltantes por variable y rótulo de celda (CA-13.1, CA-13.2).
7. La serie vive solo en memoria durante la solicitud (CA-5.2).

**Cobertura (CA-4.5):** se construye el intervalo cubierto de cada variable:
- inicio: el máximo entre el inicio documentado de la variable (en configuración, verificado en V-1) y su primera fecha con dato;
- fin: su última fecha con dato.

Una racha final de valores de relleno se interpreta como «aún no publicado». Una ventana que no queda completa dentro de la cobertura de las 7 variables se **bloquea** (no se sustituye). Los faltantes interiores siguen las reglas de RF-6.

### 6.4 Manejo de errores [RF-16, CA-5.3–CA-5.5, CA-8.17]

| Situación | Detección | HTTP | `category` / `code` | `retryable` | Mensaje (español) |
|---|---|---|---|---|---|
| JSON mal formado, tipos o rangos inválidos, campos desconocidos | Pydantic | 422 | `input` / `invalid_input` | no | «La solicitud tiene datos inválidos…» + `details[]` |
| Datos de riego | Pydantic (`extra`) + regla específica | 422 | `input` / `irrigation_not_supported` | no | «El MVP solo evalúa secano; no se admiten datos de riego.» |
| Incoherencias semánticas (calendario, catálogo, θ, años…) | `validation.py` | 422 | `input` / `invalid_input` | no | Lista completa en `details[]`; no se consultó a NASA |
| Sin conexión o error de DNS hacia POWER | `httpx.ConnectError` | 503 | `nasa_power` / `power_unreachable` | sí | «No se pudo conectar con NASA POWER. Verifique la conexión a internet y reintente. No se calculó ningún escenario.» |
| **POWER no responde a tiempo** | `httpx.TimeoutException` | **504** | `nasa_power` / `power_timeout` | sí | «NASA POWER no respondió dentro de 60 s. No se calculó ningún escenario. Reintente en unos minutos.» |
| POWER limita la frecuencia (429) | Código HTTP 429 | 503 | `nasa_power` / `power_rate_limited` | sí | «NASA POWER rechazó temporalmente la consulta por exceso de pedidos. Reintente más tarde.» |
| POWER responde 4xx/5xx | Código HTTP ≠ 200 | 502 | `nasa_power` / `power_bad_response` | sí | «NASA POWER devolvió un error ({código}). No se calculó ningún escenario.» |
| Respuesta con formato inesperado, variable ausente, unidades distintas o sin elevación | `climate_parser.py` | 502 | `nasa_power` / `power_bad_response` | sí | «NASA POWER devolvió una respuesta incompleta o con formato inesperado. No se calculó ningún escenario.» |
| Escenario fuera de cobertura o con lluvia/temperatura faltante | `missing_data.py` | **200** | — (escenario `blocked`) | — | Motivo dentro de `scenarios[].blocked_reasons` |
| Todos los escenarios bloqueados | `simulation_service.py` | **200** | — | — | `results: []`, motivos y advertencia `SCENARIOS_BLOCKED` (CA-16.3) |
| Falla de cierre de masa, límites, `NaN` o `Ya` fuera de [0, Ym] | `CalculationIntegrityError` | 500 | `internal` / `calculation_integrity` | no | «Error interno de cálculo: un control de consistencia falló y no se entregan resultados. Informe el código de solicitud al equipo.» |
| Excepción no prevista | Manejador genérico | 500 | `internal` / `unexpected_error` | no | «Error interno inesperado. Informe el código de solicitud al equipo.» |

- Los detalles técnicos (pila de llamadas, valores intermedios) solo van al log del servidor, junto al `request_id`; nunca a la respuesta (CA-16.5).
- Una falla de integridad invalida **toda** la solicitud (ver decisión T-14).

### 6.5 Versionado del contrato [CA-15.6]

- Prefijo de ruta `/api/v1` y campo `contract_version` («1.0»).
- Una prueba compara el esquema OpenAPI generado con una instantánea guardada en `tests/`. Si se agrega un campo opcional, la instantánea se actualiza. Si se elimina o renombra un campo, cambia la versión mayor.

---

## 7. Algoritmo principal (pseudocódigo)

### 7.1 Orquestación de una solicitud [RF-1…RF-17]

```
function simulate(request, power_client, clock) -> SimulationResponse:
    # 1. Validación completa, sin red (CA-5.3, CA-16.1)
    errors = validate_semantics(request, CATALOG, today = clock.today_utc())
    if errors: raise InputValidationError(errors)                          # → 422

    # 2. Parámetros efectivos y supuestos fijos
    registry = AssumptionRegistry()
    registry.add_always_on()                                                # CA-14.2
    resolved = resolve_parameters(request, CATALOG, registry)              # CA-1.9, 3.3, 3.4, 3.10, 3.12
    windows  = [build_window(y, resolved.window_start) for y in request.start_years]   # CA-4.2

    # 3. Una única consulta en vivo (CA-5.1, CA-5.2)
    span    = (min(w.first_day for w in windows), max(w.last_day for w in windows))
    raw     = power_client.fetch_daily(resolved.lat, resolved.lon, span, POWER_PARAMETERS)
              # ConnectError → 503 · Timeout → 504 · HTTP ≠ 200 → 502
    climate = parse_power_response(raw, span)                               # CA-5.5, CA-6.1
    provenance = build_provenance(raw, climate, clock.now_utc())            # RF-13

    # 4. Escenarios × rotaciones
    outcomes, runs = [], []
    for window in windows:
        block = check_coverage(window, climate)                             # CA-4.5
        if block: outcomes.append(blocked(window, block)); continue
        days    = climate.slice(window)                                     # 730/731 registros en orden
        missing = classify_missing(days)                                    # CA-6.1–6.3 (+ Tmáx < Tmín)
        if missing.blocking: outcomes.append(blocked(window, missing.reasons)); continue
        weather = apply_fao56_substitutions(days, climate.elevation_m, resolved.lat, registry, window)   # CA-6.4–6.8
        et0     = clamp_negative(et0_series(weather, climate.elevation_m, resolved.lat), registry, window)  # RF-7, CA-7.2
        outcomes.append(computed(window, missing.substitutions, sum(rain(days)), sum(et0)))

        for rotation in resolved.rotations:                                 # la ET₀ se calcula una sola vez por escenario
            timeline = build_timeline(window, rotation)                     # RF-3, CA-3.11
            balance  = run_daily_balance(timeline, weather, et0, resolved.parcel)    # RF-8 (§7.4)
            crops    = [crop_outcome(seg, balance, registry) for seg in timeline.crop_segments]   # RF-9
            economy  = rotation_economics(crops, rotation)                  # RF-10
            exposure = soil_exposure(timeline, days.ws2m_max_raw)           # RF-11 (valores crudos de POWER)
            runs.append(RunResult(rotation.id, window.start_year, balance.summary, crops, economy, exposure))

    # 5. Agregados y salida
    ranges      = compute_ranges(runs, outcomes)                            # RF-12
    comparisons = pairwise_margin_differences(runs)                         # CA-15.4, D-15
    warnings    = build_warnings(outcomes, registry, resolved)              # RF-17, CA-1.11
    return build_response(resolved, provenance, outcomes, runs, ranges, comparisons, registry, warnings)  # RF-15
    # Cualquier CalculationIntegrityError en 4 o 5 → 500 para toda la solicitud
```

### 7.2 Calendario y línea de tiempo [RF-3, RF-4]

```
function build_window(start_year, start):                      # start = (día, mes)
    first = date(start_year, start.month, start.day)
    last  = date(start_year + 2, start.month, start.day) - 1 día
    return Window(start_year, first, last, n_days = (last - first).days + 1)     # 730 o 731

function sowing_date(window, sowing, start):                   # sowing = (window_year, día, mes)
    year_k_first = date(window.start_year + sowing.window_year - 1, start.month, start.day)
    candidate = date(year_k_first.year, sowing.month, sowing.day)
    if candidate < year_k_first: candidate = date(year_k_first.year + 1, sowing.month, sowing.day)
    return candidate

function cycle_end(sowing_date, stages):
    L = stages.initial + stages.development + stages.mid + stages.late
    return sowing_date + (L - 1) días                           # la siembra es el día 1 del ciclo

function build_timeline(window, rotation):
    segments, cursor = [], window.first
    residue = rotation.initial_residue_cover_pct                # barbecho previo al primer cultivo
    for crop in rotation.crops:                                 # en orden
        s, e = sowing_date(window, crop.sowing), cycle_end(s, crop.stages)
        if s > cursor: segments.append(Fallow(cursor, s - 1 día, residue))
        segments.append(CropSegment(crop, s, e))
        cursor  = e + 1 día
        residue = crop.residue_cover_after_pct                  # rastrojo que deja este cultivo
    if cursor <= window.last: segments.append(Fallow(cursor, window.last, residue))
    assert los segmentos cubren cada día de la ventana una sola vez        # CA-8.2
    return Timeline(segments)
```

La validación previa (§6.2) ejecuta `sowing_date` y `cycle_end` para **cada** año de inicio. Si `s` es anterior o igual al fin del cultivo previo, hay superposición (CA-3.6); si `s < first` o `e > last`, el ciclo queda fuera de la ventana (CA-3.7).

### 7.3 Clima, faltantes y ET₀ [RF-6, RF-7]

```
function classify_missing(days):
    blocking      = variables entre {PRECTOTCORR, T2M_MAX, T2M_MIN} con algún None → fechas
    inconsistent  = días con T2M_MAX < T2M_MIN → bloqueo «dato inconsistente de la fuente»
    substitutions = variables entre {ALLSKY_SFC_SW_DWN, T2MDEW, WS2M} con algún None → fechas
    # WS2M_MAX faltante no se sustituye: solo afecta al proxy (CA-11.4)
    return MissingReport(blocking ∪ inconsistent, substitutions)

function apply_fao56_substitutions(days, z, lat, registry, window):
    for d in days:
        ra  = extraterrestrial_radiation(lat, d.day_of_year)                # ec. 21–25
        rso = (0.75 + 2e-5 * z) * ra                                         # ec. 37
        rs  = d.rs   if d.rs   is not None else min(KRS * sqrt(d.tmax - d.tmin) * ra, rso)   # ec. 50, kRs = 0,16
        tdew= d.tdew if d.tdew is not None else d.tmin - TDEW_SEMIARID_OFFSET_C              # ec. 48 + anexo 6 (2 °C)
        u2  = d.ws2m if d.ws2m is not None else 2.0                          # valor provisional FAO-56
        registrar cada sustitución por variable y fecha (CA-6.7)
        yield Weather(d.date, d.rain, d.tmax, d.tmin, tdew, u2, rs, ra, rso)
    # Nunca se mira el día anterior ni el siguiente (CA-6.2)

function et0_penman_monteith(w, z):                                          # FAO-56, ec. 6; mm/día
    tmean = (w.tmax + w.tmin) / 2
    P     = 101.3 * ((293 - 0.0065 z) / 293) ^ 5.26                           # ec. 7
    gamma = 0.000665 * P                                                     # ec. 8
    es    = (e0(w.tmax) + e0(w.tmin)) / 2                                    # ec. 11–12
    ea    = e0(w.tdew)                                                       # ec. 14
    delta = 4098 * e0(tmean) / (tmean + 237.3) ^ 2                           # ec. 13
    rns   = (1 - 0.23) * w.rs                                                # ec. 38
    rnl   = SIGMA * ((tmax_K^4 + tmin_K^4) / 2) * (0.34 - 0.14 sqrt(ea)) * (1.35 * min(w.rs / w.rso, 1) - 0.35)   # ec. 39
    rn    = rns - rnl                                                        # ec. 40; G = 0 (ec. 42)
    return (0.408 delta rn + gamma (900 / (tmean + 273)) w.u2 (es - ea)) / (delta + gamma (1 + 0.34 w.u2))
```

`e0(T) = 0,6108 · exp(17,27 T / (T + 237,3))` (ecuación 11). `SIGMA = 4,903·10⁻⁹ MJ K⁻⁴ m⁻² día⁻¹`. Una ET₀ negativa se reemplaza por 0 y se registra (CA-7.2).

### 7.4 Loop diario del balance hídrico continuo (FAO-56) [RF-8]

**Modelo.** Un perfil fijo de profundidad `D` (la profundidad efectiva) dividido en dos compartimentos:
- **zona activa**, de profundidad `z_active`: la exploran las raíces del cultivo (Zr del día) o, en barbecho, la capa evaporable `Ze` = 0,15 m;
- **zona inferior**: el resto, de `z_active` hasta `D`.

El agua útil se cuenta en mm por encima de PMP. La suma de ambas zonas es el almacenamiento del perfil. El límite entre zonas se mueve (las raíces crecen, se cambia de cultivo a barbecho), pero **nunca se reinicia el agua**: solo se redistribuye, suponiendo contenido uniforme dentro de cada compartimento.

```
function run_daily_balance(timeline, weather, et0, parcel) -> BalanceRun:
    D         = parcel.effective_depth_m
    AWC       = parcel.theta_fc - parcel.theta_wp                  # m³/m³ de agua útil
    cap(z)    = 1000 * AWC * z                                     # mm de agua útil en un espesor z (m)
    C_profile = cap(D)                                             # capacidad del perfil (CA-1.6)

    # Estado inicial: humedad uniforme en todo el perfil (CA-8.3, CA-4.6)
    W0       = parcel.initial_available_water_pct / 100 * C_profile
    z_active = active_depth(timeline.day(0), D)
    W_act    = W0 * z_active / D                                   # agua en la zona activa
    W_low    = W0 - W_act                                          # agua en la zona inferior
    acc      = Accumulators()

    for i, day in enumerate(timeline.days):                        # cronológico, sin huecos (CA-8.2)
        seg = day.segment

        # (0) TRANSFERENCIA: el primer día de un segmento parte del agua con la que terminó el anterior
        if day.is_first_of(seg):
            seg.storage_at_start_mm = W_act + W_low                # = storage_at_end_mm del segmento previo (CA-8.6)

        # (1) Profundidad activa del día y redistribución sin pérdida de masa (CA-8.4, CA-8.5, CA-8.7)
        z_new        = active_depth(day, D)
        W_act, W_low = redistribute(W_act, W_low, z_active, z_new, D)
        z_active     = z_new
        C_act        = cap(z_active)
        C_low        = C_profile - C_act

        # (2) Coeficiente de estrés con el estado al inicio del día (convención FAO-56, ec. 84) (CA-8.9)
        if seg.is_crop:
            TAW = C_act;  RAW = seg.p * TAW;  Dr = TAW - W_act
            Ks  = 1 if Dr <= RAW else (TAW - Dr) / ((1 - seg.p) * TAW)

        # (3) Lluvia: llena de arriba hacia abajo; lo que no entra en el perfil se pierde (CA-8.12, CA-8.13)
        P        = weather[i].rain_mm
        into_act = min(P, C_act - W_act);             W_act += into_act
        into_low = min(P - into_act, C_low - W_low);  W_low += into_low
        excess   = P - into_act - into_low             # excedente perdido del día (escorrentía o percolación)

        # (4) Consumo, solo desde la zona activa (CA-8.8, CA-8.10, CA-8.15)
        if seg.is_crop:
            Kc  = kc_for_day(seg, day.day_in_cycle)                     # curva FAO-56 por etapas
            ETc = Kc * et0[i]
            ETa = min(Ks * ETc, W_act)                                  # nunca más que el agua disponible
            W_act -= ETa
            acc.crop(seg).add(etc = ETc, eta = ETa, stressed = Ks < 1)
        else:
            E_dem = parcel.fallow_kc_base * residue_factor(seg.residue_cover_pct) * et0[i]
            E     = min(E_dem, W_act)                                   # solo desde la capa evaporable Ze
            W_act -= E
            acc.fallow(seg).add(demand = E_dem, evap = E)

        # (5) Controles diarios (CA-8.14, CA-8.15)
        require 0 <= W_act <= C_act + ε  and  0 <= W_low <= C_low + ε          # ε = 1e-9 mm
        require consumo del día <= demanda del día
        acc.day(rain = P, excess = excess)

        # (6) TRANSFERENCIA: el agua al cierre del último día del segmento es el estado inicial del siguiente
        if day.is_last_of(seg):
            seg.storage_at_end_mm = W_act + W_low

    # (7) Cierre de masa de la corrida (CA-8.16, CA-8.17)
    W_end   = W_act + W_low
    closure = (W_end - W0) - (acc.rain - acc.crop_eta - acc.fallow_evap - acc.excess)
    if abs(closure) > 0.01: raise CalculationIntegrityError(closure, rotation, scenario)
    return BalanceRun(acc, W0, W_end, closure, timeline.segments)
```

**Funciones auxiliares:**

```
function active_depth(day, D):
    if day.segment.is_crop:
        c      = day.segment.crop
        L_grow = c.stages.initial + c.stages.development               # Zr máxima al final del desarrollo
        f      = min(1, (day.day_in_cycle - 1) / (L_grow - 1))
        return min(D, c.zr_initial + f * (c.zr_max - c.zr_initial))     # crecimiento lineal
    return min(D, ZE_FALLOW_M)                                          # 0,15 m en barbecho

function redistribute(W_act, W_low, z_old, z_new, D):                   # conserva W_act + W_low
    if z_new > z_old and D > z_old:                                     # la zona activa se profundiza
        moved = W_low * (z_new - z_old) / (D - z_old)                   # agua de la franja incorporada
        return (W_act + moved, W_low - moved)
    if z_new < z_old:                                                   # la zona activa se achica
        moved = W_act * (z_old - z_new) / z_old                         # agua de la franja que se libera
        return (W_act - moved, W_low + moved)
    return (W_act, W_low)

function kc_for_day(seg, i):                                            # FAO-56, ec. 66; i = 1…L
    L1, L2, L3 = initial, initial + development, initial + development + mid
    if i <= L1: return kc_ini
    if i <= L2: return kc_ini + (i - L1) / development * (kc_mid - kc_ini)
    if i <= L3: return kc_mid
    return kc_mid + (i - L3) / late * (kc_end - kc_mid)

function residue_factor(cover_pct):                                     # FAO-56, cap. 11
    return 1 - 0.05 * (cover_pct / 10)                                  # 0 % → 1,0 · 50 % → 0,75 · 100 % → 0,5
```

**Ejemplo de transferencia** (rotación A, perfil de 1,2 m, AWC 0,16 → capacidad 192 mm):

| Día | Segmento | z_active | W_act | W_low | Total | Qué ocurre |
|---|---|---|---|---|---|---|
| 13-03-2009 (fin) | Maíz, Zr = 1,2 m | 1,20 m | 31,2 | 0,0 | **31,2** | `storage_at_end_mm` del maíz = 31,2 |
| 14-03-2009 (paso 1) | Barbecho | 1,20 → 0,15 m | 3,9 | 27,3 | **31,2** | `storage_at_start_mm` del barbecho = 31,2; el agua de 0,15–1,2 m pasa a la zona inferior |
| Barbecho | Barbecho | 0,15 m | ≤ 24,0 | se conserva | — | La evaporación solo seca la capa de 0,15 m; el agua profunda queda para el centeno |
| 01-04-2009 | Centeno, Zr inicial 0,25 m | 0,15 → 0,25 m | ↑ | ↓ | igual al fin del barbecho | El límite baja de 0,15 a 0,25 m: la franja de 0,10 m pasa de la zona inferior a la activa, sin crear ni perder agua |
| Siguientes | Centeno, Zr creciente | 0,25 → 0,8 m | ↑ | ↓ | se conserva | Al profundizar, las raíces incorporan agua de la zona inferior |

### 7.5 Post-proceso [RF-9, RF-10, RF-11, RF-12]

```
function crop_outcome(seg, balance, registry):                          # RF-9
    ETm, ETa = Σ ETc del ciclo, Σ ETa del ciclo
    base = {fechas, storage_at_sowing = seg.storage_at_start_mm, storage_at_end = seg.storage_at_end_mm,
            ETm, ETa, ETa/ETm (si ETm > 0), stress_days}
    if seg.crop.type == cover: return base + {yield: null, note: "No aplica (cultivo de cobertura)."}
    if ETm == 0:               return base + {yield: null, note: "ETm = 0: no se calcula el rendimiento."}
    Ya_raw = Ym * (1 - Ky * (1 - ETa / ETm))
    Ya     = max(0, Ya_raw);  if Ya_raw < 0: registry.add(YIELD_CLIPPED_ZERO, ...)
    require 0 <= Ya <= Ym                                               # CA-9.4
    return base + {yield_t_ha: Ya, relative_yield: Ya / Ym}

function crop_economics(outcome, crop):                                 # RF-10
    if crop sin precio (grano) o sin costos: return {status: "sin datos"}
    income = (crop.type == grain) ? Ya * price : 0
    margin = income - direct_costs
    label  = margin < 0 ? "Margen bruto negativo" : null                # nunca «pérdida»

function rotation_economics(crops):                                     # CA-10.3, CA-10.4
    if algún cultivo «sin datos»: return {status: "not_computed", crops_missing_economics: [...]}
    return sumas de ingreso, costos y margen

function soil_exposure(timeline, ws2m_max_raw):                         # RF-11
    for day in ventana:
        if day.is_live_crop: live += 1; continue                        # el viento no se evalúa con cultivo vivo
        no_live += 1
        v = ws2m_max_raw[day]                                           # valor crudo de POWER, nunca sustituido
        if v is None: no_data += 1
        elif v > 8.0: strong += 1                                       # estrictamente mayor

function compute_ranges(runs, outcomes):                                # RF-12
    por rotación, sobre escenarios con status computed:
        Ya y ETa/ETm por posición de cultivo; margen de la rotación (solo si está calculado en todos);
        días sin cultivo vivo con viento fuerte
        → {min, median (statistics.median: promedio de los centrales si n es par), max}, n
    si n == 1: valor único con nota «sin rango»

function pairwise_margin_differences(runs):                             # D-15
    por escenario y por par (X, Y) con X posterior a Y en el orden A < B < C,
    con ambos márgenes calculados: X − Y, rotulado como descriptivo
```

---

## 8. Decisiones técnicas y alternativas descartadas

| # | Decisión | Justificación | Alternativas descartadas | RF |
|---|---|---|---|---|
| T-1 | Servicio sin estado: un `POST` síncrono que devuelve todo | Lo exige C5; el cálculo tarda menos de un segundo, salvo la espera de POWER | Trabajos en segundo plano o colas (requieren almacenamiento); WebSockets (complejidad sin beneficio) | RF-15 |
| T-2 | Endpoint `def` síncrono con `httpx.Client` | FastAPI lo ejecuta en su pool de hilos sin bloquear el bucle de eventos. Es más simple de probar y no hay concurrencia que optimizar en el MVP | `async` con `AsyncClient` (más complejidad sin ganancia); `requests` (dependencia extra; httpx ya es obligatorio para `TestClient`); `urllib` (sin transporte de prueba integrado) | RF-5 |
| T-3 | **Una consulta** que cubre desde la ventana más temprana hasta la más tardía | Lo exigen CA-5.1 y RNF-12; las ventanas superpuestas no repiten datos | Una consulta por ventana (hasta 10 llamadas); consultas en paralelo (carga sobre la API pública) | RF-5 |
| T-4 | Sin caché ni escritura de series | C5 enmendado y CA-5.2 | `lru_cache` en memoria, archivos en disco, Redis | RF-5 |
| T-5 | `domain/` puro, con dataclasses de la biblioteca estándar | Funciones puras y testeables (AGENTS); el contrato API queda desacoplado de las fórmulas | Usar Pydantic dentro del dominio (acopla y es más lento en el loop); numpy o pandas (dependencias innecesarias para ~22 000 pasos diarios) | RF-7, RF-8 |
| T-6 | **Perfil fijo con dos compartimentos y límite móvil; redistribución con contenido uniforme** | Implementa la decisión 7 del spec: raíces que crecen dentro del perfil, agua inaccesible bajo raíces jóvenes y transferencia exacta entre segmentos; la conservación de masa es trivial de verificar | Un solo balde sin crecimiento radicular (Zr no influiría en nada); modelo multicapa de 10 cm (más parámetros y pruebas); balance solo de la zona radicular, como en FAO-56 básico (pierde el agua de abajo al cambiar Zr y rompe la masa) | RF-8 |
| T-7 | Evaporación de barbecho solo desde la capa `Ze` = 0,15 m (FAO-56, cap. 7) | Con Kc 0,20 sobre todo el perfil, un barbecho largo y seco vaciaría agua profunda que en la realidad se conserva, y se penalizaría el barbecho de forma artificial | Evaporar de todo el perfil (sesgo contra el barbecho); Kc dual con TEW/REW (fuera del alcance aprobado) | RF-8 |
| T-8 | Ks con el estado al inicio del día y ETa limitada por el agua tras la lluvia | Sigue la convención de FAO-56 (agotamiento del día anterior) y garantiza `ETa ≤ disponible` | Ks después de la lluvia (no es la convención FAO-56; mezcla días) | RF-8 |
| T-9 | Lluvia de arriba hacia abajo; pérdida solo con el perfil lleno | Implementa la decisión 9 del spec y conserva masa | Percolación limitada por conductividad o escorrentía por número de curva (no aprobados) | RF-8 |
| T-10 | Raíces lineales desde Zr inicial (siembra) hasta Zr máxima al final de la etapa de desarrollo | Criterio simple de FAO-56; la profundidad máxima coincide con la cobertura plena | Crecimiento proporcional a Kc; Zr máxima recién en la cosecha | RF-8 |
| T-11 | Humedad con T2MDEW | Es el método preferido por FAO-56 (ecuación 14) | RH2M media (el método menos preferido por FAO-56); pedir ambas variables (más lógica de faltantes) | RF-7 |
| T-12 | **Viento fuerte = WS2M_MAX > 8 m/s en días sin cultivo vivo** | El máximo diario capta los episodios de ráfaga que movilizan suelo. Con la media diaria (WS2M) a 2 m, pocos días superan 8 m/s y el indicador quedaría casi siempre en cero. Se mantiene la altura de 2 m del resto de las variables | WS2M media (revisión 2, reemplazada); WS10M_MAX (otra altura, umbral no comparable); datos horarios (otra API y mucho más volumen) | RF-11 |
| T-13 | Cobertura = inicio documentado + primera y última fecha con dato; racha final de relleno = no publicado → bloqueo | Distingue «aún no publicado» (bloquear, CA-4.5) de «faltante puntual» (sustituir, RF-6) | Sustituir siempre (ocultaría radiación no publicada); solo un retraso fijo configurado (frágil) | RF-4, RF-6 |
| T-14 | Una falla de integridad invalida **toda** la solicitud (500) | Indica un defecto del modelo, no un problema de datos: una comparación parcial sería engañosa | Marcar solo la corrida afectada (resultados mezclados con un modelo defectuoso) | RF-8, RF-16 |
| T-15 | Validación en dos capas, todo antes de la red, con errores semánticos juntados | Cumple CA-5.3 y CA-16.1; el calendario por escenario usa las mismas funciones que el cálculo | Todo en validadores de Pydantic (se detiene por modelo y duplica la lógica de calendario) | RF-16 |
| T-16 | Mensajes en español con un mapa propio de tipos de error de Pydantic | La interfaz es en español (AGENTS) | El 422 por defecto de FastAPI (en inglés y con otro formato) | RF-16 |
| T-17 | Códigos HTTP: 422 / 502 / 503 / 504 / 500, más `category` y `retryable` | El frontend distingue entrada, NASA e interno (CA-16.4) y sabe cuándo ofrecer «reintentar» | Siempre 200 con una bandera de error; 400 genérico | RF-16 |
| T-18 | Unidades en el nombre de cada clave y objeto `{value, origin, source, note}` para los parámetros resueltos | Unidad explícita sin inflar el JSON (AGENTS) y origen trazable donde importa | `{value, unit}` en cada número (respuesta mucho más grande) | RF-14, RF-15 |
| T-19 | Redondeo solo al serializar | Los controles usan precisión completa | Redondear durante el cálculo (acumula error); no redondear nunca (ruido para la interfaz) | RF-15 |
| T-20 | Catálogo como JSON estático validado al arrancar | Lo pueden revisar agrónomos sin leer Python; cada valor exige una cita; el servicio falla al iniciar si el catálogo es inválido | Base de datos (prohibida); un diccionario en Python (menos revisable) | RF-2 |
| T-21 | Diferencias de margen entre pares de rotaciones, sin orden | El frontend no puede calcular (C3) y el producto no recomienda (CA-17.5) | Ranking o la etiqueta «mejor rotación» | RF-15, RF-17 |
| T-22 | Mocks con `httpx.MockTransport` y respuestas sintéticas generadas en las pruebas | Sin dependencias extra; sin guardar copias de datos reales (espíritu de C5) | respx o pytest-httpx (dependencias); vcrpy con grabaciones reales (equivale a guardar series) | RF-5 |
| T-23 | Pruebas de invariantes con el módulo `random` y semillas fijas | Cubren muchas combinaciones sin dependencias | hypothesis (dependencia nueva) | RF-8 |
| T-24 | Reloj inyectado (`clock`) | Hace deterministas la regla «ventana antes de hoy» y `computed_at` (RNF-1) | Leer la hora del sistema dentro del dominio | RF-4 |
| T-25 | Fecha «hoy» en UTC | `zoneinfo` en Windows necesita el paquete `tzdata` (una dependencia más) | Hora de Argentina con `zoneinfo` | RF-4 |

---

## 9. Estrategia de pruebas

### 9.1 Organización

```
backend/tests/
├── conftest.py                 # catálogo, reloj fijo, TestClient con el cliente POWER sustituido
├── builders/
│   ├── power_payload.py        # genera JSON con forma de POWER (rellenos, variables ausentes, unidades alteradas)
│   └── weather.py              # series diarias sintéticas con semilla (lluvias extremas, sequías)
├── unit/                       # una prueba por módulo de domain/ y services/
├── invariants/                 # conservación de masa y límites sobre miles de días sintéticos
├── integration/                # cliente POWER con MockTransport; simulation_service de punta a punta
├── api/                        # endpoints, errores, instantánea del contrato
├── nonfunctional/              # sin persistencia, lenguaje, rendimiento, regla de dependencias
└── live/                       # @pytest.mark.live: API real, excluida por defecto
```

Configuración de pytest: `addopts = -m "not live"`, con los marcadores `live` y `slow`. **Ninguna prueba por defecto usa la red** (RNF-9).

### 9.2 Pruebas unitarias del dominio

| Módulo | Casos clave | RF / CA |
|---|---|---|
| `et0` | Ejemplo 18 de FAO-56 (ET₀ diaria = 3,9 mm/día, ±0,1); ejemplo 8 de FAO-56 (Ra a 20° S el 3 de septiembre = 32,2 MJ/m²/día, ±0,1; hemisferio sur, como San Luis); ejemplo 2 de FAO-56 (P a 1800 m = 81,8 kPa); e°(20 °C) = 2,338 kPa; Hargreaves limitado por Rso; ET₀ negativa → 0 con supuesto | RF-7, CA-7.3 |
| `kc_curve` | Valores en cada límite de etapa (días L1, L2, L3, L); linealidad en desarrollo y etapa final | CA-8.8 |
| `root_growth` | Día 1 = Zr inicial; día L_grow = Zr máxima; constante después; nunca supera D | CA-8.4, CA-3.10 |
| `redistribute` | Conserva la suma exacta; contenido uniforme; D = z_old sin zona inferior; achicar y profundizar | CA-8.7 |
| `water_balance` (casos chicos calculados a mano, 3 a 10 días) | Lluvia mayor que la capacidad → excedente; humedad inicial 0 % → Ks = 0, ETa = 0; humedad inicial 100 % → primera lluvia perdida; barbecho de 0 días; agua profunda inaccesible con raíces someras (CL-16) que luego se incorpora; rastrojo 0/50/100 % → factor 1/0,75/0,5 | CA-8.1–CA-8.17 |
| `yield_response` | `0 ≤ Ya ≤ Ym`; Ky > 1 con déficit severo → 0 y supuesto; ETm = 0 → sin cálculo; cobertura → «no aplica» | RF-9 |
| `economics` | Sumas; cobertura con margen −costos; datos incompletos → «no calculado»; rótulo «margen bruto negativo» | RF-10 |
| `wind_proxy` | WS2M_MAX = 8,0 → no cuenta; 8,1 sin cultivo → cuenta; 8,1 con cultivo → no cuenta; `None` → «sin dato»; ignora los 2 m/s sustituidos en WS2M | RF-11 |
| `stats` | n impar, n par (mediana como promedio), n = 1 | RF-12 |
| `calendar` | 730 y 731 días; 29 de febrero rechazado; superposición solo en un año bisiesto (CL-4); ciclo que excede la ventana solo en un escenario (CL-5); fecha de siembra en el año 1 o 2 | RF-3, RF-4 |
| `missing_data` | Lluvia o temperatura faltante → bloqueo; Tmáx < Tmín → bloqueo; las 3 sustituciones registradas con fechas; **sin interpolación**: con vecinos distintos, el valor sustituido es exactamente el de la fórmula FAO-56 | RF-6 |

### 9.3 Invariantes: conservación de masa y límites físicos [RF-8, C4]

Un generador con semilla (`random.Random(seed)`) produce 731 días con lluvias de Poisson y exponenciales, un día de 300 mm, una sequía de 120 días y una ET₀ entre 0 y 9 mm/día. Se combina con:
- **suelos:** D = 0,3 / 1,2 / 2,0 m; AWC = 0,05 / 0,16 / 0,25;
- **humedad inicial:** 0 / 50 / 100 %;
- **rotaciones:** con barbecho de 0 días, barbecho largo, solo cobertura y Zr máxima > D;
- **semillas:** 50 por combinación (marcador `slow` para la matriz completa).

En **cada día** se verifica:
- `0 ≤ W_act ≤ C_act` y `0 ≤ W_low ≤ C_low`, por lo tanto `0 ≤ almacenamiento ≤ capacidad del perfil`;
- `ETa ≤ ETc`, `ETa ≤ agua disponible` y `E ≤ E_dem`;
- cierre diario `ΔW = P − ETa − E − excedente` con |error| ≤ 1e-9 mm.

En **cada corrida** se verifica:
- |cierre| ≤ 0,01 mm (CA-8.16);
- la cronología tiene exactamente `n_days` días consecutivos, sin huecos ni duplicados (CA-8.2);
- `storage_at_end(segmento k) == storage_at_start(segmento k+1)` (CA-8.6);
- `0 ≤ Ya ≤ Ym`.

**Unidades:** pruebas dimensionales de `cap(z)` (m³/m³ × m × 1000 = mm) y verificación de que todas las claves de salida de agua terminen en `_mm` (prueba sobre el esquema).

### 9.4 Integración con NASA POWER mediante mocks [RF-5, RF-13, CA-5.x]

Se inyecta un `httpx.MockTransport` con `app.dependency_overrides[get_power_client]`. Los cuerpos se generan con `builders/power_payload.py`; no hay archivos con datos reales.

| Escenario simulado | Resultado esperado |
|---|---|
| 200 con las 7 variables completas | 200; procedencia completa; **1 sola llamada** registrada |
| Parámetros enviados | Exactamente `parameters, community, latitude, longitude, start, end, format, time-standard`; ningún otro dato (CA-5.7) |
| `httpx.ConnectError` | 503 `power_unreachable`, `retryable: true`, sin resultados |
| `httpx.ReadTimeout` o `ConnectTimeout` | **504 `power_timeout`**, con el mensaje que indica los segundos configurados |
| Estado 500 y 404 | 502 `power_bad_response` |
| Estado 429 | 503 `power_rate_limited` |
| Cuerpo que no es JSON; falta `properties.parameter`; falta WS2M_MAX; unidades en kW-hr; sin elevación | 502 `power_bad_response` |
| Relleno −999 interior en radiación | 200; sustitución Hargreaves registrada |
| Racha final de −999 en radiación | 200; escenario afectado **bloqueado** (no sustituido) |
| −999 en lluvia | 200; escenario bloqueado con fecha |
| Solicitud inválida | 422 y **0 llamadas** al transporte (CA-5.3) |

### 9.5 API y contrato [RF-15, RF-16]

- Flujo completo con `TestClient`: 200 con todos los bloques de §5.3.
- 422 con varios errores semánticos juntos y en español.
- Riego → `irrigation_not_supported`.
- 500 de integridad, inyectando una falla en el balance con `monkeypatch`: sin resultados parciales ni detalles internos.
- Todos los escenarios bloqueados → 200 con `results: []`.
- **Instantánea del esquema OpenAPI** (CA-15.6).
- Las claves numéricas de la respuesta llevan sufijo de unidad (`_mm`, `_t_ha`, `_per_ha`, `_ms`, `_m`, `_pct`, `_days`, `_ratio`) o figuran en una lista explícita de adimensionales (CA-15.3).
- `GET /catalog`: cada valor con `source` o con `status` «sin referencia» o «no aplica».

### 9.6 Pruebas no funcionales

| Prueba | Cómo | Requisito |
|---|---|---|
| **Sin persistencia** | Durante una simulación completa, `monkeypatch` hace fallar `open` en modo escritura y `Path.write_*`; además, se ejecuta en un directorio temporal y se verifica que no aparecen archivos | C5, CA-5.2, RNF-8 |
| **Lenguaje** | Se recorren `core/messages.py` y todos los textos de respuestas de ejemplo buscando «pérdida neta», «probabilidad», «precisión», «recomendada», «óptima» y «mejor» aplicados a resultados o rotaciones | RF-17, CA-10.7 |
| **Rendimiento** | 3 rotaciones × 10 escenarios con un payload sintético: el procesamiento termina en ≤ 5 s (marcador `slow`) | RNF-3 |
| **Regla de dependencias** | Se analizan con `ast` los `import` de `domain/`: no puede haber fastapi, pydantic ni httpx | T-5 |
| **Reproducibilidad** | La misma entrada con el mismo payload y el mismo reloj produce un JSON idéntico (salvo `request_id`) | RNF-1 |

### 9.7 Prueba manual contra la API real [spec §8]

`pytest -m live` (fuera de la integración continua) envía una solicitud de 3 rotaciones × 3 escenarios para un punto de San Luis contra NASA POWER real. Verifica:
- 200, con las 7 variables presentes y las unidades esperadas;
- cierre de masa en todas las corridas;
- tiempo total registrado.

El resultado se documenta en el PR, sin guardar la serie.

### 9.8 Correspondencia con los criterios de finalización del spec (§8)

| Criterio del spec | Pruebas |
|---|---|
| Conservación de masa | §9.3 |
| Límites | §9.3 y unitarias de `water_balance` |
| Transferencia | §9.3 (`storage_at_end == storage_at_start`) |
| Raíces | Unitarias de `water_balance` (CL-16) y `root_growth` |
| Barbecho y rastrojo | Unitarias de `water_balance` |
| Excedente | Unitarias de `water_balance` y §9.3 |
| Proxy de viento | Unitarias de `wind_proxy` |
| Cronología | Unitarias de `calendar` y §9.3 |
| ET₀ (ejemplo 18) | Unitarias de `et0` |
| Faltantes | Unitarias de `missing_data` y §9.4 |
| NASA POWER (mocks y prueba manual) | §9.4 y §9.7 |
| Sin persistencia | §9.6 |
| Lenguaje | §9.6 |
| Contrato documentado | §9.5 |
| Lint y arranque | `ruff check .`, `ruff format --check .` y una prueba de importación de `app.main` |

---

## 10. Matriz de cobertura de RF

| RF | Módulos | Secciones del plan | Pruebas |
|---|---|---|---|
| RF-1 Parcela | `models/request`, `services/validation`, `services/parameter_resolver`, `domain/water_balance` | §5.2, §6.2, §7.4 | unit/validation, api |
| RF-2 Catálogo | `data/crop_catalog.json`, `services/catalog_service`, `routers/catalog` | §5.4, §6.1 | api/catalog, unit/catalog_integrity |
| RF-3 Rotaciones | `models/request`, `services/validation`, `services/parameter_resolver`, `domain/calendar` | §5.2, §6.2, §7.2 | unit/calendar, unit/validation |
| RF-4 Escenarios | `domain/calendar`, `services/validation`, `domain/missing_data` (cobertura) | §6.2, §6.3, §7.2 | unit/calendar, integration/power |
| RF-5 NASA POWER | `services/power_client`, `services/climate_parser`, `core/config` | §6.3, §6.4 | integration/power (mocks), live |
| RF-6 Faltantes | `domain/missing_data`, `domain/et0` | §7.3 | unit/missing_data, integration/power |
| RF-7 ET₀ | `domain/et0` | §7.3 | unit/et0 |
| RF-8 Balance | `domain/water_balance`, `domain/kc_curve`, `domain/root_growth` | §7.4 | unit/water_balance, invariants |
| RF-9 FAO-33 | `domain/yield_response` | §7.5 | unit/yield_response, invariants |
| RF-10 Economía | `domain/economics` | §5.2, §7.5 | unit/economics |
| RF-11 Viento | `domain/wind_proxy` | §7.5, T-12 | unit/wind_proxy |
| RF-12 Rangos | `domain/stats`, `services/simulation_service` | §7.5 | unit/stats |
| RF-13 Procedencia | `services/climate_parser`, `services/response_builder` | §5.3, §6.3 | integration/power, api |
| RF-14 Supuestos | `services/assumptions`, `core/messages` | §5.3, §11 | unit/assumptions, api |
| RF-15 Respuesta | `models/response`, `services/response_builder` | §5.1, §5.3, §6.5 | api/contract_snapshot, api |
| RF-16 Errores | `core/exceptions`, `core/error_handlers`, `services/validation` | §5.5, §6.2, §6.4 | api/errors, integration/power |
| RF-17 Lenguaje | `core/messages`, `services/response_builder` | §5.3, T-21 | nonfunctional/language |

---

## 11. Supuestos nuevos introducidos por el plan

Estos supuestos amplían las listas de CA-14.2 y CA-14.3 del spec. Se devuelven en `assumptions[]` con su código.

| Código | Supuesto | Fuente | Cuándo aparece |
|---|---|---|---|
| `FALLOW_EVAPORATION_LAYER` | En barbecho, la evaporación se extrae solo de una capa superficial de 0,15 m | FAO-56, cap. 7 (Ze 0,10–0,15 m) | Siempre que haya barbecho |
| `UNIFORM_REDISTRIBUTION` | Contenido de agua uniforme dentro de cada compartimento cuando se mueve el límite de la zona activa | Decisión del plan (T-6) | Siempre |
| `LINEAR_ROOT_GROWTH` | Raíces lineales desde Zr inicial (siembra) hasta Zr máxima al final de la etapa de desarrollo | Decisión del plan, aprobada el 2026-11-15 | Siempre que haya cultivo |
| `INITIAL_ROOT_DEPTH_TEAM` | Zr inicial de referencia de 0,25 m, decisión técnica del equipo; no es un valor de FAO-56 | Decisión del equipo AgroDSS (T-26) | Cuando el usuario no ingresa la Zr inicial |
| `TOP_DOWN_INFILTRATION` | La lluvia llena primero la zona activa y luego la inferior; solo se pierde con el perfil lleno | Decisión 9 del spec (T-9) | Siempre |
| `AVAILABLE_WATER_LIMITS` | La evaporación y la ETa no secan el suelo por debajo del PMP | Simplificación declarada | Siempre |
| `HUMIDITY_FROM_DEW_POINT` | ea a partir de T2MDEW | FAO-56, ec. 14 | Siempre |
| `SUBST_HUMIDITY_TMIN` | Si falta el punto de rocío, Tdew = Tmín − 2 °C (clima semiárido) | FAO-56, ec. 48 y anexo 6 | Al sustituir |
| `SUBST_RADIATION_HARGREAVES` | kRs = 0,16 (localidad interior); Rs limitada por Rso | FAO-56, ec. 50 | Al sustituir |
| `NO_KC_CLIMATE_ADJUSTMENT` | Kc medio y Kc final sin ajuste por humedad mínima ni viento | D-13 | Siempre |
| `WINDOW_START_DEFAULT` | La ventana empieza el 1 de julio | D-6 | Si se omite la fecha de inicio |
| `UNPUBLISHED_DATA_BLOCK` | Una racha final de datos faltantes se interpreta como «no publicado» y el escenario se bloquea | T-13 | Al bloquear |

**Códigos agregados al implementar T029 y T030** (derivados de CA-14.2, CA-14.3, CA-3.3, CA-3.4 y CA-6.6; sus textos están en `core/messages.py`): `RAINFED_NO_IRRIGATION`, `EXCESS_LOST`, `NO_CAPILLARY_RISE`, `INITIAL_MOISTURE_UNIFORM`, `INITIAL_MOISTURE_EACH_SCENARIO`, `FIXED_DEPTH_PROFILE`, `CONSTANT_PRICES_COSTS`, `PARAMETERS_NOT_CALIBRATED`, `CELL_SCALE_CLIMATE`, `FAO_REFERENCE_VALUE`, `USER_VALUE`, `ROOT_DEPTH_LIMITED`, `NO_RESIDUE_DECLARED`, `FALLOW_KC_BASE_DEFAULT`, `RESIDUE_NO_DECOMPOSITION`, `ET0_NEGATIVE_CLAMPED`, `YIELD_CLIPPED_TO_ZERO` y `SUBST_WIND_FAO56_DEFAULT` (viento medio faltante → 2 m/s, CA-6.6; FAO-56, cap. 3).

**Comportamiento agregado al spec:** un día con Tmáx < Tmín bloquea el escenario como «dato inconsistente de la fuente» (§7.3). Fue aprobado por el equipo e incorporado al spec como CA-6.10.

---

## 12. Riesgos y verificaciones previas a la implementación

| ID | Tipo | Descripción | Mitigación o acción |
|---|---|---|---|
| V-1 | Verificación (bloquea el parser) | Confirmar en la documentación de POWER: disponibilidad diaria AG de T2MDEW y WS2M_MAX; cadenas exactas de unidades; ubicación de `fill_value` y de la versión; inicio de cobertura por variable; parámetro `time-standard`; límites de parámetros y de rango por consulta | Tarea de lectura de la documentación oficial antes de `climate_parser.py`; actualizar `core/config.py` |
| V-2 | Verificación (bloquea el catálogo) | Cargar los valores de FAO-56 (tablas 11, 12 y 22) y de FAO-33 (Ky) con su cita exacta; confirmar si existen referencias para el centeno (D-14) | La hace el agrónomo del equipo; una prueba exige `source` para cada valor no nulo |
| V-3 | Verificación (pruebas) | Transcribir los datos de entrada y salida de los ejemplos 2, 8 y 18 de FAO-56 | Antes de escribir `test_et0` |
| R-1 | Riesgo | Años de inicio muy separados (por ejemplo, 1985 y 2022) generan una consulta de unos 40 años: respuesta pesada y riesgo de timeout | Timeout de lectura de 60 s; medir en la prueba manual; si hace falta, fijar un tramo máximo y documentarlo |
| R-2 | Riesgo (aceptado por C5) | Caída de NASA POWER o de internet durante la demo | Error claro y `retryable`; `GET /health` para comprobar el servicio; ensayar con conexión |
| R-3 | Riesgo | Límite de frecuencia de POWER | Una sola consulta por solicitud; 503 `power_rate_limited` |
| R-4 | Riesgo de interpretación | Simplificaciones (escorrentía, capa Ze, sin ajuste climático de Kc) | Todas declaradas como supuestos visibles |
| R-5 | Riesgo | El umbral WS2M_MAX > 8 m/s puede ser muy frecuente o muy raro en San Luis | Revisar la distribución en la prueba manual e informar al equipo, sin cambiar el umbral sin una decisión humana |

---

## 13. Orden de implementación sugerido

Cada paso termina con la lista de verificación de AGENTS: tests y ruff en verde, arranque sin errores e informe al equipo.

1. **Esqueleto:** `requirements.txt`, `pyproject.toml`, `main.py`, `core/config.py`, `GET /health` y prueba de importación.
2. **Dominio sin red:** `et0` (tras V-3), `calendar`, `kc_curve`, `root_growth`, `water_balance` y pruebas de invariantes. Es el núcleo científico y se valida primero.
3. **Dominio restante:** `yield_response`, `economics`, `wind_proxy`, `stats` y `missing_data`.
4. **Contrato y validación:** `models/*`, `services/validation`, `parameter_resolver` y catálogo (tras V-2), con `GET /catalog`.
5. **NASA POWER:** `power_client` y `climate_parser` (tras V-1), con pruebas de mocks.
6. **Orquestación:** `simulation_service`, `assumptions` y `response_builder`, con `POST /simulations`.
7. **Errores y contrato:** manejadores, instantánea de OpenAPI y pruebas no funcionales.
8. **Prueba manual en vivo**, informe y PR con la aprobación de httpx y la enmienda de la constitución.
