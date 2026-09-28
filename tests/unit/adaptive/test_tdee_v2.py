"""Robust V2 adaptive-TDEE behavior."""

from datetime import date, timedelta

import pytest

from fitadapt.adaptive.tdee import AdaptiveTdeeConfig, TdeeStability, estimate_adaptive_tdee
from fitadapt.analysis.trends import analyze_observation_trends
from fitadapt.domain.observation import DailyObservation


def _result(days=28, noise=0.0, intake=2400.0, missing_weight=()):
    observations = tuple(
        DailyObservation(
            date(2026, 1, 1) + timedelta(days=index),
            80.0 - 0.02 * index + (noise if index == 10 else 0.0),
            intake,
        )
        for index in range(days)
        if index not in missing_weight
    )
    return estimate_adaptive_tdee(
        analyze_observation_trends(observations),
        AdaptiveTdeeConfig(estimator_window_days=28),
    )


def test_v2_aligns_intake_and_weight_evidence_and_reports_stability() -> None:
    result = _result()

    assert result.estimator_method == "theil_sen_v1"
    assert result.weight_contributor_count == 28
    assert result.intake_contributor_count == 28
    assert result.evidence_calendar_span_days == 28
    assert result.aligned_mean_intake_kcal_per_day == 2400
    assert result.observed_weight_slope_kg_per_week == pytest.approx(-0.14)
    assert result.stability is TdeeStability.STABLE


def test_theil_sen_resists_one_outlier_weight() -> None:
    clean = _result()
    noisy = _result(noise=8.0)

    assert noisy.adaptive_tdee_kcal_per_day == pytest.approx(
        clean.adaptive_tdee_kcal_per_day, abs=100
    )


def test_missing_weight_evidence_is_insufficient_without_interpolation() -> None:
    result = _result(missing_weight=tuple(range(0, 20)))

    assert result.weight_contributor_count == 8
    assert result.stability is TdeeStability.INSUFFICIENT
    assert result.adaptive_tdee_kcal_per_day is None
    assert "insufficient_calendar_span" in result.reason_codes


def test_future_observations_do_not_change_prior_v2_result() -> None:
    observations = tuple(
        DailyObservation(date(2026, 1, 1) + timedelta(days=index), 80 - 0.02 * index, 2400)
        for index in range(28)
    )
    prefix = estimate_adaptive_tdee(
        analyze_observation_trends(observations), AdaptiveTdeeConfig(estimator_window_days=28)
    )
    extended = observations + (DailyObservation(date(2026, 2, 1), 100, 1000),)
    future = estimate_adaptive_tdee(
        analyze_observation_trends(extended), AdaptiveTdeeConfig(estimator_window_days=28)
    )

    assert prefix.daily_estimates[0] == future.daily_estimates[0]
