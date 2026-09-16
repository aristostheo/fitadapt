"""Tests for reproducible, date-aligned synthetic TDEE evaluation."""

import math
from dataclasses import FrozenInstanceError, astuple, replace
from datetime import date

import pytest

from fitadapt.adaptive.tdee import AdaptiveTdeeConfig
from fitadapt.analysis.trends import TrendAnalysisConfig
from fitadapt.domain.profile import (
    ActivityLevel,
    Goal,
    SexForMifflinEquation,
    UserProfile,
)
from fitadapt.evaluation.tdee import (
    TDEE_BENCHMARK_SCENARIOS,
    TdeeEvaluationError,
    calculate_tdee_error_metrics,
    evaluate_tdee_estimators,
    run_tdee_benchmark_suite,
)
from fitadapt.synthetic.history import SyntheticHistoryConfig, generate_synthetic_history


def profile() -> UserProfile:
    return UserProfile(
        age_years=30,
        height_cm=180.0,
        weight_kg=80.0,
        sex_for_mifflin_equation=SexForMifflinEquation.MALE,
        activity_level=ActivityLevel.MODERATELY_ACTIVE,
        goal=Goal.MAINTAIN,
        requested_weekly_change_kg=0.0,
    )


def history_config(**overrides: object) -> SyntheticHistoryConfig:
    values: dict[str, object] = {
        "start_date": date(2026, 1, 1),
        "days": 30,
        "seed": 19,
        "initial_true_weight_kg": 80.0,
        "base_daily_expenditure_kcal": 2000.0,
        "average_energy_intake_kcal": 2500.0,
        "average_steps": 1000.0,
        "intake_standard_deviation_kcal": 0.0,
        "steps_standard_deviation": 0.0,
        "strength_training_probability": 0.0,
        "cardio_probability": 0.0,
        "scale_weight_noise_standard_deviation_kg": 0.0,
        "calorie_logging_error_standard_deviation_kcal": 0.0,
        "steps_observation_noise_standard_deviation": 0.0,
        "missing_weight_probability": 0.0,
        "missing_nutrition_probability": 0.0,
        "missing_activity_probability": 0.0,
    }
    values.update(overrides)
    return SyntheticHistoryConfig(**values)  # type: ignore[arg-type]


def test_metrics_use_manual_mae_rmse_and_prediction_minus_truth_mean_error() -> None:
    metrics = calculate_tdee_error_metrics([100.0, 200.0], [90.0, 220.0])

    assert metrics.sample_count == 2
    assert metrics.mean_absolute_error_kcal_per_day == pytest.approx(15.0)
    assert metrics.root_mean_squared_error_kcal_per_day == pytest.approx(math.sqrt(250.0))
    assert metrics.mean_error_kcal_per_day == pytest.approx(-5.0)


def test_empty_metrics_are_explicitly_missing_not_zero() -> None:
    assert calculate_tdee_error_metrics([], []).sample_count == 0
    assert calculate_tdee_error_metrics([], []).mean_absolute_error_kcal_per_day is None
    assert calculate_tdee_error_metrics([], []).root_mean_squared_error_kcal_per_day is None
    assert calculate_tdee_error_metrics([], []).mean_error_kcal_per_day is None


def test_metrics_reject_mismatched_lengths_non_finite_and_boolean_values() -> None:
    with pytest.raises(TdeeEvaluationError, match="equal lengths"):
        calculate_tdee_error_metrics([1.0], [])
    for bad_value in (math.nan, math.inf, -math.inf, True):
        with pytest.raises(TdeeEvaluationError, match="finite non-boolean"):
            calculate_tdee_error_metrics([bad_value], [1.0])  # type: ignore[list-item]


def test_evaluation_uses_static_baseline_for_all_days_and_pairs_adaptive_dates() -> None:
    history = generate_synthetic_history(history_config())
    result = evaluate_tdee_estimators(profile(), history)

    assert result.baseline_all_days_metrics.sample_count == len(history.days)
    assert (
        result.paired_baseline_metrics.sample_count == result.paired_adaptive_metrics.sample_count
    )
    assert result.paired_evaluated_dates == result.adaptive_eligible_dates
    assert result.baseline_estimate.estimated_tdee_kcal_per_day == pytest.approx(2759.0)
    assert result.baseline_all_days_metrics.mean_error_kcal_per_day == pytest.approx(719.0)
    assert result.paired_baseline_metrics.mean_error_kcal_per_day == pytest.approx(719.0)
    assert result.adaptive_coverage_ratio == pytest.approx(20 / 30)
    assert result.adaptive_coverage_after_warmup_ratio == pytest.approx(1.0)


def test_truth_is_matched_by_date_not_day_tuple_position() -> None:
    original = generate_synthetic_history(history_config())
    reversed_history = replace(original, days=tuple(reversed(original.days)))

    assert evaluate_tdee_estimators(profile(), original) == evaluate_tdee_estimators(
        profile(), reversed_history
    )


def test_entirely_missing_observations_return_empty_paired_metrics() -> None:
    history = generate_synthetic_history(
        history_config(
            missing_weight_probability=1.0,
            missing_nutrition_probability=1.0,
            missing_activity_probability=1.0,
        )
    )
    result = evaluate_tdee_estimators(profile(), history)

    assert result.days_with_observations == 0
    assert result.adaptive_eligible_dates == ()
    assert result.paired_baseline_metrics.sample_count == 0
    assert result.paired_adaptive_metrics.mean_absolute_error_kcal_per_day is None
    assert result.adaptive_coverage_ratio == 0.0


def test_zero_baseline_paired_mae_makes_percentage_improvement_undefined() -> None:
    history = generate_synthetic_history(history_config(base_daily_expenditure_kcal=2719.0))
    result = evaluate_tdee_estimators(profile(), history)

    assert result.paired_baseline_metrics.mean_absolute_error_kcal_per_day == 0.0
    assert result.percentage_mae_improvement is None


def test_clean_and_baseline_mismatch_scenarios_show_controlled_adaptive_improvement() -> None:
    suite = run_tdee_benchmark_suite()
    results = {item.scenario.name: item.evaluation for item in suite.scenario_results}
    clean_scenario = next(
        item.scenario
        for item in suite.scenario_results
        if item.scenario.name == "clean_constant_expenditure"
    )
    clean_history = generate_synthetic_history(clean_scenario.synthetic_config)
    known_clean_expenditure_kcal_per_day = 2000.0 + 1000.0 * 0.04

    assert all(
        day.truth.true_daily_energy_expenditure_kcal
        == pytest.approx(known_clean_expenditure_kcal_per_day)
        for day in clean_history.days
    )
    assert results[
        "clean_constant_expenditure"
    ].paired_adaptive_metrics.mean_absolute_error_kcal_per_day == pytest.approx(0.0, abs=1e-9)
    assert results["clean_constant_expenditure"].percentage_mae_improvement > 0.0
    assert results["baseline_mismatch"].percentage_mae_improvement > 0.0


def test_logging_bias_scenarios_shift_adaptive_error_in_the_expected_direction() -> None:
    suite = run_tdee_benchmark_suite()
    results = {item.scenario.name: item.evaluation for item in suite.scenario_results}

    assert results["calorie_underreporting"].paired_adaptive_metrics.mean_error_kcal_per_day < 0.0
    assert results["calorie_overreporting"].paired_adaptive_metrics.mean_error_kcal_per_day > 0.0


def test_noisy_scenario_has_finite_metrics_and_missing_data_lowers_coverage() -> None:
    suite = run_tdee_benchmark_suite()
    results = {item.scenario.name: item.evaluation for item in suite.scenario_results}
    missing_scenario = next(
        item.scenario for item in suite.scenario_results if item.scenario.name == "missing_data"
    )
    complete_data_evaluation = evaluate_tdee_estimators(
        missing_scenario.profile,
        generate_synthetic_history(
            replace(
                missing_scenario.synthetic_config,
                missing_weight_probability=0.0,
                missing_nutrition_probability=0.0,
                missing_activity_probability=0.0,
            )
        ),
        missing_scenario.trend_config,
        missing_scenario.adaptive_config,
    )

    noisy_metrics = results["noisy_observations"].paired_adaptive_metrics
    assert math.isfinite(noisy_metrics.mean_absolute_error_kcal_per_day)
    assert math.isfinite(noisy_metrics.root_mean_squared_error_kcal_per_day)
    assert (
        results["missing_data"].adaptive_coverage_ratio
        <= complete_data_evaluation.adaptive_coverage_ratio
    )


def test_biased_scenario_can_make_adaptive_worse_than_static_baseline() -> None:
    suite = run_tdee_benchmark_suite()
    results = {item.scenario.name: item.evaluation for item in suite.scenario_results}

    assert results["calorie_overreporting"].percentage_mae_improvement < 0.0


def test_benchmark_definitions_are_unique_ordered_and_reproducible_with_provenance() -> None:
    first = run_tdee_benchmark_suite()
    second = run_tdee_benchmark_suite()

    assert first == second
    assert [item.scenario.name for item in first.scenario_results] == [
        "clean_constant_expenditure",
        "noisy_observations",
        "missing_data",
        "calorie_underreporting",
        "calorie_overreporting",
        "baseline_mismatch",
    ]
    assert len({item.name for item in TDEE_BENCHMARK_SCENARIOS}) == len(TDEE_BENCHMARK_SCENARIOS)
    assert all(item.scenario.synthetic_config.seed >= 0 for item in first.scenario_results)
    assert all(
        item.evaluation.policy_version == "tdee_evaluation_v1" for item in first.scenario_results
    )
    assert all(
        item.evaluation.trend_policy_version == "calendar_trends_v1"
        for item in first.scenario_results
    )
    assert all(
        item.evaluation.adaptive_policy_version == "adaptive_tdee_v1"
        for item in first.scenario_results
    )


def test_public_models_are_immutable_and_values_are_plain_python_types() -> None:
    result = evaluate_tdee_estimators(profile(), generate_synthetic_history(history_config()))
    suite = run_tdee_benchmark_suite()

    assert type(result.adaptive_eligible_dates[0]) is date
    assert type(result.adaptive_coverage_ratio) is float
    assert type(result.total_synthetic_days) is int
    assert result.percentage_mae_improvement is not None
    with pytest.raises(FrozenInstanceError):
        result.total_synthetic_days = 0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.paired_adaptive_metrics.sample_count = 0  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result.adaptive_eligible_dates.append(date.today())  # type: ignore[attr-defined]
    with pytest.raises(FrozenInstanceError):
        suite.scenario_results[0].evaluation = result  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        suite.scenario_results[0].scenario.name = "changed"  # type: ignore[misc]


def test_evaluation_does_not_mutate_inputs_and_rejects_invalid_types() -> None:
    source_profile = profile()
    source_history = generate_synthetic_history(history_config())
    trend_config = TrendAnalysisConfig()
    adaptive_config = AdaptiveTdeeConfig()
    snapshot = (
        astuple(source_profile),
        astuple(source_history),
        astuple(trend_config),
        astuple(adaptive_config),
    )

    evaluate_tdee_estimators(source_profile, source_history, trend_config, adaptive_config)

    assert snapshot == (
        astuple(source_profile),
        astuple(source_history),
        astuple(trend_config),
        astuple(adaptive_config),
    )
    with pytest.raises(TdeeEvaluationError, match="profile"):
        evaluate_tdee_estimators("profile", source_history)  # type: ignore[arg-type]
    with pytest.raises(TdeeEvaluationError, match="history"):
        evaluate_tdee_estimators(source_profile, "history")  # type: ignore[arg-type]
    with pytest.raises(TdeeEvaluationError, match="trend_config"):
        evaluate_tdee_estimators(source_profile, source_history, "trend")  # type: ignore[arg-type]
    with pytest.raises(TdeeEvaluationError, match="adaptive_config"):
        evaluate_tdee_estimators(source_profile, source_history, None, "adaptive")  # type: ignore[arg-type]


def test_malformed_empty_duplicate_and_non_finite_truth_are_rejected() -> None:
    history = generate_synthetic_history(history_config())
    empty = replace(history, days=())
    duplicate = replace(
        history,
        days=(
            history.days[0],
            replace(
                history.days[1],
                truth=replace(history.days[1].truth, observed_on=history.days[0].truth.observed_on),
            ),
            *history.days[2:],
        ),
    )
    non_finite = replace(
        history,
        days=(
            replace(
                history.days[0],
                truth=replace(history.days[0].truth, true_daily_energy_expenditure_kcal=math.inf),
            ),
            *history.days[1:],
        ),
    )

    for malformed in (empty, duplicate, non_finite):
        with pytest.raises(TdeeEvaluationError):
            evaluate_tdee_estimators(profile(), malformed)


def test_adaptive_dates_missing_from_truth_are_rejected() -> None:
    history = generate_synthetic_history(history_config())
    mismatched = replace(
        history,
        days=(
            *history.days[:20],
            replace(
                history.days[20],
                truth=replace(history.days[20].truth, observed_on=date(2025, 12, 1)),
            ),
            *history.days[21:],
        ),
    )

    with pytest.raises(TdeeEvaluationError, match="missing from synthetic truth"):
        evaluate_tdee_estimators(profile(), mismatched)


def test_scenario_input_validation_rejects_non_scenarios_and_duplicate_names() -> None:
    scenario = TDEE_BENCHMARK_SCENARIOS[0]
    duplicate = replace(scenario, description="duplicate")

    with pytest.raises(TdeeEvaluationError, match="TdeeBenchmarkScenario"):
        run_tdee_benchmark_suite(["bad"])  # type: ignore[list-item]
    with pytest.raises(TdeeEvaluationError, match="unique"):
        run_tdee_benchmark_suite([scenario, duplicate])
