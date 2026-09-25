"""Focused domain contracts for V1 nutrition target envelopes."""

from dataclasses import FrozenInstanceError, astuple
from math import inf, nan

import pytest

from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.macros import (
    MacroCalorieSource,
    MacroStrategy,
    NutritionPreferences,
    calculate_personalized_macro_plan,
)
from fitadapt.personalization.targets import (
    NUTRITION_TARGET_RANGE_POLICY_VERSION,
    NutritionRangeKind,
    NutritionTargetEnvelopeError,
    NutritionTargetRange,
    NutritionTargetRangeConfig,
    calculate_nutrition_target_envelope,
)


@pytest.fixture
def profile() -> UserProfile:
    return UserProfile(
        30, 180, 80, SexForMifflinEquation.MALE, ActivityLevel.MODERATELY_ACTIVE, Goal.MAINTAIN, 0
    )


def test_hand_calculated_balanced_envelope_preserves_exact_plan(profile: UserProfile) -> None:
    preferences = NutritionPreferences(MacroStrategy.BALANCED)
    envelope = calculate_nutrition_target_envelope(
        profile, 2400, MacroCalorieSource.BASELINE, preferences
    )
    assert envelope.calorie_adherence_range.lower_bound == 2300.0
    assert envelope.calorie_adherence_range.selected_value == 2400.0
    assert envelope.calorie_adherence_range.upper_bound == 2500.0
    assert envelope.protein_preferred_range.lower_bound == 128.0
    assert envelope.protein_preferred_range.selected_value == 144.0
    assert envelope.protein_preferred_range.upper_bound == 160.0
    assert envelope.macro_plan == calculate_personalized_macro_plan(
        profile, 2400, MacroCalorieSource.BASELINE, preferences
    )
    assert envelope.range_policy_version == NUTRITION_TARGET_RANGE_POLICY_VERSION
    assert isinstance(envelope.assumptions, tuple)


@pytest.mark.parametrize("strategy", tuple(MacroStrategy))
def test_every_strategy_has_selected_points_inside_immutable_ranges(
    profile: UserProfile, strategy: MacroStrategy
) -> None:
    preferences = (
        NutritionPreferences(strategy, 1.2, 0.2)
        if strategy is MacroStrategy.CUSTOM
        else NutritionPreferences(strategy)
    )
    envelope = calculate_nutrition_target_envelope(
        profile, 2400, MacroCalorieSource.PERSONALIZED, preferences
    )
    for target in (
        envelope.calorie_adherence_range,
        envelope.protein_preferred_range,
        envelope.fat_preferred_range,
        envelope.carbohydrate_flexible_range,
    ):
        assert target.lower_bound <= target.selected_value <= target.upper_bound
    assert envelope.macro_plan.calorie_source is MacroCalorieSource.PERSONALIZED


def test_custom_boundaries_clamp_preferred_ranges(profile: UserProfile) -> None:
    lower = calculate_nutrition_target_envelope(
        profile,
        2400,
        MacroCalorieSource.BASELINE,
        NutritionPreferences(MacroStrategy.CUSTOM, 1.2, 0.2),
    )
    upper = calculate_nutrition_target_envelope(
        profile,
        2400,
        MacroCalorieSource.BASELINE,
        NutritionPreferences(MacroStrategy.CUSTOM, 2.4, 0.4),
    )
    assert lower.protein_preferred_range.lower_bound == 96.0
    assert lower.fat_preferred_range.lower_bound == 53.333333333333336
    assert upper.protein_preferred_range.upper_bound == 192.0
    assert upper.fat_preferred_range.upper_bound == 106.66666666666667


@pytest.mark.parametrize("value", [True, "1", None, nan, inf, -inf])
def test_configuration_rejects_invalid_numeric_values(value: object) -> None:
    with pytest.raises(NutritionTargetEnvelopeError):
        NutritionTargetRangeConfig(calorie_adherence_tolerance_kcal_per_day=value)  # type: ignore[arg-type]


def test_configuration_normalizes_ints_and_public_models_are_frozen_and_slotted() -> None:
    config = NutritionTargetRangeConfig(100, 0, 0)
    assert astuple(config) == (100.0, 0.0, 0.0)
    with pytest.raises(FrozenInstanceError):
        config.calorie_adherence_tolerance_kcal_per_day = 1  # type: ignore[misc]
    with pytest.raises(NutritionTargetEnvelopeError):
        NutritionTargetRange(2, 1, 3, "g/day", "test", NutritionRangeKind.PREFERRED)


def test_inputs_are_unchanged_and_results_are_deterministic(profile: UserProfile) -> None:
    preferences = NutritionPreferences(MacroStrategy.HIGHER_FAT)
    before = astuple(profile), astuple(preferences)
    first = calculate_nutrition_target_envelope(
        profile, 2400, MacroCalorieSource.BASELINE, preferences
    )
    assert first == calculate_nutrition_target_envelope(
        profile, 2400, MacroCalorieSource.BASELINE, preferences
    )
    assert before == (astuple(profile), astuple(preferences))
    assert first.carbohydrate_flexible_range.range_kind is NutritionRangeKind.FLEXIBLE_REMAINDER


def test_public_envelope_scalars_are_builtin_python_values(profile: UserProfile) -> None:
    envelope = calculate_nutrition_target_envelope(
        profile,
        2400,
        MacroCalorieSource.PERSONALIZED,
        NutritionPreferences(MacroStrategy.HIGHER_PROTEIN),
    )

    assert type(envelope.selected_calorie_target_kcal_per_day) is float
    assert type(envelope.range_policy_version) is str
    assert type(envelope.macro_policy_version) is str
    assert type(envelope.policy_floors) is tuple
    assert type(envelope.assumptions) is tuple
    for target in (
        envelope.calorie_adherence_range,
        envelope.protein_preferred_range,
        envelope.fat_preferred_range,
        envelope.carbohydrate_flexible_range,
    ):
        assert type(target.lower_bound) is float
        assert type(target.selected_value) is float
        assert type(target.upper_bound) is float
        assert type(target.unit) is str
        assert type(target.interpretation) is str
        assert isinstance(target.range_kind, NutritionRangeKind)
