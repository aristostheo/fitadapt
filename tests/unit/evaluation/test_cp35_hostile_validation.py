"""Bounded, deterministic checks for the CP35 hostile validation harness."""

import json
import sys
from dataclasses import replace

import pytest

from fitadapt.evaluation import cp35_hostile_validation as validation


def test_cp35_development_and_held_out_seed_ranges_are_disjoint() -> None:
    validation._validate_seeds((140000, 140015), "development")
    validation._validate_seeds((150000, 150015), "held_out")
    with pytest.raises(ValueError, match="development range"):
        validation._validate_seeds((150000,), "development")
    with pytest.raises(ValueError, match="held_out range"):
        validation._validate_seeds((140000,), "held_out")


@pytest.mark.parametrize(
    ("seeds", "seed_set"),
    [
        ((), "development"),
        ((140000, 140000), "development"),
        ((True,), "development"),
        ((140000,), "unknown"),
    ],
)
def test_cp35_seed_validator_rejects_invalid_cohorts(seeds, seed_set) -> None:
    with pytest.raises(ValueError):
        validation._validate_seeds(seeds, seed_set)


def test_cp35_scenario_matrix_covers_all_required_failure_families() -> None:
    scenarios = validation.cp35_scenarios()
    names = {scenario.name for scenario in scenarios}
    categories = {scenario.category for scenario in scenarios}

    assert {
        "logging_underreport_step",
        "logging_overreport_step",
        "logging_bias_drift",
        "missing_weekends",
        "missing_clustered_weights",
        "missing_after_high_intake",
        "missing_plan_transition",
        "sparse_regular",
        "water_rebound",
        "illness_like_disturbance",
        "sodium_carb_weight_spike",
        "tdee_minus_200",
        "tdee_minus_300",
        "tdee_plus_200",
        "tdee_plus_300",
        "tdee_decline_with_water",
        "tdee_decline_underreporting",
        "poor_adherence_with_water",
        "intake_regime_change_missing",
        "plateau_noise_partial_logs",
    } <= names
    assert {
        "stationary",
        "logging_bias",
        "adherence",
        "missing_data",
        "water",
        "ambiguity",
        "combined",
        "safety",
        "true_tdee_change",
    } <= categories
    assert len(names) == len(scenarios)


def test_cp35_external_style_audit_passes_every_boundary_case() -> None:
    results = validation._external_style_audit()

    assert len(results) == 5
    assert {name for name, _, _ in results} == {
        "oversized_cut_request",
        "absurd_intake",
        "low_bmi_below_18_5",
        "near_underweight_bmi_band",
        "normal_bmi_aggressive_cut",
    }
    assert all(passed for _, _, passed in results)


def test_cp35_simulation_is_repeatable_and_replays_accepted_activation() -> None:
    scenario = next(item for item in validation.cp35_scenarios() if item.name == "tdee_minus_300")

    first = validation._simulate_user(scenario, 140000)
    second = validation._simulate_user(scenario, 140000)

    assert first == second
    assert first.metrics.checks == 9
    assert first.safety_violations == 0
    assert first.metrics.ambiguity_decrease_activation_rate == 0


def test_cp35a_decrease_proposals_are_separate_from_automatic_activation() -> None:
    scenario = next(item for item in validation.cp35_scenarios() if item.name == "tdee_minus_300")

    unreviewed = validation._simulate_user(scenario, 140000)
    explicitly_reviewed = validation._simulate_user(scenario, 140000, confirm_review_required=True)

    assert unreviewed.review_required_proposals > 0
    assert unreviewed.ready_decrease_proposals == 0
    assert unreviewed.automatic_decrease_activations == 0
    assert explicitly_reviewed.review_accepted_decreases > 0


def test_cp35_criteria_reject_unsafe_metrics_and_hold_ambiguity() -> None:
    scenario_rows = []
    for scenario in validation.cp35_scenarios():
        scenario_rows.append(
            validation.ScenarioMetrics(
                name=scenario.name,
                category=scenario.category,
                users=1,
                checks=5,
                cp29_hold_rate=0.8,
                cp29_defer_rate=0.2,
                cp29_increase_rate=0.0,
                cp29_decrease_rate=0.0,
                cp30_activate_rate=0.0,
                cp30_defer_rate=0.2,
                cp30_suppress_rate=0.0,
                review_required_decrease_proposal_rate=(
                    1.0 if scenario.name == "tdee_minus_300" else 0.0
                ),
                review_required_decrease_user_rate=(
                    1.0 if scenario.name == "tdee_minus_300" else 0.0
                ),
                activation_ready_decrease_proposal_rate=0.0,
                activation_ready_increase_proposal_rate=0.0,
                automatic_decrease_activation_rate=0.0,
                false_activation_rate=0.0,
                activation_ready_increase_by56_rate=1.0
                if scenario.name == "tdee_plus_300"
                else 0.0,
                reversal_proposal_rate=0.0,
                reversal_pending_rate=0.0,
                confirmed_reversal_rate=0.0,
                review_accepted_decrease_activation_rate=0.0,
                integration_status_rates=(),
                false_increase_rate=0.0,
                false_decrease_rate=0.0,
                false_change_rate=0.0,
                correct_direction_rate=1.0 if scenario.expected_direction else None,
                opposite_direction_rate=0.0 if scenario.expected_direction else None,
                missed_change_rate=0.0 if scenario.expected_direction else None,
                median_cp29_proposal_day=(
                    20.0 if scenario.expected_direction is not None else None
                ),
                median_cp30_activation_day=(
                    35.0 if scenario.expected_direction is not None else None
                ),
                median_transient_recovery_days=7.0 if scenario.category == "water" else None,
                mean_activations_per_user_12_weeks=0.0,
                direction_reversal_rate=0.0,
                repeated_same_direction_rate=0.0,
                indefinitely_inert_rate=0.0,
                all_checkpoint_deferred_rate=0.0,
                ambiguity_decrease_activation_rate=0.0,
                safety_violation_rate=0.0,
            )
        )

    results = validation._evaluate_criteria(tuple(scenario_rows))

    assert len(results) == len(validation.CP35_FROZEN_CRITERIA)
    assert all(item.passed for item in results)


def test_cp35_transient_and_gate_helpers_keep_day_semantics() -> None:
    assert validation._transient_end_day("spike") == 40
    assert validation._transient_end_day("persistent_drift") is None
    assert validation._relative_day(63, 28) == 34
    assert validation._relative_day(None, 28) is None


def test_cp35_disturbance_factories_cover_regime_bias_missingness_and_water_modes() -> None:
    scenarios = {item.name: item for item in validation.cp35_scenarios()}
    change = scenarios["tdee_minus_300"]
    gradual = scenarios["gradual_tdee_minus_300"]

    assert validation._actual_tdee(scenarios["stationary_clean"], 2000, 50) == 2000
    assert validation._actual_tdee(change, 2000, 27) == 2000
    assert validation._actual_tdee(change, 2000, 28) == 1700
    assert validation._actual_tdee(gradual, 2000, 27) == 2000
    assert validation._actual_tdee(gradual, 2000, 41) == 1850
    assert validation._actual_tdee(gradual, 2000, 55) == 1700
    assert validation._adherence_delta(scenarios["inconsistent_adherence"], 2400, 10, 140000) in (
        -300.0,
        0.0,
        300.0,
    )
    assert validation._adherence_delta(
        scenarios["intake_variation"], 2400, 10, 140000
    ) == pytest.approx(validation._adherence_delta(scenarios["intake_variation"], 2400, 10, 140000))
    assert validation._logging_bias(scenarios["logging_underreport_step"], 27) == 0
    assert validation._logging_bias(scenarios["logging_underreport_step"], 28) == 350
    assert validation._logging_bias(scenarios["logging_bias_drift"], 27) == 0
    assert validation._logging_bias(scenarios["logging_bias_drift"], 28) > 0

    activations = [35]
    assert validation._logging_availability(scenarios["missing_weekends"], 4, 2400, 2400, []) == (
        False,
        False,
    )
    assert validation._logging_availability(
        scenarios["missing_clustered_weights"], 40, 2400, 2400, []
    ) == (
        False,
        True,
    )
    assert validation._logging_availability(
        scenarios["missing_after_high_intake"], 10, 2700, 2400, []
    ) == (
        True,
        False,
    )
    assert validation._logging_availability(
        scenarios["missing_plan_transition"], 35, 2400, 2400, activations
    ) == (
        False,
        False,
    )
    assert validation._logging_availability(scenarios["sparse_regular"], 1, 2400, 2400, []) == (
        False,
        False,
    )

    for scenario_name in (
        "autocorrelated_water",
        "water_rebound",
        "illness_like_disturbance",
        "sodium_carb_weight_spike",
        "persistent_water_drift",
    ):
        scenario = scenarios[scenario_name]
        first = validation._water_value(scenario, 40, 0.1, 140000)
        second = validation._water_value(scenario, 40, 0.1, 140000)
        assert first == second
    assert validation._water_value(scenarios["persistent_water_drift"], 10, 0, 140000) < 0


def test_cp35_category_aggregator_combines_status_rates_and_optional_medians() -> None:
    scenario = validation.cp35_scenarios()[0]
    base = validation.ScenarioMetrics(
        name=scenario.name,
        category=scenario.category,
        users=1,
        checks=2,
        cp29_hold_rate=0.5,
        cp29_defer_rate=0.5,
        cp29_increase_rate=0,
        cp29_decrease_rate=0,
        cp30_activate_rate=0,
        cp30_defer_rate=0.5,
        cp30_suppress_rate=0,
        review_required_decrease_proposal_rate=0,
        review_required_decrease_user_rate=0,
        activation_ready_decrease_proposal_rate=0,
        activation_ready_increase_proposal_rate=0,
        automatic_decrease_activation_rate=0,
        false_activation_rate=0,
        activation_ready_increase_by56_rate=0,
        reversal_proposal_rate=0,
        reversal_pending_rate=0,
        confirmed_reversal_rate=0,
        review_accepted_decrease_activation_rate=0,
        integration_status_rates=(("more_data_needed", 0.5), ("plan_remains_appropriate", 0.5)),
        false_increase_rate=0,
        false_decrease_rate=0,
        false_change_rate=0,
        correct_direction_rate=None,
        opposite_direction_rate=None,
        missed_change_rate=None,
        median_cp29_proposal_day=None,
        median_cp30_activation_day=None,
        median_transient_recovery_days=None,
        mean_activations_per_user_12_weeks=0,
        direction_reversal_rate=0,
        repeated_same_direction_rate=0,
        indefinitely_inert_rate=0,
        all_checkpoint_deferred_rate=0.5,
        ambiguity_decrease_activation_rate=0,
        safety_violation_rate=0,
    )
    another = replace(base, users=1, checks=2, cp29_hold_rate=1.0, median_cp30_activation_day=14)

    combined = validation._aggregate_scenario(
        scenario,
        (
            validation._UserRun(base, (), (), 0, (), ()),
            validation._UserRun(another, (), (), 0, (), ()),
        ),
    )

    assert combined.users == 2
    assert combined.cp29_hold_rate == pytest.approx(0.75)
    assert dict(combined.integration_status_rates) == {
        "more_data_needed": 0.5,
        "plan_remains_appropriate": 0.5,
    }
    assert combined.median_cp30_activation_day == 14


def test_cp35_gate_study_reports_stationary_and_true_mismatch_paths() -> None:
    rows = validation._run_gate_tradeoffs((140000,))

    assert {row.scenario for row in rows} == {
        "tdee_minus_200",
        "tdee_minus_300",
        "stationary_clean",
        "autocorrelated_water",
        "persistent_water_drift",
    }
    assert all(row.users == 1 for row in rows)
    assert all(row.activation_rate_28_day >= 0 for row in rows)


def test_cp35_runner_serializes_full_report_with_mocked_user_runs(monkeypatch) -> None:
    def fake_simulation(scenario, seed, decrease_gate_days=42, *, confirm_review_required=False):
        statuses = ((validation.IntegrationAppStatus.PLAN_REMAINS_APPROPRIATE.value, 1.0),)
        metrics = validation.ScenarioMetrics(
            name=scenario.name,
            category=scenario.category,
            users=1,
            checks=len(validation.CP35_CHECKPOINT_INDICES),
            cp29_hold_rate=1.0,
            cp29_defer_rate=0.0,
            cp29_increase_rate=0.0,
            cp29_decrease_rate=0.0,
            cp30_activate_rate=0.0,
            cp30_defer_rate=0.0,
            cp30_suppress_rate=0.0,
            review_required_decrease_proposal_rate=0.0,
            review_required_decrease_user_rate=0.0,
            activation_ready_decrease_proposal_rate=0.0,
            activation_ready_increase_proposal_rate=0.0,
            automatic_decrease_activation_rate=0.0,
            false_activation_rate=0.0,
            activation_ready_increase_by56_rate=(1.0 if scenario.name == "tdee_plus_300" else 0.0),
            reversal_proposal_rate=0.0,
            reversal_pending_rate=0.0,
            confirmed_reversal_rate=0.0,
            review_accepted_decrease_activation_rate=0.0,
            integration_status_rates=statuses,
            false_increase_rate=0.0,
            false_decrease_rate=0.0,
            false_change_rate=0.0,
            correct_direction_rate=None if scenario.expected_direction is None else 1.0,
            opposite_direction_rate=None if scenario.expected_direction is None else 0.0,
            missed_change_rate=None if scenario.expected_direction is None else 0.0,
            median_cp29_proposal_day=None,
            median_cp30_activation_day=None,
            median_transient_recovery_days=7.0 if scenario.category == "water" else None,
            mean_activations_per_user_12_weeks=0.0,
            direction_reversal_rate=0.0,
            repeated_same_direction_rate=0.0,
            indefinitely_inert_rate=0.0,
            all_checkpoint_deferred_rate=0.0,
            ambiguity_decrease_activation_rate=0.0,
            safety_violation_rate=0.0,
        )
        return validation._UserRun(metrics, (), (), 0, (), ())

    monkeypatch.setattr(validation, "_simulate_user", fake_simulation)
    monkeypatch.setattr(validation, "_run_gate_tradeoffs", lambda seeds: ())

    report = validation.run_cp35_hostile_study((140000,), seed_set="development")
    serialized = json.loads(validation.report_json(report))

    assert serialized["seed_set"] == "development"
    assert len(serialized["scenarios"]) == len(validation.cp35_scenarios())
    assert dict(serialized["overall_cp29_rates"])["hold"] == 1.0
    assert serialized["overall_app_status_rates"] == [
        [validation.IntegrationAppStatus.PLAN_REMAINS_APPROPRIATE.value, 1.0]
    ]
    with pytest.raises(TypeError, match="cannot serialize"):
        validation._json_default(object())


def test_cp35_cli_validates_count_and_emits_report(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["cp35", "--seed-set", "development", "--count", "17"])
    with pytest.raises(SystemExit):
        validation.main()
    assert "--count must be between 1 and 16" in capsys.readouterr().err

    monkeypatch.setattr(sys, "argv", ["cp35", "--seed-set", "development", "--count", "1"])
    monkeypatch.setattr(
        validation,
        "run_cp35_hostile_study",
        lambda seeds, seed_set: validation.CP35Report(
            validation.CP35_PROTOCOL_VERSION,
            seed_set,
            validation.CP35_SEED_DESCRIPTION,
            tuple(seeds),
            validation.CP35_EVALUATION_DAYS,
            tuple(index + 1 for index in validation.CP35_CHECKPOINT_INDICES),
            (),
            (),
            (),
            (),
            (),
            (),
            (),
            validation._external_style_audit(),
            (),
        ),
    )
    validation.main()
    assert json.loads(capsys.readouterr().out)["seed_set"] == "development"
