"""Decision-policy contracts for proposal-only calorie adaptation."""

from dataclasses import replace
from datetime import date, timedelta

import pytest

from fitadapt.adaptive.tdee import TdeeStability
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.decisions import (
    AdaptiveEvidenceStatus,
    DecisionActivationReadiness,
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


def test_slow_fat_loss_proposes_review_required_decrease_and_fast_loss_increase_is_ready() -> None:
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
    assert slow.numerical_change_proposed is True
    assert slow.activation_readiness is DecisionActivationReadiness.REVIEW_REQUIRED
    assert RecommendationDecisionReason.DECREASE_REQUIRES_REVIEW in slow.reason_codes
    assert slow.calorie_delta_kcal_per_day == -100
    assert fast.decision is RecommendationDecisionType.INCREASE
    assert fast.calorie_delta_kcal_per_day == 100
    assert fast.activation_readiness is DecisionActivationReadiness.READY


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
    assert up.activation_readiness is DecisionActivationReadiness.REVIEW_REQUIRED
    assert RecommendationDecisionReason.DECREASE_REQUIRES_REVIEW in up.reason_codes


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
    assert result.proposed_calorie_target_kcal_per_day == 944
    assert result.activation_readiness is DecisionActivationReadiness.REVIEW_REQUIRED
    assert RecommendationDecisionReason.ADJUSTMENT_CLAMPED_TO_MINIMUM_TARGET in result.reason_codes


def test_adaptive_tdee_is_supporting_context_for_increase_only() -> None:
    profile = _profile()
    plan = _plan(profile)
    result = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        _outcome(profile, GoalProgressStatus.FASTER_THAN_EXPECTED),
        adaptive_tdee_kcal_per_day=3000,
        adaptive_tdee_stability=TdeeStability.STABLE,
    )

    assert result.decision is RecommendationDecisionType.INCREASE
    assert RecommendationDecisionReason.ADAPTIVE_TDEE_SUPPORTING in result.reason_codes
    assert result.adaptive_evidence_status is AdaptiveEvidenceStatus.STABLE


def test_stable_looking_decrease_remains_visible_but_requires_review() -> None:
    profile = _profile()
    plan = _plan(profile)
    result = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        _outcome(profile, GoalProgressStatus.SLOWER_THAN_EXPECTED),
        adaptive_tdee_kcal_per_day=2500.0,
        adaptive_tdee_stability=TdeeStability.STABLE,
    )

    assert result.decision is RecommendationDecisionType.DECREASE
    assert result.numerical_change_proposed is True
    assert result.activation_readiness is DecisionActivationReadiness.REVIEW_REQUIRED
    assert result.adaptive_evidence_status is AdaptiveEvidenceStatus.STABLE
    assert result.adaptive_tdee_kcal_per_day == 2500.0
    assert (
        RecommendationDecisionReason.PERSISTENT_WEIGHT_DRIFT_UNIDENTIFIABLE in result.reason_codes
    )
    assert RecommendationDecisionReason.DECREASE_REQUIRES_REVIEW in result.reason_codes


def test_recent_intake_change_and_sensitivity_codes_are_preserved_for_review() -> None:
    profile = _profile()
    plan = _plan(profile)
    result = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        _outcome(profile, GoalProgressStatus.SLOWER_THAN_EXPECTED),
        adaptive_tdee_kcal_per_day=2500.0,
        adaptive_tdee_stability=TdeeStability.STABILIZING,
        adaptive_tdee_reason_codes=("intake_regime_change", "post_regime_stabilization"),
    )

    assert result.decision is RecommendationDecisionType.DECREASE
    assert result.activation_readiness is DecisionActivationReadiness.REVIEW_REQUIRED
    assert RecommendationDecisionReason.RECENT_INTAKE_REGIME_CHANGE in result.reason_codes
    assert RecommendationDecisionReason.ESTIMATOR_STABILIZING in result.reason_codes


def test_slow_progress_decrease_is_permitted_only_after_long_horizon_agreement() -> None:
    profile = _profile()
    plan = _plan(profile)
    outcome = replace(
        _outcome(profile, GoalProgressStatus.SLOWER_THAN_EXPECTED),
        weight_span_days=42,
    )
    result = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        outcome,
        adaptive_tdee_kcal_per_day=2500.0,
        adaptive_tdee_stability=TdeeStability.STABLE,
        decrease_evidence_span_days=42,
        adaptive_tdee_horizon_disagreement_kcal_per_day=80.0,
    )

    assert result.decision is RecommendationDecisionType.DECREASE
    assert result.activation_readiness is DecisionActivationReadiness.REVIEW_REQUIRED
    assert result.calorie_delta_kcal_per_day == -100.0
    assert RecommendationDecisionReason.ADAPTIVE_HORIZONS_AGREE in result.reason_codes


@pytest.mark.parametrize(
    ("span", "disagreement", "required_reason"),
    [
        (28, 80.0, RecommendationDecisionReason.INSUFFICIENT_DECREASE_EVIDENCE_SPAN),
        (42, None, RecommendationDecisionReason.INSUFFICIENT_HORIZON_EVIDENCE),
        (42, 220.0, RecommendationDecisionReason.ESTIMATOR_SENSITIVITY_DISAGREEMENT),
    ],
)
def test_decrease_requires_review_without_long_span_and_horizon_agreement(
    span, disagreement, required_reason
) -> None:
    profile = _profile()
    plan = _plan(profile)
    outcome = replace(
        _outcome(profile, GoalProgressStatus.SLOWER_THAN_EXPECTED), weight_span_days=span
    )
    result = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        outcome,
        adaptive_tdee_kcal_per_day=2500.0,
        adaptive_tdee_stability=TdeeStability.STABLE,
        decrease_evidence_span_days=span,
        adaptive_tdee_horizon_disagreement_kcal_per_day=disagreement,
    )

    assert result.decision is RecommendationDecisionType.DECREASE
    assert result.calorie_delta_kcal_per_day == -100
    assert result.activation_readiness is DecisionActivationReadiness.REVIEW_REQUIRED
    assert required_reason in result.reason_codes


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
    with pytest.raises(RecommendationDecisionError):
        RecommendationDecisionConfig(policy_version="")
    with pytest.raises(RecommendationDecisionError):
        RecommendationDecisionConfig(maximum_target_kcal_per_day=0)
    with pytest.raises(RecommendationDecisionError):
        RecommendationDecisionConfig(minimum_interpretable_span_days=0)
    with pytest.raises(RecommendationDecisionError):
        RecommendationDecisionConfig(minimum_decrease_evidence_span_days=0)


@pytest.mark.parametrize(
    "progress",
    [GoalProgressStatus.DIRECTION_MISMATCH, GoalProgressStatus.INSUFFICIENT_EVIDENCE],
)
def test_directional_or_insufficient_outcome_evidence_defers_with_specific_reason(progress) -> None:
    profile = _profile()
    plan = _plan(profile)
    outcome = replace(_outcome(profile, progress), weight_span_days=21)

    result = decide_plan_adjustment(profile, plan.calorie_target_kcal_per_day, plan, outcome)

    assert result.decision is RecommendationDecisionType.DEFER
    if progress is GoalProgressStatus.DIRECTION_MISMATCH:
        assert (
            RecommendationDecisionReason.DIRECTION_MISMATCH_REQUIRES_REVIEW in result.reason_codes
        )
    else:
        assert RecommendationDecisionReason.INSUFFICIENT_WEIGHT_EVIDENCE in result.reason_codes


def test_ineligible_target_safety_defers_decision() -> None:
    profile = _profile()
    plan = _plan(profile)
    outcome = _outcome(profile, GoalProgressStatus.SLOWER_THAN_EXPECTED)
    from fitadapt.baseline.energy import calculate_baseline_energy
    from fitadapt.personalization.safety import (
        TargetEligibilityStatus,
        assess_target_eligibility,
    )

    underweight = replace(profile, weight_kg=45, height_cm=180, requested_weekly_change_kg=-0.2)
    safety = assess_target_eligibility(underweight, calculate_baseline_energy(underweight))
    assert safety.status is TargetEligibilityStatus.INELIGIBLE
    result = decide_plan_adjustment(
        underweight, plan.calorie_target_kcal_per_day, plan, outcome, target_safety=safety
    )
    assert result.decision is RecommendationDecisionType.DEFER
    assert RecommendationDecisionReason.SAFETY_TARGET_BOUND in result.reason_codes


def test_unstable_adaptive_tdee_keeps_decrease_visible_for_review() -> None:
    profile = _profile()
    plan = _plan(profile)
    outcome = _outcome(profile, GoalProgressStatus.SLOWER_THAN_EXPECTED)
    result = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        outcome,
        adaptive_tdee_kcal_per_day=2500.0,
        adaptive_tdee_stability=TdeeStability.UNSTABLE,
    )

    assert result.decision is RecommendationDecisionType.DECREASE
    assert result.activation_readiness is DecisionActivationReadiness.REVIEW_REQUIRED
    assert result.adaptive_evidence_status is AdaptiveEvidenceStatus.AMBIGUOUS
    assert RecommendationDecisionReason.ADAPTIVE_TDEE_UNSTABLE in result.reason_codes


@pytest.mark.parametrize(
    ("stability", "expected_status"),
    [
        (TdeeStability.INSUFFICIENT, AdaptiveEvidenceStatus.INSUFFICIENT),
        (TdeeStability.STABILIZING, AdaptiveEvidenceStatus.AMBIGUOUS),
        (TdeeStability.UNSTABLE, AdaptiveEvidenceStatus.AMBIGUOUS),
    ],
)
def test_ambiguous_adaptive_evidence_keeps_decrease_visible_for_review(
    stability, expected_status
) -> None:
    profile = _profile()
    plan = _plan(profile)
    result = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        _outcome(profile, GoalProgressStatus.SLOWER_THAN_EXPECTED),
        adaptive_tdee_kcal_per_day=2500.0,
        adaptive_tdee_stability=stability,
        adaptive_tdee_reason_codes=("intake_regime_change", "post_regime_stabilization")
        if stability is TdeeStability.STABILIZING
        else (),
    )

    assert result.decision is RecommendationDecisionType.DECREASE
    assert result.numerical_change_proposed is True
    assert result.activation_readiness is DecisionActivationReadiness.REVIEW_REQUIRED
    assert result.adaptive_evidence_status is expected_status
    assert result.adaptive_tdee_kcal_per_day is None
    assert RecommendationDecisionReason.ADAPTIVE_EVIDENCE_AMBIGUOUS in result.reason_codes
    assert RecommendationDecisionReason.DECREASE_REQUIRES_REVIEW in result.reason_codes
    if stability is TdeeStability.STABILIZING:
        assert RecommendationDecisionReason.RECENT_INTAKE_REGIME_CHANGE in result.reason_codes
        assert RecommendationDecisionReason.ESTIMATOR_STABILIZING in result.reason_codes


def test_cp28_supported_increase_can_proceed_with_ambiguous_tdee_but_does_not_claim_support() -> (
    None
):
    profile = _profile()
    plan = _plan(profile)
    result = decide_plan_adjustment(
        profile,
        plan.calorie_target_kcal_per_day,
        plan,
        _outcome(profile, GoalProgressStatus.FASTER_THAN_EXPECTED),
        adaptive_tdee_kcal_per_day=2600.0,
        adaptive_tdee_stability=TdeeStability.STABILIZING,
        adaptive_tdee_reason_codes=("weight_subwindow_slope_disagreement",),
    )

    assert result.decision is RecommendationDecisionType.INCREASE
    assert result.adaptive_evidence_status is AdaptiveEvidenceStatus.AMBIGUOUS
    assert result.adaptive_tdee_kcal_per_day is None
    assert RecommendationDecisionReason.ESTIMATOR_SENSITIVITY_DISAGREEMENT in result.reason_codes
    assert RecommendationDecisionReason.ADAPTIVE_TDEE_SUPPORTING not in result.reason_codes
