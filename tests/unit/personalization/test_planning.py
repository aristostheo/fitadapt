"""Composition contracts for entry-by-entry personalized plan proposals."""

from dataclasses import FrozenInstanceError, astuple
from datetime import date, timedelta
from math import isfinite

import pytest

from fitadapt.adaptive.tdee import AdaptiveTdeeConfig
from fitadapt.analysis.trends import TrendAnalysisConfig, TrendAnalysisError
from fitadapt.baseline.targets import calculate_calorie_target
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.lifecycle import (
    PersonalizationLifecycleConfig,
    PersonalizationStage,
    assess_personalization_lifecycle,
)
from fitadapt.personalization.macros import (
    MacroCalorieSource,
    MacroStrategy,
    NutritionPreferences,
    calculate_personalized_macro_plan,
)
from fitadapt.personalization.planning import (
    PERSONALIZED_PLANNING_POLICY_VERSION,
    PersonalizedPlanProgression,
    PersonalizedPlanSnapshot,
    PlanCalorieBasis,
    build_personalized_plan_progression,
    build_personalized_plan_snapshot,
)
from fitadapt.recommendation.calories import (
    CalorieRecommendationConfig,
    RecommendationReason,
    RecommendationStatus,
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
def balanced_preferences() -> NutritionPreferences:
    return NutritionPreferences(MacroStrategy.BALANCED)


def _history(
    days: int,
    *,
    weight_change_per_day: float = -0.03,
    intake: float | None = 2400.0,
    include_weight: bool = True,
    start: date = date(2026, 1, 1),
) -> tuple[DailyObservation, ...]:
    return tuple(
        DailyObservation(
            observed_on=start + timedelta(days=index),
            body_weight_kg=80.0 + weight_change_per_day * index if include_weight else None,
            energy_intake_kcal=intake,
            steps=5000,
        )
        for index in range(days)
    )


def test_empty_history_returns_explicit_undated_baseline_snapshot(
    profile: UserProfile, balanced_preferences: NutritionPreferences
) -> None:
    snapshot = build_personalized_plan_snapshot(profile, (), balanced_preferences)
    progression = build_personalized_plan_progression(profile, (), balanced_preferences)
    baseline = calculate_calorie_target(profile)

    assert snapshot.as_of_date is None
    assert snapshot.lifecycle_stage is PersonalizationStage.BASELINE
    assert snapshot.calorie_basis is PlanCalorieBasis.BASELINE
    assert snapshot.selected_calorie_target_kcal_per_day == baseline.target_calories_kcal_per_day
    assert snapshot.previous_selected_calorie_target_kcal_per_day is None
    assert snapshot.change_from_previous_snapshot_kcal_per_day is None
    assert snapshot.macro_plan.calorie_source is MacroCalorieSource.BASELINE
    assert progression.snapshots == ()
    assert progression.submitted_observation_count == 0


def test_progression_is_chronological_and_matches_latest_snapshot(
    profile: UserProfile, balanced_preferences: NutritionPreferences
) -> None:
    observations = _history(3)
    progression = build_personalized_plan_progression(
        profile, tuple(reversed(observations)), balanced_preferences
    )
    latest = build_personalized_plan_snapshot(
        profile, tuple(reversed(observations)), balanced_preferences
    )

    assert len(progression.snapshots) == len(observations)
    assert [item.as_of_date for item in progression.snapshots] == [
        item.observed_on for item in observations
    ]
    assert latest == progression.snapshots[-1]
    assert progression.submitted_observation_count == 3


def test_one_sparse_observation_returns_one_dated_baseline_snapshot(
    profile: UserProfile, balanced_preferences: NutritionPreferences
) -> None:
    observation = DailyObservation(
        observed_on=date(2026, 1, 1),
        sleep_hours=8.0,
        hunger_rating=3,
        energy_rating=4,
    )

    progression = build_personalized_plan_progression(profile, (observation,), balanced_preferences)

    assert len(progression.snapshots) == 1
    snapshot = progression.snapshots[0]
    assert snapshot.as_of_date == observation.observed_on
    assert snapshot.lifecycle_stage is PersonalizationStage.BASELINE
    assert snapshot.calorie_basis is PlanCalorieBasis.BASELINE
    assert snapshot.previous_selected_calorie_target_kcal_per_day is None
    assert snapshot.change_from_previous_snapshot_kcal_per_day is None


def test_duplicate_dates_propagate_existing_trend_error(
    profile: UserProfile, balanced_preferences: NutritionPreferences
) -> None:
    observation = _history(1)[0]

    with pytest.raises(TrendAnalysisError, match="Duplicate observed_on dates"):
        build_personalized_plan_progression(
            profile, (observation, observation), balanced_preferences
        )


@pytest.mark.parametrize(
    ("observations", "expected_stage"),
    [
        (_history(1), PersonalizationStage.CALIBRATING),
        (_history(11), PersonalizationStage.EARLY_PERSONALIZED),
        (
            (DailyObservation(observed_on=date(2026, 1, 1), steps=5000),),
            PersonalizationStage.BASELINE,
        ),
        (_history(1, include_weight=False), PersonalizationStage.CALIBRATING),
        (_history(1, intake=None), PersonalizationStage.CALIBRATING),
    ],
)
def test_non_personalized_stages_select_baseline_target(
    profile: UserProfile,
    balanced_preferences: NutritionPreferences,
    observations: tuple[DailyObservation, ...],
    expected_stage: PersonalizationStage,
) -> None:
    snapshot = build_personalized_plan_snapshot(profile, observations, balanced_preferences)
    baseline = calculate_calorie_target(profile)

    assert snapshot.lifecycle_stage is expected_stage
    assert snapshot.calorie_basis is PlanCalorieBasis.BASELINE
    assert snapshot.selected_calorie_target_kcal_per_day == baseline.target_calories_kcal_per_day
    assert snapshot.macro_plan.calorie_source is MacroCalorieSource.BASELINE


def test_personalized_stage_uses_exact_existing_recommendation_target(
    profile: UserProfile, balanced_preferences: NutritionPreferences
) -> None:
    observations = _history(28, weight_change_per_day=-0.10)
    recommendation = recommend_calorie_adjustment(profile, observations)
    snapshot = build_personalized_plan_snapshot(profile, observations, balanced_preferences)
    expected_macro = calculate_personalized_macro_plan(
        profile,
        recommendation.proposed_intake_target_kcal_per_day,
        MacroCalorieSource.PERSONALIZED,
        balanced_preferences,
    )

    assert snapshot.lifecycle_stage is PersonalizationStage.PERSONALIZED
    assert recommendation.status is RecommendationStatus.INCREASE_CALORIES
    assert snapshot.calorie_basis is PlanCalorieBasis.PERSONALIZED
    assert (
        snapshot.selected_calorie_target_kcal_per_day
        == recommendation.proposed_intake_target_kcal_per_day
    )
    assert snapshot.raw_recommendation_adjustment_kcal_per_day == (
        recommendation.raw_adjustment_kcal_per_day
    )
    assert snapshot.limited_recommendation_adjustment_kcal_per_day == (
        recommendation.recommended_adjustment_kcal_per_day
    )
    assert snapshot.recommendation_reasons == recommendation.reasons
    assert snapshot.macro_plan == expected_macro


def test_personalized_unavailable_recommendation_falls_back_to_baseline(
    profile: UserProfile, balanced_preferences: NutritionPreferences
) -> None:
    observations = _history(28, weight_change_per_day=0.0, intake=0.0)
    recommendation = recommend_calorie_adjustment(profile, observations)
    snapshot = build_personalized_plan_snapshot(profile, observations, balanced_preferences)

    assert snapshot.lifecycle_stage is PersonalizationStage.PERSONALIZED
    assert recommendation.status is RecommendationStatus.INSUFFICIENT_DATA
    assert RecommendationReason.NON_POSITIVE_PROPOSED_TARGET in recommendation.reasons
    assert snapshot.calorie_basis is PlanCalorieBasis.BASELINE
    assert (
        snapshot.selected_calorie_target_kcal_per_day
        == snapshot.baseline_calorie_target_kcal_per_day
    )
    assert snapshot.macro_plan.calorie_source is MacroCalorieSource.BASELINE
    assert snapshot.recommendation_reasons == recommendation.reasons
    assert "no actionable safe recommendation" in snapshot.assumptions[-1]


def test_zero_and_missing_intake_remain_distinct(
    profile: UserProfile, balanced_preferences: NutritionPreferences
) -> None:
    zero_intake = build_personalized_plan_snapshot(
        profile, _history(28, weight_change_per_day=0.0, intake=0.0), balanced_preferences
    )
    missing_intake = build_personalized_plan_snapshot(
        profile, _history(28, weight_change_per_day=0.0, intake=None), balanced_preferences
    )

    assert zero_intake.lifecycle_stage is PersonalizationStage.PERSONALIZED
    assert zero_intake.recommendation_status is RecommendationStatus.INSUFFICIENT_DATA
    assert RecommendationReason.NON_POSITIVE_PROPOSED_TARGET in zero_intake.recommendation_reasons
    assert missing_intake.lifecycle_stage is PersonalizationStage.CALIBRATING
    assert missing_intake.adaptive_tdee_kcal_per_day is None
    assert missing_intake.recommendation_status is RecommendationStatus.INSUFFICIENT_DATA
    assert RecommendationReason.MISSING_RECENT_INTAKE in missing_intake.recommendation_reasons


@pytest.mark.parametrize(
    ("weight_change_per_day", "expected_status", "expected_limited"),
    [
        (0.0, RecommendationStatus.HOLD, 0.0),
        (-110.0 / 7700.0, RecommendationStatus.INCREASE_CALORIES, 110.0),
        (110.0 / 7700.0, RecommendationStatus.DECREASE_CALORIES, -110.0),
        (-0.03, RecommendationStatus.INCREASE_CALORIES, 150.0),
    ],
)
def test_existing_recommendation_hold_direction_and_cap_are_preserved(
    profile: UserProfile,
    balanced_preferences: NutritionPreferences,
    weight_change_per_day: float,
    expected_status: RecommendationStatus,
    expected_limited: float,
) -> None:
    observations = _history(28, weight_change_per_day=weight_change_per_day)
    recommendation = recommend_calorie_adjustment(profile, observations)
    snapshot = build_personalized_plan_snapshot(profile, observations, balanced_preferences)

    assert recommendation.status is expected_status
    assert recommendation.recommended_adjustment_kcal_per_day == pytest.approx(expected_limited)
    assert snapshot.recommendation_status is recommendation.status
    assert snapshot.limited_recommendation_adjustment_kcal_per_day == pytest.approx(
        expected_limited
    )
    assert (
        snapshot.selected_calorie_target_kcal_per_day
        == recommendation.proposed_intake_target_kcal_per_day
    )


def test_macro_strategy_changes_allocation_not_evidence_or_calorie_target(
    profile: UserProfile,
) -> None:
    observations = _history(28, weight_change_per_day=-0.10)
    balanced = build_personalized_plan_snapshot(
        profile, observations, NutritionPreferences(MacroStrategy.BALANCED)
    )
    higher_carb = build_personalized_plan_snapshot(
        profile, observations, NutritionPreferences(MacroStrategy.HIGHER_CARB)
    )
    custom = build_personalized_plan_snapshot(
        profile, observations, NutritionPreferences(MacroStrategy.CUSTOM, 2.2, 0.30)
    )

    assert balanced.lifecycle_stage is higher_carb.lifecycle_stage is custom.lifecycle_stage
    assert balanced.adaptive_tdee_kcal_per_day == higher_carb.adaptive_tdee_kcal_per_day
    assert (
        balanced.selected_calorie_target_kcal_per_day
        == higher_carb.selected_calorie_target_kcal_per_day
    )
    assert balanced.macro_plan != higher_carb.macro_plan
    assert custom.macro_plan.strategy is MacroStrategy.CUSTOM
    for snapshot in (balanced, higher_carb, custom):
        macros = snapshot.macro_plan
        assert (
            macros.protein_kcal_per_day + macros.fat_kcal_per_day + macros.carbohydrate_kcal_per_day
            == pytest.approx(snapshot.selected_calorie_target_kcal_per_day)
        )


def test_previous_target_change_and_append_only_prefix_isolation(
    profile: UserProfile, balanced_preferences: NutritionPreferences
) -> None:
    initial = _history(21, weight_change_per_day=-0.10)
    appended = (*initial, *_history(1, start=date(2026, 2, 1), weight_change_per_day=-0.10))
    before = build_personalized_plan_progression(profile, initial, balanced_preferences)
    after = build_personalized_plan_progression(profile, appended, balanced_preferences)

    assert after.snapshots[:-1] == before.snapshots
    assert len(after.snapshots) == len(before.snapshots) + 1
    last = after.snapshots[-1]
    assert (
        last.previous_selected_calorie_target_kcal_per_day
        == before.snapshots[-1].selected_calorie_target_kcal_per_day
    )
    assert last.change_from_previous_snapshot_kcal_per_day == pytest.approx(
        last.selected_calorie_target_kcal_per_day
        - last.previous_selected_calorie_target_kcal_per_day
    )
    assert before.snapshots[0].previous_selected_calorie_target_kcal_per_day is None
    assert before.snapshots[0].change_from_previous_snapshot_kcal_per_day is None


def test_documented_progression_example_is_generated_by_the_planning_contract(
    profile: UserProfile, balanced_preferences: NutritionPreferences
) -> None:
    progression = build_personalized_plan_progression(
        profile, _history(21, weight_change_per_day=-0.10), balanced_preferences
    )
    selected = (progression.snapshots[0], progression.snapshots[10], progression.snapshots[-1])

    assert [item.as_of_date for item in selected] == [
        date(2026, 1, 1),
        date(2026, 1, 11),
        date(2026, 1, 21),
    ]
    assert [item.lifecycle_stage for item in selected] == [
        PersonalizationStage.CALIBRATING,
        PersonalizationStage.EARLY_PERSONALIZED,
        PersonalizationStage.PERSONALIZED,
    ]
    assert [item.calorie_basis for item in selected] == [
        PlanCalorieBasis.BASELINE,
        PlanCalorieBasis.BASELINE,
        PlanCalorieBasis.PERSONALIZED,
    ]
    assert [item.selected_calorie_target_kcal_per_day for item in selected] == [
        2759.0,
        2759.0,
        2550.0,
    ]


def test_future_observation_cannot_change_earlier_snapshot(
    profile: UserProfile, balanced_preferences: NutritionPreferences
) -> None:
    observations = _history(21)
    changed_future = (
        *observations[:-1],
        DailyObservation(
            observed_on=observations[-1].observed_on,
            body_weight_kg=70.0,
            energy_intake_kcal=5000.0,
            steps=0,
        ),
    )
    original = build_personalized_plan_progression(profile, observations, balanced_preferences)
    changed = build_personalized_plan_progression(profile, changed_future, balanced_preferences)

    assert changed.snapshots[:-1] == original.snapshots[:-1]
    assert all(
        item.as_of_date is not None and item.as_of_date <= observations[index].observed_on
        for index, item in enumerate(original.snapshots)
    )


def test_snapshot_components_match_direct_public_calculations(
    profile: UserProfile, balanced_preferences: NutritionPreferences
) -> None:
    observations = _history(28, weight_change_per_day=-0.10)
    snapshot = build_personalized_plan_snapshot(profile, observations, balanced_preferences)
    lifecycle = assess_personalization_lifecycle(profile, observations)
    recommendation = recommend_calorie_adjustment(profile, observations)

    assert snapshot.lifecycle_stage is lifecycle.stage
    assert snapshot.lifecycle_requirements == lifecycle.requirements
    assert snapshot.adaptive_tdee_kcal_per_day == lifecycle.adaptive_tdee_kcal_per_day
    assert snapshot.recommendation_status is recommendation.status
    assert snapshot.recommendation_reasons == recommendation.reasons
    assert snapshot.planning_policy_version == PERSONALIZED_PLANNING_POLICY_VERSION
    assert snapshot.lifecycle_policy_version == lifecycle.lifecycle_policy_version


def test_models_are_immutable_plain_and_do_not_mutate_inputs(
    profile: UserProfile, balanced_preferences: NutritionPreferences
) -> None:
    observations = list(_history(21))
    trend_config = TrendAnalysisConfig()
    adaptive_config = AdaptiveTdeeConfig()
    lifecycle_config = PersonalizationLifecycleConfig()
    recommendation_config = CalorieRecommendationConfig()
    snapshot_before = (
        astuple(profile),
        tuple(astuple(item) for item in observations),
        astuple(balanced_preferences),
        astuple(trend_config),
        astuple(adaptive_config),
        astuple(lifecycle_config),
        astuple(recommendation_config),
    )
    progression = build_personalized_plan_progression(
        profile,
        observations,
        balanced_preferences,
        trend_config,
        adaptive_config,
        lifecycle_config,
        recommendation_config,
    )
    snapshot = progression.snapshots[-1]

    assert snapshot_before == (
        astuple(profile),
        tuple(astuple(item) for item in observations),
        astuple(balanced_preferences),
        astuple(trend_config),
        astuple(adaptive_config),
        astuple(lifecycle_config),
        astuple(recommendation_config),
    )
    assert build_personalized_plan_progression(profile, observations, balanced_preferences) == (
        build_personalized_plan_progression(profile, observations, balanced_preferences)
    )
    assert type(snapshot) is PersonalizedPlanSnapshot
    assert type(progression) is PersonalizedPlanProgression
    assert type(snapshot.as_of_date) is date
    assert type(snapshot.selected_calorie_target_kcal_per_day) is float
    assert type(snapshot.eligible_adaptive_estimate_count) is int
    assert isfinite(snapshot.selected_calorie_target_kcal_per_day)
    assert snapshot.selected_calorie_target_kcal_per_day > 0
    assert isinstance(snapshot.assumptions, tuple)
    assert isinstance(progression.snapshots, tuple)
    with pytest.raises(FrozenInstanceError):
        snapshot.calorie_basis = PlanCalorieBasis.BASELINE  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        progression.submitted_observation_count = 0  # type: ignore[misc]
    with pytest.raises(AttributeError):
        progression.snapshots.append(snapshot)  # type: ignore[attr-defined]


def test_public_contract_retains_versions_precision_and_feasible_macros(
    profile: UserProfile, balanced_preferences: NutritionPreferences
) -> None:
    progression = build_personalized_plan_progression(
        profile, _history(21, weight_change_per_day=-0.10), balanced_preferences
    )

    assert not hasattr(progression, "__dict__")
    assert all(not hasattr(snapshot, "__dict__") for snapshot in progression.snapshots)
    assert progression.assumptions == (
        build_personalized_plan_progression(
            profile, _history(21, weight_change_per_day=-0.10), balanced_preferences
        ).assumptions
    )
    for snapshot in progression.snapshots:
        assert type(snapshot.as_of_date) is date
        assert type(snapshot.baseline_calorie_target_kcal_per_day) is float
        assert type(snapshot.selected_calorie_target_kcal_per_day) is float
        assert type(snapshot.eligible_adaptive_estimate_count) is int
        assert snapshot.selected_calorie_target_kcal_per_day > 0
        assert snapshot.macro_plan.calorie_target_kcal_per_day == pytest.approx(
            snapshot.selected_calorie_target_kcal_per_day
        )
        assert snapshot.macro_plan.carbohydrate_g_per_day >= 0
        assert all(
            isinstance(version, str) and version
            for version in (
                snapshot.planning_policy_version,
                snapshot.baseline_energy_formula_version,
                snapshot.baseline_activity_policy_version,
                snapshot.baseline_energy_equivalent_policy_version,
                snapshot.baseline_macro_policy_version,
                snapshot.lifecycle_policy_version,
                snapshot.trend_policy_version,
                snapshot.adaptive_policy_version,
                snapshot.recommendation_policy_version,
                snapshot.personalized_macro_policy_version,
            )
        )
