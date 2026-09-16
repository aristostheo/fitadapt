"""Tests for conservative calorie recommendation eligibility."""

import math
from dataclasses import FrozenInstanceError
from datetime import date, timedelta

import pytest

from fitadapt.analysis.trends import TrendAnalysisError
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.recommendation.calories import (
    CalorieRecommendationConfig,
    CalorieRecommendationError,
    RecommendationReason,
    RecommendationStatus,
    _apply_adjustment_policy,
    _proposed_target_safety_reason,
    recommend_calorie_adjustment,
)


def profile() -> UserProfile:
    return UserProfile(
        30,
        180.0,
        80.0,
        SexForMifflinEquation.MALE,
        ActivityLevel.MODERATELY_ACTIVE,
        Goal.MAINTAIN,
        0.0,
    )


def test_config_validation_and_normalization() -> None:
    assert (
        type(
            CalorieRecommendationConfig(hold_threshold_kcal_per_day=75).hold_threshold_kcal_per_day
        )
        is float
    )
    invalid = (
        ("minimum_calendar_history_days", True),
        ("minimum_weight_completeness", math.nan),
        ("minimum_intake_completeness", 1.1),
        ("hold_threshold_kcal_per_day", -1),
        ("maximum_adjustment_kcal_per_day", 0),
    )
    for field, value in invalid:
        with pytest.raises(CalorieRecommendationError, match=field):
            CalorieRecommendationConfig(**{field: value})  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["minimum_calendar_history_days", "minimum_adaptive_estimates"])
@pytest.mark.parametrize("value", [0, -1, True, 1.0, "1", None])
def test_integer_configuration_fields_are_strict(field: str, value: object) -> None:
    with pytest.raises(CalorieRecommendationError, match=field):
        CalorieRecommendationConfig(**{field: value})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field",
    [
        "minimum_weight_completeness",
        "minimum_intake_completeness",
        "hold_threshold_kcal_per_day",
        "maximum_adjustment_kcal_per_day",
    ],
)
@pytest.mark.parametrize("value", [True, "1", None, math.nan, math.inf, -math.inf])
def test_float_configuration_fields_reject_non_finite_or_non_numeric(
    field: str, value: object
) -> None:
    with pytest.raises(CalorieRecommendationError, match=field):
        CalorieRecommendationConfig(**{field: value})  # type: ignore[arg-type]


def test_completeness_boundaries_and_integer_normalization() -> None:
    config = CalorieRecommendationConfig(
        minimum_weight_completeness=0, minimum_intake_completeness=1
    )
    assert config.minimum_weight_completeness == 0.0
    assert config.minimum_intake_completeness == 1.0
    for field, value in (
        ("minimum_weight_completeness", -0.1),
        ("minimum_intake_completeness", 1.1),
    ):
        with pytest.raises(CalorieRecommendationError, match=field):
            CalorieRecommendationConfig(**{field: value})  # type: ignore[arg-type]


def test_empty_observations_returns_ordered_insufficient_evidence() -> None:
    result = recommend_calorie_adjustment(profile(), [])
    assert result.status is RecommendationStatus.INSUFFICIENT_DATA
    assert result.reasons == (
        RecommendationReason.INSUFFICIENT_HISTORY,
        RecommendationReason.INSUFFICIENT_WEIGHT_COMPLETENESS,
        RecommendationReason.INSUFFICIENT_INTAKE_COMPLETENESS,
        RecommendationReason.MISSING_RECENT_INTAKE,
        RecommendationReason.MISSING_WEIGHT_TREND,
        RecommendationReason.ADAPTIVE_TDEE_UNAVAILABLE,
        RecommendationReason.INSUFFICIENT_ADAPTIVE_ESTIMATES,
    )
    assert result.recommended_adjustment_kcal_per_day is None


def test_invalid_main_inputs_are_rejected() -> None:
    with pytest.raises(CalorieRecommendationError):
        recommend_calorie_adjustment("profile", [])  # type: ignore[arg-type]
    with pytest.raises(CalorieRecommendationError):
        recommend_calorie_adjustment(profile(), "observations")  # type: ignore[arg-type]


def observations(intake: float = 2000.0) -> list[DailyObservation]:
    return [
        DailyObservation(
            observed_on=date(2026, 1, 1) + timedelta(days=index),
            body_weight_kg=80.0,
            energy_intake_kcal=intake,
            steps=5000,
        )
        for index in range(30)
    ]


def test_sufficient_stable_maintenance_data_holds_current_intake() -> None:
    result = recommend_calorie_adjustment(profile(), observations())
    assert result.status is RecommendationStatus.HOLD
    assert result.raw_adjustment_kcal_per_day == pytest.approx(0.0)
    assert result.recommended_adjustment_kcal_per_day == 0.0
    assert result.proposed_intake_target_kcal_per_day == pytest.approx(2000.0)


def test_cut_reuses_signed_energy_adjustment_and_limits_recommendation() -> None:
    cut = UserProfile(
        30, 180.0, 80.0, SexForMifflinEquation.MALE, ActivityLevel.MODERATELY_ACTIVE, Goal.CUT, -0.4
    )
    result = recommend_calorie_adjustment(cut, observations())
    assert result.status is RecommendationStatus.DECREASE_CALORIES
    assert result.raw_adjustment_kcal_per_day == pytest.approx(-440.0)
    assert result.recommended_adjustment_kcal_per_day == -150.0
    assert result.proposed_intake_target_kcal_per_day == pytest.approx(1850.0)
    assert result.reasons == (RecommendationReason.LIMITED_BY_MAXIMUM_ADJUSTMENT,)


@pytest.mark.parametrize(
    ("raw", "status", "reason", "limited"),
    [
        (-75.0, RecommendationStatus.HOLD, RecommendationReason.WITHIN_HOLD_THRESHOLD, 0.0),
        (75.0, RecommendationStatus.HOLD, RecommendationReason.WITHIN_HOLD_THRESHOLD, 0.0),
        (
            75.1,
            RecommendationStatus.INCREASE_CALORIES,
            RecommendationReason.ADJUSTMENT_RECOMMENDED,
            75.1,
        ),
        (
            -150.0,
            RecommendationStatus.DECREASE_CALORIES,
            RecommendationReason.ADJUSTMENT_RECOMMENDED,
            -150.0,
        ),
        (
            150.0,
            RecommendationStatus.INCREASE_CALORIES,
            RecommendationReason.ADJUSTMENT_RECOMMENDED,
            150.0,
        ),
        (
            300.0,
            RecommendationStatus.INCREASE_CALORIES,
            RecommendationReason.LIMITED_BY_MAXIMUM_ADJUSTMENT,
            150.0,
        ),
        (
            -300.0,
            RecommendationStatus.DECREASE_CALORIES,
            RecommendationReason.LIMITED_BY_MAXIMUM_ADJUSTMENT,
            -150.0,
        ),
    ],
)
def test_adjustment_policy_threshold_and_limiting_boundaries(
    raw: float, status: RecommendationStatus, reason: RecommendationReason, limited: float
) -> None:
    assert _apply_adjustment_policy(raw, CalorieRecommendationConfig()) == (status, reason, limited)


def test_zero_intake_is_present_unsorted_is_deterministic_and_duplicates_raise() -> None:
    zero = observations(0.0)
    result = recommend_calorie_adjustment(profile(), zero)
    assert result.intake_completeness == 1.0
    assert result.recent_mean_intake_kcal_per_day == 0.0
    assert recommend_calorie_adjustment(
        profile(), list(reversed(observations()))
    ) == recommend_calorie_adjustment(profile(), observations())
    with pytest.raises(TrendAnalysisError, match="Duplicate"):
        recommend_calorie_adjustment(profile(), [*observations(), observations()[0]])


def test_goal_signed_adjustments_and_proposed_target_use_hand_values() -> None:
    gain = UserProfile(
        30, 180.0, 80.0, SexForMifflinEquation.MALE, ActivityLevel.MODERATELY_ACTIVE, Goal.GAIN, 0.2
    )
    result = recommend_calorie_adjustment(gain, observations(2000.0))
    expected_daily_goal_adjustment = 0.2 * 7700.0 / 7.0
    assert result.personalized_goal_target_kcal_per_day == pytest.approx(
        2000.0 + expected_daily_goal_adjustment
    )
    assert result.status is RecommendationStatus.INCREASE_CALORIES
    assert result.recommended_adjustment_kcal_per_day == 150.0
    assert result.proposed_intake_target_kcal_per_day == pytest.approx(2150.0)


def test_missing_intake_remains_missing_and_outputs_are_none() -> None:
    partial = [
        DailyObservation(date(2026, 1, 1) + timedelta(days=index), 80.0, None, 5000)
        for index in range(30)
    ]
    result = recommend_calorie_adjustment(profile(), partial)
    assert result.recent_mean_intake_kcal_per_day is None
    assert result.personalized_goal_target_kcal_per_day is None
    assert result.recommended_adjustment_kcal_per_day is None


def test_proposed_target_safety_boundaries_reuse_macro_policy() -> None:
    minimum = 80.0 * 1.6 * 4.0 + 80.0 * 0.6 * 9.0
    assert (
        _proposed_target_safety_reason(profile(), 0.0)
        is RecommendationReason.NON_POSITIVE_PROPOSED_TARGET
    )
    assert (
        _proposed_target_safety_reason(profile(), -1.0)
        is RecommendationReason.NON_POSITIVE_PROPOSED_TARGET
    )
    assert (
        _proposed_target_safety_reason(profile(), minimum - 0.1)
        is RecommendationReason.MACRO_POLICY_INFEASIBLE_PROPOSED_TARGET
    )
    assert _proposed_target_safety_reason(profile(), minimum) is None
    assert _proposed_target_safety_reason(profile(), minimum + 0.1) is None


def test_recommendation_models_are_frozen_and_inputs_are_unchanged() -> None:
    source = observations()
    snapshot = tuple(source)
    result = recommend_calorie_adjustment(profile(), source)
    assert source == list(snapshot)
    assert recommend_calorie_adjustment(profile(), source) == result
    with pytest.raises(FrozenInstanceError):
        result.status = RecommendationStatus.HOLD  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        CalorieRecommendationConfig().hold_threshold_kcal_per_day = 1.0  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result.reasons.append(RecommendationReason.ADJUSTMENT_RECOMMENDED)  # type: ignore[attr-defined]
