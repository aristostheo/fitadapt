"""Immutable, explainable recommendation history derived from adaptation events."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from fitadapt.personalization.adaptation import (
    PlanAdaptationAction,
    PlanAdaptationEvent,
    PlanAdaptationSource,
)
from fitadapt.personalization.decisions import RecommendationDecisionType
from fitadapt.personalization.macros import PersonalizedMacroPlan

RECOMMENDATION_HISTORY_POLICY_VERSION = "recommendation_history_v1"


class RecommendationHistoryError(ValueError):
    """Raised when recommendation-history inputs are invalid."""


class RecommendationChangeType(StrEnum):
    INITIAL_PLAN = "initial_plan"
    PROFILE_UPDATE = "profile_update"
    CALORIE_INCREASE = "calorie_increase"
    CALORIE_DECREASE = "calorie_decrease"
    HOLD = "hold"
    DEFER = "defer"
    SUPPRESSED = "suppressed"


class RecommendationChangeReason(StrEnum):
    INITIAL_ACTIVE_PLAN = "initial_active_plan"
    PROFILE_UPDATE = "profile_update"
    PROGRESS_ADAPTATION = "progress_adaptation"
    PLAN_HELD = "plan_held"
    MORE_EVIDENCE_REQUIRED = "more_evidence_required"
    REVERSAL_SUPPRESSED = "reversal_suppressed"


@dataclass(frozen=True, slots=True)
class MacroSummary:
    protein_g_per_day: float
    carbohydrate_g_per_day: float
    fat_g_per_day: float
    calorie_target_kcal_per_day: float
    macro_policy_version: str


@dataclass(frozen=True, slots=True)
class RecommendationHistoryEntry:
    effective_date: date
    source: PlanAdaptationSource
    action: PlanAdaptationAction
    change_type: RecommendationChangeType
    is_plan_change: bool
    is_evaluation_only: bool
    is_current_active_plan: bool
    previous_calorie_target_kcal_per_day: float
    resulting_or_proposed_calorie_target_kcal_per_day: float
    calorie_delta_kcal_per_day: float
    previous_macro_summary: MacroSummary | None
    resulting_or_proposed_macro_summary: MacroSummary | None
    recommendation_decision: RecommendationDecisionType
    evidence_as_of_date: date | None
    observation_window_days: int | None
    high_level_reason: RecommendationChangeReason
    reason_codes: tuple[str, ...]
    user_summary: str
    policy_versions: tuple[str, ...]
    assumptions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecommendationHistory:
    entries: tuple[RecommendationHistoryEntry, ...]
    latest_change: RecommendationHistoryEntry | None
    has_new_recommendation_event: bool
    actionable_event_available: bool
    current_active_target_kcal_per_day: float
    policy_version: str
    assumptions: tuple[str, ...]


def build_recommendation_history(
    adaptation_events: Sequence[PlanAdaptationEvent],
    *,
    current_active_macro_plan: PersonalizedMacroPlan | None = None,
    proposed_macro_plan: PersonalizedMacroPlan | None = None,
    initial_plan_date: date | None = None,
) -> RecommendationHistory:
    """Build a deterministic audit stream without persisting or mutating caller input."""
    if not isinstance(adaptation_events, (tuple, list)) or not all(
        isinstance(event, PlanAdaptationEvent) for event in adaptation_events
    ):
        raise RecommendationHistoryError(
            "adaptation_events must be a list or tuple of PlanAdaptationEvent values."
        )
    if current_active_macro_plan is not None and not isinstance(
        current_active_macro_plan, PersonalizedMacroPlan
    ):
        raise RecommendationHistoryError(
            "current_active_macro_plan must be a PersonalizedMacroPlan or None."
        )
    if proposed_macro_plan is not None and not isinstance(
        proposed_macro_plan, PersonalizedMacroPlan
    ):
        raise RecommendationHistoryError(
            "proposed_macro_plan must be a PersonalizedMacroPlan or None."
        )
    if initial_plan_date is not None and not isinstance(initial_plan_date, date):
        raise RecommendationHistoryError("initial_plan_date must be a date or None.")
    events = tuple(adaptation_events)
    if any(event.effective_date is None for event in events):
        raise RecommendationHistoryError("history events require an effective date.")
    ordered = tuple(sorted(events, key=lambda event: event.effective_date))
    if len({event.effective_date for event in ordered}) != len(ordered):
        raise RecommendationHistoryError("history events cannot share an effective date.")
    entries: list[RecommendationHistoryEntry] = []
    if not ordered and current_active_macro_plan is not None and initial_plan_date is not None:
        summary = _macro_summary(current_active_macro_plan)
        entries.append(
            RecommendationHistoryEntry(
                effective_date=initial_plan_date,
                source=PlanAdaptationSource.PROGRESS_ADAPTATION,
                action=PlanAdaptationAction.ACTIVATE,
                change_type=RecommendationChangeType.INITIAL_PLAN,
                is_plan_change=True,
                is_evaluation_only=False,
                is_current_active_plan=True,
                previous_calorie_target_kcal_per_day=current_active_macro_plan.calorie_target_kcal_per_day,
                resulting_or_proposed_calorie_target_kcal_per_day=current_active_macro_plan.calorie_target_kcal_per_day,
                calorie_delta_kcal_per_day=0.0,
                previous_macro_summary=None,
                resulting_or_proposed_macro_summary=summary,
                recommendation_decision=RecommendationDecisionType.HOLD,
                evidence_as_of_date=initial_plan_date,
                observation_window_days=None,
                high_level_reason=RecommendationChangeReason.INITIAL_ACTIVE_PLAN,
                reason_codes=("initial_active_plan",),
                user_summary="Your initial active plan was created.",
                policy_versions=(
                    RECOMMENDATION_HISTORY_POLICY_VERSION,
                    current_active_macro_plan.macro_policy_version,
                ),
                assumptions=(
                    "This initial entry is a stateless representation of the supplied active plan.",
                ),
            )
        )
    for event in ordered:
        entries.append(_entry(event, current_active_macro_plan, proposed_macro_plan))
    entries_tuple = tuple(entries)
    if current_active_macro_plan is not None:
        matching_index = next(
            (
                index
                for index in range(len(entries_tuple) - 1, -1, -1)
                if entries_tuple[index].is_plan_change
                and entries_tuple[index].resulting_or_proposed_calorie_target_kcal_per_day
                == current_active_macro_plan.calorie_target_kcal_per_day
            ),
            None,
        )
        if matching_index is not None:
            entries_tuple = tuple(
                entry
                if index != matching_index
                else dataclass_replace(entry, is_current_active_plan=True)
                for index, entry in enumerate(entries_tuple)
            )
    current_target = (
        current_active_macro_plan.calorie_target_kcal_per_day
        if current_active_macro_plan is not None
        else (
            entries_tuple[-1].resulting_or_proposed_calorie_target_kcal_per_day
            if entries_tuple
            else 0.0
        )
    )
    actual = tuple(entry for entry in entries_tuple if entry.is_plan_change)
    latest = entries_tuple[-1] if entries_tuple else None
    return RecommendationHistory(
        entries=entries_tuple,
        latest_change=actual[-1] if actual else latest,
        has_new_recommendation_event=latest is not None,
        actionable_event_available=any(entry.is_plan_change for entry in entries_tuple),
        current_active_target_kcal_per_day=current_target,
        policy_version=RECOMMENDATION_HISTORY_POLICY_VERSION,
        assumptions=(
            "History is built from caller-supplied immutable events and is not persisted.",
            "Evaluation-only entries remain visible for auditability but are distinct from "
            "plan changes.",
            "Older entries are not rewritten by newer observations or events.",
        ),
    )


def _entry(
    event: PlanAdaptationEvent,
    current_plan: PersonalizedMacroPlan | None,
    proposed_plan: PersonalizedMacroPlan | None,
) -> RecommendationHistoryEntry:
    activated = (
        event.action is PlanAdaptationAction.ACTIVATE and event.calorie_delta_kcal_per_day != 0
    )
    if event.source is PlanAdaptationSource.PROFILE_RECALCULATION:
        change_type = RecommendationChangeType.PROFILE_UPDATE
        reason = RecommendationChangeReason.PROFILE_UPDATE
        summary = "Your profile update recalculated your plan."
    elif activated and event.calorie_delta_kcal_per_day > 0:
        change_type = RecommendationChangeType.CALORIE_INCREASE
        reason = RecommendationChangeReason.PROGRESS_ADAPTATION
        summary = "Your calorie target increased based on recent progress evidence."
    elif activated:
        change_type = RecommendationChangeType.CALORIE_DECREASE
        reason = RecommendationChangeReason.PROGRESS_ADAPTATION
        summary = "Your calorie target decreased based on recent progress evidence."
    elif event.action is PlanAdaptationAction.HOLD:
        change_type = RecommendationChangeType.HOLD
        reason = RecommendationChangeReason.PLAN_HELD
        summary = "Your plan stayed the same because progress was broadly on track."
    elif event.action is PlanAdaptationAction.SUPPRESS:
        change_type = RecommendationChangeType.SUPPRESSED
        reason = RecommendationChangeReason.REVERSAL_SUPPRESSED
        summary = "A reversal was suppressed because your plan was adjusted recently."
    else:
        change_type = RecommendationChangeType.DEFER
        reason = RecommendationChangeReason.MORE_EVIDENCE_REQUIRED
        summary = "FitAdapt is collecting more data before making another change."
    previous_summary = None if current_plan is None else _macro_summary(current_plan)
    resulting_summary = None
    if proposed_plan is not None and activated:
        resulting_summary = _macro_summary(proposed_plan)
    elif current_plan is not None and change_type in (
        RecommendationChangeType.HOLD,
        RecommendationChangeType.DEFER,
        RecommendationChangeType.SUPPRESSED,
    ):
        resulting_summary = _macro_summary(current_plan)
    return RecommendationHistoryEntry(
        effective_date=event.effective_date,
        source=event.source,
        action=event.action,
        change_type=change_type,
        is_plan_change=activated
        or event.source is PlanAdaptationSource.PROFILE_RECALCULATION
        and event.calorie_delta_kcal_per_day != 0,
        is_evaluation_only=not (
            activated
            or event.source is PlanAdaptationSource.PROFILE_RECALCULATION
            and event.calorie_delta_kcal_per_day != 0
        ),
        is_current_active_plan=False,
        previous_calorie_target_kcal_per_day=event.previous_active_target_kcal_per_day,
        resulting_or_proposed_calorie_target_kcal_per_day=event.new_active_target_kcal_per_day,
        calorie_delta_kcal_per_day=event.calorie_delta_kcal_per_day,
        previous_macro_summary=previous_summary,
        resulting_or_proposed_macro_summary=resulting_summary,
        recommendation_decision=event.recommendation_decision,
        evidence_as_of_date=event.evidence_as_of_date,
        observation_window_days=None,
        high_level_reason=reason,
        reason_codes=tuple(code.value for code in event.reason_codes),
        user_summary=summary,
        policy_versions=(RECOMMENDATION_HISTORY_POLICY_VERSION, event.policy_version),
        assumptions=(
            "Summary is deterministically derived from source, action, delta, and reason codes.",
        ),
    )


def _macro_summary(plan: PersonalizedMacroPlan) -> MacroSummary:
    return MacroSummary(
        protein_g_per_day=plan.protein_g_per_day,
        carbohydrate_g_per_day=plan.carbohydrate_g_per_day,
        fat_g_per_day=plan.fat_g_per_day,
        calorie_target_kcal_per_day=plan.calorie_target_kcal_per_day,
        macro_policy_version=plan.macro_policy_version,
    )


def dataclass_replace(
    entry: RecommendationHistoryEntry, *, is_current_active_plan: bool
) -> RecommendationHistoryEntry:
    """Replace one immutable marker without exposing mutable history state."""
    return RecommendationHistoryEntry(
        **{
            field: (
                is_current_active_plan
                if field == "is_current_active_plan"
                else getattr(entry, field)
            )
            for field in entry.__dataclass_fields__
        }
    )
