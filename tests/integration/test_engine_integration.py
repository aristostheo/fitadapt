"""End-to-end app-integration scenarios across CP28-CP31."""

from datetime import date, timedelta

from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.adaptation import PlanAdaptationSource
from fitadapt.personalization.intelligence import analyze_profile_intelligence
from fitadapt.personalization.macros import MacroStrategy, NutritionPreferences


def _profile(goal: Goal = Goal.CUT, rate: float = -0.4) -> UserProfile:
    return UserProfile(
        30,
        180,
        80,
        SexForMifflinEquation.MALE,
        ActivityLevel.MODERATELY_ACTIVE,
        goal,
        rate,
    )


def _observations(days: int = 50, intake: float = 2320) -> tuple[DailyObservation, ...]:
    return tuple(
        DailyObservation(
            date(2026, 1, 1) + timedelta(days=index),
            80 - 0.10 * index,
            intake,
            steps=5000,
        )
        for index in range(days)
    )


def test_initial_and_daily_flow_have_one_authoritative_current_recommendation() -> None:
    profile = _profile()
    preferences = NutritionPreferences(MacroStrategy.BALANCED)
    initial = analyze_profile_intelligence(profile, (), preferences)
    daily = analyze_profile_intelligence(profile, _observations(), preferences)

    assert initial.current_recommendation.is_authoritative is True
    assert initial.current_recommendation.is_active is True
    assert initial.integration_status.more_data_needed is True
    assert initial.integration_status.app_status.value == "more_data_needed"
    assert (
        daily.current_recommendation.calorie_target_kcal_per_day
        == daily.plan_adaptation.current_active_target_kcal_per_day
    )
    assert (
        daily.current_recommendation.macro_plan == daily.plan_adaptation.current_active_macro_plan
    )


def test_short_or_ambiguous_adaptive_evidence_defers_and_never_activates_decrease() -> None:
    profile = _profile()
    preferences = NutritionPreferences(MacroStrategy.BALANCED)
    result = analyze_profile_intelligence(profile, _observations(28), preferences)

    assert result.recommendation_decision.decision.value in ("hold", "defer", "increase")
    assert (
        result.plan_adaptation.action.value != "activate"
        or result.plan_adaptation.calorie_delta_kcal_per_day >= 0
    )
    if result.recommendation_decision.decision.value == "defer":
        assert result.integration_status.more_data_needed is True
        assert result.integration_status.app_status.value in {
            "more_data_needed",
            "deferred_estimator_stabilizing",
            "deferred_adaptive_evidence_ambiguous",
        }


def test_cp30_defer_contract_is_authoritative_for_integration_status() -> None:
    profile = _profile()
    preferences = NutritionPreferences(MacroStrategy.BALANCED)
    result = analyze_profile_intelligence(profile, _observations(28, intake=2400), preferences)

    if result.recommendation_decision.decision.value == "defer":
        assert result.plan_adaptation.action.value == "defer"
        assert result.integration_status.plan_update_available is False
        assert result.integration_status.more_data_needed is True


def test_accepted_plan_handoff_becomes_authoritative_on_next_call() -> None:
    profile = _profile()
    preferences = NutritionPreferences(MacroStrategy.BALANCED)
    first = analyze_profile_intelligence(profile, _observations(), preferences)
    accepted_history = first.plan_adaptation.adaptation_history
    second = analyze_profile_intelligence(
        profile,
        _observations(),
        preferences,
        adaptation_history=accepted_history,
    )

    assert first.plan_adaptation.activation_available is True
    assert second.current_recommendation.source.value == "progress_adaptation"
    assert (
        second.current_recommendation.calorie_target_kcal_per_day
        == first.plan_adaptation.next_active_target_kcal_per_day
    )
    assert (
        second.plan_adaptation.current_active_target_kcal_per_day
        == second.current_recommendation.calorie_target_kcal_per_day
    )


def test_profile_recalculation_does_not_reuse_progress_adaptation_state() -> None:
    preferences = NutritionPreferences(MacroStrategy.BALANCED)
    old_profile = _profile()
    first = analyze_profile_intelligence(old_profile, _observations(), preferences)
    updated_profile = _profile(Goal.GAIN, 0.3)
    recalculated = analyze_profile_intelligence(
        updated_profile,
        _observations(),
        preferences,
        adaptation_history=first.plan_adaptation.adaptation_history,
        adaptation_source=PlanAdaptationSource.PROFILE_RECALCULATION,
    )

    assert recalculated.current_recommendation.source.value == "profile_recalculation"
    assert (
        recalculated.current_recommendation.calorie_target_kcal_per_day
        != first.current_recommendation.calorie_target_kcal_per_day
    )
    assert (
        recalculated.integration_status.adaptation_source
        is PlanAdaptationSource.PROFILE_RECALCULATION
    )


def test_as_of_pipeline_isolated_from_future_observations() -> None:
    profile = _profile()
    preferences = NutritionPreferences(MacroStrategy.BALANCED)
    prefix = _observations(28)
    future = prefix + (DailyObservation(date(2026, 2, 1), 100, 1000, steps=5000),)
    first = analyze_profile_intelligence(
        profile, prefix, preferences, outcome_as_of_date=date(2026, 1, 28)
    )
    second = analyze_profile_intelligence(
        profile, future, preferences, outcome_as_of_date=date(2026, 1, 28)
    )

    assert (
        second.current_recommendation.calorie_target_kcal_per_day
        == first.current_recommendation.calorie_target_kcal_per_day
    )
    assert second.recommendation_decision == first.recommendation_decision
    assert second.plan_adaptation.action is first.plan_adaptation.action
    assert second.recommendation_history == first.recommendation_history
    assert second.integration_status == first.integration_status
