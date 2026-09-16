"""Synthetic-only interpretation for the selected weight-change experiment."""

import math
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

import numpy as np
from sklearn.inspection import permutation_importance

from fitadapt.ml.weight_change import (
    FEATURE_NAMES,
    WEIGHT_CHANGE_FEATURE_VERSION,
    WEIGHT_CHANGE_ML_POLICY_VERSION,
    WeightChangeMlConfig,
    _cohort_configurations,
    _metrics,
    _pipelines,
    _rows,
    _select_model,
    build_synthetic_weight_change_dataset,
)
from fitadapt.synthetic.history import generate_synthetic_history

WEIGHT_CHANGE_INTERPRETATION_POLICY_VERSION = "weight_change_interpretation_v1"
INTERPRETATION_ASSUMPTIONS = (
    "Coefficients and permutation importances are non-causal synthetic diagnostics.",
    "Permutation importance uses validation data; test data is reserved for residual diagnostics.",
    "Correlated features can divide or obscure permutation importance.",
    "Synthetic results are not clinical or real-world performance evidence.",
)


class WeightChangeInterpretationError(ValueError):
    """Raised when interpretation configuration violates its diagnostic contract."""


class WeightChangeDirection(StrEnum):
    LOSS = "loss"
    STABLE = "stable"
    GAIN = "gain"


@dataclass(frozen=True, slots=True)
class WeightChangeInterpretationConfig:
    permutation_repeats: int = 20
    random_seed: int = 2026
    stable_tolerance_kg: float = 0.05

    def __post_init__(self) -> None:
        for name, value, positive in (
            ("permutation_repeats", self.permutation_repeats, True),
            ("random_seed", self.random_seed, False),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or (value <= 0 if positive else value < 0)
            ):
                raise WeightChangeInterpretationError(
                    f"{name} must be a {'positive' if positive else 'non-negative'} integer."
                )
        value = self.stable_tolerance_kg
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise WeightChangeInterpretationError(
                "stable_tolerance_kg must be a finite non-negative number."
            )
        object.__setattr__(self, "stable_tolerance_kg", float(value))


@dataclass(frozen=True, slots=True)
class ExpandedFeatureCoefficient:
    feature_name: str
    coefficient: float
    absolute_coefficient: float
    rank: int
    feature_kind: str


@dataclass(frozen=True, slots=True)
class OriginalFeaturePermutationImportance:
    feature_name: str
    mean_increase_in_mae_kg: float
    standard_deviation_kg: float
    rank: int


@dataclass(frozen=True, slots=True)
class WeightChangePredictionRecord:
    cutoff_date: date
    target_date: date
    group_id: str
    actual_weight_change_kg: float
    predicted_weight_change_kg: float
    residual_kg: float
    absolute_error_kg: float
    direction: WeightChangeDirection


@dataclass(frozen=True, slots=True)
class WeightChangeResidualSummary:
    sample_count: int
    mean_absolute_error_kg: float | None
    root_mean_squared_error_kg: float | None
    mean_residual_kg: float | None
    median_residual_kg: float | None
    median_absolute_error_kg: float | None
    maximum_absolute_error_kg: float | None
    percentile_90_absolute_error_kg: float | None


@dataclass(frozen=True, slots=True)
class WeightChangeGroupDiagnostic:
    group_id: str
    sample_count: int
    mean_absolute_error_kg: float | None
    root_mean_squared_error_kg: float | None
    mean_residual_kg: float | None
    seed: int
    calorie_logging_bias_kcal: float
    scale_weight_noise_standard_deviation_kg: float
    calorie_logging_error_standard_deviation_kcal: float
    missing_weight_probability: float
    missing_nutrition_probability: float


@dataclass(frozen=True, slots=True)
class WeightChangeDirectionDiagnostic:
    direction: WeightChangeDirection
    sample_count: int
    mean_absolute_error_kg: float | None
    root_mean_squared_error_kg: float | None
    mean_residual_kg: float | None


@dataclass(frozen=True, slots=True)
class WeightChangeInterpretationResult:
    policy_version: str
    selected_model_name: str
    ml_policy_version: str
    feature_version: str
    coefficient_status: str
    coefficients: tuple[ExpandedFeatureCoefficient, ...]
    intercept: float | None
    permutation_importances: tuple[OriginalFeaturePermutationImportance, ...]
    prediction_records: tuple[WeightChangePredictionRecord, ...]
    residual_summary: WeightChangeResidualSummary
    group_diagnostics: tuple[WeightChangeGroupDiagnostic, ...]
    direction_diagnostics: tuple[WeightChangeDirectionDiagnostic, ...]
    assumptions: tuple[str, ...]


def run_weight_change_interpretation(
    config: WeightChangeInterpretationConfig | None = None,
) -> WeightChangeInterpretationResult:
    """Fit the existing deterministic experiment and return immutable diagnostics only."""
    effective = config if config is not None else WeightChangeInterpretationConfig()
    if not isinstance(effective, WeightChangeInterpretationConfig):
        raise WeightChangeInterpretationError(
            "config must be a WeightChangeInterpretationConfig or None."
        )
    cohort = _cohort_configurations()
    dataset = build_synthetic_weight_change_dataset(
        [generate_synthetic_history(item) for item in cohort]
    )
    groups = tuple(f"history_{index:02d}" for index in range(30))
    train_groups, validation_groups, test_groups = groups[:18], groups[18:24], groups[24:]
    train, validation, test = (
        _rows(dataset, item) for item in (train_groups, validation_groups, test_groups)
    )
    fitted, results = {}, []
    for name, pipeline, specification in _pipelines(WeightChangeMlConfig()):
        pipeline.fit(*train)
        fitted[name] = pipeline
        from fitadapt.ml.weight_change import WeightChangeModelResult

        results.append(
            WeightChangeModelResult(
                name, _metrics(validation[1], pipeline.predict(validation[0])), specification
            )
        )
    selected = _select_model(tuple(results))
    model = fitted[selected.name]
    predictions = model.predict(test[0])
    examples = tuple(item for item in dataset.examples if item.group_id in test_groups)
    records = tuple(
        _record(item, float(prediction), effective.stable_tolerance_kg)
        for item, prediction in zip(examples, predictions, strict=True)
    )
    imputer = model.named_steps["imputer"]
    transformed_names = tuple(imputer.get_feature_names_out(FEATURE_NAMES))
    estimator = model.named_steps["model"]
    coefficients = ()
    intercept = None
    if hasattr(estimator, "coef_"):
        coefficients = _coefficients(transformed_names, estimator.coef_)
        intercept = float(estimator.intercept_)
    importance = permutation_importance(
        model,
        validation[0],
        validation[1],
        scoring="neg_mean_absolute_error",
        n_repeats=effective.permutation_repeats,
        random_state=effective.random_seed,
    )
    permutation = _importance(importance.importances_mean, importance.importances_std)
    summary = _summary(records)
    group_diagnostics = tuple(
        _group(group_id, records, cohort[int(group_id[-2:])]) for group_id in test_groups
    )
    direction_diagnostics = tuple(
        _direction(direction, records) for direction in WeightChangeDirection
    )
    return WeightChangeInterpretationResult(
        WEIGHT_CHANGE_INTERPRETATION_POLICY_VERSION,
        selected.name,
        WEIGHT_CHANGE_ML_POLICY_VERSION,
        WEIGHT_CHANGE_FEATURE_VERSION,
        "available" if coefficients else "unavailable",
        coefficients,
        intercept,
        permutation,
        records,
        summary,
        group_diagnostics,
        direction_diagnostics,
        INTERPRETATION_ASSUMPTIONS,
    )


def _coefficients(
    names: tuple[str, ...], values: np.ndarray
) -> tuple[ExpandedFeatureCoefficient, ...]:
    ordered = sorted(enumerate(values), key=lambda item: (-abs(float(item[1])), item[0]))
    ranks = {index: rank + 1 for rank, (index, _) in enumerate(ordered)}
    return tuple(
        ExpandedFeatureCoefficient(
            name,
            float(value),
            abs(float(value)),
            ranks[index],
            "missingness_indicator"
            if name.startswith("missingindicator_")
            else "original_imputed_feature",
        )
        for index, (name, value) in enumerate(zip(names, values, strict=True))
    )


def _importance(
    means: np.ndarray, deviations: np.ndarray
) -> tuple[OriginalFeaturePermutationImportance, ...]:
    order = sorted(range(len(FEATURE_NAMES)), key=lambda index: (-float(means[index]), index))
    ranks = {index: rank + 1 for rank, index in enumerate(order)}
    return tuple(
        OriginalFeaturePermutationImportance(
            name, float(means[index]), float(deviations[index]), ranks[index]
        )
        for index, name in enumerate(FEATURE_NAMES)
    )


def _record(item: object, prediction: float, tolerance: float) -> WeightChangePredictionRecord:
    actual = float(item.target_weight_change_kg)
    direction = (
        WeightChangeDirection.LOSS
        if actual < -tolerance
        else WeightChangeDirection.GAIN
        if actual > tolerance
        else WeightChangeDirection.STABLE
    )
    residual = prediction - actual
    return WeightChangePredictionRecord(
        item.cutoff_date,
        item.target_date,
        item.group_id,
        actual,
        prediction,
        residual,
        abs(residual),
        direction,
    )


def _summary(records: tuple[WeightChangePredictionRecord, ...]) -> WeightChangeResidualSummary:
    if not records:
        raise WeightChangeInterpretationError("residual diagnostics require at least one record.")
    residuals = np.asarray([item.residual_kg for item in records])
    absolute = np.abs(residuals)
    metrics = _metrics(np.zeros(len(residuals)), residuals)
    return WeightChangeResidualSummary(
        len(records),
        metrics.mean_absolute_error_kg,
        metrics.root_mean_squared_error_kg,
        metrics.mean_error_kg,
        float(np.median(residuals)),
        float(np.median(absolute)),
        float(np.max(absolute)),
        float(np.percentile(absolute, 90, method="linear")),
    )


def _group(
    group_id: str, records: tuple[WeightChangePredictionRecord, ...], config: object
) -> WeightChangeGroupDiagnostic:
    items = tuple(item for item in records if item.group_id == group_id)
    summary = _summary(items)
    return WeightChangeGroupDiagnostic(
        group_id,
        summary.sample_count,
        summary.mean_absolute_error_kg,
        summary.root_mean_squared_error_kg,
        summary.mean_residual_kg,
        config.seed,
        config.calorie_logging_bias_kcal,
        config.scale_weight_noise_standard_deviation_kg,
        config.calorie_logging_error_standard_deviation_kcal,
        config.missing_weight_probability,
        config.missing_nutrition_probability,
    )


def _direction(
    direction: WeightChangeDirection, records: tuple[WeightChangePredictionRecord, ...]
) -> WeightChangeDirectionDiagnostic:
    items = tuple(item for item in records if item.direction is direction)
    if not items:
        return WeightChangeDirectionDiagnostic(direction, 0, None, None, None)
    summary = _summary(items)
    return WeightChangeDirectionDiagnostic(
        direction,
        summary.sample_count,
        summary.mean_absolute_error_kg,
        summary.root_mean_squared_error_kg,
        summary.mean_residual_kg,
    )
