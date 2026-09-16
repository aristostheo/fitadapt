"""Unit tests for deterministic calorie targets and macro allocation."""

import math
from dataclasses import FrozenInstanceError, astuple

import pytest

from fitadapt.baseline.energy import BaselineEnergyEstimate
from fitadapt.baseline.targets import (
    CARBOHYDRATE_KCAL_PER_GRAM,
    DAYS_PER_WEEK,
    ENERGY_EQUIVALENT_KCAL_PER_KG,
    ENERGY_EQUIVALENT_POLICY_VERSION,
    FAT_GRAMS_PER_KG_BODY_WEIGHT,
    FAT_KCAL_PER_GRAM,
    MACRO_POLICY_VERSION,
    PROTEIN_GRAMS_PER_KG_BODY_WEIGHT,
    PROTEIN_KCAL_PER_GRAM,
    CalorieTargetEstimate,
    MacroPolicyInfeasibleError,
    calculate_calorie_target,
    calculate_daily_calorie_adjustment,
    minimum_macro_calories_kcal_per_day,
)
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile


def make_profile(**overrides: object) -> UserProfile:
    """Create the manual-reference profile and override inputs for a focused test."""
    values: dict[str, object] = {
        "age_years": 23,
        "height_cm": 192.0,
        "weight_kg": 91.0,
        "sex_for_mifflin_equation": SexForMifflinEquation.MALE,
        "activity_level": ActivityLevel.VERY_ACTIVE,
        "goal": Goal.CUT,
        "requested_weekly_change_kg": -0.45,
    }
    values.update(overrides)
    return UserProfile(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("goal", "requested_weekly_change_kg", "expected_adjustment_kcal"),
    [
        (Goal.CUT, -0.45, -495.0),
        (Goal.MAINTAIN, 0.0, 0.0),
        (Goal.GAIN, 0.25, 275.0),
    ],
)
def test_calculates_signed_daily_calorie_adjustment(
    goal: Goal,
    requested_weekly_change_kg: float,
    expected_adjustment_kcal: float,
) -> None:
    profile = make_profile(
        goal=goal,
        requested_weekly_change_kg=requested_weekly_change_kg,
    )

    assert calculate_daily_calorie_adjustment(profile) == pytest.approx(expected_adjustment_kcal)


@pytest.mark.parametrize(
    ("goal", "requested_weekly_change_kg", "expected_target_calories"),
    [
        (Goal.CUT, -0.45, 2955.0),
        (Goal.MAINTAIN, 0.0, 3450.0),
        (Goal.GAIN, 0.25, 3725.0),
    ],
)
def test_calculates_target_calories_from_baseline_and_signed_adjustment(
    goal: Goal,
    requested_weekly_change_kg: float,
    expected_target_calories: float,
) -> None:
    estimate = calculate_calorie_target(
        make_profile(goal=goal, requested_weekly_change_kg=requested_weekly_change_kg)
    )

    assert estimate.target_calories_kcal_per_day == pytest.approx(expected_target_calories)


def test_calculates_complete_manual_reference_case() -> None:
    estimate = calculate_calorie_target(make_profile())

    assert estimate.baseline_energy.estimated_ree_kcal_per_day == pytest.approx(2000.0)
    assert estimate.baseline_energy.estimated_tdee_kcal_per_day == pytest.approx(3450.0)
    assert estimate.daily_calorie_adjustment_kcal == pytest.approx(-495.0)
    assert estimate.target_calories_kcal_per_day == pytest.approx(2955.0)
    assert estimate.protein_g_per_day == pytest.approx(145.6)
    assert estimate.fat_g_per_day == pytest.approx(54.6)
    assert estimate.carbohydrate_g_per_day == pytest.approx(470.3)


def test_macro_calories_reconcile_with_target_calories() -> None:
    estimate = calculate_calorie_target(make_profile())

    macro_calories = (
        estimate.protein_g_per_day * 4.0
        + estimate.fat_g_per_day * 9.0
        + estimate.carbohydrate_g_per_day * 4.0
    )

    assert macro_calories == pytest.approx(estimate.target_calories_kcal_per_day)


def test_records_policy_versions_and_assumptions() -> None:
    estimate = calculate_calorie_target(make_profile())

    assert estimate.energy_equivalent_policy_version == ENERGY_EQUIVALENT_POLICY_VERSION
    assert estimate.macro_policy_version == MACRO_POLICY_VERSION
    assert len(estimate.assumptions) == 4


def test_keeps_goal_and_requested_change_in_result() -> None:
    profile = make_profile()
    estimate = calculate_calorie_target(profile)

    assert estimate.goal is Goal.CUT
    assert estimate.requested_weekly_change_kg == profile.requested_weekly_change_kg


def test_result_composes_baseline_energy_estimate() -> None:
    estimate = calculate_calorie_target(make_profile())

    assert isinstance(estimate.baseline_energy, BaselineEnergyEstimate)


def test_target_estimate_is_immutable() -> None:
    estimate = calculate_calorie_target(make_profile())

    with pytest.raises(FrozenInstanceError):
        estimate.target_calories_kcal_per_day = 1.0  # type: ignore[misc]


def test_calculation_does_not_mutate_input_profile() -> None:
    profile = make_profile()
    original_values = astuple(profile)

    calculate_calorie_target(profile)

    assert astuple(profile) == original_values


def test_repeated_calls_are_deterministic() -> None:
    profile = make_profile()

    assert calculate_calorie_target(profile) == calculate_calorie_target(profile)


@pytest.mark.parametrize(
    ("goal", "requested_weekly_change_kg"),
    [
        (Goal.CUT, -0.45),
        (Goal.MAINTAIN, 0.0),
        (Goal.GAIN, 0.25),
    ],
)
def test_public_numeric_outputs_are_finite_for_feasible_profiles(
    goal: Goal,
    requested_weekly_change_kg: float,
) -> None:
    estimate = calculate_calorie_target(
        make_profile(goal=goal, requested_weekly_change_kg=requested_weekly_change_kg)
    )

    numeric_values = (
        estimate.daily_calorie_adjustment_kcal,
        estimate.target_calories_kcal_per_day,
        estimate.protein_g_per_day,
        estimate.fat_g_per_day,
        estimate.carbohydrate_g_per_day,
    )
    assert all(math.isfinite(value) for value in numeric_values)
    assert estimate.carbohydrate_g_per_day >= 0


def test_raises_for_a_valid_profile_with_infeasible_macro_policy() -> None:
    profile = UserProfile(
        age_years=80,
        height_cm=100.0,
        weight_kg=30.0,
        sex_for_mifflin_equation=SexForMifflinEquation.FEMALE,
        activity_level=ActivityLevel.SEDENTARY,
        goal=Goal.CUT,
        requested_weekly_change_kg=-0.224,
    )

    with pytest.raises(MacroPolicyInfeasibleError, match="cannot fund"):
        calculate_calorie_target(profile)


def test_near_zero_remaining_calories_become_zero_carbohydrate() -> None:
    profile = UserProfile(
        age_years=80,
        height_cm=100.0,
        weight_kg=30.0,
        sex_for_mifflin_equation=SexForMifflinEquation.FEMALE,
        activity_level=ActivityLevel.SEDENTARY,
        goal=Goal.CUT,
        requested_weekly_change_kg=-82.8 * 7.0 / 7700.0,
    )

    estimate = calculate_calorie_target(profile)

    assert estimate.target_calories_kcal_per_day == pytest.approx(354.0)
    assert estimate.carbohydrate_g_per_day == pytest.approx(0.0)
    assert estimate.carbohydrate_g_per_day >= 0


def test_policy_constants_contain_approved_values() -> None:
    assert ENERGY_EQUIVALENT_KCAL_PER_KG == 7700.0
    assert DAYS_PER_WEEK == 7.0
    assert PROTEIN_GRAMS_PER_KG_BODY_WEIGHT == 1.6
    assert FAT_GRAMS_PER_KG_BODY_WEIGHT == 0.6
    assert PROTEIN_KCAL_PER_GRAM == 4.0
    assert CARBOHYDRATE_KCAL_PER_GRAM == 4.0
    assert FAT_KCAL_PER_GRAM == 9.0


def test_result_uses_the_public_estimate_type() -> None:
    assert isinstance(calculate_calorie_target(make_profile()), CalorieTargetEstimate)


def test_minimum_macro_calories_reuses_existing_policy_without_mutating_profile() -> None:
    profile = make_profile(weight_kg=80.0)
    snapshot = profile

    minimum = minimum_macro_calories_kcal_per_day(profile)

    assert minimum == pytest.approx(80.0 * 1.6 * 4.0 + 80.0 * 0.6 * 9.0)
    assert minimum == pytest.approx(
        80.0 * PROTEIN_GRAMS_PER_KG_BODY_WEIGHT * PROTEIN_KCAL_PER_GRAM
        + 80.0 * FAT_GRAMS_PER_KG_BODY_WEIGHT * FAT_KCAL_PER_GRAM
    )
    assert profile == snapshot
