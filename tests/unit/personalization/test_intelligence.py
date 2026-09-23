"""Composition contracts for the unified stateless profile-intelligence operation."""

from dataclasses import FrozenInstanceError, astuple
from datetime import date, timedelta
from math import isfinite

import pytest

from fitadapt.adaptive.tdee import AdaptiveTdeeConfig, estimate_adaptive_tdee
from fitadapt.analysis.trends import (
    TrendAnalysisConfig,
    TrendAnalysisError,
    analyze_observation_trends,
)
from fitadapt.baseline.targets import calculate_calorie_target
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.intelligence import (
    ProfileIntelligenceError,
    ProfileIntelligenceResult,
    analyze_profile_intelligence,
)
from fitadapt.personalization.lifecycle import (
    PersonalizationLifecycleConfig,
    PersonalizationStage,
    assess_personalization_lifecycle,
)
from fitadapt.personalization.macros import MacroStrategy, NutritionPreferences
from fitadapt.personalization.planning import (
    PlanCalorieBasis,
    build_personalized_plan_progression,
    build_personalized_plan_snapshot,
)
from fitadapt.recommendation.calories import (
    CalorieRecommendationConfig,
    RecommendationReason,
    recommend_calorie_adjustment,
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


@pytest.fixture
def preferences() -> NutritionPreferences:
    return NutritionPreferences(MacroStrategy.BALANCED)


def _history(
    days: int,
    *,
    weight_change_per_day: float = -0.03,
    intake: float | None = 2400.0,
    start: date = date(2026, 1, 1),
) -> tuple[DailyObservation, ...]:
    return tuple(
        DailyObservation(
            observed_on=start + timedelta(days=index),
            body_weight_kg=80.0 + weight_change_per_day * index,
            energy_intake_kcal=intake,
            steps=5000,
        )
        for index in range(days)
    )


@pytest.mark.parametrize(
    ("days", "expected_stage"),
    [
        (0, PersonalizationStage.BASELINE),
        (1, PersonalizationStage.CALIBRATING),
        (11, PersonalizationStage.EARLY_PERSONALIZED),
        (14, PersonalizationStage.PERSONALIZED),
    ],
)
def test_sections_match_direct_public_components_for_each_lifecycle_stage(
    profile: UserProfile,
    preferences: NutritionPreferences,
    days: int,
    expected_stage: PersonalizationStage,
) -> None:
    observations = _history(days)
    result = analyze_profile_intelligence(profile, observations, preferences)
    trends = analyze_observation_trends(observations)

    assert result.baseline == calculate_calorie_target(profile)
    assert result.trends == trends
    assert result.adaptive_tdee == estimate_adaptive_tdee(trends)
    assert result.lifecycle == assess_personalization_lifecycle(profile, observations)
    assert result.recommendation == recommend_calorie_adjustment(profile, observations)
    assert result.latest_plan == build_personalized_plan_snapshot(
        profile, observations, preferences
    )
    assert result.lifecycle.stage is expected_stage
    assert result.latest_plan.lifecycle_stage is result.lifecycle.stage
    assert (
        result.latest_plan.adaptive_tdee_kcal_per_day
        == result.adaptive_tdee.adaptive_tdee_kcal_per_day
    )
    assert result.latest_plan.recommendation_reasons == result.recommendation.reasons
    assert result.plan_progression is None


def test_empty_history_is_a_complete_undated_baseline_result(
    profile: UserProfile, preferences: NutritionPreferences
) -> None:
    result = analyze_profile_intelligence(profile, (), preferences, include_plan_progression=True)

    assert result.trends.points == ()
    assert result.adaptive_tdee.daily_estimates == ()
    assert result.lifecycle.stage is PersonalizationStage.BASELINE
    assert result.latest_plan.as_of_date is None
    assert result.latest_plan.calorie_basis is PlanCalorieBasis.BASELINE
    assert result.plan_progression is not None
    assert result.plan_progression.snapshots == ()


def test_requested_progression_is_chronological_prefix_only_and_matches_latest_plan(
    profile: UserProfile, preferences: NutritionPreferences
) -> None:
    observations = _history(14)
    result = analyze_profile_intelligence(
        profile, tuple(reversed(observations)), preferences, include_plan_progression=True
    )

    assert result.plan_progression == build_personalized_plan_progression(
        profile, tuple(reversed(observations)), preferences
    )
    assert result.plan_progression is not None
    assert len(result.plan_progression.snapshots) == len(observations)
    assert result.plan_progression.snapshots[-1] == result.latest_plan
    assert [item.as_of_date for item in result.plan_progression.snapshots] == [
        item.observed_on for item in observations
    ]
    assert len(result.trends.points) == len(observations)


def test_personalized_plan_and_macro_strategy_are_composed_without_changing_evidence(
    profile: UserProfile,
) -> None:
    observations = _history(21, weight_change_per_day=-0.10)
    balanced = analyze_profile_intelligence(
        profile, observations, NutritionPreferences(MacroStrategy.BALANCED)
    )
    custom = analyze_profile_intelligence(
        profile, observations, NutritionPreferences(MacroStrategy.CUSTOM, 2.2, 0.30)
    )

    assert balanced.latest_plan.calorie_basis is PlanCalorieBasis.PERSONALIZED
    assert balanced.latest_plan.selected_calorie_target_kcal_per_day == (
        balanced.recommendation.proposed_intake_target_kcal_per_day
    )
    assert balanced.baseline == custom.baseline
    assert balanced.trends == custom.trends
    assert balanced.adaptive_tdee == custom.adaptive_tdee
    assert balanced.lifecycle == custom.lifecycle
    assert balanced.recommendation == custom.recommendation
    assert balanced.latest_plan.macro_plan != custom.latest_plan.macro_plan
    assert custom.latest_plan.macro_plan.strategy is MacroStrategy.CUSTOM
    for result in (balanced, custom):
        macro = result.latest_plan.macro_plan
        macro_calories = (
            macro.protein_kcal_per_day + macro.fat_kcal_per_day + macro.carbohydrate_kcal_per_day
        )
        assert macro_calories == pytest.approx(
            result.latest_plan.selected_calorie_target_kcal_per_day
        )


def test_unsafe_personalized_recommendation_remains_visible_but_plan_falls_back(
    profile: UserProfile, preferences: NutritionPreferences
) -> None:
    result = analyze_profile_intelligence(profile, _history(28, intake=0.0), preferences)

    assert result.lifecycle.stage is PersonalizationStage.PERSONALIZED
    assert (
        RecommendationReason.MACRO_POLICY_INFEASIBLE_PROPOSED_TARGET
        in result.recommendation.reasons
    )
    assert result.latest_plan.calorie_basis is PlanCalorieBasis.BASELINE
    assert result.latest_plan.selected_calorie_target_kcal_per_day == (
        result.baseline.target_calories_kcal_per_day
    )
    assert result.latest_plan.recommendation_reasons == result.recommendation.reasons


def test_missing_and_zero_intake_are_distinct_and_sparse_history_is_supported(
    profile: UserProfile, preferences: NutritionPreferences
) -> None:
    zero = analyze_profile_intelligence(profile, _history(14, intake=0.0), preferences)
    missing = analyze_profile_intelligence(profile, _history(14, intake=None), preferences)
    sparse = analyze_profile_intelligence(
        profile,
        (DailyObservation(observed_on=date(2026, 1, 1), sleep_hours=8.0),),
        preferences,
    )

    assert zero.trends.data_quality.present_energy_intake_values == 14
    assert missing.trends.data_quality.present_energy_intake_values == 0
    assert zero.recommendation.recent_mean_intake_kcal_per_day == 0.0
    assert missing.recommendation.recent_mean_intake_kcal_per_day is None
    assert sparse.lifecycle.stage is PersonalizationStage.BASELINE


def test_duplicate_dates_propagate_existing_trend_error(
    profile: UserProfile, preferences: NutritionPreferences
) -> None:
    observation = _history(1)[0]

    with pytest.raises(TrendAnalysisError, match="Duplicate observed_on dates"):
        analyze_profile_intelligence(profile, (observation, observation), preferences)


@pytest.mark.parametrize("invalid_flag", [0, 1, "true", None])
def test_progression_flag_must_be_a_real_boolean(
    profile: UserProfile, preferences: NutritionPreferences, invalid_flag: object
) -> None:
    with pytest.raises(ProfileIntelligenceError, match="include_plan_progression"):
        analyze_profile_intelligence(
            profile,
            (),
            preferences,
            include_plan_progression=invalid_flag,  # type: ignore[arg-type]
        )


def test_domain_input_types_are_explicitly_validated(
    profile: UserProfile, preferences: NutritionPreferences
) -> None:
    with pytest.raises(ProfileIntelligenceError, match="profile"):
        analyze_profile_intelligence("profile", (), preferences)  # type: ignore[arg-type]
    with pytest.raises(ProfileIntelligenceError, match="preferences"):
        analyze_profile_intelligence(profile, (), "preferences")  # type: ignore[arg-type]
    with pytest.raises(ProfileIntelligenceError, match="observations"):
        analyze_profile_intelligence(profile, "observations", preferences)  # type: ignore[arg-type]


def test_existing_configurations_are_preserved_without_mutation(
    profile: UserProfile, preferences: NutritionPreferences
) -> None:
    trend_config = TrendAnalysisConfig(window_size_days=5, minimum_observations=3)
    adaptive_config = AdaptiveTdeeConfig(aggregation_window_days=7, minimum_estimate_points=3)
    lifecycle_config = PersonalizationLifecycleConfig(minimum_calendar_history_days=5)
    recommendation_config = CalorieRecommendationConfig(minimum_calendar_history_days=5)
    before = tuple(
        astuple(item)
        for item in (trend_config, adaptive_config, lifecycle_config, recommendation_config)
    )

    result = analyze_profile_intelligence(
        profile,
        _history(14),
        preferences,
        trend_config,
        adaptive_config,
        lifecycle_config,
        recommendation_config,
    )

    after = tuple(
        astuple(item)
        for item in (trend_config, adaptive_config, lifecycle_config, recommendation_config)
    )
    assert before == after
    assert result.trends.config == trend_config
    assert result.adaptive_tdee.config == adaptive_config


def test_result_is_frozen_slotted_plain_deterministic_and_does_not_mutate_inputs(
    profile: UserProfile, preferences: NutritionPreferences
) -> None:
    observations = list(_history(14))
    before = (astuple(profile), tuple(astuple(item) for item in observations), astuple(preferences))
    first = analyze_profile_intelligence(profile, observations, preferences)
    second = analyze_profile_intelligence(profile, observations, preferences)

    assert first == second
    after = (astuple(profile), tuple(astuple(item) for item in observations), astuple(preferences))
    assert before == after
    assert type(first) is ProfileIntelligenceResult
    assert not hasattr(first, "__dict__")
    assert isinstance(first.assumptions, tuple)
    assert type(first.baseline.target_calories_kcal_per_day) is float
    assert type(first.lifecycle.eligible_adaptive_estimate_count) is int
    assert all(isfinite(value) for value in (first.baseline.target_calories_kcal_per_day,))
    with pytest.raises(FrozenInstanceError):
        first.policy_version = "other"  # type: ignore[misc]
