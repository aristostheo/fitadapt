"""In-model synthetic CP34A comparisons for adaptive-TDEE candidates."""

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from functools import lru_cache
from statistics import median, pstdev

from fitadapt.adaptive.tdee import (
    AdaptiveTdeeConfig,
    TdeeStability,
    estimate_adaptive_tdee,
)
from fitadapt.analysis.trends import (
    TrendAnalysisConfig,
    TrendAnalysisResult,
    analyze_observation_trends,
)
from fitadapt.domain.observation import DailyObservation

CP34A_EVALUATION_POLICY_VERSION = "adaptive_tdee_cp34a_eval_v1"
CP34A2_SEED_SPLIT = "development:20000..20299; held_out:30000..30299"


@dataclass(frozen=True, slots=True)
class ErrorSummary:
    count: int
    mean_error: float | None
    mae: float | None
    median_absolute_error: float | None
    p90_absolute_error: float | None
    p95_absolute_error: float | None
    standard_deviation: float | None


@dataclass(frozen=True, slots=True)
class CandidateSummary:
    candidate: str
    scenario: str
    uncertainty_multiplier: float
    users: int
    estimate_coverage: float
    stable_fraction: float | None
    stabilizing_fraction: float | None
    unstable_fraction: float | None
    insufficient_fraction: float | None
    overall_error: ErrorSummary
    stable_error: ErrorSummary | None
    stabilizing_error: ErrorSummary | None
    unstable_error: ErrorSummary | None
    hold_rate: float
    false_increase_rate: float
    false_decrease_rate: float
    false_change_rate: float


@dataclass(frozen=True, slots=True)
class PowerSummary:
    candidate: str
    scenario: str
    uncertainty_multiplier: float
    users: int
    stable_coverage: float
    correct_direction_rate: float
    opposite_direction_rate: float
    median_days_to_detection: float | None
    detection_by_day_14: float
    detection_by_day_21: float
    detection_by_day_28: float
    detection_by_day_35: float


@dataclass(frozen=True, slots=True)
class TransitionSummary:
    candidate: str
    scenario: str
    users: int
    max_transient_error: ErrorSummary
    error_day_7: ErrorSummary
    error_day_14: ErrorSummary
    error_day_21: ErrorSummary
    error_day_28: ErrorSummary
    recovery_within_100_fraction: float
    recovery_within_150_fraction: float
    median_recovery_day_within_100: float | None
    median_recovery_day_within_150: float | None
    stable_at_day_28_fraction: float
    median_days_until_stable_recovery: float | None
    intake_regime_signal_day_7_fraction: float
    intake_regime_signal_day_14_fraction: float
    intake_regime_signal_day_21_fraction: float
    intake_regime_signal_day_28_fraction: float
    median_intake_regime_signal_day: float | None
    stable_observation_fraction: float
    stabilizing_observation_fraction: float
    unstable_observation_fraction: float
    persistent_false_change_fraction: float
    false_increase_fraction: float
    false_decrease_fraction: float


@dataclass(frozen=True, slots=True)
class CandidateSetSummary:
    seed_set: str
    stationary: tuple[CandidateSummary, ...]
    power: tuple[PowerSummary, ...]
    abrupt_intake: tuple[TransitionSummary, ...]
    transition_candidates: tuple[TransitionSummary, ...]
    model_mismatch: tuple[CandidateSummary, ...]


@dataclass(frozen=True, slots=True)
class HorizonSummary:
    scenario: str
    window_days: int
    users: int
    estimate_coverage: float
    stable_fraction: float
    stabilizing_fraction: float
    unstable_fraction: float
    false_increase_rate: float
    false_decrease_rate: float
    false_change_rate: float
    mae: float | None
    stable_mae: float | None
    nonstable_mae: float | None
    detection_by_day_28: float | None
    median_detection_day: float | None
    opposite_direction_rate: float | None
    median_transition_stable_recovery_day: float | None


@dataclass(frozen=True, slots=True)
class SensitivitySummary:
    scenario: str
    window_days: int
    users: int
    leave_first_week_range_median: float | None
    leave_last_week_range_median: float | None
    leave_one_week_range_p90: float | None
    max_block_range_median: float | None
    block_unavailable_fraction: float
    block_warning_fraction: float
    multi_horizon_disagreement_median: float | None
    multi_horizon_warning_fraction: float
    stable_mae: float | None
    nonstable_mae: float | None


@dataclass(frozen=True, slots=True)
class AsymmetricSummary:
    scenario: str
    users: int
    symmetric_false_increase: float
    symmetric_false_decrease: float
    guarded_false_increase: float
    guarded_false_decrease: float
    symmetric_correct_decrease_power: float
    guarded_correct_decrease_power: float
    median_guarded_decrease_latency: float | None
    opposite_direction_rate: float


@dataclass(frozen=True, slots=True)
class IdentifiabilitySummary:
    users: int
    maximum_observation_difference: float
    median_estimate_difference: float
    stable_classification_agreement: float
    true_tdee_difference: float


@dataclass(frozen=True, slots=True)
class CP34A3Summary:
    seed_set: str
    horizons: tuple[HorizonSummary, ...]
    sensitivity: tuple[SensitivitySummary, ...]
    asymmetric: tuple[AsymmetricSummary, ...]
    identifiability: IdentifiabilitySummary


def run_cp34a3_study(
    seeds: Sequence[int], *, seed_set: str, config: AdaptiveTdeeConfig | None = None
) -> CP34A3Summary:
    """Evaluate evidence horizons and estimator sensitivity without changing product policy."""
    _validate_cp34a3_seed_set(seeds, seed_set)
    effective = config or AdaptiveTdeeConfig()
    scenarios = (
        "scale_noise",
        "scale_intake_noise",
        "missing_data",
        "autocorrelated_water",
        "persistent_water_drift",
        "energy_deficit_matched",
        "power_plus_300",
        "power_minus_300",
        "abrupt_intake_drop",
        "abrupt_intake_water_drop",
        "abrupt_intake_water_increase",
    )
    horizons: list[HorizonSummary] = []
    sensitivity: list[SensitivitySummary] = []
    for scenario in scenarios:
        for window_days in (28, 35, 42):
            result = _cp34a3_horizon_summary(seeds, scenario, window_days, effective)
            horizons.append(result)
            if scenario in (
                "scale_noise",
                "autocorrelated_water",
                "persistent_water_drift",
                "energy_deficit_matched",
                "missing_data",
            ):
                sensitivity.append(
                    _cp34a3_sensitivity_summary(seeds, scenario, window_days, effective)
                )
    transition_recovery = {
        (scenario, window): _transition_summary(
            seeds,
            scenario,
            f"theil_sen_{window}",
            replace(
                effective,
                estimator_window_days=window,
                minimum_calendar_span_days=min(effective.minimum_calendar_span_days, window),
            ),
        ).median_days_until_stable_recovery
        for scenario in (
            "abrupt_intake_drop",
            "abrupt_intake_water_drop",
            "abrupt_intake_water_increase",
        )
        for window in (28, 35, 42)
    }
    horizons = [
        replace(
            row,
            median_transition_stable_recovery_day=transition_recovery.get(
                (row.scenario, row.window_days)
            ),
        )
        for row in horizons
    ]
    asymmetric = tuple(
        _asymmetric_action_summary(seeds, scenario, effective)
        for scenario in (
            "scale_noise",
            "scale_intake_noise",
            "autocorrelated_water",
            "persistent_water_drift",
        )
    )
    identifiability = _matched_input_identifiability(seeds, effective)
    return CP34A3Summary(seed_set, tuple(horizons), tuple(sensitivity), asymmetric, identifiability)


@lru_cache(maxsize=4096)
def _cp34a3_observations(seed: int, scenario: str) -> tuple[tuple[DailyObservation, ...], float]:
    if scenario.startswith("abrupt_intake"):
        is_up = scenario.endswith("increase")
        has_water = "water" in scenario
        return (
            _make_observations(
                seed,
                "autocorrelated_water" if has_water else "scale_intake_noise",
                days=98,
                abrupt_day=42,
                water_shift=has_water,
                intake_shift_kcal=500.0 if is_up else -500.0,
                water_shift_kg=1.5 if is_up else -1.5,
            ),
            2000.0,
        )
    if scenario == "persistent_water_drift":
        drift = -270.0 / 7700.0
        return (
            _make_observations(seed, "scale_noise", days=70, water_drift_kg_per_day=drift),
            2000.0,
        )
    if scenario == "energy_deficit_matched":
        return (
            _make_observations(
                seed,
                "scale_noise",
                days=70,
                true_tdee=2270.0,
                intake_offset=-270.0,
            ),
            2270.0,
        )
    if scenario == "power_plus_300":
        return _make_observations(seed, "scale_intake_noise", days=70, true_tdee=2300.0), 2300.0
    if scenario == "power_minus_300":
        return _make_observations(seed, "scale_intake_noise", days=70, true_tdee=1700.0), 1700.0
    return _make_observations(seed, scenario, days=70), 2000.0


def _cp34a3_horizon_summary(
    seeds: Sequence[int], scenario: str, window_days: int, config: AdaptiveTdeeConfig
) -> HorizonSummary:
    horizon_config = replace(
        config,
        estimator_window_days=window_days,
        minimum_calendar_span_days=min(config.minimum_calendar_span_days, window_days),
    )
    errors: list[float] = []
    stable_errors: list[float] = []
    nonstable_errors: list[float] = []
    stable = stabilizing = unstable = false_up = false_down = 0
    detections: list[int] = []
    opposite = 0
    is_power = scenario.startswith("power_")
    for seed in seeds:
        observations, truth = _cp34a3_observations(seed, scenario)
        trends = _analyze_cached(observations)
        estimate, base_state, uncertainty, _ = _estimate(
            f"theil_sen_{window_days}",
            observations,
            trend_result=trends,
            base_config=horizon_config,
        )
        if estimate is None:
            continue
        block_range, _, _, _, horizon_range, block_unavailable = _sensitivity_values(
            observations, trends, window_days, horizon_config
        )
        state = base_state
        if state is TdeeStability.STABLE and _sensitivity_warns(
            block_range, horizon_range, block_unavailable, horizon_config
        ):
            state = TdeeStability.STABILIZING
        error = estimate - truth
        errors.append(error)
        stable += state is TdeeStability.STABLE
        stabilizing += state is TdeeStability.STABILIZING
        unstable += state is TdeeStability.UNSTABLE
        (stable_errors if state is TdeeStability.STABLE else nonstable_errors).append(error)
        cutoff = max(75.0, 2.5 * (uncertainty or 0.0))
        if state is TdeeStability.STABLE and error > cutoff:
            false_up += 1
        elif state is TdeeStability.STABLE and error < -cutoff:
            false_down += 1
        if is_power:
            expected_direction = 1 if scenario == "power_plus_300" else -1
            detected = None
            for day in (13, 20, 27, 34, 41, 48, 55, 62, 69):
                as_of = observations[day].observed_on
                point_estimate, point_state, point_uncertainty, _ = _estimate(
                    f"theil_sen_{window_days}",
                    observations,
                    as_of,
                    trends,
                    horizon_config,
                )
                point_trends = replace(
                    trends,
                    points=tuple(point for point in trends.points if point.observed_on <= as_of),
                )
                block_range, _, _, _, horizon_range, block_unavailable = _sensitivity_values(
                    observations, point_trends, window_days, horizon_config
                )
                if point_state is TdeeStability.STABLE and _sensitivity_warns(
                    block_range, horizon_range, block_unavailable, horizon_config
                ):
                    point_state = TdeeStability.STABILIZING
                if point_estimate is None or point_state is not TdeeStability.STABLE:
                    continue
                delta = point_estimate - 2000.0
                threshold = max(75.0, 2.5 * (point_uncertainty or 0.0))
                if abs(delta) > threshold:
                    if (1 if delta > 0 else -1) == expected_direction:
                        detected = day + 1
                        detections.append(detected)
                    else:
                        opposite += 1
                    break
    n = len(seeds)
    transition_recovery = None
    return HorizonSummary(
        scenario,
        window_days,
        n,
        len(errors) / n,
        stable / n,
        stabilizing / n,
        unstable / n,
        false_up / n,
        false_down / n,
        (false_up + false_down) / n,
        None if not errors else sum(abs(value) for value in errors) / len(errors),
        None
        if not stable_errors
        else sum(abs(value) for value in stable_errors) / len(stable_errors),
        None
        if not nonstable_errors
        else sum(abs(value) for value in nonstable_errors) / len(nonstable_errors),
        None if not is_power else len(detections) / n,
        None if not detections else median(detections),
        None if not is_power else opposite / n,
        transition_recovery,
    )


def _sensitivity_warns(block_range, horizon_range, block_unavailable, config) -> bool:
    return (
        block_unavailable
        or (
            block_range is not None
            and block_range >= config.block_sensitivity_threshold_kcal_per_day
        )
        or (
            horizon_range is not None
            and horizon_range >= config.multi_horizon_disagreement_threshold_kcal_per_day
        )
    )


@lru_cache(maxsize=32768)
def _sensitivity_values(observations, trends, window_days, config):
    end = trends.points[-1].observed_on
    start = end - timedelta(days=window_days - 1)
    block_estimates: list[float] = []
    block_unavailable = False
    first_week: float | None = None
    last_week: float | None = None
    for offset in range(0, window_days, 7):
        block_start = start + timedelta(days=offset)
        block_end = min(end, block_start + timedelta(days=6))
        masked_points = tuple(
            replace(
                point,
                body_weight_kg=None,
                energy_intake_kcal=None,
            )
            if block_start <= point.observed_on <= block_end
            else point
            for point in trends.points
        )
        masked_trends = replace(trends, points=masked_points)
        sensitivity_config = replace(
            config,
            maximum_days_since_last_weigh_in=max(config.maximum_days_since_last_weigh_in, 7),
        )
        estimate, _, _, _ = _estimate(
            f"theil_sen_{window_days}",
            observations,
            trend_result=masked_trends,
            base_config=sensitivity_config,
        )
        if estimate is None:
            block_unavailable = True
        else:
            block_estimates.append(estimate)
            if offset == 0:
                first_week = estimate
            if block_end == end:
                last_week = estimate
    base, _, _, _ = _estimate(
        f"theil_sen_{window_days}", observations, trend_result=trends, base_config=config
    )
    horizons = {21, 28, 35, 42}
    values: dict[int, float] = {}
    for other in horizons:
        if other == window_days or abs(other - window_days) != 7:
            continue
        other_config = replace(
            config,
            estimator_window_days=other,
            minimum_calendar_span_days=min(config.minimum_calendar_span_days, other),
        )
        value, _, _, _ = _estimate(
            f"theil_sen_{other}", observations, trend_result=trends, base_config=other_config
        )
        if value is not None:
            values[other] = value
    horizon_range = (
        max((base, *values.values())) - min((base, *values.values()))
        if base is not None and values
        else None
    )
    block_range = max(block_estimates) - min(block_estimates) if block_estimates else None
    first_range = None if base is None or first_week is None else abs(base - first_week)
    last_range = None if base is None or last_week is None else abs(base - last_week)
    return (
        block_range,
        first_range,
        last_range,
        tuple(block_estimates),
        horizon_range,
        block_unavailable,
    )


def _cp34a3_sensitivity_summary(seeds, scenario, window_days, config):
    first_ranges: list[float] = []
    last_ranges: list[float] = []
    all_block_ranges: list[float] = []
    max_block_ranges: list[float] = []
    horizon_ranges: list[float] = []
    block_warnings = horizon_warnings = 0
    block_unavailable_count = 0
    stable_errors: list[float] = []
    nonstable_errors: list[float] = []
    for seed in seeds:
        observations, truth = _cp34a3_observations(seed, scenario)
        trends = _analyze_cached(observations)
        estimate, state, _, _ = _estimate(
            f"theil_sen_{window_days}", observations, trend_result=trends, base_config=config
        )
        if estimate is None:
            continue
        (
            block_range,
            first_range,
            last_range,
            _,
            horizon_range,
            block_unavailable,
        ) = _sensitivity_values(observations, trends, window_days, config)
        if first_range is not None:
            first_ranges.append(first_range)
        if last_range is not None:
            last_ranges.append(last_range)
        block_warning = block_unavailable or (
            block_range is not None
            and block_range >= config.block_sensitivity_threshold_kcal_per_day
        )
        if block_range is not None:
            all_block_ranges.append(block_range)
            max_block_ranges.append(block_range)
        if block_unavailable:
            block_unavailable_count += 1
        block_warnings += block_warning
        if horizon_range is not None:
            horizon_ranges.append(horizon_range)
            horizon_warnings += (
                horizon_range >= config.multi_horizon_disagreement_threshold_kcal_per_day
            )
        flagged = state is TdeeStability.STABLE and (
            _sensitivity_warns(block_range, horizon_range, block_unavailable, config)
        )
        final_state = TdeeStability.STABILIZING if flagged else state
        (stable_errors if final_state is TdeeStability.STABLE else nonstable_errors).append(
            estimate - truth
        )
    n = len(seeds)
    return SensitivitySummary(
        scenario,
        window_days,
        n,
        None if not first_ranges else median(first_ranges),
        None if not last_ranges else median(last_ranges),
        _summary(all_block_ranges).p90_absolute_error,
        None if not max_block_ranges else median(max_block_ranges),
        block_unavailable_count / n,
        block_warnings / n,
        None if not horizon_ranges else median(horizon_ranges),
        horizon_warnings / n,
        None
        if not stable_errors
        else sum(abs(value) for value in stable_errors) / len(stable_errors),
        None
        if not nonstable_errors
        else sum(abs(value) for value in nonstable_errors) / len(nonstable_errors),
    )


def _asymmetric_action_summary(seeds, scenario, config):
    false_increase = false_decrease = guarded_increase = guarded_decrease = 0
    decrease_power = guarded_power = opposite = 0
    latency: list[int] = []
    for seed in seeds:
        observations, truth = _cp34a3_observations(seed, scenario)
        trends = _analyze_cached(observations)
        estimate, state, uncertainty, _ = _estimate(
            "theil_sen_28", observations, trend_result=trends, base_config=config
        )
        if estimate is not None and state is TdeeStability.STABLE:
            block_range, _, _, _, horizon_range, unavailable = _sensitivity_values(
                observations, trends, 28, config
            )
            if _sensitivity_warns(block_range, horizon_range, unavailable, config):
                state = TdeeStability.STABILIZING
        if estimate is not None and state is TdeeStability.STABLE:
            delta = estimate - truth
            base = max(75.0, 2.5 * (uncertainty or 0.0))
            guarded = max(150.0, 3.0 * (uncertainty or 0.0))
            false_increase += delta > base
            false_decrease += delta < -base
            guarded_increase += delta > base
            guarded_decrease += delta < -guarded
        power_obs = _make_observations(seed, "scale_intake_noise", days=70, true_tdee=1700.0)
        power_trends = _analyze_cached(power_obs)
        baseline_day = guarded_day = None
        for day in (13, 20, 27, 34, 41, 48, 55, 62, 69):
            value, state, uncertainty, _ = _estimate(
                "theil_sen_28",
                power_obs,
                power_obs[day].observed_on,
                trend_result=power_trends,
                base_config=config,
            )
            point_trends = replace(
                power_trends,
                points=tuple(
                    point
                    for point in power_trends.points
                    if point.observed_on <= power_obs[day].observed_on
                ),
            )
            block_range, _, _, _, horizon_range, unavailable = _sensitivity_values(
                power_obs, point_trends, 28, config
            )
            if state is TdeeStability.STABLE and _sensitivity_warns(
                block_range, horizon_range, unavailable, config
            ):
                state = TdeeStability.STABILIZING
            if value is None or state is not TdeeStability.STABLE:
                continue
            delta = value - 2000.0
            if delta > 0:
                opposite += 1
                break
            if delta < -max(75.0, 2.5 * (uncertainty or 0.0)) and baseline_day is None:
                baseline_day = day + 1
            if delta < -max(150.0, 3.0 * (uncertainty or 0.0)):
                guarded_day = day + 1
                break
        decrease_power += baseline_day is not None
        guarded_power += guarded_day is not None
        if guarded_day is not None:
            latency.append(guarded_day)
    n = len(seeds)
    return AsymmetricSummary(
        scenario,
        n,
        false_increase / n,
        false_decrease / n,
        guarded_increase / n,
        guarded_decrease / n,
        decrease_power / n,
        guarded_power / n,
        None if not latency else median(latency),
        opposite / n,
    )


def _matched_input_identifiability(seeds, config):
    max_differences: list[float] = []
    estimate_differences: list[float] = []
    stable_agreements = 0
    for seed in seeds:
        drift_obs, drift_truth = _cp34a3_observations(seed, "persistent_water_drift")
        deficit_obs, deficit_truth = _cp34a3_observations(seed, "energy_deficit_matched")
        max_differences.append(
            max(
                abs(left.body_weight_kg - right.body_weight_kg)
                for left, right in zip(drift_obs, deficit_obs, strict=True)
            )
        )
        drift, drift_state, _, _ = _estimate("theil_sen_28", drift_obs, base_config=config)
        deficit, deficit_state, _, _ = _estimate("theil_sen_28", deficit_obs, base_config=config)
        if drift is not None and deficit is not None:
            estimate_differences.append(abs(drift - deficit))
        stable_agreements += drift_state is deficit_state
    return IdentifiabilitySummary(
        len(seeds),
        max(max_differences, default=0.0),
        None if not estimate_differences else median(estimate_differences),
        stable_agreements / len(seeds),
        270.0,
    )


def _validate_cp34a3_seed_set(seeds, seed_set):
    bounds = {"development": (40000, 40299), "held_out": (50000, 50299)}
    if seed_set not in bounds:
        raise ValueError("CP34A3 seed_set must be 'development' or 'held_out'.")
    low, high = bounds[seed_set]
    if (
        not seeds
        or len(seeds) != len(set(seeds))
        or any(
            isinstance(seed, bool) or not isinstance(seed, int) or not low <= seed <= high
            for seed in seeds
        )
    ):
        raise ValueError(f"CP34A3 seeds must be unique and in {seed_set} range {low}..{high}.")


def run_cp34a_candidate_set(
    seeds: Sequence[int],
    *,
    seed_set: str,
    uncertainty_multipliers: Sequence[float] = (1.5, 2.0, 2.5),
    config: AdaptiveTdeeConfig | None = None,
) -> CandidateSetSummary:
    """Run identical seeded users through V1, 21/28-day V2, and cumulative candidates."""
    _validate_seed_set(seeds, seed_set)
    if not uncertainty_multipliers or any(
        isinstance(value, bool) or not math.isfinite(value) or value <= 0
        for value in uncertainty_multipliers
    ):
        raise ValueError("uncertainty_multipliers must contain positive values.")
    effective_config = config or AdaptiveTdeeConfig()
    scenarios = ("scale_noise", "scale_intake_noise", "autocorrelated_water", "missing_data")
    stationary = tuple(
        summary
        for scenario in scenarios
        for candidate in ("v1", "theil_sen_21", "theil_sen_28", "cumulative")
        for summary in _candidate_summaries(
            seeds, scenario, candidate, uncertainty_multipliers, effective_config
        )
    )
    power = tuple(
        summary
        for mismatch in (300, -300)
        for candidate in ("theil_sen_21", "theil_sen_28", "cumulative")
        for summary in _power_summaries(
            seeds, mismatch, candidate, uncertainty_multipliers, effective_config
        )
    )
    scenarios = (
        "abrupt_intake_drop",
        "abrupt_intake_water_drop",
        "abrupt_intake_water_increase",
    )
    abrupt = tuple(
        _transition_summary(seeds, scenario, "theil_sen_28", effective_config)
        for scenario in scenarios
    )
    transition_candidates = tuple(
        _transition_summary(seeds, scenario, candidate, effective_config)
        for scenario in scenarios
        for candidate in ("theil_sen_28", "cumulative")
    )
    mismatch = tuple(
        summary
        for density in (6160, 9240)
        for candidate in ("theil_sen_28", "cumulative")
        for summary in _candidate_summaries(
            seeds, density, candidate, uncertainty_multipliers, effective_config
        )
    )
    return CandidateSetSummary(seed_set, stationary, power, abrupt, transition_candidates, mismatch)


def _make_observations(
    seed: int,
    scenario: str,
    *,
    days: int = 42,
    true_tdee: float = 2000.0,
    energy_density: float = 7700.0,
    intake_offset: float = 0.0,
    abrupt_day: int | None = None,
    water_shift: bool = False,
    intake_shift_kcal: float = -500.0,
    water_shift_kg: float = -1.5,
    water_drift_kg_per_day: float = 0.0,
) -> tuple[DailyObservation, ...]:
    rng = random.Random(seed)
    true_weight = 80.0
    water = 0.0
    observations: list[DailyObservation] = []
    for index in range(days):
        if water_shift and abrupt_day is not None and index >= abrupt_day:
            elapsed = index - abrupt_day + 1
            water = (
                water_shift_kg * elapsed / 7.0
                if elapsed <= 7
                else water_shift_kg * max(0.0, 1.0 - (elapsed - 7) / 14.0)
            )
        else:
            water = 0.85 * water + rng.gauss(
                0.0, 0.0 if scenario != "autocorrelated_water" else 0.45
            )
        intake_mean = true_tdee + intake_offset
        if abrupt_day is not None and index >= abrupt_day:
            intake_mean += intake_shift_kcal
        intake_noise = (
            150.0
            if scenario in ("scale_intake_noise", "autocorrelated_water", "missing_data")
            else 0.0
        )
        intake = max(0.0, intake_mean + rng.gauss(0.0, intake_noise))
        scale_sd = 0.4 if scenario != "scale_noise" else 0.4
        scale_weight = (
            true_weight + water + index * water_drift_kg_per_day + rng.gauss(0.0, scale_sd)
        )
        record_weight = not (scenario == "missing_data" and rng.random() < 0.2)
        record_intake = not (scenario == "missing_data" and rng.random() < 0.15)
        observations.append(
            DailyObservation(
                date(2026, 1, 1) + timedelta(days=index),
                scale_weight if record_weight else None,
                intake if record_intake else None,
                steps=7000,
            )
        )
        true_weight += (intake - true_tdee) / energy_density
    return tuple(observations)


@lru_cache(maxsize=32768)
def _estimate(
    candidate: str,
    observations: tuple[DailyObservation, ...],
    as_of: date | None = None,
    trend_result: TrendAnalysisResult | None = None,
    base_config: AdaptiveTdeeConfig | None = None,
):
    window_days = {
        "theil_sen_21": 21,
        "theil_sen_28": 28,
        "theil_sen_35": 35,
        "theil_sen_42": 42,
    }.get(candidate, 28)
    config = replace(
        base_config or AdaptiveTdeeConfig(),
        estimator_window_days=window_days,
        minimum_calendar_span_days=min(
            (base_config or AdaptiveTdeeConfig()).minimum_calendar_span_days,
            window_days,
        ),
    )
    prefix = tuple(item for item in observations if as_of is None or item.observed_on <= as_of)
    if trend_result is None:
        trends = _analyze_cached(prefix)
    elif as_of is None:
        trends = trend_result
    else:
        trends = replace(
            trend_result,
            points=tuple(point for point in trend_result.points if point.observed_on <= as_of),
        )
    if candidate.startswith("theil_sen") or candidate == "cumulative":
        if candidate == "cumulative":
            robust = estimate_adaptive_tdee(trends, config)
            return (
                None
                if robust.stability is TdeeStability.INSUFFICIENT
                else _cumulative_estimate(prefix, config),
                robust.stability,
                robust.uncertainty_kcal_per_day,
                robust.reason_codes,
            )
        result = estimate_adaptive_tdee(trends, config)
        return (
            result.adaptive_tdee_kcal_per_day,
            result.stability,
            result.uncertainty_kcal_per_day,
            result.reason_codes,
        )
    return _v1_estimate(trends, config), None, None, ()


def _v1_estimate(trends: TrendAnalysisResult, config: AdaptiveTdeeConfig) -> float | None:
    if not trends.points:
        return None
    start = trends.points[-1].observed_on - timedelta(days=config.aggregation_window_days - 1)
    available: list[float] = []
    for point in trends.points:
        if (
            point.observed_on < start
            or point.trailing_energy_intake_mean_kcal is None
            or point.window_weight_change_kg is None
        ):
            continue
        daily_balance = point.window_weight_change_kg * 7700.0 / trends.config.window_size_days
        available.append(point.trailing_energy_intake_mean_kcal - daily_balance)
    return None if len(available) < config.minimum_estimate_points else float(median(available))


def _cumulative_estimate(
    observations: tuple[DailyObservation, ...], config: AdaptiveTdeeConfig
) -> float | None:
    """OLS slope of cumulative intake minus 7700*weight change versus elapsed days."""
    if not observations:
        return None
    end = observations[-1].observed_on
    start = end - timedelta(days=config.estimator_window_days - 1)
    weights = tuple(
        item
        for item in observations
        if start <= item.observed_on <= end and item.body_weight_kg is not None
    )
    if len(weights) < config.minimum_weight_contributors:
        return None
    span = (weights[-1].observed_on - weights[0].observed_on).days + 1
    if span < min(config.minimum_calendar_span_days, config.estimator_window_days):
        return None
    midpoint = start + timedelta(days=(config.estimator_window_days - 1) // 2)
    first_half = sum(item.observed_on <= midpoint for item in weights)
    second_half = len(weights) - first_half
    if min(first_half, second_half) < config.minimum_weight_contributors_per_half:
        return None
    if (end - weights[-1].observed_on).days > config.maximum_days_since_last_weigh_in:
        return None
    intake_by_date = {item.observed_on: item.energy_intake_kcal for item in observations}
    expected_days = max((end - start).days, 1)
    observed_intake_days = sum(
        start <= observed_on < end and intake is not None
        for observed_on, intake in intake_by_date.items()
    )
    if observed_intake_days / expected_days < 0.9:
        return None
    if observed_intake_days < min(config.minimum_intake_contributors, expected_days):
        return None
    first = weights[0]
    points: list[tuple[float, float]] = [(0.0, 0.0)]
    cumulative_intake = 0.0
    previous_date = first.observed_on
    for weight in weights[1:]:
        interval = tuple(
            intake_by_date.get(previous_date + timedelta(days=offset))
            for offset in range((weight.observed_on - previous_date).days)
        )
        if not interval or any(value is None for value in interval):
            return None
        cumulative_intake += sum(interval)
        elapsed = (weight.observed_on - first.observed_on).days
        cumulative_net = cumulative_intake - config.energy_equivalent_kcal_per_kg * (
            weight.body_weight_kg - first.body_weight_kg
        )
        points.append((float(elapsed), float(cumulative_net)))
        previous_date = weight.observed_on
    if len(points) < 3:
        return None
    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    denominator = sum((x - mean_x) ** 2 for x, _ in points)
    if denominator <= 0:
        return None
    return sum((x - mean_x) * (y - mean_y) for x, y in points) / denominator


def _candidate_summary(
    seeds: Sequence[int], scenario: str | int, candidate: str, multiplier: float
) -> CandidateSummary:
    return _candidate_summaries(seeds, scenario, candidate, (multiplier,))[0]


def _candidate_summaries(
    seeds: Sequence[int],
    scenario: str | int,
    candidate: str,
    multipliers: Sequence[float],
    config: AdaptiveTdeeConfig | None = None,
) -> tuple[CandidateSummary, ...]:
    errors: list[float] = []
    stable_errors: list[float] = []
    stabilizing_errors: list[float] = []
    unstable_errors: list[float] = []
    counts = {state.value: 0 for state in TdeeStability}
    increases = [0] * len(multipliers)
    decreases = [0] * len(multipliers)
    holds = [0] * len(multipliers)
    for seed in seeds:
        model_mismatch = scenario in (6160, 9240)
        density = int(scenario) if model_mismatch else 7700.0
        obs = _make_observations(
            seed,
            "scale_intake_noise" if model_mismatch else scenario,
            energy_density=density,
            intake_offset=-300.0 if model_mismatch else 0.0,
        )
        trends = _analyze_cached(obs)
        estimate, stability, uncertainty, _ = _estimate(
            candidate, obs, trend_result=trends, base_config=config
        )
        if estimate is None:
            counts["insufficient"] += 1
            for index in range(len(multipliers)):
                holds[index] += 1
            continue
        error = estimate - 2000.0
        errors.append(error)
        if stability is not None:
            counts[stability.value] += 1
            if stability is TdeeStability.STABLE:
                stable_errors.append(error)
            elif stability is TdeeStability.STABILIZING:
                stabilizing_errors.append(error)
            elif stability is TdeeStability.UNSTABLE:
                unstable_errors.append(error)
        recommendation_eligible = stability is TdeeStability.STABLE or candidate == "v1"
        for index, multiplier in enumerate(multipliers):
            threshold = max(75.0, multiplier * (uncertainty or 0.0))
            if not recommendation_eligible or abs(error) <= threshold:
                holds[index] += 1
            elif error > 0:
                increases[index] += 1
            else:
                decreases[index] += 1
    return tuple(
        CandidateSummary(
            candidate,
            scenario,
            multiplier,
            len(seeds),
            len(errors) / len(seeds),
            None if candidate == "v1" else counts["stable"] / len(seeds),
            None if candidate == "v1" else counts["stabilizing"] / len(seeds),
            None if candidate == "v1" else counts["unstable"] / len(seeds),
            None if candidate == "v1" else counts["insufficient"] / len(seeds),
            _summary(errors),
            None if candidate == "v1" else _summary(stable_errors),
            None if candidate == "v1" else _summary(stabilizing_errors),
            None if candidate == "v1" else _summary(unstable_errors),
            holds[index] / len(seeds),
            increases[index] / len(seeds),
            decreases[index] / len(seeds),
            (increases[index] + decreases[index]) / len(seeds),
        )
        for index, multiplier in enumerate(multipliers)
    )


def _summary(values):
    if not values:
        return ErrorSummary(0, None, None, None, None, None, None)
    absolute_errors = sorted(abs(value) for value in values)

    def percentile(probability: float) -> float:
        return absolute_errors[
            min(len(absolute_errors) - 1, math.ceil(probability * len(absolute_errors)) - 1)
        ]

    return ErrorSummary(
        len(values),
        sum(values) / len(values),
        sum(absolute_errors) / len(values),
        median(absolute_errors),
        percentile(0.90),
        percentile(0.95),
        pstdev(absolute_errors),
    )


def _power_summary(
    seeds: Sequence[int], mismatch: int, candidate: str, multiplier: float
) -> PowerSummary:
    return _power_summaries(seeds, mismatch, candidate, (multiplier,))[0]


def _power_summaries(
    seeds: Sequence[int],
    mismatch: int,
    candidate: str,
    multipliers: Sequence[float],
    config: AdaptiveTdeeConfig | None = None,
) -> tuple[PowerSummary, ...]:
    direction_counts = [0] * len(multipliers)
    opposite_counts = [0] * len(multipliers)
    stable_counts = [0] * len(multipliers)
    latencies: list[list[int]] = [[] for _ in multipliers]
    detections = [{14: 0, 21: 0, 28: 0, 35: 0} for _ in multipliers]
    for seed in seeds:
        obs = _make_observations(seed, "scale_intake_noise", true_tdee=2000 + mismatch)
        trends = _analyze_cached(obs)
        observed_stable = False
        decided = [False] * len(multipliers)
        for day in (13, 20, 27, 34, 41):
            estimate, stability, uncertainty, _ = _estimate(
                candidate,
                obs,
                as_of=date(2026, 1, 1) + timedelta(days=day),
                trend_result=trends,
                base_config=config,
            )
            if estimate is None:
                continue
            if stability is TdeeStability.STABLE:
                observed_stable = True
            delta = estimate - 2000.0
            eligible = stability is TdeeStability.STABLE
            for index, multiplier in enumerate(multipliers):
                if decided[index] or not eligible:
                    continue
                threshold = max(75.0, multiplier * (uncertainty or 0.0))
                if abs(delta) <= threshold:
                    continue
                decided[index] = True
                if delta * mismatch > 0:
                    direction_counts[index] += 1
                    detection_day = day + 1
                    latencies[index].append(detection_day)
                    for horizon in detections[index]:
                        if detection_day <= horizon:
                            detections[index][horizon] += 1
                else:
                    opposite_counts[index] += 1
        if observed_stable:
            for index in range(len(multipliers)):
                stable_counts[index] += 1
    n = len(seeds)
    return tuple(
        PowerSummary(
            candidate,
            f"tdee_{mismatch:+d}",
            multiplier,
            n,
            stable_counts[index] / n,
            direction_counts[index] / n,
            opposite_counts[index] / n,
            median(latencies[index]) if latencies[index] else None,
            detections[index][14] / n,
            detections[index][21] / n,
            detections[index][28] / n,
            detections[index][35] / n,
        )
        for index, multiplier in enumerate(multipliers)
    )


@lru_cache(maxsize=64)
def _transition_summary(
    seeds: Sequence[int],
    scenario: str,
    candidate: str,
    config: AdaptiveTdeeConfig | None = None,
) -> TransitionSummary:
    day_errors: dict[int, list[float]] = {day: [] for day in (7, 14, 21, 28)}
    maximum_errors: list[float] = []
    recoveries_100: list[int] = []
    recoveries_150: list[int] = []
    stable_recovery_days: list[int] = []
    stable_by_day_28_count = 0
    stable_observations = stabilizing_observations = unstable_observations = 0
    evaluated_observations = 0
    signal_days_by_horizon: dict[int, list[bool]] = {day: [] for day in (7, 14, 21, 28)}
    first_signal_days: list[int] = []
    persistent_false_changes = 0
    false_increases = false_decreases = 0
    for seed in seeds:
        is_up = scenario.endswith("increase")
        has_water = "water" in scenario
        observations = _make_observations(
            seed,
            "autocorrelated_water" if has_water else "scale_intake_noise",
            days=98,
            abrupt_day=42,
            water_shift=has_water,
            intake_shift_kcal=500.0 if is_up else -500.0,
            water_shift_kg=1.5 if is_up else -1.5,
        )
        trends = _analyze_cached(observations)
        trajectory: dict[int, tuple[float, TdeeStability, tuple[str, ...]]] = {}
        for elapsed_day in range(7, 57, 7):
            offset = elapsed_day - 1
            as_of = date(2026, 1, 1) + timedelta(days=42 + offset)
            estimate, stability, _, reasons = _estimate(
                candidate,
                observations,
                as_of,
                trend_result=trends,
                base_config=config,
            )
            if estimate is not None:
                trajectory[elapsed_day] = (estimate, stability, reasons)
                evaluated_observations += 1
                stable_observations += stability is TdeeStability.STABLE
                stabilizing_observations += stability is TdeeStability.STABILIZING
                unstable_observations += stability is TdeeStability.UNSTABLE
        signed_errors = {day: value - 2000.0 for day, (value, _, _) in trajectory.items()}
        absolute_errors = {day: abs(error) for day, error in signed_errors.items()}
        signal_days = [
            day for day, (_, _, reasons) in trajectory.items() if "intake_regime_change" in reasons
        ]
        if signal_days:
            first_signal_days.append(signal_days[0])
        for horizon in signal_days_by_horizon:
            signal_days_by_horizon[horizon].append(any(day <= horizon for day in signal_days))
        if absolute_errors:
            maximum_errors.append(max(absolute_errors.values()))
        for day in day_errors:
            if day in signed_errors:
                day_errors[day].append(signed_errors[day])
        recovered_100 = next((day for day, error in absolute_errors.items() if error <= 100), None)
        recovered_150 = next((day for day, error in absolute_errors.items() if error <= 150), None)
        if recovered_100 is not None:
            recoveries_100.append(recovered_100)
        if recovered_150 is not None:
            recoveries_150.append(recovered_150)
        first_signal_day = signal_days[0] if signal_days else None
        stable_recovery = next(
            (
                day
                for day, (_, state, _) in trajectory.items()
                if first_signal_day is not None
                and day >= first_signal_day
                and state is TdeeStability.STABLE
            ),
            None,
        )
        if stable_recovery is not None:
            stable_recovery_days.append(stable_recovery)
        if trajectory.get(28, (None, None, ()))[1] is TdeeStability.STABLE:
            stable_by_day_28_count += 1
        day_28 = trajectory.get(28)
        false_increase = false_decrease = False
        if day_28 is not None:
            value, stability, _ = day_28
            delta = value - 2000.0 if value is not None else 0.0
            false_increase = stability is TdeeStability.STABLE and delta > 75.0
            false_decrease = stability is TdeeStability.STABLE and delta < -75.0
            false_increases += false_increase
            false_decreases += false_decrease
            persistent_false_changes += stability is TdeeStability.STABLE and abs(delta) > 150
    total = len(seeds)
    return TransitionSummary(
        candidate,
        scenario,
        total,
        _summary(maximum_errors),
        *(_summary(day_errors[day]) for day in (7, 14, 21, 28)),
        len(recoveries_100) / total,
        len(recoveries_150) / total,
        median(recoveries_100) if recoveries_100 else None,
        median(recoveries_150) if recoveries_150 else None,
        stable_by_day_28_count / total,
        median(stable_recovery_days) if stable_recovery_days else None,
        *(sum(values) / total for values in signal_days_by_horizon.values()),
        median(first_signal_days) if first_signal_days else None,
        stable_observations / evaluated_observations if evaluated_observations else 0.0,
        stabilizing_observations / evaluated_observations if evaluated_observations else 0.0,
        unstable_observations / evaluated_observations if evaluated_observations else 0.0,
        persistent_false_changes / total,
        false_increases / total,
        false_decreases / total,
    )


def _validate_seed_set(seeds: Sequence[int], seed_set: str) -> None:
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("seeds must be a non-empty sequence of unique integers.")
    bounds = {"development": (20000, 20299), "held_out": (30000, 30299)}
    if seed_set not in bounds:
        raise ValueError("seed_set must be 'development' or 'held_out'.")
    lower, upper = bounds[seed_set]
    if any(
        isinstance(seed, bool) or not isinstance(seed, int) or not lower <= seed <= upper
        for seed in seeds
    ):
        raise ValueError(f"all seeds must belong to the {seed_set} range {lower}..{upper}.")


@lru_cache(maxsize=4096)
def _analyze_cached(observations: tuple[DailyObservation, ...]) -> TrendAnalysisResult:
    return analyze_observation_trends(observations, TrendAnalysisConfig())
