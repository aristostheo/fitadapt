"""Large, fixed-seed CP35B confirmation of the frozen CP35A release policy.

All outputs are in-model synthetic evaluation. This module changes no production policy.
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from statistics import median
from typing import Any

from fitadapt.evaluation.cp35_hostile_validation import (
    CP35_CHECKPOINT_INDICES,
    CP35_DEVELOPMENT_SEEDS,
    CP35_EVALUATION_DAYS,
    CP35_HELD_OUT_SEEDS,
    HostileScenario,
    ScenarioMetrics,
    _aggregate_scenario,
    _evaluate_criteria,
    _simulate_user,
    _UserRun,
    cp35_scenarios,
)

CP35B_PROTOCOL_VERSION = "cp35b_confirmatory_v1"
CP35B_USERS_PER_SCENARIO = 100
CP35B_FIRST_SEED = 200000
CP35B_WORKERS = 4
CP35B_SCENARIO_NAMES = (
    "stationary_clean",
    "scale_noise",
    "intake_variation",
    "tdee_plus_300",
    "tdee_minus_300",
    "autocorrelated_water",
    "water_rebound",
    "illness_like_disturbance",
    "sodium_carb_weight_spike",
    "persistent_water_drift",
    "poor_adherence_with_water",
    "tdee_decline_underreporting",
    "repeated_slow_progress_near_floor",
    "repeated_proposals_near_bmi_band",
    "profile_update_below_bmi_18_5",
)
_NOISY_TRANSIENT_SCENARIOS = (
    "scale_noise",
    "autocorrelated_water",
    "water_rebound",
    "illness_like_disturbance",
    "sodium_carb_weight_spike",
)
_PREVIOUS_SEED_RANGES = (
    range(10000, 10300),
    range(20000, 20300),
    range(30000, 30300),
    range(40000, 40300),
    range(50000, 50300),
    range(60000, 60016),
    range(70000, 70016),
    range(80000, 80016),
    range(90000, 90016),
    range(120000, 120016),
    range(130000, 130016),
    CP35_DEVELOPMENT_SEEDS,
    CP35_HELD_OUT_SEEDS,
)


@dataclass(frozen=True, slots=True)
class UserRate:
    successes: int
    users: int
    rate: float
    wilson_95_lower: float
    wilson_95_upper: float


@dataclass(frozen=True, slots=True)
class CheckRate:
    successes: int
    checks: int
    rate: float


@dataclass(frozen=True, slots=True)
class LatencySummary:
    users_with_activation: int
    median_days: float | None
    p25_days: float | None
    p75_days: float | None


@dataclass(frozen=True, slots=True)
class ScenarioConfirmatoryResult:
    scenario: str
    category: str
    users: int
    seed_start: int
    seed_end_inclusive: int
    expected_direction: int | None
    pre_onset_activation_users: UserRate | None
    pre_onset_activation_events: int | None
    opposite_direction_activation_users: UserRate | None
    opposite_direction_activation_events: int | None
    opposite_or_pre_onset_activation_users: UserRate | None
    correct_activation_by_day_56_users: UserRate | None
    correct_activation_latency: LatencySummary | None
    ambiguous_automatic_decrease_activation_users: UserRate | None
    automatic_reversal_activation_users: UserRate
    review_required_decrease_users: UserRate
    review_required_decrease_checkpoints: CheckRate
    no_activation_by_day_84_users: UserRate
    all_checkpoints_cp29_deferred_users: UserRate
    users_with_safety_violations: UserRate
    safety_violation_count: int
    frozen_scenario_metrics: ScenarioMetrics


@dataclass(frozen=True, slots=True)
class ConfirmatoryReport:
    protocol_version: str
    evaluation_type: str
    users_per_scenario: int
    scenario_seed_ranges: tuple[tuple[str, int, int], ...]
    evaluation_days: int
    checkpoint_days: tuple[int, ...]
    frozen_criteria: tuple[Any, ...]
    scenarios: tuple[ScenarioConfirmatoryResult, ...]
    ambiguous_automatic_decrease_activation_users: UserRate
    noisy_transient_automatic_reversal_activation_users: UserRate
    notes: tuple[str, ...]


def run_confirmatory_study(*, max_workers: int = CP35B_WORKERS) -> ConfirmatoryReport:
    """Run the predeclared confirmatory scenario set on fresh deterministic cohorts."""
    if isinstance(max_workers, bool) or not isinstance(max_workers, int) or max_workers < 1:
        raise ValueError("max_workers must be a positive integer.")
    scenarios = _selected_scenarios()
    seed_ranges = _scenario_seed_ranges()
    _validate_seed_ranges(seed_ranges)
    tasks = tuple(
        (scenario, seed)
        for scenario, (_, start, end) in zip(scenarios, seed_ranges, strict=True)
        for seed in range(start, end + 1)
    )
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        all_runs = tuple(pool.map(_simulate_task, tasks, chunksize=2))

    runs_by_scenario: dict[str, list[_UserRun]] = {scenario.name: [] for scenario in scenarios}
    for (scenario, _), run in zip(tasks, all_runs, strict=True):
        runs_by_scenario[scenario.name].append(run)

    scenario_results = tuple(
        _summarize_scenario(scenario, tuple(runs), seed_range[1], seed_range[2])
        for scenario, runs, seed_range in zip(
            scenarios, (runs_by_scenario[item.name] for item in scenarios), seed_ranges, strict=True
        )
    )
    frozen_criteria = _evaluate_criteria(
        tuple(result.frozen_scenario_metrics for result in scenario_results)
    )
    ambiguous_runs = tuple(
        run
        for scenario in scenarios
        if scenario.ambiguous
        for run in runs_by_scenario[scenario.name]
    )
    noisy_runs = tuple(run for name in _NOISY_TRANSIENT_SCENARIOS for run in runs_by_scenario[name])
    return ConfirmatoryReport(
        CP35B_PROTOCOL_VERSION,
        "in-model synthetic evaluation",
        CP35B_USERS_PER_SCENARIO,
        seed_ranges,
        CP35_EVALUATION_DAYS,
        tuple(index + 1 for index in CP35_CHECKPOINT_INDICES),
        frozen_criteria,
        scenario_results,
        _user_rate(
            sum(run.automatic_decrease_activations > 0 for run in ambiguous_runs),
            len(ambiguous_runs),
        ),
        _user_rate(sum(run.confirmed_reversals > 0 for run in noisy_runs), len(noisy_runs)),
        (
            "Estimator parameters, CP29 thresholds, CP30 rules, CP35A review policy, and frozen "
            "criteria are unchanged.",
            "Every scenario uses 100 new users and a disjoint deterministic seed block; no prior "
            "CP35/CP35A seed is reused.",
            "Main-cohort runs never supply review confirmation.",
            "User-level proportion intervals are 95% Wilson score intervals. Repeated checkpoint "
            "rates are descriptive and have no independence-based interval.",
            "An activation on or before change_day + 1 is classified as pre-onset for the frozen "
            "opposite-activation criterion; correct activation latency follows the CP35 "
            "definition.",
            "No policy or threshold was tuned on this confirmatory cohort.",
            "Synthetic outcomes do not establish real-world, clinical, or physiological validity.",
        ),
    )


def _selected_scenarios() -> tuple[HostileScenario, ...]:
    by_name = {scenario.name: scenario for scenario in cp35_scenarios()}
    missing = set(CP35B_SCENARIO_NAMES) - by_name.keys()
    if missing:
        raise RuntimeError(f"confirmatory scenarios are missing from CP35: {sorted(missing)}")
    return tuple(by_name[name] for name in CP35B_SCENARIO_NAMES)


def _scenario_seed_ranges() -> tuple[tuple[str, int, int], ...]:
    return tuple(
        (
            name,
            CP35B_FIRST_SEED + index * CP35B_USERS_PER_SCENARIO,
            CP35B_FIRST_SEED + (index + 1) * CP35B_USERS_PER_SCENARIO - 1,
        )
        for index, name in enumerate(CP35B_SCENARIO_NAMES)
    )


def _validate_seed_ranges(ranges: Iterable[tuple[str, int, int]]) -> None:
    values: list[int] = []
    names: list[str] = []
    for name, start, end in ranges:
        if not name or isinstance(start, bool) or isinstance(end, bool):
            raise ValueError("each seed range must have a name and integer endpoints.")
        if not isinstance(start, int) or not isinstance(end, int) or end - start + 1 != 100:
            raise ValueError("each scenario must have exactly 100 contiguous integer seeds.")
        names.append(name)
        values.extend(range(start, end + 1))
    if len(names) != len(set(names)) or len(values) != len(set(values)):
        raise ValueError("scenario names and seed ranges must be unique.")
    if any(seed in previous for seed in values for previous in _PREVIOUS_SEED_RANGES):
        raise ValueError("confirmatory seeds must be disjoint from every earlier cohort.")


def _simulate_task(task: tuple[HostileScenario, int]) -> _UserRun:
    scenario, seed = task
    return _simulate_user(scenario, seed)


def _summarize_scenario(
    scenario: HostileScenario,
    runs: tuple[_UserRun, ...],
    seed_start: int,
    seed_end: int,
) -> ScenarioConfirmatoryResult:
    user_count = len(runs)
    expected = scenario.expected_direction
    pre_onset_events = (
        None
        if expected is None
        else tuple(
            (direction, day)
            for run in runs
            for direction, day in run.activation_events
            if day <= scenario.change_day
        )
    )
    opposite_events = (
        None
        if expected is None
        else tuple(
            (direction, day)
            for run in runs
            for direction, day in run.activation_events
            if day > scenario.change_day and direction != expected
        )
    )
    frozen_opposite_or_pre_onset_users = (
        None
        if expected is None
        else sum(
            any(
                direction != expected or day <= scenario.change_day + 1
                for direction, day in run.activation_events
            )
            for run in runs
        )
    )
    pre_onset_users = (
        None
        if pre_onset_events is None
        else sum(
            any(day <= scenario.change_day for _, day in run.activation_events) for run in runs
        )
    )
    opposite_users = (
        None
        if opposite_events is None
        else sum(
            any(
                day > scenario.change_day and direction != expected
                for direction, day in run.activation_events
            )
            for run in runs
        )
    )
    correct_latencies = (
        []
        if expected is None
        else [
            min(
                (
                    day - scenario.change_day - 1
                    for direction, day in run.activation_events
                    if direction == expected
                    and day > scenario.change_day + 1
                    and 0 <= day - scenario.change_day - 1 <= 56
                ),
                default=None,
            )
            for run in runs
        ]
    )
    detected_by56 = (
        None if expected is None else sum(value is not None for value in correct_latencies)
    )
    latency_values = [value for value in correct_latencies if value is not None]
    checks = sum(run.metrics.checks for run in runs)
    review_required_checks = sum(run.review_required_proposals for run in runs)
    ambiguous_decrease_users = (
        None
        if not scenario.ambiguous
        else sum(run.automatic_decrease_activations > 0 for run in runs)
    )
    metrics = _aggregate_scenario(scenario, runs)
    return ScenarioConfirmatoryResult(
        scenario.name,
        scenario.category,
        user_count,
        seed_start,
        seed_end,
        expected,
        None if pre_onset_users is None else _user_rate(pre_onset_users, user_count),
        None if pre_onset_events is None else len(pre_onset_events),
        None if opposite_users is None else _user_rate(opposite_users, user_count),
        None if opposite_events is None else len(opposite_events),
        None
        if frozen_opposite_or_pre_onset_users is None
        else _user_rate(frozen_opposite_or_pre_onset_users, user_count),
        None if detected_by56 is None else _user_rate(detected_by56, user_count),
        None
        if expected is None
        else LatencySummary(
            len(latency_values),
            None if not latency_values else float(median(latency_values)),
            None if not latency_values else _percentile(latency_values, 0.25),
            None if not latency_values else _percentile(latency_values, 0.75),
        ),
        None
        if ambiguous_decrease_users is None
        else _user_rate(ambiguous_decrease_users, user_count),
        _user_rate(sum(run.confirmed_reversals > 0 for run in runs), user_count),
        _user_rate(sum(run.review_required_proposals > 0 for run in runs), user_count),
        CheckRate(review_required_checks, checks, review_required_checks / checks),
        _user_rate(sum(not run.activation_events for run in runs), user_count),
        _user_rate(sum(run.metrics.all_checkpoint_deferred_rate > 0 for run in runs), user_count),
        _user_rate(sum(run.safety_violations > 0 for run in runs), user_count),
        sum(run.safety_violations for run in runs),
        metrics,
    )


def _user_rate(successes: int, users: int) -> UserRate:
    if not 0 <= successes <= users or users <= 0:
        raise ValueError("rate successes must be within a positive user denominator.")
    rate = successes / users
    z = 1.959963984540054
    z_squared = z * z
    denominator = 1 + z_squared / users
    center = (rate + z_squared / (2 * users)) / denominator
    margin = (
        z * math.sqrt(rate * (1 - rate) / users + z_squared / (4 * users * users)) / denominator
    )
    lower = 0.0 if successes == 0 else max(0.0, center - margin)
    upper = 1.0 if successes == users else min(1.0, center + margin)
    return UserRate(successes, users, rate, lower, upper)


def _percentile(values: list[int], probability: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = math.floor(index)
    upper = math.ceil(index)
    fraction = index - lower
    return float(ordered[lower] * (1 - fraction) + ordered[upper] * fraction)


def report_json(report: ConfirmatoryReport) -> str:
    return json.dumps(asdict(report), indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=CP35B_WORKERS)
    args = parser.parse_args()
    print(report_json(run_confirmatory_study(max_workers=args.workers)))


if __name__ == "__main__":
    main()
