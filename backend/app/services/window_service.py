"""Resolución de la ventana histórica: qué años de inicio se simulan (RF-4; T032 del pedido).

El usuario puede elegir los años de tres maneras:

- ``LastYears(n)``: los ``n`` años de inicio más recientes cuya ventana ya terminó;
- ``SpecificYears(years)``: años elegidos uno por uno;
- ``AllRecord()``: todos los años de inicio posibles, desde el inicio de cobertura de la fuente.

Reglas que se aplican (spec, RF-4):

- La ventana de un año de inicio Y va del día de inicio de Y al día anterior del de Y+2 (CA-4.2).
- Una ventana debe **terminar antes de hoy** (CA-4.4). Como la ventana de Y termina en Y+2, esto
  deja fuera el año en curso y el anterior (según la fecha de inicio): nunca hay escenarios
  incompletos. La fecha de «hoy» se recibe como parámetro para poder fijar el reloj en pruebas.
- Los años que generan ``LastYears`` y ``AllRecord`` empiezan en o después del inicio de cobertura
  de **todas** las variables (la radiación, 1984-01-01): así ningún escenario nace bloqueado.
- Un año **elegido** antes del inicio de cobertura no se descarta: el spec pide bloquear ese
  escenario con su motivo y seguir con los demás (CA-4.5). Aquí solo se informa en
  ``outside_coverage``; el bloqueo lo hace el servicio de simulación.
- Los años con ventanas superpuestas son válidos (CA-4.7).

Este servicio no consulta NASA POWER ni lee archivos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.core.config import Settings
from app.core.constants import (
    DEFAULT_WINDOW_START_DAY,
    DEFAULT_WINDOW_START_MONTH,
    MAX_START_YEARS,
)
from app.domain.calendar import build_window

REASON_ENDS_AFTER_TODAY = "window_ends_after_today"


@dataclass(frozen=True, slots=True)
class LastYears:
    """Los ``n`` años de inicio más recientes con ventana completa."""

    n: int


@dataclass(frozen=True, slots=True)
class SpecificYears:
    """Años de inicio elegidos por el usuario."""

    years: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class AllRecord:
    """Todos los años de inicio posibles con la cobertura disponible."""


WindowSelection = LastYears | SpecificYears | AllRecord


@dataclass(frozen=True, slots=True)
class RejectedYear:
    year: int
    reason: str
    window_last_day: date


@dataclass(frozen=True, slots=True)
class WindowResolution:
    """Resultado de resolver la selección de años.

    ``start_years`` son los años a simular, en orden creciente y sin repetidos. ``rejected`` son
    los años elegidos cuya ventana termina después de hoy (CA-4.4). ``outside_coverage`` son los
    años que empiezan antes de la cobertura de la fuente y que se bloquearán como escenario
    (CA-4.5). ``duplicates`` son los años elegidos más de una vez (CA-4.3).
    """

    start_years: tuple[int, ...]
    rejected: tuple[RejectedYear, ...] = ()
    outside_coverage: tuple[int, ...] = ()
    duplicates: tuple[int, ...] = ()

    @property
    def exceeds_limit(self) -> bool:
        """Más años que el máximo por solicitud (CA-4.3)."""
        return len(self.start_years) > MAX_START_YEARS


def utc_today() -> date:
    """Fecha actual en UTC (CA-4.4 usa la fecha del servidor, no la del navegador)."""
    return datetime.now(UTC).date()


def coverage_start(settings: Settings) -> date:
    """Primer día en que **todas** las variables requeridas tienen datos (V-1: 1984-01-01)."""
    return max(settings.variable_coverage_start.values())


def window_ends_before(start_year: int, start_day: int, start_month: int, today: date) -> bool:
    """La ventana del año de inicio termina estrictamente antes de ``today`` (CA-4.4)."""
    return build_window(start_year, start_day, start_month).last_day < today


def eligible_start_years(
    *,
    today: date,
    first_covered_day: date,
    start_day: int = DEFAULT_WINDOW_START_DAY,
    start_month: int = DEFAULT_WINDOW_START_MONTH,
) -> tuple[int, ...]:
    """Años de inicio con la ventana completa dentro de la cobertura y ya terminada.

    Es el rango continuo que va del primer año cuya ventana empieza en o después de
    ``first_covered_day`` hasta el último año cuya ventana termina antes de ``today``.
    """
    # Se parte del año de ``first_covered_day`` (o del siguiente, si su ventana empezaría antes)
    # y se avanza mientras la ventana termine antes de hoy; así no se asume ningún año fijo.
    first_year = first_covered_day.year
    if build_window(first_year, start_day, start_month).first_day < first_covered_day:
        first_year += 1
    years: list[int] = []
    year = first_year
    while window_ends_before(year, start_day, start_month, today):
        years.append(year)
        year += 1
    return tuple(years)


def resolve_window(
    selection: WindowSelection,
    *,
    today: date,
    first_covered_day: date,
    start_day: int = DEFAULT_WINDOW_START_DAY,
    start_month: int = DEFAULT_WINDOW_START_MONTH,
) -> WindowResolution:
    """Convierte la selección de años en la lista de años de inicio a simular.

    Lanza ``ValueError`` si ``LastYears.n`` no está entre 1 y el máximo por solicitud, o si la
    fecha de inicio no es válida (por ejemplo, el 29 de febrero). Un año elegido con ventana que
    termina después de hoy no lanza: se informa en ``rejected`` para que la validación de la
    solicitud lo reúna con los demás errores (CA-16.1).
    """
    eligible = eligible_start_years(
        today=today,
        first_covered_day=first_covered_day,
        start_day=start_day,
        start_month=start_month,
    )
    if isinstance(selection, LastYears):
        if not 1 <= selection.n <= MAX_START_YEARS:
            raise ValueError(f"Los últimos N años deben ser entre 1 y {MAX_START_YEARS}.")
        return WindowResolution(start_years=eligible[-selection.n :])
    if isinstance(selection, AllRecord):
        return WindowResolution(start_years=eligible)
    return _resolve_specific(selection, today, first_covered_day, start_day, start_month)


def _resolve_specific(
    selection: SpecificYears,
    today: date,
    first_covered_day: date,
    start_day: int,
    start_month: int,
) -> WindowResolution:
    seen: set[int] = set()
    duplicates: list[int] = []
    for year in selection.years:
        if year in seen and year not in duplicates:
            duplicates.append(year)
        seen.add(year)

    accepted: list[int] = []
    rejected: list[RejectedYear] = []
    outside_coverage: list[int] = []
    for year in sorted(seen):
        window = build_window(year, start_day, start_month)
        if window.last_day >= today:
            rejected.append(RejectedYear(year, REASON_ENDS_AFTER_TODAY, window.last_day))
            continue
        accepted.append(year)
        if window.first_day < first_covered_day:
            outside_coverage.append(year)
    return WindowResolution(
        start_years=tuple(accepted),
        rejected=tuple(rejected),
        outside_coverage=tuple(outside_coverage),
        duplicates=tuple(sorted(duplicates)),
    )


def power_query_range(
    start_years: tuple[int, ...] | list[int],
    start_day: int,
    start_month: int,
    *,
    not_before: date | None = None,
) -> tuple[date, date]:
    """Primer y último día que cubre la consulta única a NASA POWER (CA-5.1).

    Va del primer día de la ventana más temprana al último de la más tardía. Si se indica
    ``not_before`` (inicio de cobertura de la radiación), la consulta no pide fechas anteriores:
    con todo el rango antes de 1984 POWER omitiría la radiación y la respuesta parecería
    defectuosa (research.md V-1, O-1). Los escenarios previos a esa fecha se bloquean aparte.
    """
    if not start_years:
        raise ValueError("Se necesita al menos un año de inicio.")
    first = build_window(min(start_years), start_day, start_month).first_day
    last = build_window(max(start_years), start_day, start_month).last_day
    if not_before is not None:
        first = max(first, not_before)
    if last < first:
        raise ValueError("Ninguna ventana queda dentro del período cubierto por la fuente.")
    return first, last
