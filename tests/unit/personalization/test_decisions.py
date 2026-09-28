"""Decision-policy contracts for proposal-only calorie adaptation."""

from dataclasses import replace
from datetime import date, timedelta

import pytest

from fitadapt.baseline.targets import minimum_macro_calories_kcal_per_day
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.decisions import (
    RecommendationDecisionConfig,
    RecommendationDecisionError,
    RecommendationDecisionReason,
    RecommendationDecisionType,
    decide_plan_adjustment,
)
from fitadapt.personalization.macros import (
    MacroCalorieSource,
    MacroStrategy,
    NutritionPreferences,
    calculate_personalized_macro_plan,
)
from fitadapt.personalization.outcomes import (
    GoalProgressStatus,
    IntakeAdherenceStatus,
    OutcomeInterpretability,
    WeightTrendStatus,
    assess_plan_outcome,
)


def _profile(goal: Goal = Goal.CUT, rate: float = -0.4) -> UserProfile:
    return UserProfile(
        age_years=30,
        height_cm=180,
        weight_kg=80,
        sex_for_mifflin_equation=SexForMifflinEquation.MALE,
        activity_level=ActivityLevel.MODERATELY_ACTIVE,
        goal=goal,
        requested_weekly_change_kg=rate,
    )


def _observations(days: int = 28, intake: float | None = 2400) -> tuple[DailyObservation, ...]:
    return tuple(
        DailyObservation(
            observed_on=date(2026, 1, 1) + timedelta(days=index),
            body_weight_kg=80 - 0.01 * index,
            energy_intake_kcal=intake,
        )
        for index in range(days)
    )


def _plan(profile: UserProfile, target: float = 2400):
    return calculate_personalized_macro_plan(
        profile, target, MacroCalorieSource.BASELINE, NutritionPreferences(MacroStrategy.BALANCED)
    )


def _outcome(profile: UserProfile, progress: GoalProgressStatus, rate: float = -0.1):
    outcome = assess_plan_outcome(profile, _observations(), 2400)
    return replace(
        outcome,
        overall_interpretability=OutcomeInterpretability.INTERPRETABLE,
        intake_adherence=IntakeAdherenceStatus.NEAR_TARGET,
        weight_trend_status=WeightTrendStatus.AVAILABLE,
        goal_progress=progress,
        observed_weight_change_kg_per_week=rate,
        weight_span_days=21,
    )


def test_unavailable_or_poor_adherence_defers_and_preserves_target() -> None:
    profile = _profile()
    plan = _plan(profile)
    outcome = assess_plan_outcome(profile, (), plan.calorie_target_kcal_per_day)

    result = decide_plan_adjustment(profile, plan.calorie_target_kcal_per_day, plan, outcome)

    assert result.decision is RecommendationDecisionType.DEFER
    assert result.numerical_change_proposed is False
    assert result.proposed_calorie_target_kcal_per_day == plan.calorie_target_kcal_per_day
    assert RecommendationDecisionReason.OUTCOME_UNAVAILABLE in result.reason_codes


def test_on_track_fat_loss_holds() -> None:
    profile = _profile()
    plan = _plan(profile)
    result = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        _outcome(profile, GoalProgressStatus.BROADLY_ON_TRACK),
    )

    assert result.decision is RecommendationDecisionType.HOLD
    assert result.calorie_delta_kcal_per_day == 0


def test_slow_fat_loss_proposes_decrease_and_fast_loss_increase() -> None:
    profile = _profile()
    plan = _plan(profile)
    slow = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        _outcome(profile, GoalProgressStatus.SLOWER_THAN_EXPECTED),
    )
    fast = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        _outcome(profile, GoalProgressStatus.FASTER_THAN_EXPECTED),
    )

    assert slow.decision is RecommendationDecisionType.DECREASE
    assert fast.decision is RecommendationDecisionType.INCREASE
    assert slow.calorie_delta_kcal_per_day == -100
    assert fast.calorie_delta_kcal_per_day == 100


@pytest.mark.parametrize(
    ("goal", "progress", "expected"),
    [
        (Goal.GAIN, GoalProgressStatus.SLOWER_THAN_EXPECTED, RecommendationDecisionType.INCREASE),
        (Goal.GAIN, GoalProgressStatus.FASTER_THAN_EXPECTED, RecommendationDecisionType.DECREASE),
    ],
)
def test_gain_direction_is_goal_aware(
    goal: Goal,
    progress: GoalProgressStatus,
    expected: RecommendationDecisionType,
) -> None:
    profile = _profile(goal, 0.4)
    plan = _plan(profile)

    result = decide_plan_adjustment(
        profile, plan.calorie_target_kcal_per_day, plan, _outcome(profile, progress)
    )

    assert result.decision is expected


def test_maintenance_drift_is_goal_aware() -> None:
    profile = _profile(Goal.MAINTAIN, 0)
    plan = _plan(profile)
    down = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        _outcome(profile, GoalProgressStatus.OUTSIDE_MAINTENANCE_RANGE, rate=-0.2),
    )
    up = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        _outcome(profile, GoalProgressStatus.OUTSIDE_MAINTENANCE_RANGE, rate=0.2),
    )

    assert down.decision is RecommendationDecisionType.INCREASE
    assert up.decision is RecommendationDecisionType.DECREASE


def test_floor_constraint_is_exposed() -> None:
    profile = _profile()
    plan = _plan(profile, 1100)
    config = RecommendationDecisionConfig(
        standard_adjustment_kcal_per_day=300,
        maximum_adjustment_kcal_per_day=300,
    )
    result = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        _outcome(profile, GoalProgressStatus.SLOWER_THAN_EXPECTED),
        config=config,
    )

    assert result.decision is RecommendationDecisionType.DECREASE
    assert result.proposed_calorie_target_kcal_per_day == minimum_macro_calories_kcal_per_day(
        profile
    )
    assert RecommendationDecisionReason.ADJUSTMENT_CLAMPED_TO_MINIMUM_TARGET in result.reason_codes


def test_adaptive_tdee_is_context_only() -> None:
    profile = _profile()
    plan = _plan(profile)
    result = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        _outcome(profile, GoalProgressStatus.SLOWER_THAN_EXPECTED),
        adaptive_tdee_kcal_per_day=3000,
    )

    assert result.decision is RecommendationDecisionType.DECREASE
    assert RecommendationDecisionReason.ADAPTIVE_TDEE_CONFLICTING in result.reason_codes


def test_explicit_upper_target_bound_is_exposed() -> None:
    profile = _profile(Goal.GAIN, 0.4)
    plan = _plan(profile)
    result = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        _outcome(profile, GoalProgressStatus.SLOWER_THAN_EXPECTED),
        config=RecommendationDecisionConfig(maximum_target_kcal_per_day=2450),
    )

    assert result.decision is RecommendationDecisionType.INCREASE
    assert result.proposed_calorie_target_kcal_per_day == 2450
    assert RecommendationDecisionReason.ADJUSTMENT_CLAMPED_TO_MAXIMUM_TARGET in result.reason_codes


def test_current_target_below_floor_defers_without_reversing_direction() -> None:
    profile = _profile()
    plan = _plan(profile, 900)
    outcome = _outcome(profile, GoalProgressStatus.SLOWER_THAN_EXPECTED)
    result = decide_plan_adjustment(profile, plan.calorie_target_kcal_per_day, plan, outcome)

    assert result.decision is RecommendationDecisionType.DEFER
    assert RecommendationDecisionReason.CURRENT_TARGET_BELOW_SAFETY_FLOOR in result.reason_codes


def test_invalid_decision_inputs_are_rejected() -> None:
    profile = _profile()
    plan = _plan(profile)
    outcome = _outcome(profile, GoalProgressStatus.BROADLY_ON_TRACK)
    with pytest.raises(RecommendationDecisionError):
        decide_plan_adjustment(profile, 1, plan, outcome)
    with pytest.raises(RecommendationDecisionError):
        decide_plan_adjustment(profile, plan.calorie_target_kcal_per_day, object(), outcome)  # type: ignore[arg-type]
    with pytest.raises(RecommendationDecisionError):
        RecommendationDecisionConfig(maximum_adjustment_kcal_per_day=10)
    with pytest.raises(RecommendationDecisionError):
        RecommendationDecisionConfig(standard_adjustment_kcal_per_day="100")  # type: ignore[arg-type]


def test_ineligible_target_safety_defers_decision() -> None:
    profile = _profile()
    plan = _plan(profile)
    outcome = _outcome(profile, GoalProgressStatus.SLOWER_THAN_EXPECTED)
    from fitadapt.baseline.energy import calculate_baseline_energy
    from fitadapt.personalization.safety import (
        TargetEligibilityStatus,
        TargetSafetyReason,
        assess_target_eligibility,
    )

    underweight = replace(profile, weight_kg=45, height_cm=180, requested_weekly_change_kg=-0.2)
    safety = assess_target_eligibility(underweight, calculate_baseline_energy(underweight))
    assert safety.status is TargetEligibilityStatus.INELIGIBLE
    result = decide_plan_adjustment(
        underweight, plan.calorie_target_kcal_per_day, plan, outcome, target_safety=safety
    )
    assert TargetSafetyReason.BMI_BELOW_WEIGHT_LOSS_THRESHOLD in result.reason_codes


def test_unstable_adaptive_tdee_defers_change() -> None:
    from fitadapt.adaptive.tdee import TdeeStability

    profile = _profile()
    plan = _plan(profile)
    outcome = _outcome(profile, GoalProgressStatus.SLOWER_THAN_EXPECTED)
    result = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        outcome,
        adaptive_tdee_stability=TdeeStability.UNSTABLE,
    )

    assert result.decision is RecommendationDecisionType.DEFER
    assert RecommendationDecisionReason.ADAPTIVE_TDEE_UNSTABLE in result.reason_codes
