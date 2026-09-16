# Weight-Change ML Experiment

`weight_change_ml_v1` predicts true body weight at cutoff plus seven calendar days minus true body
weight at cutoff. Positive targets mean gain. Features are observation-derived trailing weight,
intake, steps, window weight change, contributor counts, and adaptive daily TDEE; hidden truth is
used only for exact-date labels and evaluation.

Thirty deterministic synthetic histories are split by complete history group: 18 train, 6
validation, and 6 test. Random row splitting would leak correlated history rows. Median imputation
with missing indicators is fitted on training data only. Linear and Ridge pipelines add scaling;
dummy and random forest do not. The lowest non-dummy validation MAE wins, then runs once on test;
dummy test MAE remains a reference.

```python
from fitadapt.ml import run_weight_change_benchmark

result = run_weight_change_benchmark()
print(
    [
        (item.name, item.validation_metrics.mean_absolute_error_kg)
        for item in result.validation_results
    ]
)
print(result.selected_model_name, result.selected_model_test_metrics.mean_absolute_error_kg)
print(result.dummy_test_metrics.mean_absolute_error_kg)
```

This is synthetic-only experimentation, not clinical validation or real-world predictive evidence.
The selected model can be interpreted without exposing a deployable estimator; see
[`model-interpretation.md`](model-interpretation.md).
