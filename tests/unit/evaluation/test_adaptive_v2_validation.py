"""Regression checks for CP34A's in-model synthetic candidate harness."""

from dataclasses import replace
from datetime import date, timedelta

import pytest

from fitadapt.adaptive.tdee import AdaptiveTdeeConfig, TdeeStability
from fitadapt.domain.observation import DailyObservation
from fitadapt.evaluation import adaptive_v2_validation as validation


def test_cumulative_candidate_recovers_tdee_from_day_aligned_intervals() -> None:
    energy_density = 7700.0
    observations = tuple(
        DailyObservation(
            date(2026, 1, 1) + timedelta(days=index),
            80.0 - index * 300.0 / energy_density,
            1700.0,
        )
        for index in range(35)
    )

    estimate = validation._cumulative_estimate(
        observations,
        validation.AdaptiveTdeeConfig(estimator_window_days=28),
    )

    assert estimate == pytest.approx(2000.0)


def test_cumulative_candidate_rejects_missing_intake_in_an_interval() -> None:
    observations = tuple(
        DailyObservation(
            date(2026, 1, 1) + timedelta(days=index),
            80.0 - index * 300.0 / 7700.0,
            None if index == 18 else 1700.0,
        )
        for index in range(35)
    )

    estimate = validation._cumulative_estimate(
        observations,
        validation.AdaptiveTdeeConfig(estimator_window_days=28),
    )

    assert estimate is None


@pytest.mark.parametrize(
    ("seeds", "seed_set"),
    [
        ((), "development"),
        ((20000, 20000), "development"),
        ((True,), "development"),
        ((20000,), "unknown"),
    ],
)
def test_seed_validation_rejects_invalid_sets(seeds, seed_set) -> None:
    with pytest.raises(ValueError):
        validation._validate_seed_set(seeds, seed_set)


@pytest.mark.parametrize("multipliers", [(), (0.0,), (-1.0,), (float("nan"),)])
def test_candidate_runner_rejects_invalid_uncertainty_multipliers(multipliers) -> None:
    with pytest.raises(ValueError, match="uncertainty_multipliers"):
        validation.run_cp34a_candidate_set(
            (20000,), seed_set="development", uncertainty_multipliers=multipliers
        )


def test_v1_emulation_requires_enough_recent_eligible_points() -> None:
    observations = tuple(
        DailyObservation(date(2026, 1, 1) + timedelta(days=index), 80 - index * 0.02, 2400)
        for index in range(10)
    )
    trends = validation._analyze_cached(observations)

    assert validation._v1_estimate(trends, validation.AdaptiveTdeeConfig()) is None
    assert (
        validation._v1_estimate(validation._analyze_cached(()), validation.AdaptiveTdeeConfig())
        is None
    )


def test_cumulative_candidate_rejects_short_or_stale_weight_geometry() -> None:
    observations = tuple(
        DailyObservation(date(2026, 1, 1) + timedelta(days=index), 80 - index * 0.02, 2400)
        for index in range(28)
    )
    short_span = tuple(
        DailyObservation(item.observed_on, 80.0 if index < 10 else None, item.energy_intake_kcal)
        for index, item in enumerate(observations)
    )
    stale = observations[:-5] + tuple(
        DailyObservation(item.observed_on, None, item.energy_intake_kcal)
        for item in observations[-5:]
    )
    config = validation.AdaptiveTdeeConfig(estimator_window_days=28)

    assert validation._cumulative_estimate(short_span, config) is None
    assert validation._cumulative_estimate(stale, config) is None


def test_empty_error_summary_and_v1_candidate_have_explicit_na_stability(monkeypatch):
    assert validation._summary(()) == validation.ErrorSummary(0, None, None, None, None, None, None)
    monkeypatch.setattr(validation, "_make_observations", lambda seed, scenario, **kwargs: ())
    monkeypatch.setattr(
        validation, "_estimate", lambda candidate, observations, **kwargs: (None, None, None, ())
    )

    summary = validation._candidate_summary((20000,), "scale_noise", "v1", 2.5)

    assert summary.estimate_coverage == 0
    assert summary.stable_fraction is None
    assert summary.hold_rate == 1


def test_seed_set_validation_rejects_accidental_holdout_overlap() -> None:
    with pytest.raises(ValueError, match="development range"):
        validation._validate_seed_set((20000, 30000), "development")
    with pytest.raises(ValueError, match="held_out range"):
        validation._validate_seed_set((20299,), "held_out")


def test_stationary_false_changes_require_stable_v2_and_hold_if_insufficient(monkeypatch):
    estimates = iter(
        (
            (2200.0, TdeeStability.STABLE, 0.0, ()),
            (1800.0, TdeeStability.UNSTABLE, 0.0, ()),
            (None, TdeeStability.INSUFFICIENT, None, ()),
        )
    )
    monkeypatch.setattr(validation, "_make_observations", lambda seed, scenario, **kwargs: ())
    monkeypatch.setattr(
        validation,
        "_estimate",
        lambda candidate, observations, **kwargs: next(estimates),
    )

    summary = validation._candidate_summary((0, 1, 2), "scale_noise", "theil_sen_28", 2.0)

    assert summary.hold_rate == pytest.approx(2 / 3)
    assert summary.false_increase_rate == pytest.approx(1 / 3)
    assert summary.false_decrease_rate == 0
    assert summary.false_change_rate == pytest.approx(1 / 3)
    assert summary.stable_fraction == pytest.approx(1 / 3)
    assert summary.unstable_fraction == pytest.approx(1 / 3)
    assert summary.insufficient_fraction == pytest.approx(1 / 3)


def test_v1_stability_is_reported_as_not_applicable(monkeypatch):
    monkeypatch.setattr(validation, "_make_observations", lambda seed, scenario, **kwargs: ())
    monkeypatch.setattr(
        validation,
        "_estimate",
        lambda candidate, observations, **kwargs: (2000.0, None, None, ()),
    )

    summary = validation._candidate_summary((0,), "scale_noise", "v1", 2.0)

    assert summary.stable_fraction is None
    assert summary.unstable_fraction is None
    assert summary.stable_error is None
    assert summary.unstable_error is None


def test_seeded_scenarios_are_reproducible_and_intake_noise_changes_true_weight():
    first = validation._make_observations(17, "scale_intake_noise")
    repeated = validation._make_observations(17, "scale_intake_noise")
    deterministic_intake = validation._make_observations(17, "scale_noise")

    assert first == repeated
    assert len({item.energy_intake_kcal for item in deterministic_intake}) == 1
    assert len({item.body_weight_kg for item in first}) > 1


def test_transition_runner_covers_drop_water_drop_and_increase_for_both_candidates():
    result = validation.run_cp34a_candidate_set(
        (20000,), seed_set="development", uncertainty_multipliers=(2.5,)
    )

    scenarios = {item.scenario for item in result.transition_candidates}
    candidates = {item.candidate for item in result.transition_candidates}
    assert scenarios == {
        "abrupt_intake_drop",
        "abrupt_intake_water_drop",
        "abrupt_intake_water_increase",
    }
    assert candidates == {"theil_sen_28", "cumulative"}
    assert all(item.users == 1 for item in result.transition_candidates)


@pytest.mark.parametrize("direction", [300, -300])
def test_cp34a2_water_guard_preserves_plus_minus_300_detection(direction: int) -> None:
    config = replace(
        AdaptiveTdeeConfig(),
        intake_regime_stabilization_days=28,
        subwindow_slope_disagreement_kcal_per_day=585.0,
    )

    summary = validation._power_summaries(
        range(20000, 20040), direction, "theil_sen_28", (2.5,), config
    )[0]

    assert summary.detection_by_day_28 >= 0.7
    assert summary.opposite_direction_rate == 0
    assert summary.stable_coverage >= 0.95
    assert summary.median_days_to_detection <= 28


def test_cp34a3_seed_ranges_are_disjoint_and_validated() -> None:
    validation._validate_cp34a3_seed_set((40000,), "development")
    validation._validate_cp34a3_seed_set((50000,), "held_out")
    with pytest.raises(ValueError, match="development range"):
        validation._validate_cp34a3_seed_set((50000,), "development")
    with pytest.raises(ValueError, match="held_out range"):
        validation._validate_cp34a3_seed_set((40299,), "held_out")


@pytest.mark.parametrize(
    ("seeds", "seed_set"),
    [
        ((), "development"),
        ((40000, 40000), "development"),
        ((True,), "development"),
        ((40000,), "unknown"),
    ],
)
def test_cp34a3_seed_validation_rejects_invalid_cohorts(seeds, seed_set) -> None:
    with pytest.raises(ValueError):
        validation._validate_cp34a3_seed_set(seeds, seed_set)


def test_cp34a3_study_reports_three_horizons_and_matched_input_limit():
    result = validation.run_cp34a3_study((40000,), seed_set="development")

    assert {item.window_days for item in result.horizons} == {28, 35, 42}
    assert result.identifiability.maximum_observation_difference < 1e-8
    assert result.identifiability.median_estimate_difference < 1e-6
    assert result.identifiability.true_tdee_difference == 270.0
    assert {item.scenario for item in result.asymmetric} == {
        "scale_noise",
        "scale_intake_noise",
        "autocorrelated_water",
        "persistent_water_drift",
    }


def test_cp34a3_block_sensitivity_preserves_endpoint_and_is_reproducible():
    config = replace(AdaptiveTdeeConfig(), estimator_window_days=28)
    observations = validation._make_observations(40013, "scale_noise", days=42)
    trends = validation._analyze_cached(observations)

    first = validation._sensitivity_values(observations, trends, 28, config)
    repeated = validation._sensitivity_values(observations, trends, 28, config)

    assert first == repeated
    (
        block_range,
        first_week_delta,
        last_week_delta,
        block_values,
        horizon_range,
        unavailable,
    ) = first
    assert block_range is not None and block_range >= 0
    assert first_week_delta is not None and first_week_delta >= 0
    assert last_week_delta is not None and last_week_delta >= 0
    assert len(block_values) >= 3
    assert horizon_range is not None and horizon_range >= 0
    assert not unavailable


def test_cp34a3_observation_factory_supports_stationary_noise_scenario():
    observations, truth = validation._cp34a3_observations(40021, "scale_noise")

    assert len(observations) == 70
    assert truth == 2000.0
    assert observations[0].energy_intake_kcal == pytest.approx(2000.0)
