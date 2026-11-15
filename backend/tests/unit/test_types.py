"""Pruebas de los tipos del dominio (T008).

Criterios que respaldan: CA-3.5 (duración del ciclo), CA-4.2 (ventana de 730 o 731 días),
CA-6.1 (un dato faltante es ``None``, no se rellena) y CA-8.2 (línea de tiempo continua).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import date

import pytest

from app.domain import types as t

CROP = t.CropSpec(
    crop_code="maize",
    crop_type="grain",
    sowing=t.SowingSpec(window_year=1, day=15, month=10),
    stages=t.Stages(initial=25, development=40, mid=45, late=30),
    kc_initial=0.30,
    kc_mid=1.20,
    kc_end=0.35,
    root_depth_initial_m=0.25,
    root_depth_max_m=1.2,
    depletion_fraction_p=0.55,
    ky=1.25,
    ym_t_ha=9.0,
)


def test_all_domain_types_exist() -> None:
    names = [
        "Stages",
        "SowingSpec",
        "CropSpec",
        "RotationSpec",
        "ParcelSpec",
        "Window",
        "DailyClimate",
        "Weather",
        "CropSegment",
        "FallowSegment",
        "Timeline",
    ]
    for name in names:
        assert hasattr(t, name), name


def test_domain_types_are_immutable() -> None:
    instances = [
        t.Stages(1, 2, 3, 4),
        t.SowingSpec(1, 15, 10),
        CROP,
        t.RotationSpec("A", (CROP,)),
        t.ParcelSpec(-33.68, -65.47, 0.28, 0.12, 1.2, 50.0),
        t.Window(2008, date(2008, 7, 1), date(2010, 6, 30)),
        t.DailyClimate(day=date(2008, 7, 1)),
        t.CropSegment(CROP, date(2008, 10, 15), date(2009, 3, 13)),
        t.FallowSegment(date(2009, 3, 14), date(2009, 3, 31)),
        t.Timeline(()),
    ]
    for instance in instances:
        first_field = fields(instance)[0].name
        with pytest.raises(FrozenInstanceError):
            setattr(instance, first_field, "otro valor")


def test_stages_total_days_is_the_sum() -> None:
    assert t.Stages(initial=25, development=40, mid=45, late=30).total_days == 140
    assert t.Stages(1, 1, 1, 1).total_days == 4


def test_daily_climate_accepts_none_in_every_variable() -> None:
    day = t.DailyClimate(day=date(2008, 7, 1))
    variables = [f.name for f in fields(day) if f.name != "day"]
    assert len(variables) == 7
    assert all(getattr(day, name) is None for name in variables)
    partial = t.DailyClimate(day=date(2008, 7, 2), precipitation_mm=0.0, wind_max_ms=9.1)
    assert partial.precipitation_mm == 0.0  # 0 es un valor, no un faltante
    assert partial.t_max_c is None


def test_window_n_days_covers_leap_and_regular_two_year_spans() -> None:
    assert t.Window(2008, date(2008, 7, 1), date(2010, 6, 30)).n_days == 730
    assert t.Window(2011, date(2011, 7, 1), date(2013, 6, 30)).n_days == 731


def test_segments_report_their_length_and_kind() -> None:
    crop = t.CropSegment(CROP, date(2008, 10, 15), date(2009, 3, 13))
    fallow = t.FallowSegment(date(2009, 3, 14), date(2009, 3, 31), residue_cover_pct=60.0)
    assert crop.n_days == 150
    assert fallow.n_days == 18
    assert crop.is_crop is True
    assert fallow.is_crop is False
    assert fallow.residue_cover_pct == 60.0


def test_timeline_n_days_adds_its_segments() -> None:
    timeline = t.Timeline(
        (
            t.FallowSegment(date(2008, 7, 1), date(2008, 10, 14)),
            t.CropSegment(CROP, date(2008, 10, 15), date(2009, 3, 13)),
            t.FallowSegment(date(2009, 3, 14), date(2010, 6, 30)),
        )
    )
    assert timeline.n_days == 730


def test_optional_fields_default_to_not_declared() -> None:
    assert CROP.price_per_t is None
    assert CROP.direct_costs_per_ha is None
    assert CROP.residue_cover_after_pct == 0.0
    assert t.RotationSpec("A", (CROP,)).initial_residue_cover_pct == 0.0
    assert t.ParcelSpec(-33.68, -65.47, 0.28, 0.12, 1.2, 50.0).fallow_kc_base == 0.20
