"""Tests for transparent adaptive TDEE estimation."""

import math
from dataclasses import FrozenInstanceError, astuple
from datetime import date, timedelta

import pytest

from fitadapt.adaptive.tdee import (
    AdaptiveTdeeConfig,
    AdaptiveTdeeError,
    DailyTdeeEstimate,
    TdeeEligibility,
    estimate_adaptive_tdee,
)
from fitadapt.analysis.trends import (
    DailyTrendPoint,
    DataQualityReport,
    TrendAnalysisConfig,
    TrendAnalysisResult,
    analyze_observation_trends,
)
from fitadapt.domain.observation import DailyObservation
from fitadapt.synthetic.history import SyntheticHistoryConfig, generate_synthetic_history

START = date(2026, 1, 1)


def trend_result(
    values: list[tuple[float | None, float | None]], window: int = 7
) -> TrendAnalysisResult:
    """Build deliberately simple trend features without production aggregation logic."""
    points = tuple(
        DailyTrendPoint(
            START + timedelta(days=index),
            True,
            None,
            None,
            None,
            None,
            intake,
            None,
            0,
            0,
            0,
            change,
        )
        for index, (intake, change) in enumerate(values)
    )
    quality = DataQualityReport(
        START if points else None,
        START + timedelta(days=len(points) - 1) if points else None,
        len(points),
        len(points),
        0,
        0,
        len(points),
        0.0,
        0,
        len(points),
        0.0,
        0,
        len(points),
        0.0,
    )
    return TrendAnalysisResult("test", TrendAnalysisConfig(window, 1), points, quality, ())


def test_empty_result_has_no_aggregation_dates() -> None:
    result = estimate_adaptive_tdee(trend_result([]))
    assert result.daily_estimates == ()
    assert result.adaptive_tdee_kcal_per_day is None
    assert result.median_absolute_deviation_kcal_per_day is None
    assert result.aggregation_start_date is None
    assert result.aggregation_end_date is None


def test_missing_values_produce_ineligible_estimates_in_chronological_order() -> None:
    result = estimate_adaptive_tdee(trend_result([(2000.0, None), (None, 0.1), (2000.0, 0.0)]))
    assert [item.observed_on for item in result.daily_estimates] == [
        START,
        START + timedelta(days=1),
        START + timedelta(days=2),
    ]
    assert [item.eligibility for item in result.daily_estimates] == [
        TdeeEligibility.MISSING_WEIGHT_CHANGE,
        TdeeEligibility.MISSING_INTAKE_TREND,
        TdeeEligibility.AVAILABLE,
    ]


def test_daily_formula_preserves_signed_balance_and_does_not_clamp_tdee() -> None:
    result = estimate_adaptive_tdee(
        trend_result([(2000.0, 0.0), (2000.0, -0.1), (100.0, 1.0)], window=5),
        AdaptiveTdeeConfig(7700, 3, 1),
    )
    stable, loss, extreme_gain = result.daily_estimates
    assert stable.estimated_tdee_kcal_per_day == pytest.approx(2000.0)
    assert loss.estimated_daily_energy_balance_kcal == pytest.approx(-154.0)
    assert loss.estimated_tdee_kcal_per_day == pytest.approx(2154.0)
    assert extreme_gain.estimated_tdee_kcal_per_day == pytest.approx(-1440.0)


def test_aggregation_uses_inclusive_trailing_window_and_tracks_all_eligible_points() -> None:
    result = estimate_adaptive_tdee(
        trend_result([(1000.0, 0.0), (1500.0, 0.0), (2000.0, 0.0), (3000.0, 0.0), (4000.0, 0.0)]),
        AdaptiveTdeeConfig(7700, 3, 2),
    )
    assert result.aggregation_start_date == START + timedelta(days=2)
    assert result.aggregation_end_date == START + timedelta(days=4)
    assert result.total_eligible_points == 5
    assert result.eligible_points_used == 3
    assert result.adaptive_tdee_kcal_per_day == pytest.approx(3000.0)


def test_ineligible_points_inside_aggregation_window_are_excluded() -> None:
    result = estimate_adaptive_tdee(
        trend_result([(1000.0, 0.0), (None, 0.0), (2000.0, 0.0), (3000.0, 0.0)]),
        AdaptiveTdeeConfig(7700, 3, 2),
    )
    assert result.total_eligible_points == 3
    assert result.eligible_points_used == 2
    assert result.adaptive_tdee_kcal_per_day == pytest.approx(2500.0)


def test_aggregation_medians_and_manually_verified_mad() -> None:
    odd = estimate_adaptive_tdee(
        trend_result([(1000.0, 0.0), (2000.0, 0.0), (3000.0, 0.0)]),
        AdaptiveTdeeConfig(7700, 3, 1),
    )
    even = estimate_adaptive_tdee(
        trend_result([(1000.0, 0.0), (2000.0, 0.0), (3000.0, 0.0), (4000.0, 0.0)]),
        AdaptiveTdeeConfig(7700, 4, 1),
    )
    assert odd.adaptive_tdee_kcal_per_day == pytest.approx(2000.0)
    assert odd.median_absolute_deviation_kcal_per_day == pytest.approx(1000.0)
    assert even.adaptive_tdee_kcal_per_day == pytest.approx(2500.0)
    assert even.median_absolute_deviation_kcal_per_day == pytest.approx(1000.0)


def test_aggregation_threshold_and_dates_for_insufficient_nonempty_result() -> None:
    values = [(2000.0, 0.0)] * 3
    insufficient = estimate_adaptive_tdee(trend_result(values), AdaptiveTdeeConfig(7700, 4, 4))
    assert insufficient.adaptive_tdee_kcal_per_day is None
    assert insufficient.median_absolute_deviation_kcal_per_day is None
    assert insufficient.aggregation_start_date == START - timedelta(days=1)
    assert insufficient.aggregation_end_date == START + timedelta(days=2)
    exact_threshold = estimate_adaptive_tdee(trend_result(values), AdaptiveTdeeConfig(7700, 3, 3))
    assert exact_threshold.adaptive_tdee_kcal_per_day == pytest.approx(2000.0)
    assert exact_threshold.median_absolute_deviation_kcal_per_day == 0.0


def test_one_included_estimate_has_zero_mad() -> None:
    result = estimate_adaptive_tdee(
        trend_result([(1000.0, 0.0), (2000.0, 0.0), (3000.0, 0.0)]),
        AdaptiveTdeeConfig(7700, 1, 1),
    )
    assert result.eligible_points_used == 1
    assert result.adaptive_tdee_kcal_per_day == pytest.approx(3000.0)
    assert result.median_absolute_deviation_kcal_per_day == 0.0


def test_public_values_are_plain_types_and_results_do_not_mutate_input() -> None:
    source = trend_result([(2000.0, 0.0)] * 4)
    source_snapshot = astuple(source)
    result = estimate_adaptive_tdee(source)
    estimate = result.daily_estimates[0]
    assert type(estimate.observed_on) is date
    assert type(estimate.trailing_energy_intake_mean_kcal) is float
    assert type(estimate.window_weight_change_kg) is float
    assert type(estimate.estimated_daily_energy_balance_kcal) is float
    assert type(estimate.estimated_tdee_kcal_per_day) is float
    assert type(estimate.eligibility) is TdeeEligibility
    assert type(result.eligible_points_used) is int
    assert type(result.total_eligible_points) is int
    assert source_snapshot == astuple(source)
    assert estimate_adaptive_tdee(source) == result


def test_public_dataclasses_and_daily_tuple_are_immutable() -> None:
    config = AdaptiveTdeeConfig()
    result = estimate_adaptive_tdee(trend_result([(2000.0, 0.0)] * 4), config)
    estimate = result.daily_estimates[0]
    with pytest.raises(FrozenInstanceError):
        config.aggregation_window_days = 7  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        estimate.eligibility = "arbitrary"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.daily_estimates = ()  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result.daily_estimates.append(estimate)  # type: ignore[attr-defined]


def test_eligibility_enum_rejects_arbitrary_strings_in_normal_construction() -> None:
    with pytest.raises(AdaptiveTdeeError, match="TdeeEligibility"):
        DailyTdeeEstimate(START, None, None, None, None, "available")  # type: ignore[arg-type]


def test_future_point_cannot_change_an_earlier_daily_estimate() -> None:
    base = trend_result([(2000.0, 0.0)])
    extended = trend_result([(2000.0, 0.0), (9999.0, 0.0)])
    assert (
        estimate_adaptive_tdee(base).daily_estimates[0]
        == estimate_adaptive_tdee(extended).daily_estimates[0]
    )


def test_non_finite_calculation_returns_explicit_eligibility() -> None:
    deliberately_non_finite = trend_result([(2000.0, math.inf)])
    result = estimate_adaptive_tdee(deliberately_non_finite)
    assert result.daily_estimates[0].eligibility is TdeeEligibility.NON_FINITE_RESULT
    assert result.daily_estimates[0].estimated_tdee_kcal_per_day is None


def test_controlled_synthetic_history_recovers_known_expenditure_from_observations_only() -> None:
    history = generate_synthetic_history(
        SyntheticHistoryConfig(
            start_date=START,
            days=40,
            seed=7,
            initial_true_weight_kg=80.0,
            base_daily_expenditure_kcal=2000.0,
            average_energy_intake_kcal=2500.0,
            intake_standard_deviation_kcal=0.0,
            average_steps=1000.0,
            steps_standard_deviation=0.0,
            strength_training_probability=0.0,
            strength_training_minutes=0.0,
            cardio_probability=0.0,
            cardio_minutes=0.0,
            scale_weight_noise_standard_deviation_kg=0.0,
            calorie_logging_error_standard_deviation_kcal=0.0,
            steps_observation_noise_standard_deviation=0.0,
            missing_weight_probability=0.0,
            missing_nutrition_probability=0.0,
            missing_activity_probability=0.0,
        )
    )
    # Only public observations enter the production trend and adaptive-estimation path.
    observations = [
        day.observation for day in history.days if isinstance(day.observation, DailyObservation)
    ]
    result = estimate_adaptive_tdee(analyze_observation_trends(observations))
    known_expenditure_kcal_per_day = 2000.0 + 1000.0 * 0.04
    assert result.adaptive_tdee_kcal_per_day == pytest.approx(
        known_expenditure_kcal_per_day, abs=1e-9
    )


@pytest.mark.parametrize("value", [None, 0, -1, True, "7700", -math.inf, math.inf, math.nan])
def test_rejects_invalid_energy_equivalent(value: object) -> None:
    with pytest.raises(AdaptiveTdeeError):
        AdaptiveTdeeConfig(value, 14, 4)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [None, 0, -1, True, 3.0, "3"])
def test_rejects_invalid_aggregation_window_days(value: object) -> None:
    with pytest.raises(AdaptiveTdeeError):
        AdaptiveTdeeConfig(7700, value, 1)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [None, 0, -1, True, 3.0, "3"])
def test_rejects_invalid_minimum_estimate_points(value: object) -> None:
    with pytest.raises(AdaptiveTdeeError):
        AdaptiveTdeeConfig(7700, 3, value)  # type: ignore[arg-type]


def test_rejects_minimum_estimate_points_greater_than_window() -> None:
    with pytest.raises(AdaptiveTdeeError):
        AdaptiveTdeeConfig(7700, 3, 4)


def test_rejects_invalid_trend_result_and_config() -> None:
    with pytest.raises(AdaptiveTdeeError):
        estimate_adaptive_tdee("invalid")  # type: ignore[arg-type]
    with pytest.raises(AdaptiveTdeeError):
        estimate_adaptive_tdee(trend_result([]), "invalid")  # type: ignore[arg-type]
