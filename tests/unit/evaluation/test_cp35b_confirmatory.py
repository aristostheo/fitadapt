"""CP35B confirmatory cohort protocol and leakage-audit tests."""

import json
import sys
from types import SimpleNamespace

import pytest

from fitadapt.evaluation import cp35_hostile_validation as cp35
from fitadapt.evaluation import cp35b_confirmatory as cp35b


def test_cp35b_protocol_covers_frozen_criteria_and_uses_fresh_100_user_blocks() -> None:
    scenarios = cp35b._selected_scenarios()
    seed_ranges = cp35b._scenario_seed_ranges()
    cp35b._validate_seed_ranges(seed_ranges)
    names = {scenario.name for scenario in scenarios}

    assert len(scenarios) == 15
    assert len(seed_ranges) == len(scenarios)
    assert all(end - start + 1 == 100 for _, start, end in seed_ranges)
    assert min(start for _, start, _ in seed_ranges) == 200000
    assert max(end for _, _, end in seed_ranges) == 201499
    assert not any(
        10000 <= seed <= 10299 for _, start, end in seed_ranges for seed in range(start, end + 1)
    )
    assert {
        "stationary_clean",
        "scale_noise",
        "intake_variation",
        "tdee_plus_300",
        "tdee_minus_300",
        "autocorrelated_water",
        "water_rebound",
        "poor_adherence_with_water",
        "persistent_water_drift",
        "tdee_decline_underreporting",
    } <= names
    assert all(criterion.criterion_id for criterion in cp35.CP35_FROZEN_CRITERIA)


def test_wilson_interval_covers_boundary_and_single_success_cases() -> None:
    none = cp35b._user_rate(0, 100)
    one = cp35b._user_rate(1, 100)
    all_users = cp35b._user_rate(100, 100)

    assert none.rate == 0
    assert none.wilson_95_lower == 0
    assert 0 < none.wilson_95_upper < one.wilson_95_upper
    assert one.rate == 0.01
    assert one.wilson_95_lower < one.rate < one.wilson_95_upper
    assert all_users.rate == 1
    assert all_users.wilson_95_upper == 1
    assert all_users.wilson_95_lower > 0.95


def test_held_out_plus_300_seed_150011_is_reproduced_as_pre_onset_false_positive() -> None:
    scenario = next(item for item in cp35.cp35_scenarios() if item.name == "tdee_plus_300")
    run = cp35._simulate_user(scenario, 150011)
    seed_range = next(item for item in cp35b._scenario_seed_ranges() if item[0] == scenario.name)
    result = cp35b._summarize_scenario(scenario, (run,), seed_range[1], seed_range[1])

    assert cp35._actual_tdee(scenario, 2400, 27) == 2400
    assert cp35._actual_tdee(scenario, 2400, 28) == 2700
    assert run.activation_events == ((1, 28), (1, 49), (1, 63))
    assert run.false_activations == 1
    assert result.pre_onset_activation_users is not None
    assert result.pre_onset_activation_users.successes == 1
    assert result.pre_onset_activation_events == 1
    assert result.opposite_or_pre_onset_activation_users is not None
    assert result.opposite_or_pre_onset_activation_users.successes == 1


def test_seed_validation_rejects_invalid_and_reused_ranges() -> None:
    invalid_ranges = (
        (("", 200000, 200099),),
        (("scenario", True, 200099),),
        (("scenario", 200000, 200098),),
        (("scenario", 200000, 200099), ("scenario", 200100, 200199)),
        (("first", 200000, 200099), ("second", 200050, 200149)),
        (("old", 10000, 10099),),
    )
    for ranges in invalid_ranges:
        with pytest.raises(ValueError):
            cp35b._validate_seed_ranges(ranges)


def test_scenario_selection_fails_if_a_frozen_case_disappears(monkeypatch) -> None:
    monkeypatch.setattr(cp35b, "cp35_scenarios", lambda: ())

    with pytest.raises(RuntimeError, match="confirmatory scenarios are missing"):
        cp35b._selected_scenarios()


def test_user_rate_rejects_invalid_counts() -> None:
    with pytest.raises(ValueError):
        cp35b._user_rate(-1, 100)
    with pytest.raises(ValueError):
        cp35b._user_rate(1, 0)
    with pytest.raises(ValueError):
        cp35b._user_rate(101, 100)


def test_scenario_summary_separates_activation_classes(monkeypatch) -> None:
    scenario = next(item for item in cp35.cp35_scenarios() if item.name == "tdee_plus_300")
    metrics = SimpleNamespace(checks=9, all_checkpoint_deferred_rate=0.0)
    run = SimpleNamespace(
        activation_events=((1, 28), (1, 49), (-1, 63)),
        confirmed_reversals=1,
        review_required_proposals=2,
        automatic_decrease_activations=0,
        safety_violations=0,
        metrics=metrics,
    )
    monkeypatch.setattr(cp35b, "_aggregate_scenario", lambda scenario, runs: metrics)

    result = cp35b._summarize_scenario(scenario, (run,), 200000, 200000)

    assert result.pre_onset_activation_users.successes == 1
    assert result.pre_onset_activation_events == 1
    assert result.opposite_direction_activation_users.successes == 1
    assert result.opposite_direction_activation_events == 1
    assert result.opposite_or_pre_onset_activation_users.successes == 1
    assert result.correct_activation_by_day_56_users.successes == 1
    assert result.correct_activation_latency.median_days == 20
    assert result.automatic_reversal_activation_users.successes == 1
    assert result.review_required_decrease_checkpoints.rate == pytest.approx(2 / 9)
    assert result.no_activation_by_day_84_users.successes == 0
    assert result.users_with_safety_violations.successes == 0


def test_ambiguous_scenario_summary_reports_unreviewed_decrease_and_full_hold(monkeypatch) -> None:
    scenario = next(
        item for item in cp35.cp35_scenarios() if item.name == "poor_adherence_with_water"
    )
    metrics = SimpleNamespace(checks=9, all_checkpoint_deferred_rate=1.0)
    run = SimpleNamespace(
        activation_events=((-1, 70),),
        confirmed_reversals=0,
        review_required_proposals=3,
        automatic_decrease_activations=1,
        safety_violations=2,
        metrics=metrics,
    )
    monkeypatch.setattr(cp35b, "_aggregate_scenario", lambda scenario, runs: metrics)

    result = cp35b._summarize_scenario(scenario, (run,), 201000, 201000)

    assert result.pre_onset_activation_users is None
    assert result.correct_activation_by_day_56_users is None
    assert result.ambiguous_automatic_decrease_activation_users.successes == 1
    assert result.no_activation_by_day_84_users.successes == 0
    assert result.all_checkpoints_cp29_deferred_users.successes == 1
    assert result.users_with_safety_violations.successes == 1
    assert result.safety_violation_count == 2


def test_summarize_scenario_handles_no_events_for_true_change(monkeypatch) -> None:
    scenario = next(item for item in cp35.cp35_scenarios() if item.name == "tdee_minus_300")
    metrics = SimpleNamespace(checks=9, all_checkpoint_deferred_rate=1.0)
    run = SimpleNamespace(
        activation_events=(),
        confirmed_reversals=0,
        review_required_proposals=0,
        automatic_decrease_activations=0,
        safety_violations=0,
        metrics=metrics,
    )
    monkeypatch.setattr(cp35b, "_aggregate_scenario", lambda scenario, runs: metrics)

    result = cp35b._summarize_scenario(scenario, (run,), 200400, 200400)

    assert result.pre_onset_activation_users.successes == 0
    assert result.opposite_direction_activation_users.successes == 0
    assert result.correct_activation_by_day_56_users.successes == 0
    assert result.correct_activation_latency.users_with_activation == 0
    assert result.correct_activation_latency.median_days is None
    assert result.no_activation_by_day_84_users.successes == 1


def test_confirmatory_orchestration_assembles_all_scenarios(monkeypatch) -> None:
    class ImmediatePool:
        def __init__(self, max_workers: int) -> None:
            assert max_workers == 1

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def map(self, _function, tasks, *, chunksize: int):
            assert chunksize == 2
            return tuple(
                SimpleNamespace(automatic_decrease_activations=0, confirmed_reversals=0)
                for _ in tasks
            )

    monkeypatch.setattr(cp35b, "ProcessPoolExecutor", ImmediatePool)
    monkeypatch.setattr(
        cp35b,
        "_summarize_scenario",
        lambda scenario, runs, start, end: SimpleNamespace(frozen_scenario_metrics=scenario.name),
    )
    monkeypatch.setattr(cp35b, "_evaluate_criteria", lambda metrics: tuple(metrics))

    report = cp35b.run_confirmatory_study(max_workers=1)

    assert report.protocol_version == cp35b.CP35B_PROTOCOL_VERSION
    assert report.evaluation_type == "in-model synthetic evaluation"
    assert len(report.scenarios) == 15
    assert report.frozen_criteria == tuple(cp35b.CP35B_SCENARIO_NAMES)
    assert report.ambiguous_automatic_decrease_activation_users.successes == 0
    assert report.noisy_transient_automatic_reversal_activation_users.successes == 0


def test_confirmatory_orchestration_rejects_invalid_worker_count() -> None:
    with pytest.raises(ValueError, match="max_workers"):
        cp35b.run_confirmatory_study(max_workers=0)
    with pytest.raises(ValueError, match="max_workers"):
        cp35b.run_confirmatory_study(max_workers=True)


def test_report_json_and_cli(monkeypatch, capsys) -> None:
    rate = cp35b._user_rate(0, 1)
    report = cp35b.ConfirmatoryReport(
        cp35b.CP35B_PROTOCOL_VERSION,
        "in-model synthetic evaluation",
        100,
        (),
        84,
        (),
        (),
        (),
        rate,
        rate,
        (),
    )
    assert json.loads(cp35b.report_json(report))["evaluation_type"] == (
        "in-model synthetic evaluation"
    )
    monkeypatch.setattr(sys, "argv", ["cp35b", "--workers", "1"])
    monkeypatch.setattr(cp35b, "run_confirmatory_study", lambda *, max_workers: report)
    cp35b.main()
    assert json.loads(capsys.readouterr().out)["protocol_version"] == (cp35b.CP35B_PROTOCOL_VERSION)
