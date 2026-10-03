"""Deterministic, stateless activation gating for repeated plan proposals."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from fitadapt.domain._validation import validate_finite_number
from fitadapt.domain.observation import DailyObservation
from fitadapt.personalization.decisions import (
    DecisionActivationReadiness,
    RecommendationDecision,
    RecommendationDecisionType,
)
from fitadapt.personalization.macros import PersonalizedMacroPlan
from fitadapt.personalization.outcomes import PlanOutcomeAssessment

PLAN_ADAPTATION_POLICY_VERSION = "plan_adaptation_v2"


class PlanAdaptationError(ValueError):
    """Raised when adaptation history or activation inputs are invalid."""


class PlanAdaptationAction(StrEnum):
    ACTIVATE = "activate"
    HOLD = "hold"
    DEFER = "defer"
    SUPPRESS = "suppress"
    REVIEW_REQUIRED = "review_required"
    REVERSAL_PENDING = "reversal_pending"


class PlanAdaptationSource(StrEnum):
    PROGRESS_ADAPTATION = "progress_adaptation"
    PROFILE_RECALCULATION = "profile_recalculation"


class PlanAdaptationReason(StrEnum):
    NO_EFFECTIVE_DATE = "no_effective_date"
    NO_PRIOR_ACTIVATION = "no_prior_activation"
    DECISION_HOLD = "decision_hold"
    DECISION_DEFER = "decision_defer"
    ADAPTIVE_EVIDENCE_AMBIGUOUS = "adaptive_evidence_ambiguous"
    RECENT_INTAKE_REGIME_CHANGE = "recent_intake_regime_change"
    ESTIMATOR_STABILIZING = "estimator_stabilizing"
    ESTIMATOR_SENSITIVITY_DISAGREEMENT = "estimator_sensitivity_disagreement"
    CONSERVATIVE_DECREASE_WITHHELD = "conservative_decrease_withheld"
    COOLDOWN_ACTIVE = "cooldown_active"
    INSUFFICIENT_NEW_OBSERVATIONS = "insufficient_new_observations"
    INSUFFICIENT_NEW_WEIGHT_CONTRIBUTORS = "insufficient_new_weight_contributors"
    INSUFFICIENT_NEW_INTAKE_CONTRIBUTORS = "insufficient_new_intake_contributors"
    REVERSAL_TOO_SOON = "reversal_too_soon"
    REVERSAL_NEEDS_MORE_EVIDENCE = "reversal_needs_more_evidence"
    DECREASE_REQUIRES_REVIEW = "decrease_requires_review"
    REVIEW_CONFIRMATION_MISMATCH = "review_confirmation_mismatch"
    USER_REVIEW_ACCEPTED = "user_review_accepted"
    REVERSAL_PENDING_CONFIRMATION = "reversal_pending_confirmation"
    REVERSAL_CONFIRMATION_INTERVAL = "reversal_confirmation_interval"
    REVERSAL_CONFIRMATION_NEEDS_NEW_EVIDENCE = "reversal_confirmation_needs_new_evidence"
    REVERSAL_CONFIRMATION_NEEDS_CONSISTENT_SIGNALS = (
        "reversal_confirmation_needs_consistent_signals"
    )
    REVERSAL_CONFIRMED = "reversal_confirmed"
    PROPOSAL_ACTIVATED = "proposal_activated"


@dataclass(frozen=True, slots=True)
class PlanAdaptationConfig:
    """Explicit cooldown and anti-oscillation thresholds for activation eligibility."""

    policy_version: str = PLAN_ADAPTATION_POLICY_VERSION
    minimum_days_between_activations: int = 14
    minimum_new_observations: int = 7
    minimum_new_weight_contributors: int = 4
    minimum_new_intake_contributors: int = 7
    minimum_reversal_interval_days: int = 28
    minimum_reversal_weight_contributors: int = 7
    minimum_reversal_intake_contributors: int = 14
    minimum_reversal_confirmation_interval_days: int = 14
    minimum_reversal_confirmation_observations: int = 7
    minimum_reversal_confirmation_weight_contributors: int = 4
    minimum_reversal_confirmation_intake_contributors: int = 7
    required_reversal_confirmation_evaluations: int = 2

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise PlanAdaptationError("policy_version must be a non-empty string.")
        for name in (
            "minimum_days_between_activations",
            "minimum_new_observations",
            "minimum_new_weight_contributors",
            "minimum_new_intake_contributors",
            "minimum_reversal_interval_days",
            "minimum_reversal_weight_contributors",
            "minimum_reversal_intake_contributors",
            "minimum_reversal_confirmation_interval_days",
            "minimum_reversal_confirmation_observations",
            "minimum_reversal_confirmation_weight_contributors",
            "minimum_reversal_confirmation_intake_contributors",
            "required_reversal_confirmation_evaluations",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise PlanAdaptationError(f"{name} must be a positive integer.")


@dataclass(frozen=True, slots=True)
class PlanAdaptationEvent:
    """Immutable record of one evaluated activation or non-activation decision."""

    effective_date: date | None
    previous_active_target_kcal_per_day: float
    new_active_target_kcal_per_day: float
    calorie_delta_kcal_per_day: float
    recommendation_decision: RecommendationDecisionType
    action: PlanAdaptationAction
    source: PlanAdaptationSource
    reason_codes: tuple[PlanAdaptationReason, ...]
    evidence_as_of_date: date | None
    new_observation_count: int
    new_weight_contributor_count: int
    new_intake_contributor_count: int
    policy_version: str
    proposed_delta_kcal_per_day: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.effective_date, datetime) or not isinstance(self.effective_date, date):
            raise PlanAdaptationError("effective_date must be a datetime.date.")
        if self.evidence_as_of_date is not None and (
            isinstance(self.evidence_as_of_date, datetime)
            or not isinstance(self.evidence_as_of_date, date)
        ):
            raise PlanAdaptationError("evidence_as_of_date must be a datetime.date or None.")
        for name in (
            "previous_active_target_kcal_per_day",
            "new_active_target_kcal_per_day",
            "calorie_delta_kcal_per_day",
            "proposed_delta_kcal_per_day",
        ):
            object.__setattr__(
                self,
                name,
                validate_finite_number(
                    getattr(self, name), field_name=name, error_type=PlanAdaptationError
                ),
            )
        if (
            self.previous_active_target_kcal_per_day <= 0
            or self.new_active_target_kcal_per_day <= 0
            or self.calorie_delta_kcal_per_day
            != self.new_active_target_kcal_per_day - self.previous_active_target_kcal_per_day
        ):
            raise PlanAdaptationError("adaptation event targets and delta must be consistent.")
        if not isinstance(self.recommendation_decision, RecommendationDecisionType):
            raise PlanAdaptationError(
                "recommendation_decision must be a RecommendationDecisionType."
            )
        if not isinstance(self.action, PlanAdaptationAction):
            raise PlanAdaptationError("action must be a PlanAdaptationAction.")
        if not isinstance(self.source, PlanAdaptationSource):
            raise PlanAdaptationError("source must be a PlanAdaptationSource.")
        if not isinstance(self.reason_codes, tuple) or not all(
            isinstance(item, PlanAdaptationReason) for item in self.reason_codes
        ):
            raise PlanAdaptationError(
                "reason_codes must be a tuple of PlanAdaptationReason values."
            )
        for name in (
            "new_observation_count",
            "new_weight_contributor_count",
            "new_intake_contributor_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise PlanAdaptationError(f"{name} must be a non-negative integer.")
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise PlanAdaptationError("policy_version must be a non-empty string.")


@dataclass(frozen=True, slots=True)
class PlanAdaptationDecision:
    """Activation result with the next active plan and immutable resulting history."""

    action: PlanAdaptationAction
    activation_available: bool
    activation_ready: bool
    review_required: bool
    user_attention_required: bool
    current_active_macro_plan: PersonalizedMacroPlan
    proposed_macro_plan: PersonalizedMacroPlan | None
    next_active_macro_plan: PersonalizedMacroPlan
    current_active_target_kcal_per_day: float
    proposed_target_kcal_per_day: float
    next_active_target_kcal_per_day: float
    calorie_delta_kcal_per_day: float
    effective_date: date
    recommendation_decision: RecommendationDecisionType
    reason_codes: tuple[PlanAdaptationReason, ...]
    new_observation_count: int
    new_weight_contributor_count: int
    new_intake_contributor_count: int
    adaptation_history: tuple[PlanAdaptationEvent, ...]
    policy_version: str
    assumptions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProposalReviewConfirmation:
    """Caller assertion that one exact review-required proposal was accepted."""

    effective_date: date
    proposed_target_kcal_per_day: float

    def __post_init__(self) -> None:
        if isinstance(self.effective_date, datetime) or not isinstance(self.effective_date, date):
            raise PlanAdaptationError("review confirmation effective_date must be a date.")
        object.__setattr__(
            self,
            "proposed_target_kcal_per_day",
            validate_finite_number(
                self.proposed_target_kcal_per_day,
                field_name="proposed_target_kcal_per_day",
                error_type=PlanAdaptationError,
            ),
        )
        if self.proposed_target_kcal_per_day <= 0:
            raise PlanAdaptationError("review confirmation target must be positive.")


def evaluate_plan_adaptation(
    current_active_macro_plan: PersonalizedMacroPlan,
    recommendation_decision: RecommendationDecision,
    proposed_macro_plan: PersonalizedMacroPlan | None,
    effective_date: date | None,
    prior_events: Sequence[PlanAdaptationEvent] = (),
    observations: Sequence[DailyObservation] = (),
    outcome_assessment: PlanOutcomeAssessment | None = None,
    config: PlanAdaptationConfig | None = None,
    source: PlanAdaptationSource = PlanAdaptationSource.PROGRESS_ADAPTATION,
    review_confirmation: ProposalReviewConfirmation | None = None,
) -> PlanAdaptationDecision:
    """Evaluate whether CP29's proposal is eligible for activation without persistence."""
    if not isinstance(current_active_macro_plan, PersonalizedMacroPlan):
        raise PlanAdaptationError("current_active_macro_plan must be a PersonalizedMacroPlan.")
    if not isinstance(recommendation_decision, RecommendationDecision):
        raise PlanAdaptationError("recommendation_decision must be a RecommendationDecision.")
    if effective_date is not None and (
        isinstance(effective_date, datetime) or not isinstance(effective_date, date)
    ):
        raise PlanAdaptationError("effective_date must be a datetime.date.")
    if not isinstance(source, PlanAdaptationSource):
        raise PlanAdaptationError("source must be a PlanAdaptationSource.")
    if review_confirmation is not None and not isinstance(
        review_confirmation, ProposalReviewConfirmation
    ):
        raise PlanAdaptationError(
            "review_confirmation must be a ProposalReviewConfirmation or None."
        )
    effective = config or PlanAdaptationConfig()
    if not isinstance(effective, PlanAdaptationConfig):
        raise PlanAdaptationError("config must be a PlanAdaptationConfig or None.")
    history = _validate_history(prior_events)
    submitted = tuple(observations)
    if not all(isinstance(item, DailyObservation) for item in submitted):
        raise PlanAdaptationError("observations must contain DailyObservation instances.")
    if outcome_assessment is not None and not isinstance(outcome_assessment, PlanOutcomeAssessment):
        raise PlanAdaptationError("outcome_assessment must be a PlanOutcomeAssessment or None.")
    if (
        recommendation_decision.current_calorie_target_kcal_per_day
        != current_active_macro_plan.calorie_target_kcal_per_day
    ):
        raise PlanAdaptationError("decision current target must match the active macro plan.")
    if recommendation_decision.numerical_change_proposed:
        if not isinstance(proposed_macro_plan, PersonalizedMacroPlan):
            raise PlanAdaptationError("a numerical decision requires proposed_macro_plan.")
        if (
            proposed_macro_plan.calorie_target_kcal_per_day
            != recommendation_decision.proposed_calorie_target_kcal_per_day
        ):
            raise PlanAdaptationError("proposed macro plan must match the decision target.")
    last_activation = _last_activation(history)
    new_observations, new_weight, new_intake = _fresh_counts(
        submitted,
        None if last_activation is None else last_activation.effective_date,
        effective_date,
    )
    action, reasons = _activation_action(
        recommendation_decision,
        effective_date,
        last_activation,
        new_observations,
        new_weight,
        new_intake,
        effective,
        history,
        submitted,
        review_confirmation,
    )
    review_required = (
        recommendation_decision.activation_readiness is DecisionActivationReadiness.REVIEW_REQUIRED
    )
    next_plan = (
        proposed_macro_plan
        if action is PlanAdaptationAction.ACTIVATE and proposed_macro_plan is not None
        else current_active_macro_plan
    )
    proposed_target = recommendation_decision.proposed_calorie_target_kcal_per_day
    event = (
        None
        if effective_date is None or any(item.effective_date == effective_date for item in history)
        else PlanAdaptationEvent(
            effective_date=effective_date,
            previous_active_target_kcal_per_day=current_active_macro_plan.calorie_target_kcal_per_day,
            new_active_target_kcal_per_day=next_plan.calorie_target_kcal_per_day,
            calorie_delta_kcal_per_day=next_plan.calorie_target_kcal_per_day
            - current_active_macro_plan.calorie_target_kcal_per_day,
            recommendation_decision=recommendation_decision.decision,
            action=action,
            source=source,
            reason_codes=reasons,
            evidence_as_of_date=(
                None if outcome_assessment is None else outcome_assessment.effective_date
            ),
            new_observation_count=new_observations,
            new_weight_contributor_count=new_weight,
            new_intake_contributor_count=new_intake,
            policy_version=effective.policy_version,
            proposed_delta_kcal_per_day=recommendation_decision.calorie_delta_kcal_per_day,
        )
    )
    return PlanAdaptationDecision(
        action=action,
        activation_available=action is PlanAdaptationAction.ACTIVATE,
        activation_ready=action is PlanAdaptationAction.ACTIVATE,
        review_required=review_required,
        user_attention_required=action
        in (
            PlanAdaptationAction.ACTIVATE,
            PlanAdaptationAction.REVIEW_REQUIRED,
            PlanAdaptationAction.REVERSAL_PENDING,
        ),
        current_active_macro_plan=current_active_macro_plan,
        proposed_macro_plan=proposed_macro_plan,
        next_active_macro_plan=next_plan,
        current_active_target_kcal_per_day=current_active_macro_plan.calorie_target_kcal_per_day,
        proposed_target_kcal_per_day=proposed_target,
        next_active_target_kcal_per_day=next_plan.calorie_target_kcal_per_day,
        calorie_delta_kcal_per_day=next_plan.calorie_target_kcal_per_day
        - current_active_macro_plan.calorie_target_kcal_per_day,
        effective_date=effective_date,
        recommendation_decision=recommendation_decision.decision,
        reason_codes=reasons,
        new_observation_count=new_observations,
        new_weight_contributor_count=new_weight,
        new_intake_contributor_count=new_intake,
        adaptation_history=history if event is None else history + (event,),
        policy_version=effective.policy_version,
        assumptions=(
            "Activation eligibility is stateless; the caller owns persistence and acceptance.",
            "Repeated evaluations on one effective date do not append duplicate history events.",
            "Cooldown and fresh evidence use observation dates, not wall-clock time.",
            "A reviewed decrease confirmation is bound to its exact date and proposed target.",
            "Reversal confirmation uses contributor dates strictly after the first reversal "
            "signal; overlapping windows are not treated as independent proof.",
            "The current active plan is never mutated in place.",
            "Existing CP28 and CP29 policies remain authoritative for evidence and direction.",
        ),
    )


def _validate_history(events: Sequence[PlanAdaptationEvent]) -> tuple[PlanAdaptationEvent, ...]:
    if not isinstance(events, (tuple, list)) or not all(
        isinstance(event, PlanAdaptationEvent) for event in events
    ):
        raise PlanAdaptationError(
            "prior_events must be a list or tuple of PlanAdaptationEvent values."
        )
    history = tuple(events)
    if tuple(sorted(history, key=lambda item: item.effective_date)) != history:
        raise PlanAdaptationError("prior_events must be in chronological order.")
    if len({event.effective_date for event in history}) != len(history):
        raise PlanAdaptationError("prior_events cannot contain duplicate effective dates.")
    return history


def _last_activation(events: tuple[PlanAdaptationEvent, ...]) -> PlanAdaptationEvent | None:
    activations = tuple(event for event in events if event.action is PlanAdaptationAction.ACTIVATE)
    return None if not activations else activations[-1]


def _fresh_counts(
    observations: tuple[DailyObservation, ...], since: date | None, until: date | None
) -> tuple[int, int, int]:
    fresh = tuple(
        item
        for item in observations
        if (since is None or item.observed_on > since)
        and (until is None or item.observed_on <= until)
    )
    observation_dates = {item.observed_on for item in fresh}
    weight_dates = {item.observed_on for item in fresh if item.body_weight_kg is not None}
    intake_dates = {item.observed_on for item in fresh if item.energy_intake_kcal is not None}
    return (
        len(observation_dates),
        len(weight_dates),
        len(intake_dates),
    )


def _activation_action(
    decision: RecommendationDecision,
    effective_date: date | None,
    last_activation: PlanAdaptationEvent | None,
    new_observations: int,
    new_weight: int,
    new_intake: int,
    config: PlanAdaptationConfig,
    history: tuple[PlanAdaptationEvent, ...],
    observations: tuple[DailyObservation, ...],
    review_confirmation: ProposalReviewConfirmation | None,
) -> tuple[PlanAdaptationAction, tuple[PlanAdaptationReason, ...]]:
    if effective_date is None:
        return PlanAdaptationAction.DEFER, (PlanAdaptationReason.NO_EFFECTIVE_DATE,)
    if decision.decision is RecommendationDecisionType.HOLD:
        return PlanAdaptationAction.HOLD, (PlanAdaptationReason.DECISION_HOLD,)
    if decision.decision is RecommendationDecisionType.DEFER:
        propagated = {
            "adaptive_evidence_ambiguous": PlanAdaptationReason.ADAPTIVE_EVIDENCE_AMBIGUOUS,
            "recent_intake_regime_change": PlanAdaptationReason.RECENT_INTAKE_REGIME_CHANGE,
            "estimator_stabilizing": PlanAdaptationReason.ESTIMATOR_STABILIZING,
            "estimator_sensitivity_disagreement": (
                PlanAdaptationReason.ESTIMATOR_SENSITIVITY_DISAGREEMENT
            ),
            "conservative_decrease_withheld": PlanAdaptationReason.CONSERVATIVE_DECREASE_WITHHELD,
        }
        reasons = [PlanAdaptationReason.DECISION_DEFER]
        reasons.extend(
            mapped
            for code in decision.reason_codes
            if (mapped := propagated.get(code.value)) is not None
        )
        return PlanAdaptationAction.DEFER, tuple(dict.fromkeys(reasons))

    review_required = decision.activation_readiness is DecisionActivationReadiness.REVIEW_REQUIRED
    review_accepted = review_required and _review_matches(
        decision, effective_date, review_confirmation
    )
    if last_activation is None:
        if review_required and not review_accepted:
            reasons = [PlanAdaptationReason.DECREASE_REQUIRES_REVIEW]
            if review_confirmation is not None:
                reasons.append(PlanAdaptationReason.REVIEW_CONFIRMATION_MISMATCH)
            return PlanAdaptationAction.REVIEW_REQUIRED, tuple(reasons)
        reasons = [
            PlanAdaptationReason.NO_PRIOR_ACTIVATION,
            PlanAdaptationReason.PROPOSAL_ACTIVATED,
        ]
        if review_accepted:
            reasons.append(PlanAdaptationReason.USER_REVIEW_ACCEPTED)
        return PlanAdaptationAction.ACTIVATE, tuple(reasons)
    elapsed = (effective_date - last_activation.effective_date).days
    if elapsed < 0:
        raise PlanAdaptationError("effective_date cannot precede the last activation.")
    fresh_reasons: list[PlanAdaptationReason] = []
    if elapsed < config.minimum_days_between_activations:
        fresh_reasons.append(PlanAdaptationReason.COOLDOWN_ACTIVE)
    if new_observations < config.minimum_new_observations:
        fresh_reasons.append(PlanAdaptationReason.INSUFFICIENT_NEW_OBSERVATIONS)
    if new_weight < config.minimum_new_weight_contributors:
        fresh_reasons.append(PlanAdaptationReason.INSUFFICIENT_NEW_WEIGHT_CONTRIBUTORS)
    if new_intake < config.minimum_new_intake_contributors:
        fresh_reasons.append(PlanAdaptationReason.INSUFFICIENT_NEW_INTAKE_CONTRIBUTORS)
    reversing = (
        decision.proposed_calorie_target_kcal_per_day - decision.current_calorie_target_kcal_per_day
    ) * last_activation.calorie_delta_kcal_per_day < 0
    if reversing:
        signal_direction = _sign(decision.calorie_delta_kcal_per_day)
        pending = _pending_reversal(history, last_activation, signal_direction)
        if pending is None:
            reasons = [PlanAdaptationReason.REVERSAL_PENDING_CONFIRMATION]
            if review_required:
                reasons.append(PlanAdaptationReason.DECREASE_REQUIRES_REVIEW)
            if review_confirmation is not None and not review_accepted:
                reasons.append(PlanAdaptationReason.REVIEW_CONFIRMATION_MISMATCH)
            return PlanAdaptationAction.REVERSAL_PENDING, tuple(reasons)

        pending_date = pending.effective_date
        assert pending_date is not None
        # Confirmation uses contributors strictly after the first reversal signal.
        pending_counts = _fresh_counts(observations, pending_date, effective_date)
        if (
            new_weight < config.minimum_reversal_weight_contributors
            or new_intake < config.minimum_reversal_intake_contributors
        ):
            fresh_reasons.append(PlanAdaptationReason.REVERSAL_NEEDS_MORE_EVIDENCE)
        if (
            effective_date - pending_date
        ).days < config.minimum_reversal_confirmation_interval_days:
            fresh_reasons.append(PlanAdaptationReason.REVERSAL_CONFIRMATION_INTERVAL)
        confirmation_new_observations, confirmation_new_weight, confirmation_new_intake = (
            pending_counts
        )
        if (
            confirmation_new_observations < config.minimum_reversal_confirmation_observations
            or confirmation_new_weight < config.minimum_reversal_confirmation_weight_contributors
            or confirmation_new_intake < config.minimum_reversal_confirmation_intake_contributors
        ):
            fresh_reasons.append(PlanAdaptationReason.REVERSAL_CONFIRMATION_NEEDS_NEW_EVIDENCE)
        consistent_evaluations = (
            _consistent_reversal_evaluations(history, last_activation, signal_direction) + 1
        )
        if consistent_evaluations < config.required_reversal_confirmation_evaluations:
            fresh_reasons.append(
                PlanAdaptationReason.REVERSAL_CONFIRMATION_NEEDS_CONSISTENT_SIGNALS
            )
        if elapsed < config.minimum_reversal_interval_days:
            fresh_reasons.append(PlanAdaptationReason.REVERSAL_TOO_SOON)
        if fresh_reasons:
            return PlanAdaptationAction.REVERSAL_PENDING, tuple(
                dict.fromkeys((PlanAdaptationReason.REVERSAL_PENDING_CONFIRMATION, *fresh_reasons))
            )
        if review_required and not review_accepted:
            reasons = [
                PlanAdaptationReason.REVERSAL_PENDING_CONFIRMATION,
                PlanAdaptationReason.REVERSAL_CONFIRMED,
                PlanAdaptationReason.DECREASE_REQUIRES_REVIEW,
            ]
            if review_confirmation is not None:
                reasons.append(PlanAdaptationReason.REVIEW_CONFIRMATION_MISMATCH)
            return PlanAdaptationAction.REVERSAL_PENDING, tuple(reasons)
    elif review_required and not review_accepted:
        reasons = [PlanAdaptationReason.DECREASE_REQUIRES_REVIEW]
        if review_confirmation is not None:
            reasons.append(PlanAdaptationReason.REVIEW_CONFIRMATION_MISMATCH)
        return PlanAdaptationAction.REVIEW_REQUIRED, tuple(reasons)
    if fresh_reasons:
        return PlanAdaptationAction.DEFER, tuple(dict.fromkeys(fresh_reasons))
    reasons = [PlanAdaptationReason.PROPOSAL_ACTIVATED]
    if reversing:
        reasons.append(PlanAdaptationReason.REVERSAL_CONFIRMED)
    if review_accepted:
        reasons.append(PlanAdaptationReason.USER_REVIEW_ACCEPTED)
    return PlanAdaptationAction.ACTIVATE, tuple(reasons)


def _review_matches(
    decision: RecommendationDecision,
    effective_date: date,
    confirmation: ProposalReviewConfirmation | None,
) -> bool:
    return confirmation is not None and (
        confirmation.effective_date == effective_date
        and confirmation.proposed_target_kcal_per_day
        == decision.proposed_calorie_target_kcal_per_day
    )


def _sign(value: float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def _events_after_activation(
    history: tuple[PlanAdaptationEvent, ...], last_activation: PlanAdaptationEvent
) -> tuple[PlanAdaptationEvent, ...]:
    return tuple(
        event for event in history if event.effective_date > last_activation.effective_date
    )


def _pending_reversal(
    history: tuple[PlanAdaptationEvent, ...],
    last_activation: PlanAdaptationEvent,
    direction: int,
) -> PlanAdaptationEvent | None:
    pending = None
    for event in _events_after_activation(history, last_activation):
        if (
            event.action is PlanAdaptationAction.REVERSAL_PENDING
            and _sign(event.proposed_delta_kcal_per_day) == direction
        ):
            pending = event if pending is None else pending
        else:
            pending = None
    return pending


def _consistent_reversal_evaluations(
    history: tuple[PlanAdaptationEvent, ...],
    last_activation: PlanAdaptationEvent,
    direction: int,
) -> int:
    count = 0
    for event in reversed(_events_after_activation(history, last_activation)):
        if (
            event.action is not PlanAdaptationAction.REVERSAL_PENDING
            or _sign(event.proposed_delta_kcal_per_day) != direction
        ):
            break
        count += 1
    return count
