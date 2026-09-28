"""Conservative, proposal-only decisions from existing outcome evidence."""

from dataclasses import dataclass
from enum import StrEnum

from fitadapt.adaptive.tdee import TdeeStability
from fitadapt.baseline.targets import minimum_macro_calories_kcal_per_day
from fitadapt.domain._validation import validate_finite_number
from fitadapt.domain.profile import Goal, UserProfile
from fitadapt.personalization.macros import PersonalizedMacroPlan
from fitadapt.personalization.outcomes import (
    GoalProgressStatus,
    IntakeAdherenceStatus,
    OutcomeInterpretability,
    PlanOutcomeAssessment,
    WeightTrendStatus,
)
from fitadapt.personalization.safety import TargetEligibilityAssessment, TargetEligibilityStatus

RECOMMENDATION_DECISION_POLICY_VERSION = "recommendation_decision_v1"


class RecommendationDecisionError(ValueError):
    """Raised when decision inputs or policy configuration are invalid."""


class RecommendationDecisionType(StrEnum):
    HOLD = "hold"
    INCREASE = "increase"
    DECREASE = "decrease"
    DEFER = "defer"


class RecommendationDecisionReason(StrEnum):
    OUTCOME_UNAVAILABLE = "outcome_unavailable"
    OUTCOME_NOT_INTERPRETABLE = "outcome_not_interpretable"
    INSUFFICIENT_INTAKE_EVIDENCE = "insufficient_intake_evidence"
    INSUFFICIENT_WEIGHT_EVIDENCE = "insufficient_weight_evidence"
    INSUFFICIENT_OBSERVATION_SPAN = "insufficient_observation_span"
    ADHERENCE_NOT_NEAR_TARGET = "adherence_not_near_target"
    DIRECTION_MISMATCH_REQUIRES_REVIEW = "direction_mismatch_requires_review"
    PROGRESS_BROADLY_ON_TRACK = "progress_broadly_on_track"
    MAINTENANCE_STABLE = "maintenance_stable"
    DEVIATION_BELOW_MINIMUM_ADJUSTMENT = "deviation_below_minimum_adjustment"
    SLOWER_THAN_REQUESTED = "slower_than_requested"
    FASTER_THAN_REQUESTED = "faster_than_requested"
    ADAPTIVE_TDEE_SUPPORTING = "adaptive_tdee_supporting"
    ADAPTIVE_TDEE_CONFLICTING = "adaptive_tdee_conflicting"
    ADJUSTMENT_CLAMPED_TO_MINIMUM_TARGET = "adjustment_clamped_to_minimum_target"
    ADJUSTMENT_CLAMPED_TO_MAXIMUM_TARGET = "adjustment_clamped_to_maximum_target"
    CURRENT_TARGET_BELOW_SAFETY_FLOOR = "current_target_below_safety_floor"
    SAFETY_TARGET_BOUND = "safety_target_bound"
    ADAPTIVE_TDEE_UNSTABLE = "adaptive_tdee_unstable"
    CONSERVATIVE_STANDARD_ADJUSTMENT = "conservative_standard_adjustment"


@dataclass(frozen=True, slots=True)
class RecommendationDecisionConfig:
    """Explicit, conservative thresholds for one proposal-only decision."""

    policy_version: str = RECOMMENDATION_DECISION_POLICY_VERSION
    minimum_adjustment_kcal_per_day: float = 50.0
    standard_adjustment_kcal_per_day: float = 100.0
    maximum_adjustment_kcal_per_day: float = 150.0
    maximum_target_kcal_per_day: float | None = None
    minimum_interpretable_span_days: int = 14
    adaptive_support_threshold_kcal_per_day: float = 150.0

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise RecommendationDecisionError("policy_version must be a non-empty string.")
        for name in (
            "minimum_adjustment_kcal_per_day",
            "standard_adjustment_kcal_per_day",
            "maximum_adjustment_kcal_per_day",
            "adaptive_support_threshold_kcal_per_day",
        ):
            object.__setattr__(
                self,
                name,
                validate_finite_number(
                    getattr(self, name), field_name=name, error_type=RecommendationDecisionError
                ),
            )
        if (
            self.minimum_adjustment_kcal_per_day <= 0
            or self.standard_adjustment_kcal_per_day < self.minimum_adjustment_kcal_per_day
            or self.maximum_adjustment_kcal_per_day < self.standard_adjustment_kcal_per_day
        ):
            raise RecommendationDecisionError(
                "adjustment thresholds must be positive and ordered minimum <= standard <= maximum."
            )
        if self.maximum_target_kcal_per_day is not None:
            object.__setattr__(
                self,
                "maximum_target_kcal_per_day",
                validate_finite_number(
                    self.maximum_target_kcal_per_day,
                    field_name="maximum_target_kcal_per_day",
                    error_type=RecommendationDecisionError,
                ),
            )
            if self.maximum_target_kcal_per_day <= 0:
                raise RecommendationDecisionError(
                    "maximum_target_kcal_per_day must be positive when provided."
                )
        if (
            isinstance(self.minimum_interpretable_span_days, bool)
            or not isinstance(self.minimum_interpretable_span_days, int)
            or self.minimum_interpretable_span_days <= 0
        ):
            raise RecommendationDecisionError("minimum_interpretable_span_days must be positive.")


@dataclass(frozen=True, slots=True)
class RecommendationDecision:
    """One deterministic proposal; it never activates or mutates the current plan."""

    decision: RecommendationDecisionType
    decision_available: bool
    attention_required: bool
    current_calorie_target_kcal_per_day: float
    proposed_calorie_target_kcal_per_day: float
    calorie_delta_kcal_per_day: float
    numerical_change_proposed: bool
    goal: Goal
    requested_weekly_change_kg: float
    outcome_interpretability: OutcomeInterpretability
    intake_adherence: IntakeAdherenceStatus
    weight_trend_status: WeightTrendStatus
    goal_progress: GoalProgressStatus
    limiting_reason: RecommendationDecisionReason | None
    reason_codes: tuple[RecommendationDecisionReason, ...]
    adaptive_tdee_kcal_per_day: float | None
    policy_version: str
    assumptions: tuple[str, ...]


def decide_plan_adjustment(
    profile: UserProfile,
    current_calorie_target_kcal_per_day: float,
    current_macro_plan: PersonalizedMacroPlan,
    outcome_assessment: PlanOutcomeAssessment,
    adaptive_tdee_kcal_per_day: float | None = None,
    config: RecommendationDecisionConfig | None = None,
    target_safety: TargetEligibilityAssessment | None = None,
    adaptive_tdee_stability: TdeeStability | None = None,
) -> RecommendationDecision:
    """Decide hold, increase, decrease, or defer from existing evidence only."""
    if not isinstance(profile, UserProfile):
        raise RecommendationDecisionError("profile must be a UserProfile.")
    if not isinstance(current_macro_plan, PersonalizedMacroPlan):
        raise RecommendationDecisionError("current_macro_plan must be a PersonalizedMacroPlan.")
    if not isinstance(outcome_assessment, PlanOutcomeAssessment):
        raise RecommendationDecisionError("outcome_assessment must be a PlanOutcomeAssessment.")
    if target_safety is not None and not isinstance(target_safety, TargetEligibilityAssessment):
        raise RecommendationDecisionError(
            "target_safety must be a TargetEligibilityAssessment or None."
        )
    current_target = validate_finite_number(
        current_calorie_target_kcal_per_day,
        field_name="current_calorie_target_kcal_per_day",
        error_type=RecommendationDecisionError,
    )
    if current_target <= 0 or current_target != current_macro_plan.calorie_target_kcal_per_day:
        raise RecommendationDecisionError(
            "current calorie target must be positive and match current_macro_plan."
        )
    if adaptive_tdee_kcal_per_day is not None:
        adaptive_tdee_kcal_per_day = validate_finite_number(
            adaptive_tdee_kcal_per_day,
            field_name="adaptive_tdee_kcal_per_day",
            error_type=RecommendationDecisionError,
        )
    effective = config or RecommendationDecisionConfig()
    if not isinstance(effective, RecommendationDecisionConfig):
        raise RecommendationDecisionError("config must be a RecommendationDecisionConfig or None.")
    if adaptive_tdee_stability is not None and not isinstance(
        adaptive_tdee_stability, TdeeStability
    ):
        raise RecommendationDecisionError(
            "adaptive_tdee_stability must be a TdeeStability or None."
        )
    if target_safety is not None and target_safety.status is TargetEligibilityStatus.INELIGIBLE:
        return _result(
            RecommendationDecisionType.DEFER,
            current_target,
            profile,
            outcome_assessment,
            adaptive_tdee_kcal_per_day,
            tuple(target_safety.reason_codes),
            None,
            effective,
        )
    if adaptive_tdee_stability is TdeeStability.UNSTABLE:
        return _result(
            RecommendationDecisionType.DEFER,
            current_target,
            profile,
            outcome_assessment,
            adaptive_tdee_kcal_per_day,
            (RecommendationDecisionReason.ADAPTIVE_TDEE_UNSTABLE,),
            None,
            effective,
        )
    if current_target < minimum_macro_calories_kcal_per_day(profile):
        return _result(
            RecommendationDecisionType.DEFER,
            current_target,
            profile,
            outcome_assessment,
            adaptive_tdee_kcal_per_day,
            (RecommendationDecisionReason.CURRENT_TARGET_BELOW_SAFETY_FLOOR,),
            None,
            effective,
        )
    reasons = _defer_reasons(outcome_assessment, effective)
    if reasons:
        return _result(
            RecommendationDecisionType.DEFER,
            current_target,
            profile,
            outcome_assessment,
            adaptive_tdee_kcal_per_day,
            reasons,
            None,
            effective,
        )
    direction, direction_reason = _direction(profile.goal, outcome_assessment)
    if direction is None:
        reason = (
            RecommendationDecisionReason.PROGRESS_BROADLY_ON_TRACK
            if outcome_assessment.goal_progress is GoalProgressStatus.BROADLY_ON_TRACK
            else RecommendationDecisionReason.MAINTENANCE_STABLE
        )
        return _result(
            RecommendationDecisionType.HOLD,
            current_target,
            profile,
            outcome_assessment,
            adaptive_tdee_kcal_per_day,
            (reason,),
            None,
            effective,
        )
    adaptive_reason = _adaptive_reason(
        direction, current_target, adaptive_tdee_kcal_per_day, effective
    )
    delta = min(
        effective.standard_adjustment_kcal_per_day, effective.maximum_adjustment_kcal_per_day
    )
    proposed = current_target + direction * delta
    if (
        direction < 0
        and target_safety is not None
        and (
            proposed < (target_safety.applied_calorie_floor_kcal_per_day or 0.0)
            or (
                target_safety.maximum_permitted_deficit_kcal_per_day is not None
                and proposed
                < target_safety.baseline_tdee_kcal_per_day
                - target_safety.maximum_permitted_deficit_kcal_per_day
            )
        )
    ):
        return _result(
            RecommendationDecisionType.HOLD,
            current_target,
            profile,
            outcome_assessment,
            adaptive_tdee_kcal_per_day,
            (RecommendationDecisionReason.SAFETY_TARGET_BOUND,),
            None,
            effective,
        )
    bounds_reason = None
    minimum_target = minimum_macro_calories_kcal_per_day(profile)
    if proposed < minimum_target:
        proposed = minimum_target
        bounds_reason = RecommendationDecisionReason.ADJUSTMENT_CLAMPED_TO_MINIMUM_TARGET
    if proposed > current_target + effective.maximum_adjustment_kcal_per_day:
        proposed = current_target + effective.maximum_adjustment_kcal_per_day
        bounds_reason = RecommendationDecisionReason.ADJUSTMENT_CLAMPED_TO_MAXIMUM_TARGET
    if (
        effective.maximum_target_kcal_per_day is not None
        and proposed > effective.maximum_target_kcal_per_day
    ):
        proposed = effective.maximum_target_kcal_per_day
        bounds_reason = RecommendationDecisionReason.ADJUSTMENT_CLAMPED_TO_MAXIMUM_TARGET
    actual_delta = proposed - current_target
    if abs(actual_delta) < effective.minimum_adjustment_kcal_per_day:
        return _result(
            RecommendationDecisionType.HOLD,
            current_target,
            profile,
            outcome_assessment,
            adaptive_tdee_kcal_per_day,
            (RecommendationDecisionReason.DEVIATION_BELOW_MINIMUM_ADJUSTMENT,),
            None,
            effective,
        )
    ordered_reasons = tuple(
        reason
        for reason in (direction_reason, adaptive_reason, bounds_reason)
        if reason is not None
    )
    return _result(
        RecommendationDecisionType.INCREASE
        if actual_delta > 0
        else RecommendationDecisionType.DECREASE,
        current_target,
        profile,
        outcome_assessment,
        adaptive_tdee_kcal_per_day,
        ordered_reasons,
        proposed,
        effective,
    )


def _defer_reasons(
    outcome: PlanOutcomeAssessment, config: RecommendationDecisionConfig
) -> tuple[RecommendationDecisionReason, ...]:
    reasons: list[RecommendationDecisionReason] = []
    if not outcome.assessment_available:
        reasons.append(RecommendationDecisionReason.OUTCOME_UNAVAILABLE)
    if outcome.overall_interpretability is not OutcomeInterpretability.INTERPRETABLE:
        reasons.append(RecommendationDecisionReason.OUTCOME_NOT_INTERPRETABLE)
    if outcome.intake_adherence is not IntakeAdherenceStatus.NEAR_TARGET:
        reasons.append(RecommendationDecisionReason.ADHERENCE_NOT_NEAR_TARGET)
    if outcome.weight_trend_status is not WeightTrendStatus.AVAILABLE:
        reasons.append(RecommendationDecisionReason.INSUFFICIENT_WEIGHT_EVIDENCE)
    if outcome.weight_span_days < config.minimum_interpretable_span_days:
        reasons.append(RecommendationDecisionReason.INSUFFICIENT_OBSERVATION_SPAN)
    if outcome.goal_progress is GoalProgressStatus.DIRECTION_MISMATCH:
        reasons.append(RecommendationDecisionReason.DIRECTION_MISMATCH_REQUIRES_REVIEW)
    if outcome.goal_progress is GoalProgressStatus.INSUFFICIENT_EVIDENCE:
        reasons.append(RecommendationDecisionReason.INSUFFICIENT_WEIGHT_EVIDENCE)
    return tuple(dict.fromkeys(reasons))


def _direction(
    goal: Goal, outcome: PlanOutcomeAssessment
) -> tuple[int | None, RecommendationDecisionReason | None]:
    progress = outcome.goal_progress
    if progress is GoalProgressStatus.BROADLY_ON_TRACK:
        return None, None
    if progress is GoalProgressStatus.SLOWER_THAN_EXPECTED:
        return (-1 if goal is Goal.CUT else 1), RecommendationDecisionReason.SLOWER_THAN_REQUESTED
    if progress is GoalProgressStatus.FASTER_THAN_EXPECTED:
        return (1 if goal is Goal.CUT else -1), RecommendationDecisionReason.FASTER_THAN_REQUESTED
    if progress is GoalProgressStatus.OUTSIDE_MAINTENANCE_RANGE:
        if outcome.observed_weight_change_kg_per_week is None:
            return None, None
        return (
            (1 if outcome.observed_weight_change_kg_per_week < 0 else -1),
            RecommendationDecisionReason.SLOWER_THAN_REQUESTED
            if outcome.observed_weight_change_kg_per_week < 0
            else RecommendationDecisionReason.FASTER_THAN_REQUESTED,
        )
    return None, None


def _adaptive_reason(
    direction: int,
    current_target: float,
    adaptive_tdee: float | None,
    config: RecommendationDecisionConfig,
) -> RecommendationDecisionReason | None:
    if (
        adaptive_tdee is None
        or abs(adaptive_tdee - current_target) < config.adaptive_support_threshold_kcal_per_day
    ):
        return None
    if (adaptive_tdee - current_target) * direction > 0:
        return RecommendationDecisionReason.ADAPTIVE_TDEE_SUPPORTING
    return RecommendationDecisionReason.ADAPTIVE_TDEE_CONFLICTING


def _result(
    decision: RecommendationDecisionType,
    current_target: float,
    profile: UserProfile,
    outcome: PlanOutcomeAssessment,
    adaptive_tdee: float | None,
    reasons: tuple[RecommendationDecisionReason, ...],
    proposed: float | None,
    config: RecommendationDecisionConfig,
) -> RecommendationDecision:
    target = current_target if proposed is None else proposed
    delta = target - current_target
    return RecommendationDecision(
        decision=decision,
        decision_available=True,
        attention_required=decision
        in (RecommendationDecisionType.INCREASE, RecommendationDecisionType.DECREASE),
        current_calorie_target_kcal_per_day=current_target,
        proposed_calorie_target_kcal_per_day=target,
        calorie_delta_kcal_per_day=delta,
        numerical_change_proposed=delta != 0,
        goal=profile.goal,
        requested_weekly_change_kg=profile.requested_weekly_change_kg,
        outcome_interpretability=outcome.overall_interpretability,
        intake_adherence=outcome.intake_adherence,
        weight_trend_status=outcome.weight_trend_status,
        goal_progress=outcome.goal_progress,
        limiting_reason=reasons[0]
        if decision is RecommendationDecisionType.DEFER and reasons
        else None,
        reason_codes=reasons,
        adaptive_tdee_kcal_per_day=adaptive_tdee,
        policy_version=config.policy_version,
        assumptions=(
            "This is a proposal-only decision and never activates a new plan.",
            "Existing outcome assessment supplies adherence and weight-progress interpretation.",
            "Adaptive TDEE is supporting context, not an independent target generator.",
            "Hold and defer preserve the current calorie target exactly.",
        ),
    )
