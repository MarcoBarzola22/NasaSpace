"""Calendario: fechas, ventanas de dos años, siembras y línea de tiempo (RF-3, RF-4; T013, T014).

Funciones puras sobre ``datetime.date``. Reglas del spec que se implementan aquí:

- La ventana de un escenario va del día de inicio del año Y al día anterior del año Y+2
  (730 o 731 días) y es común a todas las rotaciones (CA-4.2).
- La siembra se expresa como (año de la ventana 1 o 2, día, mes); la fecha de fin del ciclo es
  la siembra más la duración total menos un día (la siembra es el día 1 del ciclo, CA-3.5).
- El 29 de febrero no se acepta como fecha recurrente de inicio ni de siembra (CA-3.8, CA-4.3),
  porque no existe en todos los escenarios.
- Todo día de la ventana sin cultivo activo es barbecho (CA-3.11) y la línea de tiempo cubre
  cada día una sola vez (CA-8.2).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from app.core.exceptions import CalculationIntegrityError
from app.domain.types import (
    CropSegment,
    FallowSegment,
    RotationSpec,
    Segment,
    SowingSpec,
    Stages,
    Timeline,
    Window,
)

ISSUE_OVERLAP = "overlap"
ISSUE_OUTSIDE_WINDOW = "outside_window"

_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


@dataclass(frozen=True, slots=True)
class CalendarIssue:
    """Problema de calendario de una rotación en un escenario (CA-3.6, CA-3.7).

    ``crop_position`` es la posición (desde 1) del cultivo afectado. En un solapamiento,
    ``other_position`` es el cultivo anterior con el que coincide.
    """

    kind: str
    rotation_id: str
    start_year: int
    crop_position: int
    other_position: int | None = None


# --- Fechas básicas ---


def is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_month(year: int, month: int) -> int:
    if not 1 <= month <= 12:
        raise ValueError(f"El mes debe estar entre 1 y 12 (recibido: {month}).")
    if month == 2 and is_leap_year(year):
        return 29
    return _DAYS_IN_MONTH[month - 1]


def is_valid_date(year: int, month: int, day: int) -> bool:
    """Indica si (año, mes, día) es una fecha real del calendario."""
    return 1 <= month <= 12 and 1 <= day <= days_in_month(year, month)


def is_feb_29(day: int, month: int) -> bool:
    return month == 2 and day == 29


def validate_recurring_day_month(day: int, month: int) -> None:
    """Valida un día y mes que se repiten cada año; rechaza el 29 de febrero (CA-3.8, CA-4.3)."""
    if not 1 <= month <= 12:
        raise ValueError(f"El mes debe estar entre 1 y 12 (recibido: {month}).")
    if is_feb_29(day, month):
        raise ValueError("El 29 de febrero no es válido: no existe en todos los años.")
    # Se valida contra un año no bisiesto: una fecha recurrente debe existir todos los años.
    if not 1 <= day <= days_in_month(2001, month):
        raise ValueError(f"El día {day} no existe en el mes {month}.")


def day_of_year(day: date) -> int:
    """Día del año J (1 de enero = 1); el 31 de diciembre vale 365 o 366 si es bisiesto."""
    return (day - date(day.year, 1, 1)).days + 1


# --- Ventana, siembra y fin de ciclo ---


def build_window(start_year: int, start_day: int, start_month: int) -> Window:
    """Ventana de dos años que empieza el (día, mes) del año ``start_year`` (CA-4.2)."""
    validate_recurring_day_month(start_day, start_month)
    first_day = date(start_year, start_month, start_day)
    last_day = date(start_year + 2, start_month, start_day) - timedelta(days=1)
    return Window(start_year=start_year, first_day=first_day, last_day=last_day)


def sowing_date(window: Window, sowing: SowingSpec) -> date:
    """Fecha de siembra de un cultivo dentro de la ventana.

    El año 1 son los primeros doce meses desde el inicio de la ventana y el año 2, los
    siguientes. Si el (día, mes) de la siembra cae antes del inicio de ese año de la ventana,
    corresponde al año calendario siguiente.
    """
    if sowing.window_year not in (1, 2):
        raise ValueError("El año de la ventana de la siembra debe ser 1 o 2.")
    validate_recurring_day_month(sowing.day, sowing.month)
    window_year_start = date(
        window.start_year + sowing.window_year - 1,
        window.first_day.month,
        window.first_day.day,
    )
    candidate = date(window_year_start.year, sowing.month, sowing.day)
    if candidate < window_year_start:
        candidate = date(window_year_start.year + 1, sowing.month, sowing.day)
    return candidate


def cycle_end(sowing: date, stages: Stages) -> date:
    """Último día del ciclo: la siembra es el día 1 (CA-3.5)."""
    if stages.total_days < 1:
        raise ValueError("La duración total del ciclo debe ser de al menos 1 día.")
    return sowing + timedelta(days=stages.total_days - 1)


# --- Línea de tiempo y problemas de calendario ---


def _cycles(window: Window, rotation: RotationSpec) -> list[tuple[date, date]]:
    """(siembra, fin de ciclo) de cada cultivo de la rotación, en el orden dado."""
    cycles = []
    for crop in rotation.crops:
        start = sowing_date(window, crop.sowing)
        cycles.append((start, cycle_end(start, crop.stages)))
    return cycles


def _issues_in_window(rotation: RotationSpec, window: Window) -> list[CalendarIssue]:
    return issues_for_cycles(rotation.rotation_id, _cycles(window, rotation), window)


def issues_for_cycles(
    rotation_id: str, cycles: list[tuple[date, date]], window: Window
) -> list[CalendarIssue]:
    """Solapamientos y salidas de la ventana a partir de los (siembra, fin) de cada cultivo.

    La validación de la solicitud usa esta misma función antes de tener los parámetros completos
    del cultivo, de modo que el rechazo y el cálculo aplican exactamente la misma regla.
    """
    issues: list[CalendarIssue] = []
    for index, (start, end) in enumerate(cycles):
        position = index + 1
        if index > 0 and start <= cycles[index - 1][1]:
            issues.append(
                CalendarIssue(ISSUE_OVERLAP, rotation_id, window.start_year, position, position - 1)
            )
        if start < window.first_day or end > window.last_day:
            issues.append(
                CalendarIssue(ISSUE_OUTSIDE_WINDOW, rotation_id, window.start_year, position)
            )
    return issues


def calendar_issues(
    rotation: RotationSpec, start_years: Iterable[int], start_day: int, start_month: int
) -> list[CalendarIssue]:
    """Problemas de calendario de la rotación en cada escenario, solo en los años afectados.

    Como el fin de un ciclo cambia un día según incluya o no un 29 de febrero, un solapamiento
    o una salida de la ventana pueden darse solo en algunos escenarios (CL-4, CL-5).
    """
    issues: list[CalendarIssue] = []
    for start_year in start_years:
        window = build_window(start_year, start_day, start_month)
        issues.extend(_issues_in_window(rotation, window))
    return issues


def build_timeline(window: Window, rotation: RotationSpec) -> Timeline:
    """Segmentos consecutivos (barbecho y cultivos) que cubren la ventana completa."""
    if _issues_in_window(rotation, window):
        raise ValueError("La rotación se solapa o sale de la ventana: no se puede armar la línea.")
    segments: list[Segment] = []
    cursor = window.first_day
    residue_cover_pct = rotation.initial_residue_cover_pct
    for crop, (start, end) in zip(rotation.crops, _cycles(window, rotation), strict=True):
        if start > cursor:
            segments.append(FallowSegment(cursor, start - timedelta(days=1), residue_cover_pct))
        segments.append(CropSegment(crop, start, end))
        cursor = end + timedelta(days=1)
        residue_cover_pct = crop.residue_cover_after_pct
    if cursor <= window.last_day:
        segments.append(FallowSegment(cursor, window.last_day, residue_cover_pct))
    timeline = Timeline(tuple(segments))
    _check_continuity(timeline, window)
    return timeline


def _check_continuity(timeline: Timeline, window: Window) -> None:
    """Cada día de la ventana pertenece a un solo segmento, sin huecos (CA-8.2)."""
    expected = window.first_day
    for segment in timeline.segments:
        if segment.start != expected or segment.end < segment.start:
            raise CalculationIntegrityError(
                f"La línea de tiempo no es continua en {segment.start} (se esperaba {expected})."
            )
        expected = segment.end + timedelta(days=1)
    if expected != window.last_day + timedelta(days=1) or timeline.n_days != window.n_days:
        raise CalculationIntegrityError("La línea de tiempo no cubre toda la ventana.")
