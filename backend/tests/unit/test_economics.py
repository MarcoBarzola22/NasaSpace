"""Pruebas del ingreso y el margen bruto (T023).

Criterios que verifica: CA-10.1 (ingreso y margen de un cultivo de grano), CA-10.2 (cultivo de
cobertura), CA-10.3 (totales de la rotación), CA-10.4 (datos faltantes: margen no calculado),
CA-10.5 (precios y costos no negativos) y CA-10.7 (rótulo «Margen bruto negativo», nunca «pérdida»).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.domain import economics as eco
from app.domain.types import CropSpec
from app.domain.yield_response import YieldResult, crop_yield
from tests.builders.rotations import make_crop

BASE_MAIZE = replace(make_crop("maize", 1, 15, 10, (30, 40, 50, 30)), ky=1.25, ym_t_ha=9.0)
MAIZE = replace(BASE_MAIZE, price_per_t=180.0, direct_costs_per_ha=620.0)
SOY = replace(
    make_crop("soybean_first", 2, 15, 11, (20, 35, 60, 25)),
    ky=0.85,
    ym_t_ha=3.2,
    price_per_t=300.0,
    direct_costs_per_ha=380.0,
)
RYE = replace(
    make_crop("rye_cover", 1, 1, 4, (20, 40, 40, 20), crop_type="cover"), direct_costs_per_ha=95.0
)


def with_yield(yield_t_ha: float | None, ym: float = 9.0) -> YieldResult:
    relative = None if yield_t_ha is None else yield_t_ha / ym
    return YieldResult(500.0, 400.0, 0.8, yield_t_ha, relative, False)


COVER_YIELD = crop_yield(RYE, etm_mm=160.2, eta_mm=121.7)


# --- Un cultivo de grano (CA-10.1) ---


def test_economics_grain_income_and_gross_margin() -> None:
    result = eco.crop_economics(MAIZE, with_yield(5.0848))
    assert result.status == "computed"
    assert result.income_per_ha == pytest.approx(915.264, abs=1e-6)
    assert result.direct_costs_per_ha == 620.0
    assert result.gross_margin_per_ha == pytest.approx(295.264, abs=1e-6)
    assert result.gross_margin_label is None
    assert result.missing_fields == ()
    assert result.note is None


def test_economics_income_is_yield_times_price_from_the_fao33_result() -> None:
    fao33 = crop_yield(MAIZE, etm_mm=642.5, eta_mm=418.9)
    result = eco.crop_economics(MAIZE, fao33)
    assert result.income_per_ha == pytest.approx(fao33.yield_t_ha * 180.0, abs=1e-9)
    assert result.gross_margin_per_ha == pytest.approx(fao33.yield_t_ha * 180.0 - 620.0, abs=1e-9)


def test_economics_negative_margin_is_labelled_not_called_a_loss() -> None:
    result = eco.crop_economics(MAIZE, with_yield(1.0))  # ingreso 180 < costos 620
    assert result.gross_margin_per_ha == pytest.approx(-440.0)
    assert result.gross_margin_label == "Margen bruto negativo"
    assert "pérdida" not in (result.gross_margin_label or "").lower()


def test_economics_zero_margin_has_no_negative_label() -> None:
    result = eco.crop_economics(replace(MAIZE, price_per_t=620.0), with_yield(1.0))
    assert result.gross_margin_per_ha == pytest.approx(0.0, abs=1e-9)
    assert result.gross_margin_label is None


def test_economics_zero_price_gives_zero_income() -> None:
    result = eco.crop_economics(replace(MAIZE, price_per_t=0.0), with_yield(5.0))
    assert result.income_per_ha == 0.0
    assert result.gross_margin_per_ha == -620.0
    assert result.gross_margin_label == "Margen bruto negativo"


def test_economics_income_scales_linearly_with_the_yield() -> None:
    incomes = [eco.crop_economics(MAIZE, with_yield(y)).income_per_ha for y in (0.0, 2.0, 4.0, 8.0)]
    assert incomes == [0.0, 360.0, 720.0, 1440.0]


# --- Cultivo de cobertura (CA-10.2) y rendimiento no calculado ---


def test_economics_cover_crop_has_zero_income_and_margin_equal_to_minus_costs() -> None:
    result = eco.crop_economics(RYE, COVER_YIELD)
    assert result.status == "computed"
    assert result.income_per_ha == 0.0
    assert result.gross_margin_per_ha == -95.0
    assert result.gross_margin_label == "Margen bruto negativo"
    assert result.note == eco.NOTE_COVER_CROP


def test_economics_cover_crop_without_costs_is_not_computed() -> None:
    result = eco.crop_economics(replace(RYE, direct_costs_per_ha=None), COVER_YIELD)
    assert result.status == "not_computed"
    assert result.missing_fields == ("direct_costs_per_ha",)
    assert result.income_per_ha is None and result.gross_margin_per_ha is None


def test_economics_cover_crop_with_a_price_is_rejected() -> None:
    with pytest.raises(ValueError, match="cobertura"):
        eco.crop_economics(replace(RYE, price_per_t=100.0), COVER_YIELD)


def test_economics_grain_without_computed_yield_has_zero_income_and_a_visible_note() -> None:
    no_yield = crop_yield(MAIZE, etm_mm=0.0, eta_mm=0.0)
    assert no_yield.yield_t_ha is None
    result = eco.crop_economics(MAIZE, no_yield)
    assert result.income_per_ha == 0.0
    assert result.gross_margin_per_ha == -620.0
    assert result.note == eco.NOTE_NO_YIELD
    assert "rendimiento" in result.note


# --- Datos faltantes (CA-10.4) ---


def test_economics_missing_price_or_costs_is_not_computed_and_never_zero() -> None:
    no_price = eco.crop_economics(replace(MAIZE, price_per_t=None), with_yield(5.0))
    no_costs = eco.crop_economics(replace(MAIZE, direct_costs_per_ha=None), with_yield(5.0))
    neither = eco.crop_economics(BASE_MAIZE, with_yield(5.0))
    assert no_price.missing_fields == ("price_per_t",)
    assert no_costs.missing_fields == ("direct_costs_per_ha",)
    assert neither.missing_fields == ("price_per_t", "direct_costs_per_ha")
    for result in (no_price, no_costs, neither):
        assert result.status == "not_computed"
        assert result.income_per_ha is None
        assert result.gross_margin_per_ha is None
        assert result.gross_margin_label is None


@pytest.mark.parametrize(
    "changes", [{"price_per_t": -1.0}, {"direct_costs_per_ha": -0.01}], ids=["price", "costs"]
)
def test_economics_rejects_negative_inputs(changes: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="negativ"):
        eco.crop_economics(replace(MAIZE, **changes), with_yield(5.0))


# --- Rotación (CA-10.3) ---


def rotation_inputs() -> tuple[list[CropSpec], list[YieldResult]]:
    crops = [MAIZE, RYE, SOY]
    yields = [with_yield(5.0848), COVER_YIELD, with_yield(1.67, ym=3.2)]
    return crops, yields


def test_economics_rotation_totals_are_the_sum_of_the_crops() -> None:
    crops, yields = rotation_inputs()
    rotation = eco.rotation_economics(crops, yields)
    assert rotation.status == "computed"
    assert rotation.income_per_ha == pytest.approx(5.0848 * 180 + 0.0 + 1.67 * 300, abs=1e-9)
    assert rotation.direct_costs_per_ha == pytest.approx(620 + 95 + 380)
    assert rotation.gross_margin_per_ha == pytest.approx(
        rotation.income_per_ha - rotation.direct_costs_per_ha
    )
    assert rotation.gross_margin_per_ha == pytest.approx(
        sum(c.gross_margin_per_ha for c in rotation.crops), abs=1e-9
    )
    assert rotation.crops_missing_economics == ()
    assert len(rotation.crops) == 3


def test_economics_rotation_negative_total_is_labelled() -> None:
    crops, yields = rotation_inputs()
    yields[0] = with_yield(0.5)
    yields[2] = with_yield(0.2, ym=3.2)
    rotation = eco.rotation_economics(crops, yields)
    assert rotation.gross_margin_per_ha < 0
    assert rotation.gross_margin_label == "Margen bruto negativo"


def test_economics_rotation_with_a_crop_without_price_is_not_computed() -> None:
    crops, yields = rotation_inputs()
    crops[2] = replace(SOY, price_per_t=None)
    rotation = eco.rotation_economics(crops, yields)
    assert rotation.status == "not_computed"
    assert rotation.income_per_ha is None and rotation.gross_margin_per_ha is None
    assert rotation.crops_missing_economics == (
        eco.MissingEconomics(3, "soybean_first", ("price_per_t",)),
    )
    # Los cultivos completos sí conservan su propia economía (CL-29).
    assert rotation.crops[0].status == "computed"
    assert rotation.crops[0].gross_margin_per_ha == pytest.approx(295.264, abs=1e-6)
    assert rotation.crops[1].gross_margin_per_ha == -95.0


def test_economics_rotation_lists_every_crop_with_missing_data() -> None:
    crops, yields = rotation_inputs()
    crops[0] = replace(MAIZE, direct_costs_per_ha=None)
    crops[1] = replace(RYE, direct_costs_per_ha=None)
    rotation = eco.rotation_economics(crops, yields)
    assert [m.position for m in rotation.crops_missing_economics] == [1, 2]
    assert [m.crop_code for m in rotation.crops_missing_economics] == ["maize", "rye_cover"]


def test_economics_rotation_requires_one_yield_per_crop() -> None:
    crops, yields = rotation_inputs()
    with pytest.raises(ValueError, match="cultivos"):
        eco.rotation_economics(crops, yields[:2])


def test_economics_cover_only_rotation_is_a_negative_gross_margin() -> None:
    rotation = eco.rotation_economics([RYE], [COVER_YIELD])
    assert rotation.status == "computed"
    assert rotation.income_per_ha == 0.0
    assert rotation.gross_margin_per_ha == -95.0
    assert rotation.gross_margin_label == "Margen bruto negativo"


def test_economics_no_text_says_loss() -> None:
    crops, yields = rotation_inputs()
    yields[0] = with_yield(0.1)
    rotation = eco.rotation_economics(crops, yields)
    texts = [eco.LABEL_NEGATIVE_MARGIN, eco.NOTE_COVER_CROP, eco.NOTE_NO_YIELD]
    texts += [rotation.gross_margin_label or ""]
    for crop_result in rotation.crops:
        texts += [crop_result.gross_margin_label or "", crop_result.note or ""]
    for text in texts:
        assert "pérdida" not in text.lower()
        assert "perdida" not in text.lower()
