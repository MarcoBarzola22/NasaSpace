"""Textos visibles para el usuario, en español, en un solo lugar (RF-17, RF-16; T029).

Reglas (CA-16.6, CA-17.1, CA-17.5, CA-10.7):

- Todo texto que ve el usuario está aquí o, para los textos de dominio puro, en una constante
  ``NOTE_*`` de ``app.domain`` (el dominio no puede importar este módulo). Los identificadores
  técnicos del contrato (códigos, claves) van en inglés.
- Ningún texto contiene «pérdida neta», «probabilidad», «precisión», «recomendada», «óptima» ni
  «mejor». La única excepción es el rótulo literal de los rangos exigido por CA-12.5, que niega
  la probabilidad: sus frases están en ``ALLOWED_PHRASES`` y la prueba de lenguaje las admite
  solo textualmente.
- Las plantillas usan ``str.format`` con campos con nombre.

La prueba ``tests/nonfunctional/test_language.py`` recorre todo este módulo.
"""

from __future__ import annotations

from typing import Final

# Términos que ningún texto puede contener (sin distinguir mayúsculas); ver CA-17.1 y CA-17.5.
FORBIDDEN_TERMS: Final[tuple[str, ...]] = (
    "pérdida neta",
    "probabilidad",
    "precisión",
    "recomendada",
    "óptima",
    "mejor",
)

# Frases que el spec exige literalmente y que contienen un término prohibido.
ALLOWED_PHRASES: Final[tuple[str, ...]] = ("no es una probabilidad ni un pronóstico",)

# --- Rótulos exigidos por el spec ---

RANGE_LABEL: Final = (
    "rango descriptivo de los años elegidos; no es una probabilidad ni un pronóstico"  # CA-12.5
)
# CA-13.2
CELL_SCALE_LABEL: Final = (
    "dato de modelo/reanálisis de NASA POWER a escala de celda; no es una medición del lote"
)
WIND_VARIABLE_LABEL: Final = "Máximo de los valores horarios del día a 2 m (WS2M_MAX)"  # CA-11.5
WIND_THRESHOLD_SOURCE: Final = (
    "decisión del equipo AgroDSS, revisión 3; no calibrado para erosión local"  # CA-11.5
)

# --- Advertencias de interpretación (RF-17, RF-13, RF-16) ---

WARNINGS: Final[dict[str, str]] = {
    "HISTORICAL_DESCRIPTIVE": (
        "Escenarios históricos descriptivos: muestran cómo se habría comportado cada rotación "
        "con el clima de los años elegidos; no son pronósticos"
    ),
    "UNCALIBRATED_PARAMETERS": (
        "Kc, Ky, Ym y los parámetros de suelo son entradas o valores de referencia no "
        "calibrados para el lote."
    ),
    "CELL_SCALE_DATA": CELL_SCALE_LABEL,
    "NOT_A_RECOMMENDATION": (
        "AgroDSS compara escenarios para apoyar la decisión del agrónomo: no ordena las "
        "rotaciones ni indica cuál conviene. El modelo solo representa el agua del suelo; no "
        "incluye nitrógeno, malezas, enfermedades, erosión ni carbono."
    ),
    "SUBSTITUTIONS_PRESENT": (
        "Hubo días con datos faltantes de la fuente que se estimaron con procedimientos de "
        "FAO-56 solo para calcular la ET₀; el detalle está en los supuestos."
    ),
    "SCENARIOS_BLOCKED": (
        "Uno o más escenarios no se calcularon por datos insuficientes de la fuente; cada uno "
        "indica su motivo."
    ),
    "OUTSIDE_SAN_LUIS": (
        "Las coordenadas están fuera de la provincia de San Luis; los valores de referencia y "
        "el modelo están pensados para esa región."
    ),
}

# --- Supuestos (RF-14): descripción por código ---

ASSUMPTION_DESCRIPTIONS: Final[dict[str, str]] = {
    # Siempre presentes (CA-14.2 y plan §11)
    "RAINFED_NO_IRRIGATION": "Secano: el riego es 0 todos los días.",
    "TOP_DOWN_INFILTRATION": (
        "Toda la lluvia infiltra: llena primero la zona de raíces y luego el resto del perfil, "
        "sin escorrentía por intensidad."
    ),
    "EXCESS_LOST": (
        "El agua que supera la capacidad del perfil se pierde ese mismo día, sin distinguir "
        "escorrentía de percolación."
    ),
    "NO_CAPILLARY_RISE": "No hay ascenso capilar desde una napa: ese aporte es 0.",
    "INITIAL_MOISTURE_UNIFORM": (
        "La humedad inicial se reparte de manera uniforme en todo el perfil el primer día de la "
        "ventana."
    ),
    "INITIAL_MOISTURE_EACH_SCENARIO": (
        "La humedad inicial ingresada se aplica al primer día de cada escenario; no se arrastra "
        "el estado final de otro escenario."
    ),
    "FIXED_DEPTH_PROFILE": "El perfil de suelo tiene una profundidad fija durante toda la ventana.",
    "CONSTANT_PRICES_COSTS": (
        "Los precios y costos ingresados por el usuario son constantes durante toda la ventana."
    ),
    "PARAMETERS_NOT_CALIBRATED": "Los parámetros del cultivo y del suelo no están calibrados.",
    "CELL_SCALE_CLIMATE": (
        "El clima es un dato de celda de NASA POWER (modelo/reanálisis), no una medición del lote."
    ),
    "UNIFORM_REDISTRIBUTION": (
        "El contenido de agua es uniforme dentro de cada compartimento cuando se mueve el "
        "límite de la zona de raíces."
    ),
    "LINEAR_ROOT_GROWTH": (
        "Las raíces crecen en forma lineal desde la profundidad inicial, en la siembra, hasta "
        "la máxima, al final de la etapa de desarrollo."
    ),
    "AVAILABLE_WATER_LIMITS": (
        "La evaporación y la ETa no secan el suelo por debajo del punto de marchitez permanente."
    ),
    "HUMIDITY_FROM_DEW_POINT": (
        "La presión real de vapor se calcula a partir del punto de rocío a 2 m (T2MDEW)."
    ),
    "NO_KC_CLIMATE_ADJUSTMENT": "Los Kc medio y final se usan sin ajuste por humedad ni viento.",
    # Cuando ocurren (CA-14.3, CA-3.3, CA-3.4, CA-4.3 y plan §11)
    "FALLOW_EVAPORATION_LAYER": (
        "En barbecho, la evaporación sale solo de una capa superficial de 0,15 m."
    ),
    "INITIAL_ROOT_DEPTH_TEAM": (
        "Profundidad radicular inicial de referencia de 0,25 m, decisión técnica del equipo; no "
        "es un valor de FAO-56."
    ),
    "SUBST_HUMIDITY_TMIN": (
        "Si falta el punto de rocío, se estima como Tmín − 2 °C (clima semiárido) solo para la "
        "ET₀."
    ),
    "SUBST_RADIATION_HARGREAVES": (
        "Si falta la radiación solar, se estima con la fórmula de Hargreaves (kRs = 0,16), "
        "limitada por la radiación de cielo despejado, solo para la ET₀."
    ),
    "SUBST_WIND_FAO56_DEFAULT": (
        "Si falta el viento medio a 2 m, se usa 2 m/s (valor provisional de FAO-56) solo para "
        "la ET₀."
    ),
    "WINDOW_START_DEFAULT": (
        "La ventana empieza el 1 de julio porque no se indicó otra fecha de inicio."
    ),
    "UNPUBLISHED_DATA_BLOCK": (
        "Una racha final de datos faltantes se interpreta como «aún no publicado» y el "
        "escenario se bloquea."
    ),
    "FAO_REFERENCE_VALUE": "Valor tabulado FAO, no calibrado para el lote.",
    "TEAM_REFERENCE_VALUE": (
        "Valor de referencia definido por el equipo AgroDSS, no calibrado para el lote."
    ),
    "USER_VALUE": "Valor ingresado por el usuario; no está calibrado para el lote.",
    "ROOT_DEPTH_LIMITED": "La profundidad radicular se limitó a la profundidad efectiva.",
    "NO_RESIDUE_DECLARED": (
        "No se declaró rastrojo: se usa 0 % (sin reducción de la evaporación del barbecho)."
    ),
    "FALLOW_KC_BASE_DEFAULT": (
        "Kc base de barbecho definido por el equipo AgroDSS (rango 0,15–0,20); no es un valor "
        "tabulado único de FAO-56"
    ),
    "RESIDUE_NO_DECOMPOSITION": "El rastrojo declarado se mantiene constante, sin descomposición.",
    "ET0_NEGATIVE_CLAMPED": "Una ET₀ calculada negativa se llevó a 0 ese día.",
    "YIELD_CLIPPED_TO_ZERO": "Un rendimiento calculado por FAO-33 negativo se llevó a 0.",
}

# Citas de cada supuesto (CA-14.1: origen con cita). Los que no figuran no tienen cita externa.
ASSUMPTION_SOURCES: Final[dict[str, str]] = {
    "HUMIDITY_FROM_DEW_POINT": "FAO-56, ec. 14",
    "FALLOW_EVAPORATION_LAYER": "FAO-56, cap. 7 (Ze 0,10–0,15 m)",
    "SUBST_HUMIDITY_TMIN": "FAO-56, ec. 48 y anexo 6",
    "SUBST_RADIATION_HARGREAVES": "FAO-56, ec. 50",
    "UNIFORM_REDISTRIBUTION": "Decisión del plan (T-6)",
    "LINEAR_ROOT_GROWTH": "Decisión del plan, aprobada el 2026-11-15",
    "INITIAL_ROOT_DEPTH_TEAM": "Decisión del equipo AgroDSS (T-26)",
    "TOP_DOWN_INFILTRATION": "Decisión 9 del spec (T-9)",
    "NO_KC_CLIMATE_ADJUSTMENT": "Decisión D-13 del spec",
    "WINDOW_START_DEFAULT": "Decisión D-6 del spec",
    "UNPUBLISHED_DATA_BLOCK": "Decisión T-13 del plan",
    "SUBST_WIND_FAO56_DEFAULT": "FAO-56, cap. 3 (viento provisional de 2 m/s)",
}

# --- Motivos de bloqueo de escenarios (RF-4, RF-6) ---

BLOCK_REASONS: Final[dict[str, str]] = {
    "MISSING_PRECIPITATION": (
        "Falta la precipitación diaria (PRECTOTCORR) de NASA POWER en las fechas indicadas; sin "
        "ella no se puede calcular el balance hídrico."
    ),
    "MISSING_TMAX": (
        "Falta la temperatura máxima diaria (T2M_MAX) de NASA POWER en las fechas indicadas; "
        "sin ella no se puede calcular la ET₀."
    ),
    "MISSING_TMIN": (
        "Falta la temperatura mínima diaria (T2M_MIN) de NASA POWER en las fechas indicadas; "
        "sin ella no se puede calcular la ET₀."
    ),
    "INCONSISTENT_SOURCE_DATA": (
        "Dato inconsistente de la fuente: la temperatura máxima es menor que la mínima en las "
        "fechas indicadas."
    ),
    "UNPUBLISHED_DATA_BLOCK": (
        "La ventana incluye días que NASA POWER todavía no publicó para la variable indicada."
    ),
    "BEFORE_SOURCE_COVERAGE": (
        "La ventana empieza antes del período que NASA POWER cubre para la variable indicada."
    ),
}

# --- Errores de la API (plan §6.4) ---

INPUT_INVALID: Final = (
    "La solicitud tiene datos inválidos. Corrija los campos indicados y vuelva a enviarla."
)
IRRIGATION_NOT_SUPPORTED: Final = "El MVP solo evalúa secano; no se admiten datos de riego."
POWER_UNREACHABLE: Final = (
    "No se pudo conectar con NASA POWER. Verifique la conexión a internet y reintente. "
    "No se calculó ningún escenario."
)
POWER_TIMEOUT: Final = (
    "NASA POWER no respondió dentro de {seconds:g} s. No se calculó ningún escenario. "
    "Reintente en unos minutos."
)
POWER_RATE_LIMITED: Final = (
    "NASA POWER rechazó temporalmente la consulta por exceso de pedidos. Reintente más tarde."
)
POWER_BAD_STATUS: Final = "NASA POWER devolvió un error ({status}). No se calculó ningún escenario."
POWER_BAD_FORMAT: Final = (
    "NASA POWER devolvió una respuesta incompleta o con formato inesperado. "
    "No se calculó ningún escenario."
)
CALCULATION_INTEGRITY: Final = (
    "Error interno de cálculo: un control de consistencia falló y no se entregan resultados. "
    "Informe el código de solicitud al equipo."
)
UNEXPECTED_ERROR: Final = "Error interno inesperado. Informe el código de solicitud al equipo."

# --- Validación semántica de la solicitud (services/validation.py) ---

PARAMETER_LABELS: Final[dict[str, str]] = {
    "kc_initial": "Kc inicial",
    "kc_mid": "Kc medio",
    "kc_end": "Kc final",
    "root_depth_initial_m": "profundidad radicular inicial",
    "root_depth_max_m": "profundidad radicular máxima",
    "depletion_fraction_p": "fracción de agotamiento p",
    "stage_lengths_days": "duración de las cuatro etapas",
    "ky": "Ky",
}
COVER_FORBIDDEN_LABELS: Final[dict[str, str]] = {
    "ym_t_ha": "el rendimiento potencial Ym",
    "ky": "el factor de respuesta Ky",
    "economics.price_per_t": "el precio",
}

SCENARIO_ONE: Final = "el escenario {year}"
SCENARIO_MANY: Final = "los escenarios {years}"

LATITUDE_OUT_OF_RANGE: Final = (
    "La latitud {latitude:g}° está fuera de [−{limit:g}°, {limit:g}°]: el MVP está pensado "
    "para San Luis (Argentina)."
)
THETA_INCOHERENT: Final = (
    "El punto de marchitez permanente (θPMP) debe ser menor que la capacidad de campo (θCC): "
    "se recibió θPMP = {theta_wp:g} y θCC = {theta_fc:g}."
)
DUPLICATE_YEARS: Final = "Los años de inicio deben ser distintos; se repite: {years}."
WINDOW_ENDS_AFTER_TODAY: Final = (
    "La ventana del año {year} termina el {last_day:%d-%m-%Y}, después de hoy: solo se pueden "
    "simular años con la ventana de dos años completa."
)
DUPLICATE_ROTATION: Final = (
    "La rotación {rotation_id} está repetida: use A, B y C una sola vez cada una."
)
UNKNOWN_CROP: Final = "El cultivo «{crop_code}» no existe en el catálogo. Opciones: {options}."
YM_REQUIRED: Final = "Un cultivo de grano necesita el rendimiento potencial Ym (t/ha), mayor que 0."
FORBIDDEN_FOR_COVER: Final = (
    "Un cultivo de cobertura no lleva {label}; quítelo (solo admite costos directos)."
)
MISSING_REFERENCE: Final = (
    "No hay valor de referencia publicado para la {label} de «{crop_code}»: ingréselo."
)
ROOT_DEPTH_ORDER: Final = (
    "La profundidad radicular inicial ({initial:g} m) no puede superar la máxima ({maximum:g} m)."
)
CURRENCY_REQUIRED: Final = (
    "Indique la moneda (código de 3 letras, por ejemplo USD) para los precios y costos."
)
CALENDAR_OVERLAP: Final = (
    "En la rotación {rotation_id}, el cultivo {position} ({crop_code}) se solapa con el cultivo "
    "{other_position} ({other_code}) en {years}. Ajuste la fecha de siembra o la duración del "
    "ciclo."
)
CALENDAR_OUTSIDE_WINDOW: Final = (
    "En la rotación {rotation_id}, el ciclo del cultivo {position} ({crop_code}) empieza antes o "
    "termina después de la ventana de dos años en {years}. Ajuste la fecha de siembra o la "
    "duración."
)

# --- Catálogo de cultivos (services/catalog_service.py) ---

CATALOG_INVALID: Final = "Catálogo de cultivos inválido: {problems}"
CATALOG_UNREADABLE: Final = "no se pudo leer {file}: {error}"
CATALOG_ROOT_NOT_OBJECT: Final = "la raíz del catálogo debe ser un objeto"
CATALOG_MISSING_FIELD: Final = "falta el campo «{key}»"
CATALOG_CROPS_EMPTY: Final = "«crops» debe ser una lista con al menos un cultivo"
CATALOG_DUPLICATE_CROP: Final = "cultivo repetido: {crop_code}"
CATALOG_CROP_NOT_OBJECT: Final = "cada cultivo debe ser un objeto con «crop_code»"
CATALOG_CROP_NAME_MISSING: Final = "{crop_code}: falta el nombre"
CATALOG_CROP_TYPE_INVALID: Final = "{crop_code}: «crop_type» debe ser «grain» o «cover»"
CATALOG_VALUES_MISSING: Final = "{crop_code}: faltan los valores de referencia"
CATALOG_PARAMETER_NOT_ALLOWED: Final = (
    "{crop_code}.{parameter}: parámetro no permitido en el catálogo"
)
CATALOG_PARAMETER_MISSING: Final = "{crop_code}.{parameter}: falta el parámetro"
CATALOG_VALUE_NOT_OBJECT: Final = "{where}: debe ser un objeto"
CATALOG_EMPTY_STATUS_HAS_VALUE: Final = (
    "{where}: con estado «{status}» no debe haber valor, origen ni cita"
)
CATALOG_NO_SOURCE: Final = "{where}: el valor no tiene cita («source» vacío)"
CATALOG_WRONG_ORIGIN: Final = "{where}: el origen de «{status}» debe ser «{expected}»"
CATALOG_UNKNOWN_STATUS: Final = "{where}: estado desconocido «{status}»"
CATALOG_VALUE_ISSUE: Final = "{where}: {issue}"
CATALOG_STAGES_NOT_FOUR: Final = "las duraciones deben tener exactamente las 4 etapas"
CATALOG_STAGE_DAYS_INVALID: Final = "cada duración debe ser un entero de 1 día o más"
CATALOG_VALUE_NOT_NUMBER: Final = "el valor debe ser numérico"
CATALOG_NEGATIVE: Final = "no puede ser negativo"
CATALOG_NOT_POSITIVE: Final = "debe ser mayor que 0"
CATALOG_FRACTION_RANGE: Final = "debe estar entre 0 y 1 (sin incluirlos)"
CATALOG_COVER_HAS_KY: Final = "{crop_code}.ky: un cultivo de cobertura no lleva Ky («no aplica»)"
CATALOG_GRAIN_NEEDS_KY: Final = "{crop_code}.ky: un cultivo de grano necesita Ky o «sin referencia»"
CATALOG_ROOT_DEPTH_ORDER: Final = "{crop_code}: la Zr inicial no puede superar la Zr máxima"

# --- Parámetros resueltos y procedencia (services/parameter_resolver.py, climate_parser.py) ---

FALLOW_KC_SOURCE: Final = (
    "decisión del equipo AgroDSS (rango 0,15–0,20); no es un valor tabulado único de FAO-56"
)
FALLOW_EVAPORATION_LAYER_SOURCE: Final = "FAO-56, cap. 7 (capa evaporable Ze 0,10–0,15 m)"
NOTE_FAO_REFERENCE: Final = "Valor tabulado FAO, no calibrado para el lote."
NOTE_TEAM_REFERENCE: Final = (
    "Valor de referencia definido por el equipo AgroDSS, no calibrado para el lote."
)
NOTE_ROOT_DEPTH_LIMITED: Final = (
    "Limitada a la profundidad efectiva ({origin_label}: {original:g} m)."
)
ORIGIN_LABEL_USER: Final = "valor ingresado"
ORIGIN_LABEL_REFERENCE: Final = "valor de referencia"
WINDOW_START_DEFAULT_VALUE: Final = "1 de julio"

PROVENANCE_SOURCE: Final = "NASA POWER"
PROVENANCE_SERVICE: Final = "API diaria de punto, comunidad {community}"
PROVENANCE_RETRIEVAL: Final = "Consulta en vivo"
PROVENANCE_SPATIAL_NOTE: Final = (
    "El dato representa una celda de varios kilómetros (resolución nativa según la "
    "documentación de POWER), no el lote."
)

# Nombre, unidad legible y uso de cada variable de NASA POWER (CA-13.1).
POWER_VARIABLE_INFO: Final[dict[str, tuple[str, str, str]]] = {
    "PRECTOTCORR": ("Precipitación corregida", "mm/día", "Balance hídrico"),
    "T2M_MAX": ("Temperatura máxima a 2 m", "°C", "ET₀"),
    "T2M_MIN": ("Temperatura mínima a 2 m", "°C", "ET₀"),
    "T2MDEW": ("Punto de rocío a 2 m", "°C", "ET₀"),
    "WS2M": ("Velocidad media diaria del viento a 2 m", "m/s", "ET₀"),
    "WS2M_MAX": ("Velocidad máxima diaria del viento a 2 m", "m/s", "Proxy de viento fuerte"),
    "ALLSKY_SFC_SW_DWN": ("Radiación solar global en superficie", "MJ/m²/día", "ET₀"),
}
