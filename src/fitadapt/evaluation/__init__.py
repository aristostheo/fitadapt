"""Synthetic-only TDEE evaluation and deterministic benchmark scenarios."""

from fitadapt.evaluation.tdee import (
    TDEE_BENCHMARK_SCENARIOS,
    TDEE_EVALUATION_POLICY_VERSION,
    TdeeBenchmarkScenario,
    TdeeBenchmarkScenarioResult,
    TdeeBenchmarkSuiteResult,
    TdeeErrorMetrics,
    TdeeEvaluationError,
    TdeeEvaluationResult,
    calculate_tdee_error_metrics,
    evaluate_tdee_estimators,
    run_tdee_benchmark_suite,
)

__all__ = [
    "TDEE_BENCHMARK_SCENARIOS",
    "TDEE_EVALUATION_POLICY_VERSION",
    "TdeeBenchmarkScenario",
    "TdeeBenchmarkScenarioResult",
    "TdeeBenchmarkSuiteResult",
    "TdeeErrorMetrics",
    "TdeeEvaluationError",
    "TdeeEvaluationResult",
    "calculate_tdee_error_metrics",
    "evaluate_tdee_estimators",
    "run_tdee_benchmark_suite",
]
