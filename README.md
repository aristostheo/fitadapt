# FitAdapt

FitAdapt is a standalone, transparent fitness-intelligence engine. It currently produces a
deterministic REE and static baseline TDEE estimate. It is not medical advice and does not
make guarantees about body-weight change or true energy expenditure.

## V0.1 scope

V0.1 currently includes typed profile validation plus deterministic REE and baseline TDEE
calculations. Calorie targets, macros, adaptive estimation, machine learning, personal
datasets, persistence, APIs, and recommendations remain out of scope until later checkpoints.

The baseline uses rough population-level activity assumptions. It is intended as a starting
point; a future adaptive estimator will use reliable longitudinal observations to personalize
the estimate.

## Calculation contract

The core calculation will require `requested_weekly_change_kg` explicitly:

- Cut: strictly negative and no less than `-0.75%` of body weight per week.
- Maintain: exactly `0`.
- Gain: strictly positive and no greater than `+0.5%` of body weight per week.

The calculated daily calorie adjustment follows the same signed convention: negative for a
deficit, zero for maintenance, and positive for a surplus. A future interface may suggest
starting examples of `-0.5%` per week for a cut and `+0.25%` per week for a gain, but the
V0.1 engine will not silently provide defaults.

V0.1 accepts adults ages 18 through 80. This is a current product-scope limitation, not a
claim that the formulas immediately cease to apply outside those ages.

## Static energy baseline

- REE is estimated with Mifflin-St Jeor, versioned as `mifflin_st_jeor_v1`:
  `10 * weight_kg + 6.25 * height_cm - 5 * age_years`, then `+5` for the equation's male
  input or `-161` for its female input. It is an estimate, not a direct measurement. The
  source is Mifflin et al., ["A new predictive equation for resting energy expenditure in
  healthy individuals"](https://pubmed.ncbi.nlm.nih.gov/2305711/), *American Journal of
  Clinical Nutrition*, 1990; 51(2):241-247.
- TDEE is the estimated REE multiplied by an activity multiplier from the separate
  `activity_multipliers_v1` policy:

  | Activity level | Multiplier |
  | --- | ---: |
  | Sedentary | 1.200 |
  | Lightly active | 1.375 |
  | Moderately active | 1.550 |
  | Very active | 1.725 |
  | Extra active | 1.900 |

These multipliers are rough population-level categories and one of the weakest assumptions
in the static baseline, not precise measurements. A later adaptive estimator is intended to
improve on them.

```text
Validated UserProfile -> Mifflin-St Jeor REE -> activity multiplier -> baseline TDEE
```

`goal` and `requested_weekly_change_kg` are intentionally not used in this checkpoint. They
become relevant when a later checkpoint introduces calorie-target policy.

## Planned later assumptions

- Energy conversion: approximately `7,700 kcal/kg`, versioned as an explicit assumption.
  Actual weight change is not perfectly linear.
- Macros: a versioned policy using `1.6 g/kg/day` protein, a `0.6 g/kg/day` fat floor, and
  carbohydrates from the remaining calories. Total body weight is an imperfect basis across
  different body-composition ranges and may change in a later policy version.

If a calorie target cannot accommodate the protein and fat policy, the engine will return a
clear macro-policy-infeasible error rather than creating negative carbohydrate targets.

## Setup

FitAdapt targets Python 3.12 and uses [uv](https://docs.astral.sh/uv/) for environment and
dependency management. After installing uv:

```bash
uv sync --group dev
uv run ruff check .
uv run pytest
```

## Status

Checkpoint 3 adds versioned Mifflin-St Jeor REE and static baseline TDEE calculations. Calorie
targets and macro calculations have not been implemented yet.
