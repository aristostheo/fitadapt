# Personalization Lifecycle

`personalization_lifecycle_v1` is a stateless readiness assessment for the complete observation
history supplied with a call. It does not create a new TDEE estimate, a confidence score, a macro
plan, or a recommendation. Every call recomputes calendar trends and adaptive TDEE evidence, so a
new entry can update counts and completeness even when the displayed stage does not change.

## Stages

| Stage | Deterministic rule | Available evidence |
| --- | --- | --- |
| `baseline` | No body-weight and no energy-intake values exist. | Profile-only baseline calculations remain available. |
| `calibrating` | At least one weight or intake value exists, but no eligible daily adaptive estimate exists. | Calendar and completeness evidence only. |
| `early_personalized` | At least one eligible daily adaptive estimate exists, but the existing adaptive estimator has no aggregate. | Eligible-estimate count, but no new or premature TDEE is invented. |
| `personalized` | The existing adaptive estimator publishes its aggregate TDEE. | Adaptive TDEE and MAD exactly as produced by `adaptive_tdee_v1`. |

The adaptive aggregate uses its supplied `AdaptiveTdeeConfig`; by default it requires four eligible
daily estimates in its trailing 14-day aggregation window. MAD is a descriptive spread/variability
measure, not a confidence interval, certainty, or accuracy measure.

## Requirements

Requirements are ordered, machine-readable next actions rather than a score. The lifecycle only
returns requirements justified by observed evidence:

| Requirement | When it is returned |
| --- | --- |
| `add_history` | Calendar history is below the lifecycle default of 14 days. |
| `log_body_weight` | No weight is logged at baseline, or weight completeness is below the configured threshold. |
| `log_energy_intake` | No intake is logged at baseline, or intake completeness is below the configured threshold. |
| `build_weight_trend` | Some weight exists but the latest calendar point cannot yet produce a window weight change. |
| `build_intake_trend` | Some intake exists but the latest point cannot yet produce a trailing intake mean. |
| `collect_more_eligible_estimates` | At least one daily estimate exists but not enough exist for the adaptive aggregate. |

The default lifecycle completeness thresholds are 70% for body weight and intake. These thresholds
explain what to log next; they do not alter trend or adaptive-TDEE formulas. A fully personalized
result has an empty requirement tuple. `0` kcal is an observed intake value, while `null` remains
missing.

## Domain API

```python
from fitadapt.personalization.lifecycle import assess_personalization_lifecycle

result = assess_personalization_lifecycle(profile, observations)
```

The immutable result exposes stage, requirements, calendar days, weight and intake counts and
completeness ratios, eligible and required adaptive-estimate counts, optional aggregate TDEE/MAD,
all contributing policy versions, and assumptions. Duplicate dates propagate the existing
`TrendAnalysisError`; observations can otherwise be supplied unsorted. Inputs and upstream outputs
are never mutated.

## HTTP API

`POST /v1/personalization/status` accepts strict `profile` and `observations` JSON plus optional
`trend_config`, `adaptive_config`, and `lifecycle_config`. It returns JSON string enum values for
the stage and requirements, uses `null` for unavailable aggregate values, maps known domain errors
to `400`, keeps FastAPI transport validation at `422`, and documents opaque `500` errors in OpenAPI.
The endpoint stores no data.

## Boundaries And Limitations

Lifecycle readiness is not medical validation, a clinical assessment, an accuracy score, or a
guarantee that logged data is unbiased. It is sensitive to missing and inaccurate weight or intake
records, hydration and glycogen variation, and the existing adaptive estimator's assumptions.
It remains separate from Checkpoint 17 macro preferences and the calorie-recommendation policy:
it never overwrites baseline targets, adaptive results, macro plans, recommendation outputs, or
user data. FitAdapt currently has no persistence; callers must resupply history on each assessment.
