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

RECOMMENDATION_DECISION_POLICY_VERSION = "recommendation_decision_v2"


class RecommendationDecisionError(ValueError):
    """Raised when decision inputs or policy configuration are invalid."""


class RecommendationDecisionType(StrEnum):
    HOLD = "hold"
    INCREASE = "increase"
    DECREASE = "decrease"
    DEFER = "defer"


class AdaptiveEvidenceStatus(StrEnum):
    STABLE = "stable"
    AMBIGUOUS = "ambiguous"
    INSUFFICIENT = "insufficient"


class DecisionActivationReadiness(StrEnum):
    NOT_READY = "not_ready"
    REVIEW_REQUIRED = "review_required"
    READY = "ready"


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
    ADAPTIVE_EVIDENCE_STABLE = "adaptive_evidence_stable"
    ADAPTIVE_EVIDENCE_AMBIGUOUS = "adaptive_evidence_ambiguous"
    RECENT_INTAKE_REGIME_CHANGE = "recent_intake_regime_change"
    ESTIMATOR_STABILIZING = "estimator_stabilizing"
    ESTIMATOR_SENSITIVITY_DISAGREEMENT = "estimator_sensitivity_disagreement"
    MORE_EVIDENCE_REQUIRED = "more_evidence_required"
    CONSERVATIVE_DECREASE_WITHHELD = "conservative_decrease_withheld"
    PERSISTENT_WEIGHT_DRIFT_UNIDENTIFIABLE = "persistent_weight_drift_unidentifiable"
    INSUFFICIENT_DECREASE_EVIDENCE_SPAN = "insufficient_decrease_evidence_span"
    INSUFFICIENT_HORIZON_EVIDENCE = "insufficient_horizon_evidence"
    ADAPTIVE_HORIZONS_AGREE = "adaptive_horizons_agree"
    CONSERVATIVE_STANDARD_ADJUSTMENT = "conservative_standard_adjustment"
    DECREASE_REQUIRES_REVIEW = "decrease_requires_review"


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
    minimum_decrease_evidence_span_days: int = 42
    maximum_decrease_horizon_disagreement_kcal_per_day: float = 200.0

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise RecommendationDecisionError("policy_version must be a non-empty string.")
        for name in (
            "minimum_adjustment_kcal_per_day",
            "standard_adjustment_kcal_per_day",
            "maximum_adjustment_kcal_per_day",
            "adaptive_support_threshold_kcal_per_day",
            "maximum_decrease_horizon_disagreement_kcal_per_day",
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
        if (
            isinstance(self.minimum_decrease_evidence_span_days, bool)
            or not isinstance(self.minimum_decrease_evidence_span_days, int)
            or self.minimum_decrease_evidence_span_days <= 0
        ):
            raise RecommendationDecisionError(
                "minimum_decrease_evidence_span_days must be positive."
            )


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
    adaptive_evidence_status: AdaptiveEvidenceStatus
    activation_readiness: DecisionActivationReadiness
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
    adaptive_tdee_reason_codes: tuple[str, ...] = (),
    decrease_evidence_span_days: int = 0,
    adaptive_tdee_horizon_disagreement_kcal_per_day: float | None = None,
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
    if not isinstance(adaptive_tdee_reason_codes, tuple) or not all(
        isinstance(code, str) for code in adaptive_tdee_reason_codes
    ):
        raise RecommendationDecisionError("adaptive_tdee_reason_codes must be a tuple of strings.")
    if (
        isinstance(decrease_evidence_span_days, bool)
        or not isinstance(decrease_evidence_span_days, int)
        or decrease_evidence_span_days < 0
    ):
        raise RecommendationDecisionError(
            "decrease_evidence_span_days must be a non-negative integer."
        )
    if adaptive_tdee_horizon_disagreement_kcal_per_day is not None:
        adaptive_tdee_horizon_disagreement_kcal_per_day = validate_finite_number(
            adaptive_tdee_horizon_disagreement_kcal_per_day,
            field_name="adaptive_tdee_horizon_disagreement_kcal_per_day",
            error_type=RecommendationDecisionError,
        )
        if adaptive_tdee_horizon_disagreement_kcal_per_day < 0:
            raise RecommendationDecisionError(
                "adaptive_tdee_horizon_disagreement_kcal_per_day must be non-negative."
            )
    evidence_status, evidence_reasons = _adaptive_evidence(
        adaptive_tdee_kcal_per_day, adaptive_tdee_stability, adaptive_tdee_reason_codes
    )
    safe_adaptive_tdee = (
        adaptive_tdee_kcal_per_day if evidence_status is AdaptiveEvidenceStatus.STABLE else None
    )

    def finish(
        decision: RecommendationDecisionType,
        reasons: tuple[RecommendationDecisionReason, ...],
        proposed: float | None = None,
        *,
        status: AdaptiveEvidenceStatus | None = None,
        readiness: DecisionActivationReadiness | None = None,
    ) -> RecommendationDecision:
        selected_status = status or evidence_status
        contextual_reasons = tuple(
            reason
            for reason in evidence_reasons
            if not (
                selected_status is AdaptiveEvidenceStatus.AMBIGUOUS
                and reason is RecommendationDecisionReason.ADAPTIVE_EVIDENCE_STABLE
            )
        )
        all_reasons = tuple(dict.fromkeys((*reasons, *contextual_reasons)))
        return _result(
            decision,
            current_target,
            profile,
            outcome_assessment,
            safe_adaptive_tdee if selected_status is AdaptiveEvidenceStatus.STABLE else None,
            all_reasons,
            proposed,
            effective,
            selected_status,
            readiness,
        )

    if target_safety is not None and target_safety.status is TargetEligibilityStatus.INELIGIBLE:
        return finish(
            RecommendationDecisionType.DEFER,
            (RecommendationDecisionReason.SAFETY_TARGET_BOUND,),
        )
    if current_target < minimum_macro_calories_kcal_per_day(profile):
        return finish(
            RecommendationDecisionType.DEFER,
            (RecommendationDecisionReason.CURRENT_TARGET_BELOW_SAFETY_FLOOR,),
        )
    reasons = _defer_reasons(outcome_assessment, effective)
    if reasons:
        return finish(RecommendationDecisionType.DEFER, reasons)
    direction, direction_reason = _direction(profile.goal, outcome_assessment)
    if direction is None:
        reason = (
            RecommendationDecisionReason.PROGRESS_BROADLY_ON_TRACK
            if outcome_assessment.goal_progress is GoalProgressStatus.BROADLY_ON_TRACK
            else RecommendationDecisionReason.MAINTENANCE_STABLE
        )
        return finish(RecommendationDecisionType.HOLD, (reason,))
    adaptive_reason = _adaptive_reason(direction, current_target, safe_adaptive_tdee, effective)
    readiness_override: DecisionActivationReadiness | None = None
    decrease_reasons: tuple[RecommendationDecisionReason, ...] = ()
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
        return finish(
            RecommendationDecisionType.DEFER, (RecommendationDecisionReason.SAFETY_TARGET_BOUND,)
        )
    if direction < 0:
        decrease_reasons: list[RecommendationDecisionReason] = [
            direction_reason,
            RecommendationDecisionReason.PERSISTENT_WEIGHT_DRIFT_UNIDENTIFIABLE,
            RecommendationDecisionReason.DECREASE_REQUIRES_REVIEW,
        ]
        if evidence_status is not AdaptiveEvidenceStatus.STABLE:
            decrease_reasons.extend(
                (
                    RecommendationDecisionReason.ADAPTIVE_EVIDENCE_AMBIGUOUS,
                    RecommendationDecisionReason.MORE_EVIDENCE_REQUIRED,
                )
            )
        if decrease_evidence_span_days < effective.minimum_decrease_evidence_span_days:
            decrease_reasons.extend(
                (
                    RecommendationDecisionReason.INSUFFICIENT_DECREASE_EVIDENCE_SPAN,
                    RecommendationDecisionReason.MORE_EVIDENCE_REQUIRED,
                )
            )
        if adaptive_tdee_horizon_disagreement_kcal_per_day is None:
            decrease_reasons.extend(
                (
                    RecommendationDecisionReason.INSUFFICIENT_HORIZON_EVIDENCE,
                    RecommendationDecisionReason.MORE_EVIDENCE_REQUIRED,
                )
            )
        elif (
            adaptive_tdee_horizon_disagreement_kcal_per_day
            >= effective.maximum_decrease_horizon_disagreement_kcal_per_day
        ):
            decrease_reasons.extend(
                (
                    RecommendationDecisionReason.ESTIMATOR_SENSITIVITY_DISAGREEMENT,
                    RecommendationDecisionReason.MORE_EVIDENCE_REQUIRED,
                )
            )
        else:
            evidence_reasons = (
                *evidence_reasons,
                RecommendationDecisionReason.ADAPTIVE_HORIZONS_AGREE,
            )
        if adaptive_tdee_horizon_disagreement_kcal_per_day is not None and (
            adaptive_tdee_horizon_disagreement_kcal_per_day
            < effective.maximum_decrease_horizon_disagreement_kcal_per_day
        ):
            decrease_reasons = (
                *decrease_reasons,
                RecommendationDecisionReason.ADAPTIVE_HORIZONS_AGREE,
            )
        readiness_override = DecisionActivationReadiness.REVIEW_REQUIRED
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
        return finish(
            RecommendationDecisionType.HOLD,
            (RecommendationDecisionReason.DEVIATION_BELOW_MINIMUM_ADJUSTMENT,),
        )
    ordered_reasons = tuple(
        dict.fromkeys(
            reason
            for reason in (
                direction_reason,
                adaptive_reason,
                bounds_reason,
                *decrease_reasons,
            )
            if reason is not None
        )
    )
    return finish(
        RecommendationDecisionType.INCREASE
        if actual_delta > 0
        else RecommendationDecisionType.DECREASE,
        ordered_reasons,
        proposed,
        readiness=readiness_override,
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


def _adaptive_evidence(
    adaptive_tdee: float | None,
    stability: TdeeStability | None,
    estimator_reasons: tuple[str, ...],
) -> tuple[AdaptiveEvidenceStatus, tuple[RecommendationDecisionReason, ...]]:
    reasons: list[RecommendationDecisionReason] = []
    if stability is TdeeStability.STABLE and adaptive_tdee is not None and not estimator_reasons:
        status = AdaptiveEvidenceStatus.STABLE
        reasons.append(RecommendationDecisionReason.ADAPTIVE_EVIDENCE_STABLE)
    elif stability is TdeeStability.INSUFFICIENT or adaptive_tdee is None:
        status = AdaptiveEvidenceStatus.INSUFFICIENT
        reasons.extend(
            (
                RecommendationDecisionReason.ADAPTIVE_EVIDENCE_AMBIGUOUS,
                RecommendationDecisionReason.MORE_EVIDENCE_REQUIRED,
            )
        )
    else:
        status = AdaptiveEvidenceStatus.AMBIGUOUS
        reasons.append(RecommendationDecisionReason.ADAPTIVE_EVIDENCE_AMBIGUOUS)
    if "intake_regime_change" in estimator_reasons:
        reasons.append(RecommendationDecisionReason.RECENT_INTAKE_REGIME_CHANGE)
    if "post_regime_stabilization" in estimator_reasons or stability is TdeeStability.STABILIZING:
        reasons.append(RecommendationDecisionReason.ESTIMATOR_STABILIZING)
    if any("subwindow" in code or "sensitivity" in code for code in estimator_reasons):
        reasons.append(RecommendationDecisionReason.ESTIMATOR_SENSITIVITY_DISAGREEMENT)
    if stability is TdeeStability.UNSTABLE:
        reasons.append(RecommendationDecisionReason.ADAPTIVE_TDEE_UNSTABLE)
    if any(code.startswith("insufficient_") for code in estimator_reasons):
        reasons.append(RecommendationDecisionReason.MORE_EVIDENCE_REQUIRED)
    return status, tuple(dict.fromkeys(reasons))


def _result(
    decision: RecommendationDecisionType,
    current_target: float,
    profile: UserProfile,
    outcome: PlanOutcomeAssessment,
    adaptive_tdee: float | None,
    reasons: tuple[RecommendationDecisionReason, ...],
    proposed: float | None,
    config: RecommendationDecisionConfig,
    adaptive_evidence_status: AdaptiveEvidenceStatus,
    activation_readiness: DecisionActivationReadiness | None = None,
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
        limiting_reason=(
            next(
                (
                    reason
                    for reason in reasons
                    if reason
                    in (
                        RecommendationDecisionReason.CONSERVATIVE_DECREASE_WITHHELD,
                        RecommendationDecisionReason.ESTIMATOR_STABILIZING,
                        RecommendationDecisionReason.ESTIMATOR_SENSITIVITY_DISAGREEMENT,
                        RecommendationDecisionReason.ADAPTIVE_EVIDENCE_AMBIGUOUS,
                        RecommendationDecisionReason.ADHERENCE_NOT_NEAR_TARGET,
                        RecommendationDecisionReason.OUTCOME_NOT_INTERPRETABLE,
                        RecommendationDecisionReason.SAFETY_TARGET_BOUND,
                        RecommendationDecisionReason.DECREASE_REQUIRES_REVIEW,
                        RecommendationDecisionReason.PERSISTENT_WEIGHT_DRIFT_UNIDENTIFIABLE,
                    )
                ),
                reasons[0] if decision is RecommendationDecisionType.DEFER and reasons else None,
            )
            if decision is RecommendationDecisionType.DEFER
            or activation_readiness is DecisionActivationReadiness.REVIEW_REQUIRED
            else None
        ),
        reason_codes=reasons,
        adaptive_tdee_kcal_per_day=adaptive_tdee,
        adaptive_evidence_status=adaptive_evidence_status,
        activation_readiness=(
            activation_readiness
            or (
                DecisionActivationReadiness.READY
                if decision is RecommendationDecisionType.INCREASE
                else DecisionActivationReadiness.NOT_READY
                if decision in (RecommendationDecisionType.HOLD, RecommendationDecisionType.DEFER)
                else DecisionActivationReadiness.REVIEW_REQUIRED
            )
        ),
        policy_version=config.policy_version,
        assumptions=(
            "This is a proposal-only decision and never activates a new plan.",
            "Existing outcome assessment supplies adherence and weight-progress interpretation.",
            "Adaptive TDEE is an observational estimate, not measured expenditure or an "
            "independent target generator.",
            "Weight, logged intake, and dates alone cannot distinguish every persistent "
            "non-energy weight drift from energy-balance change.",
            "Hold and defer preserve the current calorie target exactly.",
        ),
    )
