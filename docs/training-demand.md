# Training Demand And Performance Context

Checkpoint 25 adds an informational, deterministic training-demand assessment. It combines a small
questionnaire with observed steps, strength minutes, and cardio minutes. It does not change energy,
macros, target envelopes, or recommendations.

## Separation From Energy Policies

Baseline TDEE and adaptive TDEE remain the only energy-estimation systems. Training demand does not
add activity calories, estimate workout expenditure, replace either TDEE, or create training-day and
rest-day targets. It is a product-policy description of context, not a calorie-burn estimate,
training prescription, diagnosis, recovery guarantee, or performance guarantee.

## Questionnaire And Observation Evidence

`TrainingContext` records occupation activity, optional typical steps, resistance/cardio/sport
frequency and weekly minutes, recorded intensities, and primary focus. It intentionally does not
collect sport names, exercises, gyms, splits, or decorative details.

Observed evidence uses only fields actually present on `DailyObservation`: steps, strength-training
minutes, and cardio minutes. It never infers occupation, sport, intensity, focus, recovery, sleep,
weight, intake, hunger, or nutrition adherence.

A sufficiently complete observed stream replaces the questionnaire assumption for that stream.
Insufficient observed coverage falls back to questionnaire evidence instead of lowering demand.
Occupation and questionnaire sport information remain questionnaire evidence. Conflicts are retained
in ordered reason codes and are not silently erased. Assessments use a trailing 14-calendar-day
window anchored to the latest eligible observation date; future observations cannot influence an
earlier assessment.

## Missing Versus Zero

Missing means no evidence was recorded. Missing steps, strength minutes, or cardio minutes are never
converted to zero activity. An explicit zero is a valid contributor and can support a low observed
structured-training classification when coverage is sufficient.

The default observed-stream policy requires at least 4 contributors and 50% completeness in the
14-day window. Each result reports eligible calendar days, submitted observation records, contributor
count, completeness, mean, and weekly equivalent where available.

## Classification And Priorities

Demand levels are FitAdapt product-policy classifications, not universal physiological cutoffs:

- `low`: zero volume or below the moderate threshold
- `moderate`: positive volume below the high threshold
- `high`: at least 240 weighted minutes per week
- `very_high`: at least 360 weighted minutes, at least 4 training days, and substantial supporting evidence

The default thresholds are 120 moderate minutes, 240 high minutes, 360 very-high minutes, and
7,500/12,500 supporting steps per day. Intensity weights are low `1.0`, moderate `1.25`, and
vigorous `1.5`. Physically demanding occupation can support a very-high overall classification only
when high structured demand already exists. High steps alone never imply high structured training.

Resistance demand produces a future-facing protein-priority signal. Cardio and sport demand produce
a carbohydrate/performance-priority signal. These priorities do not modify current macro plans.

## API And Unified Flow

`POST /v1/training/demand` returns the complete `TrainingDemandAssessment`. It supports questionnaire-
only, observation-only, combined, and insufficient evidence. Transport failures use `422`, domain
failures use `training_domain_error` with `400`, and unexpected failures use the existing opaque `500`
error envelope.

`POST /v1/profile-intelligence` accepts optional `training_context` and returns additive
`training_assessment`. Existing requests remain valid. The assessment is current/latest only and is
not copied into progression snapshots. It may use the latest observations even when questionnaire
context is omitted.

## Policy And Limitations

The policy is versioned as `training_demand_v1`. Public bounds are conservative data-quality guards:
steps up to 100,000/day, resistance minutes up to 1,680/week, and cardio or sport minutes up to
2,100/week. They are not universal physiological limits.

Questionnaire self-report can be incomplete or inaccurate. Observation streams may be sparse. The
current observation model has no sport-specific records or recorded intensity, so sport and intensity
remain questionnaire-only. The system has no workout-calorie estimation, clinical status, or
performance guarantee.

A later checkpoint may use the reviewed assessment for training-aware protein policy, carbohydrate
policy, or possible training/rest-day strategies. Checkpoint 25 does not implement those changes.
