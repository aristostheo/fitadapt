# V0.1 Architecture

V0.1 keeps the scientific core independent of databases, frameworks, and user interfaces.
The initial execution path is intentionally small:

```text
Validated user profile
        |
        v
Versioned deterministic baseline calculations
        |
        v
Transparent baseline estimate and assumptions
```

The `UserProfile` domain model validates its inputs before they reach any calculation code.
The baseline package now performs a pure, versioned calculation:

```text
UserProfile -> Mifflin-St Jeor REE -> activity multiplier -> BaselineEnergyEstimate
```

`BaselineEnergyEstimate` preserves full calculation precision and records both formula and
activity-policy versions. REE is an estimate of resting energy expenditure; TDEE is that estimate
adjusted by a rough population-level activity multiplier. Goal and requested weekly change are
validated profile inputs but do not affect energy estimates until the calorie-target checkpoint.

The activity multipliers are intentionally isolated from the REE formula because they represent
a separate, weaker static assumption. The adaptive-estimation layer is intended to improve on
these population-level assumptions using reliable longitudinal observations.

The target layer composes, rather than copies, `BaselineEnergyEstimate`:

```text
Validated profile
    -> estimated REE and baseline TDEE
    -> signed daily calorie adjustment
    -> daily calorie target
    -> protein and fat allocation
    -> remaining calories assigned to carbohydrates
    -> CalorieTargetEstimate
```

It uses a versioned `7,700 kcal/kg` planning approximation and a separate, versioned macro
policy. These deterministic outputs are distinct from personalized/adaptive estimates and
recommendations. If protein and fat cannot fit within a target, the policy raises an explicit error
instead of producing negative carbohydrates or silently changing inputs.

## Daily Observation Boundary

`UserProfile` represents relatively stable user settings and a selected goal. `DailyObservation`
represents partial measurements captured for one calendar date. Its optional fields preserve the
distinction between missing (`None`) and an observed zero; it does not fill, infer, or derive
values.

Daily observations remain upstream of trend, data-quality, adaptive-estimation, and modelling
layers. They do not reconcile nutrition totals or reject future dates, because those behaviours
would introduce assumptions about logging and the current clock into the domain model.

## Calendar Trend Boundary

The analysis layer reindexes observations onto continuous calendar dates, calculates trailing-only
rolling features, and reports completeness with all calendar days as denominators. It does not
impute values, predict outcomes, or personalize estimates.

## Current Calculation Paths

```text
UserProfile
    -> baseline REE/TDEE
    -> baseline calorie and macro targets

DailyObservation history
    -> calendar-aware trends
    -> adaptive TDEE estimate
```

The adaptive result is an observed-data estimate only. It does not overwrite the baseline estimate,
change calorie or macro targets, or generate recommendations. Future layers include predictive
models, recommendation policy, storage, and APIs.

## Synthetic Evaluation Boundary

The evaluation layer is the only non-test layer permitted to compare production estimates with
synthetic hidden truth. It builds trends and adaptive estimates from `DailyObservation` values
only, then aligns eligible adaptive estimates to hidden truth by exact `datetime.date` afterward.

```text
Profile -> static baseline -----------------+
                                             +-> evaluation metrics
Observations -> trends -> adaptive TDEE -----+
                                             |
Synthetic hidden truth ----------------------+
```

Hidden truth must never enter production trend or adaptive estimation. Baseline-all-days metrics
use every synthetic truth date; paired baseline and adaptive metrics use the same adaptive-eligible
dates. This boundary supports controlled synthetic evaluation, not real-world validation.

## Synthetic Data Boundary

Synthetic generation is an in-memory test/development layer, not a source of real-world evidence:

```text
Simulation configuration
          -> hidden daily truth
          -> noise and missingness
          -> DailyObservation or no observation
```

`SyntheticHistory` retains hidden truth for evaluation, while future estimators must consume only
the noisy observations. A seed-scoped NumPy generator makes results reproducible. The simulator is
deliberately linear and does not model metabolic adaptation, body composition, or other complex
physiology.

Future predictive models, recommendation policy, storage, and API layers will remain separate.
They must consume the core through typed inputs and outputs, not embed calculation rules themselves.

## Data and privacy boundary

No personal fitness or health-adjacent data belongs in this repository. Future local datasets
will be ignored under `data/private/`; synthetic data will be explicitly labelled as synthetic.
