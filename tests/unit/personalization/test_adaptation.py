"""Longitudinal activation-gating contracts."""

from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest

from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.adaptation import (
    PlanAdaptationAction,
    PlanAdaptationConfig,
    PlanAdaptationError,
    PlanAdaptationReason,
    evaluate_plan_adaptation,
)
from fitadapt.personalization.decisions import (
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


def _profile() -> UserProfile:
    return UserProfile(
        30,
        180,
        80,
        SexForMifflinEquation.MALE,
        ActivityLevel.MODERATELY_ACTIVE,
        Goal.CUT,
        -0.4,
    )


def _observations(start: date, days: int, intake: float = 2400) -> tuple[DailyObservation, ...]:
    return tuple(
        DailyObservation(
            start + timedelta(days=index),
            80 - 0.01 * index,
            intake,
        )
        for index in range(days)
    )


def _plans() -> tuple[object, object]:
    profile = _profile()
    preferences = NutritionPreferences(MacroStrategy.BALANCED)
    current = calculate_personalized_macro_plan(
        profile, 2400, MacroCalorieSource.BASELINE, preferences
    )
    proposed = calculate_personalized_macro_plan(
        profile, 2300, MacroCalorieSource.BASELINE, preferences
    )
    return current, proposed


def _decision(current, proposed, progress=GoalProgressStatus.SLOWER_THAN_EXPECTED):
    profile = _profile()
    outcome = assess_plan_outcome(profile, _observations(date(2026, 1, 1), 28), 2400)
    outcome = outcome.__class__(
        **{
            **{field: getattr(outcome, field) for field in outcome.__dataclass_fields__},
            "overall_interpretability": OutcomeInterpretability.INTERPRETABLE,
            "intake_adherence": IntakeAdherenceStatus.NEAR_TARGET,
            "weight_trend_status": WeightTrendStatus.AVAILABLE,
            "goal_progress": progress,
            "observed_weight_change_kg_per_week": -0.1,
            "weight_span_days": 21,
        }
    )
    return decide_plan_adjustment(profile, current.calorie_target_kcal_per_day, current, outcome)


def test_first_proposal_activates_and_returns_new_immutable_history() -> None:
    current, proposed = _plans()
    decision = _decision(current, proposed)
    result = evaluate_plan_adaptation(
        current,
        decision,
        proposed,
        date(2026, 1, 28),
        observations=_observations(date(2026, 1, 1), 28),
    )

    assert result.action is PlanAdaptationAction.ACTIVATE
    assert result.activation_available is True
    assert result.next_active_macro_plan == proposed
    assert result.current_active_macro_plan == current
    assert len(result.adaptation_history) == 1
    assert result.adaptation_history[0].action is PlanAdaptationAction.ACTIVATE


def test_same_observations_defer_during_cooldown() -> None:
    current, proposed = _plans()
    decision = _decision(current, proposed)
    first = evaluate_plan_adaptation(
        current,
        decision,
        proposed,
        date(2026, 1, 28),
        observations=_observations(date(2026, 1, 1), 28),
    )
    second = evaluate_plan_adaptation(
        current,
        decision,
        proposed,
        date(2026, 1, 28),
        prior_events=first.adaptation_history,
        observations=_observations(date(2026, 1, 1), 28),
    )

    assert second.action is PlanAdaptationAction.DEFER
    assert PlanAdaptationReason.COOLDOWN_ACTIVE in second.reason_codes
    assert second.next_active_macro_plan == current


def test_enough_new_same_direction_evidence_activates_again() -> None:
    current, proposed = _plans()
    profile = _profile()
    proposed_again = calculate_personalized_macro_plan(
        profile, 2200, MacroCalorieSource.BASELINE, NutritionPreferences(MacroStrategy.BALANCED)
    )
    decision = _decision(current, proposed)
    first = evaluate_plan_adaptation(
        current,
        decision,
        proposed,
        date(2026, 1, 28),
        observations=_observations(date(2026, 1, 1), 28),
    )
    second_decision = _decision(proposed, proposed_again)
    result = evaluate_plan_adaptation(
        proposed,
        second_decision,
        proposed_again,
        date(2026, 2, 20),
        prior_events=first.adaptation_history,
        observations=_observations(date(2026, 1, 1), 51),
    )

    assert result.action is PlanAdaptationAction.ACTIVATE


def test_reversal_requires_stronger_fresh_evidence_then_activates() -> None:
    current, proposed = _plans()
    decision = _decision(current, proposed)
    first = evaluate_plan_adaptation(
        current,
        decision,
        proposed,
        date(2026, 1, 28),
        observations=_observations(date(2026, 1, 1), 28),
    )
    reversal = _decision(proposed, current, GoalProgressStatus.FASTER_THAN_EXPECTED)
    suppressed = evaluate_plan_adaptation(
        proposed,
        reversal,
        current,
        date(2026, 2, 20),
        prior_events=first.adaptation_history,
        observations=_observations(date(2026, 1, 1), 35),
    )
    activated = evaluate_plan_adaptation(
        proposed,
        reversal,
        current,
        date(2026, 3, 1),
        prior_events=first.adaptation_history,
        observations=_observations(date(2026, 1, 1), 60),
    )

    assert suppressed.action is PlanAdaptationAction.SUPPRESS
    assert PlanAdaptationReason.REVERSAL_NEEDS_MORE_EVIDENCE in suppressed.reason_codes
    assert activated.action is PlanAdaptationAction.ACTIVATE


def test_hold_and_defer_do_not_change_active_plan() -> None:
    current, proposed = _plans()
    hold_decision = _decision(current, proposed, GoalProgressStatus.BROADLY_ON_TRACK)
    result = evaluate_plan_adaptation(
        current,
        hold_decision,
        proposed,
        date(2026, 1, 28),
        observations=_observations(date(2026, 1, 1), 28),
    )

    assert result.action is PlanAdaptationAction.HOLD
    assert result.next_active_macro_plan == current
    assert result.calorie_delta_kcal_per_day == 0


def test_future_observations_do_not_count_before_as_of_date() -> None:
    current, proposed = _plans()
    decision = _decision(current, proposed)
    first = evaluate_plan_adaptation(
        current,
        decision,
        proposed,
        date(2026, 1, 28),
        observations=_observations(date(2026, 1, 1), 28),
    )
    later = evaluate_plan_adaptation(
        proposed,
        _decision(proposed, current, GoalProgressStatus.FASTER_THAN_EXPECTED),
        current,
        date(2026, 2, 11),
        prior_events=first.adaptation_history,
        observations=_observations(date(2026, 1, 1), 60),
    )
    prefix = evaluate_plan_adaptation(
        proposed,
        _decision(proposed, current, GoalProgressStatus.FASTER_THAN_EXPECTED),
        current,
        date(2026, 2, 11),
        prior_events=first.adaptation_history,
        observations=_observations(date(2026, 1, 1), 42),
    )

    assert later.action is prefix.action
    assert later.reason_codes == prefix.reason_codes
    assert later.new_observation_count == prefix.new_observation_count


def test_history_validation_is_strict_and_input_is_not_mutated() -> None:
    current, proposed = _plans()
    decision = _decision(current, proposed)
    first = evaluate_plan_adaptation(
        current,
        decision,
        proposed,
        date(2026, 1, 28),
        observations=_observations(date(2026, 1, 1), 28),
    )
    history = list(first.adaptation_history)
    with pytest.raises(PlanAdaptationError):
        evaluate_plan_adaptation(
            proposed,
            decision,
            current,
            date(2026, 2, 28),
            prior_events=history + history,
        )
    assert len(history) == 1


def test_no_effective_date_defers_without_event() -> None:
    current, proposed = _plans()
    decision = _decision(current, proposed)
    result = evaluate_plan_adaptation(current, decision, proposed, None)

    assert result.action is PlanAdaptationAction.DEFER
    assert result.adaptation_history == ()
    assert PlanAdaptationReason.NO_EFFECTIVE_DATE in result.reason_codes


def test_config_rejects_invalid_threshold() -> None:
    with pytest.raises(PlanAdaptationError):
        PlanAdaptationConfig(minimum_new_observations=0)


def test_decision_hold_and_defer_actions_are_distinct() -> None:
    current, proposed = _plans()
    hold = _decision(current, proposed, GoalProgressStatus.BROADLY_ON_TRACK)
    deferred = replace(hold, decision=RecommendationDecisionType.DEFER)

    held = evaluate_plan_adaptation(current, hold, proposed, date(2026, 1, 28))
    delayed = evaluate_plan_adaptation(current, deferred, proposed, date(2026, 1, 28))

    assert held.action is PlanAdaptationAction.HOLD
    assert delayed.action is PlanAdaptationAction.DEFER


def test_invalid_evaluation_inputs_are_rejected() -> None:
    current, proposed = _plans()
    decision = _decision(current, proposed)
    with pytest.raises(PlanAdaptationError):
        evaluate_plan_adaptation(object(), decision, proposed, date(2026, 1, 28))  # type: ignore[arg-type]
    with pytest.raises(PlanAdaptationError):
        evaluate_plan_adaptation(current, object(), proposed, date(2026, 1, 28))  # type: ignore[arg-type]
    with pytest.raises(PlanAdaptationError):
        evaluate_plan_adaptation(current, decision, proposed, datetime(2026, 1, 28))
    with pytest.raises(PlanAdaptationError):
        evaluate_plan_adaptation(current, decision, proposed, date(2026, 1, 28), source=object())  # type: ignore[arg-type]
    with pytest.raises(PlanAdaptationError):
        evaluate_plan_adaptation(current, decision, proposed, date(2026, 1, 28), config=object())  # type: ignore[arg-type]
    with pytest.raises(PlanAdaptationError):
        evaluate_plan_adaptation(
            current, decision, proposed, date(2026, 1, 28), observations=(object(),)
        )  # type: ignore[arg-type]
    with pytest.raises(PlanAdaptationError):
        evaluate_plan_adaptation(
            current, decision, proposed, date(2026, 1, 28), outcome_assessment=object()
        )  # type: ignore[arg-type]
    with pytest.raises(PlanAdaptationError):
        evaluate_plan_adaptation(proposed, decision, current, date(2026, 1, 28))
    with pytest.raises(PlanAdaptationError):
        evaluate_plan_adaptation(current, decision, None, date(2026, 1, 28))
    with pytest.raises(PlanAdaptationError):
        evaluate_plan_adaptation(current, decision, _plans()[0], date(2026, 1, 28))


def test_event_validation_and_history_order_are_strict() -> None:
    current, proposed = _plans()
    decision = _decision(current, proposed)
    result = evaluate_plan_adaptation(
        current,
        decision,
        proposed,
        date(2026, 1, 28),
        observations=_observations(date(2026, 1, 1), 28),
    )
    event = result.adaptation_history[0]
    with pytest.raises(PlanAdaptationError):
        replace(event, effective_date=None)
    with pytest.raises(PlanAdaptationError):
        replace(event, calorie_delta_kcal_per_day=0)
    with pytest.raises(PlanAdaptationError):
        replace(event, reason_codes=("bad",))
    with pytest.raises(PlanAdaptationError):
        evaluate_plan_adaptation(
            proposed,
            decision,
            current,
            date(2026, 1, 27),
            prior_events=result.adaptation_history,
        )
