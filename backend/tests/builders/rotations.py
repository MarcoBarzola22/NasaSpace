"""Rotaciones y cultivos de ejemplo para las pruebas de invariantes (T021)."""

from __future__ import annotations

from app.domain.types import CropSpec, RotationSpec, SowingSpec, Stages


def make_crop(
    code: str,
    window_year: int,
    day: int,
    month: int,
    stages: tuple[int, int, int, int],
    *,
    crop_type: str = "grain",
    zr_initial_m: float = 0.25,
    zr_max_m: float = 1.2,
    p: float = 0.55,
    residue_after_pct: float = 0.0,
) -> CropSpec:
    is_grain = crop_type == "grain"
    return CropSpec(
        crop_code=code,
        crop_type=crop_type,
        sowing=SowingSpec(window_year, day, month),
        stages=Stages(*stages),
        kc_initial=0.30,
        kc_mid=1.20,
        kc_end=0.35,
        root_depth_initial_m=zr_initial_m,
        root_depth_max_m=zr_max_m,
        depletion_fraction_p=p,
        ky=1.0 if is_grain else None,
        ym_t_ha=5.0 if is_grain else None,
        residue_cover_after_pct=residue_after_pct,
    )


def invariant_rotations() -> dict[str, RotationSpec]:
    """Cuatro rotaciones que ejercitan los casos límite del balance (plan §9.3)."""
    maize = make_crop("maize", 1, 15, 10, (30, 40, 50, 30), residue_after_pct=60.0)
    wheat = make_crop("wheat", 1, 1, 6, (25, 55, 70, 35))
    soy_second = make_crop("soybean_second", 2, 3, 12, (15, 25, 50, 20))
    rye = make_crop(
        "rye_cover",
        1,
        1,
        4,
        (20, 40, 40, 20),
        crop_type="cover",
        zr_max_m=1.0,
        residue_after_pct=80.0,
    )
    deep = make_crop("deep", 1, 1, 10, (30, 40, 50, 30), zr_initial_m=0.4, zr_max_m=2.5)
    return {
        # Trigo y soja de segunda sin barbecho entre ambos (barbecho de 0 días).
        "zero_day_fallow": RotationSpec("B", (maize, wheat, soy_second)),
        # Un solo cultivo y barbechos largos antes y después.
        "long_fallow": RotationSpec("A", (maize,), initial_residue_cover_pct=30.0),
        # Solo cultivo de cobertura.
        "cover_only": RotationSpec("C", (rye,)),
        # Zr máxima mayor que la profundidad del suelo (se limita a la profundidad efectiva).
        "deep_roots": RotationSpec("A", (deep,)),
    }
