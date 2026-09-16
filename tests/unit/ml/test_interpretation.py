"""Tests for immutable synthetic model diagnostics."""

import math
from dataclasses import FrozenInstanceError
from datetime import date

import numpy as np
import pytest
from sklearn.inspection import permutation_importance

from fitadapt.ml.interpretation import (
    WeightChangeDirection,
    WeightChangeInterpretationConfig,
    WeightChangeInterpretationError,
    WeightChangeInterpretationResult,
    WeightChangePredictionRecord,
    _coefficients,
    _direction,
    _importance,
    _record,
    _summary,
    run_weight_change_interpretation,
)
from fitadapt.ml.weight_change import (
    FEATURE_NAMES,
    WeightChangeMlConfig,
    WeightChangeModelResult,
    _cohort_configurations,
    _metrics,
    _pipelines,
    _rows,
    _select_model,
    build_synthetic_weight_change_dataset,
    run_weight_change_benchmark,
)
from fitadapt.synthetic.history import generate_synthetic_history


@pytest.fixture(scope="module")
def interpretation_result() -> WeightChangeInterpretationResult:
    return run_weight_change_interpretation()


@pytest.fixture(scope="module")
def fitted_context() -> tuple[object, object, object, object, object]:
    cohort = _cohort_configurations()
    dataset = build_synthetic_weight_change_dataset(
        [generate_synthetic_history(config) for config in cohort]
    )
    groups = tuple(f"history_{index:02d}" for index in range(30))
    train, validation, test = (
        _rows(dataset, group_set) for group_set in (groups[:18], groups[18:24], groups[24:])
    )
    fitted, results = {}, []
    for name, pipeline, specification in _pipelines(WeightChangeMlConfig()):
        pipeline.fit(*train)
        fitted[name] = pipeline
        results.append(
            WeightChangeModelResult(
                name, _metrics(validation[1], pipeline.predict(validation[0])), specification
            )
        )
    selected = _select_model(tuple(results))
    return fitted[selected.name], validation, test, cohort, selected


def test_config_validation_and_direction_boundaries() -> None:
    for value in (0, -1, True, 1.0, "1", None):
        with pytest.raises(WeightChangeInterpretationError):
            WeightChangeInterpretationConfig(permutation_repeats=value)  # type: ignore[arg-type]
    assert WeightChangeInterpretationConfig(stable_tolerance_kg=1).stable_tolerance_kg == 1.0


def test_random_seed_and_tolerance_validation_are_strict() -> None:
    for value in (-1, True, 1.0, "1", None):
        with pytest.raises(WeightChangeInterpretationError, match="random_seed"):
            WeightChangeInterpretationConfig(random_seed=value)  # type: ignore[arg-type]
    for value in (-1, True, "1", None, math.nan, math.inf, -math.inf):
        with pytest.raises(WeightChangeInterpretationError, match="stable_tolerance_kg"):
            WeightChangeInterpretationConfig(stable_tolerance_kg=value)  # type: ignore[arg-type]
    assert (
        type(WeightChangeInterpretationConfig(stable_tolerance_kg=2).stable_tolerance_kg) is float
    )


def test_interpretation_matches_benchmark_and_is_immutable() -> None:
    result = run_weight_change_interpretation()
    benchmark = run_weight_change_benchmark()
    assert result.selected_model_name == benchmark.selected_model_name == "linear"
    assert result.residual_summary.mean_absolute_error_kg == pytest.approx(
        benchmark.selected_model_test_metrics.mean_absolute_error_kg
    )
    assert len(result.prediction_records) == benchmark.selected_model_test_metrics.sample_count
    assert len(result.permutation_importances) == 8
    assert len(result.coefficients) == 13
    assert all(
        isinstance(item.coefficient, float) and math.isfinite(item.coefficient)
        for item in result.coefficients
    )
    assert [item.direction for item in result.direction_diagnostics] == list(WeightChangeDirection)
    with pytest.raises(FrozenInstanceError):
        result.selected_model_name = "dummy"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result.coefficients.append(result.coefficients[0])  # type: ignore[attr-defined]


def test_interpretation_is_deterministic_and_group_counts_reconcile() -> None:
    first = run_weight_change_interpretation()
    assert first == run_weight_change_interpretation()
    assert (
        sum(item.sample_count for item in first.group_diagnostics)
        == first.residual_summary.sample_count
    )
    assert (
        sum(item.sample_count for item in first.direction_diagnostics)
        == first.residual_summary.sample_count
    )


def test_coefficient_and_importance_ranks_use_declared_order_for_ties() -> None:
    coefficients = _coefficients(
        ("weight", "missingindicator_weight", "intake"), np.array([2.0, -2.0, -1.0])
    )
    assert [item.feature_kind for item in coefficients] == [
        "original_imputed_feature",
        "missingness_indicator",
        "original_imputed_feature",
    ]
    assert [item.rank for item in coefficients] == [1, 2, 3]
    assert [item.absolute_coefficient for item in coefficients] == [2.0, 2.0, 1.0]
    importance = _importance(np.zeros(len(FEATURE_NAMES)), np.ones(len(FEATURE_NAMES)))
    assert [item.feature_name for item in importance] == list(FEATURE_NAMES)
    assert [item.rank for item in importance] == list(range(1, 9))


def test_residual_summary_uses_linear_percentile_and_rejects_empty_records() -> None:
    records = tuple(
        WeightChangePredictionRecord(
            date(2026, 1, 1),
            date(2026, 1, 8),
            "g",
            0.0,
            residual,
            residual,
            abs(residual),
            WeightChangeDirection.STABLE,
        )
        for residual in (-2.0, 0.0, 4.0)
    )
    summary = _summary(records)
    assert summary.mean_absolute_error_kg == pytest.approx(2.0)
    assert summary.root_mean_squared_error_kg == pytest.approx(np.sqrt(20 / 3))
    assert summary.mean_residual_kg == pytest.approx(2 / 3)
    assert summary.median_residual_kg == 0.0
    assert summary.median_absolute_error_kg == 2.0
    assert summary.maximum_absolute_error_kg == 4.0
    assert summary.percentile_90_absolute_error_kg == pytest.approx(3.6)
    with pytest.raises(WeightChangeInterpretationError, match="at least one"):
        _summary(())


def test_direction_boundaries_and_empty_category_contract() -> None:
    class Item:
        cutoff_date = date(2026, 1, 1)
        target_date = date(2026, 1, 8)
        group_id = "g"

        def __init__(self, target: float) -> None:
            self.target_weight_change_kg = target

    records = tuple(_record(Item(value), value, 0.05) for value in (-0.05, 0.0, 0.05))
    assert all(item.direction is WeightChangeDirection.STABLE for item in records)
    empty = _direction(WeightChangeDirection.LOSS, records)
    assert (empty.sample_count, empty.mean_absolute_error_kg) == (0, None)


def test_held_out_records_are_test_only_and_group_provenance_matches() -> None:
    result = run_weight_change_interpretation()
    benchmark = run_weight_change_benchmark()
    test_groups = {f"history_{index:02d}" for index in range(24, 30)}
    assert all(
        item.group_id in test_groups and item.target_date > item.cutoff_date
        for item in result.prediction_records
    )
    assert [item.group_id for item in result.group_diagnostics] == sorted(test_groups)
    assert result.residual_summary.root_mean_squared_error_kg == pytest.approx(
        benchmark.selected_model_test_metrics.root_mean_squared_error_kg
    )


def test_public_records_groups_and_directions_reconcile(interpretation_result: object) -> None:
    result = interpretation_result
    for record in result.prediction_records:
        assert record.residual_kg == pytest.approx(
            record.predicted_weight_change_kg - record.actual_weight_change_kg
        )
        assert record.absolute_error_kg == pytest.approx(abs(record.residual_kg))
        assert type(record.cutoff_date) is date and type(record.group_id) is str
    for group in result.group_diagnostics:
        records = [item for item in result.prediction_records if item.group_id == group.group_id]
        assert group.sample_count == len(records)
        assert group.mean_absolute_error_kg == pytest.approx(
            sum(item.absolute_error_kg for item in records) / len(records)
        )
    for direction in result.direction_diagnostics:
        records = [
            item for item in result.prediction_records if item.direction is direction.direction
        ]
        assert direction.sample_count == len(records)
        if records:
            assert direction.mean_residual_kg == pytest.approx(
                sum(item.residual_kg for item in records) / len(records)
            )


def test_public_result_contains_only_immutable_plain_values(interpretation_result: object) -> None:
    result = interpretation_result
    for value in (
        result.coefficients,
        result.permutation_importances,
        result.prediction_records,
        result.group_diagnostics,
        result.direction_diagnostics,
    ):
        assert isinstance(value, tuple)
        with pytest.raises(AttributeError):
            value.append(None)  # type: ignore[attr-defined]
    assert not any(
        "Pipeline" in type(getattr(result, field)).__name__
        or "ndarray" in type(getattr(result, field)).__name__
        for field in result.__dataclass_fields__
    )


def test_reported_coefficients_reconstruct_selected_pipeline_prediction(
    interpretation_result: WeightChangeInterpretationResult,
    fitted_context: tuple[object, object, object, object, object],
) -> None:
    pipeline, validation, _, _, _ = fitted_context
    transformed = pipeline.named_steps["scaler"].transform(
        pipeline.named_steps["imputer"].transform(validation[0][:1])
    )
    coefficients = np.array([item.coefficient for item in interpretation_result.coefficients])
    reconstructed = float((transformed @ coefficients + interpretation_result.intercept)[0])
    assert reconstructed == pytest.approx(float(pipeline.predict(validation[0][:1])[0]))


def test_reported_coefficients_match_fitted_transformed_identity(
    interpretation_result: WeightChangeInterpretationResult,
    fitted_context: tuple[object, object, object, object, object],
) -> None:
    pipeline, _, _, _, _ = fitted_context
    imputer, model = pipeline.named_steps["imputer"], pipeline.named_steps["model"]
    assert [item.feature_name for item in interpretation_result.coefficients] == list(
        imputer.get_feature_names_out(FEATURE_NAMES)
    )
    assert [item.coefficient for item in interpretation_result.coefficients] == pytest.approx(
        model.coef_
    )
    assert interpretation_result.intercept == pytest.approx(model.intercept_)


def test_public_permutation_importance_matches_independent_validation_calculation(
    interpretation_result: WeightChangeInterpretationResult,
    fitted_context: tuple[object, object, object, object, object],
) -> None:
    pipeline, validation, _, _, _ = fitted_context
    expected = permutation_importance(
        pipeline,
        validation[0],
        validation[1],
        scoring="neg_mean_absolute_error",
        n_repeats=20,
        random_state=2026,
    )
    assert [
        item.mean_increase_in_mae_kg for item in interpretation_result.permutation_importances
    ] == pytest.approx(expected.importances_mean)
    assert [
        item.standard_deviation_kg for item in interpretation_result.permutation_importances
    ] == pytest.approx(expected.importances_std)


def test_group_diagnostic_provenance_uses_exact_group_identifier(
    interpretation_result: WeightChangeInterpretationResult,
    fitted_context: tuple[object, object, object, object, object],
) -> None:
    _, _, _, cohort, _ = fitted_context
    for diagnostic in interpretation_result.group_diagnostics:
        config = cohort[int(diagnostic.group_id.removeprefix("history_"))]
        assert (
            diagnostic.seed,
            diagnostic.calorie_logging_bias_kcal,
            diagnostic.scale_weight_noise_standard_deviation_kg,
            diagnostic.calorie_logging_error_standard_deviation_kcal,
            diagnostic.missing_weight_probability,
            diagnostic.missing_nutrition_probability,
        ) == pytest.approx(
            (
                config.seed,
                config.calorie_logging_bias_kcal,
                config.scale_weight_noise_standard_deviation_kg,
                config.calorie_logging_error_standard_deviation_kcal,
                config.missing_weight_probability,
                config.missing_nutrition_probability,
            )
        )
