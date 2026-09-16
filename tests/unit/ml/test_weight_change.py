"""Focused leakage-safety tests for the synthetic weight-change experiment."""

import math
from dataclasses import FrozenInstanceError, replace
from datetime import date, timedelta

import numpy as np
import pytest

from fitadapt.ml.weight_change import (
    FEATURE_NAMES,
    WeightChangeDataset,
    WeightChangeDatasetReport,
    WeightChangeExample,
    WeightChangeMlConfig,
    WeightChangeMlError,
    WeightChangeModelMetrics,
    WeightChangeModelResult,
    _cohort_configurations,
    _metrics,
    _pipelines,
    _select_model,
    build_synthetic_weight_change_dataset,
    run_weight_change_benchmark,
)
from fitadapt.synthetic.history import SyntheticHistoryConfig, generate_synthetic_history


def history() -> object:
    return generate_synthetic_history(
        SyntheticHistoryConfig(date(2026, 1, 1), 20, 1, 80.0, 2000.0, 2500.0)
    )


def test_config_and_dataset_validation() -> None:
    for value in (0, -1, True, 7.0, "7", None):
        with pytest.raises(WeightChangeMlError):
            WeightChangeMlConfig(forecast_horizon_days=value)  # type: ignore[arg-type]
    for field, values in (
        ("random_seed", (-1, True, 1.0, "1", None)),
        ("random_forest_estimators", (0, -1, True, 1.0, "1", None)),
        ("ridge_alpha", (-1, True, "1", None, math.nan, math.inf, -math.inf)),
    ):
        for value in values:
            with pytest.raises(WeightChangeMlError, match=field):
                WeightChangeMlConfig(**{field: value})  # type: ignore[arg-type]
    assert WeightChangeMlConfig(ridge_alpha=1).ridge_alpha == 1.0
    with pytest.raises(WeightChangeMlError):
        build_synthetic_weight_change_dataset([])
    with pytest.raises(WeightChangeMlError):
        build_synthetic_weight_change_dataset(["bad"])  # type: ignore[list-item]


def test_dataset_features_targets_and_report_are_date_aligned() -> None:
    source = history()
    dataset = build_synthetic_weight_change_dataset([source])  # type: ignore[list-item]
    truth = {item.truth.observed_on: item.truth.true_body_weight_kg for item in source.days}  # type: ignore[union-attr]

    assert dataset.feature_names == FEATURE_NAMES
    assert (
        dataset.report.produced_examples + dataset.report.dropped_missing_future_target
        == dataset.report.candidate_cutoff_dates
    )
    assert all(
        item.target_date == item.cutoff_date + timedelta(days=7) for item in dataset.examples
    )
    assert all(
        item.target_weight_change_kg
        == pytest.approx(truth[item.target_date] - truth[item.cutoff_date])
        for item in dataset.examples
    )
    assert all(
        "true_" not in name and "seed" not in name and "group" not in name
        for name in dataset.feature_names
    )
    assert all(len(item.feature_values) == len(FEATURE_NAMES) for item in dataset.examples)


def test_future_truth_or_observations_do_not_change_prior_features() -> None:
    source = history()
    first = build_synthetic_weight_change_dataset([source]).examples[2]  # type: ignore[list-item]

    def by_cutoff(dataset: object) -> object:
        return next(item for item in dataset.examples if item.cutoff_date == first.cutoff_date)

    future_index = next(
        index for index, day in enumerate(source.days) if day.truth.observed_on == first.target_date
    )  # type: ignore[union-attr]
    changed_truth = replace(
        source,
        days=(
            *source.days[:future_index],
            replace(
                source.days[future_index],
                truth=replace(
                    source.days[future_index].truth,
                    true_body_weight_kg=source.days[future_index].truth.true_body_weight_kg + 2.0,
                ),
            ),
            *source.days[future_index + 1 :],
        ),
    )  # type: ignore[union-attr]
    changed = by_cutoff(build_synthetic_weight_change_dataset([changed_truth]))
    assert first.feature_values == changed.feature_values
    assert changed.target_weight_change_kg == pytest.approx(first.target_weight_change_kg + 2.0)


def test_group_benchmark_has_disjoint_complete_partitions_and_train_only_pipelines() -> None:
    result = run_weight_change_benchmark()
    groups = (
        set(result.train_group_ids),
        set(result.validation_group_ids),
        set(result.test_group_ids),
    )

    assert [len(group) for group in groups] == [18, 6, 6]
    assert not groups[0] & groups[1] and not groups[0] & groups[2] and not groups[1] & groups[2]
    assert result.selected_model_name != "dummy"
    assert result.selected_model_test_metrics.sample_count > 0
    pipelines = _pipelines(WeightChangeMlConfig())
    assert "scaler" in pipelines[1][1].named_steps and "scaler" in pipelines[2][1].named_steps
    assert "scaler" not in pipelines[3][1].named_steps
    assert pipelines[3][1].named_steps["model"].random_state == 2026


def test_metrics_and_benchmark_results_are_plain_and_deterministic() -> None:
    metrics = _metrics(np.array([1.0, 2.0]), np.array([2.0, 0.0]))
    assert metrics.mean_absolute_error_kg == pytest.approx(1.5)
    assert metrics.root_mean_squared_error_kg == pytest.approx(math.sqrt(2.5))
    assert metrics.mean_error_kg == pytest.approx(-0.5)
    assert metrics.r_squared is not None
    assert run_weight_change_benchmark() == run_weight_change_benchmark()


def test_train_only_imputation_selection_and_public_immutability() -> None:
    pipeline = _pipelines(WeightChangeMlConfig(ridge_alpha=2.0, random_forest_estimators=9))[1][1]
    pipeline.named_steps["imputer"].fit(np.array([[1.0, np.nan], [3.0, np.nan]]))
    imputer = pipeline.named_steps["imputer"]
    assert imputer.statistics_[0] == 2.0
    assert imputer.transform(np.array([[np.nan, 99.0]])).shape[1] == 3
    assert imputer.statistics_[0] == 2.0
    pipes = _pipelines(WeightChangeMlConfig(ridge_alpha=2.0, random_forest_estimators=9))
    assert pipes[2][1].named_steps["model"].alpha == 2.0
    assert pipes[3][1].named_steps["model"].n_estimators == 9
    results = (
        WeightChangeModelResult("dummy", WeightChangeModelMetrics(1, 0.0, 0.0, 0.0, None), ""),
        WeightChangeModelResult("linear", WeightChangeModelMetrics(1, 2.0, 0.0, 0.0, None), ""),
        WeightChangeModelResult("ridge", WeightChangeModelMetrics(1, 1.0, 0.0, 0.0, None), ""),
        WeightChangeModelResult(
            "random_forest", WeightChangeModelMetrics(1, 1.0, 0.0, 0.0, None), ""
        ),
    )
    assert _select_model(results).name == "ridge"
    benchmark = run_weight_change_benchmark()
    with pytest.raises(FrozenInstanceError):
        benchmark.selected_model_name = "dummy"  # type: ignore[misc]
    assert isinstance(benchmark.train_group_ids, tuple)


def test_future_observation_after_cutoff_cannot_change_selected_example() -> None:
    source = history()
    original = build_synthetic_weight_change_dataset([source])  # type: ignore[list-item]
    selected = original.examples[2]
    index = next(
        i for i, day in enumerate(source.days) if day.truth.observed_on > selected.cutoff_date
    )  # type: ignore[union-attr]
    changed_day = replace(source.days[index], observation=None)  # type: ignore[union-attr]
    changed_source = replace(
        source, days=(*source.days[:index], changed_day, *source.days[index + 1 :])
    )  # type: ignore[union-attr]
    changed = next(
        item
        for item in build_synthetic_weight_change_dataset([changed_source]).examples
        if item.cutoff_date == selected.cutoff_date
    )
    assert changed.feature_values == selected.feature_values
    assert changed.target_weight_change_kg == selected.target_weight_change_kg


def test_unrelated_truth_after_target_cannot_change_selected_example() -> None:
    source = history()
    selected = build_synthetic_weight_change_dataset([source]).examples[2]  # type: ignore[list-item]
    index = next(
        i for i, day in enumerate(source.days) if day.truth.observed_on > selected.target_date
    )  # type: ignore[union-attr]
    changed_day = replace(
        source.days[index], truth=replace(source.days[index].truth, true_body_weight_kg=999.0)
    )  # type: ignore[union-attr]
    changed_source = replace(
        source, days=(*source.days[:index], changed_day, *source.days[index + 1 :])
    )  # type: ignore[union-attr]
    changed = next(
        item
        for item in build_synthetic_weight_change_dataset([changed_source]).examples
        if item.cutoff_date == selected.cutoff_date
    )
    assert changed.feature_values == selected.feature_values
    assert changed.target_weight_change_kg == selected.target_weight_change_kg


def test_selection_helper_contracts() -> None:
    def result(name: str, mae: object) -> WeightChangeModelResult:
        return WeightChangeModelResult(name, WeightChangeModelMetrics(2, mae, 1.0, 0.0, None), "")  # type: ignore[arg-type]

    assert (
        _select_model((result("dummy", 0.0), result("linear", 2.0), result("ridge", 1.0))).name
        == "ridge"
    )
    assert _select_model((result("linear", 1.0), result("ridge", 1.0))).name == "linear"
    for candidates in (
        (),
        (result("dummy", 0.0),),
        (result("linear", None),),
        (result("linear", math.nan),),
        (result("linear", math.inf),),
    ):
        with pytest.raises(WeightChangeMlError):
            _select_model(candidates)


def test_complete_group_assignment_and_end_to_end_selection_metrics() -> None:
    benchmark = run_weight_change_benchmark()
    dataset = build_synthetic_weight_change_dataset(
        [generate_synthetic_history(config) for config in _cohort_configurations()]
    )
    groups = (
        set(benchmark.train_group_ids),
        set(benchmark.validation_group_ids),
        set(benchmark.test_group_ids),
    )
    assert set(example.group_id for example in dataset.examples) == set().union(*groups)
    assert all(
        sum(example.group_id in group for group in groups) == 1 for example in dataset.examples
    )
    assert [item.name for item in benchmark.validation_results] == [
        "dummy",
        "linear",
        "ridge",
        "random_forest",
    ]
    maes = [item.validation_metrics.mean_absolute_error_kg for item in benchmark.validation_results]
    assert all(value is not None and math.isfinite(value) for value in maes)
    selected_mae = next(
        item.validation_metrics.mean_absolute_error_kg
        for item in benchmark.validation_results
        if item.name == benchmark.selected_model_name
    )
    assert selected_mae == min(maes[1:]) and selected_mae < maes[0]
    assert all(
        math.isfinite(value)
        for value in (
            benchmark.selected_model_test_metrics.mean_absolute_error_kg,
            benchmark.dummy_test_metrics.mean_absolute_error_kg,
        )
    )


def test_metric_edge_cases_and_no_signal_non_dummy_can_lose() -> None:
    assert _metrics(np.array([1.0]), np.array([2.0])).r_squared is None
    assert _metrics(np.array([1.0, 1.0]), np.array([2.0, 0.0])).r_squared is None
    for truth, predictions in (
        (np.array([]), np.array([])),
        (np.array([1.0]), np.array([1.0, 2.0])),
    ):
        with pytest.raises(WeightChangeMlError):
            _metrics(truth, predictions)
    train_x, train_y = np.zeros((4, 2)), np.array([0.0, 1.0, 0.0, 1.0])
    test_x, test_y = np.zeros((2, 2)), np.array([0.0, 1.0])
    dummy, linear = _pipelines(WeightChangeMlConfig())[:2]
    dummy[1].fit(train_x, train_y)
    linear[1].fit(train_x, train_y)
    assert (
        _metrics(test_y, linear[1].predict(test_x)).mean_absolute_error_kg
        >= _metrics(test_y, dummy[1].predict(test_x)).mean_absolute_error_kg
    )


def test_every_public_model_is_frozen_and_collections_are_tuples() -> None:
    example = WeightChangeExample(date.today(), date.today(), "g", (None,), 0.0)
    report = WeightChangeDatasetReport(1, 1, 1, 0, 0, 7, "v", "target")
    dataset = WeightChangeDataset((example,), ("feature",), report)
    metric = WeightChangeModelMetrics(1, 1.0, 1.0, 0.0, None)
    model = WeightChangeModelResult("linear", metric, "spec")
    benchmark = run_weight_change_benchmark()
    for item, field, value in (
        (WeightChangeMlConfig(), "random_seed", 1),
        (example, "group_id", "x"),
        (report, "produced_examples", 0),
        (dataset, "examples", ()),
        (metric, "sample_count", 0),
        (model, "name", "x"),
        (benchmark, "selected_model_name", "x"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(item, field, value)
    with pytest.raises(AttributeError):
        dataset.examples.append(example)  # type: ignore[attr-defined]
