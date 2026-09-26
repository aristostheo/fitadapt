"""Training-aware macro policy contracts and calorie invariants."""

from dataclasses import FrozenInstanceError
from datetime import date, timedelta

import pytest

from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.macros import (
    MacroCalorieSource,
    MacroStrategy,
    NutritionPreferences,
    calculate_personalized_macro_plan,
)
from fitadapt.personalization.targets import calculate_nutrition_target_envelope
from fitadapt.personalization.training import (
    OccupationActivity,
    PrimaryTrainingFocus,
    TrainingContext,
    TrainingIntensity,
    assess_training_demand,
)
from fitadapt.personalization.training_nutrition import (
    TrainingAwareMacroConfig,
    TrainingAwareMacroError,
)


def profile() -> UserProfile:
    return UserProfile(
        30, 180, 80, SexForMifflinEquation.MALE, ActivityLevel.MODERATELY_ACTIVE, Goal.MAINTAIN, 0
    )


def observed(
    days: int = 14, strength: float | None = 0, cardio: float | None = 0
) -> tuple[DailyObservation, ...]:
    return tuple(
        DailyObservation(
            date(2026, 1, 1) + timedelta(days=i),
            steps=5000,
            strength_training_minutes=strength,
            cardio_minutes=cardio,
        )
        for i in range(days)
    )


def plan_with(assessment=None, calories=2400):
    return calculate_personalized_macro_plan(
        profile(),
        calories,
        MacroCalorieSource.BASELINE,
        NutritionPreferences(MacroStrategy.BALANCED),
        assessment,
    )


def test_missing_or_insufficient_training_preserves_default_macro_plan() -> None:
    default = plan_with()
    insufficient = plan_with(assess_training_demand(None, observed(2)))
    assert insufficient == default
    assert insufficient.training_adjustment_applied is False


def test_resistance_training_raises_protein_without_changing_calories() -> None:
    assessment = assess_training_demand(
        TrainingContext(
            OccupationActivity.MOSTLY_SEATED,
            4,
            240,
            primary_training_focus=PrimaryTrainingFocus.RESISTANCE,
        )
    )
    default = plan_with()
    aware = plan_with(assessment)
    assert aware.protein_g_per_day > default.protein_g_per_day
    assert aware.carbohydrate_g_per_day < default.carbohydrate_g_per_day
    assert aware.calorie_target_kcal_per_day == default.calorie_target_kcal_per_day == 2400.0
    assert aware.training_adjustment_applied is True
    assert aware.protein_policy_source == "training_aware"
    assert aware.protein_priority == "high"


def test_endurance_and_sport_prioritize_carbohydrates_with_fixed_calories() -> None:
    assessment = assess_training_demand(
        TrainingContext(
            OccupationActivity.MOSTLY_SEATED,
            cardio_days_per_week=5,
            cardio_minutes_per_week=360,
            cardio_intensity=TrainingIntensity.VIGOROUS,
            primary_training_focus=PrimaryTrainingFocus.ENDURANCE,
        )
    )
    default = plan_with()
    aware = plan_with(assessment)
    assert aware.protein_g_per_day == default.protein_g_per_day
    assert aware.carbohydrate_g_per_day > default.carbohydrate_g_per_day
    assert aware.fat_g_per_day < default.fat_g_per_day
    assert aware.carbohydrate_performance_priority == "high"
    assert aware.calorie_target_kcal_per_day == 2400.0


def test_mixed_training_preserves_feasibility_and_envelope_selected_plan() -> None:
    assessment = assess_training_demand(
        TrainingContext(
            OccupationActivity.MIXED,
            4,
            240,
            cardio_days_per_week=4,
            cardio_minutes_per_week=240,
            cardio_intensity=TrainingIntensity.MODERATE,
            primary_training_focus=PrimaryTrainingFocus.MIXED,
        )
    )
    envelope = calculate_nutrition_target_envelope(
        profile(),
        2400,
        MacroCalorieSource.BASELINE,
        NutritionPreferences(MacroStrategy.BALANCED),
        training_assessment=assessment,
    )
    plan = envelope.macro_plan
    assert (
        plan.protein_kcal_per_day + plan.fat_kcal_per_day + plan.carbohydrate_kcal_per_day
        == pytest.approx(2400.0)
    )
    assert envelope.selected_calorie_target_kcal_per_day == 2400.0
    assert plan.training_reason_codes


def test_low_calorie_target_reports_constraint_without_impossible_totals() -> None:
    assessment = assess_training_demand(
        TrainingContext(
            OccupationActivity.MOSTLY_SEATED,
            5,
            360,
            primary_training_focus=PrimaryTrainingFocus.RESISTANCE,
        )
    )
    plan = plan_with(assessment, calories=900)
    assert (
        plan.protein_kcal_per_day + plan.fat_kcal_per_day + plan.carbohydrate_kcal_per_day
        == pytest.approx(900.0)
    )
    assert "calorie_budget_limited_preferred_protein_target" in plan.training_reason_codes
    assert plan.fat_percentage >= 0.20


def test_training_does_not_change_target_calculation() -> None:
    assessment = assess_training_demand(
        TrainingContext(
            OccupationActivity.MOSTLY_SEATED,
            4,
            240,
            primary_training_focus=PrimaryTrainingFocus.RESISTANCE,
        )
    )
    default = calculate_nutrition_target_envelope(
        profile(), 2400, MacroCalorieSource.BASELINE, NutritionPreferences(MacroStrategy.BALANCED)
    )
    aware = calculate_nutrition_target_envelope(
        profile(),
        2400,
        MacroCalorieSource.BASELINE,
        NutritionPreferences(MacroStrategy.BALANCED),
        training_assessment=assessment,
    )
    assert (
        default.selected_calorie_target_kcal_per_day == aware.selected_calorie_target_kcal_per_day
    )
    assert default.calorie_adherence_range == aware.calorie_adherence_range


def test_training_aware_policy_config_is_frozen_and_validated() -> None:
    config = TrainingAwareMacroConfig()
    assert config.policy_version == "training_aware_macros_v1"
    with pytest.raises(FrozenInstanceError):
        config.policy_version = "other"  # type: ignore[misc]
    with pytest.raises(TrainingAwareMacroError):
        TrainingAwareMacroConfig(high_resistance_protein_g_per_kg=1.0)
