# Synthetic TDEE Evaluation

`tdee_evaluation_v1` compares two production estimators against known synthetic expenditure. It
uses hidden truth only after calculating estimates, so production trends and adaptive TDEE remain
unaware of synthetic internals.

```text
Profile -> static baseline -----------------+
                                             +-> evaluation metrics
Observations -> trends -> adaptive TDEE -----+
                                             |
Synthetic hidden truth ----------------------+
```

## Fair Comparison

Static baseline metrics are calculated on every synthetic day. Adaptive estimates are unavailable
during trend warm-up and when required observed features are missing. Therefore paired baseline
and paired adaptive metrics are both calculated only for the exact dates carrying an eligible
adaptive daily estimate. Dates are joined by `datetime.date`, never tuple position.

Adaptive coverage is eligible dates divided by all synthetic days. The optional post-warm-up ratio
uses the number of dates from the first theoretically eligible index onward: `window_size_days +
minimum_observations - 1`. Missing data can still reduce this coverage.

For aligned prediction/truth pairs, the unrounded metrics are:

```text
error      = prediction - truth
MAE        = mean(abs(error))
RMSE       = sqrt(mean(error^2))
mean error = mean(error)

percentage MAE improvement = (paired baseline MAE - paired adaptive MAE)
                             / paired baseline MAE * 100
```

Positive percentage improvement means adaptive has lower paired MAE; a negative value means it is
worse. If paired baseline MAE is zero, percentage improvement is `None` because division is
undefined. Empty comparison sets report sample count zero and `None` errors rather than zero error.
The absolute MAE difference records only magnitude; percentage improvement retains direction.

## Benchmark Suite

`run_tdee_benchmark_suite()` runs these fixed-seed scenarios in this order:

1. `clean_constant_expenditure`: no random variation, observation noise, missingness, exercise
   variation, or logging bias. With full rolling windows, adaptive recovers the known synthetic
   daily expenditure within floating-point precision.
2. `noisy_observations`: scale, calorie logging, and step observation noise without systematic
   logging bias.
3. `missing_data`: nonzero weight, nutrition, and activity missingness.
4. `calorie_underreporting`: controlled negative systematic logged-intake bias; adaptive error
   tends downward.
5. `calorie_overreporting`: controlled positive systematic logged-intake bias; adaptive error
   tends upward and can be worse than a near-matching static baseline.
6. `baseline_mismatch`: true synthetic expenditure differs materially from static formula TDEE.

The logging-bias scenarios use `synthetic_history_v2`: observed intake is true intake plus signed
systematic bias plus zero-mean random logging error, clamped at zero. Bias is not noise.

```python
from fitadapt.evaluation import run_tdee_benchmark_suite

for item in run_tdee_benchmark_suite().scenario_results:
    metrics = item.evaluation.paired_adaptive_metrics
    print(item.scenario.name, metrics.sample_count, metrics.mean_absolute_error_kcal_per_day)
```

## Limitations

Benchmark results measure estimator recovery only inside this linear synthetic policy. They do not
prove that the baseline, adaptive estimator, intake logs, or `7,700 kcal/kg` approximation model a
real person. Water, glycogen, food logging behavior, metabolic adaptation, body composition, and
other physiology remain unmodelled. Overlapping adaptive estimates are correlated, so aggregate
metrics are descriptive rather than independent statistical evidence.
