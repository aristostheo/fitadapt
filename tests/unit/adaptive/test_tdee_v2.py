"""Robust V2 adaptive-TDEE behavior."""

from datetime import date, timedelta
from random import Random

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
    assert result.median_absolute_deviation_kcal_per_day is not None
    assert result.weight_residual_mad_kg == pytest.approx(0.0, abs=1e-9)


def test_v2_requires_weight_evidence_in_both_halves_of_the_window() -> None:
    observations = tuple(
        DailyObservation(
            date(2026, 1, 1) + timedelta(days=index),
            80.0 - 0.02 * index if index < 14 or index == 27 else None,
            2400.0,
        )
        for index in range(28)
    )

    result = estimate_adaptive_tdee(analyze_observation_trends(observations))

    assert result.stability is TdeeStability.INSUFFICIENT
    assert "insufficient_weight_window_geometry" in result.reason_codes


def _energy_balanced_history(days, intake_by_day, *, water_shift=None):
    weight = 80.0
    observations = []
    for index in range(days):
        intake = intake_by_day(index)
        observed_weight = weight + (0.0 if water_shift is None else water_shift(index))
        observations.append(
            DailyObservation(date(2026, 1, 1) + timedelta(days=index), observed_weight, intake)
        )
        weight += (intake - 2000.0) / 7700.0
    return tuple(observations)


def test_v2_marks_a_recent_intake_regime_change_stabilizing() -> None:
    observations = tuple(
        DailyObservation(
            date(2026, 1, 1) + timedelta(days=index),
            80.0 - 0.01 * index,
            1800.0 if index >= 35 else 2400.0,
        )
        for index in range(42)
    )

    result = estimate_adaptive_tdee(analyze_observation_trends(observations))

    assert result.stability is TdeeStability.STABILIZING
    assert result.reason_codes == ("intake_regime_change", "post_regime_stabilization")
    assert result.intake_regime_change_date == date(2026, 2, 5)
    assert result.stabilizing_until_date == date(2026, 2, 25)


def test_intake_regime_signal_waits_for_full_new_regime_support() -> None:
    for changed_days in range(1, 7):
        observations = tuple(
            DailyObservation(
                date(2026, 1, 1) + timedelta(days=index),
                80.0,
                2500.0 if index < 21 else 2000.0,
            )
            for index in range(21 + changed_days)
        )
        result = estimate_adaptive_tdee(analyze_observation_trends(observations))

        assert result.intake_regime_change_date is None


def test_intake_regime_threshold_is_inclusive_and_single_outlier_does_not_trigger() -> None:
    exact_threshold = tuple(
        DailyObservation(
            date(2026, 1, 1) + timedelta(days=index),
            80.0,
            2500.0 if index < 14 else 2200.0,
        )
        for index in range(28)
    )
    one_outlier = tuple(
        DailyObservation(
            date(2026, 1, 1) + timedelta(days=index),
            80.0,
            2500.0 if index == 20 else 2200.0,
        )
        for index in range(28)
    )

    detected = estimate_adaptive_tdee(analyze_observation_trends(exact_threshold))
    quiet = estimate_adaptive_tdee(analyze_observation_trends(one_outlier))

    assert detected.stability is TdeeStability.STABILIZING
    assert detected.intake_regime_change_date is not None
    assert quiet.intake_regime_change_date is None
    assert quiet.stability is not TdeeStability.STABILIZING


@pytest.mark.parametrize("shift", [-500.0, 500.0])
def test_sustained_intake_drop_or_increase_enters_stabilizing_state(shift: float) -> None:
    observations = _energy_balanced_history(49, lambda day: 2500.0 if day < 28 else 2500.0 + shift)

    result = estimate_adaptive_tdee(analyze_observation_trends(observations))

    assert result.stability is TdeeStability.STABILIZING
    assert "intake_regime_change" in result.reason_codes


def test_stabilizing_state_ends_after_configured_period_when_slopes_realign() -> None:
    observations = _energy_balanced_history(50, lambda day: 2500.0 if day < 28 else 2000.0)

    result = estimate_adaptive_tdee(analyze_observation_trends(observations))

    assert result.intake_regime_change_date == date(2026, 1, 29)
    assert result.stability is TdeeStability.STABLE


def test_abrupt_weight_displacement_and_partial_rebound_are_stabilizing() -> None:
    observations = _energy_balanced_history(
        56,
        lambda _: 2000.0,
        water_shift=lambda day: (
            0.0
            if day < 28
            else -1.5 * min((day - 27) / 7, 1.0) + 0.75 * min(max(day - 34, 0) / 14, 1.0)
        ),
    )

    result = estimate_adaptive_tdee(analyze_observation_trends(observations))

    assert result.stability is TdeeStability.STABILIZING
    assert "weight_subwindow_slope_disagreement" in result.reason_codes


def test_stationary_autocorrelated_water_is_stabilizing_not_recommendation_ready() -> None:
    observations = []
    weight = 80.0
    water = 0.0
    rng = Random(20017)
    for index in range(42):
        water = 0.85 * water + rng.gauss(0.0, 0.45)
        observations.append(
            DailyObservation(
                date(2026, 1, 1) + timedelta(days=index),
                weight + water + rng.gauss(0.0, 0.4),
                2000.0,
            )
        )

    result = estimate_adaptive_tdee(analyze_observation_trends(tuple(observations)))

    assert result.stability is TdeeStability.STABILIZING
    assert "weight_subwindow_slope_disagreement" in result.reason_codes


def test_repeated_estimation_is_deterministic_and_does_not_mutate_observations() -> None:
    observations = _energy_balanced_history(42, lambda day: 2500.0 if day < 21 else 2000.0)
    snapshot = tuple(observations)

    first = estimate_adaptive_tdee(analyze_observation_trends(observations))
    second = estimate_adaptive_tdee(analyze_observation_trends(observations))

    assert first == second
    assert observations == snapshot


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
