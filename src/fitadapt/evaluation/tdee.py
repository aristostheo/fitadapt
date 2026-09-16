"""Date-aligned, synthetic-only evaluation of baseline and adaptive TDEE estimates."""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

from fitadapt.adaptive.tdee import (
    ADAPTIVE_TDEE_POLICY_VERSION,
    AdaptiveTdeeConfig,
    TdeeEligibility,
    estimate_adaptive_tdee,
)
from fitadapt.analysis.trends import (
    TREND_ANALYSIS_POLICY_VERSION,
    TrendAnalysisConfig,
    analyze_observation_trends,
)
from fitadapt.baseline.energy import BaselineEnergyEstimate, calculate_baseline_energy
from fitadapt.domain.profile import (
    ActivityLevel,
    Goal,
    SexForMifflinEquation,
    UserProfile,
)
from fitadapt.synthetic.history import (
    SyntheticDay,
    SyntheticHistory,
    SyntheticHistoryConfig,
    generate_synthetic_history,
)

TDEE_EVALUATION_POLICY_VERSION = "tdee_evaluation_v1"
TDEE_EVALUATION_ASSUMPTIONS = (
    "Synthetic hidden truth is used only after production estimates are calculated.",
    "Paired baseline and adaptive metrics use exactly the adaptive eligible dates.",
    "Overlapping adaptive daily estimates are correlated, so metrics are descriptive rather than "
    "independent evidence.",
    "Synthetic benchmark results do not establish clinical or real-world accuracy.",
)


class TdeeEvaluationError(ValueError):
    """Raised when an evaluation input cannot support an unambiguous comparison."""


@dataclass(frozen=True, slots=True)
class TdeeErrorMetrics:
    """Unrounded prediction-minus-truth error summary for aligned daily values."""

    sample_count: int
    mean_absolute_error_kcal_per_day: float | None
    root_mean_squared_error_kcal_per_day: float | None
    mean_error_kcal_per_day: float | None


@dataclass(frozen=True, slots=True)
class TdeeEvaluationResult:
    """Transparent evaluation output for one profile and synthetic history."""

    policy_version: str
    total_synthetic_days: int
    days_with_observations: int
    adaptive_eligible_dates: tuple[date, ...]
    paired_evaluated_dates: tuple[date, ...]
    adaptive_coverage_ratio: float
    adaptive_coverage_after_warmup_ratio: float | None
    baseline_all_days_metrics: TdeeErrorMetrics
    paired_baseline_metrics: TdeeErrorMetrics
    paired_adaptive_metrics: TdeeErrorMetrics
    absolute_mae_difference_kcal_per_day: float | None
    percentage_mae_improvement: float | None
    baseline_estimate: BaselineEnergyEstimate
    trend_policy_version: str
    adaptive_policy_version: str
    synthetic_policy_version: str
    assumptions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TdeeBenchmarkScenario:
    """One inspectable deterministic synthetic benchmark definition."""

    name: str
    description: str
    profile: UserProfile
    synthetic_config: SyntheticHistoryConfig
    trend_config: TrendAnalysisConfig
    adaptive_config: AdaptiveTdeeConfig


@dataclass(frozen=True, slots=True)
class TdeeBenchmarkScenarioResult:
    """A benchmark definition paired with its reproducible evaluation result."""

    scenario: TdeeBenchmarkScenario
    evaluation: TdeeEvaluationResult


@dataclass(frozen=True, slots=True)
class TdeeBenchmarkSuiteResult:
    """Ordered output from the documented benchmark scenario suite."""

    policy_version: str
    scenario_results: tuple[TdeeBenchmarkScenarioResult, ...]
    assumptions: tuple[str, ...]


def calculate_tdee_error_metrics(
    predictions_kcal_per_day: Sequence[float], truth_kcal_per_day: Sequence[float]
) -> TdeeErrorMetrics:
    """Calculate MAE, RMSE, and signed mean error for exactly aligned values."""
    if len(predictions_kcal_per_day) != len(truth_kcal_per_day):
        raise TdeeEvaluationError("predictions and truth must have equal lengths.")
    predictions = _validated_values(predictions_kcal_per_day, "predictions_kcal_per_day")
    truths = _validated_values(truth_kcal_per_day, "truth_kcal_per_day")
    if not predictions:
        return TdeeErrorMetrics(0, None, None, None)
    errors = [prediction - truth for prediction, truth in zip(predictions, truths, strict=True)]
    count = len(errors)
    return TdeeErrorMetrics(
        sample_count=count,
        mean_absolute_error_kcal_per_day=sum(abs(error) for error in errors) / count,
        root_mean_squared_error_kcal_per_day=math.sqrt(sum(error**2 for error in errors) / count),
        mean_error_kcal_per_day=sum(errors) / count,
    )


def evaluate_tdee_estimators(
    profile: UserProfile,
    history: SyntheticHistory,
    trend_config: TrendAnalysisConfig | None = None,
    adaptive_config: AdaptiveTdeeConfig | None = None,
) -> TdeeEvaluationResult:
    """Evaluate public static and adaptive estimators against synthetic truth by date."""
    if not isinstance(profile, UserProfile):
        raise TdeeEvaluationError("profile must be a UserProfile.")
    if not isinstance(history, SyntheticHistory):
        raise TdeeEvaluationError("history must be a SyntheticHistory.")
    if trend_config is not None and not isinstance(trend_config, TrendAnalysisConfig):
        raise TdeeEvaluationError("trend_config must be a TrendAnalysisConfig or None.")
    if adaptive_config is not None and not isinstance(adaptive_config, AdaptiveTdeeConfig):
        raise TdeeEvaluationError("adaptive_config must be an AdaptiveTdeeConfig or None.")

    truth_by_date = _truth_by_date(history)
    effective_trend_config = trend_config if trend_config is not None else TrendAnalysisConfig()
    effective_adaptive_config = (
        adaptive_config if adaptive_config is not None else AdaptiveTdeeConfig()
    )
    observations = _observations(history.days)
    trend_result = analyze_observation_trends(observations, effective_trend_config)
    adaptive_result = estimate_adaptive_tdee(trend_result, effective_adaptive_config)
    baseline_estimate = calculate_baseline_energy(profile)
    eligible_estimates = tuple(
        estimate
        for estimate in adaptive_result.daily_estimates
        if estimate.eligibility is TdeeEligibility.AVAILABLE
    )
    eligible_dates = tuple(estimate.observed_on for estimate in eligible_estimates)
    adaptive_predictions = tuple(
        _required_finite(estimate.estimated_tdee_kcal_per_day, "adaptive TDEE")
        for estimate in eligible_estimates
    )
    paired_truth = tuple(_truth_for_date(truth_by_date, item_date) for item_date in eligible_dates)
    baseline_all_truth = tuple(truth_by_date[item_date] for item_date in sorted(truth_by_date))
    baseline_all_metrics = calculate_tdee_error_metrics(
        (baseline_estimate.estimated_tdee_kcal_per_day,) * len(baseline_all_truth),
        baseline_all_truth,
    )
    paired_baseline_metrics = calculate_tdee_error_metrics(
        (baseline_estimate.estimated_tdee_kcal_per_day,) * len(paired_truth), paired_truth
    )
    paired_adaptive_metrics = calculate_tdee_error_metrics(adaptive_predictions, paired_truth)
    baseline_mae = paired_baseline_metrics.mean_absolute_error_kcal_per_day
    adaptive_mae = paired_adaptive_metrics.mean_absolute_error_kcal_per_day
    absolute_mae_difference = (
        None if baseline_mae is None or adaptive_mae is None else abs(baseline_mae - adaptive_mae)
    )
    percentage_improvement = (
        None
        if baseline_mae is None or adaptive_mae is None or baseline_mae == 0.0
        else (baseline_mae - adaptive_mae) / baseline_mae * 100.0
    )
    total_days = len(history.days)
    first_theoretically_eligible_index = (
        effective_trend_config.window_size_days + effective_trend_config.minimum_observations - 1
    )
    warmup_denominator = max(total_days - first_theoretically_eligible_index, 0)
    return TdeeEvaluationResult(
        policy_version=TDEE_EVALUATION_POLICY_VERSION,
        total_synthetic_days=total_days,
        days_with_observations=len(observations),
        adaptive_eligible_dates=eligible_dates,
        paired_evaluated_dates=eligible_dates,
        adaptive_coverage_ratio=len(eligible_dates) / total_days,
        adaptive_coverage_after_warmup_ratio=(
            None if warmup_denominator == 0 else len(eligible_dates) / warmup_denominator
        ),
        baseline_all_days_metrics=baseline_all_metrics,
        paired_baseline_metrics=paired_baseline_metrics,
        paired_adaptive_metrics=paired_adaptive_metrics,
        absolute_mae_difference_kcal_per_day=absolute_mae_difference,
        percentage_mae_improvement=percentage_improvement,
        baseline_estimate=baseline_estimate,
        trend_policy_version=TREND_ANALYSIS_POLICY_VERSION,
        adaptive_policy_version=ADAPTIVE_TDEE_POLICY_VERSION,
        synthetic_policy_version=history.simulation_policy_version,
        assumptions=TDEE_EVALUATION_ASSUMPTIONS,
    )


def run_tdee_benchmark_suite(
    scenarios: Iterable[TdeeBenchmarkScenario] = (),
) -> TdeeBenchmarkSuiteResult:
    """Run supplied scenarios, or the documented default suite, in declared order."""
    supplied_scenarios = tuple(scenarios)
    effective_scenarios = TDEE_BENCHMARK_SCENARIOS if not supplied_scenarios else supplied_scenarios
    _validate_scenarios(effective_scenarios)
    return TdeeBenchmarkSuiteResult(
        policy_version=TDEE_EVALUATION_POLICY_VERSION,
        scenario_results=tuple(
            TdeeBenchmarkScenarioResult(
                scenario=scenario,
                evaluation=evaluate_tdee_estimators(
                    scenario.profile,
                    generate_synthetic_history(scenario.synthetic_config),
                    scenario.trend_config,
                    scenario.adaptive_config,
                ),
            )
            for scenario in effective_scenarios
        ),
        assumptions=TDEE_EVALUATION_ASSUMPTIONS,
    )


def _validated_values(values: Sequence[float], field_name: str) -> tuple[float, ...]:
    normalized: list[float] = []
    for value in values:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise TdeeEvaluationError(f"{field_name} must contain only finite non-boolean numbers.")
        normalized.append(float(value))
    return tuple(normalized)


def _truth_by_date(history: SyntheticHistory) -> dict[date, float]:
    if not history.days:
        raise TdeeEvaluationError("history must contain at least one synthetic day.")
    truth: dict[date, float] = {}
    for item in history.days:
        if not isinstance(item, SyntheticDay):
            raise TdeeEvaluationError("history.days must contain SyntheticDay instances.")
        item_date = item.truth.observed_on
        if item_date in truth:
            raise TdeeEvaluationError("synthetic truth dates must be unique.")
        truth[item_date] = _required_finite(
            item.truth.true_daily_energy_expenditure_kcal, "true daily expenditure"
        )
    return truth


def _observations(days: tuple[SyntheticDay, ...]) -> tuple:
    observations = []
    for item in days:
        if item.observation is not None:
            observations.append(item.observation)
    return tuple(observations)


def _truth_for_date(truth_by_date: dict[date, float], item_date: date) -> float:
    try:
        return truth_by_date[item_date]
    except KeyError as error:
        raise TdeeEvaluationError(
            f"adaptive estimate date {item_date.isoformat()} is missing from synthetic truth."
        ) from error


def _required_finite(value: float | None, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise TdeeEvaluationError(f"{field_name} must be a finite non-boolean number.")
    return float(value)


def _validate_scenarios(scenarios: tuple[TdeeBenchmarkScenario, ...]) -> None:
    names: set[str] = set()
    for scenario in scenarios:
        if not isinstance(scenario, TdeeBenchmarkScenario):
            raise TdeeEvaluationError("scenarios must contain TdeeBenchmarkScenario instances.")
        if scenario.name in names:
            raise TdeeEvaluationError("benchmark scenario names must be unique.")
        names.add(scenario.name)


def _profile() -> UserProfile:
    return UserProfile(
        age_years=30,
        height_cm=180.0,
        weight_kg=80.0,
        sex_for_mifflin_equation=SexForMifflinEquation.MALE,
        activity_level=ActivityLevel.MODERATELY_ACTIVE,
        goal=Goal.MAINTAIN,
        requested_weekly_change_kg=0.0,
    )


def _synthetic_config(
    *, seed: int, base_expenditure: float, **changes: float | int
) -> SyntheticHistoryConfig:
    values: dict[str, float | int | date] = {
        "start_date": date(2026, 1, 1),
        "days": 60,
        "seed": seed,
        "initial_true_weight_kg": 80.0,
        "base_daily_expenditure_kcal": base_expenditure,
        "average_energy_intake_kcal": 2500.0,
        "average_steps": 1000.0,
    }
    values.update(changes)
    return SyntheticHistoryConfig(**values)  # type: ignore[arg-type]


_DEFAULT_TREND_CONFIG = TrendAnalysisConfig(window_size_days=7, minimum_observations=7)
_DEFAULT_ADAPTIVE_CONFIG = AdaptiveTdeeConfig(aggregation_window_days=14, minimum_estimate_points=4)

TDEE_BENCHMARK_SCENARIOS = (
    TdeeBenchmarkScenario(
        "clean_constant_expenditure",
        "No noise, missingness, exercise variation, or logging bias.",
        _profile(),
        _synthetic_config(
            seed=101,
            base_expenditure=2000.0,
            intake_standard_deviation_kcal=0.0,
            steps_standard_deviation=0.0,
            strength_training_probability=0.0,
            strength_training_minutes=0.0,
            cardio_probability=0.0,
            cardio_minutes=0.0,
            scale_weight_noise_standard_deviation_kg=0.0,
            calorie_logging_error_standard_deviation_kcal=0.0,
            steps_observation_noise_standard_deviation=0.0,
            missing_weight_probability=0.0,
            missing_nutrition_probability=0.0,
            missing_activity_probability=0.0,
            calorie_logging_bias_kcal=0.0,
        ),
        _DEFAULT_TREND_CONFIG,
        _DEFAULT_ADAPTIVE_CONFIG,
    ),
    TdeeBenchmarkScenario(
        "noisy_observations",
        "Scale, intake, and steps include random observation noise without logging bias.",
        _profile(),
        _synthetic_config(
            seed=102,
            base_expenditure=2100.0,
            missing_weight_probability=0.0,
            missing_nutrition_probability=0.0,
            missing_activity_probability=0.0,
        ),
        _DEFAULT_TREND_CONFIG,
        _DEFAULT_ADAPTIVE_CONFIG,
    ),
    TdeeBenchmarkScenario(
        "missing_data",
        "Nonzero missing weight, nutrition, and activity probabilities reduce available "
        "observations.",
        _profile(),
        _synthetic_config(
            seed=103,
            base_expenditure=2100.0,
            missing_weight_probability=0.25,
            missing_nutrition_probability=0.2,
            missing_activity_probability=0.2,
        ),
        TrendAnalysisConfig(window_size_days=7, minimum_observations=4),
        _DEFAULT_ADAPTIVE_CONFIG,
    ),
    TdeeBenchmarkScenario(
        "calorie_underreporting",
        "Controlled negative systematic logged-intake bias.",
        _profile(),
        _synthetic_config(
            seed=104,
            base_expenditure=2040.0,
            intake_standard_deviation_kcal=0.0,
            steps_standard_deviation=0.0,
            strength_training_probability=0.0,
            cardio_probability=0.0,
            scale_weight_noise_standard_deviation_kg=0.0,
            calorie_logging_error_standard_deviation_kcal=0.0,
            steps_observation_noise_standard_deviation=0.0,
            missing_weight_probability=0.0,
            missing_nutrition_probability=0.0,
            missing_activity_probability=0.0,
            calorie_logging_bias_kcal=-250.0,
        ),
        _DEFAULT_TREND_CONFIG,
        _DEFAULT_ADAPTIVE_CONFIG,
    ),
    TdeeBenchmarkScenario(
        "calorie_overreporting",
        "Controlled positive systematic logged-intake bias.",
        _profile(),
        _synthetic_config(
            seed=105,
            base_expenditure=2669.0,
            intake_standard_deviation_kcal=0.0,
            steps_standard_deviation=0.0,
            strength_training_probability=0.0,
            cardio_probability=0.0,
            scale_weight_noise_standard_deviation_kg=0.0,
            calorie_logging_error_standard_deviation_kcal=0.0,
            steps_observation_noise_standard_deviation=0.0,
            missing_weight_probability=0.0,
            missing_nutrition_probability=0.0,
            missing_activity_probability=0.0,
            calorie_logging_bias_kcal=250.0,
        ),
        _DEFAULT_TREND_CONFIG,
        _DEFAULT_ADAPTIVE_CONFIG,
    ),
    TdeeBenchmarkScenario(
        "baseline_mismatch",
        "True expenditure is intentionally well above the profile-derived static baseline.",
        _profile(),
        _synthetic_config(
            seed=106,
            base_expenditure=3000.0,
            intake_standard_deviation_kcal=0.0,
            steps_standard_deviation=0.0,
            strength_training_probability=0.0,
            cardio_probability=0.0,
            scale_weight_noise_standard_deviation_kg=0.0,
            calorie_logging_error_standard_deviation_kcal=0.0,
            steps_observation_noise_standard_deviation=0.0,
            missing_weight_probability=0.0,
            missing_nutrition_probability=0.0,
            missing_activity_probability=0.0,
        ),
        _DEFAULT_TREND_CONFIG,
        _DEFAULT_ADAPTIVE_CONFIG,
    ),
)
