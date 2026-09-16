"""Tests for calendar-aware, leakage-free trend analysis."""

from dataclasses import FrozenInstanceError
from datetime import date, timedelta

import pytest

from fitadapt.analysis.trends import (
    TrendAnalysisConfig,
    TrendAnalysisError,
    analyze_observation_trends,
)
from fitadapt.domain.observation import DailyObservation

START = date(2026, 1, 1)


def observation(
    day: int, weight: float | None = None, intake: float | None = None, steps: int | None = None
) -> DailyObservation:
    return DailyObservation(START + timedelta(days=day), weight, intake, None, None, None, steps)


def test_empty_input_returns_explicit_empty_result() -> None:
    result = analyze_observation_trends([])
    assert result.points == ()
    assert result.data_quality.total_calendar_days == 0
    assert result.data_quality.first_date is None


def test_single_observation_is_returned_without_premature_rolling_values() -> None:
    result = analyze_observation_trends([observation(0, 70, 2000, 0)])
    point = result.points[0]
    assert point.observation_present is True
    assert point.body_weight_kg == 70.0
    assert point.trailing_body_weight_mean_kg is None
    assert point.window_weight_change_kg is None


def test_record_with_only_unanalyzed_measurement_is_present_but_analyzed_values_missing() -> None:
    record = DailyObservation(START, sleep_hours=8)
    point = analyze_observation_trends([record]).points[0]
    assert point.observation_present is True
    assert point.body_weight_kg is None
    assert point.energy_intake_kcal is None
    assert point.steps is None


def test_missing_values_remain_none_while_observed_zero_remains_zero() -> None:
    result = analyze_observation_trends([observation(0, None, 0, 0)])
    point = result.points[0]
    assert point.body_weight_kg is None
    assert point.energy_intake_kcal == 0.0
    assert point.steps == 0


def test_sorts_and_inserts_missing_calendar_dates() -> None:
    result = analyze_observation_trends([observation(2, 72), observation(0, 70)])
    assert [point.observed_on for point in result.points] == [
        START,
        START + timedelta(days=1),
        START + timedelta(days=2),
    ]
    assert result.points[1].observation_present is False
    assert result.points[1].body_weight_kg is None


def test_rejects_duplicates_and_non_observations() -> None:
    with pytest.raises(TrendAnalysisError, match="Duplicate"):
        analyze_observation_trends([observation(0, 70), observation(0, 71)])
    with pytest.raises(TrendAnalysisError, match="DailyObservation"):
        analyze_observation_trends(["not an observation"])


def test_seven_complete_days_have_exact_trailing_means() -> None:
    records = [observation(day, 70 + day, 2000 + 10 * day, 1000 * day) for day in range(7)]
    result = analyze_observation_trends(records)
    point = result.points[-1]
    assert point.trailing_body_weight_mean_kg == pytest.approx(73.0)
    assert point.trailing_energy_intake_mean_kcal == pytest.approx(2030.0)
    assert point.trailing_steps_mean == pytest.approx(3000.0)
    assert point.body_weight_contributor_count == 7


def test_threshold_calendar_window_and_future_leakage() -> None:
    config = TrendAnalysisConfig(window_size_days=7, minimum_observations=4)
    records = [observation(day, 70 + day) for day in (0, 2, 4, 6)]
    before = analyze_observation_trends(records, config)
    after = analyze_observation_trends(records + [observation(7, 99)], config)
    assert before.points[5].trailing_body_weight_mean_kg is None
    assert before.points[6].trailing_body_weight_mean_kg == pytest.approx(73.0)
    assert after.points[6] == before.points[6]


def test_sparse_records_use_calendar_days_not_last_submitted_rows() -> None:
    config = TrendAnalysisConfig(window_size_days=7, minimum_observations=2)
    result = analyze_observation_trends([observation(0, 70), observation(7, 80)], config)
    assert result.points[-1].body_weight_contributor_count == 1
    assert result.points[-1].trailing_body_weight_mean_kg is None


def test_weight_change_uses_non_overlapping_windows() -> None:
    records = [observation(day, 70.0 if day < 7 else 71.0) for day in range(14)]
    result = analyze_observation_trends(records)
    assert result.points[13].window_weight_change_kg == pytest.approx(1.0)
    assert result.points[6].window_weight_change_kg is None


def test_quality_uses_total_calendar_days_as_denominator() -> None:
    result = analyze_observation_trends(
        [observation(0, 70, 2000, 5000), observation(2, None, 2100, None)]
    )
    quality = result.data_quality
    assert (
        quality.total_calendar_days,
        quality.submitted_observation_records,
        quality.missing_calendar_days,
    ) == (3, 2, 1)
    assert quality.present_body_weight_values == 1
    assert quality.body_weight_completeness_ratio == pytest.approx(1 / 3)
    assert quality.energy_intake_completeness_ratio == pytest.approx(2 / 3)


def test_contributor_counts_quality_counts_and_python_public_types() -> None:
    result = analyze_observation_trends(
        [observation(0, 70, 2000, 1000), observation(1, None, None, 0), observation(2, 72)]
    )
    point = result.points[-1]
    quality = result.data_quality
    assert (
        point.body_weight_contributor_count,
        point.energy_intake_contributor_count,
        point.steps_contributor_count,
    ) == (2, 1, 2)
    assert (quality.present_body_weight_values, quality.missing_body_weight_values) == (2, 1)
    assert (quality.present_energy_intake_values, quality.missing_energy_intake_values) == (1, 2)
    assert (quality.present_step_values, quality.missing_step_values) == (2, 1)
    assert quality.body_weight_completeness_ratio == pytest.approx(2 / 3)
    assert quality.energy_intake_completeness_ratio == pytest.approx(1 / 3)
    assert quality.step_completeness_ratio == pytest.approx(2 / 3)
    assert type(point.observed_on) is date
    assert type(point.body_weight_kg) is float
    assert type(result.points[1].steps) is int


def test_custom_window_size_produces_window_weight_change() -> None:
    config = TrendAnalysisConfig(window_size_days=3, minimum_observations=3)
    records = [observation(day, 70.0 if day < 3 else 71.0) for day in range(6)]
    result = analyze_observation_trends(records, config)
    assert result.points[-1].window_weight_change_kg == pytest.approx(1.0)


def test_input_list_is_not_mutated_and_analysis_is_deterministic() -> None:
    records = [observation(1, 71), observation(0, 70)]
    snapshot = list(records)
    first = analyze_observation_trends(records)
    assert records == snapshot
    assert analyze_observation_trends(records) == first


def test_all_public_models_and_points_collection_are_immutable() -> None:
    config = TrendAnalysisConfig()
    result = analyze_observation_trends([observation(0, 70)], config)
    with pytest.raises(FrozenInstanceError):
        config.window_size_days = 3  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.data_quality.total_calendar_days = 1  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.points[0].steps = 1  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result.points.append(result.points[0])  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "window_size_days, minimum_observations",
    [(0, 1), (-1, 1), (7, 0), (7, -1), (7, 8), (True, 1), (7.0, 1), ("7", 1), (None, 1)],
)
def test_rejects_invalid_configuration_values(
    window_size_days: object, minimum_observations: object
) -> None:
    with pytest.raises(TrendAnalysisError):
        TrendAnalysisConfig(window_size_days, minimum_observations)  # type: ignore[arg-type]


def test_rejects_unsupported_config_type() -> None:
    with pytest.raises(TrendAnalysisError, match="config"):
        analyze_observation_trends([], config="invalid")  # type: ignore[arg-type]


def test_result_immutable_and_config_validation() -> None:
    result = analyze_observation_trends([observation(0, 70)])
    with pytest.raises(FrozenInstanceError):
        result.points = ()  # type: ignore[misc]
    for config in (TrendAnalysisConfig(7, 1),):
        assert config.window_size_days == 7
    with pytest.raises(TrendAnalysisError):
        TrendAnalysisConfig(True, 1)
    with pytest.raises(TrendAnalysisError):
        TrendAnalysisConfig(7, 8)
