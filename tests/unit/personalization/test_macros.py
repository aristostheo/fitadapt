"""Focused contracts for explicit V1 preference-driven macro planning."""

from dataclasses import FrozenInstanceError, astuple
from math import inf, nan

import pytest

from fitadapt.baseline.targets import calculate_calorie_target
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.macros import (
    MACRO_PLAN_POLICY_VERSION,
    MacroCalorieSource,
    MacroPlanInfeasibleError,
    MacroStrategy,
    NutritionPreferences,
    NutritionPreferencesError,
    calculate_personalized_macro_plan,
)


@pytest.fixture
def profile() -> UserProfile:
    return UserProfile(
        age_years=30,
        height_cm=180,
        weight_kg=80,
        sex_for_mifflin_equation=SexForMifflinEquation.MALE,
        activity_level=ActivityLevel.MODERATELY_ACTIVE,
        goal=Goal.MAINTAIN,
        requested_weekly_change_kg=0,
    )


@pytest.mark.parametrize(
    ("strategy", "protein", "fat_percentage", "protein_g", "fat_g", "carbohydrate_g"),
    [
        (MacroStrategy.BALANCED, 1.8, 0.25, 144.0, 66.66666666666667, 306.0),
        (MacroStrategy.HIGHER_CARB, 1.6, 0.20, 128.0, 53.333333333333336, 352.0),
        (MacroStrategy.HIGHER_FAT, 1.6, 0.35, 128.0, 93.33333333333333, 262.0),
        (MacroStrategy.HIGHER_PROTEIN, 2.0, 0.25, 160.0, 66.66666666666667, 290.0),
    ],
)
def test_predefined_strategies_follow_hand_calculated_allocations(
    profile: UserProfile,
    strategy: MacroStrategy,
    protein: float,
    fat_percentage: float,
    protein_g: float,
    fat_g: float,
    carbohydrate_g: float,
) -> None:
    plan = calculate_personalized_macro_plan(
        profile, 2400, MacroCalorieSource.BASELINE, NutritionPreferences(strategy)
    )

    assert plan.protein_g_per_kg == protein
    assert plan.fat_percentage == fat_percentage
    assert plan.protein_g_per_day == protein_g
    assert plan.fat_g_per_day == fat_g
    assert plan.carbohydrate_g_per_day == carbohydrate_g
    assert (
        plan.protein_kcal_per_day + plan.fat_kcal_per_day + plan.carbohydrate_kcal_per_day == 2400
    )
    assert plan.calorie_source is MacroCalorieSource.BASELINE
    assert plan.macro_policy_version == MACRO_PLAN_POLICY_VERSION


def test_custom_strategy_uses_explicit_values_and_preserves_full_precision(
    profile: UserProfile,
) -> None:
    preferences = NutritionPreferences(MacroStrategy.CUSTOM, 2.2, 0.30)
    plan = calculate_personalized_macro_plan(
        profile, 2400, MacroCalorieSource.PERSONALIZED, preferences
    )

    assert plan.protein_g_per_kg == 2.2
    assert plan.fat_percentage == 0.30
    assert plan.protein_g_per_day == 176.0
    assert plan.protein_kcal_per_day == 704.0
    assert plan.fat_g_per_day == 80.0
    assert plan.carbohydrate_g_per_day == 244.0
    assert plan.calorie_source is MacroCalorieSource.PERSONALIZED


def test_custom_boundaries_and_integer_normalization(profile: UserProfile) -> None:
    preferences = NutritionPreferences(MacroStrategy.CUSTOM, 2, 0.4)
    plan = calculate_personalized_macro_plan(
        profile, 2400, MacroCalorieSource.BASELINE, preferences
    )

    assert preferences.custom_protein_g_per_kg == 2.0
    assert isinstance(preferences.custom_protein_g_per_kg, float)
    assert preferences.custom_fat_percentage == 0.4
    assert plan.calorie_target_kcal_per_day == 2400.0
    assert isinstance(plan.calorie_target_kcal_per_day, float)
    assert NutritionPreferences(MacroStrategy.CUSTOM, 1.2, 0.2)
    assert NutritionPreferences(MacroStrategy.CUSTOM, 2.4, 0.4)


def test_invalid_strategy_and_calorie_source_enums_are_rejected(profile: UserProfile) -> None:
    with pytest.raises(NutritionPreferencesError):
        NutritionPreferences("balanced")  # type: ignore[arg-type]
    with pytest.raises(NutritionPreferencesError):
        calculate_personalized_macro_plan(
            profile,
            2400,
            "baseline",  # type: ignore[arg-type]
            NutritionPreferences(MacroStrategy.BALANCED),
        )


@pytest.mark.parametrize(
    "preferences",
    [
        (MacroStrategy.CUSTOM, None, 0.25),
        (MacroStrategy.CUSTOM, 1.8, None),
        (MacroStrategy.BALANCED, 1.8, None),
        (MacroStrategy.HIGHER_CARB, None, 0.25),
        (MacroStrategy.CUSTOM, 1.1, 0.25),
        (MacroStrategy.CUSTOM, 2.5, 0.25),
        (MacroStrategy.CUSTOM, 1.8, 0.19),
        (MacroStrategy.CUSTOM, 1.8, 0.41),
    ],
)
def test_invalid_custom_combinations_are_rejected(
    preferences: tuple[MacroStrategy, object, object],
) -> None:
    with pytest.raises(NutritionPreferencesError):
        NutritionPreferences(*preferences)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [True, "1.8", nan, inf, -inf])
def test_custom_numeric_fields_reject_invalid_values(value: object) -> None:
    with pytest.raises(NutritionPreferencesError):
        NutritionPreferences(MacroStrategy.CUSTOM, value, 0.25)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [True, "2400", None, nan, inf, -inf, 0, -1])
def test_calorie_target_rejects_invalid_values(profile: UserProfile, value: object) -> None:
    with pytest.raises(NutritionPreferencesError):
        calculate_personalized_macro_plan(
            profile,
            value,
            MacroCalorieSource.BASELINE,
            NutritionPreferences(MacroStrategy.BALANCED),  # type: ignore[arg-type]
        )


def test_infeasible_plan_and_negligible_negative_remainder(profile: UserProfile) -> None:
    with pytest.raises(MacroPlanInfeasibleError):
        calculate_personalized_macro_plan(
            profile,
            100,
            MacroCalorieSource.BASELINE,
            NutritionPreferences(MacroStrategy.HIGHER_PROTEIN),
        )
    target = 640 / 0.75 - 5e-10
    plan = calculate_personalized_macro_plan(
        profile,
        target,
        MacroCalorieSource.BASELINE,
        NutritionPreferences(MacroStrategy.HIGHER_PROTEIN),
    )
    assert plan.carbohydrate_g_per_day == 0.0


def test_models_are_immutable_and_do_not_mutate_profile(profile: UserProfile) -> None:
    snapshot = astuple(profile)
    preferences = NutritionPreferences(MacroStrategy.BALANCED)
    plan = calculate_personalized_macro_plan(
        profile, 2400, MacroCalorieSource.BASELINE, preferences
    )

    with pytest.raises(FrozenInstanceError):
        preferences.macro_strategy = MacroStrategy.CUSTOM  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        plan.protein_g_per_day = 0  # type: ignore[misc]
    assert astuple(profile) == snapshot
    assert isinstance(plan.assumptions, tuple)


def test_existing_baseline_target_is_unchanged(profile: UserProfile) -> None:
    before = calculate_calorie_target(profile)
    calculate_personalized_macro_plan(
        profile,
        before.target_calories_kcal_per_day,
        MacroCalorieSource.BASELINE,
        NutritionPreferences(MacroStrategy.BALANCED),
    )
    assert calculate_calorie_target(profile) == before
