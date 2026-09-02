# FitAdapt

FitAdapt is a standalone, transparent fitness-intelligence engine. Its first milestone
creates deterministic baseline estimates for maintenance calories, calorie targets, and
macronutrients. It is not medical advice and does not make guarantees about body-weight
change.

## V0.1 scope

V0.1 is limited to typed, validated baseline calculations. Adaptive estimation, machine
learning, personal datasets, persistence, APIs, and recommendations are deliberately out
of scope until the baseline is tested.

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

## Planned assumptions

- BMR: Mifflin-St Jeor, versioned as `mifflin_st_jeor_v1`.
- TDEE: BMR multiplied by one of five explicit activity levels; these are rough assumptions,
  not precise measurements.
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

Checkpoint 1 establishes repository tooling and the V0.1 specification. No calculation
engine has been implemented yet.
