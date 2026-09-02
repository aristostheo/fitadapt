"""Unit tests for deterministic REE and static baseline TDEE calculations."""

import math
from dataclasses import FrozenInstanceError, astuple

import pytest

from fitadapt.baseline.energy import (
    ACTIVITY_MULTIPLIERS,
    ACTIVITY_POLICY_VERSION,
    REE_FORMULA_VERSION,
    BaselineEnergyEstimate,
    calculate_baseline_energy,
    calculate_mifflin_st_jeor_ree,
)
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile


def make_profile(**overrides: object) -> UserProfile:
    """Create a valid profile and override one or more inputs for a focused test."""
    values: dict[str, object] = {
        "age_years": 23,
        "height_cm": 192.0,
        "weight_kg": 91.0,
        "sex_for_mifflin_equation": SexForMifflinEquation.MALE,
        "activity_level": ActivityLevel.VERY_ACTIVE,
        "goal": Goal.MAINTAIN,
        "requested_weekly_change_kg": 0.0,
    }
    values.update(overrides)
    return UserProfile(**values)  # type: ignore[arg-type]


def test_calculates_male_mifflin_st_jeor_ree_for_manual_reference_profile() -> None:
    profile = make_profile()

    assert calculate_mifflin_st_jeor_ree(profile) == pytest.approx(2000.0)


def test_calculates_female_mifflin_st_jeor_ree() -> None:
    profile = make_profile(sex_for_mifflin_equation=SexForMifflinEquation.FEMALE)

    assert calculate_mifflin_st_jeor_ree(profile) == pytest.approx(1834.0)


def test_male_and_female_ree_differ_by_166_kcal_per_day_for_equal_inputs() -> None:
    male_profile = make_profile(sex_for_mifflin_equation=SexForMifflinEquation.MALE)
    female_profile = make_profile(sex_for_mifflin_equation=SexForMifflinEquation.FEMALE)

    difference = calculate_mifflin_st_jeor_ree(male_profile) - calculate_mifflin_st_jeor_ree(
        female_profile
    )

    assert difference == pytest.approx(166.0)


@pytest.mark.parametrize(
    ("activity_level", "expected_multiplier"),
    [
        (ActivityLevel.SEDENTARY, 1.200),
        (ActivityLevel.LIGHTLY_ACTIVE, 1.375),
        (ActivityLevel.MODERATELY_ACTIVE, 1.550),
        (ActivityLevel.VERY_ACTIVE, 1.725),
        (ActivityLevel.EXTRA_ACTIVE, 1.900),
    ],
)
def test_uses_the_versioned_multiplier_for_each_activity_level(
    activity_level: ActivityLevel,
    expected_multiplier: float,
) -> None:
    estimate = calculate_baseline_energy(make_profile(activity_level=activity_level))

    assert estimate.activity_level is activity_level
    assert estimate.activity_multiplier == pytest.approx(expected_multiplier)


def test_calculates_tdee_for_manual_reference_profile() -> None:
    estimate = calculate_baseline_energy(make_profile())

    assert estimate.estimated_ree_kcal_per_day == pytest.approx(2000.0)
    assert estimate.activity_multiplier == pytest.approx(1.725)
    assert estimate.estimated_tdee_kcal_per_day == pytest.approx(3450.0)


def test_records_formula_and_activity_policy_versions() -> None:
    estimate = calculate_baseline_energy(make_profile())

    assert estimate.ree_formula_version == REE_FORMULA_VERSION
    assert estimate.activity_policy_version == ACTIVITY_POLICY_VERSION


def test_energy_estimate_is_immutable() -> None:
    estimate = calculate_baseline_energy(make_profile())

    with pytest.raises(FrozenInstanceError):
        estimate.estimated_ree_kcal_per_day = 1.0  # type: ignore[misc]


def test_calculation_does_not_mutate_input_profile() -> None:
    profile = make_profile()
    original_values = astuple(profile)

    calculate_baseline_energy(profile)

    assert astuple(profile) == original_values


def test_repeated_calls_are_deterministic() -> None:
    profile = make_profile()

    assert calculate_baseline_energy(profile) == calculate_baseline_energy(profile)


def test_goal_and_requested_change_do_not_affect_baseline_energy() -> None:
    maintain = make_profile(goal=Goal.MAINTAIN, requested_weekly_change_kg=0.0)
    cut = make_profile(goal=Goal.CUT, requested_weekly_change_kg=-0.5)
    gain = make_profile(goal=Goal.GAIN, requested_weekly_change_kg=0.25)

    assert calculate_baseline_energy(cut) == calculate_baseline_energy(maintain)
    assert calculate_baseline_energy(gain) == calculate_baseline_energy(maintain)


@pytest.mark.parametrize("activity_level", list(ActivityLevel))
@pytest.mark.parametrize("sex_for_mifflin_equation", list(SexForMifflinEquation))
def test_public_energy_results_are_finite_and_positive(
    activity_level: ActivityLevel, sex_for_mifflin_equation: SexForMifflinEquation
) -> None:
    estimate = calculate_baseline_energy(
        make_profile(
            activity_level=activity_level,
            sex_for_mifflin_equation=sex_for_mifflin_equation,
        )
    )

    assert math.isfinite(estimate.estimated_ree_kcal_per_day)
    assert math.isfinite(estimate.activity_multiplier)
    assert math.isfinite(estimate.estimated_tdee_kcal_per_day)
    assert estimate.estimated_ree_kcal_per_day > 0
    assert estimate.activity_multiplier > 0
    assert estimate.estimated_tdee_kcal_per_day > 0


def test_result_uses_the_public_estimate_type() -> None:
    assert isinstance(calculate_baseline_energy(make_profile()), BaselineEnergyEstimate)


def test_activity_multipliers_are_immutable() -> None:
    with pytest.raises(TypeError):
        ACTIVITY_MULTIPLIERS[ActivityLevel.SEDENTARY] = 2.0  # type: ignore[index]
