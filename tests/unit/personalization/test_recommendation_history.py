"""Recommendation-history explainability contracts."""

from dataclasses import replace
from datetime import date

import pytest

from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.adaptation import (
    PlanAdaptationAction,
    PlanAdaptationEvent,
    PlanAdaptationReason,
    PlanAdaptationSource,
)
from fitadapt.personalization.decisions import RecommendationDecisionType
from fitadapt.personalization.history import (
    RecommendationChangeType,
    RecommendationHistoryError,
    build_recommendation_history,
)
from fitadapt.personalization.macros import (
    MacroCalorieSource,
    MacroStrategy,
    NutritionPreferences,
    calculate_personalized_macro_plan,
)


def _plan(target: float = 2400):
    profile = UserProfile(
        30, 180, 80, SexForMifflinEquation.MALE, ActivityLevel.MODERATELY_ACTIVE, Goal.CUT, -0.4
    )
    return calculate_personalized_macro_plan(
        profile, target, MacroCalorieSource.BASELINE, NutritionPreferences(MacroStrategy.BALANCED)
    )


def _event(
    effective_date: date,
    action: PlanAdaptationAction,
    previous: float = 2400,
    new: float = 2300,
    source: PlanAdaptationSource = PlanAdaptationSource.PROGRESS_ADAPTATION,
) -> PlanAdaptationEvent:
    return PlanAdaptationEvent(
        effective_date=effective_date,
        previous_active_target_kcal_per_day=previous,
        new_active_target_kcal_per_day=new,
        calorie_delta_kcal_per_day=new - previous,
        recommendation_decision=(
            RecommendationDecisionType.DECREASE
            if new < previous
            else RecommendationDecisionType.HOLD
        ),
        action=action,
        source=source,
        reason_codes=(
            PlanAdaptationReason.PROPOSAL_ACTIVATED
            if action is PlanAdaptationAction.ACTIVATE
            else PlanAdaptationReason.DECISION_HOLD,
        ),
        evidence_as_of_date=effective_date,
        new_observation_count=14,
        new_weight_contributor_count=7,
        new_intake_contributor_count=14,
        policy_version="plan_adaptation_v1",
    )


def test_empty_history_and_initial_plan_are_explicit() -> None:
    result = build_recommendation_history(
        (), current_active_macro_plan=_plan(), initial_plan_date=date(2026, 1, 1)
    )

    assert len(result.entries) == 1
    assert result.entries[0].change_type is RecommendationChangeType.INITIAL_PLAN
    assert result.entries[0].is_plan_change is True
    assert result.latest_change == result.entries[0]


def test_activated_decrease_is_actionable_with_macro_summary() -> None:
    result = build_recommendation_history(
        (_event(date(2026, 1, 28), PlanAdaptationAction.ACTIVATE),),
        current_active_macro_plan=_plan(2300),
        proposed_macro_plan=_plan(2300),
    )

    entry = result.entries[0]
    assert entry.change_type is RecommendationChangeType.CALORIE_DECREASE
    assert entry.is_plan_change is True
    assert entry.is_evaluation_only is False
    assert entry.resulting_or_proposed_macro_summary is not None
    assert result.actionable_event_available is True
    assert "decreased" in entry.user_summary


@pytest.mark.parametrize(
    ("action", "change_type", "phrase"),
    [
        (PlanAdaptationAction.HOLD, RecommendationChangeType.HOLD, "stayed the same"),
        (PlanAdaptationAction.DEFER, RecommendationChangeType.DEFER, "collecting more data"),
        (PlanAdaptationAction.SUPPRESS, RecommendationChangeType.SUPPRESSED, "suppressed"),
    ],
)
def test_non_activation_entries_are_visible_but_evaluation_only(
    action: PlanAdaptationAction, change_type: RecommendationChangeType, phrase: str
) -> None:
    result = build_recommendation_history(
        (_event(date(2026, 1, 28), action),), current_active_macro_plan=_plan()
    )

    entry = result.entries[0]
    assert entry.change_type is change_type
    assert entry.is_plan_change is False
    assert entry.is_evaluation_only is True
    assert phrase in entry.user_summary
    assert result.actionable_event_available is False


def test_profile_recalculation_is_distinct() -> None:
    result = build_recommendation_history(
        (
            _event(
                date(2026, 1, 28),
                PlanAdaptationAction.ACTIVATE,
                2400,
                2500,
                PlanAdaptationSource.PROFILE_RECALCULATION,
            ),
        )
    )

    assert result.entries[0].change_type is RecommendationChangeType.PROFILE_UPDATE
    assert result.entries[0].high_level_reason.value == "profile_update"


def test_history_is_sorted_and_duplicate_dates_rejected() -> None:
    first = _event(date(2026, 1, 1), PlanAdaptationAction.ACTIVATE)
    second = _event(date(2026, 1, 2), PlanAdaptationAction.HOLD)
    result = build_recommendation_history((second, first))
    assert tuple(entry.effective_date for entry in result.entries) == (
        date(2026, 1, 1),
        date(2026, 1, 2),
    )
    with pytest.raises(RecommendationHistoryError):
        build_recommendation_history((first, replace(first, action=PlanAdaptationAction.HOLD)))


def test_invalid_history_inputs_are_rejected() -> None:
    with pytest.raises(RecommendationHistoryError):
        build_recommendation_history((object(),))  # type: ignore[arg-type]
    with pytest.raises(RecommendationHistoryError):
        build_recommendation_history((), current_active_macro_plan=object())  # type: ignore[arg-type]
    with pytest.raises(RecommendationHistoryError):
        build_recommendation_history((), initial_plan_date="2026-01-01")  # type: ignore[arg-type]
