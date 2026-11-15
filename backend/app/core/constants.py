"""Constantes físicas y de modelo aprobadas por el equipo (T006).

Cada valor tiene su origen en el spec, el plan o las verificaciones de ``research.md``.
Las constantes de configuración de la fuente (variables, cobertura, timeouts) están en
``app.core.config``. Este módulo no importa nada del proyecto, para que ``domain`` pueda usarlo.
"""

from __future__ import annotations

from typing import Final

# --- Proxy de viento fuerte (RF-11, decisión 10 del spec, revisión 3) ---
WIND_STRONG_VARIABLE: Final = "WS2M_MAX"
WIND_STRONG_THRESHOLD_MS: Final = 8.0  # día fuerte: estrictamente mayor que el umbral

# --- Barbecho y rastrojo (RF-8, decisión 8 del spec) ---
FALLOW_KC_BASE_DEFAULT: Final = 0.20
FALLOW_EVAPORATION_LAYER_M: Final = 0.15  # capa evaporable Ze (plan, T-7)
RESIDUE_EVAPORATION_REDUCTION_PER_10PCT: Final = 0.05  # FAO-56, acolchados orgánicos

# --- Profundidad radicular inicial de referencia (plan, decisión T-26) ---
DEFAULT_INITIAL_ROOT_DEPTH_M: Final = 0.25

# --- Controles de conservación de masa (RF-8) ---
MASS_CLOSURE_TOLERANCE_MM: Final = 0.01
DAILY_EPSILON_MM: Final = 1e-9

# --- Sustituciones y parámetros de FAO-56 (RF-6, RF-7) ---
HARGREAVES_KRS: Final = 0.16  # localidad interior, FAO-56 ec. 50
DEW_POINT_SEMIARID_OFFSET_C: Final = 2.0  # Tdew = Tmín − 2 °C (clima semiárido)
DEFAULT_WIND_2M_MS: Final = 2.0  # valor provisional de FAO-56
ALBEDO: Final = 0.23
STEFAN_BOLTZMANN_MJ_K4_M2_DAY: Final = 4.903e-9
KELVIN_OFFSET: Final = 273.16  # FAO-56 en Rnl (research.md, V-3)

# --- Límites de validación (RF-1, RF-3, RF-4, RF-10) ---
MAX_ROTATIONS: Final = 3
MAX_START_YEARS: Final = 10
MAX_EFFECTIVE_DEPTH_M: Final = 3.0
MAX_KC: Final = 2.0
MAX_KY: Final = 2.0
MAX_YM_T_HA: Final = 30.0
MAX_STAGE_DAYS: Final = 365
MAX_FALLOW_KC_BASE: Final = 1.0
MAX_ABS_LATITUDE_DEG: Final = 60.0  # CA-1.12: evita latitudes polares (Rso puede ser 0)

# --- Ventana por defecto (D-6): 1 de julio ---
DEFAULT_WINDOW_START_DAY: Final = 1
DEFAULT_WINDOW_START_MONTH: Final = 7

# --- Caja aproximada de San Luis (D-9); a verificar ---
SAN_LUIS_LAT_MIN_DEG: Final = -36.0
SAN_LUIS_LAT_MAX_DEG: Final = -31.8
SAN_LUIS_LON_MIN_DEG: Final = -67.6
SAN_LUIS_LON_MAX_DEG: Final = -64.8

# --- Versiones (CA-13.3, CA-15.6) ---
CONTRACT_VERSION: Final = "1.0"
MODEL_VERSION: Final = "0.1.0"
