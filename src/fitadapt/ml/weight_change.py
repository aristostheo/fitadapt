"""Leakage-safe synthetic experiment for seven-day future weight change."""

import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from fitadapt.adaptive.tdee import AdaptiveTdeeConfig, TdeeEligibility, estimate_adaptive_tdee
from fitadapt.analysis.trends import TrendAnalysisConfig, analyze_observation_trends
from fitadapt.synthetic.history import (
    SyntheticDay,
    SyntheticHistory,
    SyntheticHistoryConfig,
    generate_synthetic_history,
)

WEIGHT_CHANGE_ML_POLICY_VERSION = "weight_change_ml_v1"
WEIGHT_CHANGE_FEATURE_VERSION = "observation_trends_adaptive_v1"
FEATURE_NAMES = (
    "trailing_body_weight_mean_kg",
    "trailing_energy_intake_mean_kcal",
    "trailing_steps_mean",
    "window_weight_change_kg",
    "body_weight_contributor_count",
    "energy_intake_contributor_count",
    "steps_contributor_count",
    "adaptive_tdee_kcal_per_day",
)
ASSUMPTIONS = (
    "Features use only observation-derived trend and adaptive outputs at or before each cutoff.",
    "Synthetic hidden truth supplies only future labels and evaluation targets.",
    "Rows are split by complete synthetic-history groups, never randomly by row.",
    "Synthetic benchmark performance is not real-world or clinical evidence.",
)


class WeightChangeMlError(ValueError):
    """Raised when the experiment contract cannot be satisfied."""


@dataclass(frozen=True, slots=True)
class WeightChangeMlConfig:
    forecast_horizon_days: int = 7
    random_seed: int = 2026
    ridge_alpha: float = 1.0
    random_forest_estimators: int = 80

    def __post_init__(self) -> None:
        if (
            isinstance(self.forecast_horizon_days, bool)
            or not isinstance(self.forecast_horizon_days, int)
            or self.forecast_horizon_days <= 0
        ):
            raise WeightChangeMlError("forecast_horizon_days must be a positive integer.")
        if (
            isinstance(self.random_seed, bool)
            or not isinstance(self.random_seed, int)
            or self.random_seed < 0
        ):
            raise WeightChangeMlError("random_seed must be a non-negative integer.")
        if (
            isinstance(self.ridge_alpha, bool)
            or not isinstance(self.ridge_alpha, (int, float))
            or not math.isfinite(self.ridge_alpha)
            or self.ridge_alpha < 0
        ):
            raise WeightChangeMlError("ridge_alpha must be a finite non-negative number.")
        if (
            isinstance(self.random_forest_estimators, bool)
            or not isinstance(self.random_forest_estimators, int)
            or self.random_forest_estimators <= 0
        ):
            raise WeightChangeMlError("random_forest_estimators must be a positive integer.")
        object.__setattr__(self, "ridge_alpha", float(self.ridge_alpha))


@dataclass(frozen=True, slots=True)
class WeightChangeExample:
    cutoff_date: date
    target_date: date
    group_id: str
    feature_values: tuple[float | None, ...]
    target_weight_change_kg: float


@dataclass(frozen=True, slots=True)
class WeightChangeDatasetReport:
    input_history_count: int
    candidate_cutoff_dates: int
    produced_examples: int
    dropped_missing_future_target: int
    dropped_other: int
    forecast_horizon_days: int
    feature_version: str
    target_definition: str


@dataclass(frozen=True, slots=True)
class WeightChangeDataset:
    examples: tuple[WeightChangeExample, ...]
    feature_names: tuple[str, ...]
    report: WeightChangeDatasetReport


@dataclass(frozen=True, slots=True)
class WeightChangeModelMetrics:
    sample_count: int
    mean_absolute_error_kg: float | None
    root_mean_squared_error_kg: float | None
    mean_error_kg: float | None
    r_squared: float | None


@dataclass(frozen=True, slots=True)
class WeightChangeModelResult:
    name: str
    validation_metrics: WeightChangeModelMetrics
    specification: str


@dataclass(frozen=True, slots=True)
class WeightChangePredictionBenchmark:
    policy_version: str
    config: WeightChangeMlConfig
    dataset_report: WeightChangeDatasetReport
    train_group_ids: tuple[str, ...]
    validation_group_ids: tuple[str, ...]
    test_group_ids: tuple[str, ...]
    validation_results: tuple[WeightChangeModelResult, ...]
    selected_model_name: str
    selection_rule: str
    selected_model_test_metrics: WeightChangeModelMetrics
    dummy_test_metrics: WeightChangeModelMetrics
    feature_names: tuple[str, ...]
    cohort_configurations: tuple[SyntheticHistoryConfig, ...]
    assumptions: tuple[str, ...]


def build_synthetic_weight_change_dataset(
    histories: tuple[SyntheticHistory, ...] | list[SyntheticHistory],
    trend_config: TrendAnalysisConfig | None = None,
    adaptive_config: AdaptiveTdeeConfig | None = None,
    ml_config: WeightChangeMlConfig | None = None,
) -> WeightChangeDataset:
    """Build labels by exact future dates while retaining missing public feature values."""
    if not isinstance(histories, (tuple, list)) or not histories:
        raise WeightChangeMlError(
            "histories must be a non-empty list or tuple of SyntheticHistory instances."
        )
    if not all(isinstance(history, SyntheticHistory) for history in histories):
        raise WeightChangeMlError("histories must contain SyntheticHistory instances.")
    trend = trend_config if trend_config is not None else TrendAnalysisConfig()
    adaptive = adaptive_config if adaptive_config is not None else AdaptiveTdeeConfig()
    config = ml_config if ml_config is not None else WeightChangeMlConfig()
    if (
        not isinstance(trend, TrendAnalysisConfig)
        or not isinstance(adaptive, AdaptiveTdeeConfig)
        or not isinstance(config, WeightChangeMlConfig)
    ):
        raise WeightChangeMlError(
            "configuration values must use their corresponding FitAdapt config types."
        )
    examples: list[WeightChangeExample] = []
    candidates = missing_future = dropped_other = 0
    for history_index, history in enumerate(histories):
        truth = _truth_weights(history)
        observations = tuple(day.observation for day in history.days if day.observation is not None)
        trends = analyze_observation_trends(observations, trend)
        adaptive_by_date = {
            item.observed_on: item
            for item in estimate_adaptive_tdee(trends, adaptive).daily_estimates
        }
        for point in trends.points:
            candidates += 1
            target_date = point.observed_on + timedelta(days=config.forecast_horizon_days)
            if point.observed_on not in truth or target_date not in truth:
                missing_future += 1
                continue
            estimate = adaptive_by_date.get(point.observed_on)
            adaptive_value = (
                None
                if estimate is None or estimate.eligibility is not TdeeEligibility.AVAILABLE
                else estimate.estimated_tdee_kcal_per_day
            )
            features = (
                point.trailing_body_weight_mean_kg,
                point.trailing_energy_intake_mean_kcal,
                point.trailing_steps_mean,
                point.window_weight_change_kg,
                float(point.body_weight_contributor_count),
                float(point.energy_intake_contributor_count),
                float(point.steps_contributor_count),
                adaptive_value,
            )
            examples.append(
                WeightChangeExample(
                    point.observed_on,
                    target_date,
                    f"history_{history_index:02d}",
                    features,
                    truth[target_date] - truth[point.observed_on],
                )
            )
    report = WeightChangeDatasetReport(
        len(histories),
        candidates,
        len(examples),
        missing_future,
        dropped_other,
        config.forecast_horizon_days,
        WEIGHT_CHANGE_FEATURE_VERSION,
        "true body weight at cutoff + horizon minus true body weight at cutoff",
    )
    return WeightChangeDataset(tuple(examples), FEATURE_NAMES, report)


def run_weight_change_benchmark(
    config: WeightChangeMlConfig | None = None,
) -> WeightChangePredictionBenchmark:
    """Run fixed cohort training, validation selection, and one held-out test evaluation."""
    effective = config if config is not None else WeightChangeMlConfig()
    if not isinstance(effective, WeightChangeMlConfig):
        raise WeightChangeMlError("config must be a WeightChangeMlConfig or None.")
    cohort_configs = _cohort_configurations()
    dataset = build_synthetic_weight_change_dataset(
        tuple(generate_synthetic_history(item) for item in cohort_configs), ml_config=effective
    )
    groups = tuple(f"history_{index:02d}" for index in range(len(cohort_configs)))
    train_groups, validation_groups, test_groups = groups[:18], groups[18:24], groups[24:]
    partitions = (
        _rows(dataset, train_groups),
        _rows(dataset, validation_groups),
        _rows(dataset, test_groups),
    )
    if not all(len(partition[0]) for partition in partitions):
        raise WeightChangeMlError("each group partition must contain at least one example.")
    train, validation, test = partitions
    candidates = _pipelines(effective)
    validation_results: list[WeightChangeModelResult] = []
    fitted: dict[str, Pipeline] = {}
    for name, pipeline, specification in candidates:
        pipeline.fit(*train)
        fitted[name] = pipeline
        validation_results.append(
            WeightChangeModelResult(
                name, _metrics(validation[1], pipeline.predict(validation[0])), specification
            )
        )
    selected = _select_model(tuple(validation_results))
    return WeightChangePredictionBenchmark(
        WEIGHT_CHANGE_ML_POLICY_VERSION,
        effective,
        dataset.report,
        train_groups,
        validation_groups,
        test_groups,
        tuple(validation_results),
        selected.name,
        "lowest non-dummy validation MAE; declared order breaks ties",
        _metrics(test[1], fitted[selected.name].predict(test[0])),
        _metrics(test[1], fitted["dummy"].predict(test[0])),
        FEATURE_NAMES,
        cohort_configs,
        ASSUMPTIONS,
    )


def _truth_weights(history: SyntheticHistory) -> dict[date, float]:
    if not history.days:
        raise WeightChangeMlError("synthetic histories must not be empty.")
    values: dict[date, float] = {}
    for day in history.days:
        if (
            not isinstance(day, SyntheticDay)
            or day.truth.observed_on in values
            or not math.isfinite(day.truth.true_body_weight_kg)
        ):
            raise WeightChangeMlError(
                "synthetic truth dates must be unique with finite body weights."
            )
        values[day.truth.observed_on] = float(day.truth.true_body_weight_kg)
    return values


def _rows(dataset: WeightChangeDataset, groups: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    items = tuple(item for item in dataset.examples if item.group_id in groups)
    return np.asarray(
        [[np.nan if value is None else value for value in item.feature_values] for item in items],
        dtype=float,
    ), np.asarray([item.target_weight_change_kg for item in items], dtype=float)


def _pipelines(config: WeightChangeMlConfig) -> tuple[tuple[str, Pipeline, str], ...]:
    def imputer() -> SimpleImputer:
        return SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)

    return (
        (
            "dummy",
            Pipeline([("imputer", imputer()), ("model", DummyRegressor(strategy="mean"))]),
            "median imputer + missing indicators + DummyRegressor(mean)",
        ),
        (
            "linear",
            Pipeline(
                [
                    ("imputer", imputer()),
                    ("scaler", StandardScaler()),
                    ("model", LinearRegression()),
                ]
            ),
            "median imputer + missing indicators + scaler + LinearRegression",
        ),
        (
            "ridge",
            Pipeline(
                [
                    ("imputer", imputer()),
                    ("scaler", StandardScaler()),
                    ("model", Ridge(alpha=config.ridge_alpha)),
                ]
            ),
            f"median imputer + missing indicators + scaler + Ridge(alpha={config.ridge_alpha})",
        ),
        (
            "random_forest",
            Pipeline(
                [
                    ("imputer", imputer()),
                    (
                        "model",
                        RandomForestRegressor(
                            n_estimators=config.random_forest_estimators,
                            random_state=config.random_seed,
                            n_jobs=1,
                        ),
                    ),
                ]
            ),
            "median imputer + missing indicators + "
            f"RandomForestRegressor(random_state={config.random_seed})",
        ),
    )


def _metrics(truth: np.ndarray, predictions: np.ndarray) -> WeightChangeModelMetrics:
    if len(truth) == 0 or len(truth) != len(predictions):
        raise WeightChangeMlError("metrics require non-empty, equal-length truth and predictions.")
    errors = predictions - truth
    count = len(truth)
    r_squared = None if count < 2 or np.ptp(truth) == 0 else float(r2_score(truth, predictions))
    return WeightChangeModelMetrics(
        int(count),
        float(mean_absolute_error(truth, predictions)),
        float(math.sqrt(mean_squared_error(truth, predictions))),
        float(np.mean(errors)),
        r_squared,
    )


def _select_model(results: tuple[WeightChangeModelResult, ...]) -> WeightChangeModelResult:
    """Select solely from declared-order non-dummy validation results."""
    selectable = tuple(item for item in results if item.name != "dummy")
    if not selectable:
        raise WeightChangeMlError("validation results must contain a non-dummy candidate.")
    if any(
        isinstance(item.validation_metrics.mean_absolute_error_kg, bool)
        or not isinstance(item.validation_metrics.mean_absolute_error_kg, (int, float))
        or not math.isfinite(item.validation_metrics.mean_absolute_error_kg)
        for item in selectable
    ):
        raise WeightChangeMlError("selectable validation results require a finite numeric MAE.")
    return min(selectable, key=lambda item: item.validation_metrics.mean_absolute_error_kg)


def _cohort_configurations() -> tuple[SyntheticHistoryConfig, ...]:
    return tuple(
        SyntheticHistoryConfig(
            date(2026, 1, 1),
            70,
            500 + index,
            65.0 + index % 20,
            1800.0 + (index % 6) * 120,
            2100.0 + (index % 7) * 110,
            intake_standard_deviation_kcal=60.0 + (index % 3) * 30,
            average_steps=4000.0 + (index % 8) * 700,
            steps_standard_deviation=300.0 + (index % 4) * 150,
            scale_weight_noise_standard_deviation_kg=0.1 + (index % 3) * 0.1,
            calorie_logging_bias_kcal=(-100.0, 0.0, 100.0)[index % 3],
            calorie_logging_error_standard_deviation_kcal=40.0 + (index % 3) * 30,
            steps_observation_noise_standard_deviation=100.0 + (index % 3) * 100,
            missing_weight_probability=0.05 + (index % 3) * 0.03,
            missing_nutrition_probability=0.05 + (index % 4) * 0.02,
            missing_activity_probability=0.05 + (index % 2) * 0.04,
        )
        for index in range(30)
    )
