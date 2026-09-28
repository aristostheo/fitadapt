"""Deterministic, stateless activation gating for repeated plan proposals."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from fitadapt.domain._validation import validate_finite_number
from fitadapt.domain.observation import DailyObservation
from fitadapt.personalization.decisions import (
    RecommendationDecision,
    RecommendationDecisionType,
)
from fitadapt.personalization.macros import PersonalizedMacroPlan
from fitadapt.personalization.outcomes import PlanOutcomeAssessment

PLAN_ADAPTATION_POLICY_VERSION = "plan_adaptation_v1"


class PlanAdaptationError(ValueError):
    """Raised when adaptation history or activation inputs are invalid."""


class PlanAdaptationAction(StrEnum):
    ACTIVATE = "activate"
    HOLD = "hold"
    DEFER = "defer"
    SUPPRESS = "suppress"


class PlanAdaptationSource(StrEnum):
    PROGRESS_ADAPTATION = "progress_adaptation"
    PROFILE_RECALCULATION = "profile_recalculation"


class PlanAdaptationReason(StrEnum):
    NO_EFFECTIVE_DATE = "no_effective_date"
    NO_PRIOR_ACTIVATION = "no_prior_activation"
    DECISION_HOLD = "decision_hold"
    DECISION_DEFER = "decision_defer"
    COOLDOWN_ACTIVE = "cooldown_active"
    INSUFFICIENT_NEW_OBSERVATIONS = "insufficient_new_observations"
    INSUFFICIENT_NEW_WEIGHT_CONTRIBUTORS = "insufficient_new_weight_contributors"
    INSUFFICIENT_NEW_INTAKE_CONTRIBUTORS = "insufficient_new_intake_contributors"
    REVERSAL_TOO_SOON = "reversal_too_soon"
    REVERSAL_NEEDS_MORE_EVIDENCE = "reversal_needs_more_evidence"
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
    )
    next_plan = (
        proposed_macro_plan
        if action is PlanAdaptationAction.ACTIVATE and proposed_macro_plan is not None
        else current_active_macro_plan
    )
    proposed_target = recommendation_decision.proposed_calorie_target_kcal_per_day
    event = (
        None
        if effective_date is None
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
        )
    )
    return PlanAdaptationDecision(
        action=action,
        activation_available=action is PlanAdaptationAction.ACTIVATE,
        user_attention_required=action is PlanAdaptationAction.ACTIVATE,
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
            "Cooldown and fresh evidence use observation dates, not wall-clock time.",
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
    return (
        len(fresh),
        sum(item.body_weight_kg is not None for item in fresh),
        sum(item.energy_intake_kcal is not None for item in fresh),
    )


def _activation_action(
    decision: RecommendationDecision,
    effective_date: date | None,
    last_activation: PlanAdaptationEvent | None,
    new_observations: int,
    new_weight: int,
    new_intake: int,
    config: PlanAdaptationConfig,
) -> tuple[PlanAdaptationAction, tuple[PlanAdaptationReason, ...]]:
    if effective_date is None:
        return PlanAdaptationAction.DEFER, (PlanAdaptationReason.NO_EFFECTIVE_DATE,)
    if decision.decision is RecommendationDecisionType.HOLD:
        return PlanAdaptationAction.HOLD, (PlanAdaptationReason.DECISION_HOLD,)
    if decision.decision is RecommendationDecisionType.DEFER:
        return PlanAdaptationAction.DEFER, (PlanAdaptationReason.DECISION_DEFER,)
    if last_activation is None:
        return PlanAdaptationAction.ACTIVATE, (
            PlanAdaptationReason.NO_PRIOR_ACTIVATION,
            PlanAdaptationReason.PROPOSAL_ACTIVATED,
        )
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
        if elapsed < config.minimum_reversal_interval_days:
            fresh_reasons.append(PlanAdaptationReason.REVERSAL_TOO_SOON)
        if (
            new_weight < config.minimum_reversal_weight_contributors
            or new_intake < config.minimum_reversal_intake_contributors
        ):
            fresh_reasons.append(PlanAdaptationReason.REVERSAL_NEEDS_MORE_EVIDENCE)
        if fresh_reasons:
            return PlanAdaptationAction.SUPPRESS, tuple(dict.fromkeys(fresh_reasons))
    if fresh_reasons:
        return PlanAdaptationAction.DEFER, tuple(dict.fromkeys(fresh_reasons))
    return PlanAdaptationAction.ACTIVATE, (PlanAdaptationReason.PROPOSAL_ACTIVATED,)
